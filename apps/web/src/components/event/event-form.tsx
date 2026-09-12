"use client"

import { useRef, useState, type FormEvent } from "react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import type { ManagedPage } from "@/components/pages/page-management-panel"
import { eventDraft, lineupWithReference, EventValidationError, type EventDraft } from "@/lib/events/editor"
import { saveEvent, EventSaveError } from "@/lib/events/editor-submit"
import type { ThresholdEvent } from "@/lib/types"

const inputClass = "w-full border border-border-gray bg-pitch p-3 text-sm text-raw-white focus:border-acid focus:outline-none"
const actionClass = "border border-border-gray px-3 py-2 font-mono text-xs uppercase text-acid disabled:opacity-50"

export function EventForm({ pages, event }: { pages: ManagedPage[]; event?: ThresholdEvent }) {
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

  function field(key: "title" | "slug" | "starts_at" | "city" | "description" | "genres" | "venue_name" | "address", max?: number, required = false) {
    const props = { id: `event-${key}`, name: key, value: draft[key], maxLength: max, required, onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => update(key, e.target.value), className: inputClass, "aria-invalid": invalidField === key, "aria-describedby": invalidField === key ? "event-error" : undefined }
    return <label className="flex flex-col gap-2 text-sm" htmlFor={props.id}>{t(key)}{key === "description" ? <textarea {...props} rows={5} /> : <input {...props} type={key === "starts_at" ? "datetime-local" : "text"} step={key === "starts_at" ? "0.001" : undefined} pattern={key === "slug" ? "[a-z0-9-]{3,160}" : undefined} />}</label>
  }

  return <form onSubmit={submit} className="flex flex-col gap-5">
    <p className="text-sm text-muted">{t("timeHelp")}</p>
    {error ? <p id="event-error" ref={errorRef} tabIndex={-1} role="alert" className="text-sm text-error">{error}</p> : null}
    <fieldset disabled={pending} className="flex min-w-0 flex-col gap-5">
      {field("title", 160, true)}
      {!event ? <>{field("slug", 160, true)}<label className="flex flex-col gap-2 text-sm">{t("page_id")}<select name="page_id" value={draft.page_id} onChange={e => update("page_id", e.target.value)} required className={inputClass}>{pages.map(page => <option key={page.id} value={page.id}>{page.display_name}</option>)}</select></label></> : <p className="text-sm">{t("page_id")}: {pages.find(p => p.id === event.page_id)?.display_name}</p>}
      {field("starts_at", undefined, true)}
      {field("city", 120, true)}
      {field("description", 4000)}
      {field("genres", 418)}
      <label className="flex flex-col gap-2 text-sm">{t("location_mode")}<select name="location_mode" value={draft.location_mode} onChange={e => update("location_mode", e.target.value)} className={inputClass} disabled={event?.location_mode === "secret_location"}><option value="public_location">{t("publicLocation")}</option><option value="tba">{t("tba")}</option>{event?.location_mode === "secret_location" ? <option value="secret_location">{t("reserved")}</option> : null}</select></label>
      {event?.location_mode !== "secret_location" ? <>{field("venue_name", 160)}{field("address", 400)}</> : null}
      <fieldset className="flex min-w-0 flex-col gap-3 border-t border-border-gray pt-4"><legend className="text-sm">{t("lineup")}</legend>
        <p className="text-sm text-muted">{t("lineupHelp")}</p>
        {draft.lineup.map((artist, index) => <div key={index} className="flex flex-col gap-3 border-b border-border-gray pb-4">
          <label className="text-sm">{t("artistName")} {index + 1}<input aria-label={`${t("artistName")} ${index + 1}`} value={artist.name} maxLength={160} required className={inputClass} onChange={e => setDraft(d => ({ ...d, lineup: d.lineup.map((item, i) => i === index ? { ...item, name: e.target.value } : item) }))} /></label>
          <label className="text-sm">{t("artistReference")}<input aria-label={`${t("artistReference")} ${index + 1}`} value={artist.artist_profile_id ?? ""} maxLength={36} className={inputClass} onChange={e => setDraft(d => ({ ...d, lineup: d.lineup.map((item, i) => { if (i !== index) return item; return lineupWithReference(item, e.target.value) }) }))} /></label>
          <button type="button" className={actionClass} onClick={() => setDraft(d => ({ ...d, lineup: d.lineup.filter((_, i) => i !== index) }))}>{t("removeArtist", { index: index + 1 })}</button>
        </div>)}
        <button type="button" disabled={draft.lineup.length >= 100} className={actionClass} onClick={() => setDraft(d => ({ ...d, lineup: [...d.lineup, { name: "" }] }))}>{t("addArtist")}</button>
      </fieldset>
      <label className="flex flex-col gap-2 text-sm">{t("poster")}<input name="poster" type="file" accept="image/jpeg,image/png,image/webp" className={inputClass} onChange={e => setPoster(e.target.files?.[0] ?? null)} /></label>
      {event?.poster_media_asset_id ? <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!draft.poster_media_asset_id} onChange={e => update("poster_media_asset_id", e.target.checked ? "" : event.poster_media_asset_id!)} />{t("removePoster")}</label> : null}
      <button type="submit" className={actionClass}>{t(pending ? "saving" : event ? "save" : "create")}</button>
    </fieldset>
  </form>
}
