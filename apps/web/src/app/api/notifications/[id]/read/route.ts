import { markNotificationRead } from "@/lib/auth/product-auth"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "not authenticated" }, { status: 401 })
  }
  const { id } = await params
  const result = await markNotificationRead(id)
  return Response.json(result.body, { status: result.status })
}
