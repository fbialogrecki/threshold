import { resolveUserReference } from "@/lib/api/users-read"
import { guardEventsMutation, proxyEventsGet, proxyEventsMutation } from "@/lib/events/client"
import { guardThenResolveUsername } from "@/lib/events/guarded-username"

export const dynamic = "force-dynamic"

type Context = { params: Promise<{ slug: string }> }
type GuestInput = { username?: unknown; artist_profile_id?: unknown }

export async function GET(_: Request, { params }: Context) {
  const { slug } = await params
  return proxyEventsGet(
    `/v1/events/${encodeURIComponent(slug)}/guestlist`,
    undefined,
    { includeViewer: true, requireViewer: true },
  )
}

export async function POST(request: Request, { params }: Context) {
  const { slug } = await params
  const prepared = await guardThenResolveUsername<GuestInput, Awaited<ReturnType<typeof resolveUserReference>>>({
    guard: () => guardEventsMutation(request),
    read: () => request.json().catch(() => null) as Promise<GuestInput | null>,
    username: (input) => typeof input.username === "string" ? input.username : null,
    resolve: resolveUserReference,
  })
  if (prepared.kind === "blocked") return prepared.response
  if (prepared.kind === "invalid") {
    return Response.json({ error: "username required" }, { status: 422 })
  }
  if (prepared.kind === "notFound" || !prepared.user) {
    return Response.json({ error: "user not found" }, { status: 422 })
  }
  const { input, user } = prepared

  const artistProfileId = typeof input.artist_profile_id === "string"
    ? input.artist_profile_id.trim()
    : ""
  return proxyEventsMutation(
    request,
    `/v1/events/${encodeURIComponent(slug)}/guestlist`,
    "POST",
    {
      json: {
        guest_user_id: user.userId,
        username: user.username,
        display_name: user.displayName,
        ...(artistProfileId ? { artist_profile_id: artistProfileId } : {}),
      },
    },
  )
}
