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
    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-orange/50 bg-[#1a1206] px-4 py-2">
      <p className="font-mono text-[11px] uppercase tracking-label text-orange">
        {failed ? t("error") : t("body")}
      </p>
      <button
        type="button"
        onClick={resend}
        disabled={pending || sent}
        className="font-mono text-[11px] uppercase tracking-label text-acid hover:underline disabled:opacity-50"
      >
        {sent ? t("sent") : pending ? "…" : t("resend")}
      </button>
    </div>
  )
}
