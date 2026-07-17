import { describe, expect, it } from "bun:test"

import { recoverSession } from "@/lib/auth/recovery"

describe("session recovery", () => {
  it("posts to same-origin logout before navigating to a safe callback", async () => {
    const calls: Array<{ input: string; init?: RequestInit }> = []
    const navigations: string[] = []

    await recoverSession("/app/settings?tab=account#sessions", {
      fetcher: async (input, init) => {
        calls.push({ input: String(input), init })
        return new Response(null, { status: 204 })
      },
      navigate: (href) => navigations.push(href),
    })

    expect(calls).toEqual([{
      input: "/api/auth/logout",
      init: {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "same-origin",
      },
    }])
    expect(navigations).toEqual([
      "/login?callbackUrl=%2Fapp%2Fsettings%3Ftab%3Daccount%23sessions",
    ])
  })

  it("sanitizes callbacks and still navigates when logout is unavailable", async () => {
    const navigations: string[] = []

    await recoverSession("//evil.test", {
      fetcher: async () => {
        throw new Error("offline")
      },
      navigate: (href) => navigations.push(href),
    })

    expect(navigations).toEqual(["/login?callbackUrl=%2Fapp"])
  })
})
