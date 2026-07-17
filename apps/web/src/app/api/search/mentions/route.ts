import { searchWithStatus } from "@/lib/api/search"
import { activeMentionTrigger, suggestionMatchesMarker } from "@/lib/mentions/autocomplete"

export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  const url = new URL(request.url)
  const q = (url.searchParams.get("q") ?? "").trim().slice(0, 80)
  const trigger = activeMentionTrigger(q, q.length)
  if (!trigger) return Response.json([])

  const type = trigger.marker === "#" ? "event" : undefined
  const result = await searchWithStatus(q, type)
  if (result.error) return Response.json({ error: "search unavailable" }, { status: 503 })
  const results = result.items.filter((item) =>
    suggestionMatchesMarker(item, trigger.marker),
  )

  return Response.json(results.slice(0, 8))
}
