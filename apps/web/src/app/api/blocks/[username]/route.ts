import { unblockUser } from "@/lib/auth/product-auth"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"
import { safeLogFailure } from "@/lib/http/safe-log"
export const dynamic = "force-dynamic"

export async function DELETE(request: Request, { params }: { params: Promise<{ username: string }> }) {
  if (!(await assertSameOrigin(request))) return Response.json({ error: "forbidden" }, { status: 403 })
  if (!(await requireSession()).authenticated) return Response.json({ error: "unauthenticated" }, { status: 401 })
  const { username } = await params
  if (!username.trim() || username.length > 150) return Response.json({ error: "invalid username" }, { status: 400 })
  try {
    const result = await unblockUser(username)
    return result.status === 204 ? new Response(null, { status: 204 }) : Response.json(result.body, { status: result.status })
  } catch (error) {
    safeLogFailure({ service: "users", operation: "unblock", kind: "unavailable" }, error)
    return Response.json({ error: "users service unavailable" }, { status: 503 })
  }
}
