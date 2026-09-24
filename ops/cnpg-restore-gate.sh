#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-threshold}"
SOURCE_CLUSTER="${SOURCE_CLUSTER:-users-postgres}"
RESTORE_CLUSTER="${RESTORE_CLUSTER:-users-postgres-restore-drill}"
DATABASE="${DATABASE:-threshold_users}"
S3_SECRET="${S3_SECRET:-users-postgres-backup-s3}"
BARMAN_OBJECT_STORE="${BARMAN_OBJECT_STORE:-users-postgres-backup-store}"
KEEP_RESTORE_DRILL="${KEEP_RESTORE_DRILL:-false}"
STAMP="$(date -u +%Y%m%d%H%M%S)"
BACKUP_NAME="${BACKUP_NAME:-${SOURCE_CLUSTER}-restore-gate-${STAMP}}"

cleanup_restore() {
  if [[ "${KEEP_RESTORE_DRILL}" == "true" ]]; then
    echo "KEEP_RESTORE_DRILL=true, leaving ${RESTORE_CLUSTER} in place."
    return
  fi

  kubectl -n "${NAMESPACE}" delete cluster.postgresql.cnpg.io "${RESTORE_CLUSTER}" --ignore-not-found --wait=true >/dev/null || true
  kubectl -n "${NAMESPACE}" delete pvc -l "cnpg.io/cluster=${RESTORE_CLUSTER}" --ignore-not-found >/dev/null || true
}
trap cleanup_restore EXIT

wait_cluster_ready() {
  local cluster="$1"
  local timeout="$2"
  kubectl -n "${NAMESPACE}" wait --for=condition=Ready "cluster.postgresql.cnpg.io/${cluster}" --timeout="${timeout}"
}

echo "Checking required S3 credential secret..."
kubectl -n "${NAMESPACE}" get secret "${S3_SECRET}" >/dev/null

echo "Checking Barman Cloud Plugin ObjectStore..."
kubectl -n "${NAMESPACE}" get objectstore.barmancloud.cnpg.io "${BARMAN_OBJECT_STORE}" >/dev/null

echo "Checking source cluster..."
wait_cluster_ready "${SOURCE_CLUSTER}" 300s

echo "Creating on-demand Barman Cloud Plugin backup: ${BACKUP_NAME}"
cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: postgresql.cnpg.io/v1
kind: Backup
metadata:
  name: ${BACKUP_NAME}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: ${SOURCE_CLUSTER}
    app.kubernetes.io/component: restore-gate
    app.kubernetes.io/part-of: threshold
spec:
  cluster:
    name: ${SOURCE_CLUSTER}
  method: plugin
  pluginConfiguration:
    name: barman-cloud.cloudnative-pg.io
  target: primary
YAML

for _ in $(seq 1 180); do
  BACKUP_PHASE="$(kubectl -n "${NAMESPACE}" get "backup.postgresql.cnpg.io/${BACKUP_NAME}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  case "${BACKUP_PHASE}" in
    completed)
      break
      ;;
    failed)
      kubectl -n "${NAMESPACE}" get "backup.postgresql.cnpg.io/${BACKUP_NAME}" -o yaml >&2 || true
      echo "ERROR: backup ${BACKUP_NAME} failed" >&2
      exit 1
      ;;
  esac
  sleep 10
done

if [[ "${BACKUP_PHASE:-}" != "completed" ]]; then
  kubectl -n "${NAMESPACE}" get "backup.postgresql.cnpg.io/${BACKUP_NAME}" -o yaml >&2 || true
  echo "ERROR: backup ${BACKUP_NAME} did not complete within timeout" >&2
  exit 1
fi

echo "Backup completed. Recreating restore drill cluster: ${RESTORE_CLUSTER}"
cleanup_restore

cat <<YAML | kubectl apply -f - >/dev/null
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: ${RESTORE_CLUSTER}
  namespace: ${NAMESPACE}
  labels:
    app.kubernetes.io/name: ${RESTORE_CLUSTER}
    app.kubernetes.io/component: restore-drill
    app.kubernetes.io/part-of: threshold
spec:
  instances: 1
  imageName: ghcr.io/cloudnative-pg/postgresql:18.3-system-trixie
  bootstrap:
    recovery:
      source: ${SOURCE_CLUSTER}
  externalClusters:
    - name: ${SOURCE_CLUSTER}
      plugin:
        name: barman-cloud.cloudnative-pg.io
        parameters:
          barmanObjectName: ${BARMAN_OBJECT_STORE}
          serverName: ${SOURCE_CLUSTER}
  storage:
    size: 5Gi
    storageClass: threshold-postgres-local
    resizeInUseVolumes: true
YAML

wait_cluster_ready "${RESTORE_CLUSTER}" 30m
PRIMARY_POD="$(kubectl -n "${NAMESPACE}" get cluster.postgresql.cnpg.io "${RESTORE_CLUSTER}" -o jsonpath='{.status.currentPrimary}')"
if [[ -z "${PRIMARY_POD}" ]]; then
  echo "ERROR: restore cluster has no currentPrimary" >&2
  exit 1
fi

# Schema-agnostic sanity: works for any Alembic-managed threshold database
# (users, social, ...). Asserts the restored DB has its migration marker and at
# least one user table; fails the gate otherwise.
echo "Running SQL sanity checks on ${RESTORE_CLUSTER}/${DATABASE} via ${PRIMARY_POD}"
kubectl -n "${NAMESPACE}" exec "${PRIMARY_POD}" -- psql -d "${DATABASE}" -v ON_ERROR_STOP=1 -Atc "
select 'database=' || current_database();
select 'alembic_version=' || coalesce((select version_num from alembic_version limit 1), 'missing');
select 'public_tables=' || count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE';
select 'live_rows=' || coalesce(sum(n_live_tup), 0) from pg_stat_user_tables;
do \$\$
begin
  if (select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE') = 0 then
    raise exception 'restore-gate: restored database has no public tables';
  end if;
end
\$\$;
"

echo "OK: CNPG object-store backup and restore gate passed using backup ${BACKUP_NAME}."
