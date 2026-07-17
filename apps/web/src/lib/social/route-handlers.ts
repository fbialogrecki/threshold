import "server-only"

import { assertSameOrigin } from "@/lib/http/guard"
import { enforceLocalRateLimit, type RateLimitPolicy } from "@/lib/http/local-rate-limit"
import { safeLogFailure } from "@/lib/http/safe-log"
import {
  socialCall,
  SocialServiceConfigurationError,
  trustedAuthorHeaders,
} from "@/lib/social/client"

function responseFromSocial(result: { status: number; body: unknown }): Response {
  if (result.status === 204) return new Response(null, { status: 204 })
  return Response.json(result.body, { status: result.status })
}

function configErrorResponse(): Response {
  return Response.json(
    { error: "social service URL or internal token is not configured" },
    { status: 503 },
  )
}

async function readJson(request: Request): Promise<unknown> {
  return request.json().catch(() => null)
}

export async function proxySocialGet(
  path: string,
  request?: Request,
  options: { requireUser?: boolean } = {},
): Promise<Response> {
  try {
    const query = request ? new URL(request.url).searchParams : undefined
    // Viewer headers come from the BFF session only (never from the client);
    // when present they let social compute viewer_* fields on reads.
    const trustedHeaders = await trustedAuthorHeaders()
    if (options.requireUser && !trustedHeaders) {
      return Response.json({ error: "unauthenticated" }, { status: 401 })
    }
    const userHeaders = trustedHeaders ?? undefined
    return responseFromSocial(await socialCall(path, { query, userHeaders }))
  } catch (error) {
    if (error instanceof SocialServiceConfigurationError) {
      safeLogFailure({ service: "social", operation: "proxy_get", kind: "configuration" }, error)
      return configErrorResponse()
    }
    safeLogFailure({ service: "social", operation: "proxy_get", kind: "unavailable" }, error)
    return Response.json({ error: "social service unavailable" }, { status: 502 })
  }
}

export async function proxySocialMutation(
  request: Request,
  path: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  options: {
    readBody?: boolean
    forwardQuery?: boolean
    localRateLimit?: { scope: string; policy: RateLimitPolicy }
  } = { readBody: true },
): Promise<Response> {
  if (!(await assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }

  const userHeaders = await trustedAuthorHeaders()
  if (!userHeaders) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }
  if (options.localRateLimit) {
    const limited = enforceLocalRateLimit(
      request,
      options.localRateLimit.scope,
      options.localRateLimit.policy,
    )
    if (limited) return limited
  }

  try {
    const json = options.readBody === false ? undefined : await readJson(request)
    const query = options.forwardQuery ? new URL(request.url).searchParams : undefined
    return responseFromSocial(await socialCall(path, { method, json, query, userHeaders }))
  } catch (error) {
    if (error instanceof SocialServiceConfigurationError) {
      safeLogFailure({ service: "social", operation: "proxy_mutation", kind: "configuration" }, error)
      return configErrorResponse()
    }
    safeLogFailure({ service: "social", operation: "proxy_mutation", kind: "unavailable" }, error)
    return Response.json({ error: "social service unavailable" }, { status: 502 })
  }
}
