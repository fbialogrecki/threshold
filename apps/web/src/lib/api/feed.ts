import "server-only"

import { auth } from "@/auth"
import {
  getEventFeedCandidates,
  getEventsBatchResult,
  listEvents,
  listEventUpdates,
} from "@/lib/api/events"
import {
  getEventAnnouncementPosts,
  getFeedPosts,
} from "@/lib/api/social-read"
import { getFollowedTargets, getOrganizerRefs } from "@/lib/api/users-read"
import { listNotifications, type NotificationItem } from "@/lib/auth/product-auth"
import { canonicalCity } from "@/lib/cities"
import { feedEventScopes, feedIncludesEvents } from "@/lib/events/query"
import { assembleFeed } from "@/lib/feed/assembly"
import {
  hydrateFeedPosts,
  mergeFeedEvents,
  missingPostEventSlugs,
  organizerPageIds,
} from "@/lib/feed/hydration"
import type { FeedFilter, FeedItem, FollowTarget, ThresholdEvent } from "@/lib/types"

function asNotifications(body: unknown): NotificationItem[] {
  return Array.isArray(body) ? (body as NotificationItem[]) : []
}

async function notificationCandidates(
  getNotifications: typeof listNotifications,
): Promise<NotificationItem[]> {
  try {
    const { status, body } = await getNotifications()
    return status === 200 ? asNotifications(body) : []
  } catch {
    return []
  }
}

function splitFollowTargets(follows: FollowTarget[]) {
  const followedPageIds = new Set<string>()
  const followedUserIds = new Set<string>()
  for (const follow of follows) {
    if (!follow.target_id) continue
    if (
      follow.target_type === "page"
      || follow.target_type === "club"
      || follow.target_type === "collective"
      || follow.target_type === "project"
      || follow.target_type === "festival"
    ) {
      followedPageIds.add(follow.target_id)
    }
    if (follow.target_type === "artist" || follow.target_type === "consumer") followedUserIds.add(follow.target_id)
  }
  return { followedPageIds, followedUserIds }
}

export type FeedServices = {
  auth: typeof auth
  getEventAnnouncementPosts: typeof getEventAnnouncementPosts
  getEventFeedCandidates: typeof getEventFeedCandidates
  getEventsBatchResult: typeof getEventsBatchResult
  getFeedPosts: typeof getFeedPosts
  getFollowedTargets: typeof getFollowedTargets
  getOrganizerRefs: typeof getOrganizerRefs
  listEvents: typeof listEvents
  listEventUpdates: typeof listEventUpdates
  listNotifications: typeof listNotifications
}

const defaultFeedServices: FeedServices = {
  auth,
  getEventAnnouncementPosts,
  getEventFeedCandidates,
  getEventsBatchResult,
  getFeedPosts,
  getFollowedTargets,
  getOrganizerRefs,
  listEvents,
  listEventUpdates,
  listNotifications,
}

async function legacyCandidates(
  services: FeedServices,
  viewerCity: string | null,
  filter: FeedFilter,
) {
  const scopes = await Promise.all(
    feedEventScopes(viewerCity, filter).map((options) => services.listEvents(options)),
  )
  return [...new Map(scopes.flat().map((event) => [event.id, event])).values()]
}

/**
 * Unified chronological scene activity feed. The BFF owns assembly; services keep
 * ownership of their own read models (`social` posts, `events` events, `users` notifications/follows).
 */
export async function getFeed(filter: FeedFilter = "all"): Promise<FeedItem[]> {
  return getFeedWithServices(filter, defaultFeedServices)
}

export async function getFeedWithServices(
  filter: FeedFilter,
  services: FeedServices,
): Promise<FeedItem[]> {
  const session = await services.auth()
  const viewerCity = session?.onboarding_preferences?.city ?? null
  const includesEvents = feedIncludesEvents(filter)
  const [feedPosts, eventUpdates, notifications, follows] = await Promise.all([
    services.getFeedPosts(),
    includesEvents ? services.listEventUpdates({ limit: 100 }) : Promise.resolve([]),
    notificationCandidates(services.listNotifications),
    includesEvents ? services.getFollowedTargets() : Promise.resolve([]),
  ])
  const { followedPageIds, followedUserIds } = splitFollowTargets(follows)

  let candidateEvents: ThresholdEvent[] = []
  if (includesEvents) {
    const candidates = await services.getEventFeedCandidates({
      city: canonicalCity(viewerCity),
      followedPageIds: [...followedPageIds],
      followedCreatorUserIds: [...followedUserIds],
    })
    candidateEvents = candidates.supported
      ? candidates.items
      : await legacyCandidates(services, viewerCity, filter)
  }

  const announcements = includesEvents
    ? await services.getEventAnnouncementPosts(candidateEvents.map((event) => event.id))
    : {
        items: [],
        representedEventIds: [],
        representedEventSlugs: [],
        legacyRepresentedEventSlugs: [],
        supported: true,
      }
  const posts = [...new Map(
    [...feedPosts, ...announcements.items].map((post) => [post.id, post]),
  ).values()]
  const legacyRepresentedPosts = announcements.supported
    ? []
    : posts.filter((post) => post.systemOwned)
  const representedEventIds = new Set([
    ...announcements.representedEventIds,
    ...legacyRepresentedPosts.flatMap((post) => post.eventId ? [post.eventId] : []),
  ])
  const representedEventSlugs = new Set([
    ...announcements.representedEventSlugs,
    ...legacyRepresentedPosts.flatMap((post) => post.eventSlug ? [post.eventSlug] : []),
  ])
  const legacyRepresentedEventSlugs = new Set([
    ...announcements.legacyRepresentedEventSlugs,
    ...legacyRepresentedPosts.flatMap((post) => !post.eventId && post.eventSlug
      ? [post.eventSlug]
      : []),
  ])

  const missingSlugs = missingPostEventSlugs(posts, candidateEvents)
  const linkedEvents = await services.getEventsBatchResult(missingSlugs)
  const fallbackEvents = !linkedEvents.supported && missingSlugs.length > 0
    ? await legacyCandidates(services, viewerCity, "all")
    : []
  const events = mergeFeedEvents(
    mergeFeedEvents(candidateEvents, fallbackEvents),
    linkedEvents.items,
  )
  const organizerEventIds = new Set(
    posts.flatMap((post) => post.systemOwned && post.eventId ? [post.eventId] : []),
  )
  const legacyOrganizerEventSlugs = new Set(
    posts.flatMap((post) => post.systemOwned && !post.eventId && post.eventSlug
      ? [post.eventSlug.toLowerCase()]
      : []),
  )
  const organizers = await services.getOrganizerRefs(
    organizerPageIds(events.filter((event) =>
      organizerEventIds.has(event.id)
      || legacyOrganizerEventSlugs.has(event.slug.toLowerCase()),
    )),
  )
  return assembleFeed({
    posts: hydrateFeedPosts(posts, events, organizers),
    events,
    eventUpdates,
    notifications,
    followedPageIds,
    followedUserIds,
    representedEventIds,
    representedEventSlugs,
    legacyRepresentedEventSlugs,
    viewerCity,
    filter,
  })
}
