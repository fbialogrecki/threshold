"use client"

import { Plus, Trash } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import Image from "next/image"
import { useRouter } from "next/navigation"
import { useRef, useState, type FormEvent, type ReactNode } from "react"

import type { ManagedPage } from "@/components/pages/page-management-panel"
import { Button } from "@/components/ui/button"
import { Field, FormAlert, inputClass, Spinner } from "@/components/ui/field"
import { cn } from "@/lib/cn"
import { eventDraft, lineupWithReference, EventValidationError, type EventDraft } from "@/lib/events/editor"
import { saveEvent, EventSaveError } from "@/lib/events/editor-submit"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import type { PerlimenEvent } from "@/lib/types"

type TextKey = "title" | "slug" | "starts_at" | "city" | "description" | "genres" | "venue_name" | "address"

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-5 rounded-surface border border-border-gray bg-graphite/60 p-4 sm:p-6">
      <legend className="px-1 text-sm font-semibold text-raw-white">{title}</legend>
      {children}
    </fieldset>
  )
}

export function EventForm({ pages, event }: { pages: ManagedPage[]; event?: PerlimenEvent }) {
  const t = useTranslations("eventEditor")
  const router = useRouter()
  const [draft, setDraft] = useState<EventDraft>(() => ({ ...eventDraft(event), page_id: event?.page_id ?? pages[0]?.id ?? "" }))
  const [poster, setPoster] = useState<File | null>(null)
  const [pending, setPending] = useState(false)
  const busy = useRef(false)
  const [error, setError] = useState("")
  const [invalidField, setInvalidField] = useState("")
  const errorRef = useRef<HTMLParagraphElement>(null)
  const update = (key: keyof EventDraft, value: string) => setDraft(d => ({ ...d, [key]: value }))

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (busy.current) return
    busy.current = true
    setPending(true)
    setError("")
    setInvalidField("")
    try {
      const href = await saveEvent(draft, event, poster)
      router.push(href)
      router.refresh()
    } catch (error) {
      if (error instanceof EventValidationError) {
        setInvalidField(error.field)
        setError(t("invalid", { field: t(error.field) }))
      } else {
        const status = error instanceof EventSaveError ? error.status : 0
        setError(t(status === 409 ? "conflict" : status === 413 ? "tooLarge" : status === 401 || status === 403 ? "denied" : "saveError"))
      }
      requestAnimationFrame(() => errorRef.current?.focus())
    } finally {
      busy.current = false
      setPending(false)
    }
  }

  function field(key: TextKey, max?: number, required = false, className?: string) {
    const props = {
      id: `event-${key}`,
      name: key,
      value: draft[key],
      maxLength: max,
      required,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => update(key, e.target.value),
      className: cn(inputClass, key === "slug" && "font-mono"),
      "aria-invalid": invalidField === key,
      "aria-describedby": invalidField === key ? "event-error" : undefined,
    }
    return (
      <Field htmlFor={props.id} label={t(key)} className={className}>
        {key === "description" ? (
          <textarea {...props} rows={6} />
        ) : (
          <input
            {...props}
            type={key === "starts_at" ? "datetime-local" : "text"}
            step={key === "starts_at" ? "0.001" : undefined}
            pattern={key === "slug" ? "[a-z0-9-]{3,160}" : undefined}
            autoCapitalize={key === "slug" ? "none" : undefined}
            spellCheck={key === "slug" ? false : undefined}
          />
        )}
      </Field>
    )
  }

  const secret = event?.location_mode === "secret_location"
  const currentPoster = event?.poster_media_asset_id && draft.poster_media_asset_id
    ? mediaDerivativeUrl(event.poster_media_asset_id, "post_1280")
    : null

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      {error ? (
        <FormAlert id="event-error" ref={errorRef} focusable>
          {error}
        </FormAlert>
      ) : null}
      <fieldset disabled={pending} className="flex min-w-0 flex-col gap-5">
        <Section title={t("sectionBasics")}>
          {field("title", 160, true)}
          {!event ? (
            <div className="grid gap-5 sm:grid-cols-2">
              {field("slug", 160, true)}
              <Field htmlFor="event-page_id" label={t("page_id")}>
                <select
                  id="event-page_id"
                  name="page_id"
                  value={draft.page_id}
                  onChange={e => update("page_id", e.target.value)}
                  required
                  className={inputClass}
                >
                  {pages.map(page => <option key={page.id} value={page.id}>{page.display_name}</option>)}
                </select>
              </Field>
            </div>
          ) : (
            <p className="text-sm text-dim-white">
              <span className="text-muted">{t("page_id")}: </span>
              {pages.find(p => p.id === event.page_id)?.display_name}
            </p>
          )}
          {field("description", 4000)}
          {field("genres", 418)}
        </Section>

        <Section title={t("sectionWhenWhere")}>
          <p className="rounded-control bg-raised px-3.5 py-3 text-[13px] leading-5 text-dim-white">{t("timeHelp")}</p>
          <div className="grid gap-5 sm:grid-cols-2">
            {field("starts_at", undefined, true)}
            {field("city", 120, true)}
          </div>
          <Field htmlFor="event-location_mode" label={t("location_mode")}>
            <select
              id="event-location_mode"
              name="location_mode"
              value={draft.location_mode}
              onChange={e => update("location_mode", e.target.value)}
              className={inputClass}
              disabled={secret}
            >
              <option value="public_location">{t("publicLocation")}</option>
              <option value="tba">{t("tba")}</option>
              {secret ? <option value="secret_location">{t("reserved")}</option> : null}
            </select>
          </Field>
          {!secret ? (
            <div className="grid gap-5 sm:grid-cols-2">
              {field("venue_name", 160)}
              {field("address", 400)}
            </div>
          ) : null}
        </Section>

        <Section title={t("lineup")}>
          <p className="text-[13px] leading-5 text-muted">{t("lineupHelp")}</p>
          {draft.lineup.map((artist, index) => (
            <div key={index} className="grid gap-4 rounded-control border border-border-gray bg-pitch/50 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end">
              <Field htmlFor={`event-artist-${index}-name`} label={`${t("artistName")} ${index + 1}`}>
                <input
                  id={`event-artist-${index}-name`}
                  aria-label={`${t("artistName")} ${index + 1}`}
                  value={artist.name}
                  maxLength={160}
                  required
                  className={inputClass}
                  onChange={e => setDraft(d => ({ ...d, lineup: d.lineup.map((item, i) => i === index ? { ...item, name: e.target.value } : item) }))}
                />
              </Field>
              <Field htmlFor={`event-artist-${index}-reference`} label={t("artistReference")}>
                <input
                  id={`event-artist-${index}-reference`}
                  aria-label={`${t("artistReference")} ${index + 1}`}
                  value={artist.artist_profile_id ?? ""}
                  maxLength={36}
                  spellCheck={false}
                  className={cn(inputClass, "font-mono text-sm")}
                  onChange={e => setDraft(d => ({ ...d, lineup: d.lineup.map((item, i) => { if (i !== index) return item; return lineupWithReference(item, e.target.value) }) }))}
                />
              </Field>
              <button
                type="button"
                aria-label={t("removeArtist", { index: index + 1 })}
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-control border border-border-gray px-3 text-sm text-dim-white transition-colors hover:border-status-neutral-border hover:text-raw-white"
                onClick={() => setDraft(d => ({ ...d, lineup: d.lineup.filter((_, i) => i !== index) }))}
              >
                <Trash size={16} aria-hidden />
                <span className="sm:sr-only">{t("removeArtist", { index: index + 1 })}</span>
              </button>
            </div>
          ))}
          <button
            type="button"
            disabled={draft.lineup.length >= 100}
            className="flex min-h-12 items-center justify-center gap-2 rounded-control border border-dashed border-status-neutral-border px-4 text-[15px] font-medium text-dim-white transition-colors hover:border-acid hover:text-acid disabled:opacity-50"
            onClick={() => setDraft(d => ({ ...d, lineup: [...d.lineup, { name: "" }] }))}
          >
            <Plus size={16} weight="bold" aria-hidden />
            {t("addArtist")}
          </button>
        </Section>

        <Section title={t("sectionPoster")}>
          {currentPoster ? (
            <Image
              src={currentPoster}
              alt={t("currentPoster")}
              width={160}
              height={200}
              className="aspect-[4/5] w-32 rounded-control border border-border-gray object-cover"
            />
          ) : null}
          <Field htmlFor="event-poster" label={t("poster")}>
            <input
              id="event-poster"
              name="poster"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className={cn(inputClass, "text-sm file:mr-3 file:rounded-md file:border-0 file:bg-raised file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-raw-white")}
              onChange={e => setPoster(e.target.files?.[0] ?? null)}
            />
          </Field>
          {event?.poster_media_asset_id ? (
            <label className="flex items-center gap-3 text-[15px]">
              <input
                type="checkbox"
                className="size-5 accent-acid"
                checked={!draft.poster_media_asset_id}
                onChange={e => update("poster_media_asset_id", e.target.checked ? "" : event.poster_media_asset_id!)}
              />
              {t("removePoster")}
            </label>
          ) : null}
        </Section>

        <Button type="submit" variant="primary" size="lg" className="self-start">
          {pending ? <Spinner /> : null}
          {t(pending ? "saving" : event ? "save" : "create")}
        </Button>
      </fieldset>
    </form>
  )
}
