"""Fail-closed contract for the public source release workflow."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".woodpecker/release.yml"


class ReleaseContainmentTests(unittest.TestCase):
    def test_public_workflow_cannot_receive_publication_credentials(self) -> None:
        workflow = WORKFLOW.read_text()
        self.assertIn("release disabled until trusted external admission is installed", workflow)
        self.assertIn("exit 1", workflow)
        self.assertNotIn("from_secret:", workflow)
        self.assertNotIn("woodpecker-build-push.sh", workflow)
        self.assertNotIn("woodpecker-promote-gitops.sh", workflow)
        self.assertNotIn("event: push", workflow)
        self.assertNotIn("release: trusted", workflow)

    def test_public_security_job_runs_release_contract(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("python3 -m unittest ci.tests.test_release_contract -v", workflow)


if __name__ == "__main__":
    unittest.main()
