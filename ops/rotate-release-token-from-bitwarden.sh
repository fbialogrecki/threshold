#!/usr/bin/env bash
set -Eeuo pipefail
shopt -s inherit_errexit 2>/dev/null || true

# Rotates the release credential that promotes image digests into this
# monorepo (the release pipeline opens a PR against infra/), without printing
# or persisting its value. The GitHub PAT lives in personal Bitwarden, while
# BWS provides OpenBao bootstrap access. Operator-specific settings come from
# ops/local.env (see ops/local.env.example).

if [[ -z "${KUBECONFIG:-}" && -f "${HOME}/.kube/config" ]]; then
  export KUBECONFIG="${HOME}/.kube/config"
fi

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ops/lib-local-env.sh
source "${OPS_DIR}/lib-local-env.sh"
ops_load_local_env

BW_ACCOUNT_EMAIL="${BW_ACCOUNT_EMAIL:-}"
BW_SERVER_URL="${BW_SERVER_URL:-}"
BW_BWS_ACCESS_TOKEN_ITEM="${BW_BWS_ACCESS_TOKEN_ITEM:-}"
BW_BWS_ACCESS_TOKEN_FIELD="${BW_BWS_ACCESS_TOKEN_FIELD:-BWS_ACCESS_TOKEN}"
BW_GITHUB_TOKEN_ITEM="${BW_GITHUB_TOKEN_ITEM:-}"
BW_GITHUB_TOKEN_FIELD="${BW_GITHUB_TOKEN_FIELD:-GIT_TOKEN}"
BW_SYNC_BEFORE_READ="${BW_SYNC_BEFORE_READ:-true}"
BW_LOCK_AFTER_RUN="${BW_LOCK_AFTER_RUN:-true}"

BWS_BIN="${BWS_BIN:-bws}"
BWS_SERVER_URL="${BWS_SERVER_URL:-}"
BWS_PROJECT_ID="${BWS_PROJECT_ID:-}"
BWS_OPENBAO_TOKEN_SECRET_NAMES="${BWS_OPENBAO_TOKEN_SECRET_NAMES:-}"

OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
OPENBAO_MOUNT="${OPENBAO_MOUNT:-secret}"
OPENBAO_REMOTE_PATH="${OPENBAO_REMOTE_PATH:-threshold/ci/github-writer}"
OPENBAO_GIT_USERNAME="${OPENBAO_GIT_USERNAME:-}"
UNSEAL_SCRIPT="${UNSEAL_SCRIPT:-${OPS_DIR}/openbao-manual-unseal-from-bitwarden.sh}"

ESO_NAMESPACE="${ESO_NAMESPACE:-woodpecker}"
ESO_EXTERNAL_SECRET="${ESO_EXTERNAL_SECRET:-woodpecker-github-writer}"
ESO_K8S_SECRET="${ESO_K8S_SECRET:-woodpecker-github-writer}"
ESO_CLUSTER_SECRET_STORE_NAME="${ESO_CLUSTER_SECRET_STORE_NAME:-openbao}"

# The monorepo the release pipeline promotes into; the PAT needs push access here.
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-fbialogrecki/threshold}"
GITHUB_API_URL="${GITHUB_API_URL:-https://api.github.com}"

BW_SESSION="${BW_SESSION:-}"
BW_SESSION_CREATED_BY_SCRIPT="false"
BW_MASTER_PASSWORD_SET_BY_SCRIPT="false"
BWS_ACCESS_TOKEN_SET_BY_SCRIPT="false"
BAO_TOKEN_SET_BY_SCRIPT="false"
GITHUB_TOKEN=""
GITHUB_TOKEN_NEEDS_STORAGE="false"
TOKEN_FILE=""
USERNAME_FILE=""
BAO_TOKEN_FILE=""
LOCAL_RUN_DIR=""
REMOTE_RUN_DIR=""
REMOTE_OWNER=""
ROTATION_LOCK_FD=""

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
  log "ERROR: command failed at line ${line_no} with exit code ${exit_code}"
  exit "${exit_code}"
}

