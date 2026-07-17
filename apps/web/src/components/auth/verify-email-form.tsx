"use client"

import { useTranslations } from "next-intl"
import Link from "next/link"
import { useEffect, useRef, useState } from "react"

import { LocaleSwitcher } from "@/components/i18n/locale-switcher"

type Status = "verifying" | "ok" | "invalid" | "service" | "rate" | "missing"

/**
 * Confirms an email verification token (from the link's ?token=) against the
 * BFF on mount. The token itself is the proof, so no session is required.
 */
export function VerifyEmailForm({ token }: { token: string | null }) {
  const t = useTranslations("authUtility.verify")
  const [status, setStatus] = useState<Status>(token ? "verifying" : "missing")
  const [attempt, setAttempt] = useState(0)
  const ran = useRef(-1)

  useEffect(() => {
    if (!token || ran.current === attempt) return
    ran.current = attempt
    ;(async () => {
      try {
        const res = await fetch("/api/auth/email/verify/confirm", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ token }),
        })
        setStatus(
          res.ok
            ? "ok"
            : res.status === 400
              ? "invalid"
              : res.status === 429
                ? "rate"
                : "service",
        )
      } catch {
        setStatus("service")
      }
    })()
  }, [attempt, token])

  const caption =
    status === "ok"
      ? t("verified")
      : status === "verifying"
        ? t("verifying")
        : t("link")

  return (
    <div className="w-full max-w-md border border-border-gray bg-graphite p-7">
      <div className="flex items-start justify-between gap-4">
        <span className="font-display text-3xl tracking-[0.1em]">THRESHOLD</span>
        <LocaleSwitcher />
      </div>
      <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-muted">
        {caption}
      </p>

      <p role="status" aria-live="polite" className="mt-6 text-sm leading-7 text-dim-white">
        {status === "verifying"
          ? t("confirming")
          : status === "ok"
            ? t("success")
            : status === "service"
              ? t("service")
              : status === "rate"
                ? t("rateLimited")
                : t("invalid")}
      </p>

      {status === "service" || status === "rate" ? (
        <button
          type="button"
          onClick={() => {
            setStatus("verifying")
            setAttempt((value) => value + 1)
          }}
          className="mt-5 w-full border border-acid px-4 py-2.5 font-mono text-[11px] uppercase tracking-label text-acid hover:bg-acid hover:text-pitch"
        >
          {t("retry")}
        </button>
      ) : null}

      <Link
        href="/app"
        className="mt-5 block text-center font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid"
      >
        {t("continue")}
      </Link>
    </div>
  )
}
