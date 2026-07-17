import { describe, expect, it } from "bun:test"

import { buildSecurityHeaders } from "@/lib/http/security-headers"

describe("buildSecurityHeaders", () => {
  it("returns a deterministic restrictive policy for the current Next app", () => {
    const first = buildSecurityHeaders({ nodeEnv: "production", trustedLanHttp: false })
    const second = buildSecurityHeaders({ nodeEnv: "production", trustedLanHttp: false })

    expect(second).toEqual(first)
    expect(first).toContainEqual({ key: "X-Content-Type-Options", value: "nosniff" })
    expect(first).toContainEqual({ key: "X-Frame-Options", value: "DENY" })
    expect(first).toContainEqual({ key: "Referrer-Policy", value: "strict-origin-when-cross-origin" })
    expect(first).toContainEqual({
      key: "Permissions-Policy",
      value: "camera=(), microphone=(), geolocation=(), browsing-topics=()",
    })
    const csp = first.find(({ key }) => key === "Content-Security-Policy")?.value ?? ""
    expect(csp).toContain("default-src 'self'")
    expect(csp).toContain("script-src 'self' 'unsafe-inline'")
    expect(csp).toContain("style-src 'self' 'unsafe-inline'")
    expect(csp).toContain("img-src 'self' blob: data:")
    expect(csp).toContain("object-src 'none'")
    expect(csp).toContain("base-uri 'self'")
    expect(csp).toContain("form-action 'self'")
    expect(csp).toContain("frame-ancestors 'none'")
    expect(csp).not.toContain("unsafe-eval")
  })

  it("emits HSTS only for public HTTPS production mode", () => {
    expect(buildSecurityHeaders({ nodeEnv: "production", trustedLanHttp: false }))
      .toContainEqual({
        key: "Strict-Transport-Security",
        value: "max-age=31536000; includeSubDomains",
      })
    expect(buildSecurityHeaders({ nodeEnv: "production", trustedLanHttp: true })
      .some(({ key }) => key === "Strict-Transport-Security")).toBe(false)
    expect(buildSecurityHeaders({ nodeEnv: "development", trustedLanHttp: false })
      .some(({ key }) => key === "Strict-Transport-Security")).toBe(false)
  })

  it("allows React development diagnostics without weakening production", () => {
    const csp = buildSecurityHeaders({ nodeEnv: "development", trustedLanHttp: false })
      .find(({ key }) => key === "Content-Security-Policy")?.value
    expect(csp).toContain("'unsafe-eval'")
  })
})
