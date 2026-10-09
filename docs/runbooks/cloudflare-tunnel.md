# Cloudflare Tunnel

## Ownership and scope

- Public application hostname: `perlimen.com` (Cloudflare-managed DNS).
- Connector: `Deployment/cloudflared` in namespace `cloudflared`, owned by Argo CD `threshold-cloudflared`.
- Origin: `http://web.threshold.svc.cluster.local:80`, not private Traefik.
- Token: OpenBao KV v2 mount `secret`, key `threshold/cloudflared`, property `token`; ESO creates `Secret/cloudflared-token` in namespace `cloudflared`.
- One replica on the single NUC; rolling updates can temporarily run two. This is not host-level high availability.
- No public admin, backend API, guestlist subdomain, webhook, wildcard or private-network routes. The web BFF already provides the browser API boundary.
- TLS terminates at Cloudflare; the connector-to-edge transport is encrypted. The connector-to-web hop is HTTP inside this single-node cluster, bounded by NetworkPolicy. LAN HTTPS remains unchanged.

The image is pinned to `2026.10.0` and a digest. Automatic updates and optional Internet prechecks are disabled; required tunnel connections still run normally. Egress is limited to cluster DNS, web pods on TCP 3000 and Cloudflare's global IPv4 tunnel edge networks (`198.41.192.0/24`, `198.41.200.0/24`) on TCP/UDP 7844. Re-check [Cloudflare's firewall destinations](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/tunnel-with-firewall/) on upgrades. There is no ingress Service for connector metrics; kubelet probes use the pod directly.

## Create the remotely managed tunnel

1. Verify that `perlimen.com` is Active in Cloudflare.
2. In Cloudflare **Networking → Tunnels**, create a Cloudflared tunnel named `perlimen-nuc`.
3. Select Docker and copy only the token from the generated command. Do not run the command: GitOps owns the connector.
4. Do not add a published route until the connector is healthy.
5. Keep the token in the maintainer's password manager and OpenBao; never in chat, shell arguments/history, git, PRs or Kanban.

## Unseal and seed OpenBao

OpenBao requires manual unseal after a restart. On the NUC, from the repository root:

```bash
KUBECONFIG="$HOME/.kube/config" ops/openbao-manual-unseal-from-bitwarden.sh
KUBECONFIG="$HOME/.kube/config" kubectl get clustersecretstore openbao
```

The helper prompts locally for Bitwarden access and refreshes ESO. Do not send the master password or unseal keys to an agent.

In the private OpenBao UI at `https://openbao.internal`, select KV mount `secret`, create `threshold/cloudflared`, and set property `token` to the tunnel token. Use an existing authorized operator login; do not rotate credentials as part of this setup.

Wait for the secret and connector:

```bash
export KUBECONFIG="$HOME/.kube/config"
kubectl -n cloudflared annotate externalsecret cloudflared-token force-sync="$(date +%s)" --overwrite
kubectl -n cloudflared wait --for=condition=Ready externalsecret/cloudflared-token --timeout=120s
kubectl -n cloudflared rollout status deployment/cloudflared --timeout=180s
kubectl -n cloudflared get pods
```

A missing token leaves the pod waiting for its required Secret volume: there is no fallback credential. A sealed OpenBao or a missing KV property keeps the ExternalSecret NotReady. Never bypass ESO with an ad-hoc Kubernetes Secret.

Check the Cloudflare dashboard for a healthy connector. Inspect logs locally at `info`, never `debug`: debug output can contain request headers/tokens. After a token rotation, wait for ESO Ready, then explicitly restart only this Deployment; updating the volume does not make the process re-read the token.

## Publish only the application

In the tunnel's **Routes → Add route → Published application**:

- Hostname: `perlimen.com` (empty subdomain, domain `perlimen.com`).
- Path: empty.
- Service type: HTTP.
- URL: `web.threshold.svc.cluster.local:80`.
- HTTP Host Header: `perlimen.com`.
- No private-network route, wildcard hostname or admin hostname.

