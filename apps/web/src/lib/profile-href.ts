import type { ProfileRef } from "@/lib/types"
import { PAGE_TYPES, type PageType } from "@/lib/page-types"
import { safeInternalHref } from "@/lib/safe-href"

export function profileHref(ref: Pick<ProfileRef, "type" | "handle" | "href">): string {
  const explicit = safeInternalHref(ref.href)
  if (explicit) return explicit
  if (PAGE_TYPES.includes(ref.type as PageType)) {
    return `/pages/${ref.handle}`
  }
  return `/u/${ref.handle}`
}
