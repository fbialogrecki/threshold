import { describe, expect, it } from "bun:test"

import {
  initialQrState,
  qrExpired,
  qrExpiryDelay,
  qrReducer,
} from "@/lib/events/qr-lifecycle"

describe("QR lifecycle", () => {
  it("ignores stale generations and clears token material", () => {
    const loading = qrReducer(initialQrState, { type: "begin", generation: 2 })
    expect(qrReducer(loading, {
      type: "resolve",
      generation: 1,
      token: "stale-secret",
      expiresAt: "2030-01-01T00:00:00Z",
    })).toEqual(loading)

    const ready = qrReducer(loading, {
      type: "resolve",
      generation: 2,
      token: "current-secret",
      expiresAt: "2030-01-01T00:00:00Z",
    })
    expect(ready.status).toBe("ready")
    expect(qrReducer(ready, { type: "clear", generation: 3 })).toEqual({
      generation: 3,
      status: "idle",
      token: "",
      expiresAt: "",
    })
  })

  it("clears token material on expiry", () => {
    const ready = {
      generation: 4,
      status: "ready" as const,
      token: "short-lived-secret",
      expiresAt: "2026-07-10T10:00:01Z",
    }
    expect(qrReducer(ready, { type: "expire", generation: 4 })).toEqual({
      generation: 4,
      status: "expired",
      token: "",
      expiresAt: "",
    })
    expect(qrExpired(ready.expiresAt, Date.parse("2026-07-10T10:00:01Z"))).toBe(true)
    expect(qrExpiryDelay(ready.expiresAt, Date.parse("2026-07-10T10:00:00Z"))).toBe(1000)
  })
})
