"""Local Taskfile contract tests; fake tools are not application validation."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TASK = shutil.which("go-task") or shutil.which("task")


class TaskContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copyfile(REPO / "Taskfile.yml", self.root / "Taskfile.yml")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls"
        self.env = dict(os.environ, PATH=str(self.bin), CALLS=str(self.log))
        # Only controlled fake tools and the real Python interpreter are visible.
        (self.bin / "python3").symlink_to(sys.executable)
        for tool in ("uv", "bun", "bunx", "buf"):
            self.executable(self.bin / tool, tool)
        self.put("pyproject.toml", (REPO / "pyproject.toml").read_text())
        import tomllib

        config = tomllib.loads((REPO / "pyproject.toml").read_text())
        for member in config["tool"]["uv"]["workspace"]["members"]:
            self.put(f"{member}/pyproject.toml", "[project]\n")
            self.put(f"{member}/src/example.py", "")
            self.put(f"{member}/tests/test_example.py", "")
        self.put("uv.lock", "")

    def put(self, name: str, text: str = "") -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def executable(self, path: Path, name: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "$CALLS"\n')
        path.chmod(0o755)

    def run_task(self, target: str) -> subprocess.CompletedProcess[str]:
        assert TASK is not None, "Install go-task to run these executable contracts"
        return subprocess.run(
            [TASK, *target.split()], cwd=self.root, env=self.env,
            text=True, capture_output=True, timeout=15,
        )

    def calls(self) -> str:
        return self.log.read_text() if self.log.exists() else ""

    def test_python_missing_project_fails(self) -> None:
        (self.root / "pyproject.toml").unlink()
        for target in ("py:lint", "py:format", "py:typecheck", "py:test"):
            with self.subTest(target=target):
                self.assertNotEqual(self.run_task(target).returncode, 0)
        self.assertEqual(self.calls(), "")

    def test_python_missing_test_root_fails(self) -> None:
        shutil.rmtree(self.root / "libs/py/tests")
        self.assertNotEqual(self.run_task("py:test").returncode, 0)
        self.assertEqual(self.calls(), "")

    def test_python_commands_are_frozen(self) -> None:
        for target, command in (("py:lint", "ruff check ."),
                                ("py:format", "ruff format ."),
                                ("py:typecheck", "mypy ."), ("py:test", "pytest")):
            with self.subTest(target=target):
                result = self.run_task(target)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"uv run --frozen {command}\n", self.calls())

    def test_service_missing_project_or_tests_fails(self) -> None:
        for missing in ("pyproject.toml", "tests"):
            with self.subTest(missing=missing):
                path = self.root / "services/users" / missing
                backup = path.with_name(path.name + ".hidden")
                path.rename(backup)
                try:
                    self.assertNotEqual(self.run_task("service:test SERVICE=users").returncode, 0)
                finally:
                    backup.rename(path)

    def web_fixture(self) -> None:
        for name in ("package.json", "bun.lock", "tsconfig.json", "eslint.config.mjs",
                     "src/example.test.ts", "tooling/example.test.ts"):
            self.put(f"apps/web/{name}")
        for tool in ("tsc", "eslint"):
            self.executable(self.root / f"apps/web/node_modules/.bin/{tool}", tool)

    def test_web_missing_inputs_fail_without_downloading(self) -> None:
        self.web_fixture()
        for target, name in (("web:install", "package.json"),
                             ("web:install", "bun.lock"),
                             ("web:typecheck", "node_modules/.bin/tsc"),
                             ("web:lint", "node_modules/.bin/eslint"),
                             ("web:typecheck", "tsconfig.json"),
                             ("web:lint", "eslint.config.mjs"),
                             ("web:test", "src/example.test.ts"),
                             ("web:test", "tooling/example.test.ts")):
            with self.subTest(target=target, missing=name):
                path = self.root / "apps/web" / name
                backup = path.with_name(path.name + ".hidden")
                path.rename(backup)
                try:
                    self.assertNotEqual(self.run_task(target).returncode, 0)
                finally:
                    backup.rename(path)
        self.assertEqual(self.calls(), "")

    def test_web_invocations_are_local_frozen_and_scoped(self) -> None:
        self.web_fixture()
        for target in ("web:install", "web:typecheck", "web:lint", "web:test"):
            result = self.run_task(target)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls().splitlines(), [
            "bun install --frozen-lockfile", "tsc --noEmit", "eslint ",
            "bun test ./src ./tooling",
        ])

    def test_proto_missing_config_or_tool_fails(self) -> None:
        for target in ("proto:lint", "proto:generate", "proto:breaking"):
            with self.subTest(target=target):
                (self.root / "libs/proto").mkdir(parents=True, exist_ok=True)
                self.assertNotEqual(self.run_task(target).returncode, 0)
        self.assertEqual(self.calls(), "")
        self.put("libs/proto/buf.yaml")
        self.put("libs/proto/buf.gen.yaml")
        (self.bin / "buf").unlink()
        self.assertNotEqual(self.run_task("proto:check").returncode, 0)

    def test_install_includes_frozen_python(self) -> None:
        self.web_fixture()
        result = self.run_task("install")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("uv sync --frozen\n", self.calls())

    def test_aggregate_propagates_failure(self) -> None:
        self.web_fixture()
        self.put("libs/proto/buf.yaml")
        healthy = self.run_task("check")
        self.assertEqual(healthy.returncode, 0, healthy.stderr)
        self.assertEqual(self.calls().splitlines(), [
            "eslint ", "uv run --frozen ruff check .", "buf lint",
            "tsc --noEmit", "uv run --frozen mypy .",
            "bun test ./src ./tooling", "uv run --frozen pytest", "bun run build",
        ])
        self.log.unlink()
        (self.root / "apps/web/node_modules/.bin/eslint").write_text(
            '#!/bin/sh\nprintf "eslint exit 23\\n" >> "$CALLS"\nexit 23\n'
        )
        failed = self.run_task("check")
        self.assertNotEqual(failed.returncode, 0, failed.stderr)
        self.assertIn('"web:lint"', failed.stderr)
        self.assertIn("exit status 23", failed.stderr)
        self.assertEqual(self.calls().splitlines(), ["eslint exit 23"])


if __name__ == "__main__":
    unittest.main()
