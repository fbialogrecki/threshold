import { describe, expect, it } from "bun:test"

import { planAuthCookieMutations } from "@/lib/auth/cookie-policy"

describe("planAuthCookieMutations", () => {
  it("rewrites the refresh cookie path from /v1/auth to /api/auth", () => {
    const [mutation] = planAuthCookieMutations(
      ["threshold_refresh=abc123; Path=/v1/auth; HttpOnly; Max-Age=2592000"],
      false,
    )
    expect(mutation.name).toBe("threshold_refresh")
    expect(mutation.value).toBe("abc123")
    expect(mutation.path).toBe("/api/auth")
    expect(mutation.maxAge).toBe(2592000)
  })

  it("keeps the session cookie at root path", () => {
    const [mutation] = planAuthCookieMutations(
      ["threshold_session=tok; Path=/; HttpOnly; Max-Age=900"],
      false,
    )
    expect(mutation.path).toBe("/")
    expect(mutation.maxAge).toBe(900)
  })

  it("always marks cookies HttpOnly + SameSite=Lax and honors the secure flag", () => {
    const [insecure] = planAuthCookieMutations(
      ["threshold_session=tok; Path=/"],
      false,
    )
    expect(insecure.httpOnly).toBe(true)
    expect(insecure.sameSite).toBe("lax")
    expect(insecure.secure).toBe(false)

    const [secure] = planAuthCookieMutations(["threshold_session=tok; Path=/"], true)
    expect(secure.secure).toBe(true)
  })

  it("treats Max-Age=0 as a deletion", () => {
    const [mutation] = planAuthCookieMutations(
      ['threshold_session=""; Path=/; Max-Age=0'],
      false,
    )
    expect(mutation.value).toBe("")
    expect(mutation.maxAge).toBe(0)
  })

  it("treats a past Expires as a deletion", () => {
    const [mutation] = planAuthCookieMutations(
      [
        "threshold_refresh=gone; Path=/v1/auth; Expires=Thu, 01 Jan 1970 00:00:00 GMT",
      ],
      false,
    )
    expect(mutation.value).toBe("")
    expect(mutation.maxAge).toBe(0)
    expect(mutation.path).toBe("/api/auth")
  })

  it("bridges multiple Set-Cookie headers in one pass", () => {
    const mutations = planAuthCookieMutations(
      [
        "threshold_session=s; Path=/; HttpOnly; Max-Age=900",
        "threshold_refresh=r; Path=/v1/auth; HttpOnly; Max-Age=2592000",
      ],
      false,
    )
    expect(mutations).toHaveLength(2)
    expect(mutations.map((m) => m.path)).toEqual(["/", "/api/auth"])
  })

  it("propagates an upstream session deletion pair", () => {
    const mutations = planAuthCookieMutations(
      [
        "threshold_session=; Path=/; Max-Age=0",
        "threshold_refresh=; Path=/v1/auth; Max-Age=0",
      ],
      true,
    )

    expect(mutations).toEqual([
      {
        name: "threshold_session",
        value: "",
        path: "/",
        httpOnly: true,
        secure: true,
        sameSite: "lax",
        maxAge: 0,
      },
      {
        name: "threshold_refresh",
        value: "",
        path: "/api/auth",
        httpOnly: true,
        secure: true,
        sameSite: "lax",
        maxAge: 0,
      },
    ])
  })

  it("skips malformed headers", () => {
    expect(planAuthCookieMutations(["", "novalue"], false)).toHaveLength(0)
  })
})
