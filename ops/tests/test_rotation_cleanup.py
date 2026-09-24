"""Synthetic subprocess regression: execute real transfer/traps, never live main."""

import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

OPS_DIR = Path(__file__).resolve().parents[1]
SCRIPT = OPS_DIR / "rotate-release-token-from-bitwarden.sh"
# The harness runs a copy of the script from a temp dir, so point OPS_DIR back at
# ops/ (for lib-local-env.sh) and at an empty local.env so no operator settings leak in.
OPS_DIR_LINE = 'OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
FAKE = r"""#!/usr/bin/python3
import os, pathlib, shutil, signal, subprocess, sys
root = pathlib.Path(os.environ['FAKE_ROOT'])
a = sys.argv[1:]
if pathlib.Path(sys.argv[0]).name == 'rm':
    local_token = '/local/' in a[-1] and a[-1].endswith('/token')
    if os.environ.get('FAIL_LOCAL_CLEANUP') == '1' and local_token:
        sys.exit(23)
    sys.exit(subprocess.run(['/bin/rm', *a]).returncode)
if pathlib.Path(sys.argv[0]).name == 'bao':
    assert os.environ['BAO_TOKEN'] == 'synthetic-bao-only'
    if a[:2] == ['kv', 'put']:
        assert a[2] == 'secret/threshold/ci/github-writer'
        fields = dict(x.split('=', 1) for x in a[3:])
        assert set(fields) == {'GIT_USERNAME', 'GIT_TOKEN'}
        assert pathlib.Path(fields['GIT_USERNAME'][1:]).read_text() == 'synthetic-user'
        assert pathlib.Path(fields['GIT_TOKEN'][1:]).read_text() == 'synthetic-github-only'
    sys.exit(0)
if pathlib.Path(sys.argv[0]).name != 'kubectl':
    sys.exit(0)
def mapped(s):
    return s.replace('/tmp/', str(root / 'remote') + '/')
if a[0] == 'cp':
    count = root / 'count'
    n = int(count.read_text()) + 1 if count.exists() else 1
    count.write_text(str(n))
    dst = pathlib.Path(mapped(a[2].split(':', 1)[1]))
    shutil.copyfile(a[1], dst)
    dst.chmod(0o600)
    if os.environ.get('TRY_CONCURRENT') == '1' and not os.environ.get('REENTER'):
        env = dict(os.environ, REENTER='1')
        other = subprocess.run(
            ['/bin/bash', env['HARNESS']], env=env, capture_output=True, text=True, timeout=3
        )
        (root / 'concurrent').write_text(str(other.returncode) + '\n' + other.stderr)
    if os.environ.get('INTERRUPT') == str(n):
        os.kill(os.getppid(), signal.SIGTERM)
    sys.exit(17 if os.environ.get('FAIL_COPY') == str(n) else 0)
if a[0] == 'exec':
    cmd = a[a.index('--') + 1:]
    text = sys.stdin.read() if '-i' in a else ''
    removes = cmd[0] == 'rm' or 'rm -f' in text or any('rm -f' in x for x in cmd)
    if os.environ.get('FAIL_CLEANUP') == '1' and removes:
        sys.exit(19)
    cmd = [mapped(x) for x in cmd]
    text = mapped(text)
    if os.environ.get('COLLISION') == '1' and 'mkdir -m 700' in text:
        candidate = pathlib.Path(cmd[-2])
        candidate.mkdir(mode=0o700)
        (candidate / '.owner').write_text('another-owner')
        (candidate / 'token').write_text('another-owner-token')
    sys.exit(subprocess.run(cmd, input=text, text=True).returncode)
raise SystemExit('unexpected fake kubectl operation')
"""


