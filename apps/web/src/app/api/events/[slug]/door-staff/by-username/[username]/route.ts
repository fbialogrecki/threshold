import { proxyEventsMutation } from "@/lib/events/client"
import { minimalDoorStaffAssignment } from "@/lib/events/access"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string; username: string }> }

export async function PUT(request: Request, { params }: Context) {
  const { slug, username } = await params
  return proxyEventsMutation(
    request,
    `/v1/events/${encodeURIComponent(slug)}/door-staff/by-username/${encodeURIComponent(username)}`,
    "PUT",
    { readBody: false, successBody: minimalDoorStaffAssignment },
  )
}
