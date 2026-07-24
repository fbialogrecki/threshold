import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { NotificationInbox } from "@/components/notifications/notification-inbox"
import { EmptyState } from "@/components/ui/empty-state"
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
    <div className="flex flex-col gap-5">
      <h1 className="sr-only">{t("title")}</h1>
      <NotificationInbox initialItems={notifications} />
    </div>
  )
}
