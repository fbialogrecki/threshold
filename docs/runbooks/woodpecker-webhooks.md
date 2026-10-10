# Woodpecker Public Forge Webhooks

## Purpose And Boundaries

The application domain alone does not make GitHub webhooks work. Woodpecker is served privately at `https://woodpecker.internal`; the tunnel's connector NetworkPolicy allows only web, the dedicated webhook proxy, cluster DNS and Cloudflare tunnel edges. Do not send forge hooks to the product BFF or resume the suspended synthetic-push poller.

Woodpecker workflows already support path-filtered `pull_request` and `push` on `main`. A merge produces a `push` to `main`; no synthetic merge trigger is needed. The release workflow remains `event: manual`, with event-restricted release credentials. **Receiving forge webhooks does not authorize automatic image promotion, deployment or releases.** GitHub Actions `ci-ok` remains the PR merge gate unless the maintainer changes that process.

## GitOps Origin

`threshold-woodpecker-webhook` owns a pinned non-root NGINX proxy in namespace `woodpecker`. Its Service is `woodpecker-webhook:80` (pod port 8080); port 8081 is kubelet-only health and not in the Service. The config has exact Host/method/raw-path checks, no access/error request logging, no API token mounts and a read-only root filesystem. Hashed ConfigMap names restart the proxy after config edits.

Only connector-labelled pods in `cloudflared` can enter it; its egress reaches cluster DNS and the Woodpecker HTTP server only. Server ingress preserves private Traefik HTTP and CI-agent gRPC, adding only the proxy HTTP caller. No generic public Traefik route or direct connector-to-server allow exists.

Run `RUN_WEBHOOK_PROXY_INTEGRATION=1 python3 -m unittest discover -s ops/tests -p test_webhook_proxy.py` for actual pinned-image body/query/header forwarding, denied methods/path aliases/Host and logging checks. This synthetic test does not prove forge delivery.

## Public Exposure

Publish the approved dedicated hostname `hooks.perlimen.com`, with a webhook-only origin boundary:

- Accept only `POST /api/hook` and forward it to the Woodpecker server HTTP Service.
- Reject every other path/method; do not publish the UI, general API, OAuth callback, gRPC agent port, metrics or internal admin services.
- Preserve the request body, signature/event/delivery headers and query parameters exactly. Do not log the hook URL query: Woodpecker can embed its hook token there.
- In v3.15.0 the native GitHub adapter authenticates with a repository-scoped signed hook token in the URL; it does not configure GitHub body-HMAC signatures. `PostHook` validates that token before parsing the body and checks the forge repository ID. Do not claim an `X-Hub-Signature-256` verification that the native integration does not perform. TLS and URL-token secrecy remain required.
- Do not put an interactive Cloudflare Access/SSO challenge in front of forge deliveries. Woodpecker validates forge authentication; do not disable it to make a ping green.
- Leave authenticated product traffic uncached and the private OAuth host unchanged.

The approved origin is the dedicated proxy above, through the existing remotely managed tunnel. Add the public route only after origin readiness; use the exact fields in the Cloudflare runbook. NetworkPolicy is L3/L4, not an HTTP path allowlist; the proxy enforces HTTP scope. Do not relax the connector to arbitrary private services.

## Separate Webhook URL From Private UI

The deployed Woodpecker v3.15.0 supports `WOODPECKER_EXPERT_WEBHOOK_HOST` (see [version-pinned server flags](https://github.com/woodpecker-ci/woodpecker/blob/v3.15.0/cmd/server/flags.go)). For the proposed hostname:

```yaml
server:
  env:
    WOODPECKER_HOST: "https://woodpecker.internal"
    WOODPECKER_EXPERT_WEBHOOK_HOST: "https://hooks.perlimen.com"
```

Woodpecker appends `/api/hook` when creating the forge hook. This keeps the GitHub OAuth callback and private browser UI on their existing host; changing `WOODPECKER_HOST` to the hook-only hostname would break those flows. Add the non-secret setting through `infra/helm/woodpecker/values.yaml` in the same reviewed change as exposure. Verify against the running version again before applying it.

## Repository Identity And Hook Registration

Before repair, compare the Woodpecker `forge_remote_id` with GitHub's current repository ID. A name match or GitHub URL redirect does not prove identity. `repo sync` only refreshes the forge list.

The archived `fbialogrecki/threshold-legacy-private` and public `fbialogrecki/perlimen` are different GitHub repositories after the earlier clean-room replacement. The public source was therefore activated natively as a separate Woodpecker record with maintainer approval. The old record and its pipeline history remain intact; no SQLite edits, history transplant, unregister/re-add or credential rotation were used. Both retain private CI visibility, existing trust settings and fork approval policy.

Native `woodpecker-cli repo repair <repo-id>` reads forge metadata, updates the record, preserves its ID/history and creates an old-name redirection. **It also removes/recreates the forge webhook.** This is not a metadata-only operation; obtain approval even when the generated URL would still point to the private LAN host. Do not edit the Woodpecker SQLite database, unregister/re-add the repository or rotate credentials to work around that coupling. The [v3.15.0 repair implementation](https://github.com/woodpecker-ci/woodpecker/blob/v3.15.0/server/api/repo.go) is the version-specific behavior reference.

For a real rename (same forge ID), use native repair after origin readiness. For the distinct public source, use `woodpecker-cli repo add <verified-forge-id>` with approval; it registers the hook. Read back the exact record and hook with URL queries suppressed. The manual release invocation and trusted release-agent selector now both use `fbialogrecki/perlimen`. Seed manual-event-only credentials using `ops/configure-woodpecker-release-secrets.sh` with the authenticated HTTPS CLI context and correct kubeconfig; verify secret names/event restrictions, never values. See [naming boundaries](../rebranding.md).

## Verification Before Calling It Connected

1. Render the touched infra with `go-task infra:check`, review HTTP and NetworkPolicy scope, then perform only the approved GitOps rollout.
2. Confirm Argo's sync operation succeeded, the relevant apps are Synced/Healthy and the connector is available. Confirm the public endpoint cannot serve UI/API/OAuth/gRPC; test rejected methods/paths and origin-side denials, not just DNS.
3. Inspect the exact registered GitHub hook (never print its token), send/redeliver its real ping, and verify Woodpecker authentication accepts the actual forge request. An unsigned request returning an auth error is not delivery proof.
4. Use an approved harmless real change in a workflow-covered path; verify the matching main push/PR delivery, correct commit/branch and completed non-release pipeline. A docs-only commit may correctly create no workflow due to `when.path` and `on_empty: false`.
5. Confirm there is no release/promotion workflow or access to manual-only release secrets. Retain the suspended poller until native deliveries work; remove it only in a later cleanup.
6. Decide explicitly whether Woodpecker should duplicate GitHub Actions validation or own a selected build gate. Do not silently replace `ci-ok` or turn ordinary merges into production releases.

Public exposure, native hook repair, automatic-release policy and legacy namespace/data migration are distinct approvals. This runbook describes the path; it does not authorize any of them.
