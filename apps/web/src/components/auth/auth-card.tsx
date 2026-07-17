"use client"

import { Eye, EyeSlash } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import Link from "next/link"
import { useState } from "react"

import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { useAuthCard } from "@/components/auth/use-auth-card"
import { cn } from "@/lib/cn"
import {
  MAX_PASSWORD,
  MIN_PASSWORD,
  passwordStrength,
  type PasswordStrength,
} from "@/lib/validation"

type Mode = "login" | "register"

export function AuthCard({
  initialMode = "login",
  callbackUrl = "/app",
}: {
  initialMode?: Mode
  callbackUrl?: string
}) {
  const t = useTranslations("authFlow")
  const {
    isRegister,
    username,
    setUsername,
    email,
    setEmail,
    password,
    setPassword,
    error,
    errorField,
    loading,
    clearFieldError,
    switchMode,
    onSubmit,
  } = useAuthCard({ initialMode, callbackUrl })

  return (
    <div className="w-full max-w-md border border-border-gray bg-graphite">
      <div className="flex border-b border-border-gray">
        <ModeTab
          active={!isRegister}
          label={t("login")}
          onClick={() => switchMode("login")}
        />
        <ModeTab
          active={isRegister}
          label={t("createAccount")}
          onClick={() => switchMode("register")}
        />
      </div>

      <div className="p-7">
        <div className="flex items-start justify-between gap-4">
          <span className="font-display text-3xl tracking-[0.1em]">THRESHOLD</span>
          <LocaleSwitcher />
        </div>
        <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-muted">
          {isRegister ? t("registrationOpen") : t("loginCaption")}
        </p>

        <form onSubmit={onSubmit} className="mt-7 flex flex-col gap-4">
          <Field
            id="auth-username"
            label={isRegister ? t("nickname") : t("identifier")}
            hint={isRegister ? t("nicknameHint") : undefined}
            help={isRegister ? t("usernameHelp") : undefined}
            value={username}
            onChange={(value) => {
              setUsername(value)
              clearFieldError("username")
            }}
            placeholder="nightcrawler"
            autoComplete="username"
            required
            maxLength={isRegister ? 30 : 320}
            pattern={isRegister ? "[A-Za-z0-9_.-]{3,30}" : undefined}
            ariaInvalid={errorField === "username" || errorField === "credentials"}
            errorId={
              error && (errorField === "username" || errorField === "credentials")
                ? "auth-error"
                : undefined
            }
          />

          {isRegister ? (
            <Field
              id="auth-email"
              label={t("email")}
              value={email}
              onChange={(value) => {
                setEmail(value)
                clearFieldError("email")
              }}
              type="email"
              placeholder="you@domain.xyz"
              autoComplete="email"
              required
              maxLength={320}
              ariaInvalid={errorField === "email"}
              errorId={error && errorField === "email" ? "auth-error" : undefined}
            />
          ) : null}

          <PasswordField
            id="auth-password"
            value={password}
            onChange={(value) => {
              setPassword(value)
              clearFieldError("password")
            }}
            autoComplete={isRegister ? "new-password" : "current-password"}
            showStrength={isRegister}
            label={t("password")}
            revealHint={t("revealHint")}
            revealLabel={t("revealLabel")}
            help={isRegister ? t("passwordHelp") : undefined}
            required
            minLength={isRegister ? MIN_PASSWORD : undefined}
            maxLength={MAX_PASSWORD}
            ariaInvalid={errorField === "password" || errorField === "credentials"}
            errorId={
              error && (errorField === "password" || errorField === "credentials")
                ? "auth-error"
                : undefined
            }
          />

          {error ? (
            <p
              id="auth-error"
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
            {loading
              ? t("working")
              : isRegister
                ? t("createAccountAction")
                : t("loginAction")}
          </button>
        </form>

        {!isRegister ? (
          <div className="mt-4 text-center">
            <Link
              href="/reset-password"
              className="font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid"
            >
              {t("forgotPassword")}
            </Link>
          </div>
        ) : null}

        <div className="mt-5 border-t border-border-gray pt-4 text-center">
          {isRegister ? (
            <button
              type="button"
              onClick={() => switchMode("login")}
              className="font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid"
            >
              {t("hasAccount")}{" "}
              <span className="text-acid">{t("login")}</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => switchMode("register")}
              className="font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid"
            >
              {t("noAccount")}{" "}
              <span className="text-acid">{t("createOne")}</span>
            </button>
          )}
        </div>

        <Link
          href="/"
          className="mt-4 block text-center font-mono text-[11px] uppercase tracking-label text-muted hover:text-raw-white"
        >
          {t("back")}
        </Link>
      </div>
    </div>
  )
}

function ModeTab({
  active,
  label,
  onClick,
}: {
  active: boolean
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "flex-1 border-r border-border-gray px-4 py-3 font-mono text-[11px] uppercase tracking-label last:border-r-0 transition-colors",
        active ? "bg-raised text-acid" : "text-muted hover:text-raw-white",
      )}
    >
      {label}
    </button>
  )
}

