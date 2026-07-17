import { describe, expect, it, mock } from "bun:test"

import { assembleFeed } from "@/lib/feed/assembly"
import type { SocialPost } from "@/lib/api/social-read"
import type { ThresholdEvent } from "@/lib/types"

mock.module("server-only", () => ({}))
const { getEventAnnouncementPosts, mapPost } = await import("@/lib/api/social-read")

const raw: SocialPost = {
  id: "post-1",
  author_user_id: "user-1",
  author_username: "threshold-events",
  author_display_name: "Threshold Events",
  author_type: "system",
  group_id: null,
  event_id: "event-1",
  event_slug: "bass-theory",
  body: "New event: Bass Theory",
  created_at: "2026-07-01T10:00:00.000Z",
  up_count: 0,
  down_count: 0,
  viewer_vote: null,
  viewer_is_author: true,
  emoji_reactions: [],
  comment_count: 0,
  media_asset_ids: [],
  mentions: [],
}

describe("social post mapping", () => {
  it("maps paired event identity and system ownership", () => {
    expect(mapPost(raw)).toMatchObject({
      id: "post-1",
      eventId: "event-1",
      eventSlug: "bass-theory",
      systemOwned: true,
      viewerIsAuthor: false,
    })
  })

  it("preserves represented announcements hidden from the visible post list", async () => {
    const result = await getEventAnnouncementPosts(
      ["event-1"],
      async () => ({
        status: 200,
        body: {
          posts: [],
          represented_event_ids: ["event-1"],
          represented_event_slugs: ["bass-theory"],
        },
      }),
      async () => ({}),
    )

    expect(result).toEqual({
      items: [],
      representedEventIds: ["event-1"],
      representedEventSlugs: ["bass-theory"],
      legacyRepresentedEventSlugs: [],
      supported: true,
    })
  })

  it("infers represented refs only from visible legacy system posts", async () => {
    const result = await getEventAnnouncementPosts(
      ["event-1"],
      async () => ({ status: 200, body: [raw] }),
      async () => ({}),
    )

    expect(result.representedEventIds).toEqual(["event-1"])
    expect(result.representedEventSlugs).toEqual(["bass-theory"])
    expect(result.legacyRepresentedEventSlugs).toEqual([])
    expect(result.items).toHaveLength(1)
  })

  it("keeps new-envelope ids and legacy-array slugs across two chunks", async () => {
    let calls = 0
    const legacy = {
      ...raw,
      id: "legacy-post",
      event_id: null,
      event_slug: "legacy-night",
    }
    const result = await getEventAnnouncementPosts(
      Array.from({ length: 101 }, (_, index) => `event-${index}`),
      async () => {
        calls += 1
        return calls === 1
          ? {
              status: 200,
              body: {
                posts: [],
                represented_event_ids: ["event-new"],
                represented_event_slugs: ["new-night"],
              },
            }
          : { status: 200, body: [legacy] }
      },
      async () => ({}),
    )
    const event = (id: string, slug: string): ThresholdEvent => ({
      id,
      slug,
      title: slug,
      description: null,
      starts_at: "2026-08-15T20:00:00Z",
      city: "Warsaw",
      location_mode: "public_location",
      venue_name: null,
      address: null,
      genres: [],
      lineup: [],
      page_id: "page-1",
      poster_media_asset_id: null,
      created_by_user_id: null,
      boost_count: 0,
      follower_count: 0,
      is_following: false,
      is_boosting: false,
      created_at: "2026-07-01T10:00:00Z",
      updated_at: "2026-07-01T10:00:00Z",
    })
    const items = assembleFeed({
      posts: result.items,
      events: [event("event-new", "new-night"), event("event-legacy", "legacy-night")],
      eventUpdates: [],
      notifications: [],
      followedPageIds: new Set(["page-1"]),
      followedUserIds: new Set(),
      representedEventIds: new Set(result.representedEventIds),
      representedEventSlugs: new Set(result.representedEventSlugs),
      legacyRepresentedEventSlugs: new Set(result.legacyRepresentedEventSlugs),
      viewerCity: "Warsaw",
      filter: "all",
    })

    expect(calls).toBe(2)
    expect(result.representedEventIds).toEqual(["event-new"])
    expect(result.legacyRepresentedEventSlugs).toEqual(["legacy-night"])
    expect(items.map((item) => item.kind)).toEqual(["post"])
  })
})
