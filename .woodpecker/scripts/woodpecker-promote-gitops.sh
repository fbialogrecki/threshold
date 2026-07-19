#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_PATH=$(realpath "$0")
readonly SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
readonly BUMP_HELPER="$SCRIPT_DIR/bump-service-gitops.py"
readonly BACKENDS=(auth-gateway events media social users)
readonly APPLICATIONS=(auth-gateway events media social users web)
readonly GIT_BIN=${WOODPECKER_GIT_BIN:-git}
readonly CURL_BIN=${WOODPECKER_CURL_BIN:-curl}
readonly KUBE_TOKEN_FILE=${WOODPECKER_KUBE_TOKEN_FILE:-/var/run/secrets/kubernetes.io/serviceaccount/token}
readonly KUBE_CA=${WOODPECKER_KUBE_CA:-/var/run/secrets/kubernetes.io/serviceaccount/ca.crt}
readonly RELEASE_CONFIG_NAME=${WOODPECKER_RELEASE_CONFIG_NAME:-woodpecker-release-config}
readonly IMAGE_DIGEST_DIR=${WOODPECKER_IMAGE_DIGEST_DIR:-.woodpecker-digests}

die() {
  echo "$*" >&2
  exit 1
}

usage() {
  echo "usage: $0 [--dry-run] [--changed-files <file>] [--self-test]" >&2
  exit 2
}

select_backends() {
  local app
  for app in "${BACKENDS[@]}"; do
    selected["$app"]=1
  done
}

select_all() {
  local app
  for app in "${APPLICATIONS[@]}"; do
    selected["$app"]=1
  done
}

map_path() {
  local path=$1 app

  case "$path" in
    services/auth-gateway/*) selected[auth-gateway]=1 ;;
    services/events/*) selected[events]=1 ;;
    services/media/*) selected[media]=1 ;;
    services/social/*) selected[social]=1 ;;
    services/users/*) selected[users]=1 ;;
    apps/web/*) selected[web]=1 ;;
    libs/py/*|pyproject.toml|uv.lock|.python-version|.woodpecker/python-quality.yml)
      select_backends
      ;;
    .woodpecker/scripts/woodpecker-build-push.sh|.woodpecker/scripts/woodpecker-promote-gitops.sh|.woodpecker/scripts/bump-service-gitops.py|.woodpecker/release.yml)
      select_all
      ;;
    .woodpecker/auth-gateway.yml|.woodpecker/events.yml|.woodpecker/media.yml|.woodpecker/social.yml|.woodpecker/users.yml|.woodpecker/web.yml)
      app=${path##*/}
      selected["${app%.yml}"]=1
      ;;
  esac
}

print_selected() {
  local app
  for app in "${APPLICATIONS[@]}"; do
    [[ -v "selected[$app]" ]] && printf '%s\n' "$app"
  done
  return 0
}

