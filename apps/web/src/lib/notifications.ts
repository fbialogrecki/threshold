import { safeInternalHref } from "@/lib/safe-href"

export type NotificationView = {
  type: string
  target_url?: string | null
  read_at?: string | null
  title?: string
  body?: string | null
  metadata?: Record<string, string | number | boolean | null>
}

export type NotificationTypeKey =
  | "activity"
  | "comment"
  | "eventUpdate"
  | "follow"
  | "groupPost"
  | "guestlistAdded"
  | "guestlistQuota"
  | "guestlistRemoved"
  | "mention"
  | "pageRole"
  | "pageUpdate"
  | "reaction"
  | "residency"
  | "vote"

const TYPE_KEYS: Record<string, NotificationTypeKey> = {
  "comment.created": "comment",
  "event.created": "eventUpdate",
  "event.post.created": "eventUpdate",
  "event.updated": "eventUpdate",
  "follow.created": "follow",
  "group.post.created": "groupPost",
  "guestlist.added": "guestlistAdded",
  "guestlist.dj_quota_changed": "guestlistQuota",
  "guestlist.removed": "guestlistRemoved",
  "mention.created": "mention",
  "page.member_removed": "pageRole",
  "page.member_upserted": "pageRole",
  "page.owner_assigned": "pageRole",
  "page.post.created": "pageUpdate",
  "page.updated": "pageUpdate",
  "page.mentioned": "mention",
  "reaction.created": "reaction",
  "residency.accepted": "residency",
  "residency.invited": "residency",
  "residency.rejected": "residency",
  "user.mentioned": "mention",
  "vote.created": "vote",
}

export function notificationTypeKey(type: string): NotificationTypeKey {
  return TYPE_KEYS[type] ?? "activity"
}

export function notificationHref(notification: NotificationView): string | null {
  return safeInternalHref(notification.target_url)
}

export function notificationIsUnread(notification: NotificationView): boolean {
  return !notification.read_at
}

export function notificationRole(value: unknown): "owner" | "admin" | "editor" | "unknown" {
  return value === "owner" || value === "admin" || value === "editor" ? value : "unknown"
}

function text(metadata: NotificationView["metadata"], ...keys: string[]): string | null {
  for (const key of keys) {
    const value = metadata?.[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return null
}

export type NotificationMessageKey =
  | "comment"
  | "commentNamed"
  | "eventUpdate"
  | "eventUpdateNamed"
  | "follow"
  | "followNamed"
  | "groupPost"
  | "guestlistAdded"
  | "guestlistAddedNamed"
  | "guestlistQuota"
  | "guestlistQuotaNamed"
  | "guestlistRemoved"
  | "guestlistRemovedNamed"
  | "mention"
  | "mentionNamed"
  | "pageRole"
  | "pageRoleNamed"
  | "pageRoleRemoved"
  | "pageRoleRemovedNamed"
  | "pageUpdate"
  | "pageUpdateNamed"
  | "reaction"
  | "reactionNamed"
  | "residencyAccepted"
  | "residencyAcceptedNamed"
  | "residencyInvited"
  | "residencyInvitedNamed"
  | "residencyRejected"
  | "residencyRejectedNamed"
  | "vote"
  | "voteNamed"

export type NotificationMessage = {
  titleKey: NotificationMessageKey | null
  values: Record<string, string>
  body: string | null
  localized: boolean
}

export function notificationMessage(notification: NotificationView): NotificationMessage {
  const metadata = notification.metadata
  const actor = text(metadata, "actor_display_name", "actor_username", "actor_handle")
  const event = text(metadata, "event_title")
  const page = text(metadata, "page_name")
  const known = (
    titleKey: NotificationMessageKey,
    values: Record<string, string> = {},
    body: string | null = null,
  ): NotificationMessage => ({ titleKey, values, body, localized: true })

  switch (notification.type) {
    case "follow.created":
      return known(actor ? "followNamed" : "follow", actor ? { actor } : {})
    case "comment.created":
      return known(actor ? "commentNamed" : "comment", actor ? { actor } : {})
    case "mention.created":
    case "page.mentioned":
    case "user.mentioned":
      return known(actor ? "mentionNamed" : "mention", actor ? { actor } : {})
    case "event.created":
    case "event.updated":
    case "event.post.created":
      return known(
        event ? "eventUpdateNamed" : "eventUpdate",
        event ? { event } : {},
        notification.type === "event.post.created" ? notification.body ?? null : null,
      )
    case "guestlist.added":
      return known(event ? "guestlistAddedNamed" : "guestlistAdded", event ? { event } : {})
    case "guestlist.removed":
      return known(event ? "guestlistRemovedNamed" : "guestlistRemoved", event ? { event } : {})
    case "guestlist.dj_quota_changed":
      return known(event ? "guestlistQuotaNamed" : "guestlistQuota", event ? { event } : {})
    case "page.member_removed":
      return known(page ? "pageRoleRemovedNamed" : "pageRoleRemoved", page ? { page } : {})
    case "page.member_upserted":
    case "page.owner_assigned": {
      const role = notificationRole(metadata?.role)
      return known(
        page ? "pageRoleNamed" : "pageRole",
        page ? { page, role } : { role },
      )
    }
    case "residency.invited":
      return known(page ? "residencyInvitedNamed" : "residencyInvited", page ? { page } : {})
    case "residency.accepted":
      return known(actor ? "residencyAcceptedNamed" : "residencyAccepted", actor ? { actor } : {})
    case "residency.rejected":
      return known(actor ? "residencyRejectedNamed" : "residencyRejected", actor ? { actor } : {})
    case "reaction.created":
      return known(actor ? "reactionNamed" : "reaction", actor ? { actor } : {})
    case "vote.created":
      return known(actor ? "voteNamed" : "vote", actor ? { actor } : {})
    case "page.post.created":
    case "page.updated":
      return known(page ? "pageUpdateNamed" : "pageUpdate", page ? { page } : {})
    case "group.post.created":
      return known("groupPost")
    default:
      return {
        titleKey: null,
        values: {},
        body: notification.body ?? null,
        localized: false,
      }
  }
}

export function updatePendingIds(
  current: ReadonlySet<string>,
  id: string,
  pending: boolean,
): Set<string> {
  const next = new Set(current)
  if (pending) next.add(id)
  else next.delete(id)
  return next
}

export function notificationUnreadCount(value: unknown): number {
  if (!value || typeof value !== "object" || !("count" in value)) return 0
  const count = (value as { count?: unknown }).count
  return typeof count === "number" && Number.isFinite(count) && count > 0
    ? Math.floor(count)
    : 0
}

export function unreadBadgeLabel(count: number): string {
  return count > 99 ? "99+" : String(Math.max(0, Math.floor(count)))
}
