import type { ThresholdEvent } from "@/lib/types"

export type EventDraft = {
  title: string; slug: string; page_id: string; starts_at: string; city: string
  description: string; genres: string; location_mode: string; venue_name: string
  address: string; poster_media_asset_id: string; lineup: Record<string, string>[]
}

export function eventDraft(event?: ThresholdEvent): EventDraft {
  return {
    title: event?.title ?? "", slug: event?.slug ?? "", page_id: event?.page_id ?? "",
    starts_at: event ? new Date(event.starts_at).toISOString().slice(0, -1) : "",
    city: event?.city ?? "", description: event?.description ?? "", genres: event?.genres.join(", ") ?? "",
    location_mode: event?.location_mode ?? "public_location", venue_name: event?.venue_name ?? "",
    address: event?.address ?? "", poster_media_asset_id: event?.poster_media_asset_id ?? "",
    lineup: event?.lineup.map(item => typeof item === "string" ? { name: item } : { ...item }) ?? [],
  }
}

export class EventValidationError extends Error {
  constructor(public field: keyof EventDraft) { super(field) }
}

function utcTime(value: string): string {
  if (!/^\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d{1,3})?)?$/.test(value)) throw new EventValidationError("starts_at")
  const date = new Date(`${value}Z`)
  if (!Number.isFinite(date.getTime()) || !date.toISOString().startsWith(value)) throw new EventValidationError("starts_at")
  return date.toISOString()
}

export function eventPayload(draft: EventDraft, original?: ThresholdEvent): Record<string, unknown> {
  const before = original ? eventDraft(original) : null
  const payload: Record<string, unknown> = {}
  const changed = (key: keyof EventDraft) => !before || JSON.stringify(draft[key]) !== JSON.stringify(before[key])
  const bounded: [keyof EventDraft, number, boolean][] = [
    ["title", 160, true], ["city", 120, true], ["description", 4000, false],
    ["venue_name", 160, false], ["address", 400, false], ["poster_media_asset_id", 36, false],
  ]
  for (const [key, max, required] of bounded) {
    if (!changed(key)) continue
    const value = draft[key] as string
    if (value.length > max || (required && !value.trim())) throw new EventValidationError(key)
    payload[key] = value || null
  }
  if (!original) {
    if (!/^[a-z0-9-]{3,160}$/.test(draft.slug)) throw new EventValidationError("slug")
    if (draft.page_id.length !== 36) throw new EventValidationError("page_id")
    payload.slug = draft.slug
    payload.page_id = draft.page_id
  }
  if (changed("starts_at")) payload.starts_at = utcTime(draft.starts_at)
  if (changed("location_mode")) {
    if (!["public_location", "tba"].includes(draft.location_mode)) throw new EventValidationError("location_mode")
    payload.location_mode = draft.location_mode
  }
  if (changed("genres")) {
    const genres = draft.genres.split(",").map(s => s.trim()).filter(Boolean)
    if (genres.length > 10 || genres.some(s => s.length > 40)) throw new EventValidationError("genres")
    payload.genres = genres
  }
  if (changed("lineup")) {
    if (draft.lineup.length > 100 || draft.lineup.some(item => !item.name?.trim() || item.name.length > 160 || (item.artist_profile_id?.length ?? 0) > 36)) throw new EventValidationError("lineup")
    payload.lineup = draft.lineup.map(item => ({ ...item }))
  }
  return payload
}

export function lineupWithReference(item: Record<string, string>, reference: string): Record<string, string> {
  if ((item.artist_profile_id ?? "") === reference) return { ...item }
  const next = { ...item }
  for (const key of ["artist_profile_id", "artist_handle", "display_name", "target_url"]) delete next[key]
  if (reference) next.artist_profile_id = reference
  return next
}
