import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { PageManagementPanel, type ManagedPage } from "@/components/pages/page-management-panel"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { listManagedPages } from "@/lib/auth/product-auth"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("organizerPages.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function OrganizerPagesPage() {
  const [response, t] = await Promise.all([
    listManagedPages().catch(() => null),
    getTranslations("organizerPages"),
  ])
  const pages = (response?.status === 200 && Array.isArray(response.body) ? response.body : []) as ManagedPage[]

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      {!response || response.status !== 200 ? (
        <EmptyState
          tone="error"
          title={t("loadErrorTitle")}
          body={t("loadError")}
          eyebrow={t("errorEyebrow")}
          actionLabel={t("retry")}
          actionHref="/app/pages"
        />
      ) : (
        <PageManagementPanel pages={pages} />
      )}
    </div>
  )
}
