"""Fail closed unless every required CI dependency explicitly succeeded."""

import json
import os
import sys

REQUIRED = ("python-quality", "security", "containers")


def main() -> int:
    try:
        results = json.loads(os.environ["REQUIRED_RESULTS"])
    except (KeyError, ValueError):
        print("Required dependency results are missing or invalid JSON.", file=sys.stderr)
        return 1
    if not isinstance(results, dict):
        print("Required dependency results must be an object.", file=sys.stderr)
        return 1
    failed = [
        name for name in REQUIRED
        if not isinstance(results.get(name), dict)
        or results[name].get("result") != "success"
    ]
    if failed:
        print("Required dependencies did not succeed: " + ", ".join(failed), file=sys.stderr)
        return 1
    print("All required CI dependencies succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
