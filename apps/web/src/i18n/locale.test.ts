import { describe, expect, test } from "bun:test"

import { resolveLocale } from "./locale"

describe("resolveLocale", () => {
  test("prefers a supported cookie", () => {
    expect(resolveLocale("pl", "en-US,en;q=0.9")).toBe("pl")
  })

  test("uses weighted supported languages from Accept-Language", () => {
    expect(resolveLocale(null, "de-DE, pl-PL;q=0.8, en;q=0.6")).toBe("pl")
    expect(resolveLocale(null, "pl;q=0.5, en-GB;q=0.9")).toBe("en")
  })

  test("preserves header order when quality is equal", () => {
    expect(resolveLocale(undefined, "pl-PL, en-US")).toBe("pl")
  })

  test("ignores invalid, unsupported, and refused locales", () => {
    expect(resolveLocale("de", "pl;q=0, de-DE, en;q=bogus")).toBe("en")
  })

  test("defaults to English without a supported preference", () => {
    expect(resolveLocale(undefined, null)).toBe("en")
  })
})
