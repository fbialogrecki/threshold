import type { ProfileRef } from "@/lib/types"

/**
 * One public name per person: the unique registration username, which is what
 * `handle` holds for people. Pages are entities with a proper name, and their
 * `handle` is a slug — not something to show a reader.
 */
export function profileName(profile: ProfileRef): string {
  return profile.type === "artist" || profile.type === "consumer"
    ? profile.handle
    : profile.displayName
}
