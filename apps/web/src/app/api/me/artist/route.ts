import { stripDevTokens, updateArtist } from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export const dynamic = "force-dynamic"

/** Create / update the Artist profile -> users POST /v1/me/artist. */
export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  const principal = await requireSession()
  if (!principal.authenticated) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }

  const body = (await request.json().catch(() => null)) as {
    role?: unknown
    location?: unknown
    links?: unknown
  } | null

  const links = Array.isArray(body?.links)
    ? body.links
        .map((entry) => {
          if (typeof entry !== "object" || entry === null) return null
          const { label, url } = entry as { label?: unknown; url?: unknown }
          if (typeof label !== "string" || typeof url !== "string") return null
          if (!/^https?:\/\//.test(url)) return null
          return { label, url }
        })
        .filter((link): link is { label: string; url: string } => link !== null)
    : []

  try {
    const result = await updateArtist({
      role: typeof body?.role === "string" ? body.role : null,
      location: typeof body?.location === "string" ? body.location : null,
      links,
    })
    if (result.status >= 400) {
      return Response.json({ error: "artist profile update failed" }, { status: result.status })
    }
    return Response.json(stripDevTokens(result.body), { status: 200 })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}
