#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_PATH=$(realpath "$0")
readonly SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
readonly BUMP_HELPER="$SCRIPT_DIR/bump-service-gitops.py"
readonly APPLICATIONS=(auth-gateway events media social users web)
readonly GIT_BIN=${WOODPECKER_GIT_BIN:-git}
readonly CURL_BIN=${WOODPECKER_CURL_BIN:-curl}
readonly KUBE_TOKEN_FILE=${WOODPECKER_KUBE_TOKEN_FILE:-/var/run/secrets/kubernetes.io/serviceaccount/token}
readonly KUBE_CA=${WOODPECKER_KUBE_CA:-/var/run/secrets/kubernetes.io/serviceaccount/ca.crt}
readonly KUBE_NAMESPACE_FILE=${WOODPECKER_KUBE_NAMESPACE_FILE:-/var/run/secrets/kubernetes.io/serviceaccount/namespace}
readonly RELEASE_CONFIG_NAME=${WOODPECKER_RELEASE_CONFIG_NAME:-woodpecker-release-config}
readonly IMAGE_DIGEST_DIR=${WOODPECKER_IMAGE_DIGEST_DIR:-.woodpecker-digests}

die() {
  echo "$*" >&2
  exit 1
}

usage() {
  echo "usage: $0 [--dry-run] [--self-test]" >&2
  exit 2
}

self_test() {
  local tmp output resolved_digest_dir
  export GITOPS_REPO_SLUG=test/perlimen
  export GITOPS_REPO_URL=https://github.com/test/perlimen.git
  export IMAGE_REGISTRY=registry.example.test/perlimen
  tmp=$(mktemp -d)
  trap "rm -rf -- '$tmp'" EXIT

  output=$(CI_PIPELINE_EVENT=push CI_COMMIT_BRANCH=main \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" --dry-run)
  [[ "$output" == $'auth-gateway\nevents\nmedia\nsocial\nusers\nweb' ]] ||
    die "self-test failed: consistent full image set"
  for event in manual pull_request tag; do
    if CI_PIPELINE_EVENT="$event" CI_COMMIT_BRANCH=main \
      CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
      "$SCRIPT_PATH" --dry-run >/dev/null 2>&1; then
      die "self-test failed: non-push event accepted"
    fi
  done
  if CI_PIPELINE_EVENT=push CI_COMMIT_BRANCH=feature \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" --dry-run >/dev/null 2>&1; then
    die "self-test failed: non-main branch accepted"
  fi

  mkdir "$tmp/home" "$tmp/digests"
  for app in "${APPLICATIONS[@]}"; do
    printf '%s\n' 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' > "$tmp/digests/$app.digest"
  done
  resolved_digest_dir=$(cd "$tmp" && resolve_digest_dir digests)
  [[ "$resolved_digest_dir" == "$tmp/digests" ]] ||
    die "self-test failed: relative digest directory was not anchored to the workspace"
  printf 'service-account-token\n' > "$tmp/token"
  printf 'woodpecker-release\n' > "$tmp/namespace"
  : > "$tmp/ca"
  cat > "$tmp/curl" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *"api.github.com"* ]]; then
  [[ "$*" == *"Authorization: Bearer t"* ]] || exit 42
  if [[ "$*" == *"api.github.com/graphql"* ]]; then
    [[ "$*" == *'"prId": "PR_test"'* ]] || exit 43
    echo auto-merge >> "$WOODPECKER_TEST_LOG"
    printf '%s\n' '{"data":{}}'
  elif [[ "$*" == *"-X POST"* ]]; then
    echo pr-create >> "$WOODPECKER_TEST_LOG"
    printf '%s\n' '{"node_id":"PR_test"}'
  else
    echo pr-list >> "$WOODPECKER_TEST_LOG"
    printf '%s\n' '[]'
  fi
  exit 0
fi
[[ "$*" == *"Authorization: Bearer service-account-token"* ]] || exit 42
echo auth >> "$WOODPECKER_TEST_LOG"
printf '%s\n' '{"data":{"GIT_USERNAME":"dQ==","GIT_TOKEN":"dA=="}}'
EOF
  cat > "$tmp/git" <<'EOF'
