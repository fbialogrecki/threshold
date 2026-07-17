import { describe, expect, it } from "bun:test"

import {
  LocalFixedWindowRateLimiter,
  rateLimitResponse,
  requestClientKey,
  resolveTrustedProxyDepth,
} from "@/lib/http/local-rate-limit"

describe("single-instance local rate limiting", () => {
  it("blocks after the configured limit and reports an integer retry delay", () => {
    let now = 1_000
    const limiter = new LocalFixedWindowRateLimiter({ maxEntries: 10, now: () => now })
    expect(limiter.consume("login:client", { limit: 2, windowMs: 10_000 })).toEqual({ allowed: true })
    expect(limiter.consume("login:client", { limit: 2, windowMs: 10_000 })).toEqual({ allowed: true })
    expect(limiter.consume("login:client", { limit: 2, windowMs: 10_000 })).toEqual({
      allowed: false,
      retryAfterSeconds: 10,
    })

    now = 11_000
    expect(limiter.consume("login:client", { limit: 2, windowMs: 10_000 })).toEqual({ allowed: true })
  })

  it("fails closed at capacity without evicting active blocked windows", () => {
    const limiter = new LocalFixedWindowRateLimiter({ maxEntries: 2, now: () => 1_000 })
    limiter.consume("one", { limit: 1, windowMs: 60_000 })
    limiter.consume("two", { limit: 1, windowMs: 60_000 })
    expect(limiter.consume("one", { limit: 1, windowMs: 60_000 })).toEqual({
      allowed: false,
      retryAfterSeconds: 60,
    })
    expect(limiter.consume("three", { limit: 1, windowMs: 60_000 })).toEqual({
      allowed: false,
      retryAfterSeconds: 60,
    })
    expect(limiter.size).toBe(2)
    expect(limiter.consume("one", { limit: 1, windowMs: 60_000 })).toEqual({
      allowed: false,
      retryAfterSeconds: 60,
    })
  })

  it("uses one conservative fallback key when proxy trust is not configured", () => {
    const request = new Request("https://threshold.test/api/auth/login", {
      headers: { "x-forwarded-for": "203.0.113.8, 10.0.0.4" },
    })
    expect(requestClientKey(request)).toBe("unknown")
    expect(requestClientKey(new Request("https://threshold.test"))).toBe("unknown")
  })

  it("selects the configured proxy depth from the right of the forwarded chain", () => {
    const request = new Request("https://threshold.test/api/auth/login", {
      headers: { "x-forwarded-for": "spoofed, 203.0.113.8, 10.0.0.4" },
    })
    expect(requestClientKey(request, 2)).toBe("203.0.113.8")
    expect(requestClientKey(request, 1)).toBe("10.0.0.4")
  })

  it("falls back conservatively for invalid trust or forwarded chains", () => {
    const malformed = new Request("https://threshold.test", {
      headers: { "x-forwarded-for": "203.0.113.8, not-an-ip" },
    })
    expect(requestClientKey(malformed, 1)).toBe("unknown")
    expect(requestClientKey(malformed, 0)).toBe("unknown")
    expect(requestClientKey(malformed, 11)).toBe("unknown")
    expect(requestClientKey(new Request("https://threshold.test"), 1)).toBe("unknown")
    expect(requestClientKey(new Request("https://threshold.test", {
      headers: { "x-forwarded-for": "deadbeef" },
    }), 1)).toBe("unknown")
  })

  it("enables proxy-derived keys only for an explicit bounded depth", () => {
    expect(resolveTrustedProxyDepth("2")).toBe(2)
    expect(resolveTrustedProxyDepth(undefined)).toBeUndefined()
    expect(resolveTrustedProxyDepth("0")).toBeUndefined()
    expect(resolveTrustedProxyDepth("11")).toBeUndefined()
    expect(resolveTrustedProxyDepth("1 proxy")).toBeUndefined()
  })

  it("emits Retry-After on the bounded 429 response", async () => {
    const response = rateLimitResponse(17)
    expect(response.status).toBe(429)
    expect(response.headers.get("retry-after")).toBe("17")
    expect(await response.json()).toEqual({ error: "too many attempts" })
  })
})
