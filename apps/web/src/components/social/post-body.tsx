"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import type { ReactNode } from "react"
import { useState, useTransition } from "react"

import { OwnerMenu } from "@/components/social/owner-menu"
import { RichText } from "@/components/social/rich-text"
import type { MentionRef } from "@/lib/types"

const MAX_BODY = 2000

/**
 * Post body with owner controls: the author (viewer_is_author from the
 * social service, enforced server-side too) can edit inline or delete from the
 * owner menu. Everyone else sees plain text.
 */
export function PostBody({
  postId,
  body,
  mentions,
  editedAtIso,
  viewerIsAuthor,
  identity,
  redirectHomeOnDelete = false,
}: {
  postId: string
  body: string
  mentions: MentionRef[]
  editedAtIso: string | null
  viewerIsAuthor: boolean
  /** author name, handle and age as one block; the row height matches the avatar */
  identity: ReactNode
  /** set on /posts/[id]: the page disappears with the post */
  redirectHomeOnDelete?: boolean
}) {
  const t = useTranslations("post")
  const router = useRouter()
  const [text, setText] = useState(body)
  const [edited, setEdited] = useState(editedAtIso !== null)
  const [mode, setMode] = useState<"view" | "edit">("view")
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
      }
    })
  }

  const actionClass =
    "font-mono text-[10px] uppercase tracking-label text-muted hover:text-acid"

  return (
    <>
      {/* Row height matches the avatar so the first text line centres on it. */}
      <div className="flex min-h-10 items-center gap-3">
        <div className="min-w-0 flex-1">{identity}</div>
        {viewerIsAuthor && mode !== "edit" ? (
          <OwnerMenu
            pending={pending}
            onEdit={() => {
              setDraft(text)
              setMode("edit")
            }}
            onDelete={confirmDelete}
          />
        ) : null}
      </div>
      {mode === "edit" ? (
        <form onSubmit={saveEdit} className="mt-1.5">
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={4}
            maxLength={MAX_BODY}
            autoFocus
            aria-label={t("editPost")}
            className="w-full resize-none border border-border-gray p-2 text-sm leading-6 text-raw-white focus:border-acid focus:outline-none"
          />
          {error ? (
            <p className="mt-1 text-sm text-error">{error}</p>
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
        <div className="mt-1.5">
          <p className="text-[15px] leading-7 text-raw-white">
            <RichText text={text} mentions={mentions} />
            {edited ? (
              <span className="ml-2 font-mono text-[10px] uppercase tracking-label text-muted">
                {t("edited")}
              </span>
            ) : null}
          </p>
          {error ? <p className="mt-1 text-sm text-error">{error}</p> : null}
        </div>
      )}
    </>
  )
}
