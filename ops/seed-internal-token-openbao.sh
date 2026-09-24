#!/usr/bin/env bash
set -euo pipefail

OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
APP_NAMESPACE="${APP_NAMESPACE:-threshold}"
SOURCE_SECRET="${SOURCE_SECRET:-social-secrets}"
SOURCE_SECRET_KEY="${SOURCE_SECRET_KEY:-THRESHOLD_INTERNAL_TOKEN}"
MOUNT_PATH="${MOUNT_PATH:-secret}"
REMOTE_PATH="${REMOTE_PATH:-threshold/internal}"
REMOTE_PROPERTY="${REMOTE_PROPERTY:-THRESHOLD_INTERNAL_TOKEN}"

TOKEN_FILE=""
INTERNAL_TOKEN_FILE=""
cleanup() {
  [[ -n "${TOKEN_FILE}" && -f "${TOKEN_FILE}" ]] && rm -f "${TOKEN_FILE}"
  [[ -n "${INTERNAL_TOKEN_FILE}" && -f "${INTERNAL_TOKEN_FILE}" ]] && rm -f "${INTERNAL_TOKEN_FILE}"
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

INTERNAL_TOKEN_B64="$(
  kubectl get secret "${SOURCE_SECRET}" -n "${APP_NAMESPACE}" \
    -o "jsonpath={.data.${SOURCE_SECRET_KEY}}" 2>/dev/null || true
)"

TOKEN_FILE="$(mktemp)"
INTERNAL_TOKEN_FILE="$(mktemp)"
chmod 600 "${TOKEN_FILE}" "${INTERNAL_TOKEN_FILE}"
printf '%s' "${BAO_TOKEN}" > "${TOKEN_FILE}"

if [[ -n "${INTERNAL_TOKEN_B64}" ]]; then
  printf '%s' "${INTERNAL_TOKEN_B64}" | base64 -d > "${INTERNAL_TOKEN_FILE}"
else
  python3 - <<'PY' > "${INTERNAL_TOKEN_FILE}"
import secrets

print(secrets.token_urlsafe(48))
PY
fi

if [[ ! -s "${INTERNAL_TOKEN_FILE}" ]]; then
  echo "ERROR: internal token value is empty" >&2
  exit 1
fi

kubectl cp "${TOKEN_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seed-internal-bao-token" >/dev/null
kubectl cp "${INTERNAL_TOKEN_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seed-internal-token" >/dev/null

kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- \
  "${MOUNT_PATH}" "${REMOTE_PATH}" "${REMOTE_PROPERTY}" <<'EOF_INNER'
set -eu
MOUNT_PATH="$1"
REMOTE_PATH="$2"
REMOTE_PROPERTY="$3"

cleanup_inner() {
  rm -f /tmp/seed-internal-bao-token /tmp/seed-internal-token
}
trap cleanup_inner EXIT

if [ ! -s /tmp/seed-internal-token ]; then
  echo "ERROR: copied internal token file is empty" >&2
  exit 1
fi

export BAO_ADDR="http://127.0.0.1:8200"
export BAO_TOKEN="$(cat /tmp/seed-internal-bao-token)"
bao kv put "${MOUNT_PATH}/${REMOTE_PATH}" "${REMOTE_PROPERTY}=@/tmp/seed-internal-token" >/dev/null
bao kv get -field="${REMOTE_PROPERTY}" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
bao read "${MOUNT_PATH}/data/${REMOTE_PATH}" >/dev/null
EOF_INNER

echo "OK: seeded and verified OpenBao ${MOUNT_PATH}/${REMOTE_PATH} property ${REMOTE_PROPERTY}. Value was not printed."
