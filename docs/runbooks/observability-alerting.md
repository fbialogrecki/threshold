# Observability And Alerting

Everything here is managed by Argo CD from `infra/`. Do not run `helm upgrade` against these releases.

## Pipelines

- **Application telemetry.** Services send OTLP to the OpenTelemetry Collector (`otel-collector.observability:4317`). The collector sends traces to Tempo, logs to Loki and metrics to Mimir. Config: `infra/helm/otel-collector/values.yaml`.
- **Infrastructure metrics.** There is no Prometheus operator. Alloy (DaemonSet) scrapes kube-state-metrics (`job="kube-state-metrics"`), node-exporter (`node-exporter`), CNPG instances on `:9187` (`cnpg`, with a `cnpg_cluster` label) and kubelet cAdvisor memory metrics for the `web` container (`kubelet-cadvisor`), and remote-writes to `mimir-gateway`. Config: `infra/helm/alloy/values.yaml`.
- **Pod logs.** Alloy tails `/var/log/pods` and writes to Loki.

Retention: Loki 30 days (streams labelled `retention="audit"`, from pod label `threshold.io/log-retention=audit`, keep 12 months), Tempo 14 days, Mimir 30 days.

Quick check in Grafana (Mimir datasource):

```promql
up{job=~"cnpg|kube-state-metrics|node-exporter"}
```

Every series should be `1`.

## Grafana

- Reached at `grafana.internal`. Login uses the admin credential from OpenBao, materialized by `ExternalSecret/grafana-admin`; Grafana is not behind Authentik.
- Datasources Mimir, Loki and Tempo are provisioned in `infra/helm/grafana/values.yaml`. The Mimir datasource has the fixed uid `PAE45454D0EDB9216`, which the alert rules reference. Do not change it without updating the rules.
- Dashboards are JSON files in `infra/grafana/dashboards/`, rendered into ConfigMaps labelled `grafana_dashboard=1` in `infra/kustomize/base/observability/grafana-dashboards.yaml`. Edit the JSON, run `python3 infra/grafana/render-configmaps.py`, and commit both; do not edit panels in the UI.

## Alert Rules

Rules are provisioned as code in folder **Threshold Alerts** and evaluated every minute.

Group `threshold-infra` in `infra/helm/grafana/values.yaml`:

| uid | Fires when | For | Severity |
|---|---|---|---|
| `threshold-cnpg-down` | `up{job="cnpg"}` is 0 | 5m | critical |
| `threshold-cnpg-backup-old` | WAL segments waiting to be archived in namespace `threshold` | 30m | warning |
| `threshold-node-disk-near-full` | Root filesystem below 10% free | 15m | warning |
| `threshold-pod-crashloop` | A container in `threshold`, `observability`, `woodpecker`, `seaweedfs`, `authentik` or `infra` is in `CrashLoopBackOff` | 5m | warning |

Group `threshold-applications` in `infra/helm/grafana/application-alerts.yaml`:

| uid | Fires when | For | Severity |
|---|---|---|---|
| `threshold-app-unavailable` | An app deployment (`auth-gateway`, `events`, `media`, `social`, `users`, `web`) has no available replica | 5m | critical |
| `threshold-app-http-5xx` | More than 5% of a service's requests return 5xx | 10m | warning |
| `threshold-app-http-latency` | A service's p95 latency exceeds 1 s | 10m | warning |

The HTTP rules use the `threshold_http_server_*` metrics from `libs/py/threshold_common/http_observability.py` and ignore health, metrics and docs routes.

Why a WAL alert and not a base-backup-age alert: CNPG's `cnpg_collector_last_available_backup_timestamp` is not reliable with the Barman Cloud plugin. Stuck WAL archiving is the failure that breaks continuous backup and point-in-time recovery, and it is exported reliably. Nothing alerts on a missed daily base backup yet; check `kubectl -n threshold get backups.postgresql.cnpg.io` by hand. `authentik-postgres` is not covered by the WAL rule.

### Template escaping

The Grafana chart passes provisioning through Helm `tpl`, so Grafana templates in annotations must be wrapped in a raw block:

```yaml
description: "{{`Pod {{ $labels.namespace }}/{{ $labels.pod }} is crash looping.`}}"
```

## Notifications

No contact point is configured. Alerts are visible only in Grafana (Alerting → Alert rules). To add one, provision `contactpoints.yaml` and `policies.yaml` under `alerting:` in `infra/helm/grafana/values.yaml`, with any channel secret (webhook URL, SMTP password) coming from OpenBao through an `ExternalSecret`, never inline.

## Testing A Rule

Argo CD only syncs `main`, so a rule test is a short-lived change there: tighten one rule's threshold (for example the disk rule's `lt` value to `0.99`), merge, confirm the rule goes to `Firing` in the UI, then revert.
