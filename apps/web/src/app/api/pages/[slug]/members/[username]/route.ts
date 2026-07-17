import { removePageMember, setPageMember } from "@/lib/auth/product-auth"
import { UsersServiceConfigurationError } from "@/lib/auth/users-service-url"
import { assertSameOrigin, requireSession } from "@/lib/http/guard"

export const dynamic = "force-dynamic"

type Params = { params: Promise<{ slug: string; username: string }> }

export async function PUT(request: Request, { params }: Params) {
  if (!(await assertSameOrigin(request))) return Response.json({ error: "forbidden" }, { status: 403 })
  const principal = await requireSession()
  if (!principal.authenticated) return Response.json({ error: "unauthenticated" }, { status: 401 })
  const { slug, username } = await params
  const body = (await request.json().catch(() => null)) as { role?: unknown } | null
  const role = body?.role === "admin" ? "admin" : "editor"
  try {
    const result = await setPageMember(slug, username, role)
    return Response.json(result.body, { status: result.status })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}

export async function DELETE(request: Request, { params }: Params) {
  if (!(await assertSameOrigin(request))) return Response.json({ error: "forbidden" }, { status: 403 })
  const principal = await requireSession()
  if (!principal.authenticated) return Response.json({ error: "unauthenticated" }, { status: 401 })
  const { slug, username } = await params
  try {
    const result = await removePageMember(slug, username)
    return new Response(null, { status: result.status })
  } catch (error) {
    if (error instanceof UsersServiceConfigurationError) {
      return Response.json({ error: "users service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}