assert_output() {
  local name=$1 fixture=$2 expected=$3 output
  output=$(CI_PIPELINE_EVENT=push \
    CI_PREV_COMMIT_SHA=1111111111111111111111111111111111111111 \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" --dry-run --changed-files "$fixture")
  [[ "$output" == "$expected" ]] || die "self-test failed: $name"
}

self_test() {
  local tmp output
  export GITOPS_REPO_SLUG=test/threshold-gitops
  export GITOPS_REPO_URL=https://github.com/test/threshold-gitops.git
  export IMAGE_REGISTRY=registry.example.test/threshold
  tmp=$(mktemp -d)
  trap "rm -rf -- '$tmp'" EXIT

  printf 'services/users/src/users/main.py\n' > "$tmp/users"
  assert_output users-only "$tmp/users" users
  output=$(WOODPECKER_GIT_BIN=/bin/false WOODPECKER_CURL_BIN=/bin/false \
    CI_PIPELINE_EVENT=push \
    CI_PREV_COMMIT_SHA=1111111111111111111111111111111111111111 \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" --dry-run --changed-files "$tmp/users")
  [[ "$output" == users ]] || die "self-test failed: dry-run attempted external commands"

  printf 'apps/web/src/app/page.tsx\n' > "$tmp/web"
  assert_output web-only "$tmp/web" web

  printf 'libs/py/threshold_common/nats.py\n' > "$tmp/libs-py"
  assert_output libs-py "$tmp/libs-py" $'auth-gateway\nevents\nmedia\nsocial\nusers'

  printf '.woodpecker/scripts/woodpecker-build-push.sh\n' > "$tmp/build-helper"
  assert_output build-helper "$tmp/build-helper" $'auth-gateway\nevents\nmedia\nsocial\nusers\nweb'

  printf '.woodpecker/users.yml\n' > "$tmp/workflow"
  assert_output workflow-control "$tmp/workflow" users

  printf '.woodpecker/python-quality.yml\n' > "$tmp/python-quality"
  assert_output python-quality "$tmp/python-quality" $'auth-gateway\nevents\nmedia\nsocial\nusers'

  for fixture in .woodpecker/scripts/woodpecker-promote-gitops.sh .woodpecker/scripts/bump-service-gitops.py .woodpecker/release.yml; do
    printf '%s\n' "$fixture" > "$tmp/all-control"
    assert_output "$fixture" "$tmp/all-control" $'auth-gateway\nevents\nmedia\nsocial\nusers\nweb'
  done

  printf '.woodpecker/services.yml\n' > "$tmp/legacy-workflow"
  assert_output legacy-workflow-removed "$tmp/legacy-workflow" ""

  output=$(CI_PIPELINE_EVENT=manual "$SCRIPT_PATH" --dry-run)
  [[ "$output" == $'auth-gateway\nevents\nmedia\nsocial\nusers\nweb' ]] ||
    die "self-test failed: manual-all"

  if CI_PIPELINE_EVENT=push CI_PREV_COMMIT_SHA=invalid \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" --dry-run --changed-files "$tmp/users" >/dev/null 2>&1; then
    die "self-test failed: invalid SHA was accepted"
  fi

  if CI_PIPELINE_EVENT=push \
    CI_PREV_COMMIT_SHA=1111111111111111111111111111111111111111 \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" --dry-run >/dev/null 2>&1; then
    die "self-test failed: unavailable diff was accepted"
  fi

  mkdir "$tmp/home" "$tmp/digests"
  for app in "${APPLICATIONS[@]}"; do
    printf '%s\n' 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' > "$tmp/digests/$app.digest"
  done
  printf 'service-account-token\n' > "$tmp/token"
  : > "$tmp/ca"
  cat > "$tmp/curl" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *"api.github.com"* ]]; then
  if [[ "$*" == *"-X POST"* ]]; then
    echo pr-create >> "$WOODPECKER_TEST_LOG"
    printf '%s\n' '{}'
  else
    echo pr-list >> "$WOODPECKER_TEST_LOG"
    printf '%s\n' '[]'
  fi
  exit 0
fi
echo auth >> "$WOODPECKER_TEST_LOG"
printf '%s\n' '{"data":{"GIT_USERNAME":"dQ==","GIT_TOKEN":"dA=="}}'
EOF
  cat > "$tmp/git" <<'EOF'
#!/usr/bin/env bash
case "${1:-}:${2:-}:${3:-}" in
  fetch:*)
    printf 'fetch:%s\n' "${!#}" >> "$WOODPECKER_TEST_LOG"
    ;;
  show:*)
    echo show >> "$WOODPECKER_TEST_LOG"
    cat <<'PY'
import os
import sys
from pathlib import Path

with Path(os.environ["WOODPECKER_TEST_LOG"]).open("a") as log:
    service = sys.argv[sys.argv.index("--service") + 1]
    tag = sys.argv[sys.argv.index("--tag") + 1]
    log.write(f"invoke:{__file__}:{service}:{tag}\n")
