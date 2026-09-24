#!/usr/bin/env bash
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# End-to-end helper for Threshold media/SeaweedFS S3 secret bootstrap.
# Flow:
# 1. Configure/unlock the operator's personal Bitwarden vault (settings in ops/local.env).
# 2. Read BWS_ACCESS_TOKEN from the personal Bitwarden item.
# 3. Use BWS to unseal OpenBao through the existing helper if needed.
# 4. Use BWS to read a write-capable OpenBao token.
# 5. Seed OpenBao paths threshold/media/s3 and threshold/seaweedfs/s3 via ops/seed-media-s3-openbao.sh.
# 6. Apply/refresh ExternalSecrets and verify only key names/readiness, never values.
# 7. Restart SeaweedFS S3 gateway, bootstrap media bucket, run hardening checks and CNPG restore gate.

if [[ -z "${KUBECONFIG:-}" && -f "${HOME}/.kube/config" ]]; then
  export KUBECONFIG="${HOME}/.kube/config"
fi

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ops/lib-local-env.sh
source "${OPS_DIR}/lib-local-env.sh"
ops_load_local_env

# Account, server and item names come from ops/local.env (see local.env.example).
BW_ACCOUNT_EMAIL="${BW_ACCOUNT_EMAIL:-}"
BW_SERVER_URL="${BW_SERVER_URL:-}"
BW_BWS_ACCESS_TOKEN_ITEM="${BW_BWS_ACCESS_TOKEN_ITEM:-}"
BW_BWS_ACCESS_TOKEN_FIELD="${BW_BWS_ACCESS_TOKEN_FIELD:-BWS_ACCESS_TOKEN}"
BW_SYNC_BEFORE_READ="${BW_SYNC_BEFORE_READ:-true}"
BW_LOCK_AFTER_RUN="${BW_LOCK_AFTER_RUN:-true}"

BWS_BIN="${BWS_BIN:-bws}"
BWS_SERVER_URL="${BWS_SERVER_URL:-}"
BWS_PROJECT_ID="${BWS_PROJECT_ID:-}"
BWS_OPENBAO_TOKEN_SECRET_NAMES="${BWS_OPENBAO_TOKEN_SECRET_NAMES:-}"

OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
ESO_CLUSTER_SECRET_STORE_NAME="${ESO_CLUSTER_SECRET_STORE_NAME:-openbao}"
SEAWEEDFS_NAMESPACE="${SEAWEEDFS_NAMESPACE:-seaweedfs}"
THRESHOLD_NAMESPACE="${THRESHOLD_NAMESPACE:-threshold}"
SEAWEEDFS_S3_DEPLOYMENT="${SEAWEEDFS_S3_DEPLOYMENT:-seaweedfs-s3}"
SEAWEEDFS_EXTERNAL_SECRET="${SEAWEEDFS_EXTERNAL_SECRET:-seaweedfs-s3-config}"
SEAWEEDFS_K8S_SECRET="${SEAWEEDFS_K8S_SECRET:-seaweedfs-s3-config}"
MEDIA_EXTERNAL_SECRET="${MEDIA_EXTERNAL_SECRET:-media-s3}"
MEDIA_K8S_SECRET="${MEDIA_K8S_SECRET:-media-s3}"

SEAWEEDFS_ES_MANIFEST="${SEAWEEDFS_ES_MANIFEST:-${OPS_DIR}/../infra/kustomize/base/object-storage/seaweedfs-s3-config-external-secret.yaml}"
MEDIA_ES_MANIFEST="${MEDIA_ES_MANIFEST:-${OPS_DIR}/../infra/kustomize/base/media/media-s3-external-secret.yaml}"
SEED_MEDIA_SCRIPT="${SEED_MEDIA_SCRIPT:-${OPS_DIR}/seed-media-s3-openbao.sh}"
UNSEAL_SCRIPT="${UNSEAL_SCRIPT:-${OPS_DIR}/openbao-manual-unseal-from-bitwarden.sh}"
BOOTSTRAP_BUCKET_SCRIPT="${BOOTSTRAP_BUCKET_SCRIPT:-${OPS_DIR}/bootstrap-media-s3-bucket.sh}"
VERIFY_HARDENING_SCRIPT="${VERIFY_HARDENING_SCRIPT:-${OPS_DIR}/verify-seaweedfs-s3-hardening.sh}"
CNPG_RESTORE_GATE_SCRIPT="${CNPG_RESTORE_GATE_SCRIPT:-${OPS_DIR}/cnpg-restore-gate.sh}"
RUN_CNPG_RESTORE_GATE="${RUN_CNPG_RESTORE_GATE:-true}"
MEDIA_FORCE_ROTATE="${MEDIA_FORCE_ROTATE:-false}"

