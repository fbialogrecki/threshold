import { describe, expect, it } from "bun:test"

import {
  notificationHref,
  notificationIsUnread,
  notificationMessage,
  notificationRole,
  notificationTypeKey,
  notificationUnreadCount,
  unreadBadgeLabel,
  updatePendingIds,
} from "@/lib/notifications"

describe("notification helpers", () => {
  it("maps known backend types without exposing raw type strings", () => {
    expect(notificationTypeKey("mention.created")).toBe("mention")
    expect(notificationTypeKey("comment.created")).toBe("comment")
    expect(notificationTypeKey("guestlist.added")).toBe("guestlistAdded")
    expect(notificationTypeKey("unknown.type")).toBe("activity")
  })

  it("keeps only safe internal targets", () => {
    expect(notificationHref({ type: "follow.created", target_url: "/u/dj-one" })).toBe("/u/dj-one")
    expect(notificationHref({ type: "follow.created", target_url: "//evil.test" })).toBeNull()
    expect(notificationHref({ type: "follow.created", target_url: "https://evil.test" })).toBeNull()
  })

  it("derives unread state from read_at", () => {
    expect(notificationIsUnread({ type: "follow.created", read_at: null })).toBe(true)
    expect(notificationIsUnread({ type: "follow.created", read_at: "2026-07-10T10:00:00Z" })).toBe(false)
  })

  it("builds localized known messages from structured metadata", () => {
    expect(notificationMessage({
      type: "follow.created",
      title: "stored English is ignored",
      metadata: { actor_display_name: "DJ Żuraw" },
    })).toMatchObject({
      titleKey: "followNamed",
      values: { actor: "DJ Żuraw" },
      localized: true,
    })
    expect(notificationMessage({
      type: "page.member_upserted",
      metadata: { page_name: "Praga Noise", role: "admin" },
    })).toMatchObject({
      titleKey: "pageRoleNamed",
      values: { page: "Praga Noise", role: "admin" },
    })
    expect(notificationRole("future-role")).toBe("unknown")
  })

  it("tracks overlapping read operations independently", () => {
    const both = updatePendingIds(updatePendingIds(new Set(), "one", true), "two", true)
    const remaining = updatePendingIds(both, "one", false)
    expect([...remaining]).toEqual(["two"])
  })

  it("normalizes the shared unread badge value", () => {
    expect(notificationUnreadCount({ count: 7 })).toBe(7)
    expect(notificationUnreadCount({ count: -1 })).toBe(0)
    expect(notificationUnreadCount({ count: "7" })).toBe(0)
    expect(unreadBadgeLabel(7)).toBe("7")
    expect(unreadBadgeLabel(120)).toBe("99+")
  })
})