PY
    ;;
  clone:*)
    destination=${!#}
    mkdir -p "$destination/infra/kustomize/overlays/local/users"
    cat > "$destination/infra/kustomize/overlays/local/users/kustomization.yaml" <<'YAML'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
images:
  - name: threshold/users
    newName: core.harbor.domain/threshold/users
    newTag: old
YAML
    echo clone >> "$WOODPECKER_TEST_LOG"
    ;;
  config:*) echo config >> "$WOODPECKER_TEST_LOG" ;;
  diff:--cached:--quiet)
    echo staged-diff >> "$WOODPECKER_TEST_LOG"
    exit 1
    ;;
  diff:--name-only:HEAD)
    echo worktree-diff >> "$WOODPECKER_TEST_LOG"
    printf 'infra/kustomize/overlays/local/users/kustomization.yaml\n'
    ;;
  diff:*)
    echo diff >> "$WOODPECKER_TEST_LOG"
    [[ "${WOODPECKER_TEST_FAIL_DIFF:-0}" == 0 ]] || exit 1
    if [[ "${WOODPECKER_TEST_FULL_PATH:-0}" == 1 ]]; then
      printf 'services/users/src/users/main.py\n'
    else
      printf 'docs/no-application-change.md\n'
    fi
    ;;
  add:*) echo add >> "$WOODPECKER_TEST_LOG" ;;
  commit:*) echo commit >> "$WOODPECKER_TEST_LOG" ;;
  push:*)
    echo push >> "$WOODPECKER_TEST_LOG"
    count_file="$WOODPECKER_TEST_LOG.pushes"
    count=0
    [[ ! -f "$count_file" ]] || count=$(<"$count_file")
    count=$((count + 1))
    printf '%s\n' "$count" > "$count_file"
    [[ "$count" -gt "${WOODPECKER_TEST_PUSH_FAILURES:-0}" ]]
    ;;
esac
EOF
  chmod +x "$tmp/curl" "$tmp/git"

  : > "$tmp/sequence"
  HOME="$tmp/home" WOODPECKER_CURL_BIN="$tmp/curl" WOODPECKER_GIT_BIN="$tmp/git" \
    WOODPECKER_IMAGE_DIGEST_DIR="$tmp/digests" \
    WOODPECKER_KUBE_TOKEN_FILE="$tmp/token" WOODPECKER_KUBE_CA="$tmp/ca" \
    WOODPECKER_TEST_LOG="$tmp/sequence" CI_PIPELINE_EVENT=push \
    CI_COMMIT_BRANCH=main CI_REPO_DEFAULT_BRANCH=main CI_REPO=test/threshold \
    CI_PREV_COMMIT_SHA=1111111111111111111111111111111111111111 \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" >/dev/null
  [[ "$(<"$tmp/sequence")" == $'auth\nfetch:1111111111111111111111111111111111111111\nfetch:2222222222222222222222222222222222222222\ndiff' ]] ||
    die "self-test failed: credentials were not configured before source fetch/diff"
  [[ ! -e "$tmp/home/.git-credentials" ]] ||
    die "self-test failed: credentials were not cleaned"

  : > "$tmp/sequence"
  if HOME="$tmp/home" WOODPECKER_CURL_BIN="$tmp/curl" WOODPECKER_GIT_BIN="$tmp/git" \
    WOODPECKER_IMAGE_DIGEST_DIR="$tmp/digests" \
    WOODPECKER_KUBE_TOKEN_FILE="$tmp/token" WOODPECKER_KUBE_CA="$tmp/ca" \
    WOODPECKER_TEST_LOG="$tmp/sequence" WOODPECKER_TEST_FAIL_DIFF=1 \
    CI_PIPELINE_EVENT=push CI_COMMIT_BRANCH=main CI_REPO_DEFAULT_BRANCH=main \
    CI_REPO=test/threshold \
    CI_PREV_COMMIT_SHA=1111111111111111111111111111111111111111 \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" >/dev/null 2>&1; then
    die "self-test failed: unavailable production diff was accepted"
  fi
  [[ "$(<"$tmp/sequence")" == $'auth\nfetch:1111111111111111111111111111111111111111\nfetch:2222222222222222222222222222222222222222\ndiff' ]] ||
    die "self-test failed: unavailable diff sequence or cleanup"

  : > "$tmp/sequence"
  rm -f "$tmp/sequence.pushes"
  HOME="$tmp/home" WOODPECKER_CURL_BIN="$tmp/curl" WOODPECKER_GIT_BIN="$tmp/git" \
    WOODPECKER_IMAGE_DIGEST_DIR="$tmp/digests" \
    WOODPECKER_KUBE_TOKEN_FILE="$tmp/token" WOODPECKER_KUBE_CA="$tmp/ca" \
    WOODPECKER_TEST_LOG="$tmp/sequence" WOODPECKER_TEST_FULL_PATH=1 \
    WOODPECKER_TEST_PUSH_FAILURES=1 \
    CI_PIPELINE_EVENT=push CI_COMMIT_BRANCH=main CI_REPO_DEFAULT_BRANCH=main \
    CI_REPO=test/threshold \
    CI_PREV_COMMIT_SHA=1111111111111111111111111111111111111111 \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" >/dev/null

  local full_log
  full_log=$(<"$tmp/sequence")
  [[ "$full_log" == $'auth\nfetch:1111111111111111111111111111111111111111\nfetch:2222222222222222222222222222222222222222\ndiff\nclone\nconfig\nconfig\nworktree-diff\nadd\nstaged-diff\ncommit\npush\nclone\nconfig\nconfig\nworktree-diff\nadd\nstaged-diff\ncommit\npush\npr-list\npr-create' ]] ||
    die "self-test failed: fresh retry did not reapply selected bumps"

  echo "self-test passed"
}