#!/usr/bin/env bash
case "${1:-}:${2:-}:${3:-}" in
  clone:*)
    destination=${!#}
    for app in auth-gateway events media social users web; do
      mkdir -p "$destination/infra/kustomize/overlays/local/$app"
      cat > "$destination/infra/kustomize/overlays/local/$app/kustomization.yaml" <<YAML
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
images:
  - name: threshold/$app
    newName: registry.example.test/perlimen/$app
    newTag: old
YAML
    done
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
  add:*) echo add >> "$WOODPECKER_TEST_LOG" ;;
  commit:*) echo commit >> "$WOODPECKER_TEST_LOG" ;;
  push:*)
    printf 'push:%s\n' "${!#}" >> "$WOODPECKER_TEST_LOG"
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
  rm -f "$tmp/sequence.pushes"
  HOME="$tmp/home" GIT_USERNAME=u GIT_TOKEN=t \
    WOODPECKER_CURL_BIN="$tmp/curl" WOODPECKER_GIT_BIN="$tmp/git" \
    WOODPECKER_IMAGE_DIGEST_DIR="$tmp/digests" \
    WOODPECKER_KUBE_TOKEN_FILE="$tmp/token" WOODPECKER_KUBE_CA="$tmp/ca" \
    WOODPECKER_KUBE_NAMESPACE_FILE="$tmp/namespace" \
    WOODPECKER_TEST_LOG="$tmp/sequence" AUTO_MERGE=true \
    WOODPECKER_TEST_PUSH_FAILURES=1 \
    CI_PIPELINE_EVENT=push CI_COMMIT_BRANCH=main CI_REPO_DEFAULT_BRANCH=main \
    CI_REPO=test/perlimen \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" >/dev/null

  local full_log
  full_log=$(<"$tmp/sequence")
  [[ "$full_log" == $'clone\nconfig\nconfig\nworktree-diff\nadd\nstaged-diff\ncommit\npush:HEAD:refs/heads/ci/promote-222222222222\nclone\nconfig\nconfig\nworktree-diff\nadd\nstaged-diff\ncommit\npush:HEAD:refs/heads/ci/promote-222222222222\npr-list\npr-create\nauto-merge' ]] ||
    die "self-test failed: fresh retry did not reapply selected bumps"

  echo "self-test passed"
}

promotion_tmp=
git_credentials_file=
image_digest_dir=

resolve_digest_dir() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "$PWD" "$1" ;;
  esac
}

cleanup() {
  [[ -z "$promotion_tmp" ]] || rm -rf -- "$promotion_tmp"
  unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0
  unset GIT_TOKEN GIT_USERNAME
}

configure_credentials() {
  [[ -n "${GIT_USERNAME:-}" && -n "${GIT_TOKEN:-}" ]] ||
    die "Event-restricted Git credentials are required"

  printf 'https://%s:%s@github.com\n' "$GIT_USERNAME" "$GIT_TOKEN" > "$git_credentials_file"
  chmod 600 "$git_credentials_file"
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0=credential.helper
  export GIT_CONFIG_VALUE_0="store --file=$git_credentials_file"
  unset GIT_USERNAME
}

load_release_config() {
  [[ -n "${GITOPS_REPO_SLUG:-}" && -n "${GITOPS_REPO_URL:-}" && -n "${IMAGE_REGISTRY:-}" ]] && return
  local config_json kube_namespace kube_token
  kube_token=$(<"$KUBE_TOKEN_FILE")
  kube_namespace=$(<"$KUBE_NAMESPACE_FILE")
  config_json=$("$CURL_BIN" --fail --silent --show-error --cacert "$KUBE_CA" \
    -H "Authorization: Bearer $kube_token" \
    "https://kubernetes.default.svc/api/v1/namespaces/$kube_namespace/configmaps/$RELEASE_CONFIG_NAME")
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
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) dry_run=1 ;;
    --self-test) self_test; exit 0 ;;
    *) usage ;;
  esac
  shift
done

