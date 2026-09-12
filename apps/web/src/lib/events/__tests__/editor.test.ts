import { expect, test } from "bun:test"
import { eventDraft, eventPayload, lineupWithReference } from "../editor"
import { event } from "./editor.fixture"


test("untouched edit sends no fields, preserving timestamp precision, poster ownership and rich metadata", () => {
  expect(eventPayload(eventDraft(event), event)).toEqual({})
})
test("title-only edits do not overwrite concurrent changes or rich lineup", () => {
  expect(eventPayload({ ...eventDraft(event), title: "Changed" }, event)).toEqual({ title: "Changed" })
})
test("lineup edits preserve artist references and unknown keys", () => {
  const draft = eventDraft(event)
  draft.lineup[0].name = "New billing"
  expect(eventPayload(draft, event)).toEqual({ lineup: [{ ...event.lineup[0] as object, name: "New billing" }] })
  expect((event.lineup[0] as { name: string }).name).toBe("Artist")
})
test("explicit UTC datetime conversion handles DST date and preserves seconds", () => {
  const draft = eventDraft(event)
  expect(draft.starts_at).toBe("2026-10-25T00:30:42.123")
  expect(eventPayload({ ...draft, starts_at: "2026-10-25T01:30" }, event)).toEqual({ starts_at: "2026-10-25T01:30:00.000Z" })
})
test("creation uses supported schema and requires a managed page and bounded values", () => {
  const draft = { ...eventDraft(event), slug: "new-night" }
  expect(eventPayload(draft)).toMatchObject({ slug: "new-night", page_id: event.page_id, starts_at: "2026-10-25T00:30:42.123Z" })
  for (const patch of [ { title: " " }, { title: "a".repeat(161) }, { city: "" }, { slug: "bad/slug" }, { page_id: "" }, { starts_at: "2026-02-30T10:00" }, { location_mode: "secret_location" }, { genres: Array(11).fill("techno").join(",") }, { lineup: [{ name: "", artist_profile_id: "a" }] } ]) {
    expect(() => eventPayload({ ...draft, ...patch })).toThrow()
  }
})
test("clearing optional values is explicit and editing never sends create-only identity", () => {
  expect(eventPayload({ ...eventDraft(event), description: "", poster_media_asset_id: "", slug: "forged", page_id: "forged" }, event)).toEqual({ description: null, poster_media_asset_id: null })
})

test("unlinking or replacing an artist clears stale public identity links but retains custom metadata", () => {
  const item = { name: "Billing", artist_profile_id: "old", artist_handle: "Old", display_name: "Old", target_url: "/u/Old", slot: "03:00" }
  expect(lineupWithReference(item, "")).toEqual({ name: "Billing", slot: "03:00" })
  expect(lineupWithReference(item, "new")).toEqual({ name: "Billing", slot: "03:00", artist_profile_id: "new" })
  expect(lineupWithReference(item, "old")).toEqual(item)
})
