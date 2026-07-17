import { proxyEventsMutation } from "@/lib/events/client"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string; assignmentId: string }> }

export async function DELETE(request: Request, { params }: Context) {
  const { slug, assignmentId } = await params
  return proxyEventsMutation(
    request,
    `/v1/events/${encodeURIComponent(slug)}/door-staff/${encodeURIComponent(assignmentId)}`,
    "DELETE",
    { readBody: false },
  )
}
