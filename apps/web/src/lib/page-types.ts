export const PAGE_TYPES = ["club", "collective", "project", "festival"] as const

export type PageType = (typeof PAGE_TYPES)[number]
export type DisplayPageType = PageType | "unknown"
export type PageRole = "owner" | "admin" | "editor" | "unknown"

export function pageType(value: unknown): PageType {
  return PAGE_TYPES.includes(value as PageType) ? value as PageType : "club"
}

export function displayPageType(value: unknown): DisplayPageType {
  return PAGE_TYPES.includes(value as PageType) ? value as PageType : "unknown"
}

export function pageRole(value: unknown): PageRole {
  return value === "owner" || value === "admin" || value === "editor" ? value : "unknown"
}
