# OpenBao Unseal

OpenBao (`openbao-0` in namespace `default`) starts sealed after every host reboot or pod restart. While it is sealed, External Secrets Operator cannot refresh secrets, and anything that needs a new or rotated secret fails.

Unsealing is manual on purpose. The unseal keys are never stored on the server, and there is no boot-time job with stored machine credentials. A human runs one script after a reboot.

## How The Script Gets The Keys

1. The personal Bitwarden CLI (`bw`) is unlocked, prompting for the master password on the terminal if needed.
2. The Bitwarden Secrets Manager access token is read from a personal Bitwarden item.
3. Bitwarden Secrets Manager (`bws`) returns the unseal key secrets.
4. The keys go to OpenBao through a local `kubectl port-forward`, one at a time, until OpenBao reports unsealed.
5. ESO is forced to revalidate `ClusterSecretStore/openbao` and every `ExternalSecret` using it.

The Bitwarden account, server URL, item and field names, and BWS secret names are set in `ops/local.env` (git-ignored). This document refers to them only as "the Bitwarden items named in `ops/local.env`".

## Prerequisites

- `bw` and `bws` on `PATH`, `kubectl` with access to the cluster.
- `ops/local.env` with the Bitwarden settings. Copy `ops/local.env.example` and fill in every placeholder; variables set in the environment override the file.
- The Bitwarden master password.

## Procedure

1. Check the pod:

   ```bash
   kubectl -n default get pod openbao-0
   ```

   `0/1 Running` usually means sealed.

2. Optionally validate Bitwarden access without touching OpenBao. This checks that the BWS token and all unseal secrets are readable and prints no values:

   ```bash
   BWS_VALIDATE_ONLY=true ops/openbao-manual-unseal-from-bitwarden.sh
   ```

3. Unseal:

   ```bash
   ops/openbao-manual-unseal-from-bitwarden.sh
   ```

   If the pod is already ready, the script only refreshes ESO. Otherwise it submits keys until OpenBao reports unsealed, then refreshes ESO.

4. Verify:

   ```bash
   kubectl -n default exec openbao-0 -- bao status
   kubectl get clustersecretstore openbao
   kubectl get externalsecret -A
   ```

   `Sealed` must be `false`, the store `Valid`, and every `ExternalSecret` `SecretSynced`.

## Overrides

Set these in the environment or in `ops/local.env`:

| Variable | Default | Purpose |
|---|---|---|
| `OPENBAO_NAMESPACE` / `OPENBAO_POD` | `default` / `openbao-0` | Target pod |
| `OPENBAO_LOCAL_PORT` | `18200` | Local port-forward port |
| `OPENBAO_UNSEAL_THRESHOLD` | `3` | Number of keys to submit |
| `BWS_PROJECT_ID` | empty | Limit lookups to one BWS project |
| `BWS_VALIDATE_ONLY` | `false` | Check access only |
| `BW_LOCK_AFTER_RUN` | `true` | Lock `bw` afterwards if the script unlocked it |
| `ESO_FORCE_REFRESH_AFTER_UNSEAL` | `true` | Force ESO refresh after unseal |
| `ESO_CLUSTER_SECRET_STORE_NAME` | `openbao` | Store to refresh |

## Cleanup And Limits

On exit the script stops the port-forward, locks the `bw` session it opened, and unsets the master password, session key, BWS token and key values in its own process. It cannot clear variables that were already exported in the calling shell, so do not export any of them by hand.

## Safety

- Never commit or paste unseal keys, the root token, the BWS access token, `bw` session keys or vault exports.
- Keep the BWS machine account limited to the secrets this script needs.
- Do not turn this into a boot-time service unless storing machine-readable Bitwarden credentials on the server is an explicit, accepted choice.
- The script changes nothing in the cluster except OpenBao's sealed state and ESO refresh annotations.
