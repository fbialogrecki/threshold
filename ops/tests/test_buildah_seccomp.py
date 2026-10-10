import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "profile", Path(__file__).parents[1] / "install-buildah-seccomp.py"
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BuildahProfile(unittest.TestCase):
    def test_preserves_denials_and_limits_namespace_creation(self):
        base = {
            "defaultAction": "SCMP_ACT_ERRNO",
            "syscalls": [{"names": ["read"], "action": "SCMP_ACT_ALLOW"}],
        }
        result = module.buildah_profile(base)
        self.assertEqual(len(base["syscalls"]), 1)
        self.assertEqual(result["defaultAction"], base["defaultAction"])
        self.assertEqual(result["syscalls"][0], base["syscalls"][0])
        rule = result["syscalls"][1]["args"][0]

        def allows(flags):
            return flags & rule["value"] == rule["valueTwo"]

        for flags in [0x10000000, 0x00020000, 0x04000000, module.NAMESPACES]:
            self.assertTrue(allows(flags))
        for flags in [0x40000000, 0x20000000, 0x08000000, module.NAMESPACES | 0x40000000]:
            self.assertFalse(allows(flags))
        self.assertEqual(result["syscalls"][2]["names"], ["mount", "umount2"])
        with self.assertRaises(ValueError):
            module.buildah_profile({"defaultAction": "SCMP_ACT_ALLOW"})
