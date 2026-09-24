#!/usr/bin/env bash
set -euo pipefail

# Seeds the repo secrets that .woodpecker/release.yml reads with from_secret.
# Every secret is limited to the manual event, which is how releases start.
#
# Values come from the in-cluster seed Secrets/ConfigMap in the woodpecker
# namespace, plus HARBOR_IP from ops/local.env. Each value is written to a
# private temp file and passed as `--value @file` (woodpecker-cli reads the
# file itself), so no secret value appears in any process's argv.
#
# No --image filter is set. In Woodpecker v3 an image filter turns a secret
# into a plugin-only secret: steps with `commands:` (all release.yml steps) are
# refused with "secret ... is only allowed to be used by plugins". The server
# also rejects digest-pinned references (name@sha256:...) in the image list.

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ops/lib-local-env.sh
source "${OPS_DIR}/lib-local-env.sh"
ops_load_local_env

readonly REPOSITORY=${WOODPECKER_RELEASE_REPOSITORY:-fbialogrecki/threshold}
readonly NAMESPACE=${WOODPECKER_RELEASE_SEED_NAMESPACE:-woodpecker}
# Promotion opens its digest PR against infra/ in the monorepo itself.
readonly GITOPS_REPO_SLUG=${RELEASE_GITOPS_REPO_SLUG:-fbialogrecki/threshold}
readonly GITOPS_REPO_URL=${RELEASE_GITOPS_REPO_URL:-https://github.com/fbialogrecki/threshold.git}
HARBOR_IP="${HARBOR_IP:-}"

ops_require_env HARBOR_IP
command -v woodpecker-cli >/dev/null 2>&1 || { echo "ERROR: woodpecker-cli is required" >&2; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "ERROR: kubectl is required" >&2; exit 1; }

umask 077
VALUE_FILE="$(mktemp)"
chmod 600 "$VALUE_FILE"
trap 'rm -f -- "$VALUE_FILE"' EXIT

secret_value() {
  kubectl -n "$NAMESPACE" get secret "$1" -o "jsonpath={.data.$2}" | base64 --decode
}

config_value() {
  kubectl -n "$NAMESPACE" get configmap woodpecker-release-config -o "jsonpath={.data.$1}"
}

literal() {
  printf '%s' "$1"
}

# set_secret NAME COMMAND [ARGS...]: runs COMMAND to produce the value, writes
# it to the temp file and upserts it. Like the command substitution it
# replaces, trailing newlines are dropped.
set_secret() {
  local name=$1 value
  shift
  value="$("$@")"
  if [[ -z "$value" ]]; then
    echo "ERROR: empty value for $name (source: $*)" >&2
    exit 1
  fi
  printf '%s' "$value" > "$VALUE_FILE"
  unset value

  local -a args=(--repository "$REPOSITORY" --name "$name" --value "@${VALUE_FILE}" --event manual)
  if ! woodpecker-cli repo secret update "${args[@]}" >/dev/null 2>&1; then
    woodpecker-cli repo secret add "${args[@]}" >/dev/null
  fi
  : > "$VALUE_FILE"
}

# Used by the build-images step (quay.io/buildah/stable).
set_secret release_harbor_username secret_value woodpecker-harbor-ci HARBOR_USERNAME
set_secret release_harbor_password secret_value woodpecker-harbor-ci HARBOR_PASSWORD
set_secret release_registry config_value REGISTRY
set_secret release_image_namespace config_value IMAGE_NAMESPACE
set_secret release_harbor_ip literal "$HARBOR_IP"
set_secret release_harbor_ca_sha256 config_value HARBOR_CA_SHA256

# Used by the promote-gitops step (python:3.13-alpine).
set_secret release_git_username secret_value woodpecker-github-writer GIT_USERNAME
set_secret release_git_token secret_value woodpecker-github-writer GIT_TOKEN
set_secret release_image_registry config_value IMAGE_REGISTRY
set_secret release_gitops_repo_slug literal "$GITOPS_REPO_SLUG"
set_secret release_gitops_repo_url literal "$GITOPS_REPO_URL"

printf 'Configured manual-event-only release secrets for %s\n' "$REPOSITORY"
