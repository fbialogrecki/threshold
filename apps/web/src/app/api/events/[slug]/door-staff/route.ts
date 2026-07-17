import { proxyEventsGet } from "@/lib/events/client"
import { minimalDoorStaffList } from "@/lib/events/access"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string }> }

export async function GET(_: Request, { params }: Context) {
  const { slug } = await params
  return proxyEventsGet(
    `/v1/events/${encodeURIComponent(slug)}/door-staff`,
    undefined,
    {
      includeViewer: true,
      requireViewer: true,
      successBody: minimalDoorStaffList,
    },
  )
}
