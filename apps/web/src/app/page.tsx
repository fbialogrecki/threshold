import type { Metadata } from "next"
import type { ReactNode } from "react"
import {
  ArrowUpRight,
  CalendarBlank,
  CalendarPlus,
  Clock,
  EyeSlash,
  GithubLogo,
  ListBullets,
  Lock,
  Plus,
  ProhibitInset,
  QrCode,
  Storefront,
  UserCircle,
} from "@phosphor-icons/react/ssr"
import type { Icon } from "@phosphor-icons/react"
import { getTranslations } from "next-intl/server"
import Link from "next/link"

import { auth } from "@/auth"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { LogoutButton } from "@/components/auth/logout-button"
import { HeroVisual } from "@/components/landing/hero-visual"
import { ButtonLink } from "@/components/ui/button"
import { authenticatedHref } from "@/lib/auth/routing"
import { cn } from "@/lib/cn"

const REPO_URL = "https://github.com/fbialogrecki/perlimen"
const REPO_LABEL = "github.com/fbialogrecki/perlimen"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("landing.metadata")
  return { title: t("title"), description: t("description") }
}

function SectionTitle({ index, children }: { index: string; children: ReactNode }) {
  return (
    <h2 className="flex items-baseline gap-4 font-display text-3xl leading-none tracking-[0.01em] sm:text-5xl">
      <span className="font-mono text-sm font-medium tracking-normal text-acid">{index}</span>
      {children}
    </h2>
  )
}

function Feature({ icon: Glyph, label, body }: { icon: Icon; label: string; body: string }) {
  return (
    <div className="flex gap-4 border-t border-border-gray py-6 first:border-t-0 first:pt-0 last:pb-0">
      <Glyph size={22} className="mt-0.5 shrink-0 text-acid" aria-hidden />
      <div>
        <dt className="text-lg font-semibold text-raw-white">{label}</dt>
        <dd className="mt-1.5 text-[15px] leading-7 text-dim-white">{body}</dd>
      </div>
    </div>
  )
}

function Question({ question, answer }: { question: string; answer: string }) {
  return (
    <details className="landing-faq border-b border-border-gray">
      <summary className="flex cursor-pointer items-center justify-between gap-6 py-5 text-lg font-semibold text-raw-white transition-colors hover:text-acid">
        {question}
        <Plus
          size={20}
          className="landing-faq-icon shrink-0 text-acid transition-transform duration-300 ease-out-expo"
          aria-hidden
        />
      </summary>
      <p className="max-w-[60ch] pb-6 text-[15px] leading-7 text-dim-white">{answer}</p>
    </details>
  )
}