function PasswordField({
  id,
  value,
  onChange,
  autoComplete,
  showStrength,
  label,
  revealHint,
  revealLabel,
  help,
  required,
  minLength,
  maxLength,
  ariaInvalid,
  errorId,
}: {
  id: string
  value: string
  onChange: (value: string) => void
  autoComplete?: string
  showStrength?: boolean
  label: string
  revealHint: string
  revealLabel: string
  help?: string
  required?: boolean
  minLength?: number
  maxLength?: number
  ariaInvalid?: boolean
  errorId?: string
}) {
  const t = useTranslations("authFlow.strength")
  const [reveal, setReveal] = useState(false)
  const strength = showStrength ? passwordStrength(value) : null
  const helpId = help ? `${id}-help` : undefined

  return (
    <label htmlFor={id} className="flex flex-col gap-1.5">
      <span className="flex items-center justify-between font-mono text-[11px] uppercase tracking-label text-muted">
        {label}
        <span className="text-muted">{revealHint}</span>
      </span>
      <div className="relative">
        <input
          id={id}
          type={reveal ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="••••••••"
          autoComplete={autoComplete}
          required={required}
          minLength={minLength}
          maxLength={maxLength}
          aria-invalid={ariaInvalid || undefined}
          aria-describedby={[helpId, errorId].filter(Boolean).join(" ") || undefined}
          className="w-full border border-border-gray bg-pitch px-3 py-2.5 pr-11 font-mono text-sm text-raw-white placeholder:text-muted focus:border-acid focus:outline-none"
        />
        <button
          type="button"
          aria-label={revealLabel}
          aria-pressed={reveal}
          onPointerDown={(event) => {
            event.preventDefault()
            setReveal(true)
          }}
          onPointerUp={() => setReveal(false)}
          onPointerLeave={() => setReveal(false)}
          onPointerCancel={() => setReveal(false)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault()
              setReveal(true)
            }
          }}
          onKeyUp={(event) => {
            if (event.key === "Enter" || event.key === " ") setReveal(false)
          }}
          onBlur={() => setReveal(false)}
          className="absolute inset-y-0 right-0 flex items-center px-3 text-muted transition-colors hover:text-acid focus:text-acid focus:outline-none"
        >
          {reveal
            ? <Eye size={16} weight="bold" aria-hidden />
            : <EyeSlash size={16} weight="bold" aria-hidden />}
        </button>
      </div>
      {help ? (
        <span id={helpId} className="text-xs leading-5 text-muted">
          {help}
        </span>
      ) : null}
      {strength && value ? (
        <StrengthMeter
          strength={strength}
          label={t("label")}
          value={t(
            strength.score === 1
              ? "tooShort"
              : strength.score === 2
                ? "fair"
                : strength.score === 3
                  ? "good"
                  : "strong",
          )}
        />
      ) : null}
    </label>
  )
}

function StrengthMeter({
  strength,
  label,
  value,
}: {
  strength: PasswordStrength
  label: string
  value: string
}) {
  const fill =
    strength.score <= 1 ? "#ff5c5c" : strength.score === 2 ? "#e6b800" : "#c6ff00"
  return (
    <div className="mt-1 flex flex-col gap-1">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="h-1 flex-1 transition-colors"
            style={{ backgroundColor: i < strength.score ? fill : "#2a2a2a" }}
          />
        ))}
      </div>
      <span className="font-mono text-[11px] uppercase tracking-label text-muted">
        {label}: <span style={{ color: fill }}>{value}</span>
      </span>
    </div>
  )
}

function Field({
  id,
  label,
  hint,
  help,
  value,
  onChange,
  type = "text",
  placeholder,
  autoComplete,
  required,
  maxLength,
  pattern,
  ariaInvalid,
  errorId,
}: {
  id: string
  label: string
  hint?: string
  help?: string
  value: string
  onChange: (value: string) => void
  type?: string
  placeholder?: string
  autoComplete?: string
  required?: boolean
  maxLength?: number
  pattern?: string
  ariaInvalid?: boolean
  errorId?: string
}) {
  const helpId = help ? `${id}-help` : undefined
  return (
    <label htmlFor={id} className="flex flex-col gap-1.5">
      <span className="flex items-center justify-between font-mono text-[11px] uppercase tracking-label text-muted">
        {label}
        {hint ? <span className="text-border-gray">{hint}</span> : null}
      </span>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        maxLength={maxLength}
        pattern={pattern}
        aria-invalid={ariaInvalid || undefined}
        aria-describedby={[helpId, errorId].filter(Boolean).join(" ") || undefined}
        className="border border-border-gray bg-pitch px-3 py-2.5 font-mono text-sm text-raw-white placeholder:text-muted focus:border-acid focus:outline-none"
      />
      {help ? (
        <span id={helpId} className="text-xs leading-5 text-muted">
          {help}
        </span>
      ) : null}
    </label>
  )
}
