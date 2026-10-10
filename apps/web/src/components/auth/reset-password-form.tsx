"use client"

import { CheckCircle, EnvelopeSimple } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import Link from "next/link"
import { useState, type ReactNode } from "react"

import { AuthPanel } from "@/components/auth/auth-panel"
import { PasswordField } from "@/components/auth/password-field"
import { Button } from "@/components/ui/button"
import { Field, FormAlert, inputClass, Spinner } from "@/components/ui/field"
import { MAX_PASSWORD, MIN_PASSWORD, passwordPolicyError } from "@/lib/validation"

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

function BackToLogin() {
  const t = useTranslations("authUtility")
  return (
    <Link
      href="/login"
      className="mt-6 block text-center text-sm text-muted transition-colors hover:text-acid"
    >
      {t("backToLogin")}
    </Link>
  )
}

function Done({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div role="status" aria-live="polite" className="mt-6 flex gap-3 rounded-control bg-acid/5 p-4">
      <span className="text-acid">{icon}</span>
      <p className="text-[15px] leading-7 text-dim-white">{children}</p>
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
      <AuthPanel title={t("checkInbox")}>
        <Done icon={<EnvelopeSimple size={22} aria-hidden />}>{t("sent")}</Done>
        <BackToLogin />
      </AuthPanel>
    )
  }

  return (
    <AuthPanel title={t("title")}>
      <form onSubmit={onSubmit} className="mt-7 flex flex-col gap-5">
        <Field htmlFor="reset-email" label={t("email")}>
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
            className={inputClass}
          />
        </Field>
        {error ? <FormAlert id="reset-request-error">{error}</FormAlert> : null}
        <Button
          type="submit"
          variant="primary"
          size="lg"
          disabled={loading || !email.trim()}
          className="w-full"
        >
          {loading ? (
            <>
              <Spinner />
              {t("working")}
            </>
          ) : (
            t("send")
          )}
        </Button>
      </form>
      <BackToLogin />
    </AuthPanel>
  )
}

function ConfirmForm({ token }: { token: string }) {
  const t = useTranslations("authUtility.reset")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)
  const [passwordInvalid, setPasswordInvalid] = useState(false)

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
      <AuthPanel title={t("updated")}>
        <Done icon={<CheckCircle size={22} weight="fill" aria-hidden />}>{t("updatedBody")}</Done>
        <BackToLogin />
      </AuthPanel>
    )
  }

  return (
    <AuthPanel title={t("newTitle")}>
      <form onSubmit={onSubmit} className="mt-7 flex flex-col gap-5">
        <PasswordField
          id="reset-password"
          label={t("newPassword")}
          value={password}
          onChange={(value) => {
            setPassword(value)
            setPasswordInvalid(false)
          }}
          autoComplete="new-password"
          showStrength
          help={t("passwordHelp")}
          required
          minLength={MIN_PASSWORD}
          maxLength={MAX_PASSWORD}
          ariaInvalid={passwordInvalid}
          errorId={passwordInvalid ? "reset-password-error" : undefined}
        />
        {error ? <FormAlert id="reset-password-error">{error}</FormAlert> : null}
        <Button type="submit" variant="primary" size="lg" disabled={loading} className="w-full">
          {loading ? (
            <>
              <Spinner />
              {t("working")}
            </>
          ) : (
            t("change")
          )}
        </Button>
      </form>
      <BackToLogin />
    </AuthPanel>
  )
}
