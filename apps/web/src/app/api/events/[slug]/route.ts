import { proxyEventsGet, proxyEventsMutation } from "@/lib/events/client"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string }> }

export async function GET(_request: Request, { params }: Context) {
  const { slug } = await params
  return proxyEventsGet(`/v1/events/${encodeURIComponent(slug)}`)
}

export async function PATCH(request: Request, { params }: Context) {
  const { slug } = await params
  return proxyEventsMutation(request, `/v1/events/${encodeURIComponent(slug)}`, "PATCH")
}
