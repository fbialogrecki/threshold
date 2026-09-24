# Threshold Agent Guide

Threshold is a social and event-discovery platform for the music scene. The MVP proves the community, profiles, groups, public event pages, media pipeline, and moderation loop before ticketing, payments, mobile apps, DMs, or recommendation systems.

This file is the active project briefing for coding agents: product scope, architecture rules, and implementation guidance. Keep it concise and update it in the same change that alters a convention.

## How To Use This File

- Treat `AGENTS.md` like code: keep it current and under 20k characters. Prefer exact commands over prose.
- Put durable project guidance here. How the system fits together is described in `docs/architecture.md`; when a technical choice changes, update that description in the same PR. Scratch implementation notes go in `docs/plans/`, which git ignores.
- The nearest nested `AGENTS.md` also applies. For `apps/web`, read `apps/web/AGENTS.md` before touching Next.js code.

## Repository Shape

```text
apps/web/                 Next.js app, Bun runtime/package manager
services/auth-gateway/    Internal/admin SSO edge pattern and health checks
services/users/           Product auth, sessions, profiles, pages, follows, canonical blocks
services/social/          Groups, posts, comments, votes, emoji, feed, safety
services/media/           Image upload, validation, SeaweedFS/S3, WebP derivatives
services/events/          Event CRUD, public event read model, follow, boost
libs/py/                  Shared Python helpers
infra/                    Kustomize, Helm values, ArgoCD app-of-apps (ArgoCD tracks main)
ops/                      Operator scripts: secret seeding, token rotation, backups
docs/                     Architecture, release/deploy flow, runbooks
graphify-out/             Generated code graph (ignored)
```

## Source Of Truth

- `Taskfile.yml` is the local and CI command contract.
- This repository is the only one. `main` is both code history and ArgoCD desired state (`infra/`). Secrets live in OpenBao/ESO and Bitwarden, never in git; private operator values live in the ignored `ops/local.env`.
- ArgoCD + Kustomize/Helm own local Kubernetes resources. Manual `kubectl apply` is only for reviewed bootstrap or emergency recovery.
- Each deployable app should have one ArgoCD application or generated ApplicationSet entry.
- Adopted Helm releases are managed by ArgoCD. Do not use `helm upgrade` on them unless a runbook explicitly says so.

## Commands

Run from the repository root; `go-task --list` shows everything.

```bash
go-task check                               # lint, typecheck, test, build
go-task web:lint | web:typecheck | web:test | web:build
go-task py:lint | py:typecheck | py:test
go-task service:test SERVICE=users          # also service:lint, service:dev
go-task infra:check                         # render every kustomization, reject inline Secret data
go-task repo:secret-scan
graphify update .                           # after modifying code files
```

Live infra mutation needs explicit approval and a narrow reason. The CNPG restore gate (a backup plus a disposable restore cluster) is only for backup/data-sensitive work, run with explicit approval. Operator scripts are in `ops/`; after changing `ops/backup/` or `ops/cnpg-restore-gate.sh`, run `go-task ops:backup:install` so cron runs the new copy.

## Stack

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, Bun.
- Backend: Python 3.13, FastAPI, async where useful, SQLAlchemy/Alembic, Ruff, mypy.
- Messaging: NATS Core request/reply and pub/sub. JetStream is deferred until a feature truly needs durable delivery.
- Contracts: JSON over HTTPS for browser-facing APIs and JSON over HTTP/NATS between services.
- Data: PostgreSQL via CloudNativePG. Each service owns its database or schema.
- Object storage: SeaweedFS S3-compatible API. Backend owns buckets and object keys.
- Secrets: OpenBao + External Secrets Operator. No plaintext secrets in git.
- Observability: OpenTelemetry, Loki, Grafana, Tempo, Mimir, Grafana Alloy, OTel Collector.
- CI/CD: GitHub Actions validates PRs (`ci-ok` is the gate). A release is `go-task release VERSION=vX.Y.Z`: it tags `main` and starts the Woodpecker `release` pipeline, which pushes images to Harbor and opens a digest PR against `infra/`; ArgoCD syncs once it merges. See `docs/release-and-deploy.md`.

## Product Rules

