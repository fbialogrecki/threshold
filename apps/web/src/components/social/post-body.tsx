"use client"

import { PencilSimple, Trash } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import type { ReactNode } from "react"
import { useState, useTransition } from "react"

import { RichText } from "@/components/social/rich-text"
import type { MentionRef } from "@/lib/types"

const MAX_BODY = 2000

/**
 * Post body with owner controls: the author (viewer_is_author from the
 * social service, enforced server-side too) can edit inline or delete with
 * an inline confirm. Everyone else sees plain text.
 */
export function PostBody({
  postId,
  body,
  mentions,
  editedAtIso,
  viewerIsAuthor,
  header,
  age,
  redirectHomeOnDelete = false,
}: {
  postId: string
  body: string
  mentions: MentionRef[]
  editedAtIso: string | null
  viewerIsAuthor: boolean
  header: ReactNode
  age: ReactNode
  /** set on /posts/[id]: the page disappears with the post */
  redirectHomeOnDelete?: boolean
}) {
  const t = useTranslations("post")
  const router = useRouter()
  const [text, setText] = useState(body)
  const [edited, setEdited] = useState(editedAtIso !== null)
  const [mode, setMode] = useState<"view" | "edit" | "confirm-delete">("view")
  const [draft, setDraft] = useState(body)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  function saveEdit(event: React.FormEvent) {
    event.preventDefault()
    const next = draft.trim()
    if (!next || next === text) {
      setMode("view")
      setDraft(text)
      return
    }
    setError(null)
    startTransition(async () => {
      try {
        const response = await fetch(`/api/social/posts/${encodeURIComponent(postId)}`, {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ body: next }),
        })
        if (!response.ok) throw new Error("edit failed")
        setText(next)
        setEdited(true)
        setMode("view")
      } catch {
        setError(t("editError"))
      }
    })
  }

  function confirmDelete() {
    setError(null)
    startTransition(async () => {
      try {
        const response = await fetch(`/api/social/posts/${encodeURIComponent(postId)}`, {
          method: "DELETE",
        })
        if (!response.ok && response.status !== 204) throw new Error("delete failed")
        if (redirectHomeOnDelete) {
          router.push("/app")
        }
        router.refresh()
      } catch {
        setError(t("deleteError"))
        setMode("view")
      }
    })
  }

  const actionClass =
    "font-mono text-[10px] uppercase tracking-label text-muted hover:text-acid"

  const ownerActions = viewerIsAuthor && mode !== "edit" ? (
    mode === "confirm-delete" ? (
      <span className="flex flex-wrap items-center justify-end gap-2">
        <span className="font-mono text-[10px] uppercase tracking-label text-error">
          {t("deleteConfirm")}
        </span>
        <button
          type="button"
          onClick={confirmDelete}
          disabled={pending}
          className="font-mono text-[10px] uppercase tracking-label text-error hover:text-raw-white"
        >
          {pending ? t("deleting") : t("yes")}
        </button>
        <button type="button" onClick={() => setMode("view")} className={actionClass}>
          {t("no")}
        </button>
      </span>
    ) : (
      <>
        <button
          type="button"
          onClick={() => {
            setDraft(text)
            setMode("edit")
          }}
          className={`${actionClass} inline-flex items-center gap-1`}
        >
          <PencilSimple size={13} aria-hidden />
          {t("edit")}
        </button>
        <button
          type="button"
          onClick={() => setMode("confirm-delete")}
          className={`${actionClass} inline-flex items-center gap-1`}
        >
          <Trash size={13} aria-hidden />
          {t("delete")}
        </button>
      </>
    )
  ) : null

  return (
    <>
      <div className="flex items-start justify-between gap-3">
        {header}
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          {age}
          {ownerActions}
        </div>
      </div>
      {mode === "edit" ? (
        <form onSubmit={saveEdit} className="mt-3">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          rows={4}
          maxLength={MAX_BODY}
          autoFocus
          aria-label={t("editPost")}
          className="w-full resize-none border border-border-gray bg-pitch p-2 text-sm leading-6 text-raw-white focus:border-acid focus:outline-none"
        />
        {error ? (
          <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-error">
            {error}
          </p>
        ) : null}
        <div className="mt-1.5 flex items-center gap-3">
          <button type="submit" disabled={pending} className={actionClass}>
            {pending ? t("saving") : t("save")}
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("view")
              setDraft(text)
            }}
            className={actionClass}
          >
            {t("cancel")}
          </button>
        </div>
        </form>
      ) : (
        <div className="mt-3">
          <p className="text-[15px] leading-7 text-raw-white">
        <RichText text={text} mentions={mentions} />
        {edited ? (
          <span className="ml-2 font-mono text-[10px] uppercase tracking-label text-muted">
            {t("edited")}
          </span>
        ) : null}
          </p>
      {error ? (
        <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-error">
          {error}
        </p>
      ) : null}
        </div>
      )}
    </>
  )
}
