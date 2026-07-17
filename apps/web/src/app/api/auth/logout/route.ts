import {
  bridgeAuthCookies,
  clearAuthCookies,
} from "@/lib/auth/cookies"
import { logout } from "@/lib/auth/product-auth"
import { assertSameOrigin } from "@/lib/http/guard"
import { safeLogFailure } from "@/lib/http/safe-log"

export const dynamic = "force-dynamic"

async function clearSession() {
  try {
    const result = await logout()
    await bridgeAuthCookies(result.setCookies)
  } catch (error) {
    safeLogFailure({ service: "users", operation: "logout", kind: "unavailable" }, error)
    // Local clearing still prevents an invalid upstream session from looping.
  } finally {
    await clearAuthCookies()
  }
}

/**
 * Logout BFF: revokes the session in `users` and bridges the cookie-clearing
 * Set-Cookie headers onto the browser. Idempotent — always clears locally.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  await clearSession()
  return new Response(null, { status: 204 })
}
