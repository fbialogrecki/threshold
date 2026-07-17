/**
 * Threshold domain contracts (frontend view).
 * These mirror product domain rules and libs/proto so backend response
 * mapping stays explicit at the UI boundary.
 */

import type { PageType } from "@/lib/page-types"

type ProfileType = "artist" | "consumer" | PageType

export type ProfileRef = {
  id: string
  type: ProfileType
  /** username for artists/consumers, slug for pages */
  handle: string
  displayName: string
  avatarUrl?: string
  href?: string
}

type EventRef = {
  slug: string
  title: string
}

export type LocationMode = "public_location" | "tba" | "secret_location"

export type EventLineupItem =
  | string
  | { artist_profile_id?: string; artist_handle?: string; display_name?: string; target_url?: string; name: string }

/**
 * Access flow state for secret-location events.
 * "none" means the event has no access gate.
 */
export type AccessState =
  | "none"
  | "locked"
  | "pending"
  | "approved"
  | "rejected"

export type ThresholdEvent = {
  id: string
  slug: string
  title: string
  description: string | null
  starts_at: string
  city: string | null
  location_mode: LocationMode
  venue_name: string | null
  address: string | null
  genres: string[]
  lineup: EventLineupItem[]
  page_id: string | null
  poster_media_asset_id: string | null
  created_by_user_id: string | null
  boost_count: number
  follower_count: number
  is_following: boolean
  is_boosting: boolean
  created_at: string
  updated_at: string
}

export type GuestQuota = {
  id: string
  event_id: string
  event_slug: string
  artist_profile_id: string
  quota: number
  used: number
  remaining: number
}

export type EventGuestAccess = {
  event_id: string
  event_slug: string
  user_id: string
  status: "active" | "removed"
  can_check_in: boolean
  checked_in_at: string | null
}

export type EventViewerContext = {
  event_id: string
  event_slug: string
  active_guest_access: EventGuestAccess | null
  can_mint_qr: boolean
  can_manage_guestlist: boolean
  can_set_dj_quota: boolean
  can_check_in: boolean
  can_post_update: boolean
  viewer_lineup_artists: {
    artist_profile_id: string
    quota: GuestQuota | null
  }[]
  quota_summaries: GuestQuota[]
}

export type ManagerGuestlistEntry = {
  id: string
  guest_user_id: string
  username: string | null
  display_name: string
  source: "organizer" | "dj"
  status: "active" | "removed"
  checked_in_at: string | null
}

export type DoorStaffAssignment = {
  id: string
  username: string | null
  display_name: string | null
  assigned_at: string
}

export type VoteKind = "up" | "down"

/** Aggregated emoji reaction on a post, with the viewer's own state. */
export type EmojiReaction = {
  emoji: string
  count: number
  viewerReacted: boolean
}

type MediaAttachment = {
  assetId: string
  url: string
}

export type MentionRef = {
  mentionType: "user" | "artist" | "page" | "event" | string
  targetHandle: string
  targetId: string | null
  displayName: string | null
  targetUrl: string | null
  startIndex: number | null
  endIndex: number | null
}

export type Post = {
  id: string
  author: ProfileRef
  systemOwned: boolean
  createdAtIso: string
  /** set when the author edited the post */
  editedAtIso: string | null
  body: string
  mentions: MentionRef[]
  tags: string[]
  commentCount: number
  upCount: number
  downCount: number
  /** the viewer's current vote, null when not voted or anonymous */
  viewerVote: VoteKind | null
  /** true when the viewer authored this post (enables edit/delete) */
  viewerIsAuthor: boolean
  emojiReactions: EmojiReaction[]
  media: MediaAttachment[]
  eventId: string | null
  eventSlug: string | null
  linkedEvent?: ThresholdEvent
}

/** A comment on a post; replies carry parentId (up to two levels of nesting). */
export type Comment = {
  id: string
  postId: string
  parentId: string | null
  author: ProfileRef
  createdAtIso: string
  editedAtIso: string | null
  body: string
  mentions: MentionRef[]
  upCount: number
  downCount: number
  viewerVote: VoteKind | null
  viewerIsAuthor: boolean
}

export type AccessUpdate = {
  id: string
  createdAtIso: string
  event: EventRef
  state: AccessState
  note: string
}

export type EventUpdate = {
  id: string
  eventId: string
  event: EventRef
  authorUserId: string
  authorPageId: string
  body: string
  kind: "update" | string
  createdAtIso: string
  updatedAtIso: string
}

type FeedMetadata = {
  publishedAtIso: string
  source: "social" | "events" | "notifications" | "future"
  reason: string
}

export type FeedItem =
  | { kind: "post"; post: Post; feed: FeedMetadata }
  | { kind: "event"; event: ThresholdEvent; feed: FeedMetadata }
  | { kind: "access_update"; update: AccessUpdate; feed: FeedMetadata }
  | { kind: "event_update"; update: EventUpdate; feed: FeedMetadata }
  | { kind: "residency_update"; feed: FeedMetadata }
  | { kind: "lineup_update"; feed: FeedMetadata }
  | { kind: "guestlist_update"; feed: FeedMetadata }

/** Unified scene activity feed filters. Future kinds stay typed but unsourced until their slices land. */
export type FeedFilter = "all" | "posts" | "events" | "access"

/** A scene group (live, from the social service). */
export type Group = {
  id: string
  slug: string
  name: string
  city: string
  sceneTag?: string
  official: boolean
}

type ResidencyState = "pending" | "confirmed" | "ended"

export type Residency = {
  pageHandle: string
  pageName: string
  state: ResidencyState
}

export type ExternalLink = {
  label: string
  url: string
}

/** A follow relationship the current user has, from `users /v1/me/follows`. */
export type FollowTarget = {
  target_type: "artist" | "consumer" | "page" | PageType
  target_id?: string
  target_handle: string
  display_name: string
}

/** Right rail: where do I have access */
export type AccessSummary = {
  event: EventRef
  city: string
  dateText: string
  locationMode: LocationMode
  state: AccessState
}

/** Right rail: what is on tonight */
export type TonightItem = {
  event: EventRef
  locationMode: LocationMode
  venueText: string
}

export type SearchResultType =
  | "artist"
  | "consumer"
  | PageType
  | "group"
  | "event"
  | "unknown"

export type SearchResult = {
  type: SearchResultType
  title: string
  subtitle: string
  href: string
  /** username, page slug, group slug or event slug used for autocomplete insertion. */
  handle: string
}

export type SearchResultGroup = {
  id: "profiles" | "pages" | "groups" | "events"
  items: SearchResult[]
}
