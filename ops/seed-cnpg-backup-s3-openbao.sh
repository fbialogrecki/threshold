#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-threshold}"
SEAWEEDFS_NAMESPACE="${SEAWEEDFS_NAMESPACE:-seaweedfs}"
CNPG_SECRET_NAME="${CNPG_SECRET_NAME:-users-postgres-backup-s3}"
SEAWEEDFS_SECRET_NAME="${SEAWEEDFS_SECRET_NAME:-seaweedfs-s3-config}"
BUCKET_NAME="${BUCKET_NAME:-threshold-cnpg-backups}"
MOUNT_PATH="${MOUNT_PATH:-secret}"
REMOTE_PATH="${REMOTE_PATH:-threshold/cnpg/users-postgres/s3}"
OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
OPENBAO_POD="${OPENBAO_POD:-openbao-0}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl is required" >&2
  exit 1
fi
if ! command -v kubectl >/dev/null 2>&1; then
  echo "ERROR: kubectl is required" >&2
  exit 1
fi

S3_ACCESS_ID="${S3_ACCESS_ID:-cnpg_backup_$(openssl rand -hex 8)}"
S3_SECRET_VALUE="${S3_SECRET_VALUE:-$(openssl rand -base64 48 | tr -d '\n')}"
WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

cat >"${WORK_DIR}/seaweedfs_s3_config" <<EOF
{
  "identities": [
    {
      "name": "cnpg-backup",
      "credentials": [
        {
          "accessKey": "${S3_ACCESS_ID}",
          "secretKey": "${S3_SECRET_VALUE}"
        }
      ],
      "actions": [
        "Admin",
        "Read",
        "Write",
        "List"
      ]
    }
  ]
}
EOF
printf '%s' "${S3_ACCESS_ID}" >"${WORK_DIR}/ACCESS_KEY_ID"
printf '%s' "${S3_SECRET_VALUE}" >"${WORK_DIR}/SECRET_ACCESS_KEY"
chmod 600 "${WORK_DIR}"/*

kubectl -n "${NAMESPACE}" create secret generic "${CNPG_SECRET_NAME}" \
  --from-file=ACCESS_KEY_ID="${WORK_DIR}/ACCESS_KEY_ID" \
  --from-file=SECRET_ACCESS_KEY="${WORK_DIR}/SECRET_ACCESS_KEY" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl -n "${SEAWEEDFS_NAMESPACE}" create secret generic "${SEAWEEDFS_SECRET_NAME}" \
  --from-file=seaweedfs_s3_config="${WORK_DIR}/seaweedfs_s3_config" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

if [[ -n "${BAO_TOKEN:-}" ]]; then
  printf '%s' "${BAO_TOKEN}" >"${WORK_DIR}/bao-token"
  kubectl cp "${WORK_DIR}/bao-token" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/cnpg-backup-s3-token" >/dev/null
  kubectl cp "${WORK_DIR}/seaweedfs_s3_config" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/cnpg-backup-s3-config" >/dev/null
  kubectl cp "${WORK_DIR}/ACCESS_KEY_ID" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/cnpg-backup-s3-access-key" >/dev/null
  kubectl cp "${WORK_DIR}/SECRET_ACCESS_KEY" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/cnpg-backup-s3-secret-key" >/dev/null
  kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- "${MOUNT_PATH}" "${REMOTE_PATH}" <<'EOF_INNER'
set -eu
MOUNT_PATH="$1"
REMOTE_PATH="$2"
cleanup_inner() {
  rm -f /tmp/cnpg-backup-s3-token /tmp/cnpg-backup-s3-config /tmp/cnpg-backup-s3-access-key /tmp/cnpg-backup-s3-secret-key
}
trap cleanup_inner EXIT
export BAO_ADDR="http://127.0.0.1:8200"
export BAO_TOKEN="$(cat /tmp/cnpg-backup-s3-token)"
bao kv put "${MOUNT_PATH}/${REMOTE_PATH}" \
  ACCESS_KEY_ID=@/tmp/cnpg-backup-s3-access-key \
  SECRET_ACCESS_KEY=@/tmp/cnpg-backup-s3-secret-key \
  seaweedfs_s3_config=@/tmp/cnpg-backup-s3-config >/dev/null
bao kv get -field="ACCESS_KEY_ID" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
bao kv get -field="SECRET_ACCESS_KEY" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
bao kv get -field="seaweedfs_s3_config" "${MOUNT_PATH}/${REMOTE_PATH}" >/dev/null
EOF_INNER
  echo "OK: CNPG backup S3 credentials written to Kubernetes secrets and OpenBao path ${MOUNT_PATH}/${REMOTE_PATH}."
else
  echo "OK: CNPG backup S3 credentials written to Kubernetes secrets."
  echo "NOTE: BAO_TOKEN not set; OpenBao path ${MOUNT_PATH}/${REMOTE_PATH} was not updated."
fi

echo "NEXT: restart SeaweedFS S3 gateway, create bucket ${BUCKET_NAME}, then run ops/cnpg-restore-gate.sh."