cleanup_remote() {
  [[ -n "${REMOTE_RUN_DIR}" ]] || return 0
  kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- \
    "${REMOTE_RUN_DIR}" "${REMOTE_OWNER}" <<'EOF_CLEANUP'
set -eu
dir="$1"
owner="$2"
[ -e "$dir" ] || [ -L "$dir" ] || exit 0
[ -d "$dir" ] && [ ! -L "$dir" ]
[ "$(stat -c %u "$dir")" = "$(id -u)" ]
[ "$(stat -c %a "$dir")" = 700 ]
[ -f "$dir/.owner" ] && [ ! -L "$dir/.owner" ]
[ "$(cat "$dir/.owner")" = "$owner" ]
rm -f -- "$dir/token" "$dir/username" "$dir/bao-token"
rm -f -- "$dir/.owner"
rmdir -- "$dir"
EOF_CLEANUP
}

cleanup() {
  local status=$? cleanup_failed=0
  trap - EXIT ERR HUP INT TERM
  cleanup_remote >/dev/null 2>&1 || cleanup_failed=1
  [[ -z "${TOKEN_FILE}" ]] || rm -f -- "${TOKEN_FILE}" || cleanup_failed=1
  [[ -z "${USERNAME_FILE}" ]] || rm -f -- "${USERNAME_FILE}" || cleanup_failed=1
  [[ -z "${BAO_TOKEN_FILE}" ]] || rm -f -- "${BAO_TOKEN_FILE}" || cleanup_failed=1
  [[ -z "${LOCAL_RUN_DIR}" ]] || rmdir -- "${LOCAL_RUN_DIR}" || cleanup_failed=1

  if [[ "${BW_SESSION_CREATED_BY_SCRIPT}" == "true" && "${BW_LOCK_AFTER_RUN}" == "true" && -n "${BW_SESSION}" ]]; then
    bw --session "${BW_SESSION}" --quiet lock >/dev/null 2>&1 || true
  fi
  unset GITHUB_TOKEN BW_SESSION
  [[ "${BWS_ACCESS_TOKEN_SET_BY_SCRIPT}" != "true" ]] || unset BWS_ACCESS_TOKEN
  [[ "${BAO_TOKEN_SET_BY_SCRIPT}" != "true" ]] || unset BAO_TOKEN
  [[ "${BW_MASTER_PASSWORD_SET_BY_SCRIPT}" != "true" ]] || unset BW_MASTER_PASSWORD
  if [[ "$cleanup_failed" == 1 ]]; then
    log "ERROR: credential cleanup incomplete; operator remediation required."
    status=1
  fi
  exit "$status"
}
trap cleanup EXIT
trap on_error ERR
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

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
  { : < /dev/tty; } 2>/dev/null || fail "Bitwarden login/unlock needs an interactive TTY"
  printf 'Bitwarden master password for %s (input hidden): ' "${BW_ACCOUNT_EMAIL}" > /dev/tty
  IFS= read -rs BW_MASTER_PASSWORD < /dev/tty
  printf '\n' > /dev/tty
  export BW_MASTER_PASSWORD
  BW_MASTER_PASSWORD_SET_BY_SCRIPT="true"
}

clear_bw_master_password() {
  [[ "${BW_MASTER_PASSWORD_SET_BY_SCRIPT}" != "true" ]] || unset BW_MASTER_PASSWORD
  BW_MASTER_PASSWORD_SET_BY_SCRIPT="false"
}