export default async function Landing() {
  const [session, t] = await Promise.all([auth(), getTranslations("landing")])
  const authed = Boolean(session?.user)
  const ctaHref = session?.user ? authenticatedHref(session, "/app") : "/register"
  const ctaLabel = authed ? t("enterFeed") : t("createAccount")
  const boundaryLabel = t("privacyBoundary")

  const refusals = [
    { icon: Clock, key: "ranking", offset: "" },
    { icon: ProhibitInset, key: "ads", offset: "sm:mt-10" },
    { icon: EyeSlash, key: "trackers", offset: "sm:mt-20" },
  ] as const

  return (
    <main className="relative bg-pitch text-raw-white">
      <a
        href="#content"
        className="skip-link rounded-control border border-acid bg-pitch px-4 py-2 text-sm font-semibold text-acid"
      >
        {t("skipToContent")}
      </a>

      <div className="landing-hero relative isolate overflow-hidden">
        <HeroVisual className="absolute top-14 right-[-40%] w-[115%] opacity-60 sm:top-10 sm:right-[-14%] sm:w-[76%] sm:opacity-90 lg:top-1/2 lg:right-[-4%] lg:w-[min(58%,46rem)] lg:-translate-y-1/2 lg:opacity-100" />

        <div className="relative mx-auto flex min-h-[min(100svh,58rem)] w-full max-w-6xl flex-col px-5 sm:px-10">
          <header className="flex items-center justify-between gap-2 py-5 sm:gap-4 sm:py-7">
            <Link
              href="/"
              translate="no"
              className="flex items-center gap-1.5 font-display text-lg tracking-[0.08em] sm:text-2xl sm:tracking-[0.12em]"
            >
              PERLIMEN
              <span className="size-2 rounded-full bg-acid" aria-hidden />
            </Link>
            <nav aria-label={t("navigation")} className="flex items-center gap-2 sm:gap-5">
              <LocaleSwitcher />
              <Link
                href="/privacy"
                className="hidden text-sm text-dim-white transition-colors hover:text-acid sm:block"
              >
                {boundaryLabel}
              </Link>
              {authed ? (
                <LogoutButton />
              ) : (
                <Link
                  href="/login"
                  className="shrink-0 whitespace-nowrap rounded-control border border-border-gray bg-pitch/60 px-3.5 py-1.5 text-sm font-medium transition-colors hover:border-acid hover:text-acid"
                >
                  {t("login")}
                </Link>
              )}
            </nav>
          </header>

          {/*
            The headline is sized against this capped container, not the
            viewport, so the longest Polish word cannot overflow at any width.
            The `vh` arm only shrinks it on short landscape screens to keep
            the CTA above the fold.
          */}
          <div className="@container flex flex-1 flex-col justify-center py-12 sm:py-16">
            <p className="inline-flex w-fit animate-rise items-center gap-2 rounded-full border border-border-gray bg-pitch/70 px-3 py-1.5 text-[13px] font-medium text-dim-white">
              <span className="size-1.5 rounded-full bg-acid" aria-hidden />
              {t("eyebrow")}
            </p>
            <h1 className="mt-6 animate-rise font-display text-[min(11.5cqi,17vh)] leading-[0.84] tracking-[-0.005em] [animation-delay:80ms]">
              <span className="block">{t("heroLineOne")}</span>
              <span className="block text-acid">{t("heroLineTwo")}</span>
            </h1>
            <p className="mt-7 max-w-[34ch] animate-rise text-pretty text-lg leading-relaxed text-dim-white [animation-delay:160ms] sm:text-xl">
              {t("lede")}
            </p>
            <div className="mt-9 flex animate-rise flex-wrap items-center gap-3 [animation-delay:240ms]">
              <ButtonLink variant="primary" size="lg" href={ctaHref}>
                {ctaLabel}
              </ButtonLink>
              {authed ? null : (
                <ButtonLink size="lg" href="/login" className="bg-pitch/60">
                  {t("login")}
                </ButtonLink>
              )}
            </div>
            <p className="mt-6 inline-flex animate-rise items-center gap-2 text-sm text-dim-white [animation-delay:320ms]">
              <span className="size-2 rounded-full bg-acid" aria-hidden />
              {t("registrationOpen")}
            </p>
          </div>

          <a
            href="#content"
            className="mb-8 w-fit text-sm text-muted transition-colors hover:text-acid"
          >
            {t("manifestLabel")}
          </a>
        </div>
      </div>

      <div id="content" tabIndex={-1} className="mx-auto w-full max-w-6xl px-5 sm:px-10">
        <section className="landing-reveal border-t border-border-gray py-16 sm:py-24">
          <SectionTitle index="01">{t("manifest.title")}</SectionTitle>
          <p className="mt-8 max-w-[22ch] text-pretty text-2xl leading-tight font-semibold sm:text-4xl">
            {t("manifest.lede")}
          </p>
          <dl className="mt-12 grid gap-3 sm:grid-cols-3 sm:items-start">
            {refusals.map(({ icon: Glyph, key, offset }) => (
              <div
                key={key}
                className={cn("rounded-surface border border-border-gray bg-graphite p-6", offset)}
              >
                <span className="grid size-11 place-items-center rounded-full bg-acid/10 text-acid">
                  <Glyph size={22} aria-hidden />
                </span>
                <dt className="mt-8 text-lg font-semibold">{t(`manifest.${key}.label`)}</dt>
                <dd className="mt-2 text-[15px] leading-7 text-dim-white">
                  {t(`manifest.${key}.body`)}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <div className="grid gap-x-12 border-t border-border-gray lg:grid-cols-[1fr_1.1fr]">
          <section className="landing-reveal py-16 sm:py-24">
            <SectionTitle index="02">{t("forYou.title")}</SectionTitle>
            <dl className="mt-10">
              <Feature
                icon={ListBullets}
                label={t("forYou.chronology.label")}
                body={t("forYou.chronology.body")}
              />
              <Feature
                icon={CalendarBlank}
                label={t("forYou.events.label")}
                body={t("forYou.events.body")}
              />
              <Feature
                icon={UserCircle}
                label={t("forYou.name.label")}
                body={t("forYou.name.body")}
              />
            </dl>
          </section>

          <section className="landing-reveal mb-16 rounded-surface border border-border-gray bg-graphite p-6 sm:p-10 lg:mt-12 lg:mb-24">
            <SectionTitle index="03">{t("forScene.title")}</SectionTitle>
            <dl className="mt-10">
              <Feature
                icon={Storefront}
                label={t("forScene.page.label")}
                body={t("forScene.page.body")}
              />
              <Feature
                icon={CalendarPlus}
                label={t("forScene.events.label")}
                body={t("forScene.events.body")}
              />
              <Feature
                icon={QrCode}
                label={t("forScene.guestlist.label")}
                body={t("forScene.guestlist.body")}
              />
            </dl>
            <p className="mt-8 text-sm text-muted">{t("forScene.note")}</p>
          </section>
        </div>

        {/* Protection reads as full contrast plus a padlock, never as colour. */}
        <section className="landing-reveal grid gap-8 border-t border-border-gray py-16 sm:grid-cols-[auto_1fr] sm:gap-12 sm:py-24">
          <Lock size={44} weight="bold" className="text-raw-white" aria-hidden />
          <div>
            <SectionTitle index="04">{t("boundary.title")}</SectionTitle>
            <p className="mt-6 max-w-[52ch] text-pretty text-lg leading-8 text-raw-white sm:text-xl sm:leading-9">
              {t("boundary.body")}
            </p>
            <Link
              href="/privacy"
              className="group mt-7 inline-flex items-center gap-2 text-[15px] font-semibold underline decoration-border-gray underline-offset-4 transition-colors hover:text-acid hover:decoration-acid"
            >
              {boundaryLabel}
              <ArrowUpRight
                size={16}
                className="transition-transform duration-200 ease-out-expo group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                aria-hidden
              />
            </Link>
          </div>
        </section>

        <section className="landing-reveal grid gap-10 border-t border-border-gray py-16 sm:py-24 lg:grid-cols-[1fr_1.6fr]">
          <SectionTitle index="05">{t("questions.title")}</SectionTitle>
          <div className="border-t border-border-gray lg:border-t-0">
            <Question question={t("questions.free.question")} answer={t("questions.free.answer")} />
            <Question
              question={t("questions.realName.question")}
              answer={t("questions.realName.answer")}
            />
            <Question
              question={t("questions.anonymous.question")}
              answer={t("questions.anonymous.answer")}
            />
            <Question
              question={t("questions.images.question")}
              answer={t("questions.images.answer")}
            />
            <Question question={t("questions.app.question")} answer={t("questions.app.answer")} />
          </div>
        </section>

        <section className="landing-reveal grid gap-10 border-t border-border-gray py-16 sm:py-24 lg:grid-cols-[1fr_1.6fr]">
          <SectionTitle index="06">{t("who.title")}</SectionTitle>
          <div>
            <p className="max-w-[56ch] text-pretty text-lg leading-8 text-dim-white">
              {t("who.body")}
            </p>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer"
              translate="no"
              className="group mt-7 inline-flex max-w-full items-center gap-2 rounded-full border border-border-gray px-4 py-2 text-sm font-medium transition-colors hover:border-acid hover:text-acid"
            >
              <GithubLogo size={18} className="shrink-0" aria-hidden />
              <span className="truncate">{REPO_LABEL}</span>
              <ArrowUpRight
                size={14}
                className="shrink-0 transition-transform duration-200 ease-out-expo group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                aria-hidden
              />
            </a>
          </div>
        </section>

        <div className="landing-reveal relative overflow-hidden rounded-surface border border-acid/30 bg-[radial-gradient(40rem_20rem_at_100%_0%,rgba(198,255,0,0.12),transparent_70%)] p-8 sm:p-14">
          <p className="font-display text-3xl leading-none sm:text-5xl">{t("closing")}</p>
          <ButtonLink variant="primary" size="lg" href={ctaHref} className="mt-8">
            {ctaLabel}
          </ButtonLink>
        </div>

        <footer className="mt-16 flex flex-wrap items-center justify-between gap-3 border-t border-border-gray py-8 text-sm text-muted">
          <span>{t("footer")}</span>
          <Link href="/privacy" className="transition-colors hover:text-acid">
            {boundaryLabel}
          </Link>
        </footer>
      </div>
    </main>
  )
}
