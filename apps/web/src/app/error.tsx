"use client"

import { useTranslations } from "next-intl"
import Link from "next/link"

import { authSurfaceClass } from "@/components/auth/auth-panel"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"

/**
 * Root error boundary. Server error details never reach the browser in
 * production, so only the digest is shown, as a reference for server logs.
 */
export default function ErrorPage({
  error,
  retry,
}: {
  error: Error & { digest?: string }
  retry: () => void
}) {
  const t = useTranslations("errorPages")
  return (
    <main className="flex min-h-svh items-center justify-center bg-pitch px-5 py-12 text-raw-white">
      <section role="alert" className={cn("w-full max-w-md p-6 sm:p-8", authSurfaceClass)}>
        <p className="flex items-center gap-2 text-sm font-medium text-orange">
          <span aria-hidden className="size-2 rounded-full bg-orange" />
          {t("errorEyebrow")}
        </p>
        <h1 className="mt-4 font-display text-3xl leading-none">{t("errorTitle")}</h1>
        <p className="mt-3 text-[15px] leading-7 text-dim-white">{t("errorBody")}</p>
        {error.digest ? (
          <p className="mt-4 text-xs text-muted">
            {t("reference")} <span className="font-mono">{error.digest}</span>
          </p>
        ) : null}
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Button type="button" variant="primary" size="lg" onClick={() => retry()}>
            {t("retry")}
          </Button>
          <Link
            href="/"
            className="inline-flex min-h-12 items-center justify-center rounded-control px-4 text-[15px] text-dim-white transition-colors hover:text-raw-white"
          >
            {t("home")}
          </Link>
        </div>
      </section>
    </main>
  )
}
