type CookieSecurityEnvironment = {
  nodeEnv: string | undefined
  authCookieSecure: string | undefined
  trustedLanHttp: string | undefined
}

export type CookieSecurity = {
  secure: boolean
  trustedLanHttp: boolean
}

/**
 * Production is public HTTPS by default. Plain HTTP is accepted only for an
 * explicitly acknowledged trusted-LAN deployment; it is not suitable for a
 * public endpoint.
 */
export function resolveCookieSecurity(env: CookieSecurityEnvironment): CookieSecurity {
  const secure = env.authCookieSecure === "true"
  const trustedLanHttp = env.trustedLanHttp === "true"

  if (env.nodeEnv === "production") {
    if (secure && trustedLanHttp) {
      throw new Error("AUTH_COOKIE_SECURE=true and WEB_TRUSTED_LAN_HTTP=true must not be combined")
    }
    if (!secure && !trustedLanHttp) {
      throw new Error(
        "Production requires AUTH_COOKIE_SECURE=true; plain HTTP requires the explicit WEB_TRUSTED_LAN_HTTP=true escape hatch",
      )
    }
  }

  return { secure, trustedLanHttp }
}
