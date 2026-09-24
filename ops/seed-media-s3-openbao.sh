#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-threshold}"
SEAWEEDFS_NAMESPACE="${SEAWEEDFS_NAMESPACE:-seaweedfs}"
CNPG_SECRET_NAME="${CNPG_SECRET_NAME:-users-postgres-backup-s3}"
MEDIA_SECRET_NAME="${MEDIA_SECRET_NAME:-media-s3}"
SEAWEEDFS_SECRET_NAME="${SEAWEEDFS_SECRET_NAME:-seaweedfs-s3-config}"
BUCKET_NAME="${BUCKET_NAME:-threshold-media}"
S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-http://seaweedfs-s3.seaweedfs.svc.cluster.local:8333}"
S3_REGION="${S3_REGION:-us-east-1}"
MOUNT_PATH="${MOUNT_PATH:-secret}"
MEDIA_REMOTE_PATH="${MEDIA_REMOTE_PATH:-threshold/media/s3}"
SEAWEEDFS_REMOTE_PATH="${SEAWEEDFS_REMOTE_PATH:-threshold/seaweedfs/s3}"
OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
OPENBAO_POD="${OPENBAO_POD:-openbao-0}"

for cmd in kubectl openssl python3; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "ERROR: ${cmd} is required" >&2
    exit 1
  fi
done

WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT
chmod 700 "${WORK_DIR}"

kubectl -n "${NAMESPACE}" get secret "${CNPG_SECRET_NAME}" >/dev/null

kubectl -n "${NAMESPACE}" get secret "${CNPG_SECRET_NAME}" \
  -o jsonpath='{.data.ACCESS_KEY_ID}' | base64 -d >"${WORK_DIR}/CNPG_ACCESS_KEY_ID"
kubectl -n "${NAMESPACE}" get secret "${CNPG_SECRET_NAME}" \
  -o jsonpath='{.data.SECRET_ACCESS_KEY}' | base64 -d >"${WORK_DIR}/CNPG_SECRET_ACCESS_KEY"

MEDIA_FORCE_ROTATE="${MEDIA_FORCE_ROTATE:-false}"

if [[ -n "${MEDIA_ACCESS_KEY_ID:-}" && -n "${MEDIA_SECRET_ACCESS_KEY:-}" ]]; then
  :
elif [[ "${MEDIA_FORCE_ROTATE}" != "true" ]] && kubectl -n "${NAMESPACE}" get secret "${MEDIA_SECRET_NAME}" >/dev/null 2>&1; then
  MEDIA_ACCESS_KEY_ID="$(kubectl -n "${NAMESPACE}" get secret "${MEDIA_SECRET_NAME}" -o jsonpath='{.data.S3_ACCESS_KEY_ID}' | base64 -d)"
  MEDIA_SECRET_ACCESS_KEY="$(kubectl -n "${NAMESPACE}" get secret "${MEDIA_SECRET_NAME}" -o jsonpath='{.data.S3_SECRET_ACCESS_KEY}' | base64 -d)"
else
  MEDIA_ACCESS_KEY_ID="media_$(openssl rand -hex 12)"
  MEDIA_SECRET_ACCESS_KEY="$(openssl rand -base64 48 | tr -d '\n')"
fi

if [[ -z "${MEDIA_ACCESS_KEY_ID}" || -z "${MEDIA_SECRET_ACCESS_KEY}" ]]; then
  echo "ERROR: media S3 credentials resolved to empty values" >&2
  exit 1
fi

