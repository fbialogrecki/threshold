import { expect, test } from "bun:test"
import { loadEventEditor } from "../editor-access"
import { event } from "./editor.fixture"

const page = { id: event.page_id!, slug: "page", display_name: "Page", role: "editor", page_type: "club" }
function services(status = "authenticated", role = "editor") {
  const calls: string[] = []
  return { calls, getSessionState: async () => ({ status }), listManagedPages: async () => { calls.push("pages"); return { status: 200, body: [{ ...page, role }] } }, getEventViewerContext: async () => { calls.push("context"); return { event_slug: event.slug, can_post_update: true } }, getEvent: async () => { calls.push("event"); return event } }
}
test("anonymous and unavailable auth cannot fetch organizer data", async () => {
  for (const status of ["anonymous", "invalid", "unavailable"]) {
    const deps = services(status)
    expect((await loadEventEditor(event.slug, deps)).status).not.toBe("ready")
    expect(deps.calls).toEqual([])
  }
})
test("owner/admin/editor can create and edit; outsider cannot", async () => {
  for (const role of ["owner", "admin", "editor"]) {
    expect((await loadEventEditor(undefined, services("authenticated", role))).status).toBe("ready")
    expect((await loadEventEditor(event.slug, services("authenticated", role))).status).toBe("ready")
  }
  const outsider = services("authenticated", "viewer")
  expect((await loadEventEditor(event.slug, outsider)).status).toBe("forbidden")
  expect(outsider.calls).toEqual(["pages"])
})
test("viewer context gate precedes event data and membership must match event page", async () => {
  const deps = services()
  deps.getEventViewerContext = async () => ({ event_slug: event.slug, can_post_update: false })
  expect((await loadEventEditor(event.slug, deps)).status).toBe("forbidden")
  expect(deps.calls).not.toContain("event")
  const other = services()
  other.listManagedPages = async () => ({ status: 200, body: [{ ...page, id: "other-page" }] })
  expect((await loadEventEditor(event.slug, other)).status).toBe("forbidden")
})
test("failed memberships fail closed with retryable state", async () => {
  const deps = services()
  deps.listManagedPages = async () => { throw new Error("offline") }
  expect((await loadEventEditor(undefined, deps)).status).toBe("unavailable")
})
