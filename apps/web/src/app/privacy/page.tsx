import { ArrowLeft, Lock } from "@phosphor-icons/react/ssr"
import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import Link from "next/link"

import { AuthShell } from "@/components/auth/auth-shell"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("privacy.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function PrivacyPage() {
  const t = await getTranslations("privacy")
  const accessFacts = ["server", "plaintext", "future"] as const
  const disclosurePoints = ["one", "two", "three"] as const

  return (
    <AuthShell>
      <article className="w-full max-w-3xl animate-rise">
        <p className="inline-flex items-center gap-2 rounded-full border border-border-gray bg-pitch/70 px-3 py-1.5 text-[13px] font-medium text-dim-white">
          <Lock size={14} weight="bold" className="text-raw-white" aria-hidden />
          {t("eyebrow")}
        </p>
        <h1 className="mt-5 font-display text-[clamp(2rem,7vw,3.25rem)] leading-[0.95] text-balance">
          {t("title")}
        </h1>
        {/* An explicit limit of the current release: orange marks what is not done yet. */}
        <p className="mt-6 flex items-start gap-3 rounded-control border border-orange/40 bg-orange/10 px-4 py-3 text-[15px] leading-6 text-raw-white">
          <span aria-hidden className="mt-2 size-2 shrink-0 rounded-full bg-orange" />
          {t("limit")}
        </p>

        <section aria-labelledby="privacy-boundary" className="mt-10">
          <h2 id="privacy-boundary" className="text-lg font-semibold text-raw-white">
            {t("boundary")}
          </h2>
          <dl className="mt-4 grid gap-3 sm:grid-cols-3">
            {accessFacts.map((fact) => (
              <div
                key={fact}
                className="rounded-surface border border-border-gray bg-graphite/60 p-5"
              >
                <dt className="text-sm font-semibold text-raw-white">{t(`facts.${fact}.label`)}</dt>
                <dd className="mt-2 text-[15px] leading-7 text-dim-white">{t(`facts.${fact}.value`)}</dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="mt-10">
          <p className="max-w-[65ch] text-[17px] leading-8 text-dim-white">{t("intro")}</p>
          <ol className="mt-6 flex flex-col gap-2">
            {disclosurePoints.map((point, index) => (
              <li
                key={point}
                className="flex gap-4 rounded-control border border-border-gray px-4 py-4"
              >
                <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full bg-raised font-mono text-xs text-dim-white">
                  {index + 1}
                </span>
                <p className="text-[15px] leading-7 text-raw-white">{t(`points.${point}`)}</p>
              </li>
            ))}
          </ol>
        </section>

        <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-border-gray pt-6">
          <p className="max-w-[48ch] text-sm text-muted">{t("footer")}</p>
          <Link
            href="/"
            className="inline-flex items-center gap-2 text-sm font-medium text-dim-white transition-colors hover:text-acid"
          >
            <ArrowLeft size={14} weight="bold" aria-hidden />
            {t("back")}
          </Link>
        </div>
      </article>
    </AuthShell>
  )
}
