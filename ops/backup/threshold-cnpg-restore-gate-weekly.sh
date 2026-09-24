#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/bin:/usr/bin:/bin:${HOME}/.local/bin:${HOME}/bin"
export KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"

# Runs the copy of ops/cnpg-restore-gate.sh installed in ~/bin, so a cron job
# never depends on (or rewrites) a checkout someone is working in.
SCRIPT="${HOME}/bin/cnpg-restore-gate.sh"
STATE_DIR="${HOME}/.local/state/threshold-cnpg-restore-gate"
LOG_FILE="${STATE_DIR}/weekly.log"
LOCK_FILE="${STATE_DIR}/weekly.lock"

mkdir -p "${STATE_DIR}"

{
  echo "===== $(date -Is) threshold CNPG restore gate start ====="

  flock -n 9 || {
    echo "Another restore gate run is already active; exiting."
    exit 0
  }

  "${SCRIPT}"

  echo "===== $(date -Is) threshold CNPG restore gate OK ====="
} 9>"${LOCK_FILE}" >>"${LOG_FILE}" 2>&1
