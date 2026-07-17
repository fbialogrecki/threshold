import "server-only"

import { searchEventsResult } from "@/lib/api/events"
import { searchGroupsResult } from "@/lib/api/social-read"
import { searchEntities } from "@/lib/auth/product-auth"
import { cityLabel } from "@/lib/cities"
import { PAGE_TYPES, type PageType } from "@/lib/page-types"
import { searchResultType, searchSubtitle } from "@/lib/search/display"
import type { SearchResult, SearchResultType } from "@/lib/types"

type UsersSearchItem = {
  type: string
  handle: string
  display_name: string
  subtitle: string | null
}

/**
 * Live search: profiles + pages from `users`, groups from `social`, events from `events`. `type`
 * narrows the result set; omit it for an "all" search.
 */
export async function search(
  query: string,
  type?: SearchResultType,
  locale = "en",
): Promise<SearchResult[]> {
  return (await searchWithStatus(query, type, locale)).items
}

export async function searchWithStatus(
  query: string,
  type?: SearchResultType,
  locale = "en",
): Promise<{ items: SearchResult[]; error: boolean }> {
  const q = query.trim()
  if (!q) return { items: [], error: false }

  const wantProfiles = !type || type === "artist" || type === "consumer"
  const wantPages = !type || PAGE_TYPES.includes(type as PageType)
  const wantGroups = !type || type === "group"
  const wantEvents = !type || type === "event"

  const results: SearchResult[] = []
  let error = false

  if (wantProfiles || wantPages) {
    const sources = [
      ...(wantProfiles ? ["profiles" as const] : []),
      ...(wantPages ? ["pages" as const] : []),
    ]
    for (const source of sources) {
      const response = await searchEntities(q, source).catch(() => null)
      if (response?.status === 200 && Array.isArray(response.body)) {
        for (const item of response.body as UsersSearchItem[]) {
          const resultType = searchResultType(item.type)
          if (type && resultType !== type) continue
          results.push({
            type: resultType,
            title: item.display_name,
            subtitle: searchSubtitle(resultType, item.subtitle, locale),
            href: source === "pages" ? `/pages/${item.handle}` : `/u/${item.handle}`,
            handle: item.handle,
          })
        }
      } else {
        error = true
      }
    }
  }

  if (wantGroups) {
    const groups = await searchGroupsResult(q)
    error ||= groups.error
    for (const group of groups.items) {
      results.push({
        type: "group",
        title: group.name,
        subtitle: cityLabel(group.city, locale),
        href: `/groups/${group.slug}`,
        handle: group.slug,
      })
    }
  }

  if (wantEvents) {
    const events = await searchEventsResult(q)
    error ||= events.error
    for (const event of events.items) {
      results.push({
        type: "event",
        title: event.title,
        subtitle: [event.city ? cityLabel(event.city, locale) : "", event.genres.slice(0, 2).join(" / ")]
          .filter(Boolean)
          .join(" · "),
        href: `/events/${event.slug}`,
        handle: event.slug,
      })
    }
  }

  return { items: results, error }
}
