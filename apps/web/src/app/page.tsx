import type { Metadata } from "next"
import type { ReactNode } from "react"
import { Lock } from "@phosphor-icons/react/ssr"
import { getTranslations } from "next-intl/server"
import Link from "next/link"

import { auth } from "@/auth"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { LogoutButton } from "@/components/auth/logout-button"
import { ButtonLink } from "@/components/ui/button"
import { authenticatedHref } from "@/lib/auth/routing"

const REPO_URL = "https://github.com/fbialogrecki/threshold"
const REPO_LABEL = "github.com/fbialogrecki/threshold"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("landing.metadata")
  return { title: t("title"), description: t("description") }
}

function Section({
  index,
  title,
  children,
}: {
  index: string
  title: string
  children: ReactNode
}) {
  return (
    <section className="grid gap-4 border-t border-border-gray py-10 sm:grid-cols-[10rem_1fr] sm:gap-10 sm:py-14">
      <div className="flex items-baseline gap-3 sm:flex-col sm:gap-3">
        <span className="font-mono text-[11px] tracking-label text-muted">{index}</span>
        <h2 className="font-display text-xl tracking-wide sm:text-2xl">{title}</h2>
      </div>
      <div className="max-w-[68ch] text-pretty">{children}</div>
    </section>
  )
}

function Fact({ label, body }: { label: string; body: string }) {
  return (
    <div className="border-b border-border-gray py-4 first:pt-0 last:border-b-0 last:pb-0">
      <dt className="font-mono text-[11px] uppercase tracking-label text-raw-white">{label}</dt>
      <dd className="mt-1.5 text-[15px] leading-7 text-dim-white">{body}</dd>
    </div>
  )
}

function Question({ question, answer }: { question: string; answer: string }) {
  return (
    <div className="border-b border-border-gray py-4 first:pt-0 last:border-b-0 last:pb-0">
      <dt className="font-semibold text-[15px] text-raw-white">{question}</dt>
      <dd className="mt-1.5 text-[15px] leading-7 text-dim-white">{answer}</dd>
    </div>
  )
}

