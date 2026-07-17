import { proxyEventsMutation } from "@/lib/events/client"
import { minimalCheckInResponse } from "@/lib/events/access"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string }> }

export async function POST(request: Request, { params }: Context) {
  const { slug } = await params
  return proxyEventsMutation(
    request,
    `/v1/events/${encodeURIComponent(slug)}/check-in`,
    "POST",
    { successBody: minimalCheckInResponse, hideErrorBody: true },
  )
}
