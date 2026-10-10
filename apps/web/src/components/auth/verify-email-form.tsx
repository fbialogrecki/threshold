"use client"

import { CheckCircle, WarningCircle } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useEffect, useRef, useState } from "react"

import { AuthPanel } from "@/components/auth/auth-panel"
import { Button, ButtonLink } from "@/components/ui/button"
import { Spinner } from "@/components/ui/field"
import { cn } from "@/lib/cn"

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

  const title =
    status === "ok"
      ? t("verified")
      : status === "verifying"
        ? t("verifying")
        : t("link")
  const retryable = status === "service" || status === "rate"

  return (
    <AuthPanel title={title}>
      <div
        role="status"
        aria-live="polite"
        className={cn(
          "mt-6 flex gap-3 rounded-control p-4",
          status === "ok" ? "bg-acid/5" : status === "verifying" ? "bg-raised" : "bg-orange/10",
        )}
      >
        <span
          className={cn(
            "mt-1",
            status === "ok" ? "text-acid" : status === "verifying" ? "text-dim-white" : "text-orange",
          )}
        >
          {status === "verifying" ? (
            <Spinner />
          ) : status === "ok" ? (
            <CheckCircle size={22} weight="fill" aria-hidden />
          ) : (
            <WarningCircle size={22} aria-hidden />
          )}
        </span>
        <p className="text-[15px] leading-7 text-dim-white">
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
      </div>

      <div className="mt-6 flex flex-col gap-3">
        {retryable ? (
          <Button
            size="lg"
            className="w-full"
            onClick={() => {
              setStatus("verifying")
              setAttempt((value) => value + 1)
            }}
          >
            {t("retry")}
          </Button>
        ) : null}
        <ButtonLink
          href="/app"
          size="lg"
          variant={status === "ok" ? "primary" : "ghost"}
          className="w-full"
        >
          {t("continue")}
        </ButtonLink>
      </div>
    </AuthPanel>
  )
}
