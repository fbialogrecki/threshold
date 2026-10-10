import contextlib
import io
import unittest
from unittest.mock import patch

from ci.woodpecker.verify_main_ci import check_ready, main, wait_for_ci

SHA = "a" * 40


def check(
    status: str = "completed",
    conclusion: str | None = "success",
    *,
    sha: str = SHA,
    identifier: int = 1,
    app: str = "github-actions",
    name: str = "ci-ok",
) -> dict[str, object]:
    return {
        "id": identifier,
        "name": name,
        "head_sha": sha,
        "app": {"slug": app},
        "status": status,
        "conclusion": conclusion,
    }


class MainCIGateTests(unittest.TestCase):
    def test_requires_exact_successful_gate(self) -> None:
        self.assertTrue(check_ready({"check_runs": [check()]}, SHA))
        self.assertFalse(check_ready({"check_runs": []}, SHA))
        self.assertFalse(check_ready({"check_runs": [check(app="other-app")]}, SHA))
        self.assertFalse(check_ready({"check_runs": [check(name="web")]}, SHA))
        self.assertFalse(check_ready({"check_runs": [check("in_progress", None)]}, SHA))

    def test_rejects_wrong_commit_and_unsuccessful_conclusions(self) -> None:
        with self.assertRaises(ValueError):
            check_ready({"check_runs": [check(sha="b" * 40)]}, SHA)
        for conclusion in ("failure", "cancelled", "skipped", "neutral", "timed_out", None):
            with self.subTest(conclusion=conclusion), self.assertRaises(RuntimeError):
                check_ready({"check_runs": [check(conclusion=conclusion)]}, SHA)

    def test_latest_retry_cannot_reuse_earlier_success(self) -> None:
        self.assertFalse(
            check_ready({"check_runs": [check(), check("queued", None, identifier=2)]}, SHA)
        )
        with self.assertRaises(RuntimeError):
            check_ready({"check_runs": [check(), check(conclusion="failure", identifier=2)]}, SHA)
        self.assertTrue(
            check_ready({"check_runs": [check(conclusion="failure"), check(identifier=2)]}, SHA)
        )

    def test_waits_until_gate_is_complete(self) -> None:
        with (
            patch("ci.woodpecker.verify_main_ci.fetch_checks") as fetch,
            patch("ci.woodpecker.verify_main_ci.time.sleep") as sleep,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            fetch.side_effect = [{"check_runs": []}, {"check_runs": [check()]}]
            wait_for_ci(SHA, "fixture-token")
            self.assertEqual(fetch.call_count, 2)
            sleep.assert_called_once_with(15)

    def test_timeout_and_network_errors_fail_closed(self) -> None:
        with patch("ci.woodpecker.verify_main_ci.fetch_checks") as fetch:
            with self.assertRaises(TimeoutError):
                wait_for_ci(SHA, "fixture-token", timeout=0)
            fetch.assert_not_called()
            fetch.side_effect = OSError("unreachable")
            with self.assertRaises(OSError):
                wait_for_ci(SHA, "fixture-token")

    def test_only_main_pushes_can_publish(self) -> None:
        environment = {
            "CI_PIPELINE_EVENT": "push",
            "CI_COMMIT_BRANCH": "main",
            "CI_REPO": "fbialogrecki/perlimen",
            "CI_COMMIT_SHA": SHA,
            "GIT_TOKEN": "fixture-token",
        }
        with (
            patch.dict("os.environ", environment, clear=True),
            patch("ci.woodpecker.verify_main_ci.wait_for_ci") as wait,
        ):
            main()
            wait.assert_called_once_with(SHA, "fixture-token")
        for key, value in (
            ("CI_PIPELINE_EVENT", "pull_request"),
            ("CI_PIPELINE_EVENT", "manual"),
            ("CI_PIPELINE_EVENT", "tag"),
            ("CI_COMMIT_BRANCH", "feature"),
            ("CI_REPO", "other/perlimen"),
            ("CI_COMMIT_SHA", "invalid"),
            ("GIT_TOKEN", ""),
        ):
            with (
                self.subTest(key=key, value=value),
                patch.dict("os.environ", {**environment, key: value}, clear=True),
                patch("ci.woodpecker.verify_main_ci.wait_for_ci") as wait,
                self.assertRaises(ValueError),
            ):
                main()
            wait.assert_not_called()
