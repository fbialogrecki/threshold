"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useTransition } from "react"

export function AuthServiceUnavailable() {
  const t = useTranslations("authServiceUnavailable")
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  return (
    <main className="flex min-h-screen items-center justify-center bg-pitch px-6 text-raw-white">
      <section
        role="alert"
        className="w-full max-w-md border border-orange bg-graphite p-6"
      >
        <p className="font-mono text-[11px] uppercase tracking-label text-orange">
          {t("eyebrow")}
        </p>
        <h1 className="mt-3 font-display text-3xl tracking-wide">{t("title")}</h1>
        <p className="mt-3 text-sm leading-7 text-dim-white">{t("body")}</p>
        <button
          type="button"
          disabled={pending}
          onClick={() => startTransition(() => router.refresh())}
          className="mt-5 border border-acid px-4 py-2.5 font-mono text-xs uppercase tracking-label text-acid hover:bg-acid hover:text-pitch disabled:opacity-50"
        >
          {pending ? t("retrying") : t("retry")}
        </button>
      </section>
    </main>
  )
}
