# Backup And Restore

A backup is not trusted until a restore from it has succeeded. There are two independent layers:

1. **CNPG object-store backups** inside the cluster: continuous WAL archiving plus a daily base backup per database.
2. **Host Borg backups** on the server: logical dumps, Kubernetes/Helm exports, home directory, and a weekly system tar.

## CNPG Object-Store Backups

Each service cluster (`users-postgres`, `social-postgres`, `events-postgres`, `media-postgres`) archives WAL and takes a daily `ScheduledBackup` through the Barman Cloud plugin to `s3://threshold-cnpg-backups/<cluster>` on SeaweedFS. Retention is 14 days (`retentionPolicy` on each `ObjectStore`). All four use the shared `cnpg-backup` S3 identity from OpenBao `threshold/cnpg/users-postgres/s3`.

Manifests: `infra/kustomize/base/<service>/postgres-backup-objectstore.yaml`, `postgres-scheduled-backup.yaml`, `cnpg-backup-s3-external-secret.yaml`.

Check the latest backups:

```bash
kubectl -n threshold get backups.postgresql.cnpg.io --sort-by=.metadata.creationTimestamp | tail
kubectl -n threshold get scheduledbackups.postgresql.cnpg.io
```

### Restore gate

`ops/cnpg-restore-gate.sh` takes an on-demand plugin backup of a cluster, restores it into a throwaway cluster, runs SQL sanity checks (Alembic marker present, at least one table), and deletes the throwaway cluster and its PVCs. It defaults to `users-postgres`; other clusters use overrides:

```bash
SOURCE_CLUSTER=social-postgres \
RESTORE_CLUSTER=social-postgres-restore-drill \
DATABASE=threshold_social \
S3_SECRET=social-postgres-backup-s3 \
BARMAN_OBJECT_STORE=social-postgres-backup-store \
ops/cnpg-restore-gate.sh
```

Set `KEEP_RESTORE_DRILL=true` to keep the restored cluster for inspection; delete it afterwards. The gate writes to the cluster, so run it only for backup or data work, not as a routine check.

## Host Borg Backups

The Borg repository is on a separate local disk, `/mnt/backup/borg/nuc`. Settings (`BACKUP_ROOT`, `BORG_REPO`, `HOST_LABEL`, `LOG_DIR`, `STAGING_BASE`) are in `~/.config/nuc-backup/config.env`, which is not in the repository.

Scripts are in `ops/backup/`; the restore gate is `ops/cnpg-restore-gate.sh`. Cron runs copies in `~/bin`, never the checkout. Install or update them with:

```bash
task ops:backup:install
```

Re-run it after every change to `ops/backup/` or `ops/cnpg-restore-gate.sh`. It shows a diff for each replaced file.

| Script | Runs | Contents |
|---|---|---|
| `nuc-backup-daily.sh` | Mon–Sat 05:17, user crontab | Kubernetes/Helm exports, `pg_dump -Fc` of every CNPG database, home directory |
| `nuc-backup-weekly.sh` | Sun 05:37, root crontab | The same, plus a tar of `/etc`, `/boot`, k3s server state and storage, and SeaweedFS data |
| `threshold-cnpg-restore-gate-weekly.sh` | Sun 04:20, user crontab | Runs `~/bin/cnpg-restore-gate.sh` for `users-postgres` under a lock |
| `nuc-backup-restore-test.sh` | by hand | Restores database dumps from Borg into a throwaway container |
| `nuc-backup-lib.sh` | sourced | Shared functions |

Crontab entries. User crontab (`crontab -e`):

```cron
17 5 * * 1-6 ~/bin/nuc-backup-daily.sh >> ~/.local/state/nuc-backup/daily.log 2>&1
20 4 * * 0 ~/bin/threshold-cnpg-restore-gate-weekly.sh
```

Root crontab (`sudo crontab -e`). `~` would point at root's home here, so use the maintainer's absolute home path:

```cron
37 5 * * 0 /home/<user>/bin/nuc-backup-weekly.sh >> /home/<user>/.local/state/nuc-backup/weekly.log 2>&1
```

Behaviour worth knowing:

- The scripts set `PATH` and `KUBECONFIG` themselves; cron's `PATH` has no `/usr/local/bin`, and the root job has no kubeconfig of its own.
- Any failed step (empty export, failed `pg_dump`, Borg error) marks the run failed. The run still finishes and prunes, then exits 1 with `finished WITH ERRORS` at the end of the log. Borg warnings (exit 1) do not fail the run.
- Weekly runs as root, then hands repository files back to the maintainer's user so daily runs and `borg list` work without sudo.
- Harbor registry and Trivy data are excluded from the weekly tar; images are rebuilt from CI.
- Prune keeps 7 daily, 4 weekly and 6 monthly archives per family (`home`, `k8s`, `system-k3s`, `warnings`).

Logs: `~/.local/state/nuc-backup/` and `~/.local/state/threshold-cnpg-restore-gate/`.

## Checking That Backups Restore

```bash
~/bin/nuc-backup-restore-test.sh            # newest *-k8s-* archive
~/bin/nuc-backup-restore-test.sh <archive>  # a specific archive
borg list /mnt/backup/borg/nuc | tail
```

The restore test extracts every `*.dump` from the archive, restores each into a throwaway Postgres container (podman, no cluster access), and prints table and row counts. It exits 1 if any restore fails.

## Restoring A Database From A Borg Dump

Use this when the object-store backups are unusable. Restore into a new database first, verify, then switch.

```bash
cd "$(mktemp -d)"
borg extract /mnt/backup/borg/nuc::<archive> --pattern '+**/postgres/*.dump' --pattern '-**'
dump=$(find . -name 'threshold__users-postgres__threshold_users.dump')

kubectl -n threshold exec users-postgres-1 -c postgres -- createdb threshold_users_restore
kubectl -n threshold exec -i users-postgres-1 -c postgres -- \
  pg_restore --no-owner -d threshold_users_restore < "$dump"
kubectl -n threshold exec users-postgres-1 -c postgres -- \
  psql -d threshold_users_restore -Atc 'select version_num from alembic_version'
```

Compare row counts with the live database, then decide how to switch (rename databases during a maintenance window, or restore over the original with `pg_restore --clean --if-exists`). Drop the scratch database when done.

## Known Gaps

- No off-host copy. The server and the backup disk can be lost together.
- The Borg repository is unencrypted, like the source disk. Encrypt it when an off-host copy is added.
- OpenBao's file backend is copied live in the weekly tar, not from a snapshot. No OpenBao restore drill has been run.
- No drill has rebuilt a fresh cluster from `infra/` plus restored OpenBao state.
- Backup retention (Borg monthly copies for about 6 months) does not match the 30-day retention assumed by the account-erasure notes. Unresolved.
