import { describe, expect, it } from "bun:test"

import { groupSearchResults, searchSuggestions } from "@/lib/search/grouping"
import type { SearchResult } from "@/lib/types"

describe("groupSearchResults", () => {
  it("groups profiles, pages, groups and events in stable search order", () => {
    const results: SearchResult[] = [
      { type: "event", title: "Bass Theory", subtitle: "Berlin", href: "/events/bass-theory", handle: "bass-theory" },
      { type: "consumer", title: "Filip", subtitle: "", href: "/u/filip", handle: "filip" },
      { type: "club", title: "Tresor", subtitle: "Berlin", href: "/pages/tresor", handle: "tresor" },
      { type: "group", title: "Warsaw Techno", subtitle: "Warsaw", href: "/groups/warsaw-techno", handle: "warsaw-techno" },
      { type: "artist", title: "DJ One", subtitle: "Live Act", href: "/u/dj-one", handle: "dj-one" },
      { type: "project", title: "Live Project", subtitle: "Lodz", href: "/pages/live-project", handle: "live-project" },
      { type: "festival", title: "Night Festival", subtitle: "Krakow", href: "/pages/night-festival", handle: "night-festival" },
    ]

    expect(groupSearchResults(results)).toEqual([
      { id: "profiles", items: [results[1], results[4]] },
      { id: "pages", items: [results[2], results[5], results[6]] },
      { id: "groups", items: [results[3]] },
      { id: "events", items: [results[0]] },
    ])
  })
})

describe("searchSuggestions", () => {
  it("returns actionable empty-state suggestions", () => {
    expect(searchSuggestions()).toEqual([
      { id: "events", href: "/app/events" },
      { id: "groups", href: "/groups" },
      { id: "pages", href: "/app/pages" },
    ])
  })
})
