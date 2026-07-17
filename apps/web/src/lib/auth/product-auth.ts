import "server-only"

import { cookies } from "next/headers"

import { REFRESH_COOKIE, SESSION_COOKIE } from "@/lib/auth/cookies"
import { resolveUsersServiceUrl } from "@/lib/auth/users-service-url"
import type { NotificationPreferences } from "@/lib/notification-preferences"

/**
 * Server-only client for the `users` product-auth API (`/v1/auth/*`).
 * The browser never reaches `users` directly; the BFF route handlers and SSR
 * session reader call through here and bridge the resulting cookies.
 */
const USERS_SERVICE_URL = process.env.USERS_SERVICE_URL

export type UsersResponse = {
  status: number
  body: unknown
  /** Raw Set-Cookie headers from `users`, to be bridged onto the browser. */
  setCookies: string[]
}

function baseUrl(): string {
  return resolveUsersServiceUrl(USERS_SERVICE_URL)
}

/** Forward only the opaque auth cookies, never unrelated browser cookies. */
async function authCookieHeader(): Promise<string> {
  const store = await cookies()
  return [SESSION_COOKIE, REFRESH_COOKIE]
    .map((name) => {
      const value = store.get(name)?.value
      return value ? `${name}=${value}` : null
    })
    .filter((entry): entry is string => entry !== null)
    .join("; ")
}

async function call(
  path: string,
  init: { method: string; json?: unknown; forwardCookies?: boolean } = {
    method: "GET",
  },
): Promise<UsersResponse> {
  const headers = new Headers({ accept: "application/json" })
  let requestBody: string | undefined

  if (init.json !== undefined) {
    headers.set("content-type", "application/json")
    requestBody = JSON.stringify(init.json)
  }
  if (init.forwardCookies) {
    const cookieHeader = await authCookieHeader()
    if (cookieHeader) headers.set("cookie", cookieHeader)
  }

  const response = await fetch(`${baseUrl()}${path}`, {
    method: init.method,
    headers,
    body: requestBody,
    cache: "no-store",
  })

  const setCookies = response.headers.getSetCookie?.() ?? []
  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }

  return { status: response.status, body, setCookies }
}

/**
 * Removes dev-only token fields from a `users` response body before it is ever
 * returned to the browser. SECURITY: `dev_password_reset_token` /
 * `dev_email_verification_token` are exposed by `users` when
 * `auth_dev_expose_tokens` is on; forwarding them to the caller would let
 * anyone request a reset for a victim's email and read the token back. The
 * tokens are only ever read out-of-band (server logs / direct API) in dev.
 */
export function stripDevTokens(body: unknown): unknown {
  if (body === null || typeof body !== "object") return body
  const clone: Record<string, unknown> = { ...(body as Record<string, unknown>) }
  delete clone.dev_email_verification_token
  delete clone.dev_password_reset_token
  return clone
}

export type RegisterPayload = {
  email: string
  username: string
  password: string
  display_name?: string
}

export function register(payload: RegisterPayload): Promise<UsersResponse> {
  return call("/v1/auth/register", { method: "POST", json: payload })
}

export function login(payload: {
  email_or_username: string
  password: string
}): Promise<UsersResponse> {
  return call("/v1/auth/login", { method: "POST", json: payload })
}

export function logout(): Promise<UsersResponse> {
  return call("/v1/auth/logout", { method: "POST", forwardCookies: true })
}

export function refresh(): Promise<UsersResponse> {
  return call("/v1/auth/refresh", { method: "POST", forwardCookies: true })
}

export function me(): Promise<UsersResponse> {
  return call("/v1/auth/me", { method: "GET", forwardCookies: true })
}

export function passwordResetRequest(email: string): Promise<UsersResponse> {
  return call("/v1/auth/password/reset/request", { method: "POST", json: { email } })
}

export function passwordResetConfirm(payload: {
  token: string
  new_password: string
}): Promise<UsersResponse> {
  return call("/v1/auth/password/reset/confirm", { method: "POST", json: payload })
}

export function emailVerifyRequest(): Promise<UsersResponse> {
  return call("/v1/auth/email/verify/request", { method: "POST", forwardCookies: true })
}

export function emailVerifyConfirm(token: string): Promise<UsersResponse> {
  return call("/v1/auth/email/verify/confirm", { method: "POST", json: { token } })
}

// --- Slice 2: profile, onboarding, artist, account, follows (session-bound) ---

export function updateOnboarding(payload: {
  city: string | null
  preferred_scenes: string | null
}): Promise<UsersResponse> {
  return call("/v1/me/onboarding", { method: "PUT", json: payload, forwardCookies: true })
}

export type ProfileUpdatePayload = {
  display_name?: string
  username?: string
  bio?: string
  city?: string
  avatar_media_asset_id?: string
}

export function updateProfile(payload: ProfileUpdatePayload): Promise<UsersResponse> {
  return call("/v1/me/profile", { method: "PATCH", json: payload, forwardCookies: true })
}

