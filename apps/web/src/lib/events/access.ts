import type {
  DoorStaffAssignment,
  EventLineupItem,
  EventViewerContext,
} from "@/lib/types"

export type LineupArtistChoice = { id: string; name: string }

export function lineupArtistChoices(lineup: EventLineupItem[]): LineupArtistChoice[] {
  const seen = new Set<string>()
  return lineup.flatMap((item) => {
    if (typeof item === "string" || !item.artist_profile_id || seen.has(item.artist_profile_id)) {
      return []
    }
    seen.add(item.artist_profile_id)
    return [{ id: item.artist_profile_id, name: item.display_name ?? item.name }]
  })
}

export function viewerArtistChoices(
  lineup: EventLineupItem[],
  context: EventViewerContext,
): LineupArtistChoice[] {
  const owned = new Set(context.viewer_lineup_artists.map((artist) => artist.artist_profile_id))
  return lineupArtistChoices(lineup).filter((artist) => owned.has(artist.id))
}

export function eventAccessSurfaces(context: EventViewerContext | null) {
  return {
    guest: !!context?.active_guest_access,
    managerGuestlist: !!context?.can_manage_guestlist,
    doorStaffManagement: !!context?.can_manage_guestlist,
    quotas: !!context?.can_set_dj_quota,
    djGuests: (context?.viewer_lineup_artists.length ?? 0) > 0,
    checkIn: !!context?.can_check_in,
    postUpdate: !!context?.can_post_update,
  }
}

export function eventLoginHref(slug: string): string {
  const callback = `/events/${encodeURIComponent(slug)}`
  return `/login?callbackUrl=${encodeURIComponent(callback)}`
}

export type MinimalCheckInResponse = {
  status: string
  display_name: string
  username?: string
}

export function minimalCheckInResponse(value: unknown): MinimalCheckInResponse | null {
  if (typeof value !== "object" || value === null) return null
  const body = value as Record<string, unknown>
  if (typeof body.status !== "string" || typeof body.display_name !== "string") return null
  return {
    status: body.status,
    display_name: body.display_name,
    ...(typeof body.username === "string" ? { username: body.username } : {}),
  }
}

export function minimalDoorStaffList(value: unknown): DoorStaffAssignment[] | null {
  if (!Array.isArray(value)) return null
  const result: DoorStaffAssignment[] = []
  for (const item of value) {
    const assignment = minimalDoorStaffAssignment(item)
    if (!assignment) return null
    result.push(assignment)
  }
  return result
}

export function minimalDoorStaffAssignment(value: unknown): DoorStaffAssignment | null {
  if (typeof value !== "object" || value === null) return null
  const row = value as Record<string, unknown>
  if (typeof row.id !== "string" || typeof row.assigned_at !== "string") return null
  return {
    id: row.id,
    username: typeof row.username === "string" ? row.username : null,
    display_name: typeof row.display_name === "string" ? row.display_name : null,
    assigned_at: row.assigned_at,
  }
}

export type MutationFailure = "unauthorized" | "forbidden" | "conflict" | "notFound" | "generic"

export function mutationFailure(status: number): MutationFailure {
  if (status === 401) return "unauthorized"
  if (status === 403) return "forbidden"
  if (status === 404) return "notFound"
  if (status === 409) return "conflict"
  return "generic"
}

export type CheckInErrorKey =
  | "mutationUnauthorized"
  | "mutationForbidden"
  | "alreadyCheckedIn"
  | "checkInError"

export function checkInErrorKey(status: number): CheckInErrorKey {
  if (status === 401) return "mutationUnauthorized"
  if (status === 403) return "mutationForbidden"
  if (status === 409) return "alreadyCheckedIn"
  return "checkInError"
}