printf '%s' "${MEDIA_ACCESS_KEY_ID}" >"${WORK_DIR}/MEDIA_ACCESS_KEY_ID"
printf '%s' "${MEDIA_SECRET_ACCESS_KEY}" >"${WORK_DIR}/MEDIA_SECRET_ACCESS_KEY"
chmod 600 "${WORK_DIR}"/*

python3 - "${WORK_DIR}" <<'PY'
import json
import pathlib
import sys

work_dir = pathlib.Path(sys.argv[1])
cnpg_access = (work_dir / "CNPG_ACCESS_KEY_ID").read_text()
cnpg_secret = (work_dir / "CNPG_SECRET_ACCESS_KEY").read_text()
media_access = (work_dir / "MEDIA_ACCESS_KEY_ID").read_text()
media_secret = (work_dir / "MEDIA_SECRET_ACCESS_KEY").read_text()
config = {
    "identities": [
        {
            "name": "thresholdCnpgBackup",
            "credentials": [
                {"accessKey": cnpg_access, "secretKey": cnpg_secret},
            ],
            "actions": ["Admin", "Read", "Write", "List"],
        },
        {
            "name": "thresholdMediaRuntime",
            "credentials": [
                {"accessKey": media_access, "secretKey": media_secret},
            ],
            "actions": ["Read", "Write", "List"],
        },
    ]
}
(work_dir / "seaweedfs_s3_config").write_text(json.dumps(config, separators=(",", ":")))
PY
chmod 600 "${WORK_DIR}/seaweedfs_s3_config"

kubectl -n "${NAMESPACE}" create secret generic "${MEDIA_SECRET_NAME}" \
  --from-literal=S3_ENDPOINT_URL="${S3_ENDPOINT_URL}" \
  --from-literal=S3_BUCKET="${BUCKET_NAME}" \
  --from-literal=S3_REGION="${S3_REGION}" \
  --from-literal=S3_FORCE_PATH_STYLE="true" \
  --from-file=S3_ACCESS_KEY_ID="${WORK_DIR}/MEDIA_ACCESS_KEY_ID" \
  --from-file=S3_SECRET_ACCESS_KEY="${WORK_DIR}/MEDIA_SECRET_ACCESS_KEY" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl -n "${SEAWEEDFS_NAMESPACE}" create secret generic "${SEAWEEDFS_SECRET_NAME}" \
  --from-file=seaweedfs_s3_config="${WORK_DIR}/seaweedfs_s3_config" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

if [[ -n "${BAO_TOKEN:-}" ]]; then
  printf '%s' "${BAO_TOKEN}" >"${WORK_DIR}/bao-token"
  kubectl cp "${WORK_DIR}/bao-token" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/media-s3-token" >/dev/null
  kubectl cp "${WORK_DIR}/MEDIA_ACCESS_KEY_ID" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/media-s3-access-key" >/dev/null
  kubectl cp "${WORK_DIR}/MEDIA_SECRET_ACCESS_KEY" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/media-s3-secret-key" >/dev/null
  kubectl cp "${WORK_DIR}/seaweedfs_s3_config" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:/tmp/seaweedfs-s3-config" >/dev/null
  kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- \
    "${MOUNT_PATH}" "${MEDIA_REMOTE_PATH}" "${SEAWEEDFS_REMOTE_PATH}" <<'EOF_INNER'
set -eu
MOUNT_PATH="$1"
MEDIA_REMOTE_PATH="$2"
SEAWEEDFS_REMOTE_PATH="$3"
cleanup_inner() {
  rm -f /tmp/media-s3-token /tmp/media-s3-access-key /tmp/media-s3-secret-key /tmp/seaweedfs-s3-config
}
trap cleanup_inner EXIT
export BAO_ADDR="http://127.0.0.1:8200"
export BAO_TOKEN="$(cat /tmp/media-s3-token)"
bao kv put "${MOUNT_PATH}/${MEDIA_REMOTE_PATH}" \
  ACCESS_KEY_ID=@/tmp/media-s3-access-key \
  SECRET_ACCESS_KEY=@/tmp/media-s3-secret-key >/dev/null
bao kv put "${MOUNT_PATH}/${SEAWEEDFS_REMOTE_PATH}" \
  seaweedfs_s3_config=@/tmp/seaweedfs-s3-config >/dev/null
bao kv get -field="ACCESS_KEY_ID" "${MOUNT_PATH}/${MEDIA_REMOTE_PATH}" >/dev/null
bao kv get -field="SECRET_ACCESS_KEY" "${MOUNT_PATH}/${MEDIA_REMOTE_PATH}" >/dev/null
bao kv get -field="seaweedfs_s3_config" "${MOUNT_PATH}/${SEAWEEDFS_REMOTE_PATH}" >/dev/null
EOF_INNER
  echo "OK: media S3 credentials and combined SeaweedFS S3 config written to Kubernetes and OpenBao paths."
else
  echo "OK: media S3 credentials and combined SeaweedFS S3 config written to Kubernetes secrets."
  echo "NOTE: BAO_TOKEN not set; OpenBao paths were not updated."
fi

echo "NEXT: restart SeaweedFS S3 gateway, run ops/bootstrap-media-s3-bucket.sh, then ops/cnpg-restore-gate.sh."
