"use client"

import { ArrowFatDown, ArrowFatUp } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { cn } from "@/lib/cn"
import type { VoteKind } from "@/lib/types"

type VoteState = {
  up: number
  down: number
  vote: VoteKind | null
}

function applyVote(state: VoteState, next: VoteKind | null): VoteState {
  const counts = { up: state.up, down: state.down }
  if (state.vote) counts[state.vote] = Math.max(0, counts[state.vote] - 1)
  if (next) counts[next] += 1
  return { ...counts, vote: next }
}

/**
 * Up/down vote pair with separate counters, used on posts and comments.
 * Optimistic: clicking the active arrow removes the vote, clicking the other
 * one swaps it (both counters adjust); rolls back when the request fails.
 * A 401 redirects to /login instead of mutating.
 */
export function VoteButtons({
  targetType,
  targetId,
  upCount,
  downCount,
  viewerVote,
  size = "md",
}: {
  targetType: "post" | "comment"
  targetId: string
  upCount: number
  downCount: number
  viewerVote: VoteKind | null
  size?: "md" | "sm"
}) {
  const t = useTranslations("post")
  const router = useRouter()
  const [state, setState] = useState<VoteState>({
    up: upCount,
    down: downCount,
    vote: viewerVote,
  })
  const [, startTransition] = useTransition()

  function toggle(kind: VoteKind) {
    const next = state.vote === kind ? null : kind
    const previous = state
    setState(applyVote(state, next))

    startTransition(async () => {
      try {
        const endpoint = `/api/social/${targetType === "post" ? "posts" : "comments"}/${encodeURIComponent(targetId)}/reaction`
        const response = await fetch(endpoint, {
          method: next ? "PUT" : "DELETE",
          headers: next ? { "content-type": "application/json" } : undefined,
          body: next ? JSON.stringify({ kind: next }) : undefined,
        })
        if (response.status === 401) {
          setState(previous)
          router.push("/login")
          return
        }
        if (!response.ok) throw new Error("vote failed")
      } catch {
        setState(previous)
      }
    })
  }

  const compact = size === "sm"

  return (
    <div
      className={cn(
        "inline-flex items-center font-mono uppercase tracking-label",
        compact ? "gap-1 text-[10px]" : "gap-1.5 text-xs",
      )}
    >
      <button
        type="button"
        onClick={() => toggle("up")}
        aria-pressed={state.vote === "up"}
        aria-label={state.vote === "up" ? t("removeUpvote") : t("upvote")}
        className={cn(
          "inline-flex items-center gap-1 border bg-graphite transition-colors",
          compact ? "px-1.5 py-0.5" : "px-2 py-1",
          state.vote === "up"
            ? "border-acid bg-acid/15 text-acid"
            : "border-border-gray text-dim-white hover:border-acid hover:text-acid",
        )}
      >
        <ArrowFatUp size={compact ? 12 : 14} weight={state.vote === "up" ? "fill" : "regular"} aria-hidden />
        <span className="tabular-nums">{state.up}</span>
      </button>
      <button
        type="button"
        onClick={() => toggle("down")}
        aria-pressed={state.vote === "down"}
        aria-label={state.vote === "down" ? t("removeDownvote") : t("downvote")}
        className={cn(
          "inline-flex items-center gap-1 border bg-graphite transition-colors",
          compact ? "px-1.5 py-0.5" : "px-2 py-1",
          state.vote === "down"
            ? "border-violet bg-violet/15 text-violet"
            : "border-border-gray text-dim-white hover:border-violet hover:text-violet",
        )}
      >
        <ArrowFatDown size={compact ? 12 : 14} weight={state.vote === "down" ? "fill" : "regular"} aria-hidden />
        <span className="tabular-nums">{state.down}</span>
      </button>
    </div>
  )
}
