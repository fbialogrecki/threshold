#!/usr/bin/env bash
set -euo pipefail
# The library sits next to this script: in ~/bin when installed, or in
# ops/backup/ in the repository.
# shellcheck source=ops/backup/nuc-backup-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/nuc-backup-lib.sh"
require_backup_env
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
STAGING="$(make_runtime_staging daily)"
trap 'rm -rf "$STAGING"' EXIT INT TERM

mkdir -p "$LOG_DIR"
echo "== Daily backup $STAMP =="

echo "-- exporting Kubernetes/Helm metadata --"
export_k8s_metadata "$STAGING"

echo "-- dumping PostgreSQL databases --"
dump_databases "$STAGING"

borg_run create --stats --compression zstd,6 \
  "$BORG_REPO::${HOST_LABEL}-daily-k8s-${STAMP}" \
  "$STAGING"

borg_run create --stats --compression zstd,6 \
  "${common_borg_excludes[@]}" \
  "$BORG_REPO::${HOST_LABEL}-daily-home-${STAMP}" \
  "$BACKUP_HOME"

# /etc, /boot, k3s PVs and SeaweedFS are handled by the root weekly backup.
run_prune
borg list "$BORG_REPO" | tail -20

if (( BACKUP_FAILED )); then
  echo "== Daily backup $STAMP finished WITH ERRORS (see above) ==" >&2
  exit 1
fi
echo "== Daily backup $STAMP OK =="
