import { describe, expect, it } from "bun:test"

import { resolveCookieSecurity } from "@/lib/auth/cookie-security"

describe("resolveCookieSecurity", () => {
  it("fails closed when production cookies are not Secure", () => {
    expect(() => resolveCookieSecurity({
      nodeEnv: "production",
      authCookieSecure: "false",
      trustedLanHttp: undefined,
    })).toThrow("AUTH_COOKIE_SECURE=true")
  })

  it("permits insecure production cookies only with the explicit trusted-LAN escape hatch", () => {
    expect(resolveCookieSecurity({
      nodeEnv: "production",
      authCookieSecure: "false",
      trustedLanHttp: "true",
    })).toEqual({ secure: false, trustedLanHttp: true })
  })

  it("rejects contradictory public HTTPS and trusted-LAN settings", () => {
    expect(() => resolveCookieSecurity({
      nodeEnv: "production",
      authCookieSecure: "true",
      trustedLanHttp: "true",
    })).toThrow("must not")
  })

  it("preserves plain HTTP local development", () => {
    expect(resolveCookieSecurity({
      nodeEnv: "development",
      authCookieSecure: undefined,
      trustedLanHttp: undefined,
    })).toEqual({ secure: false, trustedLanHttp: false })
  })
})
