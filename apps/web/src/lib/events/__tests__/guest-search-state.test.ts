import { describe, expect, it } from "bun:test"

import {
  guestSearchReducer,
  initialGuestSearchState,
} from "@/lib/events/guest-search-state"
import type { SearchResult } from "@/lib/types"

const people: SearchResult[] = [
  { type: "consumer", title: "Ada", subtitle: "", href: "/u/ada", handle: "ada" },
  { type: "artist", title: "Bob", subtitle: "", href: "/u/bob", handle: "bob" },
]

describe("guest search state", () => {
  it("clears stale results while a new request loads", () => {
    const loaded = guestSearchReducer(
      guestSearchReducer(initialGuestSearchState, { type: "query", query: "ad", requestId: 1 }),
      { type: "success", requestId: 1, results: people },
    )
    const loading = guestSearchReducer(loaded, { type: "query", query: "bo", requestId: 2 })
    expect(loading.status).toBe("loading")
    expect(loading.results).toEqual([])
    expect(loading.open).toBe(false)
  })

  it("ignores stale responses and wraps keyboard navigation", () => {
    const loading = guestSearchReducer(initialGuestSearchState, {
      type: "query",
      query: "ad",
      requestId: 2,
    })
    expect(guestSearchReducer(loading, {
      type: "success",
      requestId: 1,
      results: people,
    })).toEqual(loading)

    const loaded = guestSearchReducer(loading, {
      type: "success",
      requestId: 2,
      results: people,
    })
    expect(guestSearchReducer(loaded, { type: "move", direction: -1 }).activeIndex).toBe(1)
  })

  it("distinguishes errors from empty successful results", () => {
    const loading = guestSearchReducer(initialGuestSearchState, {
      type: "query",
      query: "zz",
      requestId: 1,
    })
    expect(guestSearchReducer(loading, { type: "error", requestId: 1 }).status).toBe("error")
    expect(guestSearchReducer(loading, {
      type: "success",
      requestId: 1,
      results: [],
    }).status).toBe("success")
  })
})
