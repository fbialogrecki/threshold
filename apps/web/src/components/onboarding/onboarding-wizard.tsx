"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import { CITY_OPTIONS, type CanonicalCity } from "@/lib/cities"
import { cn } from "@/lib/cn"
import { onboardingSubmissionSucceeded } from "@/lib/onboarding/plan"

const SCENES = ["techno", "industrial", "hardcore", "ebm", "acid", "rave", "ambient", "experimental"]
const STEPS = ["identity", "city", "frequencies", "access", "done"] as const

export function OnboardingWizard({
  defaultNickname = "",
  callbackUrl = "/app",
}: {
  defaultNickname?: string
  callbackUrl?: string
}) {
  const router = useRouter()
  const t = useTranslations("onboarding")
  const [step, setStep] = useState(0)
  const [nickname, setNickname] = useState(defaultNickname)
  const [city, setCity] = useState<CanonicalCity | null>(null)
  const [scenes, setScenes] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [nicknameInvalid, setNicknameInvalid] = useState(false)
  const [pending, startTransition] = useTransition()

  function toggle<T>(list: T[], value: T): T[] {
    return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
  }

  function finish() {
    startTransition(async () => {
      setError(null)
      setNicknameInvalid(false)
      try {
        const name = nickname.trim().replace(/^@/, "")
        if (name) {
          const profileResponse = await fetch("/api/me/profile", {
            method: "PATCH",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ display_name: name }),
          })
          if (!profileResponse.ok) {
            setError(t("errors.profile"))
            setNicknameInvalid(true)
            return
          }
        }
        const response = await fetch("/api/onboarding", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            city,
            preferredScenes: scenes,
          }),
        })
        if (!onboardingSubmissionSucceeded(response.status)) {
          setError(t("errors.save"))
          return
        }
      } catch {
        setError(t("errors.network"))
        return
      }
      router.push(callbackUrl)
      router.refresh()
    })
  }

  const canNext = step === 0
    ? nickname.trim().length > 0
    : step === 1
      ? city !== null
      : true

  return (
    <div className="border border-border-gray bg-graphite">
      <div className="flex overflow-x-auto border-b border-border-gray">
        {STEPS.map((label, index) => (
          <div
            key={label}
            className={cn(
              "min-w-28 flex-1 border-r border-border-gray px-3 py-3 font-mono text-[11px] uppercase tracking-label last:border-r-0",
              index === step ? "bg-raised text-acid" : index < step ? "text-dim-white" : "text-muted",
            )}
          >
            {index + 1}. {t(`steps.${label}`)}
          </div>
        ))}
      </div>

      <div className="p-6">
        {step === 0 ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-7 text-dim-white">{t("identity.body")}</p>
            <input
              aria-label={t("identity.nickname")}
              value={nickname}
              onChange={(event) => {
                setNickname(event.target.value)
                setNicknameInvalid(false)
              }}
              placeholder="@nightcrawler"
              required
              maxLength={120}
              aria-invalid={nicknameInvalid || undefined}
              aria-describedby={`onboarding-nickname-help${nicknameInvalid ? " onboarding-error" : ""}`}
              className="border border-border-gray bg-pitch p-3 font-mono text-sm text-raw-white placeholder:text-muted focus:border-acid focus:outline-none"
            />
            <p id="onboarding-nickname-help" className="font-mono text-[11px] uppercase tracking-label text-muted">{t("identity.hint")}</p>
          </div>
        ) : null}

        {step === 1 ? (
          <fieldset className="flex flex-col gap-4">
            <legend className="text-sm leading-7 text-dim-white">{t("city.body")}</legend>
            <div className="flex flex-wrap gap-2">
              {CITY_OPTIONS.map((option) => (
                <label
                  key={option.value}
                  className={cn(
                    "cursor-pointer border px-3 py-2 font-mono text-xs uppercase tracking-label has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-acid",
                    city === option.value
                      ? "border-acid text-acid"
                      : "border-border-gray text-dim-white hover:text-raw-white",
                  )}
                >
                  <input
                    type="radio"
                    name="onboarding-city"
                    value={option.value}
                    checked={city === option.value}
                    onChange={() => setCity(option.value)}
                    required
                    className="sr-only"
                  />
                  {t(`cities.${option.value}`)}
                </label>
              ))}
            </div>
          </fieldset>
        ) : null}

        {step === 2 ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-7 text-dim-white">{t("frequencies.body")}</p>
            <div className="flex flex-wrap gap-2">
              {SCENES.map((scene) => (
                <button
                  key={scene}
                  type="button"
                  onClick={() => setScenes((current) => toggle(current, scene))}
                  aria-pressed={scenes.includes(scene)}
                  className={cn("border px-3 py-2 font-mono text-xs uppercase tracking-label", scenes.includes(scene) ? "border-violet text-violet" : "border-border-gray text-dim-white hover:text-raw-white")}
                >
                  #{scene}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-7 text-dim-white">{t("access.body")}</p>
            <p className="font-mono text-[11px] uppercase tracking-label text-muted">{t("access.hint")}</p>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-7 text-dim-white">{t("done.body")}</p>
            <p className="font-mono text-[11px] uppercase tracking-label text-muted">{t("done.hint")}</p>
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-border-gray p-4">
        {error ? <p id="onboarding-error" role="alert" className="font-mono text-[11px] uppercase tracking-label text-error">{error}</p> : null}
        <Button variant="ghost" onClick={() => setStep((value) => Math.max(0, value - 1))} disabled={step === 0 || pending}>{t("back")}</Button>
        {step < STEPS.length - 1 ? (
          <Button variant="primary" onClick={() => setStep((value) => value + 1)} disabled={!canNext || pending}>{t("next")}</Button>
        ) : (
          <Button variant="primary" onClick={finish} disabled={pending}>{pending ? t("saving") : t("finish")}</Button>
        )}
      </div>
    </div>
  )
}
