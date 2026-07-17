import { describe, expect, it } from "bun:test"

import { searchResultType, searchSubtitle } from "@/lib/search/display"

describe("search display mappings", () => {
  it("localizes known Page city subtitles without changing user content", () => {
    expect(searchSubtitle("club", "Wroclaw", "pl")).toBe("Wrocław")
    expect(searchSubtitle("artist", "Wroclaw", "pl")).toBe("Wroclaw")
  })

  it("maps unknown backend types to a neutral result type", () => {
    expect(searchResultType("future-page-type")).toBe("unknown")
    expect(searchResultType("festival")).toBe("festival")
  })
})
