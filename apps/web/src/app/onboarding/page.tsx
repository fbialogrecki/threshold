import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import { redirect } from "next/navigation"

import { auth } from "@/auth"
import { AuthShell } from "@/components/auth/auth-shell"
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
    <AuthShell>
      <div className="@container w-full max-w-3xl">
        <h1 className="animate-rise font-display text-[min(12cqi,4.5rem)] leading-[0.9]">
          {t("title")}
        </h1>
        <p className="mt-3 animate-rise text-[17px] leading-7 text-dim-white [animation-delay:80ms]">
          {t("subtitle")}
        </p>
        <div className="mt-8 animate-rise [animation-delay:160ms]">
          <OnboardingWizard
            defaultNickname={session.user.username ?? ""}
            callbackUrl={safeCallback}
          />
        </div>
      </div>
    </AuthShell>
  )
}
