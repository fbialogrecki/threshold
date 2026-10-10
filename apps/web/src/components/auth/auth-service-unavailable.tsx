"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useTransition } from "react"

import { Button } from "@/components/ui/button"

export function AuthServiceUnavailable() {
  const t = useTranslations("authServiceUnavailable")
  const router = useRouter()
  const [pending, startTransition] = useTransition()

  return (
    <main className="flex min-h-screen items-center justify-center bg-pitch px-6 text-raw-white">
      <section
        role="alert"
        className="w-full max-w-md rounded-surface border border-orange/60 bg-graphite p-6 sm:p-8"
      >
        <p className="flex items-center gap-2 text-sm font-medium text-orange">
          <span className="size-2 rounded-full bg-orange" aria-hidden />
          {t("eyebrow")}
        </p>
        <h1 className="mt-4 font-display text-3xl leading-none">{t("title")}</h1>
        <p className="mt-4 text-[15px] leading-7 text-dim-white">{t("body")}</p>
        <Button
          size="lg"
          disabled={pending}
          onClick={() => startTransition(() => router.refresh())}
          className="mt-6 w-full"
        >
          {pending ? t("retrying") : t("retry")}
        </Button>
      </section>
    </main>
  )
}
