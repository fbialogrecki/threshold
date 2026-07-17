import { proxyEventsMutation } from "@/lib/events/client"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string; artistProfileId: string }> }

export async function PUT(request: Request, { params }: Context) {
  const { slug, artistProfileId } = await params
  return proxyEventsMutation(
    request,
    `/v1/events/${encodeURIComponent(slug)}/guestlist/quotas/${encodeURIComponent(artistProfileId)}`,
    "PUT",
  )
}
