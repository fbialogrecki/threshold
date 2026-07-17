import { markAllNotificationsRead } from "@/lib/auth/product-auth"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "not authenticated" }, { status: 401 })
  }
  const result = await markAllNotificationsRead()
  return Response.json(result.body, { status: result.status })
}
