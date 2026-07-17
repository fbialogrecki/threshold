import { describe, expect, it } from "bun:test"

import { safeInternalHref } from "@/lib/safe-href"

describe("safeInternalHref", () => {
  it("preserves valid internal paths, queries and hashes", () => {
    expect(safeInternalHref("/app")).toBe("/app")
    expect(safeInternalHref("/events/rave?tab=lineup")).toBe("/events/rave?tab=lineup")
    expect(safeInternalHref("/app/search?q=https%3A%2F%2Fexample.test#results")).toBe(
      "/app/search?q=https%3A%2F%2Fexample.test#results",
    )
    expect(safeInternalHref("/posts/a:b?time=12:30#part:2")).toBe(
      "/posts/a:b?time=12:30#part:2",
    )
  })

  it("rejects absolute and scheme-relative URLs", () => {
    expect(safeInternalHref("//evil.test", "/app")).toBe("/app")
    expect(safeInternalHref("https://evil.test", "/app")).toBe("/app")
    expect(safeInternalHref("javascript:alert(1)", "/app")).toBe("/app")
  })

  it("rejects raw and encoded backslash normalization", () => {
    for (const href of [
      "/\\evil.test",
      "/%5cevil.test",
      "/%5C%5Cevil.test",
      "/%255cevil.test",
      "/%25255cevil.test",
    ]) {
      expect(safeInternalHref(href, "/app")).toBe("/app")
    }
  })

  it("rejects encoded scheme-relative variants at multiple depths", () => {
    let deeplyEncoded = "//evil.test"
    for (let depth = 0; depth < 6; depth++) {
      deeplyEncoded = encodeURIComponent(deeplyEncoded)
    }
    for (const href of [
      "/%2fevil.test",
      "/%2F%2Fevil.test",
      "/%252F%252Fevil.test",
      "/%25252F%25252Fevil.test",
      `/${deeplyEncoded}`,
    ]) {
      expect(safeInternalHref(href, "/app")).toBe("/app")
    }
  })

  it("rejects controls and malformed encodings", () => {
    for (const href of [
      "/app\n//evil.test",
      "/app\n",
      "/app\u0000",
      "/%0d%0aLocation%3A%20https%3A%2F%2Fevil.test",
      "/%250aevil.test",
      "/bad%",
      "/bad%2",
      "/bad%zz",
    ]) {
      expect(safeInternalHref(href, "/app")).toBe("/app")
    }
  })
})
