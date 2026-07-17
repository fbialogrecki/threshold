import { describe, expect, it, mock } from "bun:test"

mock.module("server-only", () => ({}))
const { postWithServices } = await import("./route")

type Services = Parameters<typeof postWithServices>[1]

function request(payload: unknown) {
  return new Request("http://threshold.test/api/social/posts", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      origin: "http://threshold.test",
    },
    body: JSON.stringify(payload),
  })
}

function malformedRequest() {
  return new Request("http://threshold.test/api/social/posts", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      origin: "http://threshold.test",
    },
    body: "{",
  })
}

function services(overrides: Partial<Services> = {}): Services {
  return {
    assertSameOrigin: async () => true,
    trustedAuthorHeaders: async () => ({
      "X-Threshold-User-Id": "viewer-1",
    }),
    eventsCall: async () => ({
      status: 200,
      body: { id: "event-1", slug: "bass-theory" },
    }),
    proxySocialMutation: async (postRequest) => {
      const payload = await postRequest.json() as Record<string, unknown>
      return Response.json({ id: "post-1", ...payload }, { status: 201 })
    },
    ...overrides,
  }
}

describe("post write orchestration", () => {
  it("runs same-origin and authentication guards before parsing or service calls", async () => {
    let authCalls = 0
    let serviceCalls = 0
    const forbidden = await postWithServices(
      malformedRequest(),
      services({
        assertSameOrigin: async () => false,
        trustedAuthorHeaders: async () => {
          authCalls += 1
          return null
        },
        eventsCall: async () => {
          serviceCalls += 1
          return { status: 200, body: {} }
        },
        proxySocialMutation: async () => {
          serviceCalls += 1
          return Response.json({})
        },
      }),
    )
    expect(forbidden.status).toBe(403)
    expect(authCalls).toBe(0)
    expect(serviceCalls).toBe(0)

    const unauthenticated = await postWithServices(
      malformedRequest(),
      services({
        trustedAuthorHeaders: async () => null,
        eventsCall: async () => {
          serviceCalls += 1
          return { status: 200, body: {} }
        },
        proxySocialMutation: async () => {
          serviceCalls += 1
          return Response.json({})
        },
      }),
    )
    expect(unauthenticated.status).toBe(401)
    expect(serviceCalls).toBe(0)
  })

  it("posts canonical event attachments only to the event endpoint", async () => {
    const paths: string[] = []
    let forwarded: Record<string, unknown> = {}
    const response = await postWithServices(
      request({ body: "linked", event_slug: "bass-theory", event_id: "untrusted" }),
      services({
        proxySocialMutation: async (postRequest, path) => {
          paths.push(path)
          forwarded = await postRequest.json() as Record<string, unknown>
          return Response.json({ id: "post-1", ...forwarded }, { status: 201 })
        },
      }),
    )

    expect(paths).toEqual(["/v1/event-posts"])
    expect(forwarded).toMatchObject({
      event_id: "event-1",
      event_slug: "bass-theory",
    })
    expect(response.status).toBe(201)
  })

  it("maps old event-post endpoints to retryable 503 before mutation", async () => {
    const response = await postWithServices(
      request({ body: "linked", event_slug: "bass-theory" }),
      services({
        proxySocialMutation: async (_postRequest, path) => {
          expect(path).toBe("/v1/event-posts")
          return Response.json({ error: "not found" }, { status: 404 })
        },
      }),
    )

    expect(response.status).toBe(503)
    expect(response.headers.get("retry-after")).toBe("30")
  })

  it("posts image and text posts only to the ordinary endpoint", async () => {
    let eventCalls = 0
    const paths: string[] = []
    const response = await postWithServices(
      request({ body: "image", media_asset_ids: ["asset-1"] }),
      services({
        eventsCall: async () => {
          eventCalls += 1
          return { status: 500, body: null }
        },
        proxySocialMutation: async (_postRequest, path) => {
          paths.push(path)
          return Response.json({ id: "post-1" }, { status: 201 })
        },
      }),
    )

    expect(eventCalls).toBe(0)
    expect(paths).toEqual(["/v1/posts"])
    expect(response.status).toBe(201)
  })
})
