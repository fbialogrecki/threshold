import { describe, expect, it } from "bun:test"

import { mediaCacheControl } from "@/lib/media/cache"

describe("mediaCacheControl", () => {
  it("uses immutable caching only for successful assets", () => {
    expect(mediaCacheControl(200)).toBe("public, max-age=31536000, immutable")
    expect(mediaCacheControl(206)).toBe("public, max-age=31536000, immutable")
  })

  it("does not cache transient missing or failed responses", () => {
    expect(mediaCacheControl(404)).toBe("no-store")
    expect(mediaCacheControl(503)).toBe("no-store")
  })
})
