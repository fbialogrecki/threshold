import Link from "next/link"
import { getSessionState } from "@/lib/auth/session"
import { listManagedPages } from "@/lib/auth/product-auth"
import { managedEventPages } from "@/lib/events/editor-access"
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

  const session = await getSessionState()
  const pages = session.status === "authenticated" ? await listManagedPages().catch(() => null) : null
  const canCreate = pages?.status === 200 && managedEventPages(pages.body).length > 0
  const editor = await getTranslations("eventEditor")

  // The nav already names this route, so the visible title is redundant; the
  // heading stays for screen readers navigating by landmark.
  return (
    <div className="flex flex-col gap-5">
      <h1 className="sr-only">{t("title")}</h1>
      {canCreate ? <Link href="/app/events/new" className="self-start border border-border-gray px-3 py-2 font-mono text-xs uppercase text-acid">{editor("create")}</Link> : null}

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
