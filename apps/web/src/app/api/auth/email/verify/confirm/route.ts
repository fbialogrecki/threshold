import { bridgeAuthCookies } from "@/lib/auth/cookies"
import { emailVerifyConfirm } from "@/lib/auth/product-auth"
import { assertSameOrigin } from "@/lib/http/guard"
import { enforceLocalRateLimit, LOCAL_ABUSE_POLICIES } from "@/lib/http/local-rate-limit"
import { safeLogFailure } from "@/lib/http/safe-log"

export const dynamic = "force-dynamic"

/**
 * Email verification confirm BFF: consumes a verification token. Open to
 * logged-out callers since the token itself is the proof.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const limited = enforceLocalRateLimit(
    request,
    "email-verification-confirm",
    LOCAL_ABUSE_POLICIES.emailVerificationConfirm,
  )
  if (limited) return limited

  const body = (await request.json().catch(() => null)) as { token?: unknown } | null
  const token = typeof body?.token === "string" ? body.token : ""
  if (token.length < 20) {
    return Response.json({ error: "invalid verification link" }, { status: 400 })
  }

  let result
  try {
    result = await emailVerifyConfirm(token)
  } catch (error) {
    safeLogFailure({ service: "users", operation: "email_verification_confirm", kind: "unavailable" }, error)
    return Response.json({ error: "verification service unavailable" }, { status: 503 })
  }
  await bridgeAuthCookies(result.setCookies)
  if (result.status === 400) {
    return Response.json({ error: "invalid verification link" }, { status: 400 })
  }
  if (result.status === 429) {
    return Response.json({ error: "too many attempts" }, { status: 429 })
  }
  if (result.status !== 200) {
    return Response.json({ error: "verification service unavailable" }, { status: 503 })
  }

  return Response.json({ status: "ok" }, { status: 200 })
}
