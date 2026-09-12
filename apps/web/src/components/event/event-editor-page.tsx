import Link from "next/link"
import { notFound, redirect } from "next/navigation"
import { getTranslations } from "next-intl/server"
import { EventForm } from "./event-form"
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
  return <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
    <h1 className="border-b border-border-gray pb-4 font-display text-3xl">{t(slug ? "edit" : "create")}</h1>
    {access.status === "ready" ? <EventForm pages={access.pages} event={access.event} /> : <>
      <p role="alert">{t(access.status === "unavailable" ? "unavailable" : "forbidden")}</p>
      <Link className="font-mono text-xs text-acid" href={access.status === "unavailable" ? path : "/app/pages"}>{t(access.status === "unavailable" ? "retry" : "managePages")}</Link>
    </>}
  </div>
}
