export const MAX_POST_BODY = 2000
export const MAX_POST_IMAGES = 4

export type PostComposerInput = {
  body: string
  groupSlug?: string
  eventSlug?: string
  mediaAssetIds?: string[]
}

export function buildPostPayload(input: PostComposerInput) {
  if (input.eventSlug?.trim() && input.mediaAssetIds?.length) {
    throw new Error("posts may attach images or an event, not both")
  }
  return {
    body: input.body.trim(),
    group_slug: input.groupSlug ?? null,
    event_slug: input.eventSlug?.trim() || null,
    mentions: [],
    media_asset_ids: (input.mediaAssetIds ?? []).slice(0, MAX_POST_IMAGES),
  }
}

export function canSubmitPost(input: Pick<PostComposerInput, "body">): boolean {
  const length = input.body.trim().length
  return length > 0 && length <= MAX_POST_BODY
}

type EventValidation =
  | { ok: true; event: { id: string; slug: string } | null }
  | {
      ok: false
      error: "invalid event_slug" | "event not found" | "event validation unavailable"
      status: number
    }

export async function validateSelectedEvent(
  payload: unknown,
  lookupEvent: (slug: string) => Promise<{ status: number; body: unknown }>,
): Promise<EventValidation> {
  if (typeof payload !== "object" || payload === null || !("event_slug" in payload)) {
    return { ok: true, event: null }
  }
  const value = (payload as { event_slug?: unknown }).event_slug
  if (value === null || value === undefined || value === "") return { ok: true, event: null }
  if (typeof value !== "string") return { ok: false, error: "invalid event_slug", status: 422 }
  const slug = value.trim().toLowerCase()
  if (!/^[a-z0-9-]{3,160}$/.test(slug)) {
    return { ok: false, error: "invalid event_slug", status: 422 }
  }
  const { status, body } = await lookupEvent(slug)
  if (status === 200) {
    if (typeof body === "object" && body !== null) {
      const event = body as { id?: unknown; slug?: unknown }
      if (typeof event.id === "string" && typeof event.slug === "string") {
        return { ok: true, event: { id: event.id, slug: event.slug } }
      }
    }
    return { ok: false, error: "event validation unavailable", status: 503 }
  }
  if (status === 404) return { ok: false, error: "event not found", status: 422 }
  return {
    ok: false,
    error: "event validation unavailable",
    status: status >= 500 ? status : 503,
  }
}

export function canonicalPostPayload(
  payload: unknown,
  event: { id: string; slug: string } | null,
): Record<string, unknown> | null {
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) return null
  const canonical = { ...(payload as Record<string, unknown>) }
  delete canonical.event_id
  if (!event) {
    canonical.event_slug = null
    return canonical
  }
  if (Array.isArray(canonical.media_asset_ids) && canonical.media_asset_ids.length > 0) {
    return null
  }
  canonical.event_id = event.id
  canonical.event_slug = event.slug
  return canonical
}

export function createdPostMatchesEvent(
  body: unknown,
  event: { id: string; slug: string } | null,
): boolean {
  if (!event) return true
  if (typeof body !== "object" || body === null) return false
  const post = body as { event_id?: unknown; event_slug?: unknown }
  return post.event_id === event.id && post.event_slug === event.slug
}

