import { bridgeAuthCookies } from "@/lib/auth/cookies"
import { register, stripDevTokens } from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin } from "@/lib/http/guard"
import { enforceLocalRateLimit, LOCAL_ABUSE_POLICIES } from "@/lib/http/local-rate-limit"
import { safeLogFailure } from "@/lib/http/safe-log"
import { validateRegistration } from "@/lib/validation"

export const dynamic = "force-dynamic"

/**
 * Registration BFF: creates the product account in `users /v1/auth/register`
 * and bridges the session cookies it returns, so the user is auto-logged-in.
 * No session is required (the caller is a logged-out visitor) but same-origin
 * is enforced as a lightweight CSRF guard.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const limited = enforceLocalRateLimit(request, "auth-register", LOCAL_ABUSE_POLICIES.register)
  if (limited) return limited

  const body = (await request.json().catch(() => null)) as Record<
    string,
    unknown
  > | null
  const check = validateRegistration(body ?? {})
  if (!check.ok) {
    return Response.json({ error: check.error }, { status: 400 })
  }

  let result
  try {
    result = await register({
      email: check.value.email,
      username: check.value.username,
      password: check.value.password,
      display_name: check.value.displayName,
    })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      safeLogFailure({ service: "users", operation: "register", kind: "configuration" }, error)
      return Response.json(
        { error: "users service URL is not configured" },
        { status: 503 },
      )
    }
    safeLogFailure({ service: "users", operation: "register", kind: "unavailable" }, error)
    return Response.json({ error: "registration service unavailable" }, { status: 503 })
  }

  await bridgeAuthCookies(result.setCookies)
  if (result.status === 409) {
    return Response.json({ error: "account already exists" }, { status: 409 })
  }
  if (result.status === 422) {
    return Response.json({ error: "password does not meet policy" }, { status: 422 })
  }
  if (result.status === 429) {
    return Response.json({ error: "too many attempts" }, { status: 429 })
  }
  if (result.status !== 201) {
    return Response.json({ error: "could not create account" }, { status: 502 })
  }

  // SECURITY: never forward dev_email_verification_token to the browser.
  return Response.json(stripDevTokens(result.body), { status: 201 })
}
