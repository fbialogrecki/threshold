"""Executable, dependency-free regressions for the required CI gate."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("python-quality", "security", "containers")


class RequiredResultsTests(unittest.TestCase):
    def run_gate(self, payload: str | None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.pop("REQUIRED_RESULTS", None)
        if payload is not None:
            env["REQUIRED_RESULTS"] = payload
        return subprocess.run(
            [sys.executable, str(ROOT / "ci/check-required-results.py")],
            env=env, capture_output=True, text=True, check=False,
        )

    def test_only_all_expected_successes_pass(self) -> None:
        good = {name: {"result": "success"} for name in REQUIRED}
        self.assertEqual(self.run_gate(json.dumps(good)).returncode, 0)
        for name in REQUIRED:
            for state in ("failure", "cancelled", "skipped", "unknown", "", None, True, 0):
                with self.subTest(name=name, state=state):
                    bad = {**good, name: {"result": state}}
                    self.assertNotEqual(self.run_gate(json.dumps(bad)).returncode, 0)
            replacements: tuple[object, ...] = ({}, None, [], "success")
            for replacement in replacements:
                with self.subTest(name=name, replacement=replacement):
                    self.assertNotEqual(
                        self.run_gate(json.dumps({**good, name: replacement})).returncode, 0,
                    )
            missing = good.copy()
            del missing[name]
            self.assertNotEqual(self.run_gate(json.dumps(missing)).returncode, 0)

    def test_missing_malformed_and_wrong_shape_fail(self) -> None:
        for payload in (None, "", "{", "null", "[]", '"success"', "true", "1", "{}"):
            with self.subTest(payload=payload):
                self.assertNotEqual(self.run_gate(payload).returncode, 0)


class ShellSyntaxTests(unittest.TestCase):
    def run_check(self, *paths: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(ROOT / "ci/check-shell-syntax.sh"), *map(str, paths)],
            capture_output=True, text=True, check=False,
        )

    def test_checks_every_file_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            sentinel = directory / "must not exist"
            valid = directory / "valid first.sh"
            valid.write_text(f'touch "{sentinel}"\n')
            second = directory / "second file.sh"
            second.write_text("if then\n")
            # Demonstrate the old command ignores the second script entirely.
            old = subprocess.run(
                ["bash", "-n", str(valid), str(second)],
                capture_output=True, check=False,
            )
            self.assertEqual(old.returncode, 0)
            self.assertNotEqual(self.run_check(valid, second).returncode, 0)
            second.write_text("printf 'valid\\n'\n")
            self.assertEqual(self.run_check(valid, second).returncode, 0)
            self.assertFalse(sentinel.exists())
            self.assertNotEqual(self.run_check(valid, directory / "missing.sh").returncode, 0)
            self.assertNotEqual(self.run_check(directory).returncode, 0)

    def test_empty_selection_fails(self) -> None:
        self.assertNotEqual(self.run_check().returncode, 0)


class WorkflowWiringTests(unittest.TestCase):
    def test_required_gate_and_independent_quality(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        # Deliberately scoped to this workflow's two-space job layout, not a YAML parser.
        jobs = dict(re.findall(
            r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)",
            workflow.split("jobs:\n", 1)[1], re.M | re.S,
        ))
        self.assertIn("python-quality", jobs)
        quality = jobs["python-quality"]
        self.assertNotRegex(quality, r"(?m)^    (needs|if):")
        for command in ("uv sync --frozen", "uv run --frozen ruff check .",
                        "uv run --frozen mypy .", "uv run --frozen pytest -q",
                        "uv export --frozen", "pip-audit --strict",
                        "uv run --frozen python ci/verify-pip-audit.py"):
            self.assertIn(command, quality)
        gate = jobs["python"]
        self.assertIn("    if: always()\n", gate)
        self.assertIn("    needs: [python-quality, security, containers]\n", gate)
        self.assertIn("REQUIRED_RESULTS: ${{ toJSON(needs) }}", gate)
        self.assertIn("run: python3 ci/check-required-results.py", gate)
        self.assertNotIn("continue-on-error", gate)
        self.assertIn("actions/checkout@", gate)
        security = jobs["security"]
        self.assertIn("run: bash ci/check-shell-syntax.sh ci/woodpecker/*.sh ci/*.sh", security)
        self.assertNotIn("bash -n ci/woodpecker/*.sh", security)
        self.assertIn("web", jobs)
        for name in (*REQUIRED, "web"):
            self.assertNotIn("continue-on-error", jobs[name])

    def test_security_enrolls_both_contract_modules(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        security = workflow.split("  security:\n", 1)[1].split("  containers:\n", 1)[0]
        self.assertIn(
            "run: python3 -m unittest ci.tests.test_ci_contract ci.tests.test_task_contract -v",
            security,
        )
        self.assertIn('python3 -c "import tomllib"', security)

    def test_task_install_is_pinned_verified_and_before_tests(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        security = workflow.split("  security:\n", 1)[1].split("  containers:\n", 1)[0]
        self.assertIn("- name: Install Task", security)
        install = security.split("- name: Install Task", 1)[1].split("      - ", 1)[0]
        for required in (
            "TASK_VERSION: 3.48.0",
            "TASK_SHA256: f4bfc4eef1b2557b262f3cc0a79976a421885cb7b9e71cfe75568a2ebe4d7ae5",
            "https://github.com/go-task/task/releases/download/v${TASK_VERSION}/${archive}",
            'archive="task_linux_amd64.tar.gz"',
            'echo "${TASK_SHA256}  /tmp/${archive}" | sha256sum --check --strict',
            'tar -xzf "/tmp/${archive}" -C "${task_dir}" task',
            'sudo install -m 0755 "${task_dir}/task" /usr/local/bin/go-task',
        ):
            self.assertIn(required, install)
        self.assertLess(install.index("sha256sum"), install.index("tar -xzf"))
        self.assertLess(install.index("tar -xzf"), install.index("sudo install"))
        self.assertLess(security.index("- name: Install Task"), security.index("-m unittest"))

    def test_web_uses_installed_tools_scoped_tests_and_packaged_build(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        web = workflow.split("  web:\n", 1)[1]
        for command in (
            "bun install --frozen-lockfile", "bun audit", "bun test ./src ./tooling",
            "./node_modules/.bin/tsc --noEmit", "./node_modules/.bin/eslint",
            "AUTH_COOKIE_SECURE=true bun run build",
        ):
            with self.subTest(command=command):
                self.assertIn(f"- run: {command}\n", web)
        self.assertNotIn("bunx", web)
        self.assertNotIn("bun --bun next build", web)


if __name__ == "__main__":
    unittest.main()
