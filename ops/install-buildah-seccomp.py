#!/usr/bin/env python3
"""Install a node-local Buildah exception derived from its runtime default."""

import copy
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROFILE = Path("/var/lib/kubelet/seccomp/perlimen/buildah.json")
# Buildah 1.43's rootless setup and chroot runner need only these namespaces.
NAMESPACES = 0x10000000 | 0x00020000 | 0x04000000  # user, mount, UTS


def buildah_profile(default: dict[str, Any]) -> dict[str, Any]:
    if default.get("defaultAction") != "SCMP_ACT_ERRNO":
        raise ValueError("expected a default-deny runtime profile")
    profile = copy.deepcopy(default)
    profile["syscalls"].extend(
        [
            {
                "names": ["unshare"],
                "action": "SCMP_ACT_ALLOW",
                "args": [
                    {
                        "index": 0,
                        "value": ~NAMESPACES & 0xFFFFFFFF,
                        "valueTwo": 0,
                        "op": "SCMP_CMP_MASKED_EQ",
                    }
                ],
            },
            # CAP_SYS_ADMIN remains absent in the parent namespace. Mounts are
            # possible only inside Buildah's nested user namespace.
            {"names": ["mount", "umount2"], "action": "SCMP_ACT_ALLOW"},
        ]
    )
    return profile


def read_json(*command: str) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(subprocess.check_output(command, text=True))
    return result


def main() -> None:
    if os.geteuid() != 0:
        raise SystemExit("run with sudo on the k3s node")
    pods = read_json(
        "kubectl",
        "get",
        "pods",
        "-n",
        "woodpecker",
        "-l",
        "app.kubernetes.io/name=woodpecker-release-agent",
        "-o",
        "json",
    )["items"]
    pod = next(p for p in pods if p["status"]["phase"] == "Running")
    if pod["spec"]["securityContext"]["seccompProfile"]["type"] != "RuntimeDefault":
        raise SystemExit("release agent must use RuntimeDefault")
    container_id = pod["status"]["containerStatuses"][0]["containerID"].split("://", 1)[1]
    default = read_json("crictl", "inspect", container_id)["info"]["runtimeSpec"]["linux"][
        "seccomp"
    ]
    profile = buildah_profile(default)
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=PROFILE.parent, delete=False) as output:
        temporary = Path(output.name)
        json.dump(profile, output, indent=2)
        output.write("\n")
    try:
        temporary.chmod(0o644)
        temporary.replace(PROFILE)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Installed {PROFILE}; node RuntimeDefault and capabilities unchanged")


if __name__ == "__main__":
    main()
