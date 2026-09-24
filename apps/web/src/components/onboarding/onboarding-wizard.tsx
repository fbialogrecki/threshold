"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useRef, useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import { CITY_OPTIONS, type CanonicalCity } from "@/lib/cities"
import { cn } from "@/lib/cn"
import { saveSetup, validPages } from "@/lib/onboarding/setup"
import { USERNAME_PATTERN } from "@/lib/validation"

const SCENES = ["techno", "industrial", "hardcore", "ebm", "acid", "rave", "ambient", "experimental"]
const STEPS = ["identity", "city", "frequencies", "artist", "pages", "access", "done"] as const
type PageDraft = { display_name: string; slug: string; page_type: "club" | "collective" | "project" | "festival"; about: string }

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
  const [isArtist, setIsArtist] = useState(false)
  const [role, setRole] = useState("DJ")
  const [location, setLocation] = useState("")
  const [artistUrl, setArtistUrl] = useState("")
  const [pages, setPages] = useState<PageDraft[]>([])
  const createdSlugs = useRef(new Set<string>())
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
      if (!city) return
      const result = await saveSetup({
        username: nickname,
        city,
        scenes,
        artist: isArtist ? { role, location, url: artistUrl } : null,
        pages,
      }, createdSlugs.current)
      if (!result.ok) {
        setError(t(`errors.${result.error}`))
        setStep(STEPS.indexOf(result.step))
        setNicknameInvalid(result.step === "identity")
        return
      }
      router.push(callbackUrl)
      router.refresh()
    })
  }

  const canNext = step === 0
    ? new RegExp(`^${USERNAME_PATTERN}$`).test(nickname.trim())
    : step === 1
      ? city !== null
      : step === 3
        ? !isArtist || (role.trim().length > 0 && (!artistUrl.trim() || /^https?:\/\//.test(artistUrl.trim())))
        : step === 4
          ? validPages(pages)
      : true

  return (
    <div className="border border-border-gray">
      <div className="flex overflow-x-auto border-b border-border-gray">
        {STEPS.map((label, index) => (
          <div
            key={label}
            className={cn(
              "min-w-28 flex-1 border-r border-border-gray px-3 py-3 font-mono text-[11px] uppercase tracking-label last:border-r-0",
              index === step ? "text-acid" : index < step ? "text-dim-white" : "text-muted",
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
              placeholder="nightcrawler"
              required
              maxLength={30}
              pattern={USERNAME_PATTERN}
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
            <p className="text-sm leading-7 text-dim-white">{t("artist.body")}</p>
            <label className="flex items-center gap-3 text-sm">
              <input type="checkbox" checked={isArtist} onChange={(event) => setIsArtist(event.target.checked)} className="accent-acid" />
              {t("artist.enable")}
            </label>
            {isArtist ? (
              <div className="flex flex-col gap-4 border-l border-border-gray pl-4">
                <label className="flex flex-col gap-2 text-sm">{t("artist.role")}
                  <input value={role} onChange={(event) => setRole(event.target.value)} maxLength={120} className="border border-border-gray bg-pitch p-3 text-raw-white focus:border-acid focus:outline-none" />
                </label>
                <label className="flex flex-col gap-2 text-sm">{t("artist.location")}
                  <input value={location} onChange={(event) => setLocation(event.target.value)} maxLength={120} className="border border-border-gray bg-pitch p-3 text-raw-white focus:border-acid focus:outline-none" />
                </label>
                <label className="flex flex-col gap-2 text-sm">{t("artist.url")}
                  <input type="url" value={artistUrl} onChange={(event) => setArtistUrl(event.target.value)} placeholder="https://" className="border border-border-gray bg-pitch p-3 text-raw-white focus:border-acid focus:outline-none" />
                </label>
              </div>
            ) : null}
            <p className="text-xs text-muted">{t("artist.hint")}</p>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-7 text-dim-white">{t("pages.body")}</p>
            {pages.map((page, index) => (
              <fieldset key={index} className="flex flex-col gap-3 border-l border-border-gray pl-4">
                <legend className="font-mono text-xs uppercase tracking-label text-muted">{t("pages.entry", { number: index + 1 })}</legend>
                <label className="flex flex-col gap-2 text-sm">{t("pages.name")}
                  <input value={page.display_name} onChange={(event) => setPages((current) => current.map((item, i) => i === index ? { ...item, display_name: event.target.value } : item))} maxLength={160} className="border border-border-gray bg-pitch p-3 text-raw-white focus:border-acid focus:outline-none" />
                </label>
                <label className="flex flex-col gap-2 text-sm">{t("pages.slug")}
                  <input value={page.slug} onChange={(event) => setPages((current) => current.map((item, i) => i === index ? { ...item, slug: event.target.value } : item))} maxLength={120} pattern="[a-z0-9-]{2,120}" placeholder="my-club" className="border border-border-gray bg-pitch p-3 font-mono text-raw-white focus:border-acid focus:outline-none" />
                </label>
                <label className="flex flex-col gap-2 text-sm">{t("pages.type")}
                  <select value={page.page_type} onChange={(event) => setPages((current) => current.map((item, i) => i === index ? { ...item, page_type: event.target.value as PageDraft["page_type"] } : item))} className="border border-border-gray bg-pitch p-3 text-raw-white focus:border-acid focus:outline-none">
                    {(["club", "collective", "project", "festival"] as const).map((type) => <option key={type} value={type}>{t(`pages.types.${type}`)}</option>)}
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-sm">{t("pages.about")}
                  <textarea value={page.about} onChange={(event) => setPages((current) => current.map((item, i) => i === index ? { ...item, about: event.target.value } : item))} maxLength={2000} className="min-h-20 border border-border-gray bg-pitch p-3 text-raw-white focus:border-acid focus:outline-none" />
                </label>
                <Button variant="ghost" onClick={() => setPages((current) => current.filter((_, i) => i !== index))}>{t("pages.remove")}</Button>
              </fieldset>
            ))}
            <Button variant="ghost" onClick={() => setPages((current) => [...current, { display_name: "", slug: "", page_type: "club", about: "" }])}>{t("pages.add")}</Button>
            <p className="text-xs text-muted">{t("pages.hint")}</p>
          </div>
        ) : null}

        {step === 5 ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-7 text-dim-white">{t("access.body")}</p>
            <p className="font-mono text-[11px] uppercase tracking-label text-muted">{t("access.hint")}</p>
          </div>
        ) : null}

        {step === 6 ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-7 text-dim-white">{t("done.body")}</p>
            <p className="text-sm text-dim-white">{t("done.summary", { username: nickname, city: city ? t(`cities.${city}`) : "", artist: isArtist ? role : t("done.none"), pages: pages.length ? pages.map((page) => page.display_name).join(", ") : t("done.none") })}</p>
            <p className="font-mono text-[11px] uppercase tracking-label text-muted">{t("done.hint")}</p>
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-border-gray p-4">
        {error ? <p id="onboarding-error" role="alert" className="font-mono text-[11px] uppercase tracking-label text-error">{error}</p> : null}
        <Button variant="ghost" onClick={() => { setError(null); setStep((value) => Math.max(0, value - 1)) }} disabled={step === 0 || pending}>{t("back")}</Button>
        {step < STEPS.length - 1 ? (
          <Button variant="primary" onClick={() => { setError(null); setStep((value) => value + 1) }} disabled={!canNext || pending}>{t("next")}</Button>
        ) : (
          <Button variant="primary" onClick={finish} disabled={pending}>{pending ? t("saving") : t("finish")}</Button>
        )}
      </div>
    </div>
  )
}
