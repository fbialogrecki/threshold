"use client"

import { useTranslations } from "next-intl"
import Link from "next/link"
import { useState } from "react"

import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import {
  MAX_PASSWORD,
  MIN_PASSWORD,
  passwordPolicyError,
  passwordStrength,
} from "@/lib/validation"

/**
 * Two-phase password reset UI driven by the BFF.
 * - No token in the URL: request a reset link (always generic success).
 * - Token present: set a new password, then bounce to login.
 *
 * The reset token is delivered out-of-band (email in prod; server logs in dev);
 * it is never surfaced by the request endpoint to the browser.
 */
export function ResetPasswordForm({ token }: { token: string | null }) {
  return token ? <ConfirmForm token={token} /> : <RequestForm />
}

function Shell({
  caption,
  children,
}: {
  caption: string
  children: React.ReactNode
}) {
  const t = useTranslations("authUtility")
  return (
    <div className="w-full max-w-md border border-border-gray bg-graphite p-7">
      <div className="flex items-start justify-between gap-4">
        <span className="font-display text-3xl tracking-[0.1em]">THRESHOLD</span>
        <LocaleSwitcher />
      </div>
      <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-muted">
        {caption}
      </p>
      {children}
      <Link
        href="/login"
        className="mt-5 block text-center font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid"
      >
        {t("backToLogin")}
      </Link>
    </div>
  )
}

function RequestForm() {
  const t = useTranslations("authUtility.reset")
  const [email, setEmail] = useState("")
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const response = await fetch("/api/auth/password/reset/request", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      })
      if (!response.ok) {
        setError(response.status === 429 ? t("rateLimited") : t("unavailable"))
        return
      }
      setDone(true)
    } catch {
      setError(t("network"))
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <Shell caption={t("checkInbox")}>
        <p role="status" aria-live="polite" className="mt-6 text-sm leading-7 text-dim-white">
          {t("sent")}
        </p>
      </Shell>
    )
  }

  return (
    <Shell caption={t("title")}>
      <form onSubmit={onSubmit} className="mt-7 flex flex-col gap-4">
        <label htmlFor="reset-email" className="flex flex-col gap-1.5">
          <span className="font-mono text-[11px] uppercase tracking-label text-muted">
            {t("email")}
          </span>
          <input
            id="reset-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@domain.xyz"
            autoComplete="email"
            required
            maxLength={320}
            aria-describedby={error ? "reset-request-error" : undefined}
            className="border border-border-gray bg-pitch px-3 py-2.5 font-mono text-sm text-raw-white placeholder:text-muted focus:border-acid focus:outline-none"
          />
        </label>
        {error ? (
          <p id="reset-request-error" role="alert" className="font-mono text-[11px] uppercase tracking-label text-error">
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={loading || !email.trim()}
          className="mt-1 border border-acid bg-acid px-4 py-3 font-mono text-xs uppercase tracking-cta text-pitch transition-colors hover:bg-[#d4ff3a] disabled:opacity-50"
        >
          {loading ? t("working") : t("send")}
        </button>
      </form>
    </Shell>
  )
}

function ConfirmForm({ token }: { token: string }) {
  const t = useTranslations("authUtility.reset")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)
  const [passwordInvalid, setPasswordInvalid] = useState(false)
  const strength = passwordStrength(password)
  const strengthLabel = t(
    strength.score <= 1
      ? "strengthValues.1"
      : strength.score === 2
        ? "strengthValues.2"
        : strength.score === 3
          ? "strengthValues.3"
          : "strengthValues.4",
  )

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    setError(null)
    setPasswordInvalid(false)
    const policyError = passwordPolicyError(password)
    if (policyError) {
      setError(t(`policyErrors.${policyError}`))
      setPasswordInvalid(true)
      return
    }
    setLoading(true)
    try {
      const res = await fetch("/api/auth/password/reset/confirm", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token, password }),
      })
      if (!res.ok) {
        setError(
          res.status === 400
            ? t("invalid")
            : res.status === 429
              ? t("rateLimited")
              : t("unavailable"),
        )
        return
      }
      setDone(true)
    } catch {
      setError(t("network"))
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <Shell caption={t("updated")}>
        <p role="status" aria-live="polite" className="mt-6 text-sm leading-7 text-dim-white">
          {t("updatedBody")}
        </p>
      </Shell>
    )
  }

  return (
    <Shell caption={t("newTitle")}>
      <form onSubmit={onSubmit} className="mt-7 flex flex-col gap-4">
        <label htmlFor="reset-password" className="flex flex-col gap-1.5">
          <span className="font-mono text-[11px] uppercase tracking-label text-muted">
            {t("newPassword")}
          </span>
          <input
            id="reset-password"
            type="password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value)
              setPasswordInvalid(false)
            }}
            placeholder="••••••••"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            maxLength={MAX_PASSWORD}
            aria-invalid={passwordInvalid || undefined}
            aria-describedby={`reset-password-help${passwordInvalid ? " reset-password-error" : ""}`}
            className="border border-border-gray bg-pitch px-3 py-2.5 font-mono text-sm text-raw-white placeholder:text-muted focus:border-acid focus:outline-none"
          />
          <span id="reset-password-help" className="text-xs leading-5 text-muted">
            {t("passwordHelp")}
          </span>
          {password ? (
            <span className="font-mono text-[11px] uppercase tracking-label text-muted">
              {t("strength")}: {strengthLabel}
            </span>
          ) : null}
        </label>

        {error ? (
          <p
            id="reset-password-error"
            role="alert"
            className="border border-error/60 bg-[#1a0606] px-3 py-2 font-mono text-[11px] uppercase tracking-label text-error"
          >
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={loading}
          className="mt-1 border border-acid bg-acid px-4 py-3 font-mono text-xs uppercase tracking-cta text-pitch transition-colors hover:bg-[#d4ff3a] disabled:opacity-50"
        >
          {loading ? t("working") : t("change")}
        </button>
      </form>
    </Shell>
  )
}
