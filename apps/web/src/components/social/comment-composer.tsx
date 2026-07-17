"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import { MentionAutocompleteTextarea } from "@/components/social/mention-autocomplete-textarea"

const MAX = 1000

/**
 * Comment form for top-level comments and one-level replies (parentId).
 * With onCreated the new comment is handed to the caller for local state
 * updates (no full router.refresh); without it the page is refreshed.
 */
export function CommentComposer({
  postId,
  parentId,
  initialValue = "",
  autoFocus = false,
  compact = false,
  onCreated,
}: {
  postId: string
  parentId?: string | null
  initialValue?: string
  autoFocus?: boolean
  compact?: boolean
  onCreated?: (rawComment: unknown) => void
}) {
  const t = useTranslations("commentComposer")
  const router = useRouter()
  const [body, setBody] = useState(initialValue)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    const text = body.trim()
    if (!text) return
    setError(null)

    startTransition(async () => {
      try {
        const response = await fetch(
          `/api/social/posts/${encodeURIComponent(postId)}/comments`,
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(
              parentId ? { body: text, parent_id: parentId } : { body: text },
            ),
          },
        )
        if (!response.ok) {
          if (response.status === 401) {
            router.push("/login")
            return
          }
          setError(t("postError"))
          return
        }
        setBody("")
        if (onCreated) {
          onCreated(await response.json().catch(() => null))
        } else {
          router.refresh()
        }
      } catch {
        setError(t("networkError"))
      }
    })
  }

  // Compact mode (inline comments) stays low-profile: a slim one-row field
  // that only grows and reveals its footer once the user starts typing.
  const active = body.length > 0

  return (
    <form
      onSubmit={onSubmit}
      className={
        compact
          ? "border border-border-gray bg-graphite p-2 focus-within:border-acid"
          : "border border-border-gray bg-graphite p-4 focus-within:border-acid"
      }
    >
      <label className="sr-only" htmlFor={`comment-body-${postId}-${parentId ?? "top"}`}>
        {parentId ? t("replyLabel") : t("commentLabel")}
      </label>
      <MentionAutocompleteTextarea
        id={`comment-body-${postId}-${parentId ?? "top"}`}
        value={body}
        onChangeValue={setBody}
        rows={compact ? (active ? 2 : 1) : 3}
        maxLength={MAX}
        autoFocus={autoFocus}
        placeholder={parentId ? t("replyPlaceholder") : t("commentPlaceholder")}
        className={
          compact
            ? "w-full resize-none bg-pitch p-2 text-sm leading-6 text-raw-white placeholder:text-muted focus:outline-none"
            : "w-full resize-none bg-pitch p-3 text-sm leading-7 text-raw-white placeholder:text-muted focus:outline-none"
        }
      />
      {error ? (
        <p className="mt-2 font-mono text-[11px] uppercase tracking-label text-error">
          {error}
        </p>
      ) : null}
      {!compact || active ? (
        <div className={compact ? "mt-2 flex items-center justify-between" : "mt-3 flex items-center justify-between"}>
          <span className="font-mono text-[11px] uppercase tracking-label text-muted">
            {body.length}/{MAX}
          </span>
          <Button
            type="submit"
            variant="primary"
            className={compact ? "px-3 py-1" : undefined}
            disabled={pending || body.trim().length === 0}
          >
            {pending ? t("posting") : parentId ? t("reply") : t("comment")}
          </Button>
        </div>
      ) : null}
    </form>
  )
}
