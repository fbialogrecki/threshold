import { describe, expect, it } from "bun:test"

import {
  assembleFeed,
  eventVisibleInFeed,
  notificationToFeedItem,
  type FeedAssemblySource,
} from "@/lib/feed/assembly"
import type { NotificationItem } from "@/lib/auth/product-auth"
import type { FeedItem, Post, ThresholdEvent } from "@/lib/types"

function post(id: string, createdAtIso: string): Post {
  return {
    id,
    author: { id: "user-1", type: "artist", handle: "dj-one", displayName: "DJ One" },
    systemOwned: false,
    createdAtIso,
    editedAtIso: null,
    body: `post ${id}`,
    mentions: [],
    tags: [],
    commentCount: 0,
    upCount: 0,
    downCount: 0,
    viewerVote: null,
    viewerIsAuthor: false,
    emojiReactions: [],
    media: [],
    eventId: null,
    eventSlug: null,
  }
}

function event(overrides: Partial<ThresholdEvent>): ThresholdEvent {
  return {
    id: "event-1",
    slug: "bass-theory",
    title: "Bass Theory",
    description: null,
    starts_at: "2026-08-15T20:00:00.000Z",
    city: "Warsaw",
    location_mode: "public_location",
    venue_name: "Room 1",
    address: null,
    genres: [],
    lineup: [],
    page_id: "page-1",
    poster_media_asset_id: null,
    created_by_user_id: "user-9",
    boost_count: 0,
    follower_count: 0,
    is_following: false,
    is_boosting: false,
    created_at: "2026-07-01T10:00:00.000Z",
    updated_at: "2026-07-01T10:00:00.000Z",
    ...overrides,
  }
}

function source(overrides: Partial<FeedAssemblySource> = {}): FeedAssemblySource {
  return {
    posts: [],
    events: [],
    eventUpdates: [],
    notifications: [],
    followedPageIds: new Set(),
    followedUserIds: new Set(),
    representedEventIds: new Set(),
    representedEventSlugs: new Set(),
    legacyRepresentedEventSlugs: new Set(),
    viewerCity: null,
    filter: "all",
    ...overrides,
  }
}

