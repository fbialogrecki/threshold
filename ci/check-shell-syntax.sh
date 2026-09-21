#!/usr/bin/env bash
# Parse each explicit file separately; never execute the selected scripts.
set -u

if (( $# == 0 )); then
  printf 'No shell scripts selected.\n' >&2
  exit 1
fi

status=0
for file in "$@"; do
  if [[ ! -f "$file" ]]; then
    printf 'Not a shell script file: %s\n' "$file" >&2
    status=1
  elif ! bash -n -- "$file"; then
    status=1
  fi
done
exit "$status"
