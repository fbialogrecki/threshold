import { bridgeAuthCookies } from "@/lib/auth/cookies"
import { emailVerifyRequest } from "@/lib/auth/product-auth"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"
import { enforceLocalRateLimit, LOCAL_ABUSE_POLICIES } from "@/lib/http/local-rate-limit"
import { safeLogFailure } from "@/lib/http/safe-log"

export const dynamic = "force-dynamic"

/**
 * Email verification resend BFF. Requires a session. The verification token is
 * never returned to the browser (SECURITY: stripped / dropped here); it is
 * delivered by email in production and read out-of-band in dev.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }
  const limited = enforceLocalRateLimit(
    request,
    "email-verification-request",
    LOCAL_ABUSE_POLICIES.emailVerificationRequest,
  )
  if (limited) return limited

  let result
  try {
    result = await emailVerifyRequest()
  } catch (error) {
    safeLogFailure({ service: "users", operation: "email_verification_request", kind: "unavailable" }, error)
    return Response.json({ error: "verification service unavailable" }, { status: 503 })
  }
  await bridgeAuthCookies(result.setCookies)
  if (result.status === 429) {
    return Response.json({ error: "too many attempts" }, { status: 429 })
  }
  if (result.status !== 200) {
    return Response.json({ error: "verification service unavailable" }, { status: 503 })
  }
  return Response.json({ status: "ok" }, { status: 200 })
}
