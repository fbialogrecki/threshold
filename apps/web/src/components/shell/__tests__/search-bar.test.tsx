import { expect, test } from "bun:test"
import { NextIntlClientProvider } from "next-intl"
import { AppRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime"
import { renderToStaticMarkup } from "react-dom/server"

import messages from "../../../../messages/en.json"
import { SearchBar } from "../search-bar"

const router = { bfcacheId: "test", push() {}, refresh() {}, replace() {}, back() {}, forward() {}, prefetch() {} }

test("simultaneous sidebar and page searches own unique accessible IDs", () => {
  const html = renderToStaticMarkup(
    <AppRouterContext.Provider value={router}>
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}>
        <SearchBar compact />
        <SearchBar initialQuery="Local" />
      </NextIntlClientProvider>
    </AppRouterContext.Provider>,
  )
  const inputs = [...html.matchAll(/<input\b[^>]*>/g)].map(([tag]) => tag)
  const ids = inputs.map((input) => input.match(/\bid="([^"]+)"/)?.[1])
  expect(inputs).toHaveLength(2)
  expect(ids.every(Boolean)).toBe(true)
  expect(new Set(ids).size).toBe(2)
  for (const [index, id] of ids.entries()) {
    expect(html).toContain(`for="${id}"`)
    expect(inputs[index]).toContain(`aria-controls="${id}-suggestions"`)
    expect(inputs[index]).toContain('role="combobox"')
  }
})
