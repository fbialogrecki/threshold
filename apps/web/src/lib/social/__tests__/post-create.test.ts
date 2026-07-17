import { describe, expect, it } from "bun:test"

import {
  buildPostPayload,
  canonicalPostPayload,
  canSubmitPost,
  createdPostMatchesEvent,
  validateSelectedEvent,
} from "@/lib/social/post-create"

describe("post composer contract", () => {
  it("builds trimmed image or event payloads without client event ids", () => {
    expect(buildPostPayload({
      body: "  New set tonight  ",
      eventSlug: "bass-theory",
    })).toEqual({
      body: "New set tonight",
      group_slug: null,
      event_slug: "bass-theory",
      mentions: [],
      media_asset_ids: [],
    })
    expect(buildPostPayload({
      body: "New set tonight",
      mediaAssetIds: ["asset-1", "asset-2"],
    })).toMatchObject({
      event_slug: null,
      media_asset_ids: ["asset-1", "asset-2"],
    })
    expect(canSubmitPost({ body: "  " })).toBe(false)
    expect(canSubmitPost({ body: "ready" })).toBe(true)
    expect(() => buildPostPayload({
      body: "conflict",
      eventSlug: "bass-theory",
      mediaAssetIds: ["asset-1"],
    })).toThrow("images or an event")
  })
})

describe("event selection validation", () => {
  it("normalizes and validates an existing event", async () => {
    const seen: string[] = []
    const result = await validateSelectedEvent(
      { event_slug: " Bass-Theory " },
      async (slug) => {
        seen.push(slug)
        return slug === "bass-theory"
          ? { status: 200, body: { id: "event-1", slug } }
          : { status: 404, body: null }
      },
    )

    expect(result).toEqual({
      ok: true,
      event: { id: "event-1", slug: "bass-theory" },
    })
    expect(seen).toEqual(["bass-theory"])
  })

  it("rejects invalid and missing selected events", async () => {
    expect(await validateSelectedEvent(
      { event_slug: "../private" },
      async () => ({ status: 200, body: null }),
    )).toEqual({ ok: false, error: "invalid event_slug", status: 422 })
    expect(await validateSelectedEvent(
      { event_slug: "missing-event" },
      async () => ({ status: 404, body: null }),
    )).toEqual({ ok: false, error: "event not found", status: 422 })
  })

  it("preserves upstream server failures during validation", async () => {
    expect(await validateSelectedEvent(
      { event_slug: "bass-theory" },
      async () => ({ status: 503, body: null }),
    )).toEqual({
      ok: false,
      error: "event validation unavailable",
      status: 503,
    })
  })

  it("overwrites untrusted event ids and detects older social responses", () => {
    const event = { id: "event-1", slug: "bass-theory" }
    expect(canonicalPostPayload({
      body: "linked",
      event_id: "client-controlled",
      event_slug: "bass-theory",
      media_asset_ids: [],
    }, event)).toMatchObject({
      event_id: "event-1",
      event_slug: "bass-theory",
    })
    expect(canonicalPostPayload({
      body: "conflict",
      event_slug: "bass-theory",
      media_asset_ids: ["asset-1"],
    }, event)).toBeNull()
    expect(createdPostMatchesEvent(
      { event_id: "event-1", event_slug: "bass-theory" },
      event,
    )).toBeTrue()
    expect(createdPostMatchesEvent(
      { event_slug: "bass-theory" },
      event,
    )).toBeFalse()
  })
})
