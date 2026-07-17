import { describe, expect, it } from "bun:test"

import {
  checkInErrorKey,
  eventAccessSurfaces,
  eventLoginHref,
  lineupArtistChoices,
  minimalCheckInResponse,
  minimalDoorStaffAssignment,
  mutationFailure,
  viewerArtistChoices,
} from "@/lib/events/access"
import type { EventViewerContext } from "@/lib/types"

const context: EventViewerContext = {
  event_id: "event-1",
  event_slug: "night",
  active_guest_access: null,
  can_mint_qr: false,
  can_manage_guestlist: false,
  can_set_dj_quota: false,
  can_check_in: false,
  can_post_update: false,
  viewer_lineup_artists: [{ artist_profile_id: "artist-2", quota: null }],
  quota_summaries: [],
}

describe("event access lineup choices", () => {
  const lineup = [
    { artist_profile_id: "artist-1", name: "One" },
    { artist_profile_id: "artist-2", name: "Two", display_name: "DJ Two" },
    { artist_profile_id: "artist-2", name: "Duplicate" },
    "Unlinked artist",
  ]

  it("offers only linked lineup artists to managers", () => {
    expect(lineupArtistChoices(lineup)).toEqual([
      { id: "artist-1", name: "One" },
      { id: "artist-2", name: "DJ Two" },
    ])
  })

  it("limits DJ choices to server-provided owned artists", () => {
    expect(viewerArtistChoices(lineup, context)).toEqual([
      { id: "artist-2", name: "DJ Two" },
    ])
  })
})

describe("event access capability surfaces", () => {
  it("shows only check-in for a door-only viewer", () => {
    expect(eventAccessSurfaces({ ...context, can_check_in: true, viewer_lineup_artists: [] })).toEqual({
      guest: false,
      managerGuestlist: false,
      doorStaffManagement: false,
      quotas: false,
      djGuests: false,
      checkIn: true,
      postUpdate: false,
    })
  })

  it("keeps manager, DJ, and check-in capabilities independent", () => {
    const surfaces = eventAccessSurfaces({
      ...context,
      can_manage_guestlist: true,
      can_set_dj_quota: true,
      can_check_in: true,
      can_post_update: true,
    })
    expect(surfaces.managerGuestlist).toBe(true)
    expect(surfaces.djGuests).toBe(true)
    expect(surfaces.checkIn).toBe(true)
    expect(surfaces.postUpdate).toBe(true)
  })
})

describe("event access boundaries", () => {
  it("allowlists only minimal check-in fields", () => {
    expect(minimalCheckInResponse({
      status: "checked_in",
      display_name: "Guest",
      username: "guest",
      guest_user_id: "secret-id",
      event_slug: "secret-night",
    })).toEqual({
      status: "checked_in",
      display_name: "Guest",
      username: "guest",
    })
    expect(minimalCheckInResponse({ status: "ok", guest_user_id: "id" })).toBeNull()
  })

  it("allowlists door staff assignment fields without user IDs", () => {
    expect(minimalDoorStaffAssignment({
      id: "assignment-1",
      username: "door",
      display_name: "Door Person",
      assigned_at: "2026-07-10T10:00:00Z",
      user_id: "private-user-id",
    })).toEqual({
      id: "assignment-1",
      username: "door",
      display_name: "Door Person",
      assigned_at: "2026-07-10T10:00:00Z",
    })
  })

  it("encodes the event callback as one internal path", () => {
    expect(eventLoginHref("night?next=https://evil.example")).toBe(
      "/login?callbackUrl=%2Fevents%2Fnight%253Fnext%253Dhttps%253A%252F%252Fevil.example",
    )
  })

  it("classifies mutation failures without exposing upstream bodies", () => {
    expect([401, 403, 404, 409, 500].map(mutationFailure)).toEqual([
      "unauthorized",
      "forbidden",
      "notFound",
      "conflict",
      "generic",
    ])
  })

  it("maps check-in statuses to dedicated localized errors", () => {
    expect([401, 403, 404, 409, 500].map(checkInErrorKey)).toEqual([
      "mutationUnauthorized",
      "mutationForbidden",
      "checkInError",
      "alreadyCheckedIn",
      "checkInError",
    ])
  })
})
