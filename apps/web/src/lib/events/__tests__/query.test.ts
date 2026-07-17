import { describe, expect, it } from "bun:test"

import {
  buildEventListQuery,
  feedEventScopes,
  feedIncludesEvents,
} from "../query"

describe("buildEventListQuery", () => {
  it("passes the viewer city to the Events API with existing filters", () => {
    expect(buildEventListQuery({
      city: "Wroclaw",
      limit: 25,
      sort: "created",
      pageId: "page-1",
    }).toString()).toBe("limit=25&sort=created&city=Wroclaw&page_id=page-1")
  })

  it("requests the explicit chronological upcoming contract", () => {
    expect(buildEventListQuery({ upcoming: true }).toString())
      .toBe("limit=100&sort=starts&upcoming=true")
  })
})

describe("feedEventScopes", () => {
  it("canonicalizes localized city display text for the Events API", () => {
    expect(feedEventScopes("Wrocław", "all")).toEqual([
      { sort: "created", city: "Wroclaw" },
      { sort: "created" },
    ])
  })

  it("uses one full source when the viewer has no city", () => {
    expect(feedEventScopes(null, "events")).toEqual([{ sort: "created" }])
  })

  it("makes no event requests for posts and access filters", () => {
    expect(feedIncludesEvents("posts")).toBeFalse()
    expect(feedIncludesEvents("access")).toBeFalse()
    expect(feedEventScopes("Warsaw", "posts")).toEqual([])
    expect(feedEventScopes("Warsaw", "access")).toEqual([])
  })
})