[[ "${CI_PIPELINE_EVENT:-}" == push ]] || die "Promotion requires a push event"
[[ "${CI_COMMIT_BRANCH:-}" == main ]] || die "Promotion requires main"
[[ "${CI_COMMIT_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || die "CI_COMMIT_SHA must be a full SHA"
[[ "${AUTO_MERGE:-false}" == true || "${AUTO_MERGE:-false}" == false ]] ||
  die "AUTO_MERGE must be true or false"

if [[ "$dry_run" == 1 ]]; then
  printf '%s\n' "${APPLICATIONS[@]}"
  exit 0
fi

trap cleanup EXIT
promotion_tmp=$(mktemp -d)
git_credentials_file="$promotion_tmp/git-credentials"
[[ -f "$BUMP_HELPER" ]] || die "Missing release bump helper: $BUMP_HELPER"
image_digest_dir=$(resolve_digest_dir "$IMAGE_DIGEST_DIR")
[[ -d "$image_digest_dir" ]] || die "Missing image digest directory: $image_digest_dir"
load_release_config
configure_credentials

selected_apps=("${APPLICATIONS[@]}")

image_tag=${CI_COMMIT_SHA}
gitops_branch=${GITOPS_BRANCH:-main}
gitops_repo_slug=${GITOPS_REPO_SLUG:?GITOPS_REPO_SLUG is required}
apps_csv=$(IFS=,; echo "${selected_apps[*]}")
promotion_branch="ci/promote-${CI_COMMIT_SHA:0:12}"
commit_message="chore(gitops): promote $apps_csv from $image_tag"
pr_title="Promote $apps_csv from $image_tag"
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
    "$GIT_BIN" config user.name perlimen-ci-bot || exit 1
    "$GIT_BIN" config user.email perlimen-ci-bot@users.noreply.github.com || exit 1

    for app in "${selected_apps[@]}"; do
      target="infra/kustomize/overlays/local/$app/kustomization.yaml"
      [[ -f "$target" ]] || {
        echo "Missing selected overlay: $target" >&2
        exit 1
      }
      allowed_targets["$target"]=1
      targets+=("$target")
      digest=$(<"$image_digest_dir/$app.digest") || exit 1
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
    "$GIT_BIN" commit -m "$commit_message" || exit 1
    "$GIT_BIN" push --force origin "HEAD:refs/heads/$promotion_branch" || exit 1

    existing_pr=$("$CURL_BIN" --fail --silent --show-error \
      -H "Authorization: Bearer $GIT_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/$gitops_repo_slug/pulls?state=open&base=$gitops_branch&head=${gitops_repo_slug%%/*}:$promotion_branch") || exit 1
    pr_node_id=$(printf '%s' "$existing_pr" | python3 -c 'import json,sys; prs=json.load(sys.stdin); print(prs[0]["node_id"] if prs else "")') || exit 1
    if [[ -z "$pr_node_id" ]]; then
      pr_payload=$(python3 -c 'import json,sys; print(json.dumps({"title": sys.argv[1], "head": sys.argv[2], "base": sys.argv[3], "body": sys.argv[4]}))' \
        "$pr_title" "$promotion_branch" "$gitops_branch" \
        "Automated digest-only promotion for source commit $CI_COMMIT_SHA.") || exit 1
      created_pr=$("$CURL_BIN" --fail --silent --show-error -X POST \
        -H "Authorization: Bearer $GIT_TOKEN" \
        -H "Accept: application/vnd.github+json" \
        -H "Content-Type: application/json" \
        -d "$pr_payload" "https://api.github.com/repos/$gitops_repo_slug/pulls") || exit 1
      pr_node_id=$(printf '%s' "$created_pr" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("node_id", ""))') || exit 1
    fi

    if [[ "${AUTO_MERGE:-false}" == true ]]; then
      [[ -n "$pr_node_id" ]] || { echo "GitHub did not return the PR node id" >&2; exit 1; }
      merge_payload=$(python3 -c 'import json,sys; print(json.dumps({"query": "mutation($prId: ID!) { enablePullRequestAutoMerge(input: {pullRequestId: $prId, mergeMethod: SQUASH}) { clientMutationId } }", "variables": {"prId": sys.argv[1]}}, separators=(", ", ": ")))' \
        "$pr_node_id") || exit 1
      merge_result=$("$CURL_BIN" --fail --silent --show-error -X POST \
        -H "Authorization: Bearer $GIT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$merge_payload" "https://api.github.com/graphql") || exit 1
      printf '%s' "$merge_result" | python3 -c 'import json,sys; r=json.load(sys.stdin); sys.exit(1 if r.get("errors") else 0)' || {
        echo "Enabling auto-merge failed: $merge_result" >&2
        exit 1
      }
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
