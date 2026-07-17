import { proxySocialMutation } from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxySocialMutation(request, `/v1/comments/${encodeURIComponent(id)}/reaction`, "PUT")
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxySocialMutation(
    request,
    `/v1/comments/${encodeURIComponent(id)}/reaction`,
    "DELETE",
    { readBody: false },
  )
}
