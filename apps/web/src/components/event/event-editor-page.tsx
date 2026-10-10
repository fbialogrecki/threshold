import { ArrowLeft } from "@phosphor-icons/react/ssr"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"
import { EventForm } from "./event-form"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { getSessionState } from "@/lib/auth/session"
import { listManagedPages } from "@/lib/auth/product-auth"
import { getEvent, getEventViewerContext } from "@/lib/api/events"
import { loadEventEditor } from "@/lib/events/editor-access"
import { loginHref } from "@/lib/auth/routing"

export async function EventEditorPage({ slug }: { slug?: string }) {
  const path = slug ? `/app/events/${encodeURIComponent(slug)}/edit` : "/app/events/new"
  const access = await loadEventEditor(slug, { getSessionState, listManagedPages, getEvent, getEventViewerContext })
  if (access.status === "unauthenticated") redirect(loginHref(path))
  if (access.status === "missing") notFound()
  const t = await getTranslations("eventEditor")
  const backHref = slug ? `/events/${encodeURIComponent(slug)}` : "/app/events"
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <Link
        href={backHref}
        className="inline-flex w-fit items-center gap-2 text-sm text-muted transition-colors hover:text-raw-white"
      >
        <ArrowLeft size={14} weight="bold" aria-hidden />
        {t(slug ? "backToEvent" : "backToEvents")}
      </Link>
      <PageHeader title={t(slug ? "edit" : "create")} />
      {access.status === "ready" ? (
        <EventForm pages={access.pages} event={access.event} />
      ) : (
        <EmptyState
          tone="error"
          title={t(slug ? "edit" : "create")}
          body={t(access.status === "unavailable" ? "unavailable" : "forbidden")}
          actionLabel={t(access.status === "unavailable" ? "retry" : "managePages")}
          actionHref={access.status === "unavailable" ? path : "/app/pages"}
        />
      )}
    </div>
  )
}
