import { getTranslations } from "next-intl/server"
import Link from "next/link"
import type { ReactNode } from "react"

import { LocaleSwitcher } from "@/components/i18n/locale-switcher"

/** The frame shared by login, register, reset, verify and onboarding. */
export async function AuthShell({ children }: { children: ReactNode }) {
  const t = await getTranslations("landing")
  return (
    <main className="relative isolate flex min-h-svh flex-col overflow-hidden bg-pitch text-raw-white">
      <div
        aria-hidden
        className="hero-visual pointer-events-none absolute -top-48 -right-64 -z-10 w-[48rem] opacity-40"
      >
        <div className="hero-fallback" />
      </div>
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-10">
        <Link
          href="/"
          translate="no"
          className="flex items-center gap-1.5 font-display text-xl tracking-[0.12em]"
        >
          PERLIMEN
          <span className="size-2 rounded-full bg-acid" aria-hidden />
        </Link>
        <LocaleSwitcher />
      </header>
      <div className="mx-auto flex w-full max-w-6xl flex-1 items-center justify-center px-5 py-8 sm:px-10 sm:py-12">
        {children}
      </div>
      <footer className="mx-auto flex w-full max-w-6xl flex-wrap justify-between gap-3 px-5 py-6 text-sm text-muted sm:px-10">
        <span>{t("footer")}</span>
        <Link href="/privacy" className="transition-colors hover:text-acid">
          {t("privacyBoundary")}
        </Link>
      </footer>
    </main>
  )
}
