import {
  proxySocialGet,
  proxySocialMutation,
} from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxySocialGet(`/v1/posts/${encodeURIComponent(id)}/comments`, request)
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  return proxySocialMutation(request, `/v1/posts/${encodeURIComponent(id)}/comments`, "POST")
}
