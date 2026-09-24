#!/usr/bin/env bash
set -euo pipefail

OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
MOUNT_PATH="${MOUNT_PATH:-secret}"
REMOTE_PATH="${REMOTE_PATH:-threshold/seaweedfs/s3}"

ADMIN_ACCESS_KEY="${SEAWEEDFS_S3_ADMIN_ACCESS_KEY:-}"
ADMIN_SECRET_KEY="${SEAWEEDFS_S3_ADMIN_SECRET_KEY:-}"
READ_ACCESS_KEY="${SEAWEEDFS_S3_READ_ACCESS_KEY:-}"
READ_SECRET_KEY="${SEAWEEDFS_S3_READ_SECRET_KEY:-}"

random_token() {
  local bytes="$1"
  openssl rand -base64 "${bytes}" | tr -d '=+/\n' | cut -c1-"${bytes}"
}

if [[ -z "${ADMIN_ACCESS_KEY}" ]]; then
  ADMIN_ACCESS_KEY="$(random_token 20)"
fi

if [[ -z "${ADMIN_SECRET_KEY}" ]]; then
  ADMIN_SECRET_KEY="$(random_token 40)"
fi

if [[ -z "${READ_ACCESS_KEY}" ]]; then
  READ_ACCESS_KEY="$(random_token 20)"
fi

if [[ -z "${READ_SECRET_KEY}" ]]; then
  READ_SECRET_KEY="$(random_token 40)"
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
CONFIG_FILE="$(mktemp)"

cleanup() {
  rm -f "${TOKEN_FILE}" "${CONFIG_FILE}"
}
trap cleanup EXIT

chmod 600 "${TOKEN_FILE}" "${CONFIG_FILE}"
printf '%s' "${BAO_TOKEN}" > "${TOKEN_FILE}"

ADMIN_ACCESS_KEY="${ADMIN_ACCESS_KEY}" \
ADMIN_SECRET_KEY="${ADMIN_SECRET_KEY}" \
READ_ACCESS_KEY="${READ_ACCESS_KEY}" \
READ_SECRET_KEY="${READ_SECRET_KEY}" \
python3 - <<'PY' > "${CONFIG_FILE}"
import json
import os

config = {
    "identities": [
        {
            "name": "thresholdAdmin",
            "credentials": [
                {
                    "accessKey": os.environ["ADMIN_ACCESS_KEY"],
                    "secretKey": os.environ["ADMIN_SECRET_KEY"],
                }
            ],
            "actions": ["Admin", "Read", "Write"],
        },
        {
            "name": "thresholdReadOnly",
            "credentials": [
                {
                    "accessKey": os.environ["READ_ACCESS_KEY"],
                    "secretKey": os.environ["READ_SECRET_KEY"],
                }
            ],
            "actions": ["Read"],
        },
    ]
}
print(json.dumps(config, separators=(",", ":")))
PY

kubectl cp "${TOKEN_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seaweedfs-s3-token" >/dev/null
kubectl cp "${CONFIG_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seaweedfs-s3-config" >/dev/null

kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- "${MOUNT_PATH}" "${REMOTE_PATH}" <<'EOF_INNER'
set -eu

MOUNT_PATH="$1"
REMOTE_PATH="$2"

cleanup_inner() {
  rm -f /tmp/seaweedfs-s3-token /tmp/seaweedfs-s3-config
}
trap cleanup_inner EXIT

export BAO_ADDR="http://127.0.0.1:8200"
export BAO_TOKEN="$(cat /tmp/seaweedfs-s3-token)"

bao kv put "${MOUNT_PATH}/${REMOTE_PATH}" \
  seaweedfs_s3_config=@/tmp/seaweedfs-s3-config >/dev/null

bao kv get -field="seaweedfs_s3_config" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null

echo "OK: OpenBao secret seeded and verified: ${MOUNT_PATH}/${REMOTE_PATH}"
EOF_INNER

echo "OK: SeaweedFS S3 config written without printing credential values."
