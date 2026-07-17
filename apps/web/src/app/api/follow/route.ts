import {
  followTarget,
  unfollowTarget,
  type FollowTargetType,
} from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export const dynamic = "force-dynamic"

const TARGET_TYPES: FollowTargetType[] = ["artist", "consumer", "page"]

function parseTargetType(value: unknown): FollowTargetType | null {
  return typeof value === "string" && TARGET_TYPES.includes(value as FollowTargetType)
    ? (value as FollowTargetType)
    : null
}

/**
 * Follow / unfollow -> users /v1/me/follows. `follow: false` unfollows.
 */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }

  const body = (await request.json().catch(() => null)) as {
    handle?: unknown
    targetType?: unknown
    follow?: unknown
  } | null

  const handle = typeof body?.handle === "string" ? body.handle.trim() : ""
  const targetType = parseTargetType(body?.targetType)
  const follow = body?.follow !== false

  if (!handle || !targetType) {
    return Response.json({ error: "handle and targetType required" }, { status: 400 })
  }

  try {
    const result = follow
      ? await followTarget(targetType, handle)
      : await unfollowTarget(targetType, handle)
    if (result.status >= 400) {
      return Response.json({ error: "follow update failed" }, { status: result.status })
    }
    return Response.json({ ok: true, following: follow }, { status: 200 })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}