ensure_bw_session() {
  local status_json status user_email

  log "Configuring Bitwarden CLI server: ${BW_SERVER_URL}..."
  if ! bw --quiet config server "${BW_SERVER_URL}" >/dev/null 2>&1; then
    log "Bitwarden CLI refused server switch. Logging out and retrying..."
    bw --quiet logout >/dev/null 2>&1 || true
    bw --quiet config server "${BW_SERVER_URL}" >/dev/null \
      || fail "failed to configure Bitwarden CLI server"
  fi

  status_json="$(bw_status_json)"
  status="$(jq -r '.status // "unknown"' <<<"${status_json}")"
  user_email="$(jq -r '.userEmail // empty' <<<"${status_json}")"

  if [[ "${status}" != "unauthenticated" && -n "${user_email}" && "${user_email}" != "${BW_ACCOUNT_EMAIL}" ]]; then
    log "Bitwarden CLI is logged into ${user_email}; switching to ${BW_ACCOUNT_EMAIL}..."
    bw --quiet logout >/dev/null 2>&1 || true
    status="unauthenticated"
  fi

  case "${status}" in
    unlocked)
      log "Bitwarden CLI is already unlocked."
      ;;
    locked)
      read_bw_master_password
      BW_SESSION="$(bw unlock --passwordenv BW_MASTER_PASSWORD --raw)"
      clear_bw_master_password
      BW_SESSION_CREATED_BY_SCRIPT="true"
      ;;
    unauthenticated)
      read_bw_master_password
      BW_SESSION="$(bw login "${BW_ACCOUNT_EMAIL}" --passwordenv BW_MASTER_PASSWORD --raw)"
      clear_bw_master_password
      BW_SESSION_CREATED_BY_SCRIPT="true"
      ;;
    *)
      fail "unexpected Bitwarden status: ${status}"
      ;;
  esac
  [[ "${status}" == unlocked || -n "${BW_SESSION}" ]] || fail "Bitwarden did not return a session"

  if [[ "${BW_SYNC_BEFORE_READ}" == "true" ]]; then
    log "Syncing Bitwarden personal vault..."
    bw_vault_cmd sync --quiet >/dev/null
  fi
}

