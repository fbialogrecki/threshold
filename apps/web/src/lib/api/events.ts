import "server-only"

import {
  eventsCall,
  EventsServiceConfigurationError,
} from "@/lib/events/client"
import { isUnsupportedEndpoint } from "@/lib/api/rollout"
import { buildEventListQuery, type EventListOptions } from "@/lib/events/query"
import type {
  DoorStaffAssignment,
  EventUpdate,
  EventViewerContext,
  LocationMode,
  ManagerGuestlistEntry,
  ThresholdEvent,
} from "@/lib/types"

type EventResponse = Omit<ThresholdEvent, "location_mode"> & {
  location_mode: LocationMode | "public"
}

type EventUpdateResponse = {
  id: string
  event_id: string
  event_slug: string
  event_title: string
  author_user_id: string
  author_page_id: string
  body: string
  kind: string
  created_at: string
  updated_at: string
}

function isEvent(value: unknown): value is EventResponse {
  return typeof value === "object" && value !== null && "slug" in value && "title" in value
}

function isEventList(body: unknown): body is { items: EventResponse[] } {
  return typeof body === "object" && body !== null && Array.isArray((body as { items?: unknown }).items)
}

function isEventUpdateList(body: unknown): body is { items: EventUpdateResponse[] } {
  return typeof body === "object" && body !== null && Array.isArray((body as { items?: unknown }).items)
}

function isViewerContext(body: unknown): body is EventViewerContext {
  if (typeof body !== "object" || body === null) return false
  const value = body as Partial<EventViewerContext>
  return typeof value.event_slug === "string"
    && typeof value.can_mint_qr === "boolean"
    && typeof value.can_manage_guestlist === "boolean"
    && typeof value.can_set_dj_quota === "boolean"
    && typeof value.can_check_in === "boolean"
    && typeof value.can_post_update === "boolean"
    && Array.isArray(value.viewer_lineup_artists)
    && Array.isArray(value.quota_summaries)
}

function isManagerGuestlist(body: unknown): body is ManagerGuestlistEntry[] {
  return Array.isArray(body) && body.every((entry) =>
    typeof entry === "object"
    && entry !== null
    && typeof (entry as Partial<ManagerGuestlistEntry>).guest_user_id === "string"
    && typeof (entry as Partial<ManagerGuestlistEntry>).display_name === "string",
  )
}

function isDoorStaffList(body: unknown): body is DoorStaffAssignment[] {
  return Array.isArray(body) && body.every((entry) =>
    typeof entry === "object"
    && entry !== null
    && typeof (entry as Partial<DoorStaffAssignment>).id === "string"
    && typeof (entry as Partial<DoorStaffAssignment>).assigned_at === "string",
  )
}

function normalizeEvent(event: EventResponse): ThresholdEvent {
  return {
    ...event,
    location_mode: event.location_mode === "public" ? "public_location" : event.location_mode,
  }
}

function normalizeEventUpdate(update: EventUpdateResponse): EventUpdate {
  return {
    id: update.id,
    eventId: update.event_id,
    event: { slug: update.event_slug, title: update.event_title },
    authorUserId: update.author_user_id,
    authorPageId: update.author_page_id,
    body: update.body,
    kind: update.kind,
    createdAtIso: update.created_at,
    updatedAtIso: update.updated_at,
  }
}

export async function listEvents(
  options: EventListOptions = {},
): Promise<ThresholdEvent[]> {
  return (await listEventsResult(options)).items
}

export async function listEventsResult(
  options: EventListOptions = {},
): Promise<{ items: ThresholdEvent[]; error: boolean }> {
  try {
    const { status, body } = await eventsCall("/v1/events", {
      query: buildEventListQuery(options),
      includeViewer: true,
    })
    return status === 200 && isEventList(body)
      ? { items: body.items.map(normalizeEvent), error: false }
      : { items: [], error: true }
  } catch {
    return { items: [], error: true }
  }
}

export async function searchEvents(query: string): Promise<ThresholdEvent[]> {
  return (await searchEventsResult(query)).items
}

