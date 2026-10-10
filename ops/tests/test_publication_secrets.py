import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class PublicationSecretTests(unittest.TestCase):
    def test_seeding_scopes_events_and_keeps_values_out_of_arguments(self) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / "kubectl").write_text(
                "#!/usr/bin/env python3\n"
                "import base64,sys\n"
                "value = 'fixture-value'\n"
                "print(base64.b64encode(value.encode()).decode() "
                "if 'secret' in sys.argv else value)\n"
            )
            (tmp / "woodpecker-cli").write_text(
                "#!/usr/bin/env python3\n"
                "import json,os,stat,sys\n"
                "from pathlib import Path\n"
                "args=sys.argv[1:]\n"
                "value_arg=args[args.index('--value')+1]\n"
                "assert value_arg.startswith('@')\n"
                "p=Path(value_arg[1:])\n"
                "assert stat.S_IMODE(p.stat().st_mode)==0o600 and p.read_text()\n"
                "assert 'fixture-value' not in args\n"
                "events=[args[i+1] for i,a in enumerate(args) if a=='--event']\n"
                "with open(os.environ['TEST_LOG'],'a') as log:\n"
                " log.write(json.dumps({'name':args[args.index('--name')+1],"
                "'events':events,'value_file':str(p)})+'\\n')\n"
            )
            for command in ("kubectl", "woodpecker-cli"):
                (tmp / command).chmod(0o755)
            subprocess.run(
                ["bash", "ops/configure-woodpecker-release-secrets.sh"],
                cwd=root,
                env={
                    **os.environ,
                    "PATH": f"{tmp}:{os.environ['PATH']}",
                    "OPS_ENV_FILE": str(tmp / "missing.env"),
                    "HARBOR_IP": "127.0.0.1",
                    "WOODPECKER_RELEASE_REPOSITORY": "test/perlimen",
                    "TEST_LOG": str(tmp / "log"),
                },
                capture_output=True,
                check=True,
            )
            records = [json.loads(line) for line in (tmp / "log").read_text().splitlines()]
            self.assertEqual(len(records), 11)
            self.assertEqual(len({record["name"] for record in records}), 11)
            for record in records:
                self.assertEqual(record["events"], ["push", "manual"])
                self.assertFalse(Path(record["value_file"]).exists())
