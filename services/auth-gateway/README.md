# auth-gateway

Thin internal/admin edge service for Threshold Authentik-backed SSO flows.

This service is not product-auth for public Threshold users. Public register/login/session flows belong to product-auth in `users` and use custom UI + HttpOnly cookies.

Current scope:

- `/healthz`
- `/readyz`
- `/me` requiring a Bearer token issued by Authentik
- Authentik JWKS/JWT validation
- user context propagation
- NATS request/reply to `users.current_profile.v1`

Intended boundary:

- internal/admin/backend service access: Authentik OIDC/JWT through `auth-gateway`
- product user access: `users` product-auth session, no Authentik dependency in public login/register
