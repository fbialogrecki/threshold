"use client"

import { Check, Plus, Trash } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState, useTransition } from "react"

import { authSurfaceClass } from "@/components/auth/auth-panel"
import { Button } from "@/components/ui/button"
import { Field, FormAlert, inputClass, Spinner } from "@/components/ui/field"
import { CITY_OPTIONS, type CanonicalCity } from "@/lib/cities"
import { cn } from "@/lib/cn"
import { saveSetup, type PageDraft } from "@/lib/onboarding/setup"
import { canContinue, isSkipping, STEPS } from "@/lib/onboarding/steps"
import { USERNAME_PATTERN } from "@/lib/validation"

const SCENES = ["techno", "industrial", "hardcore", "ebm", "acid", "rave", "ambient", "experimental"]
const PAGE_TYPES = ["club", "collective", "project", "festival"] as const

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
  const headingRef = useRef<HTMLHeadingElement>(null)
  const moved = useRef(false)

  // Each step swaps the content under the user, so focus follows to the new
  // heading; never on first render, which would steal focus from the page.
  useEffect(() => {
    if (moved.current) headingRef.current?.focus()
  }, [step])

  function goTo(next: number) {
    moved.current = true
    setStep(next)
  }

  function toggle<T>(list: T[], value: T): T[] {
    return list.includes(value) ? list.filter((item) => item !== value) : [...list, value]
  }

  function updatePage(index: number, patch: Partial<PageDraft>) {
    setPages((current) => current.map((item, i) => (i === index ? { ...item, ...patch } : item)))
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
        goTo(STEPS.indexOf(result.step))
        setNicknameInvalid(result.step === "identity")
        return
      }
      router.push(callbackUrl)
      router.refresh()
    })
  }

  const name = STEPS[step]
  const draft = { nickname, city, scenes, isArtist, role, artistUrl, pages }
  const canNext = canContinue(name, draft)
  const last = step === STEPS.length - 1
  const none = t("done.none")

  return (
    <div className={authSurfaceClass}>
      <div className="border-b border-border-gray p-5 sm:px-7">
        <p className="flex items-baseline justify-between gap-3 text-sm text-dim-white lg:hidden">
          <span>{t("stepOf", { current: step + 1, total: STEPS.length })}</span>
          <span className="font-semibold text-raw-white">{t(`steps.${name}`)}</span>
        </p>
        <div
          className="mt-3 h-1 overflow-hidden rounded-full bg-border-gray lg:hidden"
          aria-hidden
        >
          <div
            className="h-full rounded-full bg-acid transition-[width] duration-500 ease-out-expo"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>
        <ol aria-label={t("progressLabel")} className="hidden grid-cols-7 gap-2 lg:grid">
          {STEPS.map((label, index) => (
            <li
              key={label}
              aria-current={index === step ? "step" : undefined}
              className="flex flex-col gap-2"
            >
              <span
                className={cn(
                  "h-1 rounded-full transition-colors duration-300",
                  index <= step ? "bg-acid" : "bg-border-gray",
                )}
                aria-hidden
              />
              <span
                className={cn(
                  "flex items-center gap-1.5 text-[13px] leading-tight",
                  index === step
                    ? "font-semibold text-raw-white"
                    : index < step
                      ? "text-dim-white"
                      : "text-muted",
                )}
              >
                {index < step ? <Check size={12} weight="bold" className="shrink-0 text-acid" aria-hidden /> : null}
                {t(`steps.${label}`)}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <div key={step} className="animate-step p-5 sm:p-7">
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="font-display text-2xl leading-none sm:text-3xl"
        >
          {t(`steps.${name}`)}
        </h2>

        {name === "identity" ? (
          <div className="mt-4 flex flex-col gap-5">
            <p className="text-[15px] leading-7 text-dim-white">{t("identity.body")}</p>
            <Field
              htmlFor="onboarding-nickname"
              label={t("identity.nickname")}
              help={t("identity.hint")}
              helpId="onboarding-nickname-help"
            >
              <input
                id="onboarding-nickname"
                value={nickname}
                onChange={(event) => {
                  setNickname(event.target.value)
                  setNicknameInvalid(false)
                }}
                placeholder="nightcrawler"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
                maxLength={30}
                pattern={USERNAME_PATTERN}
                aria-invalid={nicknameInvalid || undefined}
                aria-describedby={`onboarding-nickname-help${nicknameInvalid ? " onboarding-error" : ""}`}
                className={inputClass}
              />
            </Field>
          </div>
        ) : null}

        {name === "city" ? (
          <fieldset className="mt-4">
            <legend className="text-[15px] leading-7 text-dim-white">{t("city.body")}</legend>
            <div className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {CITY_OPTIONS.map((option) => {
                const selected = city === option.value
                return (
                  <label
                    key={option.value}
                    className={cn(
                      "flex cursor-pointer items-center justify-between gap-2 rounded-control border px-4 py-3.5 text-[15px] font-medium transition-[color,background-color,border-color,scale] duration-150 ease-press active:scale-[0.98] has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-acid",
                      selected
                        ? "border-acid bg-acid/10 text-raw-white"
                        : "border-border-gray text-dim-white hover:border-status-neutral-border hover:text-raw-white",
                    )}
                  >
                    <input
                      type="radio"
                      name="onboarding-city"
                      value={option.value}
                      checked={selected}
                      onChange={() => setCity(option.value)}
                      required
                      className="sr-only"
                    />
                    {t(`cities.${option.value}`)}
                    <Check
                      size={16}
                      weight="bold"
                      className={cn("shrink-0 text-acid transition-opacity", selected ? "opacity-100" : "opacity-0")}
                      aria-hidden
                    />
                  </label>
                )
              })}
            </div>
          </fieldset>
        ) : null}

        {name === "frequencies" ? (
          <div className="mt-4 flex flex-col gap-5">
            <p className="text-[15px] leading-7 text-dim-white">{t("frequencies.body")}</p>
            <div className="flex flex-wrap gap-2">
              {SCENES.map((scene) => {
                const selected = scenes.includes(scene)
                return (
                  <button
                    key={scene}
                    type="button"
                    onClick={() => setScenes((current) => toggle(current, scene))}
                    aria-pressed={selected}
                    className={cn(
                      "rounded-full border px-4 py-2 text-[15px] font-medium transition-[color,background-color,border-color,scale] duration-150 ease-press active:scale-95",
                      selected
                        ? "border-acid bg-acid text-pitch"
                        : "border-border-gray text-dim-white hover:border-status-neutral-border hover:text-raw-white",
                    )}
                  >
                    #{scene}
                  </button>
                )
              })}
            </div>
          </div>
        ) : null}

        {name === "artist" ? (
          <div className="mt-4 flex flex-col gap-5">
            <p className="text-[15px] leading-7 text-dim-white">{t("artist.body")}</p>
            <label className="flex cursor-pointer items-center gap-3 rounded-control border border-border-gray p-4 text-[15px] font-medium transition-colors has-[:checked]:border-acid has-[:checked]:bg-acid/5">
              <input
                type="checkbox"
                checked={isArtist}
                onChange={(event) => setIsArtist(event.target.checked)}
                className="size-5 shrink-0 accent-acid"
              />
              {t("artist.enable")}
            </label>
            {isArtist ? (
              <div className="grid animate-step gap-5 sm:grid-cols-2">
                <Field htmlFor="onboarding-artist-role" label={t("artist.role")}>
                  <input id="onboarding-artist-role" value={role} onChange={(event) => setRole(event.target.value)} maxLength={120} className={inputClass} />
                </Field>
                <Field htmlFor="onboarding-artist-location" label={t("artist.location")}>
                  <input id="onboarding-artist-location" value={location} onChange={(event) => setLocation(event.target.value)} maxLength={120} className={inputClass} />
                </Field>
                <Field htmlFor="onboarding-artist-url" label={t("artist.url")} className="sm:col-span-2">
                  <input id="onboarding-artist-url" type="url" value={artistUrl} onChange={(event) => setArtistUrl(event.target.value)} placeholder="https://" className={inputClass} />
                </Field>
              </div>
            ) : null}
            <p className="text-[13px] leading-5 text-muted">{t("artist.hint")}</p>
          </div>
        ) : null}

        {name === "pages" ? (
          <div className="mt-4 flex flex-col gap-5">
            <p className="text-[15px] leading-7 text-dim-white">{t("pages.body")}</p>
            {pages.map((page, index) => (
              <fieldset key={index} className="grid animate-step gap-5 rounded-control border border-border-gray bg-pitch/50 p-4 sm:grid-cols-2 sm:p-5">
                <legend className="px-1 text-sm font-semibold text-raw-white">{t("pages.entry", { number: index + 1 })}</legend>
                <Field htmlFor={`onboarding-page-${index}-name`} label={t("pages.name")}>
                  <input id={`onboarding-page-${index}-name`} value={page.display_name} onChange={(event) => updatePage(index, { display_name: event.target.value })} maxLength={160} className={inputClass} />
                </Field>
                <Field htmlFor={`onboarding-page-${index}-slug`} label={t("pages.slug")}>
                  <input id={`onboarding-page-${index}-slug`} value={page.slug} onChange={(event) => updatePage(index, { slug: event.target.value })} maxLength={120} pattern="[a-z0-9-]{2,120}" placeholder="my-club" autoCapitalize="none" spellCheck={false} className={cn(inputClass, "font-mono")} />
                </Field>
                <Field htmlFor={`onboarding-page-${index}-type`} label={t("pages.type")}>
                  <select id={`onboarding-page-${index}-type`} value={page.page_type} onChange={(event) => updatePage(index, { page_type: event.target.value as PageDraft["page_type"] })} className={inputClass}>
                    {PAGE_TYPES.map((type) => <option key={type} value={type}>{t(`pages.types.${type}`)}</option>)}
                  </select>
                </Field>
                <Field htmlFor={`onboarding-page-${index}-about`} label={t("pages.about")} className="sm:col-span-2">
                  <textarea id={`onboarding-page-${index}-about`} value={page.about} onChange={(event) => updatePage(index, { about: event.target.value })} maxLength={2000} className={cn(inputClass, "min-h-24")} />
                </Field>
                <button
                  type="button"
                  onClick={() => setPages((current) => current.filter((_, i) => i !== index))}
                  className="inline-flex w-fit items-center gap-2 text-sm text-muted transition-colors hover:text-raw-white sm:col-span-2"
                >
                  <Trash size={16} aria-hidden />
                  {t("pages.remove")}
                </button>
              </fieldset>
            ))}
            <button
              type="button"
              onClick={() => setPages((current) => [...current, { display_name: "", slug: "", page_type: "club", about: "" }])}
              className="flex items-center justify-center gap-2 rounded-control border border-dashed border-status-neutral-border px-4 py-3.5 text-[15px] font-medium text-dim-white transition-[color,border-color,scale] duration-150 ease-press hover:border-acid hover:text-acid active:scale-[0.99]"
            >
              <Plus size={16} weight="bold" aria-hidden />
              {t("pages.add")}
            </button>
            <p className="text-[13px] leading-5 text-muted">{t("pages.hint")}</p>
          </div>
        ) : null}

        {name === "access" ? (
          <div className="mt-4 flex flex-col gap-5">
            {city ? (
              <p className="rounded-control border border-acid/30 bg-acid/5 px-4 py-5 font-display text-3xl leading-none text-acid sm:text-4xl">
                {t(`cities.${city}`)}
              </p>
            ) : null}
            <p className="text-[15px] leading-7 text-dim-white">{t("access.body")}</p>
            <p className="text-[13px] leading-5 text-muted">{t("access.hint")}</p>
          </div>
        ) : null}

        {name === "done" ? (
          <div className="mt-4 flex flex-col gap-5">
            <p className="text-[15px] leading-7 text-dim-white">{t("done.body")}</p>
            <dl className="divide-y divide-border-gray rounded-control border border-border-gray">
              {([
                ["identity", nickname.trim()],
                ["city", city ? t(`cities.${city}`) : none],
                ["frequencies", scenes.length ? scenes.map((scene) => `#${scene}`).join(" ") : none],
                ["artist", isArtist ? role : none],
                ["pages", pages.length ? pages.map((page) => page.display_name).join(", ") : none],
              ] as const).map(([key, value]) => (
                <div key={key} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3">
                  <dt className="text-sm text-muted">{t(`steps.${key}`)}</dt>
                  <dd className="min-w-0 break-words text-[15px] font-medium text-raw-white">{value}</dd>
                </div>
              ))}
            </dl>
            <p className="text-[13px] leading-5 text-muted">{t("done.hint")}</p>
          </div>
        ) : null}

        {error ? (
          <div className="mt-6">
            <FormAlert id="onboarding-error">{error}</FormAlert>
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border-gray p-4 sm:px-7">
        <Button
          variant="ghost"
          size="lg"
          onClick={() => {
            setError(null)
            goTo(Math.max(0, step - 1))
          }}
          disabled={pending}
          className={cn("px-3", step === 0 && "invisible")}
        >
          {t("back")}
        </Button>
        {last ? (
          <Button variant="primary" size="lg" onClick={finish} disabled={pending}>
            {pending ? (
              <>
                <Spinner />
                {t("saving")}
              </>
            ) : (
              t("finish")
            )}
          </Button>
        ) : (
          <Button
            variant={isSkipping(name, draft) ? "secondary" : "primary"}
            size="lg"
            onClick={() => {
              setError(null)
              goTo(step + 1)
            }}
            disabled={!canNext || pending}
          >
            {isSkipping(name, draft) ? t("skip") : t("next")}
          </Button>
        )}
      </div>
    </div>
  )
}
