#!/usr/bin/env python3
"""Render Grafana dashboard JSON files into Kustomize ConfigMap manifests.

Run after editing a dashboard in infra/grafana/dashboards/. With --check,
exit 1 instead of writing when the committed manifest is out of date.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = ROOT / "infra/grafana/dashboards"
OUTPUT = ROOT / "infra/kustomize/base/observability/grafana-dashboards.yaml"

DASHBOARDS = [
    ("grafana-dashboard-threshold-service", "threshold-service-overview.json"),
    ("grafana-dashboard-threshold-nats", "threshold-nats-overview.json"),
    ("grafana-dashboard-threshold-db", "threshold-db-overview.json"),
    ("grafana-dashboard-threshold-authentik", "threshold-authentik-overview.json"),
]


def indent_block(content: str) -> str:
    return "\n".join("    " + line for line in content.splitlines())


def render_configmap(name: str, filename: str) -> str:
    dashboard_path = DASHBOARD_DIR / filename
    dashboard_json = dashboard_path.read_text()
    block = indent_block(dashboard_json)
    return f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {name}
  labels:
    grafana_dashboard: "1"
    app.kubernetes.io/name: {name}
    app.kubernetes.io/part-of: threshold
  annotations:
    threshold.dev/source-file: infra/grafana/dashboards/{filename}
data:
  {filename}: |-
{block}
"""


def render() -> str:
    return "---\n".join(render_configmap(name, filename) for name, filename in DASHBOARDS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if the manifest differs from the rendered dashboards; write nothing",
    )
    args = parser.parse_args()

    rendered = render()
    output = OUTPUT.relative_to(ROOT)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text() != rendered:
            print(
                f"{output} is out of date; run infra/grafana/render-configmaps.py", file=sys.stderr
            )
            return 1
        print(f"{output} is up to date")
        return 0

    OUTPUT.write_text(rendered)
    print(f"Rendered {len(DASHBOARDS)} dashboard ConfigMaps to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
