import { bridgeAuthCookies } from "@/lib/auth/cookies"
import { deleteAccount, me, stripDevTokens } from "@/lib/auth/product-auth"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export const dynamic = "force-dynamic"

/**
 * Returns the current product-auth profile by proxying `users /v1/auth/me`
 * with the forwarded session cookie. No Authentik, no bearer tokens.
 */
export async function GET() {
  if (!process.env.USERS_SERVICE_URL) {
    return Response.json(
      { error: "users service URL is not configured" },
      { status: 503 },
    )
  }

  const response = await me()
  await bridgeAuthCookies(response.setCookies)
  if (response.status === 401) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }
  if (response.status !== 200) {
    return Response.json({ error: "profile lookup failed" }, { status: 502 })
  }

  return Response.json(stripDevTokens(response.body), { status: 200 })
}

/**
 * Account deletion (GDPR) -> users DELETE /v1/me. `users` anonymizes the
 * account, revokes sessions and propagates anonymization to `social`, then
 * clears the auth cookies, which we bridge onto the browser.
 */
export async function DELETE(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }

  const result = await deleteAccount()
  await bridgeAuthCookies(result.setCookies)
  if (result.status !== 204 && result.status !== 200) {
    return Response.json({ error: "account deletion failed" }, { status: 502 })
  }

  return new Response(null, { status: 204 })
}
