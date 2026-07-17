import { describe, expect, test } from "bun:test"

import { absoluteMediaDerivativeUrl, mediaDerivativeUrl } from "@/lib/media/urls"

describe("media urls", () => {
  test("builds proxied derivative URL", () => {
    expect(mediaDerivativeUrl("asset 1", "avatar_512")).toBe(
      "/api/media/assets/assets/asset%201/avatar_512.webp",
    )
  })

  test("builds absolute metadata URL without raw storage keys", () => {
    const previous = process.env.NEXTAUTH_URL
    process.env.NEXTAUTH_URL = "https://threshold.example/"

    expect(absoluteMediaDerivativeUrl("asset-1", "avatar_512")).toBe(
      "https://threshold.example/api/media/assets/assets/asset-1/avatar_512.webp",
    )

    if (previous === undefined) {
      delete process.env.NEXTAUTH_URL
    } else {
      process.env.NEXTAUTH_URL = previous
    }
  })
})
