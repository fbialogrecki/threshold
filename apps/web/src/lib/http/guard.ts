import { headers } from "next/headers"

import { getSession } from "@/lib/auth/session"

/**
 * Rejects cross-origin mutations (lightweight CSRF guard for BFF route
 * handlers). Browsers send Origin on POST/PUT/DELETE; we require it to match
 * the request host.
 */
export async function assertSameOrigin(request: Request): Promise<boolean> {
  const origin = request.headers.get("origin")
  if (!origin) {
    // No Origin header: treat as same-origin only for navigations, but our
    // mutations always run from fetch() which sets Origin, so be strict.
    return false
  }

  const headerStore = await headers()
  const host = headerStore.get("host")
  if (!host) return false

  try {
    return new URL(origin).host === host
  } catch {
    return false
  }
}

export type Principal = { authenticated: true } | { authenticated: false }

export async function requireSession(): Promise<Principal> {
  const session = await getSession()
  return session?.user ? { authenticated: true } : { authenticated: false }
}
