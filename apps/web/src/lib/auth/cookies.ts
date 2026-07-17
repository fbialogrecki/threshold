import "server-only"

import { cookies } from "next/headers"

import { resolveCookieSecurity } from "@/lib/auth/cookie-security"
import {
  planAuthCookieMutations,
  REFRESH_COOKIE,
  SESSION_COOKIE,
} from "@/lib/auth/cookie-policy"

export {
  SESSION_COOKIE,
  REFRESH_COOKIE,
} from "@/lib/auth/cookie-policy"

function cookieSecure(): boolean {
  return resolveCookieSecurity({
    nodeEnv: process.env.NODE_ENV,
    authCookieSecure: process.env.AUTH_COOKIE_SECURE,
    trustedLanHttp: process.env.WEB_TRUSTED_LAN_HTTP,
  }).secure
}

/**
 * Bridges Set-Cookie headers returned by the `users` service onto the
 * browser-facing origin: rewrites the refresh cookie path and applies a single,
 * consistent Secure/SameSite policy. Always HttpOnly — browser JS never reads
 * the session or refresh tokens.
 */
export async function bridgeAuthCookies(setCookieHeaders: string[]): Promise<void> {
  if (setCookieHeaders.length === 0) return
  const store = await cookies()
  for (const mutation of planAuthCookieMutations(setCookieHeaders, cookieSecure())) {
    const { name, value, ...options } = mutation
    store.set(name, value, options)
  }
}

export async function clearAuthCookies(): Promise<void> {
  const store = await cookies()
  store.set(SESSION_COOKIE, "", {
    path: "/",
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: "lax",
    maxAge: 0,
  })
  store.set(REFRESH_COOKIE, "", {
    path: "/api/auth",
    httpOnly: true,
    secure: cookieSecure(),
    sameSite: "lax",
    maxAge: 0,
  })
}
