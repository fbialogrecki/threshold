import { describe, expect, it, mock } from "bun:test"

mock.module("server-only", () => ({}))
const { getEventFeedCandidates } = await import("@/lib/api/events")

function event(id: string, createdAt: string) {
  return {
    id,
    slug: id,
    title: id,
    description: null,
    starts_at: "2026-08-15T20:00:00Z",
    city: "Warsaw",
    location_mode: "public_location",
    venue_name: null,
    address: null,
    genres: [],
    lineup: [],
    page_id: null,
    poster_media_asset_id: null,
    created_by_user_id: null,
    boost_count: 0,
    follower_count: 0,
    is_following: false,
    is_boosting: false,
    created_at: createdAt,
    updated_at: createdAt,
  }
}

describe("events feed candidate client", () => {
  it("uses one base viewer call plus independent page and creator scopes", async () => {
    const calls: { path: string; options: Record<string, unknown> }[] = []
    const result = await getEventFeedCandidates({
      city: "Warsaw",
      followedPageIds: ["page-1"],
      followedCreatorUserIds: ["user-1"],
    }, async (path, options) => {
      calls.push({ path, options: options ?? {} })
      return { status: 200, body: [] }
    })

    expect(result).toEqual({ items: [], supported: true })
    expect(calls).toHaveLength(3)
    expect(calls[0].path).toBe("/internal/v1/events/feed-candidates")
    expect(calls[0].options).toMatchObject({
      method: "POST",
      includeViewer: true,
      requireViewer: false,
      json: {
        city: "Warsaw",
        followed_page_ids: [],
        followed_creator_user_ids: [],
        limit: 100,
      },
    })
    expect(calls[0].options.json).not.toHaveProperty("followed_event_ids")
    expect(calls[1].options).toMatchObject({
      includeViewer: false,
      json: {
        city: null,
        followed_page_ids: ["page-1"],
        followed_creator_user_ids: [],
      },
    })
    expect(calls[2].options).toMatchObject({
      includeViewer: false,
      json: {
        city: null,
        followed_page_ids: [],
        followed_creator_user_ids: ["user-1"],
      },
    })
  })

  it("chunks more than 100 ids without cross-product requests", async () => {
    const calls: Record<string, unknown>[] = []
    await getEventFeedCandidates({
      city: "Warsaw",
      followedPageIds: Array.from({ length: 205 }, (_, index) => `page-${index}`),
      followedCreatorUserIds: Array.from({ length: 101 }, (_, index) => `user-${index}`),
    }, async (_path, options) => {
      calls.push(options ?? {})
      return { status: 200, body: [] }
    })

    expect(calls).toHaveLength(6)
    const payloads = calls.map((call) => call.json as {
      followed_page_ids: string[]
      followed_creator_user_ids: string[]
    })
    expect(payloads.map((payload) => payload.followed_page_ids.length)).toEqual([
      0, 100, 100, 5, 0, 0,
    ])
    expect(payloads.map((payload) => payload.followed_creator_user_ids.length)).toEqual([
      0, 0, 0, 0, 100, 1,
    ])
    expect(payloads.every((payload) =>
      payload.followed_page_ids.length === 0
      || payload.followed_creator_user_ids.length === 0,
    )).toBeTrue()
  })

  it("dedupes merged scopes and sorts them newest first", async () => {
    let calls = 0
    const result = await getEventFeedCandidates({
      city: "Warsaw",
      followedPageIds: ["page-1"],
      followedCreatorUserIds: [],
    }, async () => {
      calls += 1
      return calls === 1
        ? { status: 200, body: [event("old", "2026-07-01T10:00:00Z")] }
        : {
            status: 200,
            body: [
              event("new", "2026-07-02T10:00:00Z"),
              event("old", "2026-07-01T10:00:00Z"),
            ],
          }
    })

    expect(result.items.map(({ id }) => id)).toEqual(["new", "old"])
  })

  it("marks old 404 and 405 endpoints for bounded fallback", async () => {
    const input = {
      city: "Warsaw",
      followedPageIds: [],
      followedCreatorUserIds: [],
    }
    for (const status of [404, 405]) {
      let calls = 0
      expect(await getEventFeedCandidates(
        input,
        async () => {
          calls += 1
          return { status, body: null }
        },
      )).toEqual({ items: [], supported: false })
      expect(calls).toBe(1)
    }
  })
})