promotion_tmp=
git_credentials_file=

cleanup() {
  [[ -z "$promotion_tmp" ]] || rm -rf -- "$promotion_tmp"
  unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0
  unset GIT_TOKEN GIT_USERNAME SECRET_JSON KUBE_TOKEN
}

configure_credentials() {
  KUBE_TOKEN=$(<"$KUBE_TOKEN_FILE")
  SECRET_JSON=$("$CURL_BIN" --fail --silent --show-error --cacert "$KUBE_CA" \
    -H "Authorization: Bearer $KUBE_TOKEN" \
    https://kubernetes.default.svc/api/v1/namespaces/woodpecker/secrets/woodpecker-github-writer)
  GIT_USERNAME=$(printf '%s' "$SECRET_JSON" | python3 -c \
    'import base64,json,sys; print(base64.b64decode(json.load(sys.stdin)["data"]["GIT_USERNAME"]).decode())')
  GIT_TOKEN=$(printf '%s' "$SECRET_JSON" | python3 -c \
    'import base64,json,sys; print(base64.b64decode(json.load(sys.stdin)["data"]["GIT_TOKEN"]).decode())')

  printf 'https://%s:%s@github.com\n' "$GIT_USERNAME" "$GIT_TOKEN" > "$git_credentials_file"
  chmod 600 "$git_credentials_file"
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0=credential.helper
  export GIT_CONFIG_VALUE_0="store --file=$git_credentials_file"
  unset GIT_USERNAME SECRET_JSON KUBE_TOKEN
}

load_release_config() {
  [[ -n "${GITOPS_REPO_SLUG:-}" && -n "${GITOPS_REPO_URL:-}" && -n "${IMAGE_REGISTRY:-}" ]] && return
  local config_json kube_token
  kube_token=$(<"$KUBE_TOKEN_FILE")
  config_json=$("$CURL_BIN" --fail --silent --show-error --cacert "$KUBE_CA" \
    -H "Authorization: Bearer $kube_token" \
    "https://kubernetes.default.svc/api/v1/namespaces/woodpecker/configmaps/$RELEASE_CONFIG_NAME")
  config_value() {
    printf '%s' "$config_json" | python3 -c \
      'import json,sys; print(json.load(sys.stdin).get("data", {}).get(sys.argv[1], ""))' "$1"
  }
  GITOPS_REPO_SLUG=${GITOPS_REPO_SLUG:-$(config_value GITOPS_REPO_SLUG)}
  GITOPS_REPO_URL=${GITOPS_REPO_URL:-$(config_value GITOPS_REPO_URL)}
  IMAGE_REGISTRY=${IMAGE_REGISTRY:-$(config_value IMAGE_REGISTRY)}
  unset kube_token config_json
}

dry_run=0
changed_files_file=
self_test_requested=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --changed-files)
      [[ $# -ge 2 ]] || usage
      changed_files_file=$2
      shift
      ;;
    --self-test) self_test_requested=1 ;;
    *) usage ;;
  esac
  shift
