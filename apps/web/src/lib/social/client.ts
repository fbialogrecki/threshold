import "server-only"

import { getSession, type Session } from "@/lib/auth/session"

export class SocialServiceConfigurationError extends Error {
  constructor(message = "SOCIAL_SERVICE_URL or THRESHOLD_INTERNAL_TOKEN is not configured") {
    super(message)
    this.name = "SocialServiceConfigurationError"
  }
}

export type SocialResponse = {
  status: number
  body: unknown
}

type SocialCallOptions = {
  method?: string
  json?: unknown
  query?: URLSearchParams
  userHeaders?: HeadersInit
}

function baseUrl(): string {
  const value = process.env.SOCIAL_SERVICE_URL
  if (!value?.trim()) throw new SocialServiceConfigurationError()
  return value.replace(/\/$/, "")
}

function internalToken(): string {
  const value = process.env.THRESHOLD_INTERNAL_TOKEN
  if (!value?.trim()) throw new SocialServiceConfigurationError()
  return value
}

export async function socialCall(
  path: string,
  options: SocialCallOptions = {},
): Promise<SocialResponse> {
  const headers = new Headers({
    accept: "application/json",
    "X-Threshold-Internal-Token": internalToken(),
    ...options.userHeaders,
  })
  let body: string | undefined

  if (options.json !== undefined) {
    headers.set("content-type", "application/json")
    body = JSON.stringify(options.json)
  }

  const query = options.query?.toString()
  const response = await fetch(`${baseUrl()}${path}${query ? `?${query}` : ""}`, {
    method: options.method ?? "GET",
    headers,
    body,
    cache: "no-store",
  })

  const text = await response.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }

  return { status: response.status, body: parsed }
}

function displayNameFromSession(session: Session): string {
  const profile = session.consumer_profile
  if (profile && typeof profile === "object" && "display_name" in profile) {
    const value = (profile as { display_name?: unknown }).display_name
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return session.user.username ?? "deleted-user"
}

export async function trustedAuthorHeaders(): Promise<HeadersInit | null> {
  const session = await getSession()
  if (!session?.user) return null

  return {
    "X-Threshold-User-Id": session.user.id,
    "X-Threshold-Username": session.user.username ?? "deleted-user",
    "X-Threshold-Display-Name": displayNameFromSession(session),
  }
}
