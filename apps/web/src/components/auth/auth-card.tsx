"use client"

import { useTranslations } from "next-intl"
import Link from "next/link"

import { authSurfaceClass } from "@/components/auth/auth-panel"
import { PasswordField } from "@/components/auth/password-field"
import { useAuthCard } from "@/components/auth/use-auth-card"
import { Button } from "@/components/ui/button"
import { Field, FormAlert, inputClass, Spinner } from "@/components/ui/field"
import { cn } from "@/lib/cn"
import { MAX_PASSWORD, MIN_PASSWORD, USERNAME_PATTERN } from "@/lib/validation"

type Mode = "login" | "register"

const JOURNEY = ["account", "setup", "feed"] as const

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
  const credentialsError = errorField === "username" || errorField === "credentials"

  return (
    <div className="grid w-full max-w-5xl items-center gap-8 lg:grid-cols-[1fr_minmax(0,28rem)] lg:gap-x-16 lg:gap-y-10">
      <div className="@container animate-rise lg:self-end">
        <p className="inline-flex items-center gap-2 rounded-full border border-border-gray bg-pitch/70 px-3 py-1.5 text-[13px] font-medium text-dim-white">
          <span className="size-1.5 rounded-full bg-acid" aria-hidden />
          {isRegister ? t("registrationOpen") : t("loginCaption")}
        </p>
        <h1 className="mt-5 font-display text-[min(13cqi,4.5rem)] leading-[0.9] tracking-[0.005em]">
          {isRegister ? t("registerHeading") : t("loginHeading")}
        </h1>
        <p className="mt-4 max-w-[42ch] text-pretty text-[17px] leading-7 text-dim-white">
          {isRegister ? t("registrationSteps") : t("loginLede")}
        </p>
      </div>

      <div
        className={cn(
          "animate-rise p-5 [animation-delay:80ms] sm:p-7 lg:col-start-2 lg:row-span-2 lg:row-start-1",
          authSurfaceClass,
        )}
      >
        <div className="relative grid grid-cols-2 rounded-control border border-border-gray bg-pitch p-1">
          <span
            aria-hidden
            className={cn(
              "absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-[0.5rem] bg-raised transition-transform duration-300 ease-out-expo",
              isRegister && "translate-x-full",
            )}
          />
          <ModeTab active={!isRegister} label={t("login")} onClick={() => switchMode("login")} />
          <ModeTab
            active={isRegister}
            label={t("createAccount")}
            onClick={() => switchMode("register")}
          />
        </div>

        <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-5">
          <Field
            htmlFor="auth-username"
            label={isRegister ? t("nickname") : t("identifier")}
            hint={isRegister ? t("nicknameHint") : undefined}
            help={isRegister ? t("usernameHelp") : undefined}
            helpId="auth-username-help"
          >
            <input
              id="auth-username"
              value={username}
              onChange={(event) => {
                setUsername(event.target.value)
                clearFieldError("username")
              }}
              placeholder="nightcrawler"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              maxLength={isRegister ? 30 : 320}
              pattern={isRegister ? USERNAME_PATTERN : undefined}
              aria-invalid={credentialsError || undefined}
              aria-describedby={
                [
                  isRegister ? "auth-username-help" : null,
                  error && credentialsError ? "auth-error" : null,
                ]
                  .filter(Boolean)
                  .join(" ") || undefined
              }
              className={inputClass}
            />
          </Field>

          {isRegister ? (
            <Field htmlFor="auth-email" label={t("email")}>
              <input
                id="auth-email"
                type="email"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value)
                  clearFieldError("email")
                }}
                placeholder="you@domain.xyz"
                autoComplete="email"
                required
                maxLength={320}
                aria-invalid={errorField === "email" || undefined}
                aria-describedby={error && errorField === "email" ? "auth-error" : undefined}
                className={inputClass}
              />
            </Field>
          ) : null}

          <PasswordField
            id="auth-password"
            label={t("password")}
            value={password}
            onChange={(value) => {
              setPassword(value)
              clearFieldError("password")
            }}
            autoComplete={isRegister ? "new-password" : "current-password"}
            showStrength={isRegister}
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

          {error ? <FormAlert id="auth-error">{error}</FormAlert> : null}

          <Button type="submit" variant="primary" size="lg" disabled={loading} className="w-full">
            {loading ? (
              <>
                <Spinner />
                {t("working")}
              </>
            ) : isRegister ? (
              t("createAccountAction")
            ) : (
              t("loginAction")
            )}
          </Button>
        </form>

        <div className="mt-6 flex flex-col items-center gap-3 border-t border-border-gray pt-5 text-sm">
          {isRegister ? null : (
            <Link href="/reset-password" className="text-dim-white transition-colors hover:text-acid">
              {t("forgotPassword")}
            </Link>
          )}
          <button
            type="button"
            onClick={() => switchMode(isRegister ? "login" : "register")}
            className="text-muted transition-colors hover:text-raw-white"
          >
            {isRegister ? t("hasAccount") : t("noAccount")}{" "}
            <span className="font-semibold text-acid">
              {isRegister ? t("login") : t("createOne")}
            </span>
          </button>
          <Link href="/" className="text-muted transition-colors hover:text-raw-white">
            {t("back")}
          </Link>
        </div>
      </div>

      {isRegister ? (
        <section aria-labelledby="auth-journey" className="animate-rise [animation-delay:160ms] lg:self-start">
          <h2 id="auth-journey" className="text-sm font-semibold text-raw-white">
            {t("journey.title")}
          </h2>
          <ol className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            {JOURNEY.map((step, index) => (
              <li
                key={step}
                aria-current={index === 0 ? "step" : undefined}
                className={cn(
                  "rounded-control border p-4",
                  index === 0 ? "border-acid/40 bg-acid/5" : "border-border-gray",
                )}
              >
                <span
                  className={cn(
                    "grid size-7 place-items-center rounded-full font-mono text-xs font-semibold",
                    index === 0 ? "bg-acid text-pitch" : "bg-raised text-dim-white",
                  )}
                  aria-hidden
                >
                  {index + 1}
                </span>
                <p className="mt-3 font-semibold">{t(`journey.${step}.title`)}</p>
                <p className="mt-1 text-sm leading-6 text-dim-white">{t(`journey.${step}.body`)}</p>
              </li>
            ))}
          </ol>
          <p className="mt-4 max-w-[60ch] text-[13px] leading-5 text-muted">{t("journey.verify")}</p>
        </section>
      ) : null}
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
        "relative rounded-[0.5rem] px-3 py-2.5 text-sm font-semibold transition-colors",
        active ? "text-raw-white" : "text-muted hover:text-raw-white",
      )}
    >
      {label}
    </button>
  )
}
