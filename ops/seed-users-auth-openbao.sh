#!/usr/bin/env bash
set -euo pipefail

OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
MOUNT_PATH="${MOUNT_PATH:-secret}"
REMOTE_PATH="${REMOTE_PATH:-threshold/users/auth}"

TOKEN_FILE=""
SECRETS_FILE=""
cleanup() {
  [[ -n "${TOKEN_FILE}" && -f "${TOKEN_FILE}" ]] && rm -f "${TOKEN_FILE}"
  [[ -n "${SECRETS_FILE}" && -f "${SECRETS_FILE}" ]] && rm -f "${SECRETS_FILE}"
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

TOKEN_FILE="$(mktemp)"
SECRETS_FILE="$(mktemp)"
chmod 600 "${TOKEN_FILE}" "${SECRETS_FILE}"
printf '%s' "${BAO_TOKEN}" > "${TOKEN_FILE}"
python3 - <<'PY' > "${SECRETS_FILE}"
import secrets

print(f"THRESHOLD_AUTH_PASSWORD_PEPPER_CURRENT={secrets.token_urlsafe(48)}")
print("THRESHOLD_AUTH_PASSWORD_PEPPER_VERSION=1")
print(f"THRESHOLD_AUTH_SESSION_TOKEN_HMAC_KEY={secrets.token_urlsafe(48)}")
print(f"THRESHOLD_AUTH_AUDIT_HASH_KEY={secrets.token_urlsafe(48)}")
PY

kubectl cp "${TOKEN_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seed-users-auth-token" >/dev/null
kubectl cp "${SECRETS_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seed-users-auth-values" >/dev/null

kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- \
  "${MOUNT_PATH}" "${REMOTE_PATH}" <<'EOF_INNER'
set -eu
MOUNT_PATH="$1"
REMOTE_PATH="$2"

cleanup_inner() {
  rm -f /tmp/seed-users-auth-token /tmp/seed-users-auth-values /tmp/seed-users-auth-THRESHOLD_*
}
trap cleanup_inner EXIT

export BAO_ADDR="http://127.0.0.1:8200"
export BAO_TOKEN="$(cat /tmp/seed-users-auth-token)"

set --
while IFS='=' read -r key value; do
  value_file="/tmp/seed-users-auth-${key}"
  printf '%s' "${value}" > "${value_file}"
  set -- "$@" "${key}=@${value_file}"
done < /tmp/seed-users-auth-values
bao kv put "${MOUNT_PATH}/${REMOTE_PATH}" "$@" >/dev/null
bao kv get -field="THRESHOLD_AUTH_PASSWORD_PEPPER_CURRENT" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
bao kv get -field="THRESHOLD_AUTH_SESSION_TOKEN_HMAC_KEY" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
bao kv get -field="THRESHOLD_AUTH_AUDIT_HASH_KEY" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
bao read "${MOUNT_PATH}/data/${REMOTE_PATH}" >/dev/null
EOF_INNER

echo "OK: seeded and verified OpenBao ${MOUNT_PATH}/${REMOTE_PATH} auth secret properties. Values were not printed."
