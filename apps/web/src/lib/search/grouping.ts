import type { SearchResult, SearchResultGroup } from "@/lib/types"

const GROUPS: { id: SearchResultGroup["id"]; types: SearchResult["type"][] }[] = [
  { id: "profiles", types: ["consumer", "artist"] },
  { id: "pages", types: ["club", "collective", "project", "festival", "unknown"] },
  { id: "groups", types: ["group"] },
  { id: "events", types: ["event"] },
]

export function groupSearchResults(results: SearchResult[]): SearchResultGroup[] {
  return GROUPS.map((group) => ({
    id: group.id,
    items: results.filter((result) => group.types.includes(result.type)),
  })).filter((group) => group.items.length > 0)
}

export function searchSuggestions(): { id: "events" | "groups" | "pages"; href: string }[] {
  return [
    { id: "events", href: "/app/events" },
    { id: "groups", href: "/groups" },
    { id: "pages", href: "/app/pages" },
  ]
}
