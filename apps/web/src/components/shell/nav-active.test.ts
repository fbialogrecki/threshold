import { describe, expect, test } from "bun:test"

import { isNavActive } from "@/components/shell/nav-active"

describe("isNavActive", () => {
  test("maps detail routes to their primary destinations", () => {
    expect(isNavActive("/app", "/posts/post-1")).toBe(true)
    expect(isNavActive("/app/events", "/events/night-one")).toBe(true)
    expect(isNavActive("/groups", "/groups/warsaw-techno")).toBe(true)
  })

  test("keeps compose and notifications independently active", () => {
    expect(isNavActive("/app/compose", "/app/compose")).toBe(true)
    expect(isNavActive("/app", "/app/compose")).toBe(false)
    expect(isNavActive("/app/notifications", "/app/notifications/notice-1")).toBe(true)
  })

  test("does not match routes that only share a prefix", () => {
    expect(isNavActive("/groups", "/groupship")).toBe(false)
    expect(isNavActive("/app/events", "/events-old")).toBe(false)
  })
})
