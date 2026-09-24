#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="${NAMESPACE:-threshold}"
SECRET_NAME="${SECRET_NAME:-media-s3}"
JOB_NAME="${JOB_NAME:-media-s3-bucket-bootstrap}"
AWS_CLI_IMAGE="${AWS_CLI_IMAGE:-amazon/aws-cli:2.15.57}"
TIMEOUT="${TIMEOUT:-180s}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "ERROR: kubectl is required" >&2
  exit 1
fi

kubectl -n "${NAMESPACE}" get secret "${SECRET_NAME}" >/dev/null
kubectl -n "${NAMESPACE}" delete pod "${JOB_NAME}" --ignore-not-found --wait=true >/dev/null

cat <<YAML | kubectl -n "${NAMESPACE}" apply -f - >/dev/null
apiVersion: v1
kind: Pod
metadata:
  name: ${JOB_NAME}
  labels:
    app.kubernetes.io/name: media
    app.kubernetes.io/component: s3-bucket-bootstrap
    app.kubernetes.io/part-of: threshold
spec:
  restartPolicy: Never
  containers:
    - name: aws-cli
      image: ${AWS_CLI_IMAGE}
      imagePullPolicy: IfNotPresent
      envFrom:
        - secretRef:
            name: ${SECRET_NAME}
      command:
        - /bin/sh
        - -c
        - |
          set -eu
          export AWS_ACCESS_KEY_ID="\${S3_ACCESS_KEY_ID}"
          export AWS_SECRET_ACCESS_KEY="\${S3_SECRET_ACCESS_KEY}"
          endpoint="\${S3_ENDPOINT_URL:?missing S3_ENDPOINT_URL}"
          bucket="\${S3_BUCKET:?missing S3_BUCKET}"
          region="\${S3_REGION:-us-east-1}"
          if aws --endpoint-url "\${endpoint}" s3api head-bucket --bucket "\${bucket}" >/dev/null 2>&1; then
            echo "OK: bucket exists"
            exit 0
          fi
          aws --endpoint-url "\${endpoint}" s3api create-bucket --bucket "\${bucket}" --region "\${region}" >/dev/null
          aws --endpoint-url "\${endpoint}" s3api head-bucket --bucket "\${bucket}" >/dev/null
          echo "OK: bucket created"
YAML

kubectl -n "${NAMESPACE}" wait --for=condition=Ready "pod/${JOB_NAME}" --timeout="${TIMEOUT}" >/dev/null || true
kubectl -n "${NAMESPACE}" wait --for=jsonpath='{.status.phase}'=Succeeded "pod/${JOB_NAME}" --timeout="${TIMEOUT}" >/dev/null
kubectl -n "${NAMESPACE}" logs "pod/${JOB_NAME}"
kubectl -n "${NAMESPACE}" delete pod "${JOB_NAME}" --wait=true >/dev/null
