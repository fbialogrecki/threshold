#!/usr/bin/env python3
"""Update one application's local Kustomize overlay image for GitOps promotion."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SUPPORTED_SERVICES = {"auth-gateway", "events", "media", "social", "users", "web"}
DEFAULT_ENVIRONMENT = "local"

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bump one application image in "
            "infra/kustomize/overlays/<env>/<service>/kustomization.yaml."
        )
    )
    parser.add_argument(
        "--service",
        required=True,
        help="Application name: auth-gateway, events, media, social, users, or web.",
    )
    parser.add_argument(
        "--digest", required=True, help="Immutable sha256 image digest to write."
    )
    parser.add_argument(
        "--image-registry",
        required=True,
        help="Registry/namespace prefix.",
    )
    parser.add_argument(
        "--env",
        default=DEFAULT_ENVIRONMENT,
        help=f"Kustomize overlay environment. Default: {DEFAULT_ENVIRONMENT}",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root. Default: current directory.",
    )
    return parser.parse_args()


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def validate(args: argparse.Namespace) -> None:
    if args.service not in SUPPORTED_SERVICES:
        allowed = ", ".join(sorted(SUPPORTED_SERVICES))
        fail(f"unsupported application '{args.service}'. Allowed: {allowed}")
    if not DIGEST_RE.fullmatch(args.digest):
        fail("digest must be a lowercase sha256 value")
    if not args.image_registry or args.image_registry.endswith("/"):
        fail("image registry must be a non-empty prefix without a trailing slash")
    if "/" in args.env or args.env in {"", ".", ".."}:
        fail("env must be a single overlay directory name")


def bump(path: Path, service: str, image_registry: str, digest: str) -> bool:
    if not path.is_file():
        fail(f"missing application overlay: {path}")

    lines = path.read_text().splitlines()
    expected_name = f"threshold/{service}"
    desired_new_name = f"{image_registry}/{service}"
    desired_digest = digest

    in_target_image = False
    saw_target_image = False
    saw_digest_field = False
    changed = False
    out: list[str] = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("- name:"):
            image_name = stripped.split(":", 1)[1].strip().strip('"\'')
            in_target_image = image_name == expected_name
            saw_target_image = saw_target_image or in_target_image
            out.append(line)
            continue

        if in_target_image and stripped.startswith("newName:"):
            indent = line[: len(line) - len(line.lstrip())]
            new_line = f"{indent}newName: {desired_new_name}"
            changed = changed or new_line != line
            out.append(new_line)
            continue

        if in_target_image and (
            stripped.startswith("newTag:") or stripped.startswith("digest:")
        ):
            if saw_digest_field:
                changed = True
                continue
            indent = line[: len(line) - len(line.lstrip())]
            new_line = f"{indent}digest: {desired_digest}"
            saw_digest_field = True
            changed = changed or new_line != line
            out.append(new_line)
            continue

        out.append(line)

    if not saw_target_image:
        fail(f"missing images entry with name: {expected_name} in {path}")
    if not saw_digest_field:
        fail(f"missing newTag or digest field for: {expected_name} in {path}")

    if changed:
        path.write_text("\n".join(out) + "\n")

    return changed


def main() -> int:
    args = parse_args()
    validate(args)

    repo_root = Path(args.repo_root).resolve()
    target = (
        repo_root
        / "infra"
        / "kustomize"
        / "overlays"
        / args.env
        / args.service
        / "kustomization.yaml"
    )
    changed = bump(target, args.service, args.image_registry, args.digest)
    status = "updated" if changed else "already current"
    print(f"{status}: {target} -> {args.image_registry}/{args.service}@{args.digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
