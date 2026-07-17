import { proxyEventsMutation } from "@/lib/events/client"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string }> }

export async function POST(request: Request, { params }: Context) {
  const { slug } = await params
  return proxyEventsMutation(request, `/v1/events/${encodeURIComponent(slug)}/follow`, "POST", {
    readBody: false,
  })
}

export async function DELETE(request: Request, { params }: Context) {
  const { slug } = await params
  return proxyEventsMutation(request, `/v1/events/${encodeURIComponent(slug)}/follow`, "DELETE", {
    readBody: false,
  })
}
