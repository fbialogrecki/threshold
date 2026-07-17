import { afterEach, describe, expect, it } from "bun:test"

import { proxy } from "@/proxy"

const environment = process.env as unknown as Record<string, string | undefined>
const originalEnvironment = {
  nodeEnv: process.env.NODE_ENV,
  authCookieSecure: process.env.AUTH_COOKIE_SECURE,
  trustedLanHttp: process.env.WEB_TRUSTED_LAN_HTTP,
}

function restoreEnvironment(): void {
  environment.NODE_ENV = originalEnvironment.nodeEnv
  process.env.AUTH_COOKIE_SECURE = originalEnvironment.authCookieSecure
  process.env.WEB_TRUSTED_LAN_HTTP = originalEnvironment.trustedLanHttp
}

afterEach(restoreEnvironment)

describe("proxy security configuration", () => {
  it("validates cookie security on every request", () => {
    environment.NODE_ENV = "development"
    delete process.env.AUTH_COOKIE_SECURE
    delete process.env.WEB_TRUSTED_LAN_HTTP
    expect(proxy().status).toBe(200)

    environment.NODE_ENV = "production"
    process.env.AUTH_COOKIE_SECURE = "false"
    delete process.env.WEB_TRUSTED_LAN_HTTP
    expect(() => proxy()).toThrow("AUTH_COOKIE_SECURE=true")
  })
})
