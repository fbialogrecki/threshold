import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("savedPage.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function SavedPage() {
  const t = await getTranslations("savedPage")
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <EmptyState
        title={t("emptyTitle")}
        body={t("emptyBody")}
        eyebrow={t("emptyEyebrow")}
        actionLabel={t("action")}
        actionHref="/app"
      />
    </div>
  )
}
