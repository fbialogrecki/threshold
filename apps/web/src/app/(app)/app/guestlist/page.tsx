import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { EmptyState } from "@/components/ui/empty-state"
import { MonoLabel } from "@/components/ui/mono-label"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("guestlistPage.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function GuestlistPage() {
  const t = await getTranslations("guestlistPage")

  return (
    <div className="flex flex-col gap-6">
      <header className="border-b border-border-gray pb-4">
        <h1 className="font-display text-4xl tracking-wide text-raw-white">
          {t("title")}
        </h1>
        <MonoLabel tone="muted" className="mt-1 block">
          {t("subtitle")}
        </MonoLabel>
      </header>

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