describe("assembleFeed", () => {
  it("merges posts, visible events and access updates into stable chronological order", () => {
    const accessNotification: NotificationItem = {
      id: "notif-1",
      recipient_user_id: "user-1",
      actor_user_id: null,
      type: "guestlist.added",
      target_type: "event",
      target_id: "event-2",
      target_url: "/events/secret-night",
      title: "Guestlist access granted",
      body: "You are on the list.",
      metadata: { event_slug: "secret-night", event_title: "Secret Night", access_state: "approved" },
      read_at: null,
      created_at: "2026-07-01T12:00:00.000Z",
    }

    const items = assembleFeed(source({
      posts: [post("post-old", "2026-07-01T09:00:00.000Z")],
      events: [event({ id: "event-1", created_at: "2026-07-01T11:00:00.000Z", page_id: "page-1" })],
      eventUpdates: [{
        id: "update-1",
        event: { slug: "bass-theory", title: "Bass Theory" },
        eventId: "event-1",
        authorUserId: "user-1",
        authorPageId: "page-1",
        body: "Doors open at 22:00.",
        kind: "update",
        createdAtIso: "2026-07-01T10:30:00.000Z",
        updatedAtIso: "2026-07-01T10:30:00.000Z",
      }],
      notifications: [accessNotification],
      followedPageIds: new Set(["page-1"]),
    }))

    expect(items.map((item) => item.kind)).toEqual(["access_update", "event", "event_update", "post"])
    expect(items.map((item) => item.feed.reason)).toEqual([
      "Your access changed",
      "You follow this page",
      "Event organizer update",
      "From your following feed",
    ])
  })

  it("filters by feed item class", () => {
    const items = assembleFeed(source({
      filter: "events",
      posts: [post("post-1", "2026-07-01T09:00:00.000Z")],
      events: [event({ page_id: "page-1" })],
      followedPageIds: new Set(["page-1"]),
    }))

    expect(items.map((item) => item.kind)).toEqual(["event"])
  })

  it("only shows organizer updates for events visible to the viewer", () => {
    const items = assembleFeed(source({
      events: [event({ id: "event-hidden", slug: "hidden", page_id: "page-hidden", city: "Berlin" })],
      eventUpdates: [{
        id: "update-hidden",
        event: { slug: "hidden", title: "Hidden" },
        eventId: "event-hidden",
        authorUserId: "user-1",
        authorPageId: "page-hidden",
        body: "Invisible update.",
        kind: "update",
        createdAtIso: "2026-07-01T10:30:00.000Z",
        updatedAtIso: "2026-07-01T10:30:00.000Z",
      }],
      viewerCity: "Warsaw",
    }))

    expect(items).toEqual([])
  })

  it("keeps typed placeholders for future feed item kinds out of the live feed until sourced", () => {
    const items: FeedItem[] = assembleFeed(source())

    expect(items).toEqual([])
  })

  it("keeps standalone fallback beside an ordinary event-linked post", () => {
    const linked = event({ id: "event-linked", slug: "linked-night", page_id: "page-1" })
    const linkedPost = {
      ...post("post-linked", "2026-07-02T10:00:00.000Z"),
      eventId: linked.id,
      eventSlug: linked.slug,
      linkedEvent: linked,
    }

    const items = assembleFeed(source({
      posts: [linkedPost],
      events: [linked],
      followedPageIds: new Set(["page-1"]),
    }))

    expect(items.map((item) => item.kind)).toEqual(["post", "event"])
  })

  it("lets a system announcement replace the standalone event by id", () => {
    const linked = event({ id: "event-linked", slug: "linked-night", page_id: "page-1" })
    const announcement = {
      ...post("announcement", "2026-07-02T10:00:00.000Z"),
      systemOwned: true,
      eventId: linked.id,
      eventSlug: linked.slug,
      linkedEvent: linked,
    }
    const items = assembleFeed(source({
      posts: [announcement],
      events: [linked],
      followedPageIds: new Set(["page-1"]),
      representedEventIds: new Set([linked.id]),
    }))

    expect(items.map((item) => item.kind)).toEqual(["post"])
  })

  it("suppresses represented blocked or group-hidden announcements without rendering a post", () => {
    for (const representedEventIds of [
      new Set(["event-linked"]),
      new Set(["event-linked"]),
    ]) {
      const items = assembleFeed(source({
        posts: [],
        events: [event({ id: "event-linked", page_id: "page-1" })],
        followedPageIds: new Set(["page-1"]),
        representedEventIds,
      }))
      expect(items).toEqual([])
    }
  })

  it("keeps fallback when a deleted announcement is not represented", () => {
    const items = assembleFeed(source({
      posts: [],
      events: [event({ id: "event-deleted", page_id: "page-1" })],
      followedPageIds: new Set(["page-1"]),
    }))

    expect(items.map((item) => item.kind)).toEqual(["event"])
  })

  it("falls back to slug when suppressing a duplicate standalone event", () => {
    const linkedPost = {
      ...post("post-linked", "2026-07-02T10:00:00.000Z"),
      systemOwned: true,
      eventSlug: "same-night",
    }

    const items = assembleFeed(source({
      posts: [linkedPost],
      events: [event({ id: "event-other-id", slug: "same-night", page_id: "page-1" })],
      followedPageIds: new Set(["page-1"]),
      representedEventSlugs: new Set(["same-night"]),
      legacyRepresentedEventSlugs: new Set(["same-night"]),
    }))

    expect(items.map((item) => item.kind)).toEqual(["post"])
  })

  it("does not use slug fallback when a paired immutable event id differs", () => {
    const linkedPost = {
      ...post("post-linked", "2026-07-02T10:00:00.000Z"),
      systemOwned: true,
      eventId: "event-original",
      eventSlug: "same-night",
    }
    const items = assembleFeed(source({
      posts: [linkedPost],
      events: [event({ id: "event-reused", slug: "same-night", page_id: "page-1" })],
      followedPageIds: new Set(["page-1"]),
      representedEventIds: new Set(["event-original"]),
      representedEventSlugs: new Set(["same-night"]),
    }))

    expect(items.map((item) => item.kind)).toEqual(["post", "event"])
  })

  it("keeps the full standalone event when no linked post represents it", () => {
    const standalone = event({
      page_id: "page-1",
      poster_media_asset_id: "poster-1",
      starts_at: "2026-08-15T20:00:00.000Z",
    })
    const items = assembleFeed(source({
      events: [standalone],
      followedPageIds: new Set(["page-1"]),
    }))

    expect(items).toHaveLength(1)
    expect(items[0].kind).toBe("event")
    if (items[0].kind === "event") {
      expect(items[0].event).toEqual(standalone)
      expect(items[0].event.poster_media_asset_id).toBe("poster-1")
    }
  })

  it("sorts strictly newest-first with stable id tie-breaking", () => {
    const items = assembleFeed(source({
      posts: [
        post("post-z", "2026-07-02T10:00:00.000Z"),
        post("post-a", "2026-07-02T10:00:00.000Z"),
        post("post-old", "2026-07-01T10:00:00.000Z"),
      ],
    }))

    expect(items.map((item) => item.kind === "post" ? item.post.id : "")).toEqual([
      "post-a",
      "post-z",
      "post-old",
    ])
  })

  it("sorts offsets by epoch and equivalent instants by stable id", () => {
    const items = assembleFeed(source({
      posts: [
        post("post-z", "2026-07-02T12:00:00+02:00"),
        post("post-a", "2026-07-02T10:00:00Z"),
        post("post-new", "2026-07-02T09:30:00-01:00"),
      ],
    }))

    expect(items.map((item) => item.kind === "post" ? item.post.id : "")).toEqual([
      "post-new",
      "post-a",
      "post-z",
    ])
  })

  it("places invalid timestamps last with stable id ordering", () => {
    const items = assembleFeed(source({
      posts: [
        post("invalid-z", "not-a-date"),
        post("valid", "2026-07-02T10:00:00Z"),
        post("invalid-a", ""),
      ],
    }))

    expect(items.map((item) => item.kind === "post" ? item.post.id : "")).toEqual([
      "valid",
      "invalid-a",
      "invalid-z",
    ])
  })
})

