import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { NotificationInbox } from "@/components/notifications/notification-inbox"
import { EmptyState } from "@/components/ui/empty-state"
import { MonoLabel } from "@/components/ui/mono-label"
import { listNotifications, type NotificationItem } from "@/lib/auth/product-auth"

function asNotifications(body: unknown): NotificationItem[] {
  return Array.isArray(body) ? (body as NotificationItem[]) : []
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("notifications.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function NotificationsPage() {
  const [result, t] = await Promise.all([
    listNotifications().catch(() => null),
    getTranslations("notifications"),
  ])
  if (!result || result.status !== 200) {
    return (
      <EmptyState
        eyebrow={t("errorEyebrow")}
        title={t("loadErrorTitle")}
        body={t("loadError")}
        actionLabel={t("retry")}
        actionHref="/app/notifications"
      />
    )
  }
  const notifications = asNotifications(result.body)

  return (
    <div className="space-y-6">
      <header className="border-b border-border-gray pb-5">
        <MonoLabel tone="cyan">{t("eyebrow")}</MonoLabel>
        <h1 className="mt-2 font-display text-4xl tracking-wide text-raw-white">{t("title")}</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted">
          {t("subtitle")}
        </p>
      </header>

      <NotificationInbox initialItems={notifications} />
    </div>
  )
}
