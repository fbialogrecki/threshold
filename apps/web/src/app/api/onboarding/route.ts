import { stripDevTokens, updateOnboarding } from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"
import {
  hasRequiredOnboardingCity,
  parseOnboardingPayload,
  persistOnboarding,
} from "@/lib/onboarding/plan"
import { socialCall, trustedAuthorHeaders } from "@/lib/social/client"

export const dynamic = "force-dynamic"

/**
 * Onboarding write -> users PUT /v1/me/onboarding. Persists city +
 * preferred_scenes for the signed-in user.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }

  const payload = parseOnboardingPayload(await request.json().catch(() => null))
  if (!hasRequiredOnboardingCity(payload)) {
    return Response.json({ error: "supported city required" }, { status: 400 })
  }

  try {
    const userHeaders = await trustedAuthorHeaders()
    if (!userHeaders) {
      return Response.json({ error: "user identity unavailable" }, { status: 503 })
    }
    const { result, cityGroup } = await persistOnboarding(
      payload,
      updateOnboarding,
      userHeaders,
      socialCall,
    )
    if (cityGroup?.status !== "joined") {
      return Response.json(
        { error: "official city group join failed", city_group: cityGroup },
        { status: 502 },
      )
    }
    if (result.status !== 200) {
      return Response.json({ error: "onboarding update failed" }, { status: 502 })
    }
    const body = stripDevTokens(result.body)
    return Response.json({
      ...(typeof body === "object" && body !== null ? body : { result: body }),
      city_group: cityGroup,
    }, { status: 200 })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}
