import { describe, expect, it } from "bun:test"

import {
  bootstrapCityGroup,
  buildEmptyFeedSuggestions,
  hasRequiredOnboardingCity,
  onboardingSubmissionSucceeded,
  parseOnboardingPayload,
  persistOnboarding,
} from "../plan"

describe("parseOnboardingPayload", () => {
  it("keeps city and scenes without accepting client-selected bootstrap targets", () => {
    const parsed = parseOnboardingPayload({
      city: " Wrocław ",
      preferredScenes: ["techno", "", 42, "acid"],
      initialGroups: ["techno-wroclaw", "../bad", "rave"],
      initialFollows: [
        { targetType: "club", targetHandle: "ciało" },
        { targetType: "admin", targetHandle: "root" },
        { targetType: "artist", targetHandle: "@dj-sub" },
      ],
    })

    expect(parsed).toEqual({
      city: "Wroclaw",
      preferredScenes: ["techno", "acid"],
    })
  })

  it("requires a canonical city", () => {
    expect(hasRequiredOnboardingCity(parseOnboardingPayload({
      city: "Warsaw",
      preferredScenes: [],
    }))).toBeTrue()
    expect(hasRequiredOnboardingCity(parseOnboardingPayload({
      city: "Unknown",
      preferredScenes: [],
    }))).toBeFalse()
  })
})

describe("bootstrapCityGroup", () => {
  it("resolves canonical Wroclaw against the exact seeded spelling and joins its real slug", async () => {
    const calls: { path: string; options?: { method?: string; userHeaders?: HeadersInit } }[] = []
    const result = await bootstrapCityGroup(
      "Wroclaw",
      { "X-Threshold-User-Id": "user-1" },
      async (path, options) => {
        calls.push({ path, options })
        if (path === "/v1/groups") {
          return {
            status: 200,
            body: [
              { slug: "community-one", city: "Wroclaw", official: false },
              { slug: "techno-wroclaw", city: "Wroclaw", official: true },
            ],
          }
        }
        return { status: 200, body: { status: "ok" } }
      },
    )

    expect(result).toEqual({ status: "joined", slug: "techno-wroclaw" })
    expect(calls.map(({ path }) => path)).toEqual([
      "/v1/groups",
      "/v1/groups/techno-wroclaw/membership",
    ])
    expect(calls[1]?.options?.method).toBe("POST")
  })

  it("succeeds honestly without joining a fuzzy or non-official match", async () => {
    const calls: string[] = []
    const result = await bootstrapCityGroup("Warsaw", {}, async (path) => {
      calls.push(path)
      return {
        status: 200,
        body: [
          { slug: "warsaw-nearby", city: "warsaw", official: true },
          { slug: "warsaw-unofficial", city: "Warsaw", official: false },
        ],
      }
    })

    expect(result).toEqual({ status: "not_found" })
    expect(calls).toEqual(["/v1/groups"])
  })
})

describe("persistOnboarding", () => {
  it("joins the official city group before marking onboarding complete", async () => {
    const order: string[] = []
    const persisted = await persistOnboarding(
      parseOnboardingPayload({
        city: "Warsaw",
        preferredScenes: ["techno"],
      }),
      async (payload) => {
        order.push("update")
        expect(payload).toEqual({
          city: "Warsaw",
          preferred_scenes: "techno",
        })
        return { status: 200, body: { saved: true } }
      },
      { "X-Threshold-User-Id": "user-1" },
      async (path) => {
        order.push(path)
        return path === "/v1/groups"
          ? {
              status: 200,
              body: [{ slug: "warsaw", city: "Warsaw", official: true }],
            }
          : { status: 200, body: { joined: true } }
      },
    )

    expect(order).toEqual([
      "/v1/groups",
      "/v1/groups/warsaw/membership",
      "update",
    ])
    expect(persisted.result.status).toBe(200)
    expect(persisted.cityGroup).toEqual({ status: "joined", slug: "warsaw" })
  })

  it("does not mark onboarding complete when city-group lookup fails", async () => {
    let updates = 0
    const persisted = await persistOnboarding(
      parseOnboardingPayload({ city: "Warsaw", preferredScenes: [] }),
      async () => {
        updates += 1
        return { status: 200, body: { saved: true } }
      },
      { "X-Threshold-User-Id": "user-1" },
      async () => ({ status: 503, body: null }),
    )

    expect(updates).toBe(0)
    expect(persisted.result.status).toBe(424)
    expect(persisted.cityGroup).toEqual({ status: "lookup_failed" })
  })

  it("does not persist required onboarding when joining the city group fails", async () => {
    let updates = 0
    const persisted = await persistOnboarding(
      parseOnboardingPayload({ city: "Wrocław", preferredScenes: [] }),
      async () => {
        updates += 1
        return { status: 200, body: { saved: true } }
      },
      { "X-Threshold-User-Id": "user-1" },
      async (path) => path === "/v1/groups"
        ? {
            status: 200,
            body: [{ slug: "techno-wroclaw", city: "Wroclaw", official: true }],
          }
        : { status: 503, body: null },
    )

    expect(updates).toBe(0)
    expect(persisted.result.status).toBe(424)
    expect(persisted.cityGroup).toEqual({
      status: "join_failed",
      slug: "techno-wroclaw",
    })
  })
})

describe("onboardingSubmissionSucceeded", () => {
  it("allows redirects only after a successful onboarding response", () => {
    expect(onboardingSubmissionSucceeded(200)).toBeTrue()
    expect(onboardingSubmissionSucceeded(204)).toBeTrue()
    expect(onboardingSubmissionSucceeded(400)).toBeFalse()
    expect(onboardingSubmissionSucceeded(503)).toBeFalse()
  })
})

describe("buildEmptyFeedSuggestions", () => {
  it("uses localized city copy and scenes without fake metrics", () => {
    expect(buildEmptyFeedSuggestions({ city: "Wroclaw", preferredScenes: "techno,acid" })).toEqual([
      "Join official Wroclaw groups",
      "Follow techno and acid pages",
      "Browse upcoming Wroclaw events",
    ])
    expect(buildEmptyFeedSuggestions({
      city: "Warsaw",
      preferredScenes: null,
      locale: "pl",
    })).toEqual([
      "Join official Warszawa groups",
      "Follow artists, clubs and collectives",
      "Browse upcoming Warszawa events",
    ])
  })
})
