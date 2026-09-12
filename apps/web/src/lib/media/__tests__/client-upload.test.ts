import { afterEach, describe, expect, it, mock, spyOn } from "bun:test"

mock.module("server-only", () => ({}))
const socialClient = await import("@/lib/social/client")
const { uploadMediaAsset } = await import("@/lib/media/client")

const originalFetch = globalThis.fetch
const originalMediaUrl = process.env.MEDIA_SERVICE_URL
const originalInternalToken = process.env.THRESHOLD_INTERNAL_TOKEN

function restoreEnvironment(name: string, value: string | undefined) {
  if (value === undefined) delete process.env[name]
  else process.env[name] = value
}

afterEach(() => {
  mock.restore()
  globalThis.fetch = originalFetch
  restoreEnvironment("MEDIA_SERVICE_URL", originalMediaUrl)
  restoreEnvironment("THRESHOLD_INTERNAL_TOKEN", originalInternalToken)
})

describe("media service upload client", () => {
  it("uses the inbound ReadableStream directly with Node fetch duplex", async () => {
    spyOn(socialClient, "trustedAuthorHeaders").mockResolvedValue({ "X-Threshold-User-Id": "user-1" })
    process.env.MEDIA_SERVICE_URL = "http://media.test"
    process.env.THRESHOLD_INTERNAL_TOKEN = "secret"
    const request = new Request("http://threshold.test/api/media/assets", {
      method: "POST",
      headers: {
        "content-type": "multipart/form-data; boundary=test",
        "content-length": "23",
      },
      body: "streamed multipart body",
    })
    let init: (RequestInit & { duplex?: string }) | undefined
    globalThis.fetch = mock(async (_url, options) => {
      init = options
      return Response.json({ id: "asset-1" }, { status: 201 })
    }) as unknown as typeof fetch

    const response = await uploadMediaAsset(request)

    expect(response.status).toBe(201)
    expect(init?.body).toBe(request.body)
    expect(init?.duplex).toBe("half")
    expect(new Headers(init?.headers).get("content-type")).toBe("multipart/form-data; boundary=test")
    expect(new Headers(init?.headers).get("content-length")).toBe("23")
  })
})
