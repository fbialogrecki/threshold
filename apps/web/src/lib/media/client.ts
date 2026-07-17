import "server-only"

import { mediaCacheControl } from "@/lib/media/cache"
import { trustedAuthorHeaders } from "@/lib/social/client"

export class MediaServiceConfigurationError extends Error {
  constructor(message = "MEDIA_SERVICE_URL or THRESHOLD_INTERNAL_TOKEN is not configured") {
    super(message)
    this.name = "MediaServiceConfigurationError"
  }
}

function baseUrl(): string {
  const value = process.env.MEDIA_SERVICE_URL
  if (!value?.trim()) throw new MediaServiceConfigurationError()
  return value.replace(/\/$/, "")
}

function internalToken(): string {
  const value = process.env.THRESHOLD_INTERNAL_TOKEN
  if (!value?.trim()) throw new MediaServiceConfigurationError()
  return value
}

export async function uploadMediaAsset(request: Request): Promise<Response> {
  const userHeaders = await trustedAuthorHeaders()
  if (!userHeaders) return Response.json({ error: "unauthenticated" }, { status: 401 })

  const headers = new Headers({
    "X-Threshold-Internal-Token": internalToken(),
    ...userHeaders,
  })
  for (const name of ["content-type", "content-length"]) {
    const value = request.headers.get(name)
    if (value !== null) headers.set(name, value)
  }
  const response = await fetch(`${baseUrl()}/v1/assets/upload`, {
    method: "POST",
    headers,
    body: request.body,
    duplex: "half",
    cache: "no-store",
  } as RequestInit & { duplex: "half" })
  return new Response(response.body, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  })
}

export async function fetchMediaAsset(path: string): Promise<Response> {
  const response = await fetch(`${baseUrl()}/media/assets/${path}`, {
    headers: { "X-Threshold-Internal-Token": internalToken() },
    cache: "no-store",
  })
  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") ?? "application/octet-stream",
      "cache-control": mediaCacheControl(response.status),
    },
  })
}

