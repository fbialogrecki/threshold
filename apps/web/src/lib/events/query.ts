import { canonicalCity, type CanonicalCity } from "@/lib/cities"
import type { FeedFilter } from "@/lib/types"

export type EventListOptions = {
  limit?: number
  sort?: "starts" | "created"
  city?: CanonicalCity
  pageId?: string
  artistProfileId?: string
  upcoming?: boolean
}

export function buildEventListQuery(options: EventListOptions = {}): URLSearchParams {
  const { limit = 100, sort = "starts", city, pageId, artistProfileId, upcoming } = options
  const query = new URLSearchParams({ limit: String(limit), sort })
  if (city) query.set("city", city)
  if (pageId) query.set("page_id", pageId)
  if (artistProfileId) query.set("artist_profile_id", artistProfileId)
  if (upcoming) query.set("upcoming", "true")
  return query
}

export function feedIncludesEvents(filter: FeedFilter): boolean {
  return filter === "all" || filter === "events"
}

export function feedEventScopes(
  viewerCity: string | null,
  filter: FeedFilter = "all",
): EventListOptions[] {
  if (!feedIncludesEvents(filter)) return []
  const city = canonicalCity(viewerCity)
  return city
    ? [{ sort: "created", city }, { sort: "created" }]
    : [{ sort: "created" }]
}
