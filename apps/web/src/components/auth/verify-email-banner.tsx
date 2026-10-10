"use client"

import { useTranslations } from "next-intl"
import { useState } from "react"

/**
 * Shown inside the app shell while the signed-in user's email is unverified.
 * Lets them trigger a resend; the link itself is delivered by email (prod) or
 * read from server logs (dev) and never returned to the browser.
 */
export function VerifyEmailBanner() {
  const t = useTranslations("authUtility.banner")
  const [sent, setSent] = useState(false)
  const [pending, setPending] = useState(false)
  const [failed, setFailed] = useState(false)

  async function resend() {
    setPending(true)
    setFailed(false)
    try {
      const response = await fetch("/api/auth/email/verify/request", {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "same-origin",
      })
      if (!response.ok) throw new Error("verification request failed")
      setSent(true)
    } catch {
      setFailed(true)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-orange/40 bg-orange/10 px-4 py-2.5">
      <p className="flex items-center gap-2 text-sm text-raw-white">
        <span className="size-2 shrink-0 rounded-full bg-orange" aria-hidden />
        {failed ? t("error") : t("body")}
      </p>
      <button
        type="button"
        onClick={resend}
        disabled={pending || sent}
        className="rounded-control border border-border-gray px-3 py-1 text-sm font-semibold text-acid transition-[border-color,scale] duration-150 ease-press hover:border-acid active:scale-[0.97] disabled:opacity-60"
      >
        {sent ? t("sent") : pending ? "…" : t("resend")}
      </button>
    </div>
  )
}
