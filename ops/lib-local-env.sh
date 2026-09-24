# shellcheck shell=bash
# Shared helper for ops/ scripts. Source it after setting OPS_DIR.
#
# Operator-specific settings (Bitwarden account, vault item names, LAN
# addresses) live in ops/local.env, which is gitignored. Copy
# ops/local.env.example to ops/local.env and fill it in. OPS_LOCAL_ENV points
# at a different file.
#
# The file is parsed, not executed: only KEY=VALUE lines, an optional leading
# `export`, and optional single or double quotes around the whole value.
# Variables already set in the environment take precedence over the file.
# Values are set as shell variables and are not exported.

ops_local_env_file() {
  printf '%s' "${OPS_LOCAL_ENV:-${OPS_DIR:?OPS_DIR must be set before sourcing lib-local-env.sh}/local.env}"
}

ops_load_local_env() {
  local file line name value lineno=0
  local kv_re='^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$'
  local skip_re='^[[:space:]]*(#.*)?$'
  local dq_re='^"(.*)"[[:space:]]*$'
  local sq_re="^'(.*)'[[:space:]]*$"

  file="$(ops_local_env_file)"
  [[ -f "${file}" ]] || return 0

  while IFS= read -r line || [[ -n "${line}" ]]; do
    lineno=$((lineno + 1))
    [[ "${line}" =~ ${skip_re} ]] && continue
    if [[ ! "${line}" =~ ${kv_re} ]]; then
      printf 'ERROR: %s line %d is not KEY=VALUE\n' "${file}" "${lineno}" >&2
      exit 1
    fi
    name="${BASH_REMATCH[2]}"
    value="${BASH_REMATCH[3]}"
    if [[ "${value}" =~ ${dq_re} || "${value}" =~ ${sq_re} ]]; then
      value="${BASH_REMATCH[1]}"
    fi
    [[ -n "${!name+x}" ]] || printf -v "${name}" '%s' "${value}"
  done < "${file}"
}

# Exits with a clear message when any named setting is empty or unset.
ops_require_env() {
  local name
  local -a missing=()
  for name in "$@"; do
    [[ -n "${!name:-}" ]] || missing+=("${name}")
  done
  if (( ${#missing[@]} > 0 )); then
    printf 'ERROR: missing required setting(s): %s\n' "${missing[*]}" >&2
    printf 'Set them in %s (template: ops/local.env.example) or in the environment.\n' "$(ops_local_env_file)" >&2
    exit 1
  fi
}