describe("eventVisibleInFeed", () => {
  it("admits followed page, followed profile, followed event and city-scene events", () => {
    expect(eventVisibleInFeed(event({ page_id: "page-1" }), source({ followedPageIds: new Set(["page-1"]) }))).toBe("You follow this page")
    expect(eventVisibleInFeed(event({ created_by_user_id: "user-2" }), source({ followedUserIds: new Set(["user-2"]) }))).toBe("You follow this organizer")
    expect(eventVisibleInFeed(event({ is_following: true }), source())).toBe("You follow this event")
    expect(eventVisibleInFeed(event({ city: "Warsaw" }), source({ viewerCity: "warsaw" }))).toBe("Your city scene")
    expect(eventVisibleInFeed(event({ city: "Berlin" }), source({ viewerCity: "warsaw" }))).toBeNull()
  })
})

describe("notificationToFeedItem", () => {
  it("maps access-sensitive notifications to feed access cards only", () => {
    const access = notificationToFeedItem({
      id: "n1",
      recipient_user_id: "user-1",
      actor_user_id: null,
      type: "secret_location.access_granted",
      target_type: "event",
      target_id: "event-1",
      target_url: "/events/bass-theory",
      title: "Access granted",
      body: null,
      metadata: { event_slug: "bass-theory", event_title: "Bass Theory", access_state: "approved" },
      read_at: null,
      created_at: "2026-07-01T12:00:00.000Z",
    })
    const mention = notificationToFeedItem({
      id: "n2",
      recipient_user_id: "user-1",
      actor_user_id: "user-2",
      type: "mention.post",
      target_type: "post",
      target_id: "post-1",
      target_url: "/posts/post-1",
      title: "Mentioned you",
      body: null,
      metadata: {},
      read_at: null,
      created_at: "2026-07-01T12:00:00.000Z",
    })

    expect(access?.kind).toBe("access_update")
    expect(mention).toBeNull()
  })
})
