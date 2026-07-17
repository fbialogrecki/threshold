import { listNotifications } from "@/lib/auth/product-auth"
import { requireSession } from "@/lib/http/guard"

export async function GET() {
  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "not authenticated" }, { status: 401 })
  }
  const result = await listNotifications()
  return Response.json(result.body, { status: result.status })
}
