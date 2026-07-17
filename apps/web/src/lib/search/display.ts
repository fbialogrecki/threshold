import { cityLabel } from "@/lib/cities"
import { PAGE_TYPES, type PageType } from "@/lib/page-types"
import type { SearchResultType } from "@/lib/types"

export function searchResultType(value: string): SearchResultType {
  return [
    "artist",
    "consumer",
    "club",
    "collective",
    "project",
    "festival",
    "group",
    "event",
  ].includes(value)
    ? value as SearchResultType
    : "unknown"
}

export function searchSubtitle(
  type: SearchResultType,
  value: string | null,
  locale: string,
): string {
  return value && PAGE_TYPES.includes(type as PageType) ? cityLabel(value, locale) : value ?? ""
}
