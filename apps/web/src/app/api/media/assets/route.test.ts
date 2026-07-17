import { describe, expect, it, mock } from "bun:test"

mock.module("server-only", () => ({}))
const { MAX_MEDIA_UPLOAD_BYTES, postWithServices } = await import("./route")

type Services = Parameters<typeof postWithServices>[1]

function services(overrides: Partial<Services> = {}): Services {
  return {
    assertSameOrigin: async () => true,
    uploadMediaAsset: async () => Response.json({ id: "asset-1" }, { status: 201 }),
    ...overrides,
  }
}

describe("media upload proxy", () => {
  it("forwards a bounded request stream without parsing it into FormData", async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("streamed multipart body"))
        controller.close()
      },
    })
    const request = new Request("http://threshold.test/api/media/assets", {
      method: "POST",
      headers: {
        origin: "http://threshold.test",
        "content-type": "multipart/form-data; boundary=test",
      },
      body,
      duplex: "half",
    } as RequestInit & { duplex: "half" })
    let forwarded: Request | undefined

    const response = await postWithServices(request, services({
      uploadMediaAsset: async (incoming) => {
        forwarded = incoming
        return Response.json({ id: "asset-1" }, { status: 201 })
      },
    }))

    expect(response.status).toBe(201)
    expect(forwarded).toBeDefined()
    expect(forwarded).not.toBe(request)
    expect(await forwarded?.text()).toBe("streamed multipart body")
  })

  it("rejects oversized and malformed content-length before proxying", async () => {
    let proxyCalls = 0
    const svc = services({
      uploadMediaAsset: async () => {
        proxyCalls += 1
        return Response.json({})
      },
    })
    const oversized = new Request("http://threshold.test/api/media/assets", {
      method: "POST",
      headers: {
        origin: "http://threshold.test",
        "content-length": String(MAX_MEDIA_UPLOAD_BYTES + 1),
      },
      body: "x",
    })
    const malformed = new Request("http://threshold.test/api/media/assets", {
      method: "POST",
      headers: { origin: "http://threshold.test", "content-length": "wat" },
      body: "x",
    })

    const oversizedResponse = await postWithServices(oversized, svc)
    const malformedResponse = await postWithServices(malformed, svc)

    expect(oversizedResponse.status).toBe(413)
    expect(await oversizedResponse.json()).toEqual({ error: "upload is too large" })
    expect(malformedResponse.status).toBe(400)
    expect(await malformedResponse.json()).toEqual({ error: "invalid content-length" })
    expect(proxyCalls).toBe(0)
  })

  it("maps a fetch-wrapped streamed size violation to 413", async () => {
    const request = new Request("http://threshold.test/api/media/assets", {
      method: "POST",
      headers: { origin: "http://threshold.test" },
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new Uint8Array(MAX_MEDIA_UPLOAD_BYTES))
          controller.enqueue(new Uint8Array(1))
          controller.close()
        },
      }),
      duplex: "half",
    } as RequestInit & { duplex: "half" })

    const response = await postWithServices(request, services({
      uploadMediaAsset: async (incoming) => {
        try {
          await incoming.arrayBuffer()
        } catch (error) {
          throw new TypeError("fetch failed", { cause: error })
        }
        return Response.json({})
      },
    }))

    expect(response.status).toBe(413)
    expect(await response.json()).toEqual({ error: "upload is too large" })
  })
})
