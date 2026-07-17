import "server-only"

import {
  getPublicPage as fetchPublicPage,
  getPublicProfile as fetchPublicProfile,
  listFollows,
} from "@/lib/auth/product-auth"
import { resolveUsersServiceUrl } from "@/lib/auth/users-service-url"
import type { OrganizerRef } from "@/lib/feed/hydration"
import { pageType, type PageType } from "@/lib/page-types"
import type { ExternalLink, FollowTarget, Residency } from "@/lib/types"

export type PublicProfileView = {
  id: string
  type: "artist" | "consumer"
  username: string
  artistProfileId: string
  displayName: string
  bio: string
  role: string
  location: string
  links: ExternalLink[]
  avatarMediaAssetId: string
  residencies: Residency[]
  followerCount: number
}

export type PublicPageView = {
  id: string
  slug: string
  name: string
  type: PageType
  city: string
  about: string
  links: ExternalLink[]
  avatarMediaAssetId: string
  residents: { handle: string; displayName: string; state: "accepted" }[]
  followerCount: number
  isFollowing: boolean
}

export type UserReference = {
  userId: string
  username: string
  displayName: string
}

function mapLinks(raw: unknown): ExternalLink[] {
  if (!Array.isArray(raw)) return []
  return raw
    .map((entry) => {
      if (typeof entry !== "object" || entry === null) return null
      const { label, url } = entry as { label?: unknown; url?: unknown }
      if (typeof label !== "string" || typeof url !== "string") return null
      if (!/^https?:\/\//.test(url)) return null
      return { label, url }
    })
    .filter((link): link is ExternalLink => link !== null)
}

function mapResidencies(raw: unknown): Residency[] {
  if (!Array.isArray(raw)) return []
  return raw.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null) return []
    const { page_slug, page_name } = entry as { page_slug?: unknown; page_name?: unknown }
    if (typeof page_slug !== "string" || typeof page_name !== "string") return []
    return [{ pageHandle: page_slug, pageName: page_name, state: "confirmed" }]
  })
}

function mapResidents(raw: unknown): { handle: string; displayName: string; state: "accepted" }[] {
  if (!Array.isArray(raw)) return []
  return raw.flatMap((entry) => {
    if (typeof entry !== "object" || entry === null) return []
    const { username, display_name } = entry as { username?: unknown; display_name?: unknown }
    if (typeof username !== "string" || typeof display_name !== "string") return []
    return [{ handle: username, displayName: display_name, state: "accepted" }]
  })
}

export async function getProfile(username: string): Promise<PublicProfileView | null> {
  if (!process.env.USERS_SERVICE_URL) return null
  const { status, body } = await fetchPublicProfile(username)
  if (status !== 200 || typeof body !== "object" || body === null) return null
  const p = body as {
    id?: string
    type?: string
    username?: string
    artist_profile_id?: string | null
    display_name?: string
    bio?: string | null
    role?: string | null
    location?: string | null
    links?: unknown
    avatar_media_asset_id?: string | null
    residencies?: unknown
    follower_count?: number
  }
  return {
    id: p.id ?? "",
    type: p.type === "artist" ? "artist" : "consumer",
    username: p.username ?? username,
    artistProfileId: p.artist_profile_id ?? "",
    displayName: p.display_name ?? p.username ?? username,
    bio: p.bio ?? "",
    role: p.role ?? "",
    location: p.location ?? "",
    links: mapLinks(p.links),
    avatarMediaAssetId: p.avatar_media_asset_id ?? "",
    residencies: mapResidencies(p.residencies),
    followerCount: p.follower_count ?? 0,
  }
}

