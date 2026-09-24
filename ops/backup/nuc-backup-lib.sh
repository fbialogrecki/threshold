#!/usr/bin/env bash
set -euo pipefail

# cron's PATH has no /usr/local/bin (kubectl) and the root weekly job has no
# kubeconfig of its own; without these every Kubernetes export came out empty.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

# Home directory of the user whose data is backed up. The daily job runs as
# that user, so it is $HOME. The weekly job runs from root's crontab (HOME is
# /root) but from the user's ~/bin, so use the home of whoever owns this file.
# NUC_BACKUP_HOME overrides both.
if [[ -z "${NUC_BACKUP_HOME:-}" ]]; then
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    _nuc_backup_lib_owner="$(stat -c %U -- "${BASH_SOURCE[0]}")"
    NUC_BACKUP_HOME="$(getent passwd "$_nuc_backup_lib_owner" | cut -d: -f6)"
    unset _nuc_backup_lib_owner
  else
    NUC_BACKUP_HOME="$HOME"
  fi
fi
if [[ -z "$NUC_BACKUP_HOME" || ! -d "$NUC_BACKUP_HOME" ]]; then
  echo "ERROR: cannot determine the home directory to back up (set NUC_BACKUP_HOME)" >&2
  exit 1
fi
BACKUP_HOME="$NUC_BACKUP_HOME"
export KUBECONFIG="${KUBECONFIG:-$BACKUP_HOME/.kube/config}"

# config.env defines BACKUP_ROOT, BORG_REPO, HOST_LABEL, LOG_DIR, optionally
# STAGING_BASE, and BACKUP_OWNER (the user that owns the Borg repository; the
# root weekly job hands repo files back to it).
CONFIG_FILE="${NUC_BACKUP_CONFIG:-$BACKUP_HOME/.config/nuc-backup/config.env}"
if [[ ! -r "$CONFIG_FILE" ]]; then
  echo "ERROR: config file not readable: $CONFIG_FILE" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

# Any failed step sets this; entry scripts exit with it at the end so cron and
# the log show a failure instead of a quietly incomplete archive.
BACKUP_FAILED=0

fail_step() {
  echo "ERROR: $*" >&2
  BACKUP_FAILED=1
}

require_backup_env() {
  if [[ ! -d "$BACKUP_ROOT" ]]; then
    echo "ERROR: backup disk not mounted at: $BACKUP_ROOT" >&2
    exit 1
  fi
  if [[ ! -d "$BORG_REPO" ]]; then
    echo "ERROR: Borg repo not found at: $BORG_REPO" >&2
    exit 1
  fi
  export BORG_RELOCATED_REPO_ACCESS_IS_OK=yes
  export BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK=yes
}

# Borg exits 1 for warnings (e.g. an unreadable file) and still writes the
# archive. Under `set -e` that used to abort the script before pruning.
borg_run() {
  local rc=0
  borg "$@" || rc=$?
  if (( rc == 1 )); then
    echo "WARNING: borg $1 finished with warnings" >&2
  elif (( rc > 1 )); then
    fail_step "borg $1 failed with exit code $rc"
  fi
}

common_borg_excludes=(
  --exclude "$BACKUP_HOME/.cache"
  --exclude "$BACKUP_HOME/.local/share/Trash"
  --exclude '*/.local/share/containers'
  --exclude "$BACKUP_HOME/.local/state/nuc-backup-external"
  --exclude "$BACKUP_HOME/llama-cpp-turboquant"
  --exclude "$BACKUP_HOME/BACKUP"
  --exclude '*/node_modules'
  --exclude '*/.next'
  --exclude '*/dist'
  --exclude '*/build'
  --exclude '*/__pycache__'
  --exclude '*/.venv'
  --exclude '*.gguf'
  --exclude '*.safetensors'
  --exclude '*.onnx'
  --exclude '*.bin'
)

make_runtime_staging() {
  local name="$1"
  local base="${STAGING_BASE:-$BACKUP_HOME/.local/state/nuc-backup/runtime}"
  local dir="${base}/${name}-$(date +%Y-%m-%d_%H-%M-%S)"
  mkdir -p "$dir"
  chmod 700 "$base" "$dir"
  echo "$dir"
}

# Run a command into a file; a non-zero exit or an empty file is a failure.
export_to() {
  local file="$1"
  shift
  if ! "$@" > "$file" 2> "$file.err"; then
    fail_step "export failed: $(basename "$file"): $(head -c 300 "$file.err")"
  elif [[ ! -s "$file" ]]; then
    fail_step "export is empty: $(basename "$file")"
  fi
  rm -f "$file.err"
}

