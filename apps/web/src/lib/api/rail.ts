import "server-only"

import type { AccessSummary, TonightItem } from "@/lib/types"

/**
 * Access / tonight rail data depends on future organizer-managed event access.
 * Return empty states until real entitlements exist.
 */

export async function getYourAccess(): Promise<AccessSummary[]> {
  return []
}

export async function getTonight(): Promise<TonightItem[]> {
  return []
}
