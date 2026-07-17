import { describe, expect, it } from "bun:test"

import {
  passwordPolicyError,
  validateRegistration,
} from "@/lib/validation"

describe("registration validation", () => {
  const valid = {
    username: "NightCrawler",
    email: "user@domain.xyz",
    password: "Supersecret1!",
  }

  it("accepts valid input and normalizes the username", () => {
    const result = validateRegistration(valid)
    expect(result.ok).toBe(true)
    if (result.ok) {
      expect(result.value.username).toBe("nightcrawler")
      expect(result.value.email).toBe("user@domain.xyz")
    }
  })

  it("rejects invalid usernames", () => {
    expect(validateRegistration({ ...valid, username: "ab" }).ok).toBe(false)
    expect(validateRegistration({ ...valid, username: "has space" }).ok).toBe(false)
    expect(validateRegistration({ ...valid, username: "a".repeat(31) }).ok).toBe(false)
  })

  it("matches backend username characters and reserved names", () => {
    expect(validateRegistration({ ...valid, username: "Night.Crawler-01" }).ok).toBe(true)
    expect(validateRegistration({ ...valid, username: ".Admin-" })).toEqual({
      ok: false,
      error: "reservedUsername",
    })
  })

  it("rejects invalid emails", () => {
    expect(validateRegistration({ ...valid, email: "nope" }).ok).toBe(false)
  })

  it("matches every backend password requirement", () => {
    expect(passwordPolicyError("Short1!")).toBe("passwordLength")
    expect(passwordPolicyError("UPPERCASE123!")).toBe("passwordLowercase")
    expect(passwordPolicyError("lowercase123!")).toBe("passwordUppercase")
    expect(passwordPolicyError("NoDigitsHere!")).toBe("passwordDigit")
    expect(passwordPolicyError("NoSymbols1234")).toBe("passwordSymbol")
    expect(passwordPolicyError("ValidPassword1!")).toBeNull()
    expect(passwordPolicyError(`${"Aa1!".repeat(257)}`)).toBe("passwordTooLong")
  })
})
