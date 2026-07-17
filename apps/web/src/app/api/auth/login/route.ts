import { bridgeAuthCookies } from "@/lib/auth/cookies"
import { login, stripDevTokens } from "@/lib/auth/product-auth"
import { loginResponseStatus } from "@/lib/auth/status"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin } from "@/lib/http/guard"
import { enforceLocalRateLimit, LOCAL_ABUSE_POLICIES } from "@/lib/http/local-rate-limit"
import { safeLogFailure } from "@/lib/http/safe-log"

export const dynamic = "force-dynamic"

/**
 * Login BFF: forwards credentials to `users /v1/auth/login` and bridges the
 * resulting HttpOnly session/refresh cookies onto the same-origin response.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const limited = enforceLocalRateLimit(request, "auth-login", LOCAL_ABUSE_POLICIES.login)
  if (limited) return limited

  const body = (await request.json().catch(() => null)) as Record<
    string,
    unknown
  > | null

  const emailOrUsername =
    typeof body?.emailOrUsername === "string"
      ? body.emailOrUsername
      : typeof body?.username === "string"
        ? body.username
        : ""
  const password = typeof body?.password === "string" ? body.password : ""

  if (!emailOrUsername.trim() || !password) {
    return Response.json({ error: "missing credentials" }, { status: 400 })
  }

  let result
  try {
    result = await login({
      email_or_username: emailOrUsername.trim(),
      password,
    })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      safeLogFailure({ service: "users", operation: "login", kind: "configuration" }, error)
      return Response.json(
        { error: "users service URL is not configured" },
        { status: 503 },
      )
    }
    safeLogFailure({ service: "users", operation: "login", kind: "unavailable" }, error)
    return Response.json({ error: "authentication service unavailable" }, { status: 503 })
  }

  await bridgeAuthCookies(result.setCookies)
  const status = loginResponseStatus(result.status)
  if (status === 401) {
    return Response.json({ error: "invalid credentials" }, { status: 401 })
  }
  if (status === 429) {
    return Response.json({ error: "too many attempts" }, { status: 429 })
  }
  if (status === 503) {
    return Response.json({ error: "authentication service unavailable" }, { status: 503 })
  }

  return Response.json(stripDevTokens(result.body), { status: 200 })
}
