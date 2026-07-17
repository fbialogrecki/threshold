export type SecurityHeader = { key: string; value: string }

type SecurityHeaderEnvironment = {
  nodeEnv: string | undefined
  trustedLanHttp: boolean
}

/**
 * Static CSP is intentionally deterministic so it can be applied to every Next
 * response. Next and the current UI emit inline bootstrap scripts and style
 * attributes, so those two narrowly-scoped unsafe-inline exceptions are
 * required. All fetches and media remain same-origin through the BFF.
 */
export function buildSecurityHeaders(env: SecurityHeaderEnvironment): SecurityHeader[] {
  const developmentEval = env.nodeEnv === "development" ? " 'unsafe-eval'" : ""
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${developmentEval}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    "connect-src 'self'",
    "media-src 'self' blob:",
    "worker-src 'self' blob:",
    "manifest-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-src 'none'",
    "frame-ancestors 'none'",
  ].join("; ")

  const headers: SecurityHeader[] = [
    { key: "Content-Security-Policy", value: csp },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    {
      key: "Permissions-Policy",
      value: "camera=(), microphone=(), geolocation=(), browsing-topics=()",
    },
  ]

  if (env.nodeEnv === "production" && !env.trustedLanHttp) {
    headers.push({
      key: "Strict-Transport-Security",
      value: "max-age=31536000; includeSubDomains",
    })
  }

  return headers
}
