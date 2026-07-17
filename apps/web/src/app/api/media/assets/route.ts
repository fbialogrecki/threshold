import { MediaServiceConfigurationError, uploadMediaAsset } from "@/lib/media/client"
import { assertSameOrigin } from "@/lib/http/guard"

export const dynamic = "force-dynamic"
export const MAX_MEDIA_UPLOAD_BYTES = 10_100_000

type UploadServices = {
  assertSameOrigin: (request: Request) => Promise<boolean>
  uploadMediaAsset: (request: Request) => Promise<Response>
}

const defaultServices: UploadServices = { assertSameOrigin, uploadMediaAsset }

class MediaUploadTooLargeError extends Error {}

function isMediaUploadTooLarge(error: unknown): boolean {
  const seen = new Set<unknown>()
  let current = error
  for (let depth = 0; depth < 4 && current !== null && typeof current === "object"; depth += 1) {
    if (current instanceof MediaUploadTooLargeError) return true
    if (seen.has(current)) return false
    seen.add(current)
    current = "cause" in current ? current.cause : undefined
  }
  return false
}

function boundedUploadRequest(request: Request): Request {
  if (request.body === null) return request
  const reader = request.body.getReader()
  let total = 0
  const body = new ReadableStream<Uint8Array>({
    async pull(controller) {
      const { done, value } = await reader.read()
      if (done) {
        controller.close()
        return
      }
      total += value.byteLength
      if (total > MAX_MEDIA_UPLOAD_BYTES) {
        await reader.cancel("upload is too large")
        controller.error(new MediaUploadTooLargeError())
        return
      }
      controller.enqueue(value)
    },
    cancel(reason) {
      return reader.cancel(reason)
    },
  })
  return new Request(request, {
    body,
    duplex: "half",
  } as RequestInit & { duplex: "half" })
}

function contentLengthError(request: Request): Response | null {
  const value = request.headers.get("content-length")
  if (value === null) return null
  if (!/^\d+$/.test(value)) {
    return Response.json({ error: "invalid content-length" }, { status: 400 })
  }
  if (Number(value) > MAX_MEDIA_UPLOAD_BYTES) {
    return Response.json({ error: "upload is too large" }, { status: 413 })
  }
  return null
}

export async function postWithServices(
  request: Request,
  services: UploadServices,
): Promise<Response> {
  if (!(await services.assertSameOrigin(request))) {
    return Response.json({ error: "forbidden" }, { status: 403 })
  }
  const invalidLength = contentLengthError(request)
  if (invalidLength) return invalidLength

  try {
    return await services.uploadMediaAsset(boundedUploadRequest(request))
  } catch (error) {
    if (isMediaUploadTooLarge(error)) {
      return Response.json({ error: "upload is too large" }, { status: 413 })
    }
    if (error instanceof MediaServiceConfigurationError) {
      return Response.json({ error: "media service URL is not configured" }, { status: 503 })
    }
    throw error
  }
}

export async function POST(request: Request) {
  return postWithServices(request, defaultServices)
}
