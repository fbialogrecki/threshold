#!/usr/bin/env bash
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# Manual OpenBao unseal helper for the local Threshold cluster.
# Security model:
# - Personal Bitwarden CLI (bw) logs into the account configured in ops/local.env if needed.
# - BWS_ACCESS_TOKEN is read from the personal vault item named by BW_BWS_ACCESS_TOKEN_ITEM.
# - OpenBao unseal keys live in Bitwarden Secrets Manager (BWS), not on disk.
# - Secret values are read into process memory only and sent to OpenBao's local API.
# - Secret values are never printed.

if [[ -z "${KUBECONFIG:-}" && -f "${HOME}/.kube/config" ]]; then
  export KUBECONFIG="${HOME}/.kube/config"
fi

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ops/lib-local-env.sh
source "${OPS_DIR}/lib-local-env.sh"
ops_load_local_env

OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
OPENBAO_LOCAL_PORT="${OPENBAO_LOCAL_PORT:-18200}"
OPENBAO_ADDR="${OPENBAO_ADDR:-http://127.0.0.1:${OPENBAO_LOCAL_PORT}}"
OPENBAO_UNSEAL_THRESHOLD="${OPENBAO_UNSEAL_THRESHOLD:-3}"

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
# "|"-separated BWS secret names holding the unseal key shares, in submit order.
BWS_OPENBAO_UNSEAL_SECRET_NAMES="${BWS_OPENBAO_UNSEAL_SECRET_NAMES:-}"
BWS_VALIDATE_ONLY="${BWS_VALIDATE_ONLY:-false}"
ESO_FORCE_REFRESH_AFTER_UNSEAL="${ESO_FORCE_REFRESH_AFTER_UNSEAL:-true}"
ESO_CLUSTER_SECRET_STORE_NAME="${ESO_CLUSTER_SECRET_STORE_NAME:-openbao}"

BW_SESSION="${BW_SESSION:-}"
BW_SESSION_CREATED_BY_SCRIPT="false"
BW_MASTER_PASSWORD_SET_BY_SCRIPT="false"
BWS_ACCESS_TOKEN_SET_BY_SCRIPT="false"
PORT_FORWARD_PID=""

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
  log "ERROR: command failed at line ${line_no} with exit code ${exit_code}: ${BASH_COMMAND}"
  exit "${exit_code}"
}

cleanup() {
  if [[ -n "${PORT_FORWARD_PID}" ]]; then
    kill "${PORT_FORWARD_PID}" >/dev/null 2>&1 || true
    wait "${PORT_FORWARD_PID}" >/dev/null 2>&1 || true
  fi

  if [[ "${BW_SESSION_CREATED_BY_SCRIPT}" == "true" && "${BW_LOCK_AFTER_RUN}" == "true" && -n "${BW_SESSION}" ]]; then
    bw --session "${BW_SESSION}" --quiet lock >/dev/null 2>&1 || true
  fi

  if [[ "${BWS_ACCESS_TOKEN_SET_BY_SCRIPT}" == "true" ]]; then
    unset BWS_ACCESS_TOKEN
  fi
  if [[ "${BW_MASTER_PASSWORD_SET_BY_SCRIPT}" == "true" ]]; then
    unset BW_MASTER_PASSWORD
  fi
  unset BW_SESSION
}
trap cleanup EXIT
trap on_error ERR

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

ensure_bws_access() {
  if [[ -z "${BWS_ACCESS_TOKEN:-}" ]]; then
    read_bws_access_token_from_bw
  else
    log "Using BWS_ACCESS_TOKEN from current process environment."
  fi

  log "Checking Bitwarden Secrets Manager access against ${BWS_SERVER_URL}..."
  bws_secret_list >/dev/null
}