- Anonymous access is limited to the landing, login/register, password reset, email verification, and privacy routes plus direct event (`/events/[slug]`), user profile (`/u/[username]`), and Page profile (`/pages/[slug]`) detail routes.
- Feed, all `/app/*` routes, the event catalog (`/events`), groups, post permalinks, and prototypes require a product session.
- Login is required for interactions: follow, join, post, comment, vote, boost, upload, report, block, manage.
- Product auth is custom email/password auth in `users`, exposed through the web BFF. Authentik is only for infra/internal/admin SSO.
- Feed is named **Feed** (not Wall or Signal) and is chronological in MVP. Do not add algorithmic ranking, ML recommendations, or fake popularity metrics.
- A Focus Feed (one card per viewport, explicit next/previous, expandable discussion, compact-list toggle) may be compared with the chronological list. It must stay opt-in or easily switchable and never become autoplay, opaque ranking, or an infinite loop.
- Do not show fake live data. Use real backend data, an honest empty state, or hide the metric.
- Boost is social support, not RSVP and not paid promotion.
- Public identity is exactly one name per person: the unique registration username, rendered without an `@` prefix and in the case its owner typed. `display_name` is retired from user-facing surfaces; Pages keep their own display name and slug because they are entities, not people. Do not expose real-name fields as public social identity.
- Usernames allow `A-Za-z0-9_.-` plus Polish diacritics, 3–30 characters. Keep the set explicit; never widen it with `\w` or `\p{L}`, which would admit Cyrillic and Greek lookalikes.
- Username uniqueness folds case *and* diacritics, so `Żaba` and `Zaba` cannot coexist. That normalisation lives only in `services/users/src/users/domain/identity.py`. Email normalisation must not fold diacritics.
- `@` is how a mention is typed, not how it reads: resolved mentions render as the bare name.
- GDPR is a hard constraint: minimize data, delete or anonymize personal data, preserve public thread integrity where appropriate.
- No third-party trackers. Analytics, if added, must be self-hosted and privacy-aware.

## MVP Domain

Users and profiles:

- `users` owns product accounts, credentials, sessions, email verification, password reset, onboarding, Consumer/Artist profiles, Pages, PageMembership, follows, the canonical account-level block registry, public profile read models, and account deletion/anonymization.
- Page roles are `owner`, `admin`, `editor`. Enforce roles in the backend, not only UI.

Social:

- `social` owns official groups, group membership, text posts, comments, replies up to two levels, post/comment up/down votes, post emoji reactions, chronological feed, reports, and social interaction enforcement for blocks. Do not create a third block source of truth; if `social` stores block rows, treat them as enforcement/projection data for social flows.
- A post may optionally link to an event.
- Mentions of users/profiles/pages should become links and notification sources when the notification spine exists.

Media:

- `media` owns image validation, object storage writes, and WebP derivatives.
- Valid contexts include avatars, page avatars, event posters, and implemented post-image flows.
- Never accept user-controlled bucket names or object keys.

Events:

- `events` owns event CRUD, Page Admin/Editor authorization, event posters by `MediaAsset`, anonymous public read model, public SSR pages, Open Graph data, follow, and boost.
- Canonical location modes are `public_location`, `tba`, and `secret_location`. `secret_location` remains reserved for event create/update until the encrypted exact-location reveal slice lands. Guestlist/QR access exists without enabling plaintext secret-location storage.
- Secret-location address and instructions are client-side encrypted for authorized users/devices; the backend keeps metadata only, never the plaintext location. Revoking access cannot un-reveal a location, so do not pretend it does.
- Guestlists are private, never a public application flow: no "request access", "join guestlist", public invite codes, or guestlist discovery UX. Organizers/Page Admins add and remove guests (who get a notification and their own access view); each line-up artist adds guests up to an organizer-set per-event quota, enforced server-side and audited.
- Check-in: the guest shows a QR that is a short-lived, opaque, server-verified token bound to user, event, entitlement and expiry, with no PII, location or static IDs. Only the organizer or authorized door staff get the check-in view, which shows minimal confirmation (status, username, avatar, check-in state). It proves account control, not legal identity.

Notifications and discovery:

- Notifications exist for the current MVP interaction flows. New sensitive flows, especially encrypted secret-location reveal, must add explicit notification events and preferences when implemented.
- Search should cover artists, clubs/pages, collectives, events, and groups. Use Postgres full-text search before adding an external search engine.
- Discovery favors followed content, chronological context, and search over algorithmic feeds.
- In Focus Feed, scrolling inside an expanded post must not advance to the next post; keep feed navigation separate from reading state.

## Current MVP Status