export async function getPage(slug: string): Promise<PublicPageView | null> {
  if (!process.env.USERS_SERVICE_URL) return null
  const { status, body } = await fetchPublicPage(slug)
  if (status !== 200 || typeof body !== "object" || body === null) return null
  const p = body as {
    id?: string
    slug?: string
    display_name?: string
    page_type?: string | null
    city?: string | null
    about?: string | null
    links?: unknown
    avatar_media_asset_id?: string | null
    residents?: unknown
    follower_count?: number
    is_following?: boolean
  }
  return {
    id: p.id ?? "",
    slug: p.slug ?? slug,
    name: p.display_name ?? slug,
    type: pageType(p.page_type),
    city: p.city ?? "",
    about: p.about ?? "",
    links: mapLinks(p.links),
    avatarMediaAssetId: p.avatar_media_asset_id ?? "",
    residents: mapResidents(p.residents),
    followerCount: p.follower_count ?? 0,
    isFollowing: p.is_following === true,
  }
}

export async function getFollowedTargets(): Promise<FollowTarget[]> {
  try {
    const { status, body } = await listFollows()
    return status === 200 && Array.isArray(body) ? (body as FollowTarget[]) : []
  } catch {
    return []
  }
}

/** Targets the current user follows, as `${target_type}:${target_handle}` keys. */
export async function getFollowedKeys(): Promise<Set<string>> {
  const follows = await getFollowedTargets()
  const keys = follows.flatMap((follow) => {
    const handle = follow.target_handle.toLowerCase()
    const key = `${follow.target_type}:${handle}`
    return follow.target_type === "club" || follow.target_type === "collective"
      ? [key, `page:${handle}`]
      : [key]
  })
  return new Set(keys)
}

export function followKey(targetType: string, handle: string): string {
  return `${targetType}:${handle.toLowerCase()}`
}

export async function resolveUserReference(username: string): Promise<UserReference | null> {
  const handle = username.trim().replace(/^@/, "").slice(0, 30)
  if (!handle || !process.env.USERS_SERVICE_URL || !process.env.THRESHOLD_INTERNAL_TOKEN) {
    return null
  }
  try {
    const response = await fetch(
      `${resolveUsersServiceUrl(process.env.USERS_SERVICE_URL)}/internal/v1/mention-targets/profiles/${encodeURIComponent(handle)}`,
      {
        headers: {
          accept: "application/json",
          "X-Threshold-Internal-Token": process.env.THRESHOLD_INTERNAL_TOKEN,
        },
        cache: "no-store",
      },
    )
    if (!response.ok) return null
    const body = await response.json() as {
      target_id?: unknown
      handle?: unknown
      display_name?: unknown
    }
    return typeof body.target_id === "string"
      && typeof body.handle === "string"
      && typeof body.display_name === "string"
      ? { userId: body.target_id, username: body.handle, displayName: body.display_name }
      : null
  } catch {
    return null
  }
}

function isOrganizerRef(value: unknown): value is OrganizerRef {
  if (typeof value !== "object" || value === null) return false
  const ref = value as Partial<OrganizerRef>
  return typeof ref.id === "string"
    && typeof ref.slug === "string"
    && typeof ref.display_name === "string"
    && typeof ref.target_url === "string"
}

export async function getOrganizerRefs(pageIds: string[]): Promise<OrganizerRef[]> {
  const ids = [...new Set(pageIds)].slice(0, 100)
  if (ids.length === 0 || !process.env.USERS_SERVICE_URL || !process.env.THRESHOLD_INTERNAL_TOKEN) {
    return []
  }
  try {
    const response = await fetch(
      `${resolveUsersServiceUrl(process.env.USERS_SERVICE_URL)}/internal/v1/pages/organizer-refs`,
      {
        method: "POST",
        headers: {
          accept: "application/json",
          "content-type": "application/json",
          "X-Threshold-Internal-Token": process.env.THRESHOLD_INTERNAL_TOKEN,
        },
        body: JSON.stringify({ page_ids: ids }),
        cache: "no-store",
      },
    )
    if (!response.ok) return []
    const body: unknown = await response.json().catch(() => null)
    return Array.isArray(body) ? body.filter(isOrganizerRef) : []
  } catch {
    return []
  }
}