done

[[ -z "$changed_files_file" || "$dry_run" == 1 ]] ||
  die "--changed-files requires --dry-run"

if [[ "$self_test_requested" == 1 ]]; then
  [[ "$dry_run" == 0 && -z "$changed_files_file" ]] || usage
  self_test
  exit 0
fi

declare -A selected=()
event=${CI_PIPELINE_EVENT:-}

case "$event" in
  manual)
    [[ -z "$changed_files_file" ]] || die "--changed-files is only valid for push events"
    select_all
    ;;
  push)
    [[ "${CI_PREV_COMMIT_SHA:-}" =~ ^[0-9a-fA-F]{40}$ ]] ||
      die "CI_PREV_COMMIT_SHA must be a full 40-character SHA"
    [[ "${CI_COMMIT_SHA:-}" =~ ^[0-9a-fA-F]{40}$ ]] ||
      die "CI_COMMIT_SHA must be a full 40-character SHA"

    if [[ "$dry_run" == 1 ]]; then
      [[ -n "$changed_files_file" && -f "$changed_files_file" ]] ||
        die "Dry-run push requires an available --changed-files fixture"
      while IFS= read -r path; do
        [[ -z "$path" ]] || map_path "$path"
      done < "$changed_files_file"
    fi
    ;;
  *) die "CI_PIPELINE_EVENT must be push or manual" ;;
esac

if [[ "$dry_run" == 1 ]]; then
  print_selected
  exit 0
fi

[[ -n "${CI_COMMIT_SHA:-}" && "$CI_COMMIT_SHA" =~ ^[0-9a-fA-F]{40}$ ]] ||
  die "CI_COMMIT_SHA must be a full 40-character SHA"
[[ "${CI_COMMIT_BRANCH:-}" == "${CI_REPO_DEFAULT_BRANCH:-main}" ]] ||
  die "Promotion is only allowed from the default branch"

trap cleanup EXIT
promotion_tmp=$(mktemp -d)
git_credentials_file="$promotion_tmp/git-credentials"
[[ -f "$BUMP_HELPER" ]] || die "Missing release bump helper: $BUMP_HELPER"
load_release_config
configure_credentials

if [[ "$event" == push ]]; then
  "$GIT_BIN" fetch --no-tags origin "$CI_PREV_COMMIT_SHA" ||
    die "Unable to fetch CI_PREV_COMMIT_SHA"
  "$GIT_BIN" fetch --no-tags origin "$CI_COMMIT_SHA" ||
    die "Unable to fetch CI_COMMIT_SHA"
  changed_files=$("$GIT_BIN" diff --name-only "$CI_PREV_COMMIT_SHA" "$CI_COMMIT_SHA" --) ||
    die "Unable to produce source diff"
  while IFS= read -r path; do
    [[ -z "$path" ]] || map_path "$path"
  done <<< "$changed_files"
fi

