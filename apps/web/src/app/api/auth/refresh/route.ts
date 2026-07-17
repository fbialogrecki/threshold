import { bridgeAuthCookies } from "@/lib/auth/cookies"
import { refresh, stripDevTokens } from "@/lib/auth/product-auth"
import { assertSameOrigin } from "@/lib/http/guard"
import { safeLogFailure } from "@/lib/http/safe-log"

export const dynamic = "force-dynamic"

/**
 * Refresh BFF: rotates the session/refresh pair via `users /v1/auth/refresh`
 * (token family rotation happens server-side) and bridges the new cookies.
 * Called proactively by the client RefreshKeeper and on a 401 retry.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  let result
  try {
    result = await refresh()
  } catch (error) {
    safeLogFailure({ service: "users", operation: "refresh", kind: "unavailable" }, error)
    return Response.json({ error: "authentication service unavailable" }, { status: 503 })
  }

  if (result.status !== 200) {
    // Bridge any cookie-clearing headers (revoked/expired refresh) too.
    await bridgeAuthCookies(result.setCookies)
    return Response.json({ error: "invalid refresh token" }, { status: 401 })
  }

  await bridgeAuthCookies(result.setCookies)
  return Response.json(stripDevTokens(result.body), { status: 200 })
}
