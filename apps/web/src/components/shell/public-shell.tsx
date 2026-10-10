import type { ReactNode } from "react"
import Link from "next/link"
import { getTranslations } from "next-intl/server"

import { RouteRedirect } from "@/components/auth/route-redirect"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { AppShell } from "@/components/shell/app-shell"
import { ButtonLink } from "@/components/ui/button"
import { cn } from "@/lib/cn"
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
      <header className="sticky top-0 z-30 border-b border-border-gray bg-pitch/90 backdrop-blur-md">
        <div
          className={cn(
            "mx-auto flex w-full items-center justify-between gap-3 px-4 py-3 sm:px-6",
            wide ? "max-w-event-detail" : "max-w-feed",
          )}
        >
          <Link href="/" translate="no" className="flex shrink-0 items-center gap-1.5">
            <span className="font-display text-xl tracking-[0.1em] text-raw-white">PERLIMEN</span>
            <span className="size-1.5 rounded-full bg-acid" aria-hidden />
          </Link>
          {/* min-w-0 lets the longer Polish CTA wrap instead of widening a 360px page. */}
          <div className="flex min-w-0 items-center gap-2">
            <LocaleSwitcher className="shrink-0" />
            <ButtonLink
              href={onboardingRequired ? onboardingHref() : "/login"}
              variant="primary"
              size="sm"
              className="min-w-0 text-center leading-tight"
            >
              {onboardingRequired ? t("completeOnboarding") : t("login")}
            </ButtonLink>
          </div>
        </div>
      </header>
      {onboardingRequired ? (
        <div
          role="status"
          className="border-b border-acid/30 bg-acid/5 px-4 py-2.5 text-center text-sm text-raw-white"
        >
          {t("onboardingRequired")}{" "}
          <Link
            href={onboardingHref()}
            className="font-semibold text-acid underline underline-offset-4 hover:text-raw-white"
          >
            {t("completeOnboarding")}
          </Link>
        </div>
      ) : state.status === "unavailable" ? (
        <div
          role="status"
          className="border-b border-orange/40 bg-orange/10 px-4 py-2.5 text-center text-sm text-raw-white"
        >
          {authStatus("publicBanner")}
        </div>
      ) : null}
      <main className="px-4 py-6 sm:px-6 sm:py-8">
        <div className={wide ? "mx-auto w-full max-w-event-detail" : "mx-auto w-full max-w-feed"}>
          {children}
        </div>
      </main>
    </div>
  )
}
