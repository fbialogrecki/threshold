import { expect, mock, test } from "bun:test"

mock.module("server-only", () => ({}))
const { stripDevTokens } = await import("../product-auth")

test("token stripping preserves list responses and strips tokens from list items", () => {
  const pages = [{ id: "page", role: "owner", dev_email_verification_token: "test-only" }]
  expect(stripDevTokens(pages)).toEqual([{ id: "page", role: "owner" }])
  expect(stripDevTokens([])).toEqual([])
  expect(pages[0].dev_email_verification_token).toBe("test-only")
})

test("token stripping preserves object and primitive response contracts", () => {
  expect(stripDevTokens({ id: "account", dev_password_reset_token: "test-only" })).toEqual({ id: "account" })
  for (const value of [null, "message", 123, false]) expect(stripDevTokens(value)).toBe(value)
})
