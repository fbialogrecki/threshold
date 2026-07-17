"use client"

import { ArrowSquareOut, Check, Checks } from "@phosphor-icons/react"
import { useLocale, useTranslations } from "next-intl"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import { MonoLabel } from "@/components/ui/mono-label"
import { StatusBadge } from "@/components/ui/status-badge"
import { cn } from "@/lib/cn"
import { formatRelative } from "@/lib/format"
import {
  notificationHref,
  notificationIsUnread,
  notificationMessage,
  notificationRole,
  notificationTypeKey,
  updatePendingIds,
} from "@/lib/notifications"
import type { NotificationItem } from "@/lib/auth/product-auth"

export function NotificationInbox({
  initialItems,
}: {
  initialItems: NotificationItem[]
}) {
  const locale = useLocale()
  const t = useTranslations("notifications")
  const router = useRouter()
  const [items, setItems] = useState(initialItems)
  const [error, setError] = useState("")
  const [status, setStatus] = useState("")
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set())
  const [allPending, startAll] = useTransition()
  const unreadCount = items.filter(notificationIsUnread).length

  async function markRead(id: string) {
    setError("")
    setStatus("")
    setPendingIds((current) => updatePendingIds(current, id, true))
    try {
      const response = await fetch(`/api/notifications/${encodeURIComponent(id)}/read`, {
        method: "POST",
      })
      if (!response.ok) throw new Error()
      const readAt = new Date().toISOString()
      setItems((current) => current.map((item) =>
        item.id === id ? { ...item, read_at: readAt } : item,
      ))
      setStatus(t("markedRead"))
      router.refresh()
    } catch {
      setError(t("readError"))
    } finally {
      setPendingIds((current) => updatePendingIds(current, id, false))
    }
  }

  function markAllRead() {
    setError("")
    setStatus("")
    startAll(async () => {
      try {
        const response = await fetch("/api/notifications/read-all", { method: "POST" })
        if (!response.ok) throw new Error()
        const readAt = new Date().toISOString()
        setItems((current) => current.map((item) => ({ ...item, read_at: item.read_at ?? readAt })))
        setStatus(t("markedAll"))
        router.refresh()
      } catch {
        setError(t("readAllError"))
      }
    })
  }

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <MonoLabel tone="muted">{t("unreadCount", { count: unreadCount })}</MonoLabel>
        <Button
          type="button"
          variant="secondary"
          disabled={unreadCount === 0 || allPending || pendingIds.size > 0}
          onClick={markAllRead}
        >
          <Checks size={16} weight="bold" aria-hidden />
          {allPending ? t("markingAll") : t("markAll")}
        </Button>
      </div>

      {error ? (
        <p role="alert" className="border border-error/50 bg-error/10 p-3 text-sm text-error">
          {error}
        </p>
      ) : null}
      <p aria-live="polite" className="sr-only">{status}</p>

      {items.length === 0 ? (
        <div className="border border-border-gray bg-graphite p-6">
          <MonoLabel tone="dim">{t("emptyEyebrow")}</MonoLabel>
          <p className="mt-2 text-sm text-muted">{t("emptyBody")}</p>
        </div>
      ) : (
        <ol className="space-y-3">
          {items.map((item) => {
            const href = notificationHref(item)
            const unread = notificationIsUnread(item)
            const message = notificationMessage(item)
            const values = message.values.role
              ? { ...message.values, role: t(`roles.${notificationRole(message.values.role)}`) }
              : message.values
            return (
              <li key={item.id}>
                <article
                  className={cn(
                    "border bg-graphite p-4 transition-colors",
                    unread ? "border-cyan" : "border-border-gray opacity-75",
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <MonoLabel tone={unread ? "cyan" : "dim"}>
                        {t(`types.${notificationTypeKey(item.type)}`)}
                      </MonoLabel>
                      <h2 className="mt-1 font-display text-xl tracking-wide text-raw-white">
                        {message.localized && message.titleKey
                          ? t(`messages.${message.titleKey}`, values)
                          : item.title}
                      </h2>
                      {message.body ? <p className="mt-1 text-sm text-muted">{message.body}</p> : null}
                      <time
                        dateTime={item.created_at}
                        className="mt-2 block font-mono text-[10px] uppercase tracking-label text-muted"
                      >
                        {formatRelative(item.created_at, locale)}
                      </time>
                    </div>
                    <StatusBadge
                      status={unread ? "unread" : "read"}
                      label={t(unread ? "unread" : "read")}
                    />
                  </div>
                  <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border-gray pt-3">
                    {href ? (
                      <Link
                        href={href}
                        className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-label text-cyan hover:underline"
                      >
                        {t("open")}
                        <ArrowSquareOut size={14} weight="bold" aria-hidden />
                      </Link>
                    ) : null}
                    {unread ? (
                      <button
                        type="button"
                        disabled={allPending || pendingIds.has(item.id)}
                        onClick={() => markRead(item.id)}
                        className="ml-auto inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid disabled:opacity-50"
                      >
                        <Check size={14} weight="bold" aria-hidden />
                        {pendingIds.has(item.id) ? t("marking") : t("markRead")}
                      </button>
                    ) : null}
                  </div>
                </article>
              </li>
            )
          })}
        </ol>
      )}
    </>
  )
}
