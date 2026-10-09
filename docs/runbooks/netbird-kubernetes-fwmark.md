# NetBird and Kubernetes packet marks

## Why this host needs an override

NetBird 0.80.0 defaults to fwmark base `0x1bd00`. Its routed-pod mark `0x1bd22` includes kube-router's `0x10000` policy-permitted bit, as well as kube-proxy's masquerade bits. On this NUC, NetBird advertises the pod CIDR and marks traffic from it before kube-router evaluates NetworkPolicy. A web-only connector pod could therefore connect to `1.1.1.1:443` despite its egress allowlist. Internal destination ingress rules still blocked the tested private services; that did not prove egress isolation.

Use NetBird's supported `NB_FWMARK_BASE=0x10000000` to relocate the entire range to `0x10000000–0x100000ff`. The new range does not overlap kube-router's `0x10000`/`0x20000` or kube-proxy's `0x2000`/`0x4000`. This keeps NetBird firewalling and advertised routes enabled. It does not replace Kubernetes NetworkPolicy or change the CNI.

References: [NetBird environment variables](https://docs.netbird.io/client/environment-variables), [upstream collision report](https://github.com/netbirdio/netbird/issues/6022), and `client/net/fwmark.go` in the deployed NetBird version.

## Apply on the NUC

This is host configuration, not a Kubernetes resource. Explicit maintainer approval is required: restarting NetBird briefly interrupts VPN access. Use a local/LAN maintenance connection, not one that depends solely on NetBird. Check that no existing systemd override sets a different base and that the proposed range is unused before installing.

From the repository root:

```bash
sudo install -D -m 0644 ops/netbird-kubernetes-fwmark.conf \
  /etc/systemd/system/netbird.service.d/20-kubernetes-fwmark.conf
sudo systemctl daemon-reload
sudo systemctl restart netbird
sudo systemctl is-active netbird
sudo netbird status
sudo ip -4 rule show
sudo ip -6 rule show
```

The drop-in leaves the base unit, `NB_FORCE_RELAY`, profiles, keys and routes untouched. Graceful shutdown should remove the old policy-routing rule before the new process creates one for `0x10000000`. Verify the exact installed drop-in and running daemon environment, not just the install exit code.

If the old `not ... fwmark 0x1bd00 lookup 7120 priority 110` rule remains after an unclean shutdown, inspect it first. Remove only that exact obsolete NetBird rule, for each family where it actually exists; do not flush routing or firewall tables. See the upstream environment-variable documentation for the exact deletion command.

## Verification

- Management and signal reconnect; previously available relay paths stay available.
- Existing advertised networks are unchanged. A connected remote peer must exercise its actual LAN/cluster access path; a daemon status alone does not prove remote reachability.
- Live routing and NetBird firewall rules use the new range, with no old `0x1bd00` rule or `0x1bd2*` packet marks left behind.
- From a connector-labelled pod, DNS, Service/web and Cloudflare TCP 7844 work; Traefik, OpenBao, users, node HTTPS and `1.1.1.1:443` fail. Test after observing the pod's kube-router rules, not merely after Pod Ready.
- A pod without the connector label cannot reach web.
- Existing LAN web HTTPS still returns 200; unrelated app deployments stay ready.

Do not declare the tunnel ready until its separate token, connector and public-HTTPS gates pass. NetworkPolicy does not cover privileged/hostNetwork access or every node-local/SNAT path; remote NetBird authorization remains a host/network responsibility.

## Rollback

If reconnect or route verification fails, remove only `/etc/systemd/system/netbird.service.d/20-kubernetes-fwmark.conf`, reload systemd and restart NetBird gracefully. Verify the previous range and control-plane connectivity are restored. This restores the pre-existing mark collision, so keep the public tunnel inactive until a working non-overlapping configuration is verified. Do not disable either firewall as a workaround.
