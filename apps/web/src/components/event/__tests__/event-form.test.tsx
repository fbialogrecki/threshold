import { expect, test } from "bun:test"
import { renderToStaticMarkup } from "react-dom/server"
import { NextIntlClientProvider } from "next-intl"
import { AppRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime"
import { EventForm } from "../event-form"
import en from "../../../../messages/en.json"
import pl from "../../../../messages/pl.json"
import { event } from "@/lib/events/__tests__/editor.fixture"

const router = { bfcacheId: "test", push() {}, refresh() {}, replace() {}, back() {}, forward() {}, prefetch() {} }
function render(edit: boolean, messages = en) {
  return renderToStaticMarkup(<AppRouterContext.Provider value={router}><NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}><EventForm pages={[{ id: event.page_id!, slug: "club", display_name: "Club", role: "editor", page_type: "club" }]} event={edit ? event : undefined} /></NextIntlClientProvider></AppRouterContext.Provider>)
}
test("native create form has every field, UTC label, page selector, lineup and optional upload", () => {
  const html = render(false)
  for (const name of ["title", "slug", "page_id", "starts_at", "city", "description", "genres", "location_mode", "venue_name", "address", "poster"]) expect(html).toContain(`name="${name}"`)
  expect(html).toContain("datetime-local")
  expect(html).toContain("UTC")
  expect(html).toContain("Add artist")
  expect(html).not.toContain('value="secret_location"')
})
test("edit form renders references, preserves fields and locks create-only identity in both locales", () => {
  for (const messages of [en, pl]) {
    const html = render(true, messages)
    expect(html).toContain('value="artist-id"')
    expect(html).toContain("Pending venue")
    expect(html).not.toContain('name="slug"')
    expect(html).not.toContain('name="page_id"')
  }
})