extract_bw_item_value() {
  local item_json="$1" field="$2"
  jq -er --arg field "${field}" '
    [
      ((.fields // [])[]? | select(.name == $field) | .value),
      (.login.password?),
      (.notes?)
    ]
    | map(select(type == "string" and length > 0))
    | .[0] // empty
  ' <<<"${item_json}"
}

read_personal_vault_secrets() {
  local item_json

  ensure_bw_session

  log "Reading BWS access token from Bitwarden item '${BW_BWS_ACCESS_TOKEN_ITEM}'..."
  item_json="$(bw_vault_cmd get item "${BW_BWS_ACCESS_TOKEN_ITEM}")"
  BWS_ACCESS_TOKEN="$(extract_bw_item_value "${item_json}" "${BW_BWS_ACCESS_TOKEN_FIELD}")"
  [[ -n "${BWS_ACCESS_TOKEN}" ]] || fail "BWS access token is empty"
  export BWS_ACCESS_TOKEN
  BWS_ACCESS_TOKEN_SET_BY_SCRIPT="true"
  unset item_json

  log "Reading GitHub PAT from Bitwarden item '${BW_GITHUB_TOKEN_ITEM}'..."
  if ! item_json="$(bw_vault_cmd get item "${BW_GITHUB_TOKEN_ITEM}" 2>/dev/null)"; then
    log "Bitwarden item '${BW_GITHUB_TOKEN_ITEM}' does not exist."
    { : < /dev/tty; } 2>/dev/null || fail "GitHub token input needs an interactive TTY"
    printf 'Fine-grained GitHub PAT for %s (input hidden): ' "${GITHUB_REPOSITORY}" > /dev/tty
    IFS= read -rs GITHUB_TOKEN < /dev/tty
    printf '\n' > /dev/tty
    [[ -n "${GITHUB_TOKEN}" ]] || fail "GitHub PAT must not be empty"
    GITHUB_TOKEN_NEEDS_STORAGE="true"
    return
  fi
  GITHUB_TOKEN="$(extract_bw_item_value "${item_json}" "${BW_GITHUB_TOKEN_FIELD}")"
  [[ -n "${GITHUB_TOKEN}" ]] || fail "Bitwarden item '${BW_GITHUB_TOKEN_ITEM}' has no '${BW_GITHUB_TOKEN_FIELD}' value"
  unset item_json
}

build_github_token_item() {
  local template="$1"
  jq -c \
    --arg name "${BW_GITHUB_TOKEN_ITEM}" \
    --arg username "${OPENBAO_GIT_USERNAME}" \
    --arg token "${GITHUB_TOKEN}" '
      .name = $name
      | .type = 1
      | .login.username = $username
      | .login.password = $token
      | .notes = "Repository-scoped fine-grained PAT for release promotion into the monorepo."
    ' <<<"${template}"
}

store_github_token_in_bw_if_needed() {
  local template item_json encoded
  [[ "${GITHUB_TOKEN_NEEDS_STORAGE}" == "true" ]] || return 0

  log "Saving the validated PAT as login password in Bitwarden item '${BW_GITHUB_TOKEN_ITEM}'..."
  template="$(bw_vault_cmd get template item)"
  item_json="$(build_github_token_item "${template}")"
  encoded="$(printf '%s' "${item_json}" | base64 --wrap=0)"
  bw_vault_cmd create item "${encoded}" >/dev/null
  unset template item_json encoded
  GITHUB_TOKEN_NEEDS_STORAGE="false"
  log "OK: Bitwarden item created. Token value was not printed."
}

bws_secret_list() {
  if [[ -n "${BWS_PROJECT_ID}" ]]; then
    "${BWS_BIN}" --server-url "${BWS_SERVER_URL}" -o json secret list "${BWS_PROJECT_ID}"
  else
    "${BWS_BIN}" --server-url "${BWS_SERVER_URL}" -o json secret list
  fi
}

extract_bws_secret() {
  local secrets_json="$1" secret_name="$2"
  jq -er --arg name "${secret_name}" '
    def items:
      if type == "array" then .
      elif type == "object" and (.secrets | type == "array") then .secrets
      elif type == "object" and (.data | type == "array") then .data
      else [] end;
    [items[]? | select((.key // .name // "") == $name) | .value]
    | map(select(type == "string" and length > 0))
    | .[0] // empty
  ' <<<"${secrets_json}"
}

read_bao_token_from_bws() {
  local secrets_json secret_name token
  local -a secret_names

  log "Checking BWS access and reading a write-capable OpenBao token..."
  secrets_json="$(bws_secret_list)"
  IFS='|' read -r -a secret_names <<<"${BWS_OPENBAO_TOKEN_SECRET_NAMES}"
  for secret_name in "${secret_names[@]}"; do
    if token="$(extract_bws_secret "${secrets_json}" "${secret_name}" 2>/dev/null)" && [[ -n "${token}" ]]; then
      BAO_TOKEN="${token}"
      export BAO_TOKEN
      BAO_TOKEN_SET_BY_SCRIPT="true"
      unset token secrets_json
      log "OK: OpenBao token found in BWS secret '${secret_name}'. Value not printed."
      return 0
    fi
  done
  fail "no write-capable OpenBao token found in BWS"
}

unseal_openbao_if_needed() {
  log "Ensuring OpenBao is unsealed..."
  OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE}" \
  OPENBAO_POD="${OPENBAO_POD}" \
  BWS_ACCESS_TOKEN="${BWS_ACCESS_TOKEN}" \
  BW_LOCK_AFTER_RUN="false" \
  "${UNSEAL_SCRIPT}"
}

validate_github_token() {
  local response
  log "Validating GitHub token access to ${GITHUB_REPOSITORY}..."
  response="$(curl --fail --silent --show-error \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H 'Accept: application/vnd.github+json' \
    -H 'X-GitHub-Api-Version: 2022-11-28' \
    "${GITHUB_API_URL}/repos/${GITHUB_REPOSITORY}")" \
    || fail "GitHub rejected the token or repository access"

  jq -e --arg repo "${GITHUB_REPOSITORY}" '
    .full_name == $repo and .permissions.push == true
  ' <<<"${response}" >/dev/null \
    || fail "GitHub token does not have write access to ${GITHUB_REPOSITORY}"
  unset response
  log "OK: GitHub reports write access to ${GITHUB_REPOSITORY}."
}

# Single-host, same-user advisory lock (NOT a distributed cluster lock).
# Retain the non-secret lock inode; unlinking it would permit concurrent locks.
acquire_rotation_lock() {
  [[ -z "${ROTATION_LOCK_FD:-}" ]] || return 0
  require_tool flock
  local lock_dir="${HOME}/.threshold-rotation-locks" key lock_file
  umask 077
  if [[ ! -e "$lock_dir" && ! -L "$lock_dir" ]]; then
    mkdir -m 700 -- "$lock_dir" || fail "cannot create rotation lock directory"
  fi
  [[ -d "$lock_dir" && ! -L "$lock_dir" && -O "$lock_dir" ]] \
    && [[ "$(stat -c %a "$lock_dir")" == 700 ]] || fail "unsafe rotation lock directory"
  key="$(printf '%s/%s' "$OPENBAO_NAMESPACE" "$OPENBAO_POD" | sha256sum | cut -d' ' -f1)"
  lock_file="$lock_dir/$key.lock"
  [[ ! -L "$lock_file" ]] || fail "unsafe rotation lock file"
  [[ ! -e "$lock_file" || ( -f "$lock_file" && -O "$lock_file" ) ]] || fail "unsafe rotation lock file"
  exec {ROTATION_LOCK_FD}>>"$lock_file"
  flock -n "$ROTATION_LOCK_FD" || fail "rotation already running for this target on this host"
}

seed_openbao() {
  acquire_rotation_lock
  umask 077
  LOCAL_RUN_DIR="$(mktemp -d)"
  TOKEN_FILE="${LOCAL_RUN_DIR}/token"
  USERNAME_FILE="${LOCAL_RUN_DIR}/username"
  BAO_TOKEN_FILE="${LOCAL_RUN_DIR}/bao-token"
  printf '%s' "${GITHUB_TOKEN}" > "${TOKEN_FILE}"
  printf '%s' "${OPENBAO_GIT_USERNAME}" > "${USERNAME_FILE}"
  printf '%s' "${BAO_TOKEN}" > "${BAO_TOKEN_FILE}"

  # Register the candidate before any remote write; cleanup requires ownership.
  REMOTE_OWNER="${LOCAL_RUN_DIR##*/}"
  REMOTE_RUN_DIR="/tmp/rotate-release-token.${REMOTE_OWNER}"
  kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- \
    "${REMOTE_RUN_DIR}" "${REMOTE_OWNER}" <<'EOF_CREATE'
set -eu
umask 077
mkdir -m 700 -- "$1"
printf '%s' "$2" > "$1/.owner"
EOF_CREATE
  log "Writing ${OPENBAO_MOUNT}/${OPENBAO_REMOTE_PATH} in OpenBao..."
  kubectl cp "${TOKEN_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:${REMOTE_RUN_DIR}/token" >/dev/null
  kubectl cp "${USERNAME_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:${REMOTE_RUN_DIR}/username" >/dev/null
  kubectl cp "${BAO_TOKEN_FILE}" "${OPENBAO_NAMESPACE}/${OPENBAO_POD}:${REMOTE_RUN_DIR}/bao-token" >/dev/null

  kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh -s -- \
    "${OPENBAO_MOUNT}" "${OPENBAO_REMOTE_PATH}" "${REMOTE_RUN_DIR}" <<'EOF_INNER'
set -eu
mount="$1"
path="$2"
dir="$3"
export BAO_ADDR=http://127.0.0.1:8200
export BAO_TOKEN="$(cat "$dir/bao-token")"
bao kv put "${mount}/${path}" \
  GIT_USERNAME=@"$dir/username" \
  GIT_TOKEN=@"$dir/token" >/dev/null
bao kv get -field=GIT_USERNAME "${mount}/${path}" >/dev/null
bao kv get -field=GIT_TOKEN "${mount}/${path}" >/dev/null
EOF_INNER
  cleanup_remote || fail "credential cleanup incomplete; operator remediation required"
  REMOTE_RUN_DIR=""
  log "OK: OpenBao value written and read back without printing it."
}

refresh_and_verify_eso() {
  local stamp ready local_hash cluster_hash username
  stamp="$(date +%s)"
  log "Forcing ESO refresh for ${ESO_NAMESPACE}/${ESO_EXTERNAL_SECRET}..."
  kubectl annotate clustersecretstore "${ESO_CLUSTER_SECRET_STORE_NAME}" force-sync="${stamp}" --overwrite >/dev/null
  kubectl annotate externalsecret -n "${ESO_NAMESPACE}" "${ESO_EXTERNAL_SECRET}" force-sync="${stamp}" --overwrite >/dev/null

  local_hash="$(printf '%s' "${GITHUB_TOKEN}" | sha256sum | cut -d' ' -f1)"
  cluster_hash=""
  for _ in $(seq 1 60); do
    ready="$(kubectl get externalsecret -n "${ESO_NAMESPACE}" "${ESO_EXTERNAL_SECRET}" \
      -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
    if kubectl get secret -n "${ESO_NAMESPACE}" "${ESO_K8S_SECRET}" >/dev/null 2>&1; then
      cluster_hash="$(kubectl get secret -n "${ESO_NAMESPACE}" "${ESO_K8S_SECRET}" \
        -o jsonpath='{.data.GIT_TOKEN}' | base64 --decode | sha256sum | cut -d' ' -f1)"
    fi
    [[ "${ready}" == True && "${local_hash}" == "${cluster_hash}" ]] && break
    sleep 2
  done
  [[ "${ready:-}" == True ]] || fail "ExternalSecret/${ESO_EXTERNAL_SECRET} did not become Ready=True"
  [[ "${local_hash}" == "${cluster_hash}" ]] || fail "ESO secret value did not converge to the Bitwarden token"

  username="$(kubectl get secret -n "${ESO_NAMESPACE}" "${ESO_K8S_SECRET}" \
    -o jsonpath='{.data.GIT_USERNAME}' | base64 --decode)"

  [[ "${username}" == "${OPENBAO_GIT_USERNAME}" ]] || fail "ESO Git username does not match"
  unset local_hash cluster_hash username
  log "OK: ESO is Ready and the propagated secret matches Bitwarden. Hashes and values were not printed."
}

self_test() {
  local bw_fixture bws_fixture item_template item
  # Synthetic values only; the self-test needs no ops/local.env.
  local BW_GITHUB_TOKEN_ITEM='Synthetic Release Token' OPENBAO_GIT_USERNAME=synthetic-user
  bw_fixture='{"fields":[{"name":"GIT_TOKEN","value":"github-token"}],"login":{"password":"fallback"}}'
  bws_fixture='[{"key":"OpenBao Admin Token","value":"bao-token"}]'
  [[ "$(extract_bw_item_value "${bw_fixture}" GIT_TOKEN)" == github-token ]]
  [[ "$(extract_bws_secret "${bws_fixture}" 'OpenBao Admin Token')" == bao-token ]]
  item_template='{"type":1,"name":"","notes":null,"login":{"username":null,"password":null}}'
  GITHUB_TOKEN=github-token
  item="$(build_github_token_item "${item_template}")"
  jq -e '
    .type == 1
    and .name == "Synthetic Release Token"
    and .login.username == "synthetic-user"
    and .login.password == "github-token"
  ' <<<"${item}" >/dev/null
  unset GITHUB_TOKEN item
  log "self-test passed"
}

main() {
  if [[ "${1:-}" == --self-test ]]; then
    [[ $# -eq 1 ]] || fail "--self-test takes no additional arguments"
    require_tool jq
    self_test
    return
  fi
  [[ $# -eq 0 ]] || fail "usage: $0 [--self-test]"

  require_tool bw
  require_tool "${BWS_BIN}"
  require_tool jq
  require_tool curl
  require_tool kubectl
  require_tool sha256sum
  require_tool base64
  require_tool cut
  require_tool date
  ops_require_env BW_ACCOUNT_EMAIL BW_SERVER_URL BW_BWS_ACCESS_TOKEN_ITEM BW_GITHUB_TOKEN_ITEM \
    BWS_SERVER_URL BWS_OPENBAO_TOKEN_SECRET_NAMES OPENBAO_GIT_USERNAME
  [[ -x "${UNSEAL_SCRIPT}" ]] || fail "missing unseal helper: ${UNSEAL_SCRIPT}"

  acquire_rotation_lock
  read_personal_vault_secrets
  validate_github_token
  store_github_token_in_bw_if_needed
  unseal_openbao_if_needed
  read_bao_token_from_bws
  seed_openbao
  refresh_and_verify_eso
  log "OK: release token rotation completed. No secret values were printed or retained on disk."
}

main "$@"
