"""Wait for the exact main commit's GitHub Actions gate before publication."""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any

REPOSITORY = "fbialogrecki/perlimen"


def check_ready(payload: dict[str, Any], sha: str) -> bool:
    checks = [
        check
        for check in payload.get("check_runs", [])
        if check.get("name") == "ci-ok" and check.get("app", {}).get("slug") == "github-actions"
    ]
    if not checks:
        return False
    latest = max(checks, key=lambda check: check["id"])
    if latest.get("head_sha") != sha:
        raise ValueError("CI gate does not belong to the requested commit")
    if latest.get("status") != "completed":
        return False
    if latest.get("conclusion") != "success":
        raise RuntimeError(f"ci-ok did not pass: {latest.get('conclusion')}")
    return True


def fetch_checks(sha: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/commits/{sha}/check-runs"
        "?check_name=ci-ok&filter=latest&per_page=100",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "perlimen-ci",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload: dict[str, Any] = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"GitHub checks request failed (HTTP {error.code})") from None
    return payload


def wait_for_ci(sha: str, token: str, timeout: float = 1800, interval: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check_ready(fetch_checks(sha, token), sha):
            print(f"GitHub Actions ci-ok passed for {sha}", flush=True)
            return
        time.sleep(interval)
    raise TimeoutError("Timed out waiting for GitHub Actions ci-ok")


def main() -> None:
    if (
        os.environ.get("CI_PIPELINE_EVENT") != "push"
        or os.environ.get("CI_COMMIT_BRANCH") != "main"
        or os.environ.get("CI_REPO") != REPOSITORY
    ):
        raise ValueError("Automatic publication is only allowed for Perlimen main pushes")
    sha = os.environ.get("CI_COMMIT_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("CI_COMMIT_SHA must be a full lowercase commit SHA")
    token = os.environ.get("GIT_TOKEN", "")
    if not token:
        raise ValueError("The event-restricted GitHub token is required")
    wait_for_ci(sha, token)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(f"Publication blocked: {error}", file=sys.stderr)
        sys.exit(1)
