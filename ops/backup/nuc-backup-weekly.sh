#!/usr/bin/env bash
set -euo pipefail
# The library sits next to this script: in ~/bin when installed, or in
# ops/backup/ in the repository.
# shellcheck source=ops/backup/nuc-backup-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/nuc-backup-lib.sh"
require_backup_env
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
STAGING="$(make_runtime_staging weekly)"
cleanup_weekly() {
  rm -rf "$STAGING"
  normalize_repo_ownership
}
trap cleanup_weekly EXIT INT TERM

mkdir -p "$LOG_DIR"
echo "== Weekly backup $STAMP =="

echo "-- exporting Kubernetes/Helm metadata --"
export_k8s_metadata "$STAGING"

echo "-- dumping PostgreSQL databases --"
dump_databases "$STAGING"

borg_run create --stats --compression zstd,6 \
  "$BORG_REPO::${HOST_LABEL}-weekly-k8s-${STAMP}" \
  "$STAGING"

borg_run create --stats --compression zstd,6 \
  "${common_borg_excludes[@]}" \
  "$BORG_REPO::${HOST_LABEL}-weekly-home-${STAMP}" \
  "$BACKUP_HOME"

# Important system and k3s state, plus SeaweedFS (media originals/derivatives
# and the CNPG Barman bucket), which lives outside the k3s storage directory.
# Exclude rebuildable/cache-like heavy artifacts.
system_paths=(/etc /boot /var/lib/rancher/k3s/server /var/lib/rancher/k3s/storage)
for path in /storage/filer_store /ssd/seaweed-master /ssd/object_store; do
  if [[ -d "$path" ]]; then
    system_paths+=("$path")
  else
    fail_step "SeaweedFS path missing: $path"
  fi
done

set +e
tar --one-file-system --xattrs --acls --selinux --warning=no-file-changed -cpf - \
  --exclude='/var/lib/rancher/k3s/storage/*_harbor_harbor-registry' \
  --exclude='/var/lib/rancher/k3s/storage/*_harbor_data-harbor-trivy-0' \
  --exclude='/var/lib/rancher/k3s/agent/containerd' \
  "${system_paths[@]}" \
  2> "$STAGING/system-k3s-tar-warnings.txt" \
| borg create --stats --compression zstd,6 \
  --stdin-name "system-k3s-${STAMP}.tar" \
  "$BORG_REPO::${HOST_LABEL}-weekly-system-k3s-${STAMP}" \
  -
pipe_status=("${PIPESTATUS[@]}")
set -e
# tar exits 1 when files changed while being read and borg exits 1 on
# warnings; only >1 is a real error for either.
if (( pipe_status[0] > 1 || pipe_status[1] > 1 )); then
  fail_step "system/k3s archive failed (tar=${pipe_status[0]}, borg=${pipe_status[1]})"
fi

if [[ -s "$STAGING/system-k3s-tar-warnings.txt" ]]; then
  borg_run create --stats --compression zstd,6 \
    "$BORG_REPO::${HOST_LABEL}-weekly-warnings-${STAMP}" \
    "$STAGING/system-k3s-tar-warnings.txt"
fi

run_prune
borg list "$BORG_REPO" | tail -20

if (( BACKUP_FAILED )); then
  echo "== Weekly backup $STAMP finished WITH ERRORS (see above) ==" >&2
  exit 1
fi
echo "== Weekly backup $STAMP OK =="
