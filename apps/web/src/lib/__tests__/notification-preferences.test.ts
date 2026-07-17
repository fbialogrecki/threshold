import { describe, expect, it } from "bun:test"

import {
  notificationPreferenceLoad,
  notificationPreferencePayload,
  notificationPreferences,
} from "@/lib/notification-preferences"

describe("notification preferences", () => {
  it("keeps only supported boolean fields", () => {
    expect(notificationPreferencePayload({
      mentions_enabled: false,
      engagement_enabled: true,
      event_updates_enabled: "yes",
      admin: true,
    })).toEqual({ mentions_enabled: false, engagement_enabled: true })
  })

  it("requires a complete GET response", () => {
    expect(notificationPreferences({
      mentions_enabled: true,
      engagement_enabled: false,
      event_updates_enabled: true,
      page_updates_enabled: false,
    })).toEqual({
      mentions_enabled: true,
      engagement_enabled: false,
      event_updates_enabled: true,
      page_updates_enabled: false,
    })
    expect(notificationPreferences({ mentions_enabled: true })).toBeNull()
    expect(notificationPreferences({ error: "unavailable" })).toBeNull()
  })

  it("withholds controls until a complete successful GET", () => {
    const body = {
      mentions_enabled: true,
      engagement_enabled: false,
      event_updates_enabled: true,
      page_updates_enabled: false,
    }
    expect(notificationPreferenceLoad(200, body)).toEqual({ status: "ready", data: body })
    expect(notificationPreferenceLoad(503, body)).toEqual({ status: "error" })
    expect(notificationPreferenceLoad(200, { mentions_enabled: true })).toEqual({ status: "error" })
  })
})
