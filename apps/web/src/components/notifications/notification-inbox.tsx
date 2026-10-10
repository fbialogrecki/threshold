"use client"

import { ArrowSquareOut, Check, Checks } from "@phosphor-icons/react"
import { useLocale, useTranslations } from "next-intl"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/ui/empty-state"
import { FormAlert } from "@/components/ui/field"
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
        <p className="flex items-center gap-2 text-sm text-dim-white">
          <span
            aria-hidden
            className={cn("size-2 rounded-full", unreadCount > 0 ? "bg-acid" : "bg-status-neutral-border")}
          />
          {t("unreadCount", { count: unreadCount })}
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={unreadCount === 0 || allPending || pendingIds.size > 0}
          onClick={markAllRead}
        >
          <Checks size={16} weight="bold" aria-hidden />
          {allPending ? t("markingAll") : t("markAll")}
        </Button>
      </div>

      {error ? <FormAlert>{error}</FormAlert> : null}
      <p aria-live="polite" className="sr-only">{status}</p>

      {items.length === 0 ? (
        <EmptyState eyebrow={t("emptyEyebrow")} title={t("emptyTitle")} body={t("emptyBody")} />
      ) : (
        <ol className="flex flex-col gap-2">
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
                    "relative rounded-surface border p-4 transition-colors sm:p-5",
                    unread ? "border-acid/40 bg-acid/5" : "border-border-gray bg-graphite/60",
                  )}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <MonoLabel tone={unread ? "acid" : "muted"}>
                        {t(`types.${notificationTypeKey(item.type)}`)}
                      </MonoLabel>
                      <h2
                        className={cn(
                          "mt-1.5 text-[15px] leading-6 break-words",
                          unread ? "font-semibold text-raw-white" : "font-medium text-dim-white",
                        )}
                      >
                        {message.localized && message.titleKey
                          ? t(`messages.${message.titleKey}`, values)
                          : item.title}
                      </h2>
                      {message.body ? <p className="mt-1 text-sm leading-6 text-muted">{message.body}</p> : null}
                      <time dateTime={item.created_at} className="mt-2 block text-[13px] text-muted">
                        {formatRelative(item.created_at, locale)}
                      </time>
                    </div>
                    <StatusBadge
                      className="shrink-0"
                      status={unread ? "unread" : "read"}
                      label={t(unread ? "unread" : "read")}
                    />
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border-gray pt-3">
                    {href ? (
                      <Link
                        href={href}
                        className="inline-flex min-h-9 items-center gap-2 rounded-control px-2 text-sm font-semibold text-acid transition-colors hover:bg-raised"
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
                        className="ml-auto inline-flex min-h-9 items-center gap-2 rounded-control px-2 text-sm text-dim-white transition-colors hover:bg-raised hover:text-raw-white disabled:opacity-50"
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
