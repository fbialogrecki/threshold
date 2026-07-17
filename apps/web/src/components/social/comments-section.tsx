"use client"

import { PencilSimple, Trash } from "@phosphor-icons/react"
import { useLocale, useTranslations } from "next-intl"
import Link from "next/link"
import type { FormEvent, ReactNode } from "react"
import { useState, useTransition } from "react"

import { CommentComposer } from "@/components/social/comment-composer"
import { RichText } from "@/components/social/rich-text"
import { VoteButtons } from "@/components/social/vote-buttons"
import { Avatar } from "@/components/ui/avatar"
import { formatRelative } from "@/lib/format"
import { profileHref } from "@/lib/profile-href"
import type { Comment, ProfileRef } from "@/lib/types"

type RawComment = {
  id: string
  post_id: string
  parent_id?: string | null
  author_user_id: string
  author_username: string
  author_display_name: string
  author_type: string
  body: string
  created_at: string
  edited_at?: string | null
  up_count?: number
  down_count?: number
  viewer_vote?: string | null
  viewer_is_author?: boolean
  mentions?: {
    mention_type: string
    target_handle: string
    target_id?: string | null
    display_name?: string | null
    target_url?: string | null
    start_index?: number | null
    end_index?: number | null
  }[]
}

function mapRawComment(raw: RawComment): Comment {
  const author: ProfileRef = {
    id: raw.author_user_id,
    type: raw.author_type === "artist" ? "artist" : "consumer",
    handle: raw.author_username,
    displayName: raw.author_display_name,
  }
  return {
    id: raw.id,
    postId: raw.post_id,
    parentId: raw.parent_id ?? null,
    author,
    createdAtIso: raw.created_at,
    editedAtIso: raw.edited_at ?? null,
    body: raw.body,
    mentions: (raw.mentions ?? []).flatMap((mention) =>
      typeof mention === "object"
        && mention !== null
        && typeof mention.mention_type === "string"
        && typeof mention.target_handle === "string"
        ? [{
            mentionType: mention.mention_type,
            targetHandle: mention.target_handle,
            targetId: mention.target_id ?? null,
            displayName: mention.display_name ?? null,
            targetUrl: mention.target_url ?? null,
            startIndex: mention.start_index ?? null,
            endIndex: mention.end_index ?? null,
          }]
        : [],
    ),
    upCount: raw.up_count ?? 0,
    downCount: raw.down_count ?? 0,
    viewerVote: raw.viewer_vote === "up" || raw.viewer_vote === "down" ? raw.viewer_vote : null,
    viewerIsAuthor: Boolean(raw.viewer_is_author),
  }
}

function isRawComment(value: unknown): value is RawComment {
  const raw = value as Partial<RawComment>
  return (
    typeof value === "object" &&
    value !== null &&
    typeof raw.id === "string" &&
    typeof raw.post_id === "string" &&
    typeof raw.author_user_id === "string" &&
    typeof raw.author_username === "string" &&
    typeof raw.author_display_name === "string" &&
    typeof raw.author_type === "string" &&
    typeof raw.body === "string" &&
    typeof raw.created_at === "string" &&
    (raw.mentions === undefined || Array.isArray(raw.mentions))
  )
}

type ReplyTarget = {
  /** comment the reply is attached to (depth is capped at two levels) */
  parentId: string
  prefill: string
}

/** Maximum reply depth: comment (0) -> reply (1) -> reply-to-reply (2). */
const MAX_DEPTH = 2

const COMMENT_ACTION_CLASS =
  "font-mono text-[10px] uppercase tracking-label text-muted hover:text-acid"

type CommentMode = "view" | "edit" | "confirm-delete"

