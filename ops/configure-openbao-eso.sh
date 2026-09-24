#!/usr/bin/env bash
set -euo pipefail

OPENBAO_POD="${OPENBAO_POD:-openbao-0}"
OPENBAO_NAMESPACE="${OPENBAO_NAMESPACE:-default}"
ESO_NAMESPACE="${ESO_NAMESPACE:-default}"
ESO_SERVICE_ACCOUNT="${ESO_SERVICE_ACCOUNT:-external-secrets}"
MOUNT_PATH="${MOUNT_PATH:-secret}"
ROLE_NAME="${ROLE_NAME:-external-secrets}"
POLICY_NAME="${POLICY_NAME:-external-secrets-threshold}"

printf "OpenBao root token (input hidden, not stored): " >&2
IFS= read -rs BAO_TOKEN
printf "\n" >&2

if [[ -z "${BAO_TOKEN}" ]]; then
  echo "ERROR: empty token" >&2
  exit 1
fi

kubectl exec -i -n "${OPENBAO_NAMESPACE}" "${OPENBAO_POD}" -- sh <<EOF_INNER
set -eu
export BAO_ADDR="http://127.0.0.1:8200"
export BAO_TOKEN='${BAO_TOKEN}'

# Enable KV v2 if missing.
if ! bao secrets list -format=json | grep -q '"${MOUNT_PATH}/"'; then
  bao secrets enable -path="${MOUNT_PATH}" kv-v2
fi

# Enable Kubernetes auth if missing.
if ! bao auth list -format=json | grep -q '"kubernetes/"'; then
  bao auth enable kubernetes
fi

KUBERNETES_HOST="https://kubernetes.default.svc"
KUBERNETES_CA_CERT="\$(cat /var/run/secrets/kubernetes.io/serviceaccount/ca.crt)"
TOKEN_REVIEW_JWT="\$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)"

bao write auth/kubernetes/config \
  token_reviewer_jwt="\${TOKEN_REVIEW_JWT}" \
  kubernetes_host="\${KUBERNETES_HOST}" \
  kubernetes_ca_cert="\${KUBERNETES_CA_CERT}" \
  disable_iss_validation=true

cat > /tmp/${POLICY_NAME}.hcl <<'POLICY'
path "secret/data/threshold/*" {
  capabilities = ["read"]
}

path "secret/metadata/threshold/*" {
  capabilities = ["read", "list"]
}
POLICY

bao policy write "${POLICY_NAME}" /tmp/${POLICY_NAME}.hcl

bao write auth/kubernetes/role/${ROLE_NAME} \
  bound_service_account_names="${ESO_SERVICE_ACCOUNT}" \
  bound_service_account_namespaces="${ESO_NAMESPACE}" \
  policies="${POLICY_NAME}" \
  ttl="24h"

bao kv put ${MOUNT_PATH}/threshold/eso-smoke value="ok"

echo "OK: OpenBao configured for External Secrets Operator."
EOF_INNER
