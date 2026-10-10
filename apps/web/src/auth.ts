import { getSession, type Session } from "@/lib/auth/session"

/**
 * Product-auth session for server components.
 *
 * The platform's public login/register run on Perlimen's own product-auth in
 * the `users` service (opaque HttpOnly cookies bridged through the BFF), NOT on
 * Authentik. Authentik stays an internal/admin SSO concern only. `auth()` keeps
 * the historical `{ user } | null` shape so existing call sites are unchanged.
 */
export type PerlimenSession = Session

export async function auth(): Promise<PerlimenSession | null> {
  return getSession()
}
