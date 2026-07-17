import { mediaDerivativeUrl } from "@/lib/media/urls"
import { pageType } from "@/lib/page-types"
import type { Post, ThresholdEvent } from "@/lib/types"

export type OrganizerRef = {
  id: string
  slug: string
  display_name: string
  page_type: string | null
  avatar_media_asset_id: string | null
  target_url: string
}

export function organizerPageIds(events: ThresholdEvent[]): string[] {
  return [...new Set(events.flatMap((event) => event.page_id ? [event.page_id] : []))]
}

export function missingPostEventSlugs(posts: Post[], events: ThresholdEvent[]): string[] {
  const availableIds = new Set(events.map((event) => event.id))
  const availableSlugs = new Set(events.map((event) => event.slug.toLowerCase()))
  return [...new Set(posts.flatMap((post) => {
    const slug = post.eventSlug?.toLowerCase()
    if (!slug) return []
    if (post.eventId) return availableIds.has(post.eventId) ? [] : [slug]
    return availableSlugs.has(slug) ? [] : [slug]
  }))]
}

export function mergeFeedEvents(
  scopedEvents: ThresholdEvent[],
  linkedEvents: ThresholdEvent[],
): ThresholdEvent[] {
  return [...new Map([...scopedEvents, ...linkedEvents].map((event) => [event.id, event])).values()]
}

export function hydrateFeedPosts(
  posts: Post[],
  events: ThresholdEvent[],
  organizers: OrganizerRef[],
): Post[] {
  const eventsById = new Map(events.map((event) => [event.id, event]))
  const eventsBySlug = new Map(events.map((event) => [event.slug.toLowerCase(), event]))
  const organizersById = new Map(organizers.map((organizer) => [organizer.id, organizer]))

  return posts.map((post) => {
    const linkedEvent = post.eventId
      ? eventsById.get(post.eventId)
      : post.eventSlug
        ? eventsBySlug.get(post.eventSlug.toLowerCase())
        : undefined
    const organizer = linkedEvent?.page_id
      ? organizersById.get(linkedEvent.page_id)
      : undefined
    if (!linkedEvent) return post
    if (!post.systemOwned || !organizer) return { ...post, linkedEvent }
    return {
      ...post,
      linkedEvent,
      author: {
        id: organizer.id,
        type: pageType(organizer.page_type),
        handle: organizer.slug,
        displayName: organizer.display_name,
        avatarUrl: organizer.avatar_media_asset_id
          ? mediaDerivativeUrl(organizer.avatar_media_asset_id, "avatar_256")
          : undefined,
        href: organizer.target_url,
      },
      viewerIsAuthor: false,
    }
  })
}
