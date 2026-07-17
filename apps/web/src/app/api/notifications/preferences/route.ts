import {
  getNotificationPreferences,
  updateNotificationPreferences,
} from "@/lib/auth/product-auth"
import { notificationPreferencePayload } from "@/lib/notification-preferences"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export async function GET() {
  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "not authenticated" }, { status: 401 })
  }
  const result = await getNotificationPreferences()
  return Response.json(result.body, { status: result.status })
}

export async function PUT(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "not authenticated" }, { status: 401 })
  }

  const body = await request.json().catch(() => null)
  const payload = notificationPreferencePayload(body)
  if (Object.keys(payload).length === 0) {
    return Response.json({ error: "invalid preferences" }, { status: 400 })
  }
  const result = await updateNotificationPreferences(payload)
  return Response.json(result.body, { status: result.status })
}
