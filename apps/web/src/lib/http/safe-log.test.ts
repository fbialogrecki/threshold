import { describe, expect, it } from "bun:test"

import { safeLogFailure } from "@/lib/http/safe-log"

describe("safeLogFailure", () => {
  it("logs only allowlisted metadata and never serializes the error", () => {
    const entries: unknown[] = []
    const secretError = new Error("alice@example.test Bearer secret-token raw upstream body")
    secretError.stack = "STACK secret-token"

    safeLogFailure({ service: "users", operation: "login", kind: "unavailable" }, secretError, (entry) => {
      entries.push(entry)
    })

    expect(entries).toEqual([{
      event: "upstream_request_failed",
      service: "users",
      operation: "login",
      kind: "unavailable",
    }])
    const serialized = JSON.stringify(entries)
    expect(serialized).not.toContain("alice@example.test")
    expect(serialized).not.toContain("secret-token")
    expect(serialized).not.toContain("upstream body")
    expect(serialized).not.toContain("STACK")
  })
})
