import { proxySocialMutation } from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxySocialMutation(request, `/v1/posts/${encodeURIComponent(id)}/emoji`, "PUT")
}

// DELETE carries the emoji as a query param (bodies on DELETE get dropped by proxies).
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxySocialMutation(request, `/v1/posts/${encodeURIComponent(id)}/emoji`, "DELETE", {
    readBody: false,
    forwardQuery: true,
  })
}
