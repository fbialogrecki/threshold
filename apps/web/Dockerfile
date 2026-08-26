# syntax=docker/dockerfile:1

# Readable Bun 1 slim tag retained; digest pins the multi-arch index.
FROM docker.io/oven/bun:1.4-slim@sha256:4c3ac64f41e0a47e28403789a63ecdca7987f322fa811bf5b3cb0f25f18443cc AS deps
WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

FROM docker.io/oven/bun:1.4-slim@sha256:4c3ac64f41e0a47e28403789a63ecdca7987f322fa811bf5b3cb0f25f18443cc AS builder
WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN bun --bun next build

FROM docker.io/oven/bun:1.4-slim@sha256:4c3ac64f41e0a47e28403789a63ecdca7987f322fa811bf5b3cb0f25f18443cc AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

COPY --from=builder --chown=bun:bun /app/.next/standalone ./
COPY --from=builder --chown=bun:bun /app/.next/static ./.next/static

USER bun
EXPOSE 3000
CMD ["bun", "server.js"]
