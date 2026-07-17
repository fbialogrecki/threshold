import { describe, expect, it, mock } from "bun:test"

import type { FeedServices } from "@/lib/api/feed"
import type { Post, ThresholdEvent } from "@/lib/types"

mock.module("server-only", () => ({}))
const { getFeedWithServices } = await import("@/lib/api/feed")

const candidate: ThresholdEvent = {
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
  created_by_user_id: "user-2",
  boost_count: 0,
  follower_count: 1,
  is_following: true,
  is_boosting: false,
  created_at: "2026-07-01T10:00:00.000Z",
  updated_at: "2026-07-01T10:00:00.000Z",
}

const announcement: Post = {
  id: "announcement-1",
  author: {
    id: "system",
    type: "consumer",
    handle: "threshold-events",
    displayName: "Threshold Events",
  },
  systemOwned: true,
  createdAtIso: "2026-07-01T10:00:00.000Z",
  editedAtIso: null,
  body: "New event: Bass Theory",
  mentions: [],
  tags: [],
  commentCount: 0,
  upCount: 0,
  downCount: 0,
  viewerVote: null,
  viewerIsAuthor: false,
  emojiReactions: [],
  media: [],
  eventId: "event-1",
  eventSlug: "bass-theory",
}

function services(overrides: Partial<FeedServices> = {}): FeedServices {
  return {
    auth: async () => ({
      user: { id: "viewer-1", username: "viewer" },
      onboarding_preferences: { city: "Warsaw" },
    }) as never,
    getFeedPosts: async () => [],
    listEventUpdates: async () => [],
    listNotifications: async () => ({ status: 200, body: [], setCookies: [] }),
    getFollowedTargets: async () => [
      {
        target_type: "page",
        target_id: "page-1",
        target_handle: "room-one",
        display_name: "Room One",
      },
      {
        target_type: "artist",
        target_id: "user-2",
        target_handle: "dj-one",
        display_name: "DJ One",
      },
    ],
    getEventFeedCandidates: async () => ({ items: [candidate], supported: true }),
    getEventAnnouncementPosts: async () => ({
      items: [announcement],
      representedEventIds: ["event-1"],
      representedEventSlugs: ["bass-theory"],
      legacyRepresentedEventSlugs: [],
      supported: true,
    }),
    getEventsBatchResult: async () => ({ items: [], supported: true }),
    listEvents: async () => [],
    getOrganizerRefs: async () => [],
    ...overrides,
  }
}

describe("feed orchestration", () => {
  it("requests candidates and announcements once with real viewer scopes", async () => {
    const candidateInputs: unknown[] = []
    const announcementInputs: string[][] = []
    let organizerCalls = 0
    const items = await getFeedWithServices("all", services({
      getEventFeedCandidates: async (input) => {
        candidateInputs.push(input)
        return { items: [candidate], supported: true }
      },
      getEventAnnouncementPosts: async (ids) => {
        announcementInputs.push(ids)
        return {
          items: [announcement],
          representedEventIds: ["event-1"],
          representedEventSlugs: ["bass-theory"],
          legacyRepresentedEventSlugs: [],
          supported: true,
        }
      },
      getOrganizerRefs: async () => {
        organizerCalls += 1
        return []
      },
    }))

    expect(candidateInputs).toEqual([{
      city: "Warsaw",
      followedPageIds: ["page-1"],
      followedCreatorUserIds: ["user-2"],
    }])
    expect(candidateInputs[0]).not.toHaveProperty("followedEventIds")
    expect(announcementInputs).toEqual([["event-1"]])
    expect(organizerCalls).toBe(1)
    expect(items.map((item) => item.kind)).toEqual(["post"])
  })

  it("uses the bounded event fallback when feed candidates are unsupported", async () => {
    let legacyCalls = 0
    const items = await getFeedWithServices("all", services({
      getEventFeedCandidates: async () => ({ items: [], supported: false }),
      listEvents: async () => {
        legacyCalls += 1
        return [candidate]
      },
      getEventAnnouncementPosts: async () => ({
        items: [],
        representedEventIds: [],
        representedEventSlugs: [],
        legacyRepresentedEventSlugs: [],
        supported: false,
      }),
    }))

    expect(legacyCalls).toBe(2)
    expect(items.map((item) => item.kind)).toEqual(["event"])
  })

  it("infers represented refs from visible system posts when announcement endpoint is missing", async () => {
    const items = await getFeedWithServices("all", services({
      getFeedPosts: async () => [announcement],
      getEventAnnouncementPosts: async () => ({
        items: [],
        representedEventIds: [],
        representedEventSlugs: [],
        legacyRepresentedEventSlugs: [],
        supported: false,
      }),
    }))

    expect(items.map((item) => item.kind)).toEqual(["post"])
  })

  it("suppresses blocked or hidden represented announcements", async () => {
    const items = await getFeedWithServices("all", services({
      getEventAnnouncementPosts: async () => ({
        items: [],
        representedEventIds: ["event-1"],
        representedEventSlugs: ["bass-theory"],
        legacyRepresentedEventSlugs: [],
        supported: true,
      }),
    }))

    expect(items).toEqual([])
  })

  it("keeps standalone fallback when a deleted announcement is not represented", async () => {
    const items = await getFeedWithServices("all", services({
      getEventAnnouncementPosts: async () => ({
        items: [],
        representedEventIds: [],
        representedEventSlugs: [],
        legacyRepresentedEventSlugs: [],
        supported: true,
      }),
    }))

    expect(items.map((item) => item.kind)).toEqual(["event"])
  })
})
