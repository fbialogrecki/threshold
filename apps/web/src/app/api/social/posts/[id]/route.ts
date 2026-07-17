import { proxySocialMutation } from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxySocialMutation(request, `/v1/posts/${encodeURIComponent(id)}`, "PATCH")
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxySocialMutation(request, `/v1/posts/${encodeURIComponent(id)}`, "DELETE", {
    readBody: false,
  })
}
