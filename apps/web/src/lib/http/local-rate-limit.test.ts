import { describe, expect, it } from "bun:test"

import {
  LocalFixedWindowRateLimiter,
  rateLimitResponse,
  requestClientKey,
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

  it("stays memory-bounded by evicting the oldest local window", () => {
    const limiter = new LocalFixedWindowRateLimiter({ maxEntries: 2, now: () => 1_000 })
    limiter.consume("one", { limit: 1, windowMs: 60_000 })
    limiter.consume("two", { limit: 1, windowMs: 60_000 })
    limiter.consume("three", { limit: 1, windowMs: 60_000 })
    expect(limiter.size).toBe(2)
    expect(limiter.consume("one", { limit: 1, windowMs: 60_000 })).toEqual({ allowed: true })
  })

  it("keys on the first proxy-provided address without retaining user input", () => {
    const request = new Request("https://threshold.test/api/auth/login", {
      headers: { "x-forwarded-for": "203.0.113.8, 10.0.0.4" },
    })
    expect(requestClientKey(request)).toBe("203.0.113.8")
    expect(requestClientKey(new Request("https://threshold.test"))).toBe("unknown")
  })

  it("emits Retry-After on the bounded 429 response", async () => {
    const response = rateLimitResponse(17)
    expect(response.status).toBe(429)
    expect(response.headers.get("retry-after")).toBe("17")
    expect(await response.json()).toEqual({ error: "too many attempts" })
  })
})