export type ArtistUpdatePayload = {
  role?: string | null
  location?: string | null
  links: { label: string; url: string }[]
}

export function updateArtist(payload: ArtistUpdatePayload): Promise<UsersResponse> {
  return call("/v1/me/artist", { method: "POST", json: payload, forwardCookies: true })
}

export type PageCreatePayload = {
  slug: string
  display_name: string
  page_type: "club" | "collective" | "project" | "festival"
  city?: string | null
  about?: string | null
  links: { label: string; url: string }[]
}

export function createPage(payload: PageCreatePayload): Promise<UsersResponse> {
  return call("/v1/pages", { method: "POST", json: payload, forwardCookies: true })
}

export function listManagedPages(): Promise<UsersResponse> {
  return call("/v1/me/pages", { method: "GET", forwardCookies: true })
}

export function setPageMember(
  slug: string,
  username: string,
  role: "admin" | "editor",
): Promise<UsersResponse> {
  return call(`/v1/pages/${encodeURIComponent(slug)}/members/${encodeURIComponent(username)}`, {
    method: "PUT",
    json: { role },
    forwardCookies: true,
  })
}

export function removePageMember(slug: string, username: string): Promise<UsersResponse> {
  return call(`/v1/pages/${encodeURIComponent(slug)}/members/${encodeURIComponent(username)}`, {
    method: "DELETE",
    forwardCookies: true,
  })
}

/** Deletes (anonymizes) the account. `users` clears the auth cookies, which we bridge. */
export function deleteAccount(): Promise<UsersResponse> {
  return call("/v1/me", { method: "DELETE", forwardCookies: true })
}

export type FollowTargetType = "artist" | "consumer" | "page"

export function followTarget(
  targetType: FollowTargetType,
  targetHandle: string,
): Promise<UsersResponse> {
  return call("/v1/me/follows", {
    method: "POST",
    json: { target_type: targetType, target_handle: targetHandle },
    forwardCookies: true,
  })
}

export function unfollowTarget(
  targetType: FollowTargetType,
  targetHandle: string,
): Promise<UsersResponse> {
  return call(
    `/v1/me/follows/${encodeURIComponent(targetType)}/${encodeURIComponent(targetHandle)}`,
    { method: "DELETE", forwardCookies: true },
  )
}

export function listFollows(): Promise<UsersResponse> {
  return call("/v1/me/follows", { method: "GET", forwardCookies: true })
}

export function blockUser(username: string): Promise<UsersResponse> {
  return call("/v1/me/blocks", {
    method: "POST",
    json: { username },
    forwardCookies: true,
  })
}

export function reportTarget(payload: {
  target_type: "profile" | "page" | "post" | "comment"
  target_handle: string
  reason: string
  note?: string | null
}): Promise<UsersResponse> {
  return call("/v1/reports", { method: "POST", json: payload, forwardCookies: true })
}

export type NotificationItem = {
  id: string
  recipient_user_id: string
  actor_user_id: string | null
  type: string
  target_type: string
  target_id: string
  target_url: string | null
  title: string
  body: string | null
  metadata: Record<string, string | number | boolean | null>
  read_at: string | null
  created_at: string
}

export function listNotifications(): Promise<UsersResponse> {
  return call("/v1/notifications", { method: "GET", forwardCookies: true })
}

export function notificationUnreadCount(): Promise<UsersResponse> {
  return call("/v1/notifications/unread-count", { method: "GET", forwardCookies: true })
}

export function markNotificationRead(id: string): Promise<UsersResponse> {
  return call(`/v1/notifications/${encodeURIComponent(id)}/read`, {
    method: "POST",
    forwardCookies: true,
  })
}

export function markAllNotificationsRead(): Promise<UsersResponse> {
  return call("/v1/notifications/read-all", { method: "POST", forwardCookies: true })
}

export function getNotificationPreferences(): Promise<UsersResponse> {
  return call("/v1/notifications/preferences", { method: "GET", forwardCookies: true })
}

export function updateNotificationPreferences(
  payload: Partial<NotificationPreferences>,
): Promise<UsersResponse> {
  return call("/v1/notifications/preferences", {
    method: "PUT",
    json: payload,
    forwardCookies: true,
  })
}

// --- Public read models (no auth required) ---

export function getPublicProfile(username: string): Promise<UsersResponse> {
  return call(`/v1/profiles/${encodeURIComponent(username)}`, { method: "GET" })
}

export function getPublicPage(slug: string): Promise<UsersResponse> {
  return call(`/v1/pages/${encodeURIComponent(slug)}`, {
    method: "GET",
    forwardCookies: true,
  })
}

export function searchEntities(
  query: string,
  type?: "profiles" | "pages",
): Promise<UsersResponse> {
  const params = new URLSearchParams({ q: query })
  if (type) params.set("type", type)
  return call(`/v1/search?${params.toString()}`, { method: "GET" })
}
