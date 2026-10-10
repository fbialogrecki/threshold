# Release And Deploy

Perlimen is one public repository. Product code, desired cluster state and operator tooling all live here. The former separate GitOps and ops repositories are archived and read-only.

## Repository Layout

| Path | Contents |
|---|---|
| `apps/`, `services/`, `libs/` | Product code, tests, migrations, Dockerfiles |
| `infra/` | Argo CD applications (`infra/argocd`), Kustomize bases and the `local` overlay (`infra/kustomize`), Helm values (`infra/helm`), Grafana dashboards |
| `ops/` | Operator scripts: bootstrap, secret seeding, unseal, token rotation, restore gate; host backup scripts in `ops/backup/` |
| `docs/` | Architecture and runbooks |
| `ci/`, `.woodpecker/` | CI helpers and the Woodpecker release pipeline |

Private values such as the Bitwarden account and item names live in `ops/local.env`, which is git-ignored. No secret value is ever committed; secrets live in OpenBao and reach the cluster through ESO.

Argo CD tracks `https://github.com/fbialogrecki/perlimen.git`, branch `main`, path `infra/argocd` (root Application `threshold-root`). Anything merged to `main` under `infra/` is deployed.

For native forge deliveries without exposing the private CI UI, see [Woodpecker public webhooks](runbooks/woodpecker-webhooks.md). Application/build-input pushes to `main` now explicitly authorize automatic publication through the workflow below; other branches and PRs only validate.

## Automatic Main Deployment

Push a commit to `main`, directly or by merging a PR. No version argument, tag or manual pipeline creation is needed. GitHub delivers the native webhook to the public hook-only endpoint; the CI UI/OAuth remain private.

`.woodpecker/deploy.yml` runs only for application/build-input changes on `main`, on the existing `release: trusted` agent. Its publication credentials allow `push`, never PR/tag events. Public GitOps slug/URL are explicit non-secret workflow values:

1. `verify-main-ci` waits up to 30 minutes for GitHub Actions `ci-ok` on the **exact source SHA**. Pending checks wait; failure, cancellation, wrong SHA, API failure and timeout prevent publication. No old success or another app's check is accepted.
2. `build-images` builds all six images and pushes `core.harbor.domain/threshold/<service>:<full sha>`, recording the registry-provided immutable digests. It does not create SemVer tags.
3. `promote-gitops` selects the services affected by the source diff (shared Python inputs select backends; publication controls select all), opens a digest-only PR from `ci/promote-<short sha>`, and enables squash auto-merge after its `ci-ok` passes. Argo CD deploys once it merges.

Docs and `infra/`-only pushes are excluded from publication. In particular, merging the digest PR cannot start another build/promotion loop. Infrastructure changes still sync through Argo CD as before. Existing SemVer tags/history are retained; routine deployments are identified by source SHA and image digest.

During first-path verification only, the old manual workflow/task and `manual` secret scope are temporarily retained as a working fallback. Remove them only after the real automatic build/promotion/deploy succeeds.

## Buildah Runtime Profile

The node keeps `seccompDefault: true`. Buildah needs nested user/mount/UTS namespaces and mounts inside them; runtime default denies these before image building. Only Buildah steps select `Localhost: perlimen/buildah.json`, keeping ordinary steps and product pods on their existing profiles. The exception does not add capabilities or privileged mode; kernel capability checks still reject host-namespace mounts. Network, IPC and PID namespace creation remain denied.

On the single k3s node, install/rebuild the profile after runtime updates, before running CI:

```bash
sudo python3 ops/install-buildah-seccomp.py
python3 -m unittest discover -s ops/tests -p 'test_buildah_seccomp.py'
```

The installer reads the running release agent's actual default-deny runtime profile, appends only the Buildah exceptions and atomically installs `/var/lib/kubelet/seccomp/perlimen/buildah.json`. Re-run on every builder node if the cluster later grows. Verify actual image pull/build/run and a denied network-namespace probe before release. A missing profile must fail loudly, not fall back to `Unconfined`. The additional kernel syscall surface is limited to CI builders, but remains a residual risk.

If automatic publication fails, inspect the native pipeline before retrying. Redeliver the original GitHub main-push delivery to retry the same source SHA, or merge a fix for a new source SHA. Do not create or move tags, bypass `ci-ok`, or edit desired image digests by hand.

## Rollback

Revert the digest PR on `main`. Argo CD syncs the previous digests. Database migrations are not reverted automatically; write migrations so the previous release still runs against the new schema.

## Deploy Pitfalls

1. **ConfigMap-only changes are not picked up.** Service ConfigMaps load through `envFrom` without a content hash, so pods keep the old values. After merging, run `kubectl -n threshold rollout restart deploy/<service>`. An image promotion restarts pods anyway.
2. **CNPG spec changes race the migration hook.** Changing a CNPG `Cluster` spec restarts the database, and the Argo CD migration hook Job in the same sync can hit the restarting database and fail. A failed hook Job is kept (the delete policy is `HookSucceeded`), so delete it before re-syncing. `Synced`/`Healthy` does not prove migrations ran; check the Job logs or the `alembic_version` table.
3. **NetworkPolicies block new callers.** Every service has a `NetworkPolicy` in `infra/kustomize/base/<service>/networkpolicy.yaml`. A new HTTP caller must be added to the callee's policy in the same PR. A missing entry looks like a timeout, not a 403.
4. **New settings need manifests.** A new variable in a service's pydantic `Settings` needs its ConfigMap or `ExternalSecret` entry in the same PR. Otherwise the default applies silently in the cluster. `THRESHOLD_USERS_SERVICE_URL` and `THRESHOLD_EVENTS_SERVICE_URL` were both missed this way.

## Release Token Rotation

The pipeline authenticates to GitHub with a fine-grained PAT limited to the `perlimen` repository (Contents: write, Pull requests: write), valid for 90 days. It is stored in OpenBao at `secret/threshold/ci/github-writer` and reaches Woodpecker through ESO.

To rotate:

1. Create the new fine-grained PAT in GitHub with the scopes above.
2. Run `ops/rotate-release-token-from-bitwarden.sh`. It reads the PAT from the Bitwarden item named in `ops/local.env` (or prompts for it without echo and stores it there), gets OpenBao access through Bitwarden Secrets Manager, writes the new value, forces ESO to refresh and checks the propagated value. It never prints the token.
3. Re-seed the event-restricted Woodpecker repository secrets from an authenticated `woodpecker-cli` session with `ops/configure-woodpecker-release-secrets.sh`. The rotation script deliberately stops at OpenBao/ESO.
