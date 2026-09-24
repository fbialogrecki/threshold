# Threshold Web

Next.js app for Threshold, run with Bun by default.

## Default Bun workflow

Run all commands from the repository root through `Taskfile.yml`:

```bash
go-task web:install
go-task web:dev
go-task web:lint
go-task web:typecheck
go-task web:test
go-task web:build
```

Equivalent commands from `apps/web`:

```bash
bun install
bun --bun next dev
bun run lint
bunx tsc --noEmit
bun test
bun run build
```

Open http://localhost:3000 after starting the dev server.

## Environment

Copy `.env.example` to `.env.local` before running the dev server. Auth runs
against the product-auth `users` service through a same-origin BFF
(`/api/auth/*`, `/api/me`) — there is no Authentik/NextAuth on the public path.

- `USERS_SERVICE_URL` — server-only base URL of the `users` service. Point it at
  a reachable `users` instance (in-cluster Service DNS, or a port-forward like
  `http://127.0.0.1:8000` for local dev).
- `SOCIAL_SERVICE_URL` — server-only base URL of the `social` service (feed,
  groups, posts, comments, reactions).
- `THRESHOLD_INTERNAL_TOKEN` — shared secret the BFF sends to `social` as
  `X-Threshold-Internal-Token`; `social` validates it before trusting the
  `X-Threshold-User-Id` header.
- `AUTH_COOKIE_SECURE` — `false` on plain http, `true` behind https.

All product surfaces (feed, profiles, pages, groups, search) read live from the
`users` and `social` services — there is no mock data source. Event/guestlist
surfaces show honest "coming soon" states until the events service (Slice 4)
lands.

Password reset and email verification tokens are never returned to the browser;
in dev, read them from the `users` server logs / direct API responses (there is
no mail sender in MVP).

## pnpm fallback plan

Bun stays the default package manager and runtime. Use pnpm only as an emergency fallback when Bun package installation or Bun's Next.js runtime blocks local work.

### Trigger conditions

Switch to the pnpm fallback only when one of these happens:

- `bun install` fails on a valid dependency tree.
- `bun --bun next dev` or `bun run build` hits a Bun-specific runtime/tooling regression.
- A dependency requires npm lifecycle behavior that Bun cannot run correctly yet.

Do not switch just because pnpm is familiar. The project default remains Bun.

### Fallback steps

From `apps/web`:

```bash
corepack enable
corepack prepare pnpm@latest --activate
pnpm install
pnpm exec next dev
pnpm exec next build
pnpm exec eslint
pnpm exec tsc --noEmit
```

If `pnpm exec next dev` still fails but dependency installation with pnpm fixed the issue, run the scripts through Bun while keeping the pnpm-installed `node_modules`:

```bash
pnpm install
bun run dev
bun run build
bun run lint
bunx tsc --noEmit
```

### Rules while fallback is active

- Keep `bun.lock` as the canonical lockfile unless the team explicitly decides to migrate.
- Do not commit `pnpm-lock.yaml` for a temporary local fallback.
- If pnpm becomes required in CI or production, write a plain-language decision note first and update `Taskfile.yml` in the same change.
- After the Bun issue is gone, remove `node_modules`, run `bun install`, and verify `go-task web:lint`, `go-task web:typecheck`, `go-task web:test`, and `go-task web:build` again.
