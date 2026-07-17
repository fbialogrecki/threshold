import {
  eventsCall,
  EventsServiceConfigurationError,
} from "@/lib/events/client"
import { assertSameOrigin } from "@/lib/http/guard"
import {
  canonicalPostPayload,
  createdPostMatchesEvent,
  validateSelectedEvent,
} from "@/lib/social/post-create"
import { trustedAuthorHeaders } from "@/lib/social/client"
import { proxySocialMutation } from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

type PostRouteServices = {
  assertSameOrigin: typeof assertSameOrigin
  eventsCall: typeof eventsCall
  proxySocialMutation: typeof proxySocialMutation
  trustedAuthorHeaders: typeof trustedAuthorHeaders
}

const defaultServices: PostRouteServices = {
  assertSameOrigin,
  eventsCall,
  proxySocialMutation,
  trustedAuthorHeaders,
}

export function POST(request: Request) {
  return postWithServices(request, defaultServices)
}

export async function postWithServices(
  request: Request,
  services: PostRouteServices,
) {
  if (!(await services.assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  if (!(await services.trustedAuthorHeaders())) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }
  const payload: unknown = await request.clone().json().catch(() => null)
  let validation
  try {
    validation = await validateSelectedEvent(
      payload,
      (slug) => services.eventsCall(`/v1/events/${encodeURIComponent(slug)}`, {
        includeViewer: false,
      }),
    )
  } catch (error) {
    if (error instanceof EventsServiceConfigurationError) {
      return Response.json({ error: "event validation unavailable" }, { status: 503 })
    }
    throw error
  }
  if (!validation.ok) {
    return Response.json({ error: validation.error }, { status: validation.status })
  }
  const canonical = canonicalPostPayload(payload, validation.event)
  if (!canonical) {
    return Response.json(
      { error: "posts may attach images or an event, not both" },
      { status: 422 },
    )
  }
  const headers = new Headers(request.headers)
  headers.delete("content-length")
  const response = await services.proxySocialMutation(
    new Request(request.url, {
      method: "POST",
      headers,
      body: JSON.stringify(canonical),
    }),
    validation.event ? "/v1/event-posts" : "/v1/posts",
    "POST",
  )
  if (validation.event && (response.status === 404 || response.status === 405)) {
    return Response.json(
      { error: "social event posting is temporarily unavailable" },
      { status: 503, headers: { "retry-after": "30" } },
    )
  }
  if (response.ok && validation.event) {
    const body: unknown = await response.clone().json().catch(() => null)
    if (!createdPostMatchesEvent(body, validation.event)) {
      return Response.json(
        { error: "social service upgrade required" },
        { status: 503, headers: { "retry-after": "30" } },
      )
    }
  }
  return response
}
