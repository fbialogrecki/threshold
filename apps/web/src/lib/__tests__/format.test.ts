import { describe, expect, it } from "bun:test"

import { formatEventDate, formatRelative } from "@/lib/format"

describe("formatEventDate", () => {
  it("formats an ISO date in UTC", () => {
    expect(formatEventDate("2026-06-14T21:00:00.000Z")).toBe("Sun, 14 Jun")
    expect(formatEventDate("2026-06-14T21:00:00.000Z", "pl")).toBe(
      new Intl.DateTimeFormat("pl-PL", {
        weekday: "short",
        day: "numeric",
        month: "short",
        timeZone: "UTC",
      }).format(new Date("2026-06-14T21:00:00.000Z")),
    )
  })

  it("returns empty string for invalid input", () => {
    expect(formatEventDate("not-a-date")).toBe("")
  })
})

describe("formatRelative", () => {
  const now = "2026-06-05T12:00:00.000Z"
  const en = new Intl.RelativeTimeFormat("en-GB", { numeric: "auto", style: "narrow" })

  it("returns now for very recent timestamps", () => {
    expect(formatRelative("2026-06-05T11:59:30.000Z", "en", now)).toBe(en.format(0, "second"))
  })

  it("returns minutes", () => {
    expect(formatRelative("2026-06-05T11:30:00.000Z", "en", now)).toBe(en.format(-30, "minute"))
  })

  it("returns hours", () => {
    expect(formatRelative("2026-06-05T09:00:00.000Z", "en", now)).toBe(en.format(-3, "hour"))
  })

  it("returns days", () => {
    expect(formatRelative("2026-06-03T12:00:00.000Z", "en", now)).toBe(en.format(-2, "day"))
  })

  it("uses the requested locale", () => {
    expect(formatRelative("2026-06-05T11:30:00.000Z", "pl", now)).toBe(
      new Intl.RelativeTimeFormat("pl-PL", { numeric: "auto", style: "narrow" })
        .format(-30, "minute"),
    )
  })
})
