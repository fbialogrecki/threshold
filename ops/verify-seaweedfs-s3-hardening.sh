#!/usr/bin/env bash
set -euo pipefail

SEAWEEDFS_NAMESPACE="${SEAWEEDFS_NAMESPACE:-seaweedfs}"
THRESHOLD_NAMESPACE="${THRESHOLD_NAMESPACE:-threshold}"
S3_SERVICE="${S3_SERVICE:-seaweedfs-s3}"
S3_PORT="${S3_PORT:-8333}"
S3_METRICS_PORT="${S3_METRICS_PORT:-9327}"
SMOKE_POD="${SMOKE_POD:-media-s3-unauth-smoke}"
SMOKE_IMAGE="${SMOKE_IMAGE:-curlimages/curl:8.8.0}"

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: $1 is required" >&2
    exit 1
  fi
}

condition_ready() {
  local namespace="$1"
  local kind="$2"
  local name="$3"
  kubectl -n "${namespace}" get "${kind}" "${name}" \
    -o jsonpath='{range .status.conditions[*]}{.type}={.status}{"\n"}{end}' | grep -qx 'Ready=True'
}

require kubectl

echo "Checking SeaweedFS pods and S3 service shape..."
kubectl -n "${SEAWEEDFS_NAMESPACE}" wait --for=condition=Available deploy/seaweedfs-s3 --timeout=120s >/dev/null
SERVICE_TYPE="$(kubectl -n "${SEAWEEDFS_NAMESPACE}" get svc "${S3_SERVICE}" -o jsonpath='{.spec.type}')"
if [[ "${SERVICE_TYPE}" != "ClusterIP" ]]; then
  echo "ERROR: ${S3_SERVICE} service type is ${SERVICE_TYPE}, expected ClusterIP" >&2
  exit 1
fi

kubectl -n "${SEAWEEDFS_NAMESPACE}" get networkpolicy seaweedfs-s3-ingress >/dev/null
kubectl -n "${SEAWEEDFS_NAMESPACE}" get networkpolicy seaweedfs-s3-ingress \
  -o jsonpath='{.spec.ingress[*].ports[*].port}' | grep -qw "${S3_PORT}"
kubectl -n "${SEAWEEDFS_NAMESPACE}" get networkpolicy seaweedfs-s3-ingress \
  -o jsonpath='{.spec.ingress[*].ports[*].port}' | grep -qw "${S3_METRICS_PORT}"

echo "Checking ExternalSecrets readiness..."
condition_ready "${SEAWEEDFS_NAMESPACE}" externalsecret seaweedfs-s3-config
condition_ready "${THRESHOLD_NAMESPACE}" externalsecret media-s3

echo "Checking media-s3 secret key shape without decoding values..."
MEDIA_KEYS="$(kubectl -n "${THRESHOLD_NAMESPACE}" get secret media-s3 -o go-template='{{range $k, $_ := .data}}{{printf "%s\n" $k}}{{end}}' | sort | tr '\n' ',' | sed 's/,$//')"
EXPECTED_KEYS="S3_ACCESS_KEY_ID,S3_BUCKET,S3_ENDPOINT_URL,S3_FORCE_PATH_STYLE,S3_REGION,S3_SECRET_ACCESS_KEY"
if [[ "${MEDIA_KEYS}" != "${EXPECTED_KEYS}" ]]; then
  echo "ERROR: media-s3 keys are ${MEDIA_KEYS}; expected ${EXPECTED_KEYS}" >&2
  exit 1
fi

echo "Checking unauthenticated S3 behavior from a media-labelled smoke pod..."
kubectl -n "${THRESHOLD_NAMESPACE}" delete pod "${SMOKE_POD}" --ignore-not-found --wait=true >/dev/null
SMOKE_LOGS="$(kubectl -n "${THRESHOLD_NAMESPACE}" run "${SMOKE_POD}" \
  --image="${SMOKE_IMAGE}" \
  --restart=Never \
  --labels="app.kubernetes.io/name=media,app.kubernetes.io/part-of=threshold" \
  --command -- sh -c '
    set -eu
    endpoint="http://seaweedfs-s3.seaweedfs.svc.cluster.local:8333"
    status="000"
    root="000"
    for _ in $(seq 1 30); do
      status="$(curl -sS -o /tmp/status -w "%{http_code}" "${endpoint}/status" 2>/tmp/status.err || true)"
      if [ "${status}" = "200" ]; then
        break
      fi
      sleep 2
    done
    for _ in $(seq 1 30); do
      root="$(curl -sS -o /tmp/root -w "%{http_code}" "${endpoint}/" 2>/tmp/root.err || true)"
      if [ "${root}" = "403" ]; then
        break
      fi
      sleep 2
    done
    printf "status=%s\n" "${status}"
    printf "root=%s\n" "${root}"
  ' >/dev/null
kubectl -n "${THRESHOLD_NAMESPACE}" wait --for=jsonpath='{.status.phase}'=Succeeded "pod/${SMOKE_POD}" --timeout=120s >/dev/null
kubectl -n "${THRESHOLD_NAMESPACE}" logs "pod/${SMOKE_POD}")"
kubectl -n "${THRESHOLD_NAMESPACE}" delete pod "${SMOKE_POD}" --wait=true >/dev/null
if ! grep -qx 'status=200' <<<"${SMOKE_LOGS}"; then
  echo "ERROR: unauthenticated /status did not return HTTP 200" >&2
  exit 1
fi
if ! grep -qx 'root=403' <<<"${SMOKE_LOGS}"; then
  echo "ERROR: unauthenticated S3 root did not return HTTP 403" >&2
  exit 1
fi

echo "Checking CNPG backup integration state..."
kubectl -n "${THRESHOLD_NAMESPACE}" get objectstore.barmancloud.cnpg.io users-postgres-backup-store >/dev/null
kubectl -n "${THRESHOLD_NAMESPACE}" get scheduledbackup.postgresql.cnpg.io users-postgres-daily >/dev/null
kubectl -n "${THRESHOLD_NAMESPACE}" wait --for=condition=Ready cluster.postgresql.cnpg.io/users-postgres --timeout=120s >/dev/null
ARCHIVING_STATUS="$(kubectl -n "${THRESHOLD_NAMESPACE}" get cluster.postgresql.cnpg.io users-postgres -o jsonpath='{range .status.conditions[?(@.type=="ContinuousArchiving")]}{.status}{end}')"
if [[ "${ARCHIVING_STATUS}" != "True" ]]; then
  echo "ERROR: users-postgres ContinuousArchiving=${ARCHIVING_STATUS:-missing}, expected True" >&2
  exit 1
fi

echo "OK: SeaweedFS S3 hardening checks passed. Run ops/cnpg-restore-gate.sh after any S3 auth/network/restart change."
