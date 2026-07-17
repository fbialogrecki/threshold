import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import { redirect } from "next/navigation"

import { auth } from "@/auth"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard"
import {
  authenticatedHref,
  loginHref,
} from "@/lib/auth/routing"
import { safeInternalHref } from "@/lib/safe-href"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("onboarding.metadata")
  return { title: t("title"), description: t("description") }
}

export const dynamic = "force-dynamic"

export default async function OnboardingPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string }>
}) {
  const { callbackUrl } = await searchParams
  const safeCallback = safeInternalHref(callbackUrl, "/app") ?? "/app"
  const session = await auth()
  if (!session?.user) redirect(loginHref(`/onboarding?callbackUrl=${encodeURIComponent(safeCallback)}`))
  const destination = authenticatedHref(session, safeCallback)
  if (!destination.startsWith("/onboarding")) redirect(destination)
  const t = await getTranslations("onboarding")

  return (
    <main className="min-h-screen bg-pitch px-4 py-10 text-raw-white sm:px-8">
      <div className="mx-auto w-full max-w-2xl">
        <div className="flex items-start justify-between gap-4">
          <h1 className="font-display text-5xl tracking-wide">{t("title")}</h1>
          <LocaleSwitcher />
        </div>
        <p className="mt-2 font-mono text-[11px] uppercase tracking-label text-muted">
          {t("subtitle")}
        </p>
        <div className="mt-8">
          <OnboardingWizard
            defaultNickname={session.user.username ?? ""}
            callbackUrl={safeCallback}
          />
        </div>
      </div>
    </main>
  )
}
