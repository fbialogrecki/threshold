import type { ManagedPage } from "@/components/pages/page-management-panel"
import type { ThresholdEvent } from "@/lib/types"

type EditorServices = {
  getSessionState: () => Promise<{ status: string }>
  listManagedPages: () => Promise<{ status: number; body: unknown }>
  getEventViewerContext: (slug: string) => Promise<{ event_slug: string; can_post_update: boolean } | null>
  getEvent: (slug: string) => Promise<ThresholdEvent | null>
}
export type EditorAccess = { status: "ready"; pages: ManagedPage[]; event?: ThresholdEvent }
  | { status: "unauthenticated" | "forbidden" | "unavailable" | "missing" }

export function managedEventPages(body: unknown): ManagedPage[] {
  if (!Array.isArray(body)) return []
  return body.filter((p): p is ManagedPage => p && typeof p.id === "string"
    && typeof p.display_name === "string" && ["owner", "admin", "editor"].includes(p.role))
}

export async function loadEventEditor(slug: string | undefined, services: EditorServices): Promise<EditorAccess> {
  try {
    const session = await services.getSessionState()
    if (session.status === "unavailable") return { status: "unavailable" }
    if (session.status !== "authenticated") return { status: "unauthenticated" }
    const result = await services.listManagedPages()
    if (result.status !== 200) return { status: "unavailable" }
    const pages = managedEventPages(result.body)
    if (!pages.length) return { status: "forbidden" }
    if (!slug) return { status: "ready", pages }
    const context = await services.getEventViewerContext(slug)
    if (!context?.can_post_update || context.event_slug !== slug) return { status: "forbidden" }
    const event = await services.getEvent(slug)
    if (!event) return { status: "missing" }
    if (!pages.some(p => p.id === event.page_id)) return { status: "forbidden" }
    return { status: "ready", pages, event }
  } catch {
    return { status: "unavailable" }
  }
}
