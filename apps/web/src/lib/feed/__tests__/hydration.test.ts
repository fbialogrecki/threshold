import { describe, expect, it } from "bun:test"

import {
  hydrateFeedPosts,
  mergeFeedEvents,
  missingPostEventSlugs,
  organizerPageIds,
} from "@/lib/feed/hydration"
import type { Post, ThresholdEvent } from "@/lib/types"

const event: ThresholdEvent = {
  id: "event-1",
  slug: "bass-theory",
  title: "Bass Theory",
  description: null,
  starts_at: "2026-08-15T20:00:00.000Z",
  city: "warsaw",
  location_mode: "public_location",
  venue_name: "Room 1",
  address: null,
  genres: [],
  lineup: [],
  page_id: "page-1",
  poster_media_asset_id: null,
  created_by_user_id: "user-1",
  boost_count: 0,
  follower_count: 0,
  is_following: false,
  is_boosting: false,
  created_at: "2026-07-01T10:00:00.000Z",
  updated_at: "2026-07-01T10:00:00.000Z",
}

function post(systemOwned: boolean): Post {
  return {
    id: systemOwned ? "system-post" : "user-post",
    author: { id: "user-1", type: "artist", handle: "dj-one", displayName: "DJ One" },
    systemOwned,
    createdAtIso: "2026-07-01T10:00:00.000Z",
    editedAtIso: null,
    body: "Bass Theory",
    mentions: [],
    tags: [],
    commentCount: 0,
    upCount: 0,
    downCount: 0,
    viewerVote: null,
    viewerIsAuthor: !systemOwned,
    emojiReactions: [],
    media: [],
    eventId: "event-1",
    eventSlug: "bass-theory",
  }
}

describe("feed hydration", () => {
  it("batches unique organizer page ids in first-seen order", () => {
    expect(organizerPageIds([
      event,
      { ...event, id: "event-2", page_id: "page-2" },
      { ...event, id: "event-3", page_id: "page-1" },
      { ...event, id: "event-4", page_id: null },
    ])).toEqual(["page-1", "page-2"])
  })

  it("batches only unique linked event slugs missing from scoped events", () => {
    expect(missingPostEventSlugs([
      post(false),
      { ...post(false), id: "post-2", eventId: "event-2", eventSlug: "outside-window" },
      { ...post(false), id: "post-3", eventId: "event-2", eventSlug: "outside-window" },
      { ...post(false), id: "post-4", eventId: null, eventSlug: null },
    ], [event])).toEqual(["outside-window"])
  })

  it("hydrates an event fetched outside the scoped latest lists", () => {
    const outside = { ...event, id: "event-outside", slug: "outside-window" }
    const linkedPost = { ...post(false), eventId: "event-outside", eventSlug: "outside-window" }
    const merged = mergeFeedEvents([event], [outside])

    expect(merged.map((item) => item.slug)).toEqual(["bass-theory", "outside-window"])
    expect(hydrateFeedPosts([linkedPost], merged, [])[0].linkedEvent?.id).toBe("event-outside")
  })

  it("hydrates by immutable event id before legacy slug fallback", () => {
    const paired = { ...post(false), eventId: "event-canonical", eventSlug: "reused-slug" }
    const legacy = { ...post(false), id: "legacy", eventId: null, eventSlug: "reused-slug" }
    const reused = { ...event, id: "event-reused", slug: "reused-slug" }
    const canonical = { ...event, id: "event-canonical", slug: "canonical-slug" }
    const [pairedResult, legacyResult] = hydrateFeedPosts(
      [paired, legacy],
      [reused, canonical],
      [],
    )

    expect(pairedResult.linkedEvent?.id).toBe("event-canonical")
    expect(legacyResult.linkedEvent?.id).toBe("event-reused")
  })

  it("uses organizer identity only for system event posts", () => {
    const organizer = {
      id: "page-1",
      slug: "room-one",
      display_name: "Room One",
      page_type: "club",
      avatar_media_asset_id: "asset-1",
      target_url: "/pages/room-one",
    }
    const [systemPost, userPost] = hydrateFeedPosts(
      [post(true), post(false)],
      [event],
      [organizer],
    )

    expect(systemPost.author).toMatchObject({
      id: "page-1",
      handle: "room-one",
      displayName: "Room One",
      href: "/pages/room-one",
    })
    expect(systemPost.linkedEvent?.id).toBe("event-1")
    expect(systemPost.viewerIsAuthor).toBe(false)
    expect(userPost.author.handle).toBe("dj-one")
    expect(userPost.linkedEvent?.id).toBe("event-1")
  })
})
