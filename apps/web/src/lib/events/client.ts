import "server-only"

import { assertSameOrigin, requireSession } from "@/lib/http/guard"
import { safeLogFailure } from "@/lib/http/safe-log"
import { trustedAuthorHeaders } from "@/lib/social/client"

export class EventsServiceConfigurationError extends Error {
  constructor(message = "EVENTS_SERVICE_URL or THRESHOLD_INTERNAL_TOKEN is not configured") {
    super(message)
    this.name = "EventsServiceConfigurationError"
  }
}

function baseUrl(): string {
  const value = process.env.EVENTS_SERVICE_URL
  if (!value?.trim()) throw new EventsServiceConfigurationError()
  return value.replace(/\/$/, "")
}

function internalToken(): string {
  const value = process.env.THRESHOLD_INTERNAL_TOKEN
  if (!value?.trim()) throw new EventsServiceConfigurationError()
  return value
}

export async function eventsCall(
  path: string,
  options: {
    method?: string
    json?: unknown
    query?: URLSearchParams
    includeViewer?: boolean
    requireViewer?: boolean
  } = {},
) {
  const isMutation = !!options.method && options.method !== "GET"
  const includeViewer = options.includeViewer ?? isMutation
  const requireViewer = options.requireViewer ?? isMutation
  const userHeaders = includeViewer ? await trustedAuthorHeaders() : null
  if (requireViewer && !userHeaders) {
    return { status: 401, body: { error: "unauthenticated" } }
  }
  const headers = new Headers({
    accept: "application/json",
    "X-Threshold-Internal-Token": internalToken(),
    ...(userHeaders ?? {}),
  })
  let body: string | undefined
  if (options.json !== undefined) {
    headers.set("content-type", "application/json")
    body = JSON.stringify(options.json)
  }
  const query = options.query?.toString()
  const response = await fetch(`${baseUrl()}${path}${query ? `?${query}` : ""}`, {
    method: options.method ?? "GET",
    headers,
    body,
    cache: "no-store",
  })
  const text = await response.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text)
    } catch {
      parsed = text
    }
  }
  return { status: response.status, body: parsed }
}

function responseFromEvents(result: { status: number; body: unknown }): Response {
  if (result.status === 204) return new Response(null, { status: 204 })
  return Response.json(result.body, { status: result.status })
}

export async function guardEventsMutation(request: Request): Promise<Response | null> {
  if (!(await assertSameOrigin(request))) return Response.json({ error: "forbidden" }, { status: 403 })
  if (!(await requireSession()).authenticated) {
    return Response.json({ error: "unauthenticated" }, { status: 401 })
  }
  return null
}

function eventsConfigErrorResponse(): Response {
  return Response.json({ error: "events service URL is not configured" }, { status: 503 })
}

async function readJson(request: Request): Promise<unknown> {
  return request.json().catch(() => null)
}

export async function proxyEventsGet(
  path: string,
  request?: Request,
  options: {
    includeViewer?: boolean
    requireViewer?: boolean
    successBody?: (body: unknown) => unknown | null
  } = {},
): Promise<Response> {
  try {
    const query = request ? new URL(request.url).searchParams : undefined
    const result = await eventsCall(path, { ...options, query })
    if (result.status >= 200 && result.status < 300 && options.successBody) {
      const body = options.successBody(result.body)
      return body === null
        ? Response.json({ error: "invalid upstream response" }, { status: 502 })
        : Response.json(body, { status: result.status })
    }
    return responseFromEvents(result)
  } catch (error) {
    if (error instanceof EventsServiceConfigurationError) {
      safeLogFailure({ service: "events", operation: "proxy_get", kind: "configuration" }, error)
      return eventsConfigErrorResponse()
    }
    safeLogFailure({ service: "events", operation: "proxy_get", kind: "unavailable" }, error)
    return Response.json({ error: "events service unavailable" }, { status: 502 })
  }
}

export async function proxyEventsMutation(
  request: Request,
  path: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  options: {
    readBody?: boolean
    forwardQuery?: boolean
    json?: unknown
    successBody?: (body: unknown) => unknown | null
    hideErrorBody?: boolean
  } = { readBody: true },
): Promise<Response> {
  const guard = await guardEventsMutation(request)
  if (guard) return guard
  try {
    const json = options.json ?? (options.readBody === false ? undefined : await readJson(request))
    const query = options.forwardQuery ? new URL(request.url).searchParams : undefined
    const result = await eventsCall(path, { method, json, query })
    if (result.status >= 200 && result.status < 300 && options.successBody && result.status !== 204) {
      const body = options.successBody(result.body)
      return body === null
        ? Response.json({ error: "invalid upstream response" }, { status: 502 })
        : Response.json(body, { status: result.status })
    }
    if ((result.status < 200 || result.status >= 300) && options.hideErrorBody) {
      return Response.json({ error: "upstream request failed" }, { status: result.status })
    }
    return responseFromEvents(result)
  } catch (error) {
    if (error instanceof EventsServiceConfigurationError) {
      safeLogFailure({ service: "events", operation: "proxy_mutation", kind: "configuration" }, error)
      return eventsConfigErrorResponse()
    }
    safeLogFailure({ service: "events", operation: "proxy_mutation", kind: "unavailable" }, error)
    return Response.json({ error: "events service unavailable" }, { status: 502 })
  }
}
