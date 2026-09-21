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
        for command in ("uv sync --frozen", "uv run ruff check .", "uv run mypy .",
                        "uv run pytest -q", "uv export --frozen", "pip-audit --strict",
                        "python3 ci/verify-pip-audit.py"):
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
        self.assertIn("run: python3 -m unittest ci.tests.test_ci_contract -v", security)
        self.assertNotIn("bash -n ci/woodpecker/*.sh", security)
        self.assertIn("web", jobs)


if __name__ == "__main__":
    unittest.main()
