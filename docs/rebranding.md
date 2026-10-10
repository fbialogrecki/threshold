# Perlimen Naming

The product, source repository and local checkout are named **Perlimen**:

- Product domain: `https://perlimen.com`.
- Source: `https://github.com/fbialogrecki/perlimen`.
- Maintainer checkout: `/home/peregrin/Projects/perlimen`.
- Python distributions: `perlimen-workspace`, `perlimen-common`, and `perlimen-<service>`; shared imports: `perlimen_common`.
- Frontend domain types and UI identifiers use Perlimen, not the former brand.

## Deployed Compatibility Boundary

A brand rename is not a storage or infrastructure migration. The following existing identifiers deliberately remain unchanged until a separately approved, coordinated live migration:

- Kubernetes namespace `threshold`, Argo CD `threshold-*` Applications/ApplicationSet, resource names, labels/selectors, TLS issuer and private hosts.
- OpenBao `secret/threshold/*` paths, ESO target Secrets and remote property names, auth roles/policies, Bitwarden item references.
- Runtime `THRESHOLD_*` environment variables and `X-Threshold-*` HTTP headers. Internal Python attribute names are Perlimen; explicit validation/header aliases keep the deployed wire contract intact.
- Cookies `threshold_session`, `threshold_refresh`, `threshold_locale`; changing these requires deliberate session/locale handling rather than an incidental logout.
- Harbor `core.harbor.domain/threshold/<service>`, Kustomize image keys, registry credentials, S3 `threshold-media`, CNPG backup paths and restore tooling.
- `threshold.http.*` metric/instrumentation names and dashboard selectors. Historical archived repositories and old system-actor rows are not rewritten.
- Woodpecker's active public-source record, release-agent selector and manual release invocation use `fbialogrecki/perlimen`. The former record belongs to the separate archived `threshold-legacy-private` GitHub repository; its CI history remains there. Do not treat that clean-room repository replacement as a rename or transplant its forge ID/history.
- Reserved username `threshold` remains reserved alongside `perlimen` to prevent impersonation of historical system identity.

These are explicit compatibility exceptions, not a second product brand. New public text and source-level names use Perlimen. Do not add generic dual-name shims, rename upstream third-party `threshold` parameters, or rewrite Git history.

## Repository Integrations

GitHub redirects former repository URLs, but owned Argo CD source URLs, CI helpers and documentation use the canonical Perlimen URL. A GitHub rename preserves the repository identity, issues, PRs and deploy keys; verify access and CI rather than assuming every external integration refreshed its stored slug. Woodpecker's registered repository and release configuration must resolve the canonical forge identity before the next explicitly requested release.

Moving the checkout also requires updating profile cwd, linked Git worktrees and operator paths. Host backup scripts are installed copies: run `go-task ops:backup:install` when their source changes. Do not move live datasets or change cron destinations as part of a checkout rename.