bws_secret_list() {
  if [[ -n "${BWS_PROJECT_ID}" ]]; then
    bws_base_cmd secret list "${BWS_PROJECT_ID}"
  else
    bws_base_cmd secret list
  fi
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

validate_bws_secrets() {
  local secrets_json secret_name value
  local -a secret_names_array_values

  ensure_bws_access
  secrets_json="$(bws_secret_list)"
  secret_names_array "${BWS_OPENBAO_UNSEAL_SECRET_NAMES}" secret_names_array_values

  for secret_name in "${secret_names_array_values[@]}"; do
    [[ -n "${secret_name}" ]] || continue
    if ! value="$(extract_secret_value "${secrets_json}" "${secret_name}")"; then
      fail "BWS secret not found or empty: ${secret_name}"
    fi
    [[ -n "${value}" ]] || fail "BWS secret is empty: ${secret_name}"
    unset value
    log "OK: BWS secret available: ${secret_name}"
  done

  unset secrets_json
}

start_port_forward() {
  log "Opening local port-forward ${OPENBAO_ADDR} -> ${OPENBAO_NAMESPACE}/${OPENBAO_POD}:8200..."
  kubectl port-forward -n "${OPENBAO_NAMESPACE}" "pod/${OPENBAO_POD}" "${OPENBAO_LOCAL_PORT}:8200" >/tmp/threshold-openbao-port-forward.log 2>&1 &
  PORT_FORWARD_PID="$!"

  for _ in $(seq 1 40); do
    # /sys/health returns non-2xx status codes for valid states such as sealed.
    # Any HTTP response means the port-forward is ready.
    http_code="$(curl -sS -o /dev/null -w '%{http_code}' "${OPENBAO_ADDR}/v1/sys/health" 2>/dev/null || true)"
    if [[ "${http_code}" != "000" && -n "${http_code}" ]]; then
      return 0
    fi
    if ! kill -0 "${PORT_FORWARD_PID}" >/dev/null 2>&1; then
      log "Port-forward log:"
      sed -n '1,120p' /tmp/threshold-openbao-port-forward.log >&2 || true
      fail "kubectl port-forward exited early"
    fi
    sleep 0.25
  done

  log "Port-forward log:"
  sed -n '1,120p' /tmp/threshold-openbao-port-forward.log >&2 || true
  fail "OpenBao health endpoint did not become reachable through port-forward"
}

openbao_health_json() {
  curl -sS "${OPENBAO_ADDR}/v1/sys/health" || true
}

openbao_pod_ready_status() {
  kubectl get pod -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" --no-headers \
    | awk '{ print $2 }'
}

openbao_pod_looks_unsealed() {
  local ready
  ready="$(openbao_pod_ready_status)"
  [[ "${ready}" == "1/1" ]]
}

log_openbao_pod_state() {
  local ready status restart_count started_at
  ready="$(openbao_pod_ready_status)"
  status="$(kubectl get pod -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -o jsonpath='{.status.phase}')"
  restart_count="$(kubectl get pod -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -o jsonpath='{.status.containerStatuses[0].restartCount}')"
  started_at="$(kubectl get pod -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -o jsonpath='{.status.startTime}')"
  log "OpenBao pod state: READY=${ready}, STATUS=${status}, RESTARTS=${restart_count}, STARTED_AT=${started_at}"
}

openbao_is_sealed() {
  local health
  health="$(openbao_health_json)"
  if ! jq -e . >/dev/null 2>&1 <<<"${health}"; then
    log "OpenBao health endpoint returned non-JSON response: ${health}"
    return 1
  fi
  jq -er '.sealed == true' <<<"${health}" >/dev/null 2>&1
}

unseal_with_key() {
  local key="$1"
  local response sealed progress threshold

  response="$(jq -nc --arg key "${key}" '{key: $key}' \
    | curl -fsS -X PUT -H 'Content-Type: application/json' --data-binary @- "${OPENBAO_ADDR}/v1/sys/unseal")"

  sealed="$(jq -r '.sealed' <<<"${response}")"
  progress="$(jq -r '.progress' <<<"${response}")"
  threshold="$(jq -r '.t' <<<"${response}")"

  log "Unseal response: sealed=${sealed}, progress=${progress}/${threshold}"
}

force_refresh_external_secrets() {
  local stamp ns name ready status

  if [[ "${ESO_FORCE_REFRESH_AFTER_UNSEAL}" != "true" ]]; then
    log "Skipping External Secrets refresh because ESO_FORCE_REFRESH_AFTER_UNSEAL=${ESO_FORCE_REFRESH_AFTER_UNSEAL}."
    return 0
  fi

  if ! kubectl get clustersecretstore "${ESO_CLUSTER_SECRET_STORE_NAME}" >/dev/null 2>&1; then
    log "External Secrets ClusterSecretStore '${ESO_CLUSTER_SECRET_STORE_NAME}' not found. Skipping ESO refresh."
    return 0
  fi

  stamp="$(date +%s)"
  log "Forcing External Secrets refresh for ClusterSecretStore '${ESO_CLUSTER_SECRET_STORE_NAME}'..."
  kubectl annotate clustersecretstore "${ESO_CLUSTER_SECRET_STORE_NAME}" force-sync="${stamp}" --overwrite >/dev/null

  while read -r ns name; do
    [[ -n "${ns}" && -n "${name}" ]] || continue
    log "Forcing ExternalSecret refresh: ${ns}/${name}"
    kubectl annotate externalsecret -n "${ns}" "${name}" force-sync="${stamp}" --overwrite >/dev/null
  done < <(
    kubectl get externalsecrets -A -o json \
      | jq -r --arg store "${ESO_CLUSTER_SECRET_STORE_NAME}" '
          .items[]?
          | select(.spec.secretStoreRef.kind == "ClusterSecretStore" and .spec.secretStoreRef.name == $store)
          | [.metadata.namespace, .metadata.name]
          | @tsv
        '
  )

  sleep 5
  ready="$(kubectl get clustersecretstore "${ESO_CLUSTER_SECRET_STORE_NAME}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
  status="$(kubectl get clustersecretstore "${ESO_CLUSTER_SECRET_STORE_NAME}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].reason}' 2>/dev/null || true)"
  log "ClusterSecretStore '${ESO_CLUSTER_SECRET_STORE_NAME}' ready=${ready:-unknown}, status=${status:-unknown}."

  kubectl get externalsecrets -A >&2 || true
}