The local technical MVP is live on the NUC: `web`, `auth-gateway`, `users`, `social`, `media`, `events` plus the platform (Woodpecker, Harbor, ArgoCD, CNPG backups, OpenBao/ESO, LGTM). Product auth, media, events, guestlists/QR check-in, report/block, notifications, mentions, unified feed and search are implemented. Encrypted exact-location reveal for `secret_location` is deliberately post-MVP; create/update still rejects it.

Open MVP gates:

1. `users-email` wiring: `infra/` has the SMTP ConfigMap values but no `ExternalSecret/users-email` or Deployment reference. Restore it, then the maintainer seeds OpenBao and verifies real register/verify/reset delivery.
2. The maintainer runs the disposable-account product-auth smoke. Internal admin SSO QA waits for trusted HTTPS on the Authentik chain.
3. Confirm web memory stays stable (the earlier recurring OOM) before calling the cluster clean.

Do not pull post-MVP work into the MVP unless the user explicitly changes scope.

## Non-Goals

- No ticketing, split payments, paid promotion, creator monetization, or settlement in MVP.
- No DMs, stories, friend graph, algorithmic feed, user-created groups, mobile app, PWA, or public self-serve guestlist application flow.
- No separate admin panel unless a concrete role workflow forces it.
- No service mesh, saga framework, multi-cloud, or managed-only replacement for core OSS infrastructure.
- No new dependency because it is familiar. Use standard library, platform APIs, or existing project patterns first.

## Service Boundaries

- No cross-service database joins.
- Service-owned data stays behind that service's API, NATS contract, or published event.
- Shared code belongs only in `libs/py` when duplication is actually painful.
- Python services should follow the existing FastAPI layout: `main.py`, `settings.py`, `api/`, `domain/`, `db/`, `messaging/`, `telemetry.py`, and `migrations/` inside the package, plus a service-level `tests/`.
- Every service exposes `GET /healthz` and `GET /readyz`.
- Domain authorization belongs in the owning service. Gateways may authenticate, but services make access decisions.

## Frontend Rules

- Use functional React components and local helpers already present in `apps/web`.
- Prefer native web APIs and Tailwind over new UI libraries.
- Keep the brutalist dark UI language: access-first, terminal-like, color indicates state/function rather than decoration.
- Panel surfaces carry no fills: the page is `pitch`, every boundary is one `border-border-gray` rule, and hierarchy comes from rules, indentation, spacing and type. `bg-graphite`/`bg-raised` survive only on auth surfaces and the `PublicShell` header.
- One meaning per hue: `acid` affirms (primary action, active nav, upvote), `violet` is the vote axis only (downvote), `orange` flags something incomplete, protection reads as full-contrast text plus a padlock, `error` is destructive only. `cyan` is retired from status use and public surfaces.
- Size display type against its container (`@container` + `cqi`), never the viewport: the capped page column makes `vw` overflow. No `clamp()` minimum; a `min(…, vh)` arm is fine.
- Atmosphere (wash, grid, scanlines, grain) is allowed only in the landing hero band, above the threshold rule.
- `color-scheme: dark` is set on `html`. The product is dark-only; do not add light-mode affordances.
- Tailwind order can defeat `focus:` variants (`sr-only` beats `focus:not-sr-only`). Write focus-revealed elements such as the skip link as unlayered CSS in `globals.css`; verify with `CSS.forcePseudoState`, because an unfocused tab never matches `:focus`.
- Type roles: `font-display` is Archivo 700 uppercase for entity titles and is set globally in `globals.css`; author names are sans 600 in natural case and must not use it; mono is for labels, metadata, actions and statuses at 10/11/12px; human content and error messages are sans.
- The feed is a full-bleed stream: rows separated by one rule, no cards, action row as one flex row at every width with navigation left and evaluation right.
- A panel route keeps a visible title only where it names something the navigation does not. Routes that drop it keep an `sr-only` heading.
- Public event, user profile, and Page profile detail routes must keep SSR and Open Graph behavior.
- Same-origin BFF routes are the preferred browser boundary for backend calls that need cookies or internal tokens.
- For Next.js work, read `apps/web/AGENTS.md`; this version may differ from model memory.
- Bun is the default. Use the pnpm fallback in `apps/web/README.md` only for a real Bun blocker.

## Backend Rules

