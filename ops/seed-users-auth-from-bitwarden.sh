#!/usr/bin/env bash
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# End-to-end helper for Threshold product-auth secret bootstrap.
# Flow:
# 1. Configure/unlock the operator's personal Bitwarden vault (settings in ops/local.env).
# 2. Read BWS_ACCESS_TOKEN from the personal Bitwarden item.
# 3. Use BWS to unseal OpenBao through the existing helper if needed.
# 4. Use BWS to read a write-capable OpenBao token.
# 5. Seed secret/threshold/users/auth via ops/seed-users-auth-openbao.sh.
# 6. Apply/refresh ESO and verify only secret/key presence, never values.

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
ESO_NAMESPACE="${ESO_NAMESPACE:-threshold}"
ESO_CLUSTER_SECRET_STORE_NAME="${ESO_CLUSTER_SECRET_STORE_NAME:-openbao}"
USERS_AUTH_EXTERNAL_SECRET="${USERS_AUTH_EXTERNAL_SECRET:-users-auth}"
USERS_AUTH_K8S_SECRET="${USERS_AUTH_K8S_SECRET:-users-auth}"
USERS_AUTH_MANIFEST="${USERS_AUTH_MANIFEST:-${OPS_DIR}/../infra/kustomize/base/users/auth-external-secret.yaml}"
SEED_USERS_AUTH_SCRIPT="${SEED_USERS_AUTH_SCRIPT:-${OPS_DIR}/seed-users-auth-openbao.sh}"
UNSEAL_SCRIPT="${UNSEAL_SCRIPT:-${OPS_DIR}/openbao-manual-unseal-from-bitwarden.sh}"

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
  # Do not print BASH_COMMAND here. Some failing commands carry sensitive env vars.
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

apply_users_auth_external_secret() {
  log "Applying ExternalSecret manifest so live ESO mapping contains users-auth keys..."
  kubectl apply -n "${ESO_NAMESPACE}" -f "${USERS_AUTH_MANIFEST}" >/dev/null
}

seed_users_auth_openbao() {
  log "Seeding OpenBao product-auth secret via ${SEED_USERS_AUTH_SCRIPT}..."
  OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE}" \
  OPENBAO_POD="${OPENBAO_POD}" \
  BAO_TOKEN="${BAO_TOKEN}" \
  "${SEED_USERS_AUTH_SCRIPT}"
}

force_and_verify_eso() {
  local stamp ready secret_type key_count

  stamp="$(date +%s)"
  log "Forcing ESO refresh for ClusterSecretStore/${ESO_CLUSTER_SECRET_STORE_NAME} and ExternalSecret/${ESO_NAMESPACE}/${USERS_AUTH_EXTERNAL_SECRET}..."
  kubectl annotate clustersecretstore "${ESO_CLUSTER_SECRET_STORE_NAME}" force-sync="${stamp}" --overwrite >/dev/null
  kubectl annotate externalsecret -n "${ESO_NAMESPACE}" "${USERS_AUTH_EXTERNAL_SECRET}" force-sync="${stamp}" --overwrite >/dev/null

  log "Waiting for ExternalSecret/${USERS_AUTH_EXTERNAL_SECRET} Ready=True..."
  for _ in $(seq 1 60); do
    ready="$(kubectl get externalsecret -n "${ESO_NAMESPACE}" "${USERS_AUTH_EXTERNAL_SECRET}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
    if [[ "${ready}" == "True" ]]; then
      break
    fi
    sleep 2
  done

  ready="$(kubectl get externalsecret -n "${ESO_NAMESPACE}" "${USERS_AUTH_EXTERNAL_SECRET}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
  [[ "${ready}" == "True" ]] || {
    kubectl describe externalsecret -n "${ESO_NAMESPACE}" "${USERS_AUTH_EXTERNAL_SECRET}" >&2 || true
    fail "ExternalSecret/${USERS_AUTH_EXTERNAL_SECRET} did not become Ready=True"
  }

  kubectl get secret -n "${ESO_NAMESPACE}" "${USERS_AUTH_K8S_SECRET}" >/dev/null
  secret_type="$(kubectl get secret -n "${ESO_NAMESPACE}" "${USERS_AUTH_K8S_SECRET}" -o jsonpath='{.type}')"
  key_count="$(kubectl get secret -n "${ESO_NAMESPACE}" "${USERS_AUTH_K8S_SECRET}" -o json | jq '.data | keys | length')"

  log "OK: ExternalSecret/${USERS_AUTH_EXTERNAL_SECRET} Ready=True. Secret/${USERS_AUTH_K8S_SECRET} type=${secret_type}, key_count=${key_count}. Values not printed."
  log "Secret keys:"
  kubectl get secret -n "${ESO_NAMESPACE}" "${USERS_AUTH_K8S_SECRET}" -o json \
    | jq -r '.data | keys[]' >&2
}

main() {
  require_tool bw
  require_tool "${BWS_BIN}"
  require_tool jq
  require_tool kubectl
  require_tool date
  require_tool bash
  ops_require_env BWS_SERVER_URL BWS_OPENBAO_TOKEN_SECRET_NAMES

  [[ -x "${UNSEAL_SCRIPT}" ]] || fail "missing or non-executable unseal helper: ${UNSEAL_SCRIPT}"
  [[ -x "${SEED_USERS_AUTH_SCRIPT}" ]] || fail "missing or non-executable seed helper: ${SEED_USERS_AUTH_SCRIPT}"
  [[ -f "${USERS_AUTH_MANIFEST}" ]] || fail "missing users-auth ExternalSecret manifest: ${USERS_AUTH_MANIFEST}"

  log "Starting users-auth bootstrap. Bitwarden server=${BW_SERVER_URL}, BWS server=${BWS_SERVER_URL}."
  ensure_bws_access
  unseal_openbao_if_needed
  read_bao_token_from_bws
  apply_users_auth_external_secret
  seed_users_auth_openbao
  force_and_verify_eso
  log "OK: users-auth OpenBao seed + ESO verification complete. No secret values were printed."
}

main "$@"
