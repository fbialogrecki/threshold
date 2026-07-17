import { proxySocialGet } from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params
  return proxySocialGet(`/v1/groups/${encodeURIComponent(slug)}`)
}
