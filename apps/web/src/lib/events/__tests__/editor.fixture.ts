import type { ThresholdEvent } from "@/lib/types"
export const event = {
  id: "event", slug: "night-shift", title: "Night shift", page_id: "00000000-0000-0000-0000-000000000001",
  starts_at: "2026-10-25T02:30:42.123456+02:00", city: "Warszawa", description: "  keep spacing  ",
  location_mode: "tba", venue_name: "Pending venue", address: "Pending address", genres: ["Techno"],
  poster_media_asset_id: "00000000-0000-0000-0000-000000000002",
  lineup: [{ name: "Artist", artist_profile_id: "artist-id", slot: "03:00", custom: "keep", display_name: "Artist", target_url: "/u/Artist" }],
} as unknown as ThresholdEvent
