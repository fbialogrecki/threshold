#!/usr/bin/env bash
# Restore every PostgreSQL dump from the newest *-k8s-* Borg archive into a
# throwaway local Postgres container and print per-database table/row counts.
# Touches nothing in the cluster; the container and temp dir are removed after.
set -euo pipefail
# The library sits next to this script: in ~/bin when installed, or in
# ops/backup/ in the repository.
# shellcheck source=ops/backup/nuc-backup-lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/nuc-backup-lib.sh"
require_backup_env

PG_IMAGE="${PG_IMAGE:-docker.io/library/postgres:18}"
ARCHIVE="${1:-$(borg list --short --glob-archives '*-k8s-*' --sort-by timestamp --last 1 "$BORG_REPO")}"
WORK="$(mktemp -d)"
CONTAINER="nuc-restore-test-$$"
cleanup() {
  podman rm -f "$CONTAINER" >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT INT TERM

echo "== Restore test from $ARCHIVE =="
(cd "$WORK" && borg extract "$BORG_REPO::$ARCHIVE" --pattern '+**/postgres/*.dump' --pattern '-**')
mapfile -t dumps < <(find "$WORK" -name '*.dump' | sort)
if (( ${#dumps[@]} == 0 )); then
  echo "ERROR: no PostgreSQL dumps in $ARCHIVE" >&2
  exit 1
fi

podman run -d --rm --name "$CONTAINER" -e POSTGRES_PASSWORD=restore-test \
  -v "$WORK:/dumps:ro,Z" "$PG_IMAGE" >/dev/null
# The image's init step runs a temporary socket-only server that already
# answers pg_isready; checking over TCP waits for the real server.
for _ in $(seq 1 60); do
  podman exec "$CONTAINER" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && break
  sleep 1
done

failed=0
for dump in "${dumps[@]}"; do
  db="$(basename "$dump" .dump)"
  db="${db##*__}"
  inside="/dumps/${dump#"$WORK"/}"
  podman exec "$CONTAINER" createdb -U postgres "$db"
  # Roles from the cluster do not exist here, so ownership/grants are skipped.
  if podman exec "$CONTAINER" pg_restore -U postgres -d "$db" --no-owner --no-privileges --exit-on-error "$inside"; then
    podman exec "$CONTAINER" psql -U postgres -d "$db" -qc analyze
    stats="$(podman exec "$CONTAINER" psql -U postgres -d "$db" -Atc \
      "select count(*) || ' tables, ' || coalesce(sum(n_live_tup),0) || ' rows' from pg_stat_user_tables")"
    echo "OK   $db: $stats"
  else
    echo "FAIL $db" >&2
    failed=1
  fi
done
exit "$failed"
