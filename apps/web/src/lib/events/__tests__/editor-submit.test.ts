import { expect, test } from "bun:test"
import { saveEvent } from "../editor-submit"
import { eventDraft } from "../editor"
import { event } from "./editor.fixture"

test("edit uses encoded same-origin PATCH and only changed fields", async () => {
  const calls: unknown[] = []
  const saved = await saveEvent({ ...eventDraft(event), title: "New" }, event, null, async (url, init) => {
    calls.push([url, init?.method, JSON.parse(init?.body as string)])
    return Response.json({ slug: event.slug })
  })
  expect(calls).toEqual([[`/api/events/${event.slug}`, "PATCH", { title: "New" }]])
  expect(saved).toBe(`/events/${event.slug}`)
})
test("upload uses existing multipart event_poster path before create", async () => {
  const calls: string[] = []
  await saveEvent(eventDraft(event), undefined, new File(["image"], "poster.png", { type: "image/png" }), async (url, init) => {
    calls.push(String(url))
    if (url === "/api/media/assets") {
      expect((init?.body as FormData).get("context")).toBe("event_poster")
      expect((init?.body as FormData).get("file")).toBeInstanceOf(File)
      return Response.json({ id: "poster-id" }, { status: 201 })
    }
    expect(JSON.parse(init?.body as string).poster_media_asset_id).toBe("poster-id")
    return Response.json({ slug: "created" }, { status: 201 })
  })
  expect(calls).toEqual(["/api/media/assets", "/api/events"])
})
test("upload, validation, HTTP and network failures remain failures; original inputs survive", async () => {
  const draft = eventDraft(event)
  for (const status of [401, 403, 409, 422, 429, 503]) {
    await expect(saveEvent(draft, undefined, null, async () => Response.json({}, { status }))).rejects.toThrow()
  }
  await expect(saveEvent(draft, event, null, async () => { throw new Error("offline") })).rejects.toThrow()
  let calls = 0
  await expect(saveEvent(draft, undefined, new File(["x"], "x.png"), async () => { calls++; return Response.json({}, { status: 413 }) })).rejects.toThrow()
  expect(calls).toBe(1)
  expect(draft).toEqual(eventDraft(event))
})
