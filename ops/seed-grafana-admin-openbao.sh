#!/usr/bin/env bash
set -euo pipefail

OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
MOUNT_PATH="${MOUNT_PATH:-secret}"
REMOTE_PATH="${REMOTE_PATH:-threshold/observability/grafana-admin}"

if [[ -z "${GRAFANA_ADMIN_USER:-}" ]]; then
  echo "ERROR: missing GRAFANA_ADMIN_USER" >&2
  exit 1
fi

if [[ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]]; then
  echo "ERROR: missing GRAFANA_ADMIN_PASSWORD" >&2
  exit 1
fi

if [[ -z "${BAO_TOKEN:-}" ]]; then
  printf "OpenBao token with write access to %s/%s (hidden): " "${MOUNT_PATH}" "${REMOTE_PATH}" >&2
  IFS= read -rs BAO_TOKEN
  printf "\n" >&2
fi

if [[ -z "${BAO_TOKEN}" ]]; then
  echo "ERROR: empty BAO_TOKEN" >&2
  exit 1
fi

TOKEN_FILE="$(mktemp)"
USER_FILE="$(mktemp)"
PASSWORD_FILE="$(mktemp)"

cleanup() {
  rm -f "${TOKEN_FILE}" "${USER_FILE}" "${PASSWORD_FILE}"
}
trap cleanup EXIT

chmod 600 "${TOKEN_FILE}" "${USER_FILE}" "${PASSWORD_FILE}"

printf '%s' "${BAO_TOKEN}" > "${TOKEN_FILE}"
printf '%s' "${GRAFANA_ADMIN_USER}" > "${USER_FILE}"
printf '%s' "${GRAFANA_ADMIN_PASSWORD}" > "${PASSWORD_FILE}"

kubectl cp "${TOKEN_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/grafana-admin-token" >/dev/null
kubectl cp "${USER_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/grafana-admin-user" >/dev/null
kubectl cp "${PASSWORD_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/grafana-admin-password" >/dev/null

kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- "${MOUNT_PATH}" "${REMOTE_PATH}" <<'EOF_INNER'
set -eu

MOUNT_PATH="$1"
REMOTE_PATH="$2"

cleanup_inner() {
  rm -f /tmp/grafana-admin-token /tmp/grafana-admin-user /tmp/grafana-admin-password
}
trap cleanup_inner EXIT

export BAO_ADDR="http://127.0.0.1:8200"
export BAO_TOKEN="$(cat /tmp/grafana-admin-token)"

bao kv put "${MOUNT_PATH}/${REMOTE_PATH}" \
  admin-user=@/tmp/grafana-admin-user \
  admin-password=@/tmp/grafana-admin-password >/dev/null

bao kv get -field="admin-user" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
bao kv get -field="admin-password" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null

echo "OK: OpenBao secret seeded and verified: ${MOUNT_PATH}/${REMOTE_PATH}"
EOF_INNER
