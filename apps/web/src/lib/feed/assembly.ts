import type { NotificationItem } from "@/lib/auth/product-auth"
import type { AccessState, AccessUpdate, EventUpdate, FeedFilter, FeedItem, Post, ThresholdEvent } from "@/lib/types"

const ACCESS_NOTIFICATION_TYPES = new Set([
  "guestlist.added",
  "guestlist.removed",
  "guestlist.dj_quota_changed",
  "secret_location.access_granted",
  "secret_location.access_revoked",
])

type FutureFeedKind = Extract<FeedItem["kind"], "residency_update" | "lineup_update" | "guestlist_update">

export type FeedAssemblySource = {
  posts: Post[]
  events: ThresholdEvent[]
  eventUpdates: EventUpdate[]
  notifications: NotificationItem[]
  followedPageIds: Set<string>
  followedUserIds: Set<string>
  representedEventIds: Set<string>
  representedEventSlugs: Set<string>
  legacyRepresentedEventSlugs: Set<string>
  viewerCity: string | null
  filter: FeedFilter
  limit?: number
}

const FILTER_KIND: Record<Exclude<FeedFilter, "all">, Set<FeedItem["kind"]>> = {
  posts: new Set(["post"]),
  events: new Set(["event", "event_update"]),
  access: new Set(["access_update", "guestlist_update"]),
}

export const FUTURE_FEED_KINDS: FutureFeedKind[] = [
  "residency_update",
  "lineup_update",
  "guestlist_update",
]

function clean(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed ? trimmed.toLowerCase() : null
}

function eventTime(event: ThresholdEvent): string {
  return event.created_at || event.updated_at || event.starts_at
}

function stableId(item: FeedItem): string {
  switch (item.kind) {
    case "post":
      return item.post.id
    case "event":
      return item.event.id || item.event.slug
    case "access_update":
      return item.update.id
    case "event_update":
      return item.update.id
    case "residency_update":
    case "lineup_update":
    case "guestlist_update":
      return item.kind
  }
}

function timestampEpoch(value: string): number {
  const epoch = Date.parse(value)
  return Number.isNaN(epoch) ? Number.NEGATIVE_INFINITY : epoch
}

function matchesFilter(item: FeedItem, filter: FeedFilter): boolean {
  return filter === "all" || FILTER_KIND[filter].has(item.kind)
}

export function eventVisibleInFeed(event: ThresholdEvent, source: Pick<FeedAssemblySource, "followedPageIds" | "followedUserIds" | "viewerCity">): string | null {
  if (event.page_id && source.followedPageIds.has(event.page_id)) return "You follow this page"
  if (event.created_by_user_id && source.followedUserIds.has(event.created_by_user_id)) return "You follow this organizer"
  if (event.is_following) return "You follow this event"
  if (clean(event.city) && clean(event.city) === clean(source.viewerCity)) return "Your city scene"
  return null
}

function accessState(type: string, metadata: NotificationItem["metadata"]): AccessState {
  const raw = metadata.access_state
  if (raw === "locked" || raw === "pending" || raw === "approved" || raw === "rejected") return raw
  if (type === "guestlist.removed" || type === "secret_location.access_revoked") return "rejected"
  if (type === "guestlist.added" || type === "secret_location.access_granted") return "approved"
  return "pending"
}

function eventRef(notification: NotificationItem): AccessUpdate["event"] | null {
  const slugFromMetadata = notification.metadata.event_slug
  const titleFromMetadata = notification.metadata.event_title
  const slugFromUrl = notification.target_url?.match(/^\/events\/([^/?#]+)/)?.[1]
  const slug = typeof slugFromMetadata === "string" ? slugFromMetadata : slugFromUrl
  if (!slug) return null
  return {
    slug,
    title: typeof titleFromMetadata === "string" ? titleFromMetadata : notification.title,
  }
}

export function notificationToFeedItem(notification: NotificationItem): Extract<FeedItem, { kind: "access_update" }> | null {
  if (!ACCESS_NOTIFICATION_TYPES.has(notification.type)) return null
  const event = eventRef(notification)
  if (!event) return null
  return {
    kind: "access_update",
    update: {
      id: notification.id,
      createdAtIso: notification.created_at,
      event,
      state: accessState(notification.type, notification.metadata),
      note: notification.body || notification.title,
    },
    feed: {
      publishedAtIso: notification.created_at,
      source: "notifications",
      reason: "Your access changed",
    },
  }
}

export function assembleFeed(source: FeedAssemblySource): FeedItem[] {
  const legacyRepresentedEventSlugs = new Set(
    [...source.legacyRepresentedEventSlugs].map((slug) => slug.toLowerCase()),
  )
  const admittedEvents = source.events.flatMap((event): { event: ThresholdEvent; reason: string }[] => {
    const reason = eventVisibleInFeed(event, source)
    return reason ? [{ event, reason }] : []
  })
  const visibleEventIds = new Set(admittedEvents.map(({ event }) => event.id))
  const visibleEventSlugs = new Set(admittedEvents.map(({ event }) => event.slug))
  const visibleEvents: Extract<FeedItem, { kind: "event" }>[] = admittedEvents.flatMap(({ event, reason }) =>
    source.representedEventIds.has(event.id)
      || legacyRepresentedEventSlugs.has(event.slug.toLowerCase())
      ? []
      : [{ kind: "event", event, feed: { publishedAtIso: eventTime(event), source: "events", reason } }],
  )

  const items: FeedItem[] = [
    ...source.posts.map((post): FeedItem => ({
      kind: "post",
      post,
      feed: {
        publishedAtIso: post.createdAtIso,
        source: "social",
        reason: "From your following feed",
      },
    })),
    ...visibleEvents,
    ...source.eventUpdates.flatMap((update): FeedItem[] => (
      visibleEventIds.has(update.eventId) || visibleEventSlugs.has(update.event.slug)
        ? [{
            kind: "event_update",
            update,
            feed: {
              publishedAtIso: update.createdAtIso,
              source: "events",
              reason: "Event organizer update",
            },
          }]
        : []
    )),
    ...source.notifications.flatMap((notification): FeedItem[] => {
      const item = notificationToFeedItem(notification)
      return item ? [item] : []
    }),
  ]

  return items
    .filter((item) => matchesFilter(item, source.filter))
    .sort((a, b) => {
      const aEpoch = timestampEpoch(a.feed.publishedAtIso)
      const bEpoch = timestampEpoch(b.feed.publishedAtIso)
      if (aEpoch !== bEpoch) return bEpoch > aEpoch ? 1 : -1
      return stableId(a).localeCompare(stableId(b))
    })
    .slice(0, source.limit ?? 50)
}
