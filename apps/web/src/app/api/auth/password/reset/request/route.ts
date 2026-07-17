import { bridgeAuthCookies } from "@/lib/auth/cookies"
import { passwordResetRequest, stripDevTokens } from "@/lib/auth/product-auth"
import { resetRequestStatus } from "@/lib/auth/status"
import { assertSameOrigin } from "@/lib/http/guard"
import { enforceLocalRateLimit, LOCAL_ABUSE_POLICIES } from "@/lib/http/local-rate-limit"
import { safeLogFailure } from "@/lib/http/safe-log"
import { EMAIL_RE } from "@/lib/validation"

export const dynamic = "force-dynamic"

/**
 * Password reset request BFF. Always returns a generic success (anti-
 * enumeration) regardless of whether the account exists.
 *
 * SECURITY: the `users` response can carry `dev_password_reset_token` when dev
 * token exposure is on. It MUST be stripped here — forwarding it would let any
 * caller request a reset for a victim's email and read the token back, which is
 * full account takeover. In dev the token is read out-of-band (server logs).
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const limited = enforceLocalRateLimit(
    request,
    "password-reset-request",
    LOCAL_ABUSE_POLICIES.passwordResetRequest,
  )
  if (limited) return limited

  const body = (await request.json().catch(() => null)) as { email?: unknown } | null
  const email = typeof body?.email === "string" ? body.email.trim() : ""

  // Validate shape but never reveal whether the address exists.
  if (EMAIL_RE.test(email)) {
    try {
      const result = await passwordResetRequest(email)
      await bridgeAuthCookies(result.setCookies)
      void stripDevTokens(result.body)
      const status = resetRequestStatus(result.status)
      if (status === 429) {
        return Response.json({ error: "too many attempts" }, { status: 429 })
      }
      if (status === 503) {
        return Response.json({ error: "password reset unavailable" }, { status: 503 })
      }
    } catch (error) {
      safeLogFailure({ service: "users", operation: "password_reset_request", kind: "unavailable" }, error)
      return Response.json({ error: "password reset unavailable" }, { status: 503 })
    }
  }

  return Response.json({ status: "ok" }, { status: 200 })
}
