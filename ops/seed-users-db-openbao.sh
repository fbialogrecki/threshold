#!/usr/bin/env bash
set -euo pipefail

OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
APP_NAMESPACE="${APP_NAMESPACE:-threshold}"
CNPG_SECRET="${CNPG_SECRET:-users-postgres-app}"
CNPG_SECRET_KEY="${CNPG_SECRET_KEY:-uri}"
MOUNT_PATH="${MOUNT_PATH:-secret}"
REMOTE_PATH="${REMOTE_PATH:-threshold/users/db}"
REMOTE_PROPERTY="${REMOTE_PROPERTY:-THRESHOLD_DATABASE_URL}"

TOKEN_FILE=""
DB_URI_FILE=""
cleanup() {
  [[ -n "${TOKEN_FILE}" && -f "${TOKEN_FILE}" ]] && rm -f "${TOKEN_FILE}"
  [[ -n "${DB_URI_FILE}" && -f "${DB_URI_FILE}" ]] && rm -f "${DB_URI_FILE}"
}
trap cleanup EXIT

if [[ -z "${BAO_TOKEN:-}" ]]; then
  printf "OpenBao token with write access to %s/%s (input hidden, not stored): " "${MOUNT_PATH}" "${REMOTE_PATH}" >&2
  IFS= read -rs BAO_TOKEN
  printf "\n" >&2
fi

if [[ -z "${BAO_TOKEN}" ]]; then
  echo "ERROR: empty BAO_TOKEN" >&2
  exit 1
fi

DB_URI_B64="$(kubectl get secret "${CNPG_SECRET}" -n "${APP_NAMESPACE}" -o "jsonpath={.data.${CNPG_SECRET_KEY}}")"
if [[ -z "${DB_URI_B64}" ]]; then
  echo "ERROR: missing ${APP_NAMESPACE}/${CNPG_SECRET}.${CNPG_SECRET_KEY}" >&2
  exit 1
fi

TOKEN_FILE="$(mktemp)"
DB_URI_FILE="$(mktemp)"
chmod 600 "${TOKEN_FILE}" "${DB_URI_FILE}"
printf '%s' "${BAO_TOKEN}" > "${TOKEN_FILE}"
printf '%s' "${DB_URI_B64}" | base64 -d > "${DB_URI_FILE}"

if [[ ! -s "${DB_URI_FILE}" ]]; then
  echo "ERROR: decoded DB URI is empty" >&2
  exit 1
fi

kubectl cp "${TOKEN_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seed-users-db-token" >/dev/null
kubectl cp "${DB_URI_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seed-users-db-uri" >/dev/null

kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- \
  "${MOUNT_PATH}" "${REMOTE_PATH}" "${REMOTE_PROPERTY}" <<'EOF_INNER'
set -eu
MOUNT_PATH="$1"
REMOTE_PATH="$2"
REMOTE_PROPERTY="$3"

cleanup_inner() {
  rm -f /tmp/seed-users-db-token /tmp/seed-users-db-uri
}
trap cleanup_inner EXIT

if [ ! -s /tmp/seed-users-db-uri ]; then
  echo "ERROR: copied DB URI file is empty" >&2
  exit 1
fi

export BAO_ADDR="http://127.0.0.1:8200"
export BAO_TOKEN="$(cat /tmp/seed-users-db-token)"
bao kv put "${MOUNT_PATH}/${REMOTE_PATH}" "${REMOTE_PROPERTY}=@/tmp/seed-users-db-uri" >/dev/null
bao kv get -field="${REMOTE_PROPERTY}" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
bao read "${MOUNT_PATH}/data/${REMOTE_PATH}" >/dev/null
EOF_INNER

echo "OK: seeded and verified OpenBao ${MOUNT_PATH}/${REMOTE_PATH} property ${REMOTE_PROPERTY}; ESO KV v2 endpoint ${MOUNT_PATH}/data/${REMOTE_PATH} exists."
