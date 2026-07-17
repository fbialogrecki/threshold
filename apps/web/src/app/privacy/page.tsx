import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import Link from "next/link"

import { LocaleSwitcher } from "@/components/i18n/locale-switcher"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("privacy.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function PrivacyPage() {
  const t = await getTranslations("privacy")
  const accessFacts = ["server", "plaintext", "future"] as const
  const disclosurePoints = ["one", "two", "three"] as const

  return (
    <main className="min-h-screen bg-pitch px-6 py-10 text-raw-white sm:px-10 lg:px-16">
      <div className="mx-auto w-full max-w-5xl border border-border-gray bg-graphite">
        <header className="border-b border-border-gray p-6 sm:p-8">
          <div className="flex items-start justify-between gap-4">
            <p className="font-mono text-xs uppercase tracking-[0.32em] text-acid">
              {t("eyebrow")}
            </p>
            <LocaleSwitcher />
          </div>
          <h1 className="mt-6 max-w-3xl font-display text-4xl tracking-wide text-raw-white sm:text-5xl">
            {t("title")}
          </h1>
          <div className="mt-6 inline-block border border-orange bg-[#1a0f0a] p-3 font-mono text-xs uppercase tracking-label text-orange">
            {t("limit")}
          </div>
        </header>

        <div className="grid lg:grid-cols-[1.1fr_0.9fr]">
          <section className="border-b border-border-gray p-6 sm:p-8 lg:border-b-0 lg:border-r">
            <p className="max-w-2xl text-lg leading-8 text-dim-white">
              {t("intro")}
            </p>
            <div className="mt-8 grid gap-4">
              {disclosurePoints.map((point, index) => (
                <article
                  className="grid gap-3 border border-border-gray bg-raised p-5 sm:grid-cols-[3rem_1fr]"
                  key={point}
                >
                  <span className="font-mono text-sm text-muted">
                    0{index + 1}
                  </span>
                  <p className="leading-7 text-raw-white">{t(`points.${point}`)}</p>
                </article>
              ))}
            </div>
          </section>

          <aside className="p-6 sm:p-8">
            <h2 className="font-mono text-sm uppercase tracking-[0.28em] text-muted">
              {t("boundary")}
            </h2>
            <div className="mt-6 divide-y divide-border-gray border border-border-gray">
              {accessFacts.map((fact) => (
                <div className="p-5" key={fact}>
                  <p className="font-mono text-xs uppercase tracking-cta text-acid">
                    {t(`facts.${fact}.label`)}
                  </p>
                  <p className="mt-3 text-lg leading-7 text-raw-white">
                    {t(`facts.${fact}.value`)}
                  </p>
                </div>
              ))}
            </div>
          </aside>
        </div>

        <footer className="grid gap-2 border-t border-border-gray p-6 font-mono text-xs uppercase tracking-label text-muted sm:p-8">
          <p>{t("footer")}</p>
          <Link className="text-cyan" href="/">
            {t("back")}
          </Link>
        </footer>
      </div>
    </main>
  )
}