BW_SESSION="${BW_SESSION:-}"
BW_SESSION_CREATED_BY_SCRIPT="false"
BW_MASTER_PASSWORD_SET_BY_SCRIPT="false"
BWS_ACCESS_TOKEN_SET_BY_SCRIPT="false"
BAO_TOKEN_SET_BY_SCRIPT="false"

log() {
  printf '%s\n' "$*" >&2
}

fail() {
  log "ERROR: $*"
  exit 1
}

on_error() {
  local exit_code="$?"
  local line_no="${BASH_LINENO[0]:-unknown}"
  # Do not print BASH_COMMAND. Some commands carry sensitive env vars.
  log "ERROR: command failed at line ${line_no} with exit code ${exit_code}"
  exit "${exit_code}"
}
trap on_error ERR

cleanup() {
  if [[ "${BW_SESSION_CREATED_BY_SCRIPT}" == "true" && "${BW_LOCK_AFTER_RUN}" == "true" && -n "${BW_SESSION}" ]]; then
    bw --session "${BW_SESSION}" --quiet lock >/dev/null 2>&1 || true
  fi
  if [[ "${BWS_ACCESS_TOKEN_SET_BY_SCRIPT}" == "true" ]]; then
    unset BWS_ACCESS_TOKEN
  fi
  if [[ "${BAO_TOKEN_SET_BY_SCRIPT}" == "true" ]]; then
    unset BAO_TOKEN
  fi
  if [[ "${BW_MASTER_PASSWORD_SET_BY_SCRIPT}" == "true" ]]; then
    unset BW_MASTER_PASSWORD
  fi
  unset BW_SESSION
}
trap cleanup EXIT

require_tool() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required tool: $1"
}

require_file() {
  [[ -f "$1" ]] || fail "missing file: $1"
}

require_executable() {
  [[ -x "$1" ]] || fail "missing or non-executable script: $1"
}

bw_status_json() {
  bw status --raw 2>/dev/null || printf '{"status":"unknown"}'
}

bw_vault_cmd() {
  if [[ -n "${BW_SESSION}" ]]; then
    bw --session "${BW_SESSION}" "$@"
  else
    bw "$@"
  fi
}

read_bw_master_password() {
  if ! { : < /dev/tty; } 2>/dev/null; then
    fail "Bitwarden login/unlock needs an interactive TTY for the master password"
  fi

  printf 'Bitwarden master password for %s (input hidden): ' "${BW_ACCOUNT_EMAIL}" > /dev/tty
  IFS= read -rs BW_MASTER_PASSWORD < /dev/tty
  printf '\n' > /dev/tty
  export BW_MASTER_PASSWORD
  BW_MASTER_PASSWORD_SET_BY_SCRIPT="true"
}

clear_bw_master_password() {
  if [[ "${BW_MASTER_PASSWORD_SET_BY_SCRIPT}" == "true" ]]; then
    unset BW_MASTER_PASSWORD
    BW_MASTER_PASSWORD_SET_BY_SCRIPT="false"
  fi
}