export_k8s_metadata() {
  local staging="$1"
  mkdir -p "$staging/helm"
  if ! kubectl get --raw /readyz >/dev/null 2>&1; then
    fail_step "Kubernetes API unreachable with KUBECONFIG=$KUBECONFIG; skipping cluster exports"
    return
  fi
  {
    date --iso-8601=seconds
    uname -a
    borg --version || true
    kubectl version --client=true || true
    echo '--- namespaces ---'; kubectl get ns -o wide || true
    echo '--- nodes ---'; kubectl get nodes -o wide || true
    echo '--- pods ---'; kubectl get pods -A -o wide || true
    echo '--- pvc/pv ---'; kubectl get pvc,pv -A -o wide || true
    echo '--- ingress ---'; kubectl get ingress -A -o wide || true
    echo '--- helm ---'; helm list -A || true
  } > "$staging/cluster-summary.txt" 2>&1

  export_to "$staging/cluster-core.yaml" kubectl get ns,nodes,storageclass,ingressclass,crd -o yaml
  export_to "$staging/workloads-core.yaml" kubectl get all,configmap,secret,serviceaccount,role,rolebinding,pvc,ingress -A -o yaml
  export_to "$staging/external-secrets.yaml" kubectl get externalsecret,clustersecretstore,secretstore -A -o yaml
  export_to "$staging/argocd-applications.yaml" kubectl get applications.argoproj.io -A -o yaml
  export_to "$staging/cnpg-clusters.yaml" kubectl get clusters.postgresql.cnpg.io -A -o yaml
  export_to "$staging/dragonfly.yaml" kubectl get dragonflies -A -o yaml
  export_to "$staging/helm/releases.yaml" helm list -A -o yaml
  local releases
  if ! releases="$(helm list -A -o json | python3 -c 'import json,sys; [print(x["namespace"], x["name"]) for x in json.load(sys.stdin)]')"; then
    fail_step "could not list Helm releases"
    return
  fi
  while read -r ns name; do
    [[ -z "${ns:-}" || -z "${name:-}" ]] && continue
    local safe="${ns}__${name}"
    export_to "$staging/helm/${safe}.values.yaml" helm get values "$name" -n "$ns" -o yaml
    export_to "$staging/helm/${safe}.manifest.yaml" helm get manifest "$name" -n "$ns"
  done <<< "$releases"
}

# Logical dump of every CloudNativePG database. A pg_dump is consistent and
# restorable on its own, unlike the raw PV files in the weekly tar.
dump_databases() {
  local staging="$1"
  mkdir -p "$staging/postgres"
  local clusters
  if ! clusters="$(kubectl get clusters.postgresql.cnpg.io -A \
      -o jsonpath='{range .items[*]}{.metadata.namespace} {.metadata.name} {.status.currentPrimary} {.spec.bootstrap.initdb.database}{"\n"}{end}')"; then
    fail_step "could not list CNPG clusters"
    return
  fi
  while read -r ns cluster primary db; do
    [[ -z "${ns:-}" ]] && continue
    if [[ -z "${primary:-}" || -z "${db:-}" ]]; then
      fail_step "CNPG $ns/$cluster has no primary or database name"
      continue
    fi
    local out="$staging/postgres/${ns}__${cluster}__${db}.dump"
    if ! kubectl -n "$ns" exec "$primary" -c postgres -- pg_dump -Fc -d "$db" > "$out" 2> "$out.err"; then
      fail_step "pg_dump $ns/$cluster/$db failed: $(head -c 300 "$out.err")"
    elif [[ "$(head -c 5 "$out")" != "PGDMP" ]]; then
      fail_step "pg_dump $ns/$cluster/$db did not produce a custom-format dump"
    else
      echo "dumped $ns/$cluster/$db ($(du -h "$out" | cut -f1))"
    fi
    rm -f "$out.err"
  done <<< "$clusters"
}

normalize_repo_ownership() {
  # Weekly backups are run via sudo so they can read /etc, /boot and k3s state.
  # Borg then creates/updates repo segment files as root; hand them back to the
  # normal user so daily backups and `borg list` work without sudo.
  if [[ "${EUID:-$(id -u)}" -eq 0 && -d "$BORG_REPO" ]]; then
    if [[ -z "${BACKUP_OWNER:-}" ]]; then
      echo "ERROR: BACKUP_OWNER is not set in $CONFIG_FILE; Borg repo files may now be owned by root" >&2
      return 1
    fi
    find "$BORG_REPO" \( ! -user "$BACKUP_OWNER" -o ! -group "$BACKUP_OWNER" \) \
      -exec chown "$BACKUP_OWNER:$BACKUP_OWNER" {} +
  fi
}

run_prune() {
  local family
  for family in home system-k3s k8s warnings; do
    borg_run prune --list --stats \
      --glob-archives "*-${family}-*" \
      --keep-daily=7 \
      --keep-weekly=4 \
      --keep-monthly=6 \
      "$BORG_REPO"
  done
  borg_run compact "$BORG_REPO"
}
