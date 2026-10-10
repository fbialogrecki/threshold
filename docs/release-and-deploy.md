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

For native forge deliveries without exposing the private CI UI, see [Woodpecker public webhooks](runbooks/woodpecker-webhooks.md). Webhook connectivity does not enable automatic releases; the release workflow below remains manual.

## Releasing

```bash
go-task release VERSION=v1.2.3
```

The task refuses to run unless the working tree is clean, `HEAD` equals `origin/main`, the tag does not exist yet, and the `ci-ok` check on that commit is green. It then pushes an annotated tag and starts the Woodpecker `release` pipeline on `main` with `RELEASE_TAG` set. GitHub cannot reach Woodpecker on the LAN, so pushing a tag alone does nothing.

The pipeline (`.woodpecker/release.yml`) runs on the dedicated `release: trusted` agent; its secrets are limited to `manual` events:

1. `verify-tag` checks that the tag exists on origin and points at the commit being built.
2. `build-images` builds `auth-gateway`, `events`, `media`, `social`, `users` and `web`, and pushes each to `core.harbor.domain/threshold/<service>` as `:<full sha>` and `:vX.Y.Z`.
3. `promote-gitops` opens the PR **`Release vX.Y.Z: promote digests`** from branch `release/vX.Y.Z`. It changes only the image digests in `infra/kustomize/overlays/local/<service>/kustomization.yaml`.

`AUTO_MERGE` in `release.yml` controls the last step. While it is `false`, a human merges the digest PR. After the first release has gone through end to end, it becomes `true` and the pipeline enables GitHub auto-merge (squash), so the PR merges once its checks pass. Argo CD syncs after the merge.

## Buildah Runtime Profile

The node keeps `seccompDefault: true`. Buildah needs nested user/mount/UTS namespaces and mounts inside them; runtime default denies these before image building. Only Buildah steps select `Localhost: perlimen/buildah.json`, keeping ordinary steps and product pods on their existing profiles. The exception does not add capabilities or privileged mode; kernel capability checks still reject host-namespace mounts. Network, IPC and PID namespace creation remain denied.

On the single k3s node, install/rebuild the profile after runtime updates, before running CI:

```bash
sudo python3 ops/install-buildah-seccomp.py
python3 -m unittest discover -s ops/tests -p 'test_buildah_seccomp.py'
```

The installer reads the running release agent's actual default-deny runtime profile, appends only the Buildah exceptions and atomically installs `/var/lib/kubelet/seccomp/perlimen/buildah.json`. Re-run on every builder node if the cluster later grows. Verify actual image pull/build/run and a denied network-namespace probe before release. A missing profile must fail loudly, not fall back to `Unconfined`. The additional kernel syscall surface is limited to CI builders, but remains a residual risk.

If the release task pushed a tag but failed before pipeline creation, do not retag: start only the pipeline via the HTTPS server. If the fix changes the tagged source, keep the failed tag and issue a new version after green CI.

## Rollback

Revert the digest PR on `main`. Argo CD syncs the previous digests. Database migrations are not reverted automatically; write migrations so the previous release still runs against the new schema.

## Deploy Pitfalls

1. **ConfigMap-only changes are not picked up.** Service ConfigMaps load through `envFrom` without a content hash, so pods keep the old values. After merging, run `kubectl -n threshold rollout restart deploy/<service>`. An image promotion restarts pods anyway.
2. **CNPG spec changes race the migration hook.** Changing a CNPG `Cluster` spec restarts the database, and the Argo CD migration hook Job in the same sync can hit the restarting database and fail. A failed hook Job is kept (the delete policy is `HookSucceeded`), so delete it before re-syncing. `Synced`/`Healthy` does not prove migrations ran; check the Job logs or the `alembic_version` table.
3. **NetworkPolicies block new callers.** Every service has a `NetworkPolicy` in `infra/kustomize/base/<service>/networkpolicy.yaml`. A new HTTP caller must be added to the callee's policy in the same PR. A missing entry looks like a timeout, not a 403.
4. **New settings need manifests.** A new variable in a service's pydantic `Settings` needs its ConfigMap or `ExternalSecret` entry in the same PR. Otherwise the default applies silently in the cluster. `THRESHOLD_USERS_SERVICE_URL` and `THRESHOLD_EVENTS_SERVICE_URL` were both missed this way.

## Release Token Rotation

The pipeline authenticates to GitHub with a fine-grained PAT limited to the `threshold` repository (Contents: write, Pull requests: write), valid for 90 days. It is stored in OpenBao at `secret/threshold/ci/github-writer` and reaches Woodpecker through ESO.

To rotate:

1. Create the new fine-grained PAT in GitHub with the scopes above.
2. Run `ops/rotate-release-token-from-bitwarden.sh`. It reads the PAT from the Bitwarden item named in `ops/local.env` (or prompts for it without echo and stores it there), gets OpenBao access through Bitwarden Secrets Manager, writes the new value, forces ESO to refresh and checks the propagated value. It never prints the token.
3. Re-seed the event-restricted Woodpecker repository secrets from an authenticated `woodpecker-cli` session with `ops/configure-woodpecker-release-secrets.sh`. The rotation script deliberately stops at OpenBao/ESO.