function CommentItem({
  comment,
  depth,
  onReply,
  onEdited,
  onDeleted,
}: {
  comment: Comment
  depth: number
  onReply: (target: ReplyTarget) => void
  onEdited: (id: string, body: string) => void
  onDeleted: (id: string) => void
}) {
  const t = useTranslations("post")
  const locale = useLocale()
  const [mode, setMode] = useState<CommentMode>("view")
  const [draft, setDraft] = useState(comment.body)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  // Replying to a max-depth comment joins the same thread with an @mention;
  // anything shallower nests one level deeper under the clicked comment.
  const replyTarget: ReplyTarget =
    depth >= MAX_DEPTH
      ? { parentId: comment.parentId ?? comment.id, prefill: `@${comment.author.handle} ` }
      : { parentId: comment.id, prefill: "" }

  function saveEdit(event: FormEvent) {
    event.preventDefault()
    const next = draft.trim()
    if (!next || next === comment.body) {
      setMode("view")
      setDraft(comment.body)
      return
    }
    setError(null)
    startTransition(async () => {
      try {
        const response = await fetch(
          `/api/social/comments/${encodeURIComponent(comment.id)}`,
          {
            method: "PATCH",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ body: next }),
          },
        )
        if (!response.ok) throw new Error("edit failed")
        onEdited(comment.id, next)
        setMode("view")
      } catch {
        setError(t("commentEditError"))
      }
    })
  }

  function confirmDelete() {
    setError(null)
    startTransition(async () => {
      try {
        const response = await fetch(
          `/api/social/comments/${encodeURIComponent(comment.id)}`,
          { method: "DELETE" },
        )
        if (!response.ok && response.status !== 204) throw new Error("delete failed")
        onDeleted(comment.id)
      } catch {
        setError(t("commentDeleteError"))
        setMode("view")
      }
    })
  }

  return (
    <div className="flex gap-2.5">
      <Link href={profileHref(comment.author)}>
        <Avatar name={comment.author.displayName} size="sm" />
      </Link>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <Link
            href={profileHref(comment.author)}
            className="min-w-0 truncate font-display text-base tracking-wide text-raw-white hover:text-acid"
          >
            {comment.author.displayName}
          </Link>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <span className="font-mono text-[11px] text-muted">
              {formatRelative(comment.createdAtIso, locale)}
              {comment.editedAtIso ? ` · ${t("edited")}` : ""}
            </span>
            {comment.viewerIsAuthor && mode !== "edit" ? (
              mode === "confirm-delete" ? (
                <>
                  <span className="font-mono text-[10px] uppercase tracking-label text-error">
                    {t("deleteConfirm")}
                  </span>
                  <button
                    type="button"
                    onClick={confirmDelete}
                    disabled={pending}
                    className="font-mono text-[10px] uppercase tracking-label text-error hover:text-raw-white"
                  >
                    {pending ? "…" : t("yes")}
                  </button>
                  <button type="button" onClick={() => setMode("view")} className={COMMENT_ACTION_CLASS}>
                    {t("no")}
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      setDraft(comment.body)
                      setMode("edit")
                    }}
                    className={`${COMMENT_ACTION_CLASS} inline-flex items-center gap-1`}
                  >
                    <PencilSimple size={12} aria-hidden />
                    {t("edit")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("confirm-delete")}
                    className={`${COMMENT_ACTION_CLASS} inline-flex items-center gap-1`}
                  >
                    <Trash size={12} aria-hidden />
                    {t("delete")}
                  </button>
                </>
              )
            ) : null}
          </div>
        </div>

        {mode === "edit" ? (
          <CommentEditForm
            draft={draft}
            pending={pending}
            onDraftChange={setDraft}
            onSubmit={saveEdit}
            onCancel={() => {
              setMode("view")
              setDraft(comment.body)
            }}
          />
        ) : (
          <p className="mt-1 text-[15px] leading-6 text-dim-white">
            <RichText text={comment.body} mentions={comment.mentions} />
          </p>
        )}

        {error ? (
          <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-error">
            {error}
          </p>
        ) : null}

        {mode !== "edit" ? (
          <CommentActions
            comment={comment}
            replyTarget={replyTarget}
            onReply={onReply}
          />
        ) : null}
      </div>
    </div>
  )
}

