import { expect, test } from "bun:test"
import { reportContent, setAccountBlocked, safetyAllowed } from "../actions"

test("reports use social IDs for posts/comments and users handles for profiles", async () => {
  for (const type of ["post", "comment", "profile"] as const) {
    const calls: unknown[] = []
    await reportContent({ type, target: "target" }, "spam", " note ", async (url, init) => {
      calls.push([url, JSON.parse(init?.body as string)])
      return Response.json({ status: "open" }, { status: 201 })
    })
    expect(calls).toEqual([[type === "profile" ? "/api/reports" : "/api/social/reports", { target_type: type, [type === "profile" ? "target_handle" : "target_id"]: "target", reason: "spam", note: "note" }]])
  }
})
test("block and unblock use canonical users BFF and accept bodyless 204", async () => {
  const calls: unknown[] = []
  const request: (input: string, init?: RequestInit) => Promise<Response> = async (url, init) => { calls.push([url, init?.method, init?.body]); return new Response(null, { status: 204 }) }
  await setAccountBlocked("Żaba", true, request)
  await setAccountBlocked("Żaba", false, request)
  expect(calls).toEqual([["/api/blocks", "POST", JSON.stringify({ username: "Żaba" })], ["/api/blocks/%C5%BBaba", "DELETE", undefined]])
})
test("no anonymous, self or deleted account actions", () => {
  expect(safetyAllowed("viewer", "other")).toBe(true)
  expect(safetyAllowed(null, "other")).toBe(false)
  expect(safetyAllowed("viewer", "viewer")).toBe(false)
  expect(safetyAllowed("viewer", "")).toBe(false)
})
test("validation rejects empty/oversized reports and HTTP/network failures stay failed", async () => {
  for (const [reason, note] of [["", ""], ["x".repeat(81), ""], ["spam", "x".repeat(1001)]]) {
    await expect(reportContent({ type: "post", target: "id" }, reason, note, async () => { throw new Error("should not request") })).rejects.toThrow("invalid report")
  }
  for (const status of [401, 403, 404, 422, 429, 503]) {
    const request: (input: string, init?: RequestInit) => Promise<Response> = async () => new Response(null, { status })
    await expect(reportContent({ type: "post", target: "id" }, "spam", "", request)).rejects.toThrow()
    await expect(setAccountBlocked("Other", true, request)).rejects.toThrow()
  }
  await expect(setAccountBlocked("Other", false, async () => { throw new Error("offline") })).rejects.toThrow("offline")
})
