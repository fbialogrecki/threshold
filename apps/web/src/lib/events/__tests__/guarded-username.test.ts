import { describe, expect, it } from "bun:test"

import { guardThenResolveUsername } from "@/lib/events/guarded-username"

describe("guarded username lookup", () => {
  it("stops before body parsing and lookup when the guard blocks", async () => {
    const calls: string[] = []
    const result = await guardThenResolveUsername({
      guard: async () => {
        calls.push("guard")
        return new Response(null, { status: 403 })
      },
      read: async () => {
        calls.push("read")
        return { username: "ada" }
      },
      username: (input) => input.username,
      resolve: async () => {
        calls.push("resolve")
        return { id: "user-1" }
      },
    })
    expect(result.kind).toBe("blocked")
    expect(calls).toEqual(["guard"])
  })

  it("orders guard, input validation, then internal lookup", async () => {
    const calls: string[] = []
    const result = await guardThenResolveUsername({
      guard: async () => {
        calls.push("guard")
        return null
      },
      read: async () => {
        calls.push("read")
        return { username: "ada" }
      },
      username: (input) => input.username,
      resolve: async (username) => {
        calls.push(`resolve:${username}`)
        return { id: "user-1" }
      },
    })
    expect(result.kind).toBe("resolved")
    expect(calls).toEqual(["guard", "read", "resolve:ada"])
  })
})