ensure_bw_session() {
  local status_json status user_email

  log "Configuring Bitwarden CLI server: ${BW_SERVER_URL}..."
  if ! bw --quiet config server "${BW_SERVER_URL}" >/dev/null 2>&1; then
    log "Bitwarden CLI refused server switch. Logging out stale/current session, then retrying server config..."
    bw --quiet logout >/dev/null 2>&1 || true
    bw --quiet config server "${BW_SERVER_URL}" >/dev/null \
      || fail "failed to configure Bitwarden CLI server: ${BW_SERVER_URL}"
  fi

  status_json="$(bw_status_json)"
  status="$(jq -r '.status // "unknown"' <<<"${status_json}")"
  user_email="$(jq -r '.userEmail // empty' <<<"${status_json}")"

  if [[ "${status}" != "unauthenticated" && -n "${user_email}" && "${user_email}" != "${BW_ACCOUNT_EMAIL}" ]]; then
    log "Bitwarden CLI is logged into ${user_email}, expected ${BW_ACCOUNT_EMAIL}. Logging out before switching account..."
    bw --quiet logout >/dev/null 2>&1 || true
    status="unauthenticated"
  fi

  case "${status}" in
    unlocked)
      log "Bitwarden CLI is already unlocked for ${BW_ACCOUNT_EMAIL}."
      ;;
    locked)
      log "Bitwarden vault is locked for ${BW_ACCOUNT_EMAIL}."
      read_bw_master_password
      BW_SESSION="$(bw unlock --passwordenv BW_MASTER_PASSWORD --raw)"
      clear_bw_master_password
      [[ -n "${BW_SESSION}" ]] || fail "Bitwarden unlock returned an empty session"
      BW_SESSION_CREATED_BY_SCRIPT="true"
      ;;
    unauthenticated)
      log "Bitwarden CLI is not logged in. Logging into ${BW_ACCOUNT_EMAIL} on ${BW_SERVER_URL}."
      read_bw_master_password
      BW_SESSION="$(bw login "${BW_ACCOUNT_EMAIL}" --passwordenv BW_MASTER_PASSWORD --raw)"
      clear_bw_master_password
      [[ -n "${BW_SESSION}" ]] || fail "Bitwarden login returned an empty session"
      BW_SESSION_CREATED_BY_SCRIPT="true"
      ;;
    *)
      fail "unexpected Bitwarden status: ${status}"
      ;;
  esac

  if [[ "${BW_SYNC_BEFORE_READ}" == "true" ]]; then
    log "Syncing Bitwarden personal vault metadata..."
    bw_vault_cmd sync --quiet >/dev/null
  fi
}

