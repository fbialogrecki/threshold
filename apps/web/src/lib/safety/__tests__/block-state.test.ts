import { expect, test, mock } from "bun:test"
mock.module("server-only", () => ({}))
const { getAccountBlockState } = await import("../block-state")
test("canonical block read uses server-only internal API, not social projection", async () => {
  process.env.USERS_SERVICE_URL = "http://users.test"
  process.env.THRESHOLD_INTERNAL_TOKEN = "test-internal"
  const state = await getAccountBlockState("viewer", "target", async (url, init) => {
    expect(url).toBe("http://users.test/internal/v1/users/viewer/blocks/target")
    expect(new Headers(init?.headers).get("X-Threshold-Internal-Token")).toBe("test-internal")
    expect(init?.cache).toBe("no-store")
    return Response.json({ blocked: true })
  })
  expect(state).toBe(true)
})
test("unavailable block status stays unknown rather than claiming unblocked", async () => {
  expect(await getAccountBlockState("viewer", "target", async () => new Response(null, { status: 503 }))).toBeNull()
  expect(await getAccountBlockState("viewer", "target", async () => Response.json({}))).toBeNull()
})
