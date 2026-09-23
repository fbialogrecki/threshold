"""Fail-closed contract for the public source release workflow."""

import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".woodpecker/release.yml"
# Any release workflow change requires an explicit review of the entire file.
DISABLED_WORKFLOW_SHA256 = "9f2875f053c4ae80729ffc42b96bcc564a416bc7c0777eb09d595bb15539340d"


class ReleaseContainmentTests(unittest.TestCase):
    def test_public_workflow_is_exactly_the_reviewed_disabled_version(self) -> None:
        self.assertEqual(
            hashlib.sha256(WORKFLOW.read_bytes()).hexdigest(),
            DISABLED_WORKFLOW_SHA256,
        )

    def test_rejects_additional_publisher_despite_disabled_decoy(self) -> None:
        workflow = WORKFLOW.read_text().replace(
            "steps:\n",
            'labels: {release: "trusted"}\nsteps:\n'
            '  publish:\n    image: busybox\n    commands: ["true"]\n',
            1,
        )
        with TemporaryDirectory() as directory:
            fixture = Path(directory) / "release.yml"
            fixture.write_text(workflow)
            with (
                patch.dict(globals(), {"WORKFLOW": fixture}),
                self.assertRaises(AssertionError),
            ):
                self.test_public_workflow_is_exactly_the_reviewed_disabled_version()

    def test_public_security_job_runs_release_contract(self) -> None:
        workflow = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("python3 -m unittest ci.tests.test_release_contract -v", workflow)


if __name__ == "__main__":
    unittest.main()
