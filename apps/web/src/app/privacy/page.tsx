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
    <main className="min-h-screen bg-pitch px-5 py-10 text-raw-white sm:px-10">
      <div className="mx-auto w-full max-w-6xl">
        <header className="border-b border-border-gray pb-8">
          <div className="flex items-start justify-between gap-4">
            <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-muted">
              {t("eyebrow")}
            </p>
            <LocaleSwitcher />
          </div>
          <h1 className="mt-6 max-w-3xl font-display text-3xl leading-tight tracking-wide sm:text-4xl">
            {t("title")}
          </h1>
          <p className="mt-6 inline-block border border-orange px-3 py-2 font-mono text-[11px] uppercase tracking-label text-orange">
            {t("limit")}
          </p>
        </header>

        <section className="grid gap-4 border-b border-border-gray py-10 sm:grid-cols-[10rem_1fr] sm:gap-10 sm:py-14">
          <h2 className="font-mono text-[11px] uppercase tracking-label text-muted">
            {t("boundary")}
          </h2>
          <dl className="max-w-[68ch]">
            {accessFacts.map((fact) => (
              <div
                className="border-b border-border-gray py-4 first:pt-0 last:border-b-0 last:pb-0"
                key={fact}
              >
                <dt className="font-mono text-[11px] uppercase tracking-cta text-acid">
                  {t(`facts.${fact}.label`)}
                </dt>
                <dd className="mt-1.5 text-[15px] leading-7 text-raw-white">
                  {t(`facts.${fact}.value`)}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        {/* Same label axis as the section above, with nothing to name in it. */}
        <section className="grid py-10 sm:grid-cols-[10rem_1fr] sm:gap-10 sm:py-14">
          <div className="max-w-[68ch] sm:col-start-2">
            <p className="text-[15px] leading-8 text-dim-white sm:text-lg">{t("intro")}</p>
            <ol className="mt-8">
              {disclosurePoints.map((point, index) => (
                <li
                  className="grid gap-3 border-t border-border-gray py-5 sm:grid-cols-[3rem_1fr]"
                  key={point}
                >
                  <span className="font-mono text-[11px] tracking-label text-muted">
                    0{index + 1}
                  </span>
                  <p className="text-[15px] leading-7 text-raw-white">{t(`points.${point}`)}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-border-gray py-6 font-mono text-[10px] uppercase tracking-label text-muted">
          <span>{t("footer")}</span>
          <Link className="hover:text-acid" href="/">
            {t("back")}
          </Link>
        </footer>
      </div>
    </main>
  )
}