The dashboard creates the proxied tunnel DNS record. Resolve an existing conflicting apex record deliberately; do not delete unrelated mail/DNS records.

Enable **Always Use HTTPS** for the application hostname (use a hostname-scoped redirect if other zone hosts need HTTP). Keep application routes uncached: do not enable Cache Everything/APO for authenticated pages or `/api/*`. No Cloudflare Access login is required for the public product; product auth remains in `users`.

The web deployment retains `AUTH_COOKIE_SECURE=true`, `WEB_TRUSTED_LAN_HTTP=false` and `WEB_TRUSTED_PROXY_DEPTH=1`. Direct tunnel routing uses the Cloudflare-controlled rightmost forwarded client address without an extra Traefik hop. Leave visitor-IP removal transforms disabled. Verify rate limiting with the actual public path before broad use; do not blindly increase the trusted proxy depth.

## Verification and completion

Before activation, apply and verify the host's [NetBird mark-range override](netbird-kubernetes-fwmark.md). The default range collides with kube-router policy bits on this NUC and can bypass the connector's egress allowlist. A NetworkPolicy manifest or blocked private-service probe alone is not sufficient evidence.

```bash
kubectl -n argocd get application threshold-cloudflared
kubectl -n cloudflared get externalsecret cloudflared-token
kubectl -n cloudflared get deployment cloudflared
curl --fail --silent --show-error --max-time 20 https://perlimen.com/ -o /dev/null
curl --silent --show-error --max-time 20 -D - https://perlimen.com/app -o /dev/null
curl --silent --show-error --max-time 20 -D - http://perlimen.com/ -o /dev/null
```

Require all of:

- Argo sync operation succeeded and app is Synced/Healthy.
- ExternalSecret Ready and Deployment available; tunnel healthy in Cloudflare.
- HTTPS landing returns 200; anonymous protected routes do not disclose authenticated content; HTTP redirects to HTTPS.
- Product login/session behavior is exercised with a disposable account once email provisioning is complete; cookies stay Secure/HttpOnly.
- Network smoke from a pod with the connector's namespace/labels reaches web and Cloudflare TCP 7844, while Traefik, OpenBao, users and arbitrary Internet egress fail. A label-free pod must not gain web access.
- No private/admin hostname or private-network route is configured in this tunnel.

A merged manifest is not proof of a connected tunnel or working public route. Keep the Kanban card open until the live and public gates pass.

## Resend API key

Resend email provisioning is separate from tunnel activation. Verify the sender domain in Resend using the DNS records it provides; mail-only records must remain DNS-only, not proxied. Create a domain-scoped **Sending access** API key.

In OpenBao KV mount `secret`, key `threshold/users/email`, set these string properties:

| Property | Value |
| --- | --- |
| `THRESHOLD_SMTP_ENABLED` | `true` |
| `THRESHOLD_SMTP_USERNAME` | `resend` |
| `THRESHOLD_SMTP_PASSWORD` | the Resend API key |
| `THRESHOLD_SMTP_FROM` | a sender authorized by the verified domain, e.g. `no-reply@perlimen.com` |
| `THRESHOLD_WEB_HOST` | `perlimen.com`, without a scheme or path |

The existing ConfigMap selects `smtp.resend.com:587`, STARTTLS and a 10-second timeout. Do not disable TLS verification.

`ExternalSecret/users-email` materializes these five properties, and the users Deployment reads it through optional `envFrom`. The email ExternalSecret synchronizes before the rollout; a missing or incomplete OpenBao record keeps that sync wave blocked without replacing the running users pod. If an existing pod started before the Secret existed or after credentials changed, wait for ESO Ready and restart only users to reload its environment.

```bash
kubectl -n threshold annotate externalsecret users-email force-sync="$(date +%s)" --overwrite
kubectl -n threshold wait --for=condition=Ready externalsecret/users-email --timeout=120s
kubectl -n threshold rollout status deployment/users --timeout=180s
```

Require real register → verify → password-reset → login delivery smoke before closing the Resend card. ESO readiness, a healthy pod or SMTP authentication alone does not prove message delivery or working links.
