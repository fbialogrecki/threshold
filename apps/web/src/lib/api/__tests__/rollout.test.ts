import { describe, expect, it } from "bun:test"

import { isUnsupportedEndpoint } from "@/lib/api/rollout"

describe("mixed-version endpoint fallback", () => {
  it("falls back only for missing or method-unsupported endpoints", () => {
    expect(isUnsupportedEndpoint(404)).toBeTrue()
    expect(isUnsupportedEndpoint(405)).toBeTrue()
    expect(isUnsupportedEndpoint(401)).toBeFalse()
    expect(isUnsupportedEndpoint(500)).toBeFalse()
  })
})
