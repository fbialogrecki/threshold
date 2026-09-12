import { eventPayload, type EventDraft } from "./editor"
import type { ThresholdEvent } from "@/lib/types"

export class EventSaveError extends Error {
  constructor(public status: number) { super(`event save failed: ${status}`) }
}

export async function saveEvent(draft: EventDraft, original: ThresholdEvent | undefined, poster: File | null, request: (input: string, init?: RequestInit) => Promise<Response> = fetch): Promise<string> {
  const payload = eventPayload(draft, original)
  if (poster) {
    if (poster.size > 10_000_000) throw new EventSaveError(413)
    const data = new FormData()
    data.set("context", "event_poster")
    data.set("file", poster)
    const upload = await request("/api/media/assets", { method: "POST", body: data })
    if (!upload.ok) throw new EventSaveError(upload.status)
    const asset = await upload.json()
    if (typeof asset?.id !== "string") throw new EventSaveError(502)
    payload.poster_media_asset_id = asset.id
  }
  const response = await request(original ? `/api/events/${encodeURIComponent(original.slug)}` : "/api/events", {
    method: original ? "PATCH" : "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload),
  })
  if (!response.ok) throw new EventSaveError(response.status)
  const saved = await response.json()
  if (typeof saved?.slug !== "string" || !/^[a-z0-9-]{3,160}$/.test(saved.slug)) throw new EventSaveError(502)
  return `/events/${saved.slug}`
}
