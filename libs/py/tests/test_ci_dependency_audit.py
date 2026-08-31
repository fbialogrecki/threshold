import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[3]
GUARD = REPO_ROOT / "ci" / "verify-pip-audit.py"


def test_guard_accepts_report_with_required_dependency(tmp_path: Path) -> None:
    report = tmp_path / "pip-audit.json"
    report.write_text(
        json.dumps(
            {
                "dependencies": [
                    {"name": "cryptography", "version": "50.0.3", "vulns": []},
                ],
                "fixes": [],
            }
        )
    )

    result = subprocess.run(
        [sys.executable, str(GUARD), str(report), "cryptography"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_guard_rejects_report_without_required_dependency(tmp_path: Path) -> None:
    report = tmp_path / "pip-audit.json"
    report.write_text(
        json.dumps(
            {
                "dependencies": [
                    {"name": "fastapi", "version": "0.139.2", "vulns": []},
                ],
                "fixes": [],
            }
        )
    )

    result = subprocess.run(
        [sys.executable, str(GUARD), str(report), "cryptography"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "cryptography" in result.stderr


def test_python_ci_audits_exported_project_dependencies() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    normalized = " ".join(workflow.split())

    assert (
        "uv export --frozen --no-dev --no-emit-workspace --no-hashes "
        "--format requirements.txt --output-file /tmp/threshold-requirements.txt"
    ) in normalized
    assert (
        "uvx --from pip-audit==2.10.1 pip-audit --strict --format json "
        "--output /tmp/pip-audit.json -r /tmp/threshold-requirements.txt"
    ) in normalized
    assert (
        "python3 ci/verify-pip-audit.py /tmp/pip-audit.json cryptography"
    ) in normalized
