"use client"

import { CalendarBlank, ImageSquare, PaperPlaneTilt } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useEffect, useState, useTransition } from "react"

import { MentionAutocompleteTextarea } from "@/components/social/mention-autocomplete-textarea"
import { Button } from "@/components/ui/button"
import { buildPostPayload, canSubmitPost, MAX_POST_BODY, MAX_POST_IMAGES } from "@/lib/social/post-create"

type EventOption = { slug: string; title: string; starts_at: string }

function isEventOption(value: unknown): value is EventOption {
  if (typeof value !== "object" || value === null) return false
  const event = value as Partial<EventOption>
  return typeof event.slug === "string"
    && typeof event.title === "string"
    && typeof event.starts_at === "string"
}

export function PostComposer({
  compact = false,
  groupSlug,
  onPosted,
  redirectAfterPost = false,
}: {
  compact?: boolean
  groupSlug?: string
  onPosted?: () => void
  redirectAfterPost?: boolean
}) {
  const t = useTranslations("composer")
  const router = useRouter()
  const [body, setBody] = useState("")
  const [files, setFiles] = useState<File[]>([])
  const [eventSlug, setEventSlug] = useState("")
  const [events, setEvents] = useState<EventOption[]>([])
  const [error, setError] = useState<string | null>(null)
  const [eventError, setEventError] = useState<string | null>(null)
  const [fileNotice, setFileNotice] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  useEffect(() => {
    let active = true
    fetch("/api/events?upcoming=true&limit=100")
      .then((response) => {
        if (!response.ok) throw new Error("event load failed")
        return response.json()
      })
      .then((value: unknown) => {
        if (!active) return
        if (typeof value !== "object" || value === null) throw new Error("event load failed")
        const items = (value as { items?: unknown }).items
        if (!Array.isArray(items)) throw new Error("event load failed")
        setEvents(items.filter(isEventOption))
        setEventError(null)
      })
      .catch(() => {
        if (active) setEventError(t("eventLoadError"))
      })
    return () => {
      active = false
    }
  }, [t])

  async function uploadFile(file: File): Promise<string> {
    const formData = new FormData()
    formData.set("context", "post_image")
    formData.set("file", file)
    const response = await fetch("/api/media/assets", { method: "POST", body: formData })
    if (!response.ok) throw new Error("upload failed")
    const asset: unknown = await response.json()
    if (typeof asset !== "object" || asset === null || typeof (asset as { id?: unknown }).id !== "string") {
      throw new Error("upload failed")
    }
    return (asset as { id: string }).id
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmitPost({ body })) return
    setError(null)
    startTransition(async () => {
      let mediaAssetIds: string[]
      try {
        mediaAssetIds = await Promise.all(files.map(uploadFile))
      } catch {
        setError(t("uploadError"))
        return
      }
      try {
        const response = await fetch("/api/social/posts", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(buildPostPayload({
            body,
            groupSlug,
            eventSlug,
            mediaAssetIds,
          })),
        })
        if (!response.ok) {
          const failure: unknown = await response.json().catch(() => null)
          const failureCode = typeof failure === "object" && failure !== null
            ? (failure as { error?: unknown }).error
            : null
          setError(
            response.status === 401
              ? t("sessionExpired")
              : failureCode === "event not found" || failureCode === "invalid event_slug"
                ? t("eventValidationError")
                : failureCode === "event validation unavailable"
                  ? t("eventValidationUnavailable")
                  : t("publishError"),
          )
          return
        }
        setBody("")
        setFiles([])
        setFileNotice(null)
        setEventSlug("")
        onPosted?.()
        router.refresh()
        if (redirectAfterPost) router.push("/app")
      } catch {
        setError(t("networkError"))
      }
    })
  }

  return (
    <form onSubmit={onSubmit} className="border border-border-gray bg-graphite p-3 sm:p-4">
      <label className="sr-only" htmlFor={compact ? "feed-compose-body" : "compose-body"}>
        {t("textLabel")}
      </label>
      <MentionAutocompleteTextarea
        id={compact ? "feed-compose-body" : "compose-body"}
        value={body}
        onChangeValue={setBody}
        rows={compact ? 3 : 6}
        maxLength={MAX_POST_BODY}
        placeholder={t("placeholder")}
        className="w-full resize-none border border-transparent bg-pitch p-3 text-sm leading-7 text-raw-white placeholder:text-muted focus:border-acid focus:outline-none"
      />

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <label className="flex cursor-pointer items-center gap-2 border border-dashed border-border-gray bg-pitch px-3 py-2 font-mono text-[11px] uppercase tracking-label text-muted hover:border-acid hover:text-acid">
          <ImageSquare size={17} aria-hidden />
          <span>{files.length > 0 ? t("imagesSelected", { count: files.length }) : t("attachImages")}</span>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple
            className="sr-only"
            onChange={(event) => {
              const selected = Array.from(event.currentTarget.files ?? [])
              setFiles(selected.slice(0, MAX_POST_IMAGES))
              if (selected.length > 0) setEventSlug("")
              setFileNotice(
                selected.length > MAX_POST_IMAGES
                  ? t("imagesTruncated", { count: MAX_POST_IMAGES })
                  : null,
              )
            }}
          />
        </label>
        <label className="relative flex items-center gap-2 border border-border-gray bg-pitch px-3 py-2 text-muted focus-within:border-acid">
          <CalendarBlank size={17} className="shrink-0" aria-hidden />
          <span className="sr-only">{t("eventLabel")}</span>
          <select
            value={eventSlug}
            onChange={(event) => {
              const slug = event.target.value
              setEventSlug(slug)
              if (slug) {
                setFiles([])
                setFileNotice(null)
              }
            }}
            className="min-w-0 flex-1 bg-pitch font-mono text-[11px] uppercase tracking-label text-dim-white focus:outline-none"
          >
            <option value="">{t("noEvent")}</option>
            {events.map((event) => (
              <option key={event.slug} value={event.slug}>{event.title}</option>
            ))}
          </select>
        </label>
      </div>

      {fileNotice ? (
        <p className="mt-2 font-mono text-[11px] uppercase tracking-label text-orange">
          {fileNotice}
        </p>
      ) : null}
      {eventError ? (
        <p className="mt-2 font-mono text-[11px] uppercase tracking-label text-orange">
          {eventError}
        </p>
      ) : null}
      {error ? (
        <p className="mt-2 font-mono text-[11px] uppercase tracking-label text-error">{error}</p>
      ) : null}
      <div className="mt-3 flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-label text-muted">
          {body.length}/{MAX_POST_BODY}
        </span>
        <Button type="submit" variant="primary" disabled={pending || !canSubmitPost({ body })}>
          <PaperPlaneTilt size={16} aria-hidden />
          {pending ? t("publishing") : t("publish")}
        </Button>
      </div>
    </form>
  )
}
