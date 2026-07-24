"use client"

import { CalendarBlank, ImageSquare, PaperPlaneTilt } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState, useTransition } from "react"

import { MentionAutocompleteTextarea } from "@/components/social/mention-autocomplete-textarea"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
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
  // The dedicated /app/compose page is already a compose surface, so it opens
  // expanded; in the feed the composer starts as a one-line trigger.
  const [open, setOpen] = useState(!compact)
  const [body, setBody] = useState("")
  const [files, setFiles] = useState<File[]>([])
  const [eventSlug, setEventSlug] = useState("")
  const [events, setEvents] = useState<EventOption[]>([])
  const [error, setError] = useState<string | null>(null)
  const [eventError, setEventError] = useState<string | null>(null)
  const [fileNotice, setFileNotice] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()
  const formRef = useRef<HTMLFormElement>(null)

  // The feed composer has no close control: clicking away or pressing Escape
  // collapses it. A prevented Escape belongs to the mention dropdown, which
  // closes itself first and must not also collapse the composer.
  useEffect(() => {
    if (!open || !compact) return

    function onPointerDown(event: PointerEvent) {
      if (!formRef.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !event.defaultPrevented) setOpen(false)
    }

    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [open, compact])

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

  if (!open) {
    // Collapsing keeps the draft in state, so the trigger shows it back rather
    // than the placeholder; otherwise the text looks discarded.
    const draft = body.trim()
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex w-full items-center gap-3 border border-border-gray px-3 py-3 text-left transition-colors hover:border-acid"
      >
        <span className={cn("flex-1 truncate text-sm", draft ? "text-dim-white" : "text-muted")}>
          {draft || t("placeholder")}
        </span>
        <span className="font-mono text-[11px] uppercase tracking-label text-acid">
          {t("publish")}
        </span>
      </button>
    )
  }

  // The counter is noise until the limit is actually in reach.
  const remaining = MAX_POST_BODY - body.length
  const iconActionClass = "p-2 text-muted transition-colors hover:text-acid focus-within:text-acid"

  return (
    <form
      ref={formRef}
      onSubmit={onSubmit}
      className="border border-border-gray focus-within:border-acid"
    >
      <label className="sr-only" htmlFor={compact ? "feed-compose-body" : "compose-body"}>
        {t("textLabel")}
      </label>
      <MentionAutocompleteTextarea
        id={compact ? "feed-compose-body" : "compose-body"}
        value={body}
        onChangeValue={setBody}
        rows={compact ? 4 : 6}
        maxLength={MAX_POST_BODY}
        autoFocus={compact}
        placeholder={t("placeholder")}
        className="w-full resize-none bg-transparent p-3 text-[15px] leading-7 text-raw-white placeholder:text-muted focus:outline-none"
      />

      <div aria-live="polite">
        {fileNotice ? <p className="px-3 pb-2 text-sm text-orange">{fileNotice}</p> : null}
        {eventError ? <p className="px-3 pb-2 text-sm text-orange">{eventError}</p> : null}
        {error ? <p className="px-3 pb-2 text-sm text-error">{error}</p> : null}
      </div>

      <div className="flex items-center gap-1 border-t border-border-gray px-2 py-2">
        <label className={`flex cursor-pointer items-center gap-1.5 ${iconActionClass}`}>
          <ImageSquare size={18} aria-hidden />
          <span className={files.length > 0 ? "font-mono text-[10px] tabular-nums" : "sr-only"}>
            {files.length > 0 ? files.length : t("attachImages")}
          </span>
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

        <label className={`flex items-center gap-1.5 ${iconActionClass}`}>
          <CalendarBlank size={18} className="shrink-0" aria-hidden />
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
            className="max-w-28 bg-transparent font-mono text-[10px] uppercase tracking-label text-current focus:outline-none"
          >
            <option value="">{t("noEvent")}</option>
            {events.map((event) => (
              <option key={event.slug} value={event.slug}>{event.title}</option>
            ))}
          </select>
        </label>

        <span className="flex-1" />

        {remaining < 400 ? (
          <span className="font-mono text-[10px] uppercase tracking-label tabular-nums text-orange">
            {remaining}
          </span>
        ) : null}
        <Button
          type="submit"
          variant="primary"
          className="px-3 py-1.5 text-[11px]"
          disabled={pending || !canSubmitPost({ body })}
        >
          <PaperPlaneTilt size={14} aria-hidden />
          {pending ? t("publishing") : t("publish")}
        </Button>
      </div>
    </form>
  )
}