export async function searchEventsResult(
  query: string,
): Promise<{ items: ThresholdEvent[]; error: boolean }> {
  const q = query.trim().replace(/^#/, "")
  if (!q) return { items: [], error: false }
  try {
    const { status, body } = await eventsCall("/v1/events", {
      query: new URLSearchParams({ q, limit: "10" }),
      includeViewer: false,
    })
    return status === 200 && isEventList(body)
      ? { items: body.items.map(normalizeEvent), error: false }
      : { items: [], error: true }
  } catch {
    return { items: [], error: true }
  }
}

export async function getEvent(slug: string): Promise<ThresholdEvent | null> {
  try {
    const { status, body } = await eventsCall(`/v1/events/${encodeURIComponent(slug)}`, {
      includeViewer: true,
    })
    if (status !== 200 || !isEvent(body)) return null
    return normalizeEvent(body)
  } catch (error) {
    if (error instanceof EventsServiceConfigurationError) return null
    throw error
  }
}

export async function getEventViewerContext(slug: string): Promise<EventViewerContext | null> {
  try {
    const { status, body } = await eventsCall(
      `/v1/events/${encodeURIComponent(slug)}/viewer-context`,
      { includeViewer: true, requireViewer: true },
    )
    return status === 200 && isViewerContext(body) ? body : null
  } catch (error) {
    if (error instanceof EventsServiceConfigurationError) return null
    throw error
  }
}

export async function getManagerGuestlist(slug: string): Promise<ManagerGuestlistEntry[]> {
  try {
    const { status, body } = await eventsCall(
      `/v1/events/${encodeURIComponent(slug)}/guestlist`,
      { includeViewer: true, requireViewer: true },
    )
    return status === 200 && isManagerGuestlist(body) ? body : []
  } catch (error) {
    if (error instanceof EventsServiceConfigurationError) return []
    throw error
  }
}

export async function getDoorStaff(slug: string): Promise<DoorStaffAssignment[]> {
  try {
    const { status, body } = await eventsCall(
      `/v1/events/${encodeURIComponent(slug)}/door-staff`,
      { includeViewer: true, requireViewer: true },
    )
    return status === 200 && isDoorStaffList(body)
      ? body.map(({ id, username, display_name, assigned_at }) => ({
        id,
        username,
        display_name,
        assigned_at,
      }))
      : []
  } catch (error) {
    if (error instanceof EventsServiceConfigurationError) return []
    throw error
  }
}

export type EventFeedCandidateInput = {
  city: string | null
  followedPageIds: string[]
  followedCreatorUserIds: string[]
  limit?: number
}

export async function getEventFeedCandidates(
  input: EventFeedCandidateInput,
  call: typeof eventsCall = eventsCall,
): Promise<{ items: ThresholdEvent[]; supported: boolean }> {
  const pageIds = [...new Set(input.followedPageIds)]
  const creatorIds = [...new Set(input.followedCreatorUserIds)]
  const request = (
    city: string | null,
    followedPageIds: string[],
    followedCreatorUserIds: string[],
    includeViewer: boolean,
  ) => call("/internal/v1/events/feed-candidates", {
    method: "POST",
    json: {
      city,
      followed_page_ids: followedPageIds,
      followed_creator_user_ids: followedCreatorUserIds,
      limit: input.limit ?? 100,
    },
    includeViewer,
    requireViewer: false,
  })
  const base = await request(input.city, [], [], true)
  if (isUnsupportedEndpoint(base.status)) return { items: [], supported: false }
  if (base.status !== 200 || !Array.isArray(base.body)) {
    throw new Error(`events feed candidates failed with status ${base.status}`)
  }
  const chunks = (ids: string[]) => Array.from(
    { length: Math.ceil(ids.length / 100) },
    (_, index) => ids.slice(index * 100, (index + 1) * 100),
  )
  const scoped = await Promise.all([
    ...chunks(pageIds).map((ids) => request(null, ids, [], false)),
    ...chunks(creatorIds).map((ids) => request(null, [], ids, false)),
  ])
  if (scoped.some(({ status }) => isUnsupportedEndpoint(status))) {
    return { items: [], supported: false }
  }
  const responses = [base, ...scoped]
  const events = responses.flatMap(({ status, body }) => {
    if (status !== 200 || !Array.isArray(body)) {
      throw new Error(`events feed candidates failed with status ${status}`)
    }
    return body.filter(isEvent).map(normalizeEvent)
  })
  const deduped = [...new Map(events.map((event) => [event.id, event])).values()]
  deduped.sort((a, b) => {
    const aEpoch = Date.parse(a.created_at)
    const bEpoch = Date.parse(b.created_at)
    const safeA = Number.isNaN(aEpoch) ? Number.NEGATIVE_INFINITY : aEpoch
    const safeB = Number.isNaN(bEpoch) ? Number.NEGATIVE_INFINITY : bEpoch
    if (safeA !== safeB) return safeB > safeA ? 1 : -1
    return a.id.localeCompare(b.id)
  })
  return { items: deduped, supported: true }
}

export async function getEventsBatchResult(
  slugs: string[],
): Promise<{ items: ThresholdEvent[]; supported: boolean }> {
  const unique = [...new Set(slugs.map((slug) => slug.trim().toLowerCase()).filter(Boolean))]
  if (unique.length === 0) return { items: [], supported: true }
  const batches = Array.from(
    { length: Math.ceil(unique.length / 100) },
    (_, index) => unique.slice(index * 100, (index + 1) * 100),
  )
  const responses = await Promise.all(batches.map((batch) =>
    eventsCall("/internal/v1/events/batch", {
      method: "POST",
      json: { slugs: batch },
      includeViewer: false,
      requireViewer: false,
    }),
  ))
  if (responses.some(({ status }) => isUnsupportedEndpoint(status))) {
    return { items: [], supported: false }
  }
  const items = responses.flatMap(({ status, body }) => {
    if (status !== 200) throw new Error(`events batch failed with status ${status}`)
    return Array.isArray(body) ? body.filter(isEvent).map(normalizeEvent) : []
  })
  return { items, supported: true }
}

export async function getEventsBatch(slugs: string[]): Promise<ThresholdEvent[]> {
  return (await getEventsBatchResult(slugs)).items
}

export async function listEventUpdates(
  options: string | { slug?: string; limit?: number } = {},
): Promise<EventUpdate[]> {
  try {
    const { slug, limit } = typeof options === "string" ? { slug: options, limit: 50 } : options
    const path = slug
      ? `/v1/events/${encodeURIComponent(slug)}/updates`
      : "/v1/event-updates"
    const { status, body } = await eventsCall(path, {
      query: new URLSearchParams({ limit: String(limit ?? 50) }),
      includeViewer: false,
    })
    if (status !== 200 || !isEventUpdateList(body)) return []
    return body.items.map(normalizeEventUpdate)
  } catch (error) {
    if (error instanceof EventsServiceConfigurationError) return []
    throw error
  }
}
