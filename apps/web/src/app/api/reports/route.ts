import { reportTarget } from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"
import { enforceLocalRateLimit, LOCAL_ABUSE_POLICIES } from "@/lib/http/local-rate-limit"
import { safeLogFailure } from "@/lib/http/safe-log"

export const dynamic = "force-dynamic"

const TARGET_TYPES = ["profile", "page", "post", "comment"] as const

type TargetType = (typeof TARGET_TYPES)[number]

function parseTargetType(value: unknown): TargetType | null {
  return typeof value === "string" && TARGET_TYPES.includes(value as TargetType)
    ? (value as TargetType)
    : null
}

export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) return Response.json({ error: "forbidden" }, { status: 403 })
  const principal = await requireSession()
  if (!principal.authenticated) return Response.json({ error: "unauthenticated" }, { status: 401 })
  const limited = enforceLocalRateLimit(request, "users-report", LOCAL_ABUSE_POLICIES.report)
  if (limited) return limited

  const body = (await request.json().catch(() => null)) as {
    target_type?: unknown
    target_handle?: unknown
    reason?: unknown
    note?: unknown
  } | null
  const target_type = parseTargetType(body?.target_type)
  const target_handle = typeof body?.target_handle === "string" ? body.target_handle.trim() : ""
  const reason = typeof body?.reason === "string" ? body.reason.trim() : ""
  const note = typeof body?.note === "string" ? body.note.trim() : null
  if (!target_type || !target_handle || !reason) {
    return Response.json({ error: "target_type, target_handle and reason required" }, { status: 400 })
  }

  try {
    const result = await reportTarget({ target_type, target_handle, reason, note })
    return Response.json(result.body, { status: result.status })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      safeLogFailure({ service: "users", operation: "report", kind: "configuration" }, error)
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    safeLogFailure({ service: "users", operation: "report", kind: "unavailable" }, error)
    return Response.json({ error: "report service unavailable" }, { status: 503 })
  }
}
