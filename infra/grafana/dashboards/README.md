# Threshold Grafana dashboards

MVP dashboards provisioned through generated Kubernetes ConfigMaps labeled `grafana_dashboard=1`.

Canonical dashboard JSON lives in this directory. After editing dashboard JSON, run:

```bash
python3 infra/grafana/render-configmaps.py
```

The script updates `infra/kustomize/base/observability/grafana-dashboards.yaml`, which is what Kustomize/ArgoCD applies.

Dashboards:

- `threshold-service-overview.json` — per-service RPS, latency p50/p95/p99, 5xx rate, app error logs, pod restarts.
- `threshold-nats-overview.json` — NATS message throughput, pending bytes, slow-consumer proxy, future JetStream lag, NATS warning/error logs.
- `threshold-db-overview.json` — CNPG/PostgreSQL connections, transactions, rollback rate, WAL, slow-query placeholder, DB logs, replication lag.
- `threshold-authentik-overview.json` — Authentik login events, failed logins, token refresh events, restarts, HTTP 5xx, warning/error logs, DB connections.

Datasource assumptions:

- Metrics datasource variable defaults to `Mimir`.
- Logs datasource variable defaults to `Loki`.
- Panels are intentionally written against common OpenTelemetry, Kubernetes, NATS exporter, CNPG/PostgreSQL and Loki metric/log patterns. If exporter metric names differ in live cluster, edit these JSON files and let GitOps reprovision; do not hand-edit panels in Grafana UI.
