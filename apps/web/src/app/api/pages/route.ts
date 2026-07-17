import { createPage, listManagedPages, stripDevTokens, type PageCreatePayload } from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export const dynamic = "force-dynamic"

const PAGE_TYPES = new Set(["club", "collective", "project", "festival"])

export async function GET() {
  const principal = await requireSession()
  if (!principal.authenticated) return Response.json({ error: "unauthenticated" }, { status: 401 })
  try {
    const result = await listManagedPages()
    return Response.json(stripDevTokens(result.body), { status: result.status })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}

export async function POST(request: Request) {
  if (!(await assertSameOrigin(request))) return Response.json({ error: "forbidden" }, { status: 403 })
  const principal = await requireSession()
  if (!principal.authenticated) return Response.json({ error: "unauthenticated" }, { status: 401 })
  const body = (await request.json().catch(() => null)) as Record<string, unknown> | null
  const pageType = typeof body?.page_type === "string" && PAGE_TYPES.has(body.page_type) ? body.page_type : "club"
  const payload: PageCreatePayload = {
    slug: typeof body?.slug === "string" ? body.slug.trim().toLowerCase() : "",
    display_name: typeof body?.display_name === "string" ? body.display_name.trim() : "",
    page_type: pageType as PageCreatePayload["page_type"],
    city: typeof body?.city === "string" && body.city.trim() ? body.city.trim() : null,
    about: typeof body?.about === "string" && body.about.trim() ? body.about.trim() : null,
    links: [],
  }
  try {
    const result = await createPage(payload)
    return Response.json(stripDevTokens(result.body), { status: result.status })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}
