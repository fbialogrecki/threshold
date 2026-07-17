import { blockUser } from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export const dynamic = "force-dynamic"

export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) return Response.json({ error: "forbidden" }, { status: 403 })
  const principal = await requireSession()
  if (!principal.authenticated) return Response.json({ error: "unauthenticated" }, { status: 401 })

  const body = (await request.json().catch(() => null)) as { username?: unknown } | null
  const username = typeof body?.username === "string" ? body.username.trim() : ""
  if (!username) return Response.json({ error: "username required" }, { status: 400 })

  try {
    const result = await blockUser(username)
    return Response.json(result.body, { status: result.status })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}
