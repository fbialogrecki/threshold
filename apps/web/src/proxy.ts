import { NextResponse } from "next/server"

import { buildSecurityHeaders } from "@/lib/http/security-headers"

export function proxy() {
  const response = NextResponse.next()
  const securityHeaders = buildSecurityHeaders({
    nodeEnv: process.env.NODE_ENV,
    trustedLanHttp: process.env.WEB_TRUSTED_LAN_HTTP === "true",
  })
  for (const { key, value } of securityHeaders) response.headers.set(key, value)
  return response
}

export const config = {
  matcher: "/:path*",
}