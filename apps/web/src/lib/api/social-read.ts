import "server-only"

import {
  socialCall,
  SocialServiceConfigurationError,
  trustedAuthorHeaders,
} from "@/lib/social/client"
import { isUnsupportedEndpoint } from "@/lib/api/rollout"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import type {
  Comment,
  EmojiReaction,
  Group,
  MentionRef,
  Post,
  ProfileRef,
  VoteKind,
} from "@/lib/types"

type SocialEmojiReaction = {
  emoji: string
  count: number
  viewer_reacted: boolean
}

export type SocialPost = {
  id: string
  author_user_id: string
  author_username: string
  author_display_name: string
  author_type: string
  group_id: string | null
  event_id?: string | null
  event_slug?: string | null
  body: string
  created_at: string
  edited_at?: string | null
  up_count: number
  down_count: number
  viewer_vote: string | null
  viewer_is_author?: boolean
  emoji_reactions: SocialEmojiReaction[]
  comment_count: number
  media_asset_ids?: string[]
  mentions?: SocialMention[]
}

type SocialMention = {
  mention_type: string
  target_handle: string
  target_id?: string | null
  display_name?: string | null
  target_url?: string | null
  start_index?: number | null
  end_index?: number | null
}

type SocialGroup = {
  id: string
  slug: string
  name: string
  city: string
  scene_tag: string | null
  official: boolean
}

type SocialComment = {
  id: string
  post_id: string
  parent_id: string | null
  author_user_id: string
  author_username: string
  author_display_name: string
  author_type: string
  body: string
  created_at: string
  edited_at?: string | null
  up_count: number
  down_count: number
  viewer_vote: string | null
  viewer_is_author?: boolean
  mentions?: SocialMention[]
}

/** social author_type is always "user"; surface artists/consumers under /u. */
function authorRef(post: { author_user_id: string; author_username: string; author_display_name: string; author_type: string }): ProfileRef {
  return {
    id: post.author_user_id,
    type: post.author_type === "artist" ? "artist" : "consumer",
    handle: post.author_username,
    displayName: post.author_display_name,
  }
}

function mapVote(value: string | null | undefined): VoteKind | null {
  return value === "up" || value === "down" ? value : null
}

function mapEmojiReactions(reactions: SocialEmojiReaction[] | undefined): EmojiReaction[] {
  if (!Array.isArray(reactions)) return []
  return reactions.map((reaction) => ({
    emoji: reaction.emoji,
    count: reaction.count,
    viewerReacted: Boolean(reaction.viewer_reacted),
  }))
}

function mapMentions(mentions: SocialMention[] | undefined): MentionRef[] {
  if (!Array.isArray(mentions)) return []
  return mentions.map((mention) => ({
    mentionType: mention.mention_type,
    targetHandle: mention.target_handle,
    targetId: mention.target_id ?? null,
    displayName: mention.display_name ?? null,
    targetUrl: mention.target_url ?? null,
    startIndex: mention.start_index ?? null,
    endIndex: mention.end_index ?? null,
  }))
}

export function mapPost(post: SocialPost): Post {
  return {
    id: post.id,
    author: authorRef(post),
    systemOwned: post.author_type === "system",
    createdAtIso: post.created_at,
    editedAtIso: post.edited_at ?? null,
    body: post.body,
    mentions: mapMentions(post.mentions),
    tags: [],
    commentCount: post.comment_count,
    upCount: post.up_count ?? 0,
    downCount: post.down_count ?? 0,
    viewerVote: mapVote(post.viewer_vote),
    viewerIsAuthor: post.author_type !== "system" && Boolean(post.viewer_is_author),
    emojiReactions: mapEmojiReactions(post.emoji_reactions),
    media: (post.media_asset_ids ?? []).map((assetId) => ({
      assetId,
      url: mediaDerivativeUrl(assetId, "post_1280"),
    })),
    eventId: post.event_id ?? null,
    eventSlug: post.event_slug ?? null,
  }
}

function mapSocialComment(comment: SocialComment): Comment {
  return {
    id: comment.id,
    postId: comment.post_id,
    parentId: comment.parent_id ?? null,
    author: authorRef(comment),
    createdAtIso: comment.created_at,
    editedAtIso: comment.edited_at ?? null,
    body: comment.body,
    mentions: mapMentions(comment.mentions),
    upCount: comment.up_count ?? 0,
    downCount: comment.down_count ?? 0,
    viewerVote: mapVote(comment.viewer_vote),
    viewerIsAuthor: Boolean(comment.viewer_is_author),
  }
}

function mapGroup(group: SocialGroup): Group {
  return {
    id: group.id,
    slug: group.slug,
    name: group.name,
    city: group.city,
    sceneTag: group.scene_tag ?? undefined,
    official: group.official,
  }
}

function isPostList(body: unknown): body is { items: SocialPost[] } {
  return typeof body === "object" && body !== null && Array.isArray((body as { items?: unknown }).items)
}

/**
 * Viewer headers for reads: present when a session exists so the social
 * service can compute viewer_* fields; null keeps reads anonymous.
 */
async function viewerHeaders(): Promise<HeadersInit | undefined> {
  return (await trustedAuthorHeaders()) ?? undefined
}

/** Live following feed. Empty for anonymous viewers or when social is unconfigured. */
export async function getFeedPosts(): Promise<Post[]> {
  try {
    const userHeaders = await trustedAuthorHeaders()
    if (!userHeaders) return []
    const query = new URLSearchParams({ filter: "posts" })
    const { status, body } = await socialCall("/v1/feed", { query, userHeaders })
    if (status !== 200 || !isPostList(body)) return []
    return body.items.map(mapPost)
  } catch (error) {
    if (error instanceof SocialServiceConfigurationError) return []
    throw error
  }
}

export async function getEventAnnouncementPosts(
  eventIds: string[],
  call: typeof socialCall = socialCall,
  getUserHeaders: typeof trustedAuthorHeaders = trustedAuthorHeaders,
): Promise<{
  items: Post[]
  representedEventIds: string[]
  representedEventSlugs: string[]
  legacyRepresentedEventSlugs: string[]
  supported: boolean
}> {
  const ids = [...new Set(eventIds.filter(Boolean))]
  if (ids.length === 0) {
    return {
      items: [],
      representedEventIds: [],
      representedEventSlugs: [],
      legacyRepresentedEventSlugs: [],
      supported: true,
    }
  }
  const userHeaders = await getUserHeaders()
  const batches = Array.from(
    { length: Math.ceil(ids.length / 100) },
    (_, index) => ids.slice(index * 100, (index + 1) * 100),
  )
  const responses = await Promise.all(batches.map((batch) =>
    call("/internal/v1/event-announcements/batch", {
      method: "POST",
      json: { event_ids: batch, event_slugs: [] },
      userHeaders: userHeaders ?? undefined,
    }),
  ))
  if (responses.some(({ status }) => isUnsupportedEndpoint(status))) {
    return {
      items: [],
      representedEventIds: [],
      representedEventSlugs: [],
      legacyRepresentedEventSlugs: [],
      supported: false,
    }
  }
  const posts: Post[] = []
  const representedEventIds = new Set<string>()
  const representedEventSlugs = new Set<string>()
  const legacyRepresentedEventSlugs = new Set<string>()
  for (const { status, body } of responses) {
    if (status !== 200) {
      throw new Error(`social announcement batch failed with status ${status}`)
    }
    if (Array.isArray(body)) {
      const legacyPosts = (body as SocialPost[]).map(mapPost)
      posts.push(...legacyPosts)
      for (const post of legacyPosts) {
        if (!post.systemOwned) continue
        if (post.eventId) representedEventIds.add(post.eventId)
        if (post.eventSlug) {
          representedEventSlugs.add(post.eventSlug)
          if (!post.eventId) legacyRepresentedEventSlugs.add(post.eventSlug)
        }
      }
      continue
    }
    if (typeof body !== "object" || body === null) {
      throw new Error("social announcement batch returned an invalid response")
    }
    const envelope = body as {
      posts?: unknown
      represented_event_ids?: unknown
      represented_event_slugs?: unknown
    }
    if (
      !Array.isArray(envelope.posts)
      || !Array.isArray(envelope.represented_event_ids)
      || !Array.isArray(envelope.represented_event_slugs)
    ) {
      throw new Error("social announcement batch returned an invalid response")
    }
    posts.push(...(envelope.posts as SocialPost[]).map(mapPost))
    for (const id of envelope.represented_event_ids) {
      if (typeof id === "string") representedEventIds.add(id)
    }
    for (const slug of envelope.represented_event_slugs) {
      if (typeof slug === "string") representedEventSlugs.add(slug)
    }
  }
  return {
    items: [...new Map(posts.map((post) => [post.id, post])).values()],
    representedEventIds: [...representedEventIds],
    representedEventSlugs: [...representedEventSlugs],
    legacyRepresentedEventSlugs: [...legacyRepresentedEventSlugs],
    supported: true,
  }
}


export async function getGroups(): Promise<Group[]> {
  return (await getGroupsResult()).items
}

export async function getGroupsResult(): Promise<{ items: Group[]; error: boolean }> {
  try {
    const { status, body } = await socialCall("/v1/groups")
    return status === 200 && Array.isArray(body)
      ? { items: (body as SocialGroup[]).map(mapGroup), error: false }
      : { items: [], error: true }
  } catch {
    return { items: [], error: true }
  }
}

export async function getGroup(slug: string): Promise<Group | null> {
  const result = await getGroupResult(slug)
  return result.status === "ok" ? result.group : null
}

export async function getGroupResult(
  slug: string,
): Promise<
  | { status: "ok"; group: Group }
  | { status: "notFound" }
  | { status: "error" }
> {
  try {
    const { status, body } = await socialCall(`/v1/groups/${encodeURIComponent(slug)}`)
    if (status === 404) return { status: "notFound" }
    if (status !== 200 || typeof body !== "object" || body === null) return { status: "error" }
    return { status: "ok", group: mapGroup(body as SocialGroup) }
  } catch {
    return { status: "error" }
  }
}

export async function getGroupPosts(slug: string): Promise<Post[]> {
  return (await getGroupPostsResult(slug)).items
}

export async function getGroupPostsResult(
  slug: string,
): Promise<{ items: Post[]; error: boolean }> {
  try {
    const userHeaders = await viewerHeaders()
    const { status, body } = await socialCall(`/v1/groups/${encodeURIComponent(slug)}/posts`, {
      userHeaders,
    })
    return status === 200 && isPostList(body)
      ? { items: body.items.map(mapPost), error: false }
      : { items: [], error: true }
  } catch {
    return { items: [], error: true }
  }
}

/** Slugs of groups the current user has joined (empty when anonymous). */
export async function getMyGroupSlugs(): Promise<string[]> {
  return (await getMyGroupSlugsResult()).items
}

export async function getMyGroupSlugsResult(): Promise<{ items: string[]; error: boolean }> {
  try {
    const userHeaders = await trustedAuthorHeaders()
    if (!userHeaders) return { items: [], error: true }
    const { status, body } = await socialCall("/v1/me/groups", { userHeaders })
    return status === 200 && Array.isArray(body)
      ? { items: (body as SocialGroup[]).map((group) => group.slug), error: false }
      : { items: [], error: true }
  } catch {
    return { items: [], error: true }
  }
}

export async function searchGroups(query: string): Promise<Group[]> {
  return (await searchGroupsResult(query)).items
}

export async function searchGroupsResult(
  query: string,
): Promise<{ items: Group[]; error: boolean }> {
  const q = query.trim()
  if (!q) return { items: [], error: false }
  try {
    const { status, body } = await socialCall("/v1/search/groups", {
      query: new URLSearchParams({ q }),
    })
    return status === 200 && Array.isArray(body)
      ? { items: (body as SocialGroup[]).map(mapGroup), error: false }
      : { items: [], error: true }
  } catch {
    return { items: [], error: true }
  }
}

export async function getPost(id: string): Promise<Post | null> {
  try {
    const userHeaders = await viewerHeaders()
    const { status, body } = await socialCall(`/v1/posts/${encodeURIComponent(id)}`, {
      userHeaders,
    })
    if (status !== 200 || typeof body !== "object" || body === null) return null
    return mapPost(body as SocialPost)
  } catch (error) {
    if (error instanceof SocialServiceConfigurationError) return null
    throw error
  }
}

export async function getComments(postId: string): Promise<Comment[]> {
  try {
    const userHeaders = await viewerHeaders()
    const { status, body } = await socialCall(
      `/v1/posts/${encodeURIComponent(postId)}/comments`,
      { userHeaders },
    )
    if (status !== 200 || !Array.isArray(body)) return []
    return (body as SocialComment[]).map(mapSocialComment)
  } catch (error) {
    if (error instanceof SocialServiceConfigurationError) return []
    throw error
  }
}