class RotationCleanup(unittest.TestCase):
    def exercise(self, **fault):
        with tempfile.TemporaryDirectory(prefix="rotation-test-") as td:
            root = Path(td)
            for name in ("bin", "local", "remote", "home"):
                (root / name).mkdir()
            # Fixed paths belong to someone else and must not be touched by the repair.
            unknown = root / "remote" / "unrelated-run"
            unknown.mkdir()
            (unknown / "credential").write_text("other-owner-synthetic")
            for name in ("kubectl", "bao", "bw", "rm"):
                p = root / "bin" / name
                p.write_text(FAKE)
                p.chmod(0o700)
            (root / "local.env").write_text("")
            env = {
                "PATH": str(root / "bin") + ":/usr/bin:/bin",
                "HOME": str(root / "home"),
                "TMPDIR": str(root / "local"),
                "FAKE_ROOT": str(root),
                "OPS_LOCAL_ENV": str(root / "local.env"),
                **fault,
            }
            # Do not invoke normal main: load its exact source definitions and traps,
            # then exercise the actual transfer function with synthetic input only.
            source = SCRIPT.read_text()
            self.assertTrue(source.endswith('main "$@"\n'))
            self.assertEqual(source.count(OPS_DIR_LINE), 1)
            source = source.replace(OPS_DIR_LINE, f"OPS_DIR={shlex.quote(str(OPS_DIR))}\n")
            harness = root / "harness.sh"
            harness.write_text(
                source[: -len('main "$@"\n')]
                + """
PATH="$TEST_PATH"
GITHUB_TOKEN=synthetic-github-only
BAO_TOKEN=synthetic-bao-only
OPENBAO_GIT_USERNAME=synthetic-user
seed_openbao
"""
            )
            env["TEST_PATH"] = env["PATH"]
            env["HARNESS"] = str(harness)
            result = subprocess.run(
                ["/bin/bash", str(harness)], env=env, capture_output=True, text=True, timeout=10
            )
            if fault.get("TRY_CONCURRENT"):
                self.assertTrue((root / "concurrent").exists(), result.stderr)
                self.assertIn("rotation already running", (root / "concurrent").read_text())
            remaining = [
                str(p.relative_to(root))
                for directory in ("local", "remote")
                for p in (root / directory).rglob("*")
                if p.is_file() and unknown not in p.parents
            ]
            self.assertEqual((unknown / "credential").read_text(), "other-owner-synthetic")
            self.assertNotIn("synthetic-github-only", result.stdout + result.stderr)
            self.assertNotIn("synthetic-bao-only", result.stdout + result.stderr)
            return result, remaining

    def test_partial_first_copy_cleanup(self):
        result, remaining = self.exercise(FAIL_COPY="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(remaining, [])

    def test_preexisting_other_owner_is_preserved(self):
        result, remaining = self.exercise(COLLISION="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("credential cleanup incomplete", result.stderr)
        self.assertEqual(len(remaining), 2)
        self.assertTrue(any(p.endswith("/token") for p in remaining))
        self.assertFalse(any(p.startswith("local/") for p in remaining))

    def test_same_target_local_serialization(self):
        result, remaining = self.exercise(TRY_CONCURRENT="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(remaining, [])

    def test_healthy_control(self):
        result, remaining = self.exercise()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(remaining, [])

    def test_second_and_third_partial_copy_cleanup(self):
        for n in ("2", "3"):
            with self.subTest(copy=n):
                result, remaining = self.exercise(FAIL_COPY=n)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(remaining, [])

    def test_interruption_cleanup(self):
        result, remaining = self.exercise(INTERRUPT="2")
        self.assertEqual(result.returncode, 143)
        self.assertEqual(remaining, [])

    def test_local_cleanup_failure_continues_other_removals(self):
        result, remaining = self.exercise(FAIL_LOCAL_CLEANUP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("credential cleanup incomplete", result.stderr)
        self.assertEqual(len(remaining), 1)
        self.assertTrue(remaining[0].startswith("local/"))
        self.assertTrue(remaining[0].endswith("/token"))

    def test_cleanup_failure_is_explicit_and_local_cleanup_continues(self):
        result, remaining = self.exercise(FAIL_CLEANUP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("credential cleanup incomplete", result.stderr)
        self.assertTrue(any(p.endswith("/token") for p in remaining))
        self.assertFalse(any(p.startswith("local/") for p in remaining))


if __name__ == "__main__":
    unittest.main()
