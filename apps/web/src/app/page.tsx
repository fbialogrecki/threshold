import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import Link from "next/link"

import { auth } from "@/auth"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { LogoutButton } from "@/components/auth/logout-button"
import { authenticatedHref } from "@/lib/auth/routing"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("landing.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function Landing() {
  const [session, t] = await Promise.all([auth(), getTranslations("landing")])
  const authed = Boolean(session?.user)
  const principles = [
    { index: "01", title: t("principles.chronological.title"), body: t("principles.chronological.body"), tone: "text-acid" },
    { index: "02", title: t("principles.public.title"), body: t("principles.public.body"), tone: "text-cyan" },
    { index: "03", title: t("principles.private.title"), body: t("principles.private.body"), tone: "text-violet" },
  ]

  return (
    <main className="landing-void relative flex min-h-screen flex-col overflow-hidden text-raw-white">
      <div aria-hidden className="landing-grid pointer-events-none absolute inset-0" />
      <div aria-hidden className="landing-scanlines pointer-events-none absolute inset-0" />
      <div aria-hidden className="landing-grain pointer-events-none absolute inset-0" />

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 sm:px-10">
        <header className="landing-rise flex items-center justify-between gap-4 border-b border-border-gray py-5 sm:py-6">
          <Link href="/" className="landing-flicker font-display text-xl tracking-[0.12em] sm:text-2xl">
            THRESHOLD<span className="text-acid">▮</span>
          </Link>
          <nav aria-label={t("navigation")} className="flex items-center gap-2 sm:gap-4">
            <LocaleSwitcher />
            <Link href="/privacy" className="hidden font-mono text-[10px] uppercase tracking-label text-muted hover:text-acid sm:block">
              {t("privacy")}
            </Link>
            {authed ? (
              <LogoutButton />
            ) : (
              <Link href="/login" className="font-mono text-[10px] uppercase tracking-label text-dim-white hover:text-acid sm:text-[11px]">
                {t("login")}
              </Link>
            )}
          </nav>
        </header>

        <section className="grid flex-1 items-center gap-10 py-12 lg:grid-cols-[1.25fr_0.75fr] lg:py-20">
          <div>
            <p className="landing-rise font-mono text-[10px] uppercase tracking-[0.24em] text-acid sm:text-[11px]" style={{ animationDelay: "100ms" }}>
              {t("eyebrow")}<span className="landing-cursor ml-1">▮</span>
            </p>
            <h1 className="mt-5 font-display text-[clamp(4.5rem,15vw,10rem)] leading-[0.78] tracking-[0.01em]">
              <span className="landing-rise block" style={{ animationDelay: "180ms" }}>{t("heroLineOne")}</span>
              <span className="landing-rise block text-acid" style={{ animationDelay: "300ms", textShadow: "0 0 28px rgba(198,255,0,0.28)" }}>
                {t("heroLineTwo")}
              </span>
            </h1>
            <div className="landing-rise mt-6 flex items-center gap-3" style={{ animationDelay: "420ms" }}>
              <span className="landing-threshold h-px flex-1 bg-acid" />
              <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-acid">{t("manifest")}</span>
            </div>
            <p className="landing-rise mt-7 max-w-2xl text-[15px] leading-8 text-dim-white sm:text-lg" style={{ animationDelay: "520ms" }}>
              {t("body")}
            </p>
            <p className="landing-rise mt-4 font-mono text-[10px] uppercase tracking-label text-raw-white sm:text-[11px]" style={{ animationDelay: "600ms" }}>
              <span className="text-acid" aria-hidden>●</span> {t("registrationOpen")}
            </p>
            <div className="landing-rise mt-8 flex flex-wrap gap-3" style={{ animationDelay: "680ms" }}>
              <Link
                href={authed ? authenticatedHref(session!, "/app") : "/register"}
                className="inline-flex items-center justify-center border border-acid bg-acid px-5 py-3 font-mono text-xs font-medium uppercase tracking-cta text-pitch transition-colors hover:bg-[#d4ff3a]"
                style={{ color: "var(--color-pitch)" }}
              >
                {authed ? t("enterFeed") : t("createAccount")}
              </Link>
              {authed ? null : (
                <Link href="/login" className="border border-border-gray px-5 py-3 font-mono text-xs uppercase tracking-cta text-dim-white transition-colors hover:border-acid hover:text-acid">
                  {t("login")}
                </Link>
              )}
            </div>
          </div>

          <div className="landing-rise grid border border-border-gray bg-border-gray" style={{ animationDelay: "420ms" }}>
            {principles.map((item) => (
              <article key={item.index} className="grid grid-cols-[2.5rem_1fr] gap-4 border-b border-border-gray bg-graphite p-5 last:border-b-0 sm:p-6">
                <span className={`font-mono text-xs ${item.tone}`}>{item.index}</span>
                <div>
                  <h2 className="font-display text-2xl tracking-wide">{item.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-dim-white">{item.body}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border-gray py-5 font-mono text-[10px] uppercase tracking-label text-muted">
          <span>{t("footer")}</span>
          <Link href="/privacy" className="text-cyan hover:underline">{t("privacyBoundary")}</Link>
        </footer>
      </div>
    </main>
  )
}
