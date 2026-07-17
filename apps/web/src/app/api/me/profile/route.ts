import { stripDevTokens, updateProfile, type ProfileUpdatePayload } from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export const dynamic = "force-dynamic"

/** Profile edit -> users PATCH /v1/me/profile. */
export async function PATCH(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }

  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  const payload: ProfileUpdatePayload = {}
  for (const key of ["display_name", "username", "bio", "city", "avatar_media_asset_id"] as const) {
    const value = body?.[key]
    if (typeof value === "string") payload[key] = value
  }

  try {
    const result = await updateProfile(payload)
    if (result.status === 409) {
      return Response.json({ error: "username already taken" }, { status: 409 })
    }
    if (result.status >= 400) {
      return Response.json({ error: "profile update failed" }, { status: result.status })
    }
    return Response.json(stripDevTokens(result.body), { status: 200 })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}