- Use Python 3.13 typing and keep `mypy` strict clean.
- Prefer simple FastAPI routes and domain functions over framework-heavy abstractions.
- Keep migrations inside the package at `services/<svc>/src/<pkg>/migrations` so they ship in the wheel. Address them as `<pkg>:migrations`, never via `__file__` or the working directory: the image installs with `--no-editable`, so the service directory does not exist at runtime.
- Every `migrate.py` is identical apart from the package name and builds its Alembic `Config` in code; `alembic.ini` is for the CLI only, so logger levels live in `migrate.py`.
- Migration Jobs run `python -m <svc>.migrate`. `uv` is build-time only (the app user cannot write `HOME`); the venv is first on `PATH`.
- A failed migration hook must stay loud. GitOps keeps the failed Job (`hook-delete-policy: HookSucceeded`, without `BeforeHookCreation`), which turns the application Degraded and blocks the next sync until someone looks. An application can report Synced/Healthy while its sync operation failed, so never treat those two columns as proof that migrations ran.
- Use Postgres for relational work. Do not move joins or filtering into Python when SQL is the right tool.
- Use NATS request/reply for synchronous internal calls and pub/sub for non-critical events.
- For critical events that must not be lost, design transactional outbox + retry + idempotent consumers before relying on NATS Core.
- Do not log secrets, tokens, password hashes, reset tokens, or private location payloads.
- Deploy pitfalls: ConfigMaps load via `envFrom` without a hash, so a ConfigMap-only change needs `kubectl -n threshold rollout restart deploy/<svc>`. A CNPG `Cluster` spec change restarts the DB and can race the migrate hook; delete the failed hook Job before re-syncing. Every service has a NetworkPolicy, so a new HTTP caller must be added to the callee's policy (a missing entry looks like a timeout).

## Security And Secrets

- Never commit `.env` files, credentials, private keys, tokens, or rendered secrets.
- `.env.example` may contain names and dummy values only.
- Product passwords use Argon2id with project-controlled parameters and a pepper from OpenBao.
- Sessions use HttpOnly Secure SameSite cookies and server-side hashed token material.
- Internal shared tokens must stay server-side and come from OpenBao/ESO.
- SeaweedFS/S3 credentials are backend-only. Browsers never receive direct S3 credentials.
- QR check-in tokens must be short-lived, opaque, revocable, audience-scoped to check-in, and validated server-side. Do not use static QR codes or encode raw user/event IDs as proof.
- If a task touches auth, sessions, password reset, secret-location encryption, or secrets, add tests and call out residual risk.

## Testing And Definition Of Done

Match verification to risk. For small docs-only edits, a diff review may be enough. For code, run the narrowest useful gate plus any affected service or web tests.

Expected gates:

- Web change: `go-task web:lint`, `go-task web:typecheck`, `go-task web:test`; add `go-task web:build` when routing, metadata, or build config changes.
- Python service change: `go-task service:lint SERVICE=<name>`, `go-task service:test SERVICE=<name>`, plus `go-task py:typecheck` for typed shared impact.
- Cross-service contract change: tests of both the producing and consuming service, plus web tests if the BFF is affected.
- Infra change: `go-task infra:check`. A new variable in a service `Settings` needs its ConfigMap or ExternalSecret entry in the same PR.
- Data or backup-sensitive change: include migration smoke; run the CNPG restore gate only when explicitly approved.

Before calling work done:

- Tests relevant to the touched surface pass or the reason they were not run is stated.
- No unrelated refactors or formatting churn.
- No new fake data, secrets, or hidden product scope expansion.
- Public/anonymous behavior remains correct for public pages.
- `AGENTS.md` is updated if the change alters project rules, commands, or active scope.

## Agent Behavior

- Be conservative and local. Follow existing patterns before inventing a new abstraction.
- Ask before destructive infra operations, secret rotation, live cluster changes, schema rewrites, or scope expansion.
- Do not overwrite user changes or unrelated dirty files.
- Do not add broad compatibility shims for unshipped branch work; replace in-progress code cleanly when asked.
- Keep comments rare and explain why, not what.
- If a recurring agent mistake happens, fix this file rather than relying on chat memory.
- Work in short PRs, one concern each, merged with `gh pr merge --auto --squash` once CI is green. Do not start multi-package programs or master plans without explicit approval.
- Never run `go-task release` or `woodpecker-cli pipeline create` unless the maintainer explicitly asks for that release.
- Do not commit evidence files, logs, review transcripts, "closeout" reports or copies of source into any repository. Put a short verification summary in the commit message.
- Keep tests proportional to the change and test behavior, not the text of config or CI files.
- Size safeguards to this project: one maintainer, one NUC, pre-launch MVP. Do not design for hostile insiders, multi-tenant CI or enterprise compliance unless asked.
- Never disable a working release, deploy or backup path before its replacement has worked end to end.
