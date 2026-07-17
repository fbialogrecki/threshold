import { describe, expect, it } from "bun:test"

import {
  loginResponseStatus,
  mutationErrorKey,
  resetRequestStatus,
  sessionStatus,
} from "@/lib/auth/status"

describe("auth upstream status mapping", () => {
  it("recovers only invalid sessions and preserves transient failures", () => {
    expect(sessionStatus(false)).toBe("anonymous")
    expect(sessionStatus(true, 401)).toBe("invalid")
    expect(sessionStatus(true, 200)).toBe("authenticated")
    expect(sessionStatus(true, 429)).toBe("unavailable")
    expect(sessionStatus(true, 503)).toBe("unavailable")
    expect(sessionStatus(true)).toBe("unavailable")
  })

  it("preserves login 401 and 429 while mapping service failures", () => {
    expect(loginResponseStatus(200)).toBe(200)
    expect(loginResponseStatus(401)).toBe(401)
    expect(loginResponseStatus(429)).toBe(429)
    expect(loginResponseStatus(500)).toBe(503)
  })

  it("keeps reset anti-enumeration separate from service failure", () => {
    expect(resetRequestStatus(null)).toBe(200)
    expect(resetRequestStatus(200)).toBe(200)
    expect(resetRequestStatus(429)).toBe(429)
    expect(resetRequestStatus(500)).toBe(503)
  })

  it("maps mutation failures to localized error keys", () => {
    expect(mutationErrorKey(403)).toBe("forbidden")
    expect(mutationErrorKey(404)).toBe("notFound")
    expect(mutationErrorKey(429)).toBe("rateLimited")
    expect(mutationErrorKey(500)).toBe("serviceUnavailable")
  })
})
