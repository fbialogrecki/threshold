import type { ReactNode } from "react"
import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { RouteRedirect } from "@/components/auth/route-redirect"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { AppShell } from "@/components/shell/app-shell"
import {
  hasRequiredOnboarding,
  onboardingHref,
} from "@/lib/auth/routing"
import { getSessionState } from "@/lib/auth/session"

/**
 * Layout for public SSR details (/events/[slug], /u/[username], /pages/[slug]).
 * Logged-in viewers get the full AppShell; anonymous viewers get the minimal
 * public header.
 */
export async function PublicShell({
  children,
  wide = false,
}: {
  children: ReactNode
  wide?: boolean
}) {
  const [state, t, authStatus] = await Promise.all([
    getSessionState(),
    getTranslations("auth"),
    getTranslations("authServiceUnavailable"),
  ])

  if (state.status === "invalid") return <RouteRedirect destination="recover" />
  const onboardingRequired = state.status === "authenticated"
    && !hasRequiredOnboarding(state.session)
  if (state.status === "authenticated" && !onboardingRequired) {
    return <AppShell session={state.session} wide={wide}>{children}</AppShell>
  }

  return (
    <div className="min-h-screen bg-pitch text-raw-white">
      <header className="border-b border-border-gray bg-graphite">
        <div className="mx-auto flex w-full max-w-feed items-center justify-between px-4 py-4 sm:px-6">
          <Link href="/" className="font-display text-xl tracking-[0.08em] text-raw-white">
            THRESHOLD<span className="text-acid">▮</span>
          </Link>
          <div className="flex items-center gap-2">
            <LocaleSwitcher />
            <Link
              href={onboardingRequired ? onboardingHref() : "/login"}
              className="border border-acid px-3 py-1.5 font-mono text-[11px] uppercase tracking-cta text-acid transition-colors hover:bg-acid hover:text-pitch"
            >
              {onboardingRequired ? t("completeOnboarding") : t("login")}{" "}
              <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
      </header>
      {onboardingRequired ? (
        <div
          role="status"
          className="border-b border-acid/50 bg-[#111706] px-4 py-2 text-center font-mono text-[11px] uppercase tracking-label text-acid"
        >
          {t("onboardingRequired")}{" "}
          <Link href={onboardingHref()} className="underline hover:text-raw-white">
            {t("completeOnboarding")}
          </Link>
        </div>
      ) : state.status === "unavailable" ? (
        <div
          role="status"
          className="border-b border-orange/50 bg-[#1a1206] px-4 py-2 text-center font-mono text-[11px] uppercase tracking-label text-orange"
        >
          {authStatus("publicBanner")}
        </div>
      ) : null}
      <main className="px-4 py-8 sm:px-6">
        <div className={wide ? "mx-auto w-full max-w-event-detail" : "mx-auto w-full max-w-feed"}>
          {children}
        </div>
      </main>
    </div>
  )
}
