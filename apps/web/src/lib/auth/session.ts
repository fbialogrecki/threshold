import "server-only"

import { cookies } from "next/headers"
import { cache } from "react"

import { SESSION_COOKIE } from "@/lib/auth/cookies"
import { me } from "@/lib/auth/product-auth"
import { sessionStatus } from "@/lib/auth/status"

type SessionUser = {
  id: string
  username: string | null
  email: string | null
  email_verified: boolean
}

export type Session = {
  user: SessionUser
  consumer_profile?: {
    display_name?: string | null
    avatar_media_asset_id?: string | null
  } | null
  onboarding_preferences?: {
    city?: string | null
    preferred_scenes?: string | null
  } | null
}

export type SessionState =
  | { status: "authenticated"; session: Session }
  | { status: "anonymous" }
  | { status: "invalid" }
  | { status: "unavailable" }

/**
 * Server-side product-auth session reader.
 *
 * Short-circuits to null when no session cookie is present, so anonymous /
 * public SSR (landing and direct event/profile details) never makes a network
 * call. Wrapped in React `cache()` so the many `auth()` call sites in a single
 * render trigger at most one `/v1/auth/me` call per request — which matters
 * because that endpoint also writes `last_seen_at`.
 */
export const getSessionState = cache(async (): Promise<SessionState> => {
  const store = await cookies()
  const hasSessionCookie = Boolean(store.get(SESSION_COOKIE)?.value)
  if (!hasSessionCookie) return { status: "anonymous" }

  try {
    const response = await me()
    const status = sessionStatus(true, response.status)
    if (status === "authenticated") {
      return { status, session: response.body as Session }
    }
    return { status }
  } catch {
    return { status: "unavailable" }
  }
})

export async function getSession(): Promise<Session | null> {
  const state = await getSessionState()
  return state.status === "authenticated" ? state.session : null
}