main() {
  require_tool bw
  require_tool "${BWS_BIN}"
  require_tool curl
  require_tool jq
  require_tool kubectl
  require_tool sed
  require_tool date
  require_tool awk
  ops_require_env BWS_SERVER_URL BWS_OPENBAO_UNSEAL_SECRET_NAMES

  if [[ "${BWS_VALIDATE_ONLY}" == "true" ]]; then
    validate_bws_secrets
    log "OK: BWS validation passed. Secret values were not printed."
    exit 0
  fi

  kubectl get pod -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" >/dev/null

  log_openbao_pod_state
  if openbao_pod_looks_unsealed; then
    log "OpenBao pod is ready. Treating as already unsealed."
    force_refresh_external_secrets
    exit 0
  fi

  log "OpenBao pod is not ready. Treating as sealed and starting Bitwarden/BWS unseal flow..."

  start_port_forward

  log "Confirming OpenBao sealed state through local health endpoint..."
  if ! openbao_is_sealed; then
    log "OpenBao health endpoint says it is already unsealed."
    force_refresh_external_secrets
    exit 0
  fi

  local secrets_json secret_name key keys_provided
  local -a secret_names_array_values

  log "Preparing BWS access..."
  ensure_bws_access
  log "BWS access ready. Reading OpenBao unseal secrets..."
  secrets_json="$(bws_secret_list)"
  secret_names_array "${BWS_OPENBAO_UNSEAL_SECRET_NAMES}" secret_names_array_values

  keys_provided=0
  for secret_name in "${secret_names_array_values[@]}"; do
    [[ -n "${secret_name}" ]] || continue

    if ! openbao_is_sealed; then
      log "OpenBao is unsealed. Stopping before reading more keys."
      break
    fi

    key="$(extract_secret_value "${secrets_json}" "${secret_name}")"
    [[ -n "${key}" ]] || fail "BWS secret is empty: ${secret_name}"

    keys_provided=$((keys_provided + 1))
    log "Submitting unseal key ${keys_provided}/${OPENBAO_UNSEAL_THRESHOLD} from BWS secret '${secret_name}'..."
    unseal_with_key "${key}"

    unset key
  done

  unset secrets_json

  if openbao_is_sealed; then
    fail "OpenBao is still sealed after ${keys_provided} submitted key(s). Check threshold and BWS secret names."
  fi

  log "OK: OpenBao is unsealed."
  force_refresh_external_secrets
}

main "$@"