read_bws_access_token_from_bw() {
  local item_json token

  ops_require_env BW_ACCOUNT_EMAIL BW_SERVER_URL BW_BWS_ACCESS_TOKEN_ITEM
  ensure_bw_session

  log "Reading BWS access token from Bitwarden item '${BW_BWS_ACCESS_TOKEN_ITEM}'..."
  item_json="$(bw_vault_cmd get item "${BW_BWS_ACCESS_TOKEN_ITEM}")"

  token="$(jq -er --arg field "${BW_BWS_ACCESS_TOKEN_FIELD}" '
    [
      ((.fields // [])[]? | select(.name == $field) | .value),
      ((.fields // [])[]? | select(.name == "BWS_ACCESS_TOKEN") | .value),
      (.login.password?),
      (.notes?)
    ]
    | map(select(type == "string" and length > 0))
    | .[0] // empty
  ' <<<"${item_json}")"

  [[ -n "${token}" ]] || fail "Bitwarden item '${BW_BWS_ACCESS_TOKEN_ITEM}' does not contain a BWS access token"

  export BWS_ACCESS_TOKEN="${token}"
  BWS_ACCESS_TOKEN_SET_BY_SCRIPT="true"
  unset token item_json
}

bws_base_cmd() {
  "${BWS_BIN}" --server-url "${BWS_SERVER_URL}" -o json "$@"
}

bws_secret_list() {
  if [[ -n "${BWS_PROJECT_ID}" ]]; then
    bws_base_cmd secret list "${BWS_PROJECT_ID}"
  else
    bws_base_cmd secret list
  fi
}

ensure_bws_access() {
  if [[ -z "${BWS_ACCESS_TOKEN:-}" ]]; then
    read_bws_access_token_from_bw
  else
    log "Using BWS_ACCESS_TOKEN from current process environment."
  fi

  log "Checking Bitwarden Secrets Manager access against ${BWS_SERVER_URL}..."
  bws_secret_list >/dev/null
}

secret_names_array() {
  local names_string="$1"
  local -n out_ref="$2"
  IFS='|' read -r -a out_ref <<<"${names_string}"
}

extract_secret_value() {
  local secrets_json="$1"
  local secret_name="$2"

  jq -er --arg name "${secret_name}" '
    def items:
      if type == "array" then .
      elif type == "object" and (.secrets | type == "array") then .secrets
      elif type == "object" and (.data | type == "array") then .data
      else []
      end;

    [
      (items[]? | select((.key // .name // "") == $name) | .value)
    ]
    | map(select(type == "string" and length > 0))
    | .[0] // empty
  ' <<<"${secrets_json}"
}

read_bao_token_from_bws() {
  local secrets_json secret_name token
  local -a secret_names

  ensure_bws_access
  log "Reading write-capable OpenBao token from BWS. Candidate secret names: ${BWS_OPENBAO_TOKEN_SECRET_NAMES}"
  secrets_json="$(bws_secret_list)"
  secret_names_array "${BWS_OPENBAO_TOKEN_SECRET_NAMES}" secret_names

  for secret_name in "${secret_names[@]}"; do
    [[ -n "${secret_name}" ]] || continue
    if token="$(extract_secret_value "${secrets_json}" "${secret_name}" 2>/dev/null)" && [[ -n "${token}" ]]; then
      export BAO_TOKEN="${token}"
      BAO_TOKEN_SET_BY_SCRIPT="true"
      log "OK: OpenBao token found in BWS secret '${secret_name}'. Value not printed."
      unset token secrets_json
      return 0
    fi
  done

  fail "No non-empty OpenBao token found in BWS. Set BWS_OPENBAO_TOKEN_SECRET_NAMES='Exact Secret Name' if your name differs."
}

unseal_openbao_if_needed() {
  log "Ensuring OpenBao is unsealed using existing Bitwarden/BWS helper..."
  OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE}" \
  OPENBAO_POD="${OPENBAO_POD}" \
  BWS_ACCESS_TOKEN="${BWS_ACCESS_TOKEN}" \
  BW_LOCK_AFTER_RUN="false" \
  "${UNSEAL_SCRIPT}"
}

apply_external_secret_manifests() {
  log "Applying ExternalSecret manifests before ESO refresh..."
  kubectl apply -f "${SEAWEEDFS_ES_MANIFEST}" >/dev/null
  # The media manifest takes its namespace from kustomize, so set it here.
  kubectl apply -n "${THRESHOLD_NAMESPACE}" -f "${MEDIA_ES_MANIFEST}" >/dev/null
}

seed_openbao_and_k8s_secrets() {
  log "Seeding media S3 and SeaweedFS gateway config via ${SEED_MEDIA_SCRIPT}..."
  OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE}" \
  OPENBAO_POD="${OPENBAO_POD}" \
  NAMESPACE="${THRESHOLD_NAMESPACE}" \
  SEAWEEDFS_NAMESPACE="${SEAWEEDFS_NAMESPACE}" \
  MEDIA_FORCE_ROTATE="${MEDIA_FORCE_ROTATE}" \
  BAO_TOKEN="${BAO_TOKEN}" \
  "${SEED_MEDIA_SCRIPT}"
}

force_and_verify_external_secret() {
  local namespace="$1"
  local external_secret="$2"
  local k8s_secret="$3"
  local ready key_count secret_type

  log "Waiting for ExternalSecret/${namespace}/${external_secret} Ready=True..."
  for _ in $(seq 1 90); do
    ready="$(kubectl get externalsecret -n "${namespace}" "${external_secret}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
    if [[ "${ready}" == "True" ]]; then
      break
    fi
    sleep 2
  done

  ready="$(kubectl get externalsecret -n "${namespace}" "${external_secret}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
  [[ "${ready}" == "True" ]] || {
    kubectl describe externalsecret -n "${namespace}" "${external_secret}" >&2 || true
    fail "ExternalSecret/${namespace}/${external_secret} did not become Ready=True"
  }

  kubectl get secret -n "${namespace}" "${k8s_secret}" >/dev/null
  secret_type="$(kubectl get secret -n "${namespace}" "${k8s_secret}" -o jsonpath='{.type}')"
  key_count="$(kubectl get secret -n "${namespace}" "${k8s_secret}" -o json | jq '.data | keys | length')"

  log "OK: ExternalSecret/${namespace}/${external_secret} Ready=True. Secret/${k8s_secret} type=${secret_type}, key_count=${key_count}. Values not printed."
  log "Secret keys for ${namespace}/${k8s_secret}:"
  kubectl get secret -n "${namespace}" "${k8s_secret}" -o json | jq -r '.data | keys[]' >&2
}

force_and_verify_eso() {
  local stamp

  stamp="$(date +%s)"
  log "Forcing ESO refresh for ClusterSecretStore/${ESO_CLUSTER_SECRET_STORE_NAME} and media/S3 ExternalSecrets..."
  kubectl annotate clustersecretstore "${ESO_CLUSTER_SECRET_STORE_NAME}" force-sync="${stamp}" --overwrite >/dev/null
  kubectl annotate externalsecret -n "${SEAWEEDFS_NAMESPACE}" "${SEAWEEDFS_EXTERNAL_SECRET}" force-sync="${stamp}" --overwrite >/dev/null
  kubectl annotate externalsecret -n "${THRESHOLD_NAMESPACE}" "${MEDIA_EXTERNAL_SECRET}" force-sync="${stamp}" --overwrite >/dev/null

  force_and_verify_external_secret "${SEAWEEDFS_NAMESPACE}" "${SEAWEEDFS_EXTERNAL_SECRET}" "${SEAWEEDFS_K8S_SECRET}"
  force_and_verify_external_secret "${THRESHOLD_NAMESPACE}" "${MEDIA_EXTERNAL_SECRET}" "${MEDIA_K8S_SECRET}"
}

restart_s3_gateway() {
  local pod_name logs

  log "Restarting SeaweedFS S3 gateway so it loads ESO-backed config..."
  kubectl -n "${SEAWEEDFS_NAMESPACE}" rollout restart "deploy/${SEAWEEDFS_S3_DEPLOYMENT}" >/dev/null
  kubectl -n "${SEAWEEDFS_NAMESPACE}" rollout status "deploy/${SEAWEEDFS_S3_DEPLOYMENT}" --timeout=180s >/dev/null

  pod_name="$(kubectl -n "${SEAWEEDFS_NAMESPACE}" get pods \
    -l "app.kubernetes.io/component=s3,app.kubernetes.io/instance=seaweedfs,app.kubernetes.io/name=seaweedfs" \
    --sort-by=.metadata.creationTimestamp \
    -o jsonpath='{.items[-1].metadata.name}')"
  [[ -n "${pod_name}" ]] || fail "could not resolve newest SeaweedFS S3 pod"

  for _ in $(seq 1 30); do
    logs="$(kubectl -n "${SEAWEEDFS_NAMESPACE}" logs "pod/${pod_name}" --since=5m 2>/dev/null || true)"
    if grep -Eq 'Loaded 2 identities|S3 authentication enabled' <<<"${logs}"; then
      log "OK: SeaweedFS S3 gateway restarted and auth loaded in pod/${pod_name}."
      return 0
    fi
    sleep 2
  done

  kubectl -n "${SEAWEEDFS_NAMESPACE}" logs "pod/${pod_name}" --tail=180 >&2 || true
  fail "SeaweedFS S3 logs did not show auth identities after restart in pod/${pod_name}"
}

run_post_seed_gates() {
  log "Bootstrapping media S3 bucket..."
  "${BOOTSTRAP_BUCKET_SCRIPT}"

  log "Running SeaweedFS S3 hardening verification..."
  "${VERIFY_HARDENING_SCRIPT}"

  if [[ "${RUN_CNPG_RESTORE_GATE}" == "true" ]]; then
    log "Running CNPG backup+restore gate because S3 auth/network/restart changed..."
    "${CNPG_RESTORE_GATE_SCRIPT}"
  else
    log "Skipping CNPG restore gate because RUN_CNPG_RESTORE_GATE=${RUN_CNPG_RESTORE_GATE}."
  fi
}

main() {
  require_tool bw
  require_tool "${BWS_BIN}"
  require_tool jq
  require_tool kubectl
  require_tool date
  require_tool bash
  require_tool grep
  ops_require_env BWS_SERVER_URL BWS_OPENBAO_TOKEN_SECRET_NAMES

  require_file "${SEAWEEDFS_ES_MANIFEST}"
  require_file "${MEDIA_ES_MANIFEST}"
  require_executable "${UNSEAL_SCRIPT}"
  require_executable "${SEED_MEDIA_SCRIPT}"
  require_executable "${BOOTSTRAP_BUCKET_SCRIPT}"
  require_executable "${VERIFY_HARDENING_SCRIPT}"
  require_executable "${CNPG_RESTORE_GATE_SCRIPT}"

  log "Starting media/SeaweedFS S3 bootstrap. Bitwarden server=${BW_SERVER_URL}, BWS server=${BWS_SERVER_URL}."
  ensure_bws_access
  unseal_openbao_if_needed
  read_bao_token_from_bws
  seed_openbao_and_k8s_secrets
  apply_external_secret_manifests
  force_and_verify_eso
  restart_s3_gateway
  run_post_seed_gates
  log "OK: media/SeaweedFS S3 OpenBao seed + ESO + S3 + CNPG verification complete. No secret values were printed."
}

main "$@"