mapfile -t selected_apps < <(print_selected)
[[ ${#selected_apps[@]} -gt 0 ]] || {
  echo "No applications selected for promotion."
  exit 0
}

image_tag=${CI_COMMIT_SHA:0:7}
gitops_branch=${GITOPS_BRANCH:-main}
gitops_repo_slug=${GITOPS_REPO_SLUG:?GITOPS_REPO_SLUG is required}
promotion_branch="ci/promote-${CI_COMMIT_SHA:0:12}"

apps_csv=$(IFS=,; echo "${selected_apps[*]}")
repo_url=${GITOPS_REPO_URL:?GITOPS_REPO_URL is required}
image_registry=${IMAGE_REGISTRY:?IMAGE_REGISTRY is required}

promote_attempt() {
  local attempt=$1 attempt_dir="$promotion_tmp/attempt-$1" app digest target path diff_status
  local changed_paths_file="$promotion_tmp/changed-paths-$1"
  local -a targets=() changed_paths=()
  local -A allowed_targets=()

  "$GIT_BIN" clone --quiet --branch "$gitops_branch" --single-branch \
    "$repo_url" "$attempt_dir" || return 1
  (
    cd "$attempt_dir" || exit 1
    "$GIT_BIN" config user.name threshold-ci-bot || exit 1
    "$GIT_BIN" config user.email threshold-ci-bot@users.noreply.github.com || exit 1

    for app in "${selected_apps[@]}"; do
      target="infra/kustomize/overlays/local/$app/kustomization.yaml"
      [[ -f "$target" ]] || {
        echo "Missing selected overlay: $target" >&2
        exit 1
      }
      allowed_targets["$target"]=1
      targets+=("$target")
      digest=$(<"$IMAGE_DIGEST_DIR/$app.digest") || exit 1
      [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
        echo "Missing or invalid digest for $app" >&2
        exit 1
      }
      python3 "$BUMP_HELPER" --repo-root "$PWD" --service "$app" \
        --digest "$digest" --image-registry "$image_registry" || exit 1
    done

    "$GIT_BIN" diff --name-only HEAD -- > "$changed_paths_file" || exit 1
    "$GIT_BIN" ls-files --others --exclude-standard >> "$changed_paths_file" ||
      exit 1
    sort -u -o "$changed_paths_file" "$changed_paths_file" || exit 1
    mapfile -t changed_paths < "$changed_paths_file"
    for path in "${changed_paths[@]}"; do
      [[ -v "allowed_targets[$path]" ]] || {
        echo "Unexpected changed file; refusing to commit: $path" >&2
        exit 1
      }
    done
    [[ ${#changed_paths[@]} -gt 0 ]] || exit 10

    "$GIT_BIN" add -- "${targets[@]}" || exit 1
    if "$GIT_BIN" diff --cached --quiet; then
      exit 10
    else
      diff_status=$?
      [[ "$diff_status" == 1 ]] || exit 1
    fi
    "$GIT_BIN" commit -m "chore(gitops): promote $apps_csv from $image_tag" ||
      exit 1
    "$GIT_BIN" push --force origin "HEAD:refs/heads/$promotion_branch" || exit 1

    existing_pr=$("$CURL_BIN" --fail --silent --show-error \
      -H "Authorization: Bearer $GIT_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/$gitops_repo_slug/pulls?state=open&base=$gitops_branch&head=${gitops_repo_slug%%/*}:$promotion_branch") || exit 1
    pr_count=$(printf '%s' "$existing_pr" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))') || exit 1
    if [[ "$pr_count" == 0 ]]; then
      pr_payload=$(python3 -c 'import json,sys; print(json.dumps({"title": sys.argv[1], "head": sys.argv[2], "base": sys.argv[3], "body": sys.argv[4]}))' \
        "Promote $apps_csv from $image_tag" "$promotion_branch" "$gitops_branch" \
        "Automated digest-only promotion for source commit $CI_COMMIT_SHA.") || exit 1
      "$CURL_BIN" --fail --silent --show-error -X POST \
        -H "Authorization: Bearer $GIT_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -H "Content-Type: application/json" \
        -d "$pr_payload" "https://api.github.com/repos/$gitops_repo_slug/pulls" >/dev/null || exit 1
    fi
  )
}

for attempt in 1 2 3 4 5; do
  if promote_attempt "$attempt"; then
    echo "Promoted $apps_csv to $image_tag."
    exit 0
  else
    status=$?
  fi
  [[ "$status" != 10 ]] || {
    echo "GitOps overlays are already current."
    exit 0
  }
  echo "Push failed on attempt $attempt; retrying after remote update." >&2
  sleep $((attempt * 2))
done

die "Failed to push GitOps promotion after 5 attempts"
