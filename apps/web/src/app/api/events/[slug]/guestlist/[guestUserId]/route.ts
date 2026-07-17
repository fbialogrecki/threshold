import { proxyEventsMutation } from "@/lib/events/client"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string; guestUserId: string }> }

export async function DELETE(request: Request, { params }: Context) {
  const { slug, guestUserId } = await params
  return proxyEventsMutation(
    request,
    `/v1/events/${encodeURIComponent(slug)}/guestlist/${encodeURIComponent(guestUserId)}`,
    "DELETE",
    { readBody: false },
  )
}
