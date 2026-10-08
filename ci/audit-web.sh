#!/bin/sh
set -eu
# Approved ESLint-only DoS exception; the audit becomes strict again on 2026-10-22 UTC.
if [ "$(date -u +%F)" \< "2026-10-22" ]; then
  exec bun audit --ignore=GHSA-vfj7-8cjw-p6xm
fi
exec bun audit
