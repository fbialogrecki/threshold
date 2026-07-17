import { afterEach, describe, expect, it, mock } from "bun:test"

mock.module("server-only", () => ({}))
mock.module("@/lib/social/client", () => ({
  trustedAuthorHeaders: async () => ({ "X-Threshold-User-Id": "user-1" }),
}))
const { uploadMediaAsset } = await import("@/lib/media/client")

const originalFetch = globalThis.fetch

afterEach(() => {
  globalThis.fetch = originalFetch
})

describe("media service upload client", () => {
  it("uses the inbound ReadableStream directly with Node fetch duplex", async () => {
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
