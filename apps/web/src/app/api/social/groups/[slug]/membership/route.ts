import { proxySocialMutation } from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params
  return proxySocialMutation(
    request,
    `/v1/groups/${encodeURIComponent(slug)}/membership`,
    "POST",
    { readBody: false },
  )
}

export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params
  return proxySocialMutation(
    request,
    `/v1/groups/${encodeURIComponent(slug)}/membership`,
    "DELETE",
    { readBody: false },
  )
}
