#!/usr/bin/env sh
# A release is `task release VERSION=vX.Y.Z`: it pushes an annotated tag and
# starts the manual pipeline on main with RELEASE_TAG set. Refuse to build
# anything unless that tag exists and points at the commit being built.
set -eu

tag=${RELEASE_TAG:-}
printf '%s\n' "$tag" | grep -Eq '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$' || {
  echo "RELEASE_TAG must look like v1.2.3 (start releases with: task release VERSION=v1.2.3)" >&2
  exit 1
}
printf '%s\n' "${CI_COMMIT_SHA:-}" | grep -Eq '^[0-9a-f]{40}$' || {
  echo "CI_COMMIT_SHA must be a full 40-character SHA" >&2
  exit 1
}

git fetch --quiet --no-recurse-submodules origin "refs/tags/$tag:refs/tags/$tag" || {
  echo "tag $tag does not exist on origin" >&2
  exit 1
}
tagged=$(git rev-parse "refs/tags/$tag^{commit}")
[ "$tagged" = "$CI_COMMIT_SHA" ] || {
  echo "tag $tag points at $tagged, pipeline builds $CI_COMMIT_SHA" >&2
  exit 1
}
echo "release $tag = $CI_COMMIT_SHA"