function CommentEditForm({
  draft,
  pending,
  onDraftChange,
  onSubmit,
  onCancel,
}: {
  draft: string
  pending: boolean
  onDraftChange: (value: string) => void
  onSubmit: (event: FormEvent) => void
  onCancel: () => void
}) {
  const t = useTranslations("post")
  return (
    <form onSubmit={onSubmit} className="mt-1">
      <textarea
        value={draft}
        onChange={(event) => onDraftChange(event.target.value)}
        rows={2}
        maxLength={1000}
        autoFocus
        aria-label={t("editComment")}
        className="w-full resize-none border border-border-gray bg-pitch p-2 text-sm leading-6 text-raw-white focus:border-acid focus:outline-none"
      />
      <div className="mt-1 flex items-center gap-3">
        <button type="submit" disabled={pending} className={COMMENT_ACTION_CLASS}>
          {pending ? t("saving") : t("save")}
        </button>
        <button type="button" onClick={onCancel} className={COMMENT_ACTION_CLASS}>
          {t("cancel")}
        </button>
      </div>
    </form>
  )
}

function CommentActions({
  comment,
  replyTarget,
  onReply,
}: {
  comment: Comment
  replyTarget: ReplyTarget
  onReply: (target: ReplyTarget) => void
}) {
  const t = useTranslations("post")
  return (
    <div className="mt-1.5 flex items-center gap-3">
      <VoteButtons
        targetType="comment"
        targetId={comment.id}
        upCount={comment.upCount}
        downCount={comment.downCount}
        viewerVote={comment.viewerVote}
        size="sm"
      />
      <button type="button" onClick={() => onReply(replyTarget)} className={COMMENT_ACTION_CLASS}>
        {t("reply")}
      </button>
    </div>
  )
}

/**
 * Inline comments under a post: a toggle that lazily loads the thread, with
 * up to two levels of replies indented under their parents and per-thread
 * reply composers. The /posts/[id] deep-link reuses it with SSR initialComments.
 */
