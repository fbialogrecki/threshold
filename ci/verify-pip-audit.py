#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <pip-audit.json> <required-dependency>", file=sys.stderr)
        return 2

    report_path = Path(argv[1])
    report = json.loads(report_path.read_text())
    dependencies = report.get("dependencies")
    if not isinstance(dependencies, list):
        print("pip-audit report has no dependencies list", file=sys.stderr)
        return 1

    required = argv[2].casefold()
    audited = {
        dependency.get("name", "").casefold()
        for dependency in dependencies
        if isinstance(dependency, dict)
    }
    if required not in audited:
        print(f"required dependency was not audited: {argv[2]}", file=sys.stderr)
        return 1

    print(f"verified audited dependency: {argv[2]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
