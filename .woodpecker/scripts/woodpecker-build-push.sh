#!/usr/bin/env bash
set -euo pipefail

readonly SCRIPT_PATH=$(realpath "$0")
usage() {
  echo "usage: $0 <service> <dockerfile> <build-context> [cache-reference] | --self-test" >&2
  exit 2
}

self_test() {
  local tmp output auth_file line
  tmp=$(mktemp -d)
  trap "rm -rf -- '$tmp'" EXIT
  mkdir -p "$tmp/repo/context"
  : > "$tmp/repo/Dockerfile"

  output=$(cd "$tmp/repo" && WOODPECKER_DRY_RUN=1 REGISTRY=registry.example.test \
    WOODPECKER_CURL_BIN=/bin/false WOODPECKER_BUILDAH_BIN=/bin/false \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" users Dockerfile context)
  [[ "$output" == \
    "build registry.example.test/threshold/users:2222222 from Dockerfile with context context" ]] ||
    { echo "self-test failed: dry-run attempted side effects" >&2; exit 1; }

  printf 'test-ca\n' > "$tmp/ca-source"
  printf 'service-account-token\n' > "$tmp/token"
  : > "$tmp/kube-ca"
  mkdir "$tmp/anchors"
  cat > "$tmp/curl" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *"/api/v2.0/systeminfo/getcert"* ]]; then
  echo cert >> "$WOODPECKER_TEST_LOG"
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == -o ]]; then
      cp "$WOODPECKER_TEST_CA_SOURCE" "$2"
      exit
    fi
    shift
  done
  exit 1
fi
echo secret >> "$WOODPECKER_TEST_LOG"
printf '%s\n' '{"data":{"HARBOR_USERNAME":"dQ==","HARBOR_PASSWORD":"cA=="}}'
EOF
  cat > "$tmp/buildah" <<'EOF'
