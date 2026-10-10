import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { ComposeForm } from "@/components/compose/compose-form"
import { PageHeader } from "@/components/ui/page-header"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("composer.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function ComposePage() {
  const t = await getTranslations("composer")
  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <ComposeForm />
    </div>
  )
}
