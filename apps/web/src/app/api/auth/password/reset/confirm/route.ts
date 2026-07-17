import { bridgeAuthCookies } from "@/lib/auth/cookies"
import { passwordResetConfirm } from "@/lib/auth/product-auth"
import { assertSameOrigin } from "@/lib/http/guard"
import { enforceLocalRateLimit, LOCAL_ABUSE_POLICIES } from "@/lib/http/local-rate-limit"
import { safeLogFailure } from "@/lib/http/safe-log"
import { passwordPolicyError } from "@/lib/validation"

export const dynamic = "force-dynamic"

/**
 * Password reset confirm BFF: exchanges a reset token + new password. On
 * success `users` revokes all of the user's sessions, so the client must log
 * in again afterwards.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const limited = enforceLocalRateLimit(
    request,
    "password-reset-confirm",
    LOCAL_ABUSE_POLICIES.passwordResetConfirm,
  )
  if (limited) return limited

  const body = (await request.json().catch(() => null)) as {
    token?: unknown
    password?: unknown
  } | null
  const token = typeof body?.token === "string" ? body.token : ""
  const password = typeof body?.password === "string" ? body.password : ""

  if (token.length < 20) {
    return Response.json({ error: "invalid or expired reset link" }, { status: 400 })
  }
  if (passwordPolicyError(password)) {
    return Response.json({ error: "password does not meet policy" }, { status: 400 })
  }

  let result
  try {
    result = await passwordResetConfirm({ token, new_password: password })
  } catch (error) {
    safeLogFailure({ service: "users", operation: "password_reset_confirm", kind: "unavailable" }, error)
    return Response.json({ error: "password reset unavailable" }, { status: 503 })
  }
  await bridgeAuthCookies(result.setCookies)
  if (result.status === 400) {
    return Response.json({ error: "invalid or expired reset link" }, { status: 400 })
  }
  if (result.status === 429) {
    return Response.json({ error: "too many attempts" }, { status: 429 })
  }
  if (result.status !== 200) {
    return Response.json({ error: "password reset unavailable" }, { status: 503 })
  }

  return Response.json({ status: "ok" }, { status: 200 })
}
