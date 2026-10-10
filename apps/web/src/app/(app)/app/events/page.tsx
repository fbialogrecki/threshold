import { CalendarPlus } from "@phosphor-icons/react/ssr"
import { getSessionState } from "@/lib/auth/session"
import { listManagedPages } from "@/lib/auth/product-auth"
import { managedEventPages } from "@/lib/events/editor-access"
import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { EventCard } from "@/components/cards/event-card"
import { ButtonLink } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
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

  const session = await getSessionState()
  const pages = session.status === "authenticated" ? await listManagedPages().catch(() => null) : null
  const canCreate = pages?.status === 200 && managedEventPages(pages.body).length > 0
  const editor = await getTranslations("eventEditor")

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        actions={canCreate ? (
          <ButtonLink href="/app/events/new" variant="primary" size="sm">
            <CalendarPlus size={18} weight="bold" aria-hidden />
            {editor("create")}
          </ButtonLink>
        ) : null}
      />

      {result.error ? (
        <EmptyState
          tone="error"
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
        // Upcoming events in the order the service returns them: chronological.
        <ul className="grid gap-4 sm:grid-cols-2">
          {result.items.map((event) => (
            <li key={event.slug} className="min-w-0">
              <EventCard event={event} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