export default async function Landing() {
  const [session, t] = await Promise.all([auth(), getTranslations("landing")])
  const authed = Boolean(session?.user)
  const boundaryLabel = t("privacyBoundary")

  return (
    <main className="flex min-h-screen flex-col bg-pitch text-raw-white">
      {/*
        The hero band is the only atmospheric region: the wash, grid, scanlines
        and grain end exactly where the threshold rule is drawn. Below it the
        page uses the panel's language, so registration is not a visual break.
      */}
      <div className="landing-void relative flex min-h-[92vh] flex-col overflow-hidden">
        <div aria-hidden className="landing-grid pointer-events-none absolute inset-0" />
        <div aria-hidden className="landing-scanlines pointer-events-none absolute inset-0" />
        <div aria-hidden className="landing-grain pointer-events-none absolute inset-0" />

        <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col px-5 sm:px-10">
          <a
            href="#content"
            className="skip-link border border-acid bg-pitch px-3 py-2 font-mono text-[11px] uppercase tracking-label text-acid"
          >
            {t("skipToContent")}
          </a>
          <header className="flex items-center justify-between gap-4 border-b border-border-gray py-5 sm:py-6">
            <Link
              href="/"
              translate="no"
              className="font-display text-xl tracking-[0.12em] sm:text-2xl"
            >
              THRESHOLD<span className="text-acid" aria-hidden>▮</span>
            </Link>
            <nav aria-label={t("navigation")} className="flex items-center gap-2 sm:gap-4">
              <LocaleSwitcher />
              <Link
                href="/privacy"
                className="hidden font-mono text-[10px] uppercase tracking-label text-muted hover:text-acid sm:block"
              >
                {boundaryLabel}
              </Link>
              {authed ? (
                <LogoutButton />
              ) : (
                <Link
                  href="/login"
                  className="font-mono text-[10px] uppercase tracking-label text-dim-white hover:text-acid sm:text-[11px]"
                >
                  {t("login")}
                </Link>
              )}
            </nav>
          </header>

          {/*
            The headline is sized against this container, not the viewport: the
            container is centred and capped, so `vw` overflowed the longest
            Polish word. `cqi` cannot, at any width, in either locale. The `vh`
            arm only ever shrinks it, keeping the buttons reachable on a short
            landscape viewport without touching the width guarantee.
          */}
          <div className="landing-rise @container flex flex-1 flex-col justify-center py-12">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-acid sm:text-[11px]">
              {t("eyebrow")}
              <span className="landing-cursor ml-1" aria-hidden>▮</span>
            </p>
            <h1 className="mt-5 font-display text-[min(11.5cqi,18vh)] leading-[0.78] tracking-[0.01em]">
              <span className="block">{t("heroLineOne")}</span>
              <span
                className="block text-acid"
                style={{ textShadow: "0 0 28px rgba(198,255,0,0.28)" }}
              >
                {t("heroLineTwo")}
              </span>
            </h1>
            <p className="mt-7 max-w-[46ch] text-pretty text-[15px] leading-8 text-dim-white sm:text-lg">
              {t("lede")}
            </p>
            <p className="mt-4 font-mono text-[10px] uppercase tracking-label text-raw-white sm:text-[11px]">
              <span className="text-acid" aria-hidden>●</span> {t("registrationOpen")}
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink
                variant="primary"
                href={authed ? authenticatedHref(session!, "/app") : "/register"}
                className="px-5 py-3"
              >
                {authed ? t("enterFeed") : t("createAccount")}
              </ButtonLink>
              {authed ? null : (
                <ButtonLink href="/login" className="px-5 py-3">
                  {t("login")}
                </ButtonLink>
              )}
            </div>
          </div>

          <div className="mt-auto flex items-center gap-3 pb-8">
            <span className="landing-threshold h-px flex-1 bg-acid" />
            <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-acid">
              {t("thresholdLabel")}
            </span>
          </div>
        </div>
      </div>

      <div id="content" tabIndex={-1} className="mx-auto w-full max-w-6xl px-5 sm:px-10">
        <Section index="01" title={t("manifest.title")}>
          <p className="text-[15px] leading-7 text-raw-white">{t("manifest.lede")}</p>
          <dl className="mt-6">
            <Fact label={t("manifest.ranking.label")} body={t("manifest.ranking.body")} />
            <Fact label={t("manifest.ads.label")} body={t("manifest.ads.body")} />
            <Fact label={t("manifest.trackers.label")} body={t("manifest.trackers.body")} />
          </dl>
        </Section>

        <Section index="02" title={t("forYou.title")}>
          <dl>
            <Fact label={t("forYou.chronology.label")} body={t("forYou.chronology.body")} />
            <Fact label={t("forYou.events.label")} body={t("forYou.events.body")} />
            <Fact label={t("forYou.name.label")} body={t("forYou.name.body")} />
          </dl>
        </Section>

        <Section index="03" title={t("forScene.title")}>
          <dl>
            <Fact label={t("forScene.page.label")} body={t("forScene.page.body")} />
            <Fact label={t("forScene.events.label")} body={t("forScene.events.body")} />
            <Fact label={t("forScene.guestlist.label")} body={t("forScene.guestlist.body")} />
          </dl>
          <p className="mt-6 font-mono text-[11px] uppercase tracking-label text-muted">
            {t("forScene.note")}
          </p>
        </Section>

        {/* Protection reads as full contrast plus a padlock, never as colour. */}
        <Section index="04" title={t("boundary.title")}>
          <div className="flex gap-3">
            <Lock size={18} weight="bold" className="mt-0.5 shrink-0 text-raw-white" aria-hidden />
            <p className="text-[15px] leading-7 text-raw-white">{t("boundary.body")}</p>
          </div>
          <Link
            href="/privacy"
            className="mt-5 inline-block font-mono text-[11px] uppercase tracking-label text-raw-white underline decoration-border-gray underline-offset-4 hover:decoration-acid hover:text-acid"
          >
            {boundaryLabel} <span aria-hidden>→</span>
          </Link>
        </Section>

        <Section index="05" title={t("questions.title")}>
          <dl>
            <Question question={t("questions.free.question")} answer={t("questions.free.answer")} />
            <Question
              question={t("questions.realName.question")}
              answer={t("questions.realName.answer")}
            />
            <Question
              question={t("questions.anonymous.question")}
              answer={t("questions.anonymous.answer")}
            />
          </dl>
        </Section>

        <Section index="06" title={t("who.title")}>
          <p className="text-[15px] leading-7 text-dim-white">{t("who.body")}</p>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            translate="no"
            className="mt-5 inline-block font-mono text-[11px] tracking-label text-raw-white underline decoration-border-gray underline-offset-4 hover:decoration-acid hover:text-acid"
          >
            {REPO_LABEL} <span aria-hidden>→</span>
          </a>
        </Section>

        <div className="flex flex-wrap items-center justify-between gap-5 border-t border-border-gray py-10">
          <p className="font-mono text-[11px] uppercase tracking-label text-raw-white">
            <span className="text-acid" aria-hidden>●</span> {t("closing")}
          </p>
          <ButtonLink
            variant="primary"
            href={authed ? authenticatedHref(session!, "/app") : "/register"}
            className="px-5 py-3"
          >
            {authed ? t("enterFeed") : t("createAccount")}
          </ButtonLink>
        </div>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border-gray py-6 font-mono text-[10px] uppercase tracking-label text-muted">
          <span>{t("footer")}</span>
          <Link href="/privacy" className="hover:text-acid">
            {boundaryLabel} <span aria-hidden>→</span>
          </Link>
        </footer>
      </div>
    </main>
  )
}
