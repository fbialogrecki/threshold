import { describe, expect, test } from "bun:test"

import { saveSetup, validPages } from "@/lib/onboarding/setup"

const page = { display_name: "Basement", slug: "basement", page_type: "club" as const, about: "Music" }
const setup = { username: "DJZaba", city: "Warsaw", scenes: ["techno"], artist: null, pages: [] }

function response(status = 200, body: unknown = {}) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })
}

describe("registration setup", () => {
  test("skipped optional steps save only username and required city", async () => {
    const calls: string[] = []
    const request = (async (url: string) => { calls.push(url); return response() }) as typeof fetch
    expect(await saveSetup(setup, new Set(), request)).toEqual({ ok: true })
    expect(calls).toEqual(["/api/me/profile", "/api/onboarding"])
  })

  test("artist and multiple Pages are saved before city onboarding", async () => {
    const calls: { url: string; body: Record<string, unknown> }[] = []
    const request = (async (url: string, options?: RequestInit) => {
      calls.push({ url, body: JSON.parse(String(options?.body)) as Record<string, unknown> })
      return response(201)
    }) as typeof fetch
    const result = await saveSetup({ ...setup, artist: { role: "DJ", location: "Warsaw", url: "https://dj.example" }, pages: [page, { ...page, slug: "project", page_type: "project" }] }, new Set(), request)
    expect(result).toEqual({ ok: true })
    expect(calls.map((call) => call.url)).toEqual(["/api/me/profile", "/api/me/artist", "/api/pages", "/api/pages", "/api/onboarding"])
    expect(calls[1]?.body.links).toEqual([{ label: "Website", url: "https://dj.example" }])
    expect(calls[2]?.body).toMatchObject({ slug: "basement", page_type: "club", city: "Warsaw" })
  })

  test("failed onboarding retries without creating the same Page again", async () => {
    const calls: string[] = []
    let attempts = 0
    const request = (async (url: string) => {
      calls.push(url)
      if (url === "/api/onboarding" && attempts++ === 0) return response(502)
      return response(201)
    }) as typeof fetch
    const created = new Set<string>()
    expect(await saveSetup({ ...setup, pages: [page] }, created, request)).toEqual({ ok: false, step: "access", error: "save" })
    expect(await saveSetup({ ...setup, pages: [page] }, created, request)).toEqual({ ok: true })
    expect(calls.filter((url) => url === "/api/pages")).toHaveLength(1)
  })

  test("failed artist save stops before creating Pages or completing onboarding", async () => {
    const calls: string[] = []
    const request = (async (url: string) => {
      calls.push(url)
      return response(url === "/api/me/artist" ? 503 : 200)
    }) as typeof fetch
    expect(await saveSetup({ ...setup, artist: { role: "DJ", location: "", url: "" }, pages: [page] }, new Set(), request)).toEqual({ ok: false, step: "artist", error: "artist" })
    expect(calls).toEqual(["/api/me/profile", "/api/me/artist"])
  })

  test("a conflict is accepted only if the signed-in user owns the matching Page", async () => {
    const created = new Set<string>()
    const request = (async (url: string, options?: RequestInit) => {
      if (url === "/api/pages" && options?.method === "POST") return response(409)
      if (url === "/api/pages") return response(200, [page])
      return response()
    }) as typeof fetch
    expect(await saveSetup({ ...setup, pages: [page] }, created, request)).toEqual({ ok: true })
    expect(created.has("basement:Basement:club")).toBeTrue()
    const taken = (async (url: string, options?: RequestInit) =>
      url === "/api/pages" && options?.method === "POST" ? response(409)
        : url === "/api/pages" ? response(200, []) : response()) as typeof fetch
    expect(await saveSetup({ ...setup, pages: [page] }, new Set(), taken)).toEqual({ ok: false, step: "pages", error: "pageTaken" })
  })

  test("incomplete or duplicate Pages cannot be submitted", async () => {
    expect(validPages([page, { ...page, slug: "BASEMENT" }])).toBeFalse()
    expect(validPages([{ ...page, slug: "bad slug" }])).toBeFalse()
    const request = (async () => { throw new Error("must not send") }) as unknown as typeof fetch
    expect(await saveSetup({ ...setup, pages: [{ ...page, display_name: "" }] }, new Set(), request)).toEqual({ ok: false, step: "pages", error: "pageInvalid" })
  })
})