export function CommentsSection({
  postId,
  commentCount,
  initialComments,
  defaultOpen = false,
  reactions,
  votes,
}: {
  postId: string
  commentCount: number
  initialComments?: Comment[]
  defaultOpen?: boolean
  reactions?: ReactNode
  votes?: ReactNode
}) {
  const t = useTranslations("post")
  const [open, setOpen] = useState(defaultOpen)
  const [comments, setComments] = useState<Comment[] | null>(initialComments ?? null)
  const [count, setCount] = useState(commentCount)
  const [error, setError] = useState<string | null>(null)
  const [replyTarget, setReplyTarget] = useState<ReplyTarget | null>(null)
  const [loading, startTransition] = useTransition()

  function load() {
    startTransition(async () => {
      try {
        const response = await fetch(
          `/api/social/posts/${encodeURIComponent(postId)}/comments`,
        )
        if (!response.ok) throw new Error("comments failed")
        const body: unknown = await response.json()
        setComments(Array.isArray(body) ? body.filter(isRawComment).map(mapRawComment) : [])
        setError(null)
      } catch {
        setError(t("commentsLoadError"))
      }
    })
  }

  function toggleOpen() {
    const next = !open
    setOpen(next)
    if (next && comments === null) load()
  }

  function onCreated(raw: unknown) {
    if (isRawComment(raw)) {
      setComments((current) => [...(current ?? []), mapRawComment(raw)])
      setCount((value) => value + 1)
    }
    setReplyTarget(null)
  }

  function onEdited(id: string, body: string) {
    setComments((current) =>
      (current ?? []).map((comment) =>
        comment.id === id
          ? { ...comment, body, editedAtIso: new Date().toISOString() }
          : comment,
      ),
    )
  }

  function onDeleted(id: string) {
    const all = comments ?? []
    // The backend cascades replies with the comment, so drop the subtree.
    const removed = new Set<string>([id])
    let grew = true
    while (grew) {
      grew = false
      for (const comment of all) {
        if (comment.parentId && removed.has(comment.parentId) && !removed.has(comment.id)) {
          removed.add(comment.id)
          grew = true
        }
      }
    }
    setComments(all.filter((comment) => !removed.has(comment.id)))
    setCount((value) => Math.max(0, value - removed.size))
  }

  const topLevel = (comments ?? []).filter((comment) => !comment.parentId)
  const repliesByParent = new Map<string, Comment[]>()
  for (const comment of comments ?? []) {
    if (!comment.parentId) continue
    const thread = repliesByParent.get(comment.parentId) ?? []
    thread.push(comment)
    repliesByParent.set(comment.parentId, thread)
  }
  // Threads read top-down: replies chronological inside a thread.
  for (const thread of repliesByParent.values()) {
    thread.sort((a, b) => a.createdAtIso.localeCompare(b.createdAtIso))
  }

  // Flatten threads depth-first, then group consecutive same-depth rows into
  // segments. Each indented segment draws its own single guide line, so a
  // deeper thread ends the outer line instead of running parallel to it.
  type Row =
    | { kind: "comment"; comment: Comment; depth: number }
    | { kind: "composer"; parentId: string; depth: number; prefill: string }

  const rows: Row[] = []
  function flatten(comment: Comment, depth: number) {
    rows.push({ kind: "comment", comment, depth })
    for (const child of repliesByParent.get(comment.id) ?? []) {
      flatten(child, Math.min(depth + 1, MAX_DEPTH))
    }
    if (replyTarget?.parentId === comment.id) {
      rows.push({
        kind: "composer",
        parentId: comment.id,
        depth: Math.min(depth + 1, MAX_DEPTH),
        prefill: replyTarget.prefill,
      })
    }
  }
  for (const comment of topLevel) flatten(comment, 0)

  const segments: { depth: number; rows: Row[] }[] = []
  for (const row of rows) {
    const last = segments[segments.length - 1]
    if (last && last.depth === row.depth) last.rows.push(row)
    else segments.push({ depth: row.depth, rows: [row] })
  }

  const INDENT: Record<number, string> = {
    1: "ml-8 border-l border-border-gray pl-3",
    2: "ml-16 border-l border-border-gray pl-3",
  }

  function renderRow(row: Row): ReactNode {
    if (row.kind === "comment") {
      return (
        <CommentItem
          key={row.comment.id}
          comment={row.comment}
          depth={row.depth}
          onReply={setReplyTarget}
          onEdited={onEdited}
          onDeleted={onDeleted}
        />
      )
    }
    return (
      <CommentComposer
        key={`composer-${row.parentId}`}
        postId={postId}
        parentId={row.parentId}
        initialValue={row.prefill}
        autoFocus
        compact
        onCreated={onCreated}
      />
    )
  }

  return (
    <div className="mt-3">
      <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={toggleOpen}
          aria-expanded={open}
          className="font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid"
        >
          {t("commentCount", { count })} {open ? "▴" : "▾"}
        </button>
        <div className="flex min-w-0 items-center justify-between gap-3 sm:flex-1 sm:justify-end">
          {reactions ? <div className="min-w-0 flex-1 sm:flex-none">{reactions}</div> : null}
          {votes}
        </div>
      </div>

      {open ? (
        <div className="mt-3 flex flex-col gap-3 border-t border-border-gray pt-3">
          <CommentComposer postId={postId} onCreated={onCreated} compact />

          {loading && comments === null ? (
            <p className="font-mono text-[11px] uppercase tracking-label text-muted">
              {t("commentsLoading")}
            </p>
          ) : null}
          {error ? (
            <p className="font-mono text-[11px] uppercase tracking-label text-error">
              {error}
            </p>
          ) : null}

          {comments !== null && topLevel.length === 0 ? (
            <p className="text-sm leading-6 text-muted">
              {t("commentsEmpty")}
            </p>
          ) : null}

          {segments.map((segment) => {
            const first = segment.rows[0]
            const key =
              first.kind === "comment"
                ? `${segment.depth}-${first.comment.id}`
                : `${segment.depth}-composer-${first.parentId}`
            return (
              <div
                key={key}
                className={`flex flex-col gap-3 ${INDENT[segment.depth] ?? ""}`}
              >
                {segment.rows.map(renderRow)}
              </div>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