#!/usr/bin/env bash
printf '%s:%s\n' "$1" "$REGISTRY_AUTH_FILE" >> "$WOODPECKER_TEST_LOG"
if [[ "$1" == push ]]; then
  shift
  while [[ $# -gt 0 ]]; do
    if [[ "$1" == --digestfile ]]; then
      printf '%s\n' 'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' > "$2"
      break
    fi
    shift
  done
fi
EOF
  cat > "$tmp/getent" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  cat > "$tmp/update-ca-trust" <<'EOF'
#!/usr/bin/env bash
echo trust >> "$WOODPECKER_TEST_LOG"
EOF
  chmod +x "$tmp/curl" "$tmp/buildah" "$tmp/getent" "$tmp/update-ca-trust"

  : > "$tmp/log"
  if cd "$tmp/repo" && REGISTRY=registry.example.test WOODPECKER_CURL_BIN="$tmp/curl" \
    WOODPECKER_BUILDAH_BIN="$tmp/buildah" WOODPECKER_GETENT_BIN="$tmp/getent" \
    WOODPECKER_UPDATE_CA_TRUST_BIN="$tmp/update-ca-trust" \
    WOODPECKER_HARBOR_CA_ANCHOR="$tmp/anchors/harbor-ca.crt" \
    WOODPECKER_KUBE_TOKEN_FILE="$tmp/missing-token" \
    WOODPECKER_KUBE_CA="$tmp/kube-ca" WOODPECKER_TEST_LOG="$tmp/log" \
    WOODPECKER_TEST_CA_SOURCE="$tmp/ca-source" \
    HARBOR_CA_SHA256=0000000000000000000000000000000000000000000000000000000000000000 \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" users Dockerfile context >/dev/null 2>&1; then
    echo "self-test failed: mismatched CA fingerprint was accepted" >&2
    exit 1
  fi
  [[ "$(<"$tmp/log")" == cert && ! -e "$tmp/anchors/harbor-ca.crt" ]] ||
    { echo "self-test failed: CA mismatch reached credentials or trust install" >&2; exit 1; }

  : > "$tmp/log"
  ca_sha=$(sha256sum "$tmp/ca-source")
  ca_sha=${ca_sha%% *}
  (cd "$tmp/repo" && TMPDIR="$tmp" REGISTRY=registry.example.test WOODPECKER_CURL_BIN="$tmp/curl" \
    WOODPECKER_BUILDAH_BIN="$tmp/buildah" WOODPECKER_GETENT_BIN="$tmp/getent" \
    WOODPECKER_UPDATE_CA_TRUST_BIN="$tmp/update-ca-trust" \
    WOODPECKER_HARBOR_CA_ANCHOR="$tmp/anchors/harbor-ca.crt" \
    WOODPECKER_KUBE_TOKEN_FILE="$tmp/token" WOODPECKER_KUBE_CA="$tmp/kube-ca" \
    WOODPECKER_TEST_LOG="$tmp/log" WOODPECKER_TEST_CA_SOURCE="$tmp/ca-source" \
    HARBOR_CA_SHA256="$ca_sha" \
    CI_COMMIT_SHA=2222222222222222222222222222222222222222 \
    "$SCRIPT_PATH" users Dockerfile context >/dev/null)

  auth_file=
  while IFS= read -r line; do
    [[ "$line" == login:* ]] && auth_file=${line#login:}
  done < "$tmp/log"
  [[ "$(<"$tmp/log")" == $'cert\ntrust\nsecret\nlogin:'"$auth_file"$'\nbud:'"$auth_file"$'\npush:'"$auth_file" ]] ||
    { echo "self-test failed: pinned CA production sequence" >&2; exit 1; }
  [[ -n "$auth_file" && ! -e "$auth_file" ]] ||
    { echo "self-test failed: registry auth file was not removed" >&2; exit 1; }
  cmp -s "$tmp/ca-source" "$tmp/anchors/harbor-ca.crt" ||
    { echo "self-test failed: verified CA was not installed" >&2; exit 1; }

  echo "self-test passed"
}

if [[ "${1:-}" == --self-test ]]; then
  [[ $# -eq 1 ]] || usage
  self_test
  exit 0
fi

[[ $# -eq 3 || $# -eq 4 ]] || usage

SERVICE=$1
DOCKERFILE=$2
BUILD_CONTEXT=$3
CACHE_REFERENCE=${4:-}
REGISTRY=${REGISTRY:-}
IMAGE_NAMESPACE=${IMAGE_NAMESPACE:-threshold}
WOODPECKER_DRY_RUN=${WOODPECKER_DRY_RUN:-0}
HARBOR_CA_SHA256=${HARBOR_CA_SHA256:-}
HARBOR_IP=${HARBOR_IP:-}
CURL_BIN=${WOODPECKER_CURL_BIN:-curl}
BUILDAH_BIN=${WOODPECKER_BUILDAH_BIN:-buildah}
GETENT_BIN=${WOODPECKER_GETENT_BIN:-getent}
UPDATE_CA_TRUST_BIN=${WOODPECKER_UPDATE_CA_TRUST_BIN:-update-ca-trust}
HOSTS_FILE=${WOODPECKER_HOSTS_FILE:-/etc/hosts}
HARBOR_CA_ANCHOR=${WOODPECKER_HARBOR_CA_ANCHOR:-/etc/pki/ca-trust/source/anchors/harbor-ca.crt}
KUBE_TOKEN_FILE=${WOODPECKER_KUBE_TOKEN_FILE:-/var/run/secrets/kubernetes.io/serviceaccount/token}
KUBE_CA=${WOODPECKER_KUBE_CA:-/var/run/secrets/kubernetes.io/serviceaccount/ca.crt}
RELEASE_CONFIG_NAME=${WOODPECKER_RELEASE_CONFIG_NAME:-woodpecker-release-config}
IMAGE_DIGEST_DIR=${WOODPECKER_IMAGE_DIGEST_DIR:-.woodpecker-digests}

if [[ "$WOODPECKER_DRY_RUN" == 0 ]] &&
  [[ -z "$REGISTRY" || -z "$HARBOR_CA_SHA256" || -z "$IMAGE_NAMESPACE" ]]; then
  KUBE_TOKEN=$(<"$KUBE_TOKEN_FILE")
  RELEASE_CONFIG_JSON=$("$CURL_BIN" --fail --silent --show-error --cacert "$KUBE_CA" \
    -H "Authorization: Bearer $KUBE_TOKEN" \
    "https://kubernetes.default.svc/api/v1/namespaces/woodpecker/configmaps/$RELEASE_CONFIG_NAME")
  config_value() {
    printf '%s' "$RELEASE_CONFIG_JSON" | python3 -c \
      'import json,sys; print(json.load(sys.stdin).get("data", {}).get(sys.argv[1], ""))' "$1"
  }
  REGISTRY=${REGISTRY:-$(config_value REGISTRY)}
  IMAGE_NAMESPACE=${IMAGE_NAMESPACE:-$(config_value IMAGE_NAMESPACE)}
  HARBOR_IP=${HARBOR_IP:-$(config_value HARBOR_IP)}
  HARBOR_CA_SHA256=${HARBOR_CA_SHA256:-$(config_value HARBOR_CA_SHA256)}
  unset KUBE_TOKEN RELEASE_CONFIG_JSON
fi

case "$SERVICE" in
  auth-gateway|events|media|social|users|web) ;;
  *) echo "Unsupported service: $SERVICE" >&2; exit 1 ;;
esac

for path in "$DOCKERFILE" "$BUILD_CONTEXT"; do
  case "$path" in
    ""|/*|..|../*|*/../*|*/..) echo "Path must stay within the repository: $path" >&2; exit 1 ;;
  esac
done

[[ -f "$DOCKERFILE" ]] || { echo "Dockerfile not found: $DOCKERFILE" >&2; exit 1; }
[[ -d "$BUILD_CONTEXT" ]] || { echo "Build context not found: $BUILD_CONTEXT" >&2; exit 1; }
[[ "$WOODPECKER_DRY_RUN" == 0 || "$WOODPECKER_DRY_RUN" == 1 ]] || {
  echo "WOODPECKER_DRY_RUN must be 0 or 1" >&2
  exit 1
}
[[ -n "$REGISTRY" && -n "$IMAGE_NAMESPACE" ]] || {
  echo "Registry and image namespace must not be empty" >&2
  exit 1
}
[[ "${CI_COMMIT_SHA:-}" =~ ^[0-9a-fA-F]{7,}$ ]] || {
  echo "CI_COMMIT_SHA must begin with at least seven hexadecimal characters" >&2
  exit 1
}

IMAGE_TAG=${CI_COMMIT_SHA:0:7}
IMAGE="$REGISTRY/$IMAGE_NAMESPACE/$SERVICE:$IMAGE_TAG"

if [[ "$WOODPECKER_DRY_RUN" == 1 ]]; then
  printf 'build %s from %s with context %s' "$IMAGE" "$DOCKERFILE" "$BUILD_CONTEXT"
  [[ -z "$CACHE_REFERENCE" ]] || printf ' using cache %s' "$CACHE_REFERENCE"
  printf '\n'
  exit 0
fi

[[ "$HARBOR_CA_SHA256" =~ ^[0-9a-fA-F]{64}$ ]] || {
  echo "HARBOR_CA_SHA256 must be exactly 64 hexadecimal characters" >&2
  exit 1
}

REGISTRY_AUTH_FILE=
harbor_ca_tmp=
digest_tmp=

cleanup() {
  [[ -z "$REGISTRY_AUTH_FILE" ]] || rm -f -- "$REGISTRY_AUTH_FILE"
  [[ -z "$harbor_ca_tmp" ]] || rm -f -- "$harbor_ca_tmp"
  [[ -z "$digest_tmp" ]] || rm -f -- "$digest_tmp"
  unset HARBOR_PASSWORD HARBOR_USERNAME SECRET_JSON KUBE_TOKEN REGISTRY_AUTH_FILE
}
trap cleanup EXIT

REGISTRY_AUTH_FILE=$(mktemp)
harbor_ca_tmp=$(mktemp)
digest_tmp=$(mktemp)
export REGISTRY_AUTH_FILE

resolve_args=()
if ! "$GETENT_BIN" hosts "$REGISTRY" >/dev/null; then
  [[ -n "$HARBOR_IP" ]] || {
    echo "HARBOR_IP is required when REGISTRY does not resolve" >&2
    exit 1
  }
  resolve_args=(--resolve "$REGISTRY:443:$HARBOR_IP")
fi
"$CURL_BIN" --fail --silent --show-error --insecure "${resolve_args[@]}" \
  "https://$REGISTRY/api/v2.0/systeminfo/getcert" -o "$harbor_ca_tmp"
actual_ca_sha=$(sha256sum "$harbor_ca_tmp")
actual_ca_sha=${actual_ca_sha%% *}
[[ "${actual_ca_sha,,}" == "${HARBOR_CA_SHA256,,}" ]] || {
  echo "Harbor CA SHA-256 mismatch" >&2
  exit 1
}

if [[ ${#resolve_args[@]} -gt 0 ]]; then
  echo "$HARBOR_IP $REGISTRY" >> "$HOSTS_FILE"
fi
install -m 0644 "$harbor_ca_tmp" "$HARBOR_CA_ANCHOR"
"$UPDATE_CA_TRUST_BIN"

KUBE_TOKEN=$(<"$KUBE_TOKEN_FILE")
SECRET_JSON=$("$CURL_BIN" --fail --silent --show-error --cacert "$KUBE_CA" \
  -H "Authorization: Bearer $KUBE_TOKEN" \
  https://kubernetes.default.svc/api/v1/namespaces/woodpecker/secrets/woodpecker-harbor-ci)
HARBOR_USERNAME=$(printf '%s' "$SECRET_JSON" | python3 -c \
  'import base64,json,sys; print(base64.b64decode(json.load(sys.stdin)["data"]["HARBOR_USERNAME"]).decode())')
HARBOR_PASSWORD=$(printf '%s' "$SECRET_JSON" | python3 -c \
  'import base64,json,sys; print(base64.b64decode(json.load(sys.stdin)["data"]["HARBOR_PASSWORD"]).decode())')

printf '%s' "$HARBOR_PASSWORD" |
  "$BUILDAH_BIN" login --tls-verify=true -u "$HARBOR_USERNAME" --password-stdin "$REGISTRY"
unset HARBOR_PASSWORD HARBOR_USERNAME SECRET_JSON KUBE_TOKEN

cache_args=()
if [[ -n "$CACHE_REFERENCE" ]]; then
  cache_args=(--layers --cache-from "$CACHE_REFERENCE" --cache-to "$CACHE_REFERENCE")
fi

echo "Building $IMAGE"
"$BUILDAH_BIN" bud --storage-driver=vfs --isolation=chroot --format=docker \
  "${cache_args[@]}" -f "$DOCKERFILE" -t "$IMAGE" "$BUILD_CONTEXT"
"$BUILDAH_BIN" push --storage-driver=vfs --tls-verify=true --digestfile "$digest_tmp" "$IMAGE"
digest=$(<"$digest_tmp")
[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo "Registry returned an invalid image digest" >&2
  exit 1
}
install -d -m 0700 "$IMAGE_DIGEST_DIR"
printf '%s\n' "$digest" > "$IMAGE_DIGEST_DIR/$SERVICE.digest"
echo "Pushed $IMAGE@$digest"
