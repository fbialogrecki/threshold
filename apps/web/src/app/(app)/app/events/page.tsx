import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { EventCard } from "@/components/cards/event-card"
import { EmptyState } from "@/components/ui/empty-state"
import { listEventsResult } from "@/lib/api/events"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("eventsCatalog.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function AppEventsPage() {
  const [result, t] = await Promise.all([
    listEventsResult({ upcoming: true }),
    getTranslations("eventsCatalog"),
  ])

  // The nav already names this route, so the visible title is redundant; the
  // heading stays for screen readers navigating by landmark.
  return (
    <div className="flex flex-col gap-5">
      <h1 className="sr-only">{t("title")}</h1>

      {result.error ? (
        <EmptyState
          title={t("loadErrorTitle")}
          body={t("loadErrorBody")}
          eyebrow={t("errorEyebrow")}
          actionLabel={t("retry")}
          actionHref="/app/events"
        />
      ) : result.items.length === 0 ? (
        <EmptyState
          title={t("emptyTitle")}
          body={t("emptyBody")}
          eyebrow={t("emptyEyebrow")}
          actionLabel={t("emptyAction")}
          actionHref="/app/search"
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {result.items.map((event) => (
            <EventCard key={event.slug} event={event} />
          ))}
        </div>
      )}
    </div>
  )
}
