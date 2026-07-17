import { proxySocialMutation } from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ userId: string }> },
) {
  const { userId } = await params
  return proxySocialMutation(request, `/v1/blocks/${encodeURIComponent(userId)}`, "POST")
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ userId: string }> },
) {
  const { userId } = await params
  return proxySocialMutation(request, `/v1/blocks/${encodeURIComponent(userId)}`, "DELETE", {
    readBody: false,
  })
}
