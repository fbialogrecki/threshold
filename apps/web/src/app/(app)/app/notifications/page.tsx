import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { NotificationInbox } from "@/components/notifications/notification-inbox"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
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
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t("title")} />
      {result?.status === 200 ? (
        <NotificationInbox initialItems={asNotifications(result.body)} />
      ) : (
        <EmptyState
          tone="error"
          eyebrow={t("errorEyebrow")}
          title={t("loadErrorTitle")}
          body={t("loadError")}
          actionLabel={t("retry")}
          actionHref="/app/notifications"
        />
      )}
    </div>
  )
}
