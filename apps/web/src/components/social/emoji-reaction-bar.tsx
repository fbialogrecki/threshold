"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState, useTransition } from "react"

import { cn } from "@/lib/cn"
import type { EmojiReaction } from "@/lib/types"

/** Mirrors the social service cap on distinct emojis per post. */
const MAX_DISTINCT_EMOJI = 20

const QUICK_PICKS = [
  "🔥", "🖤", "⚡", "💀", "🙌", "😈", "🌀", "🚪",
  "👁", "🦇", "💥", "🤝", "😭", "😂", "🫠", "🕳",
]

/**
 * Discord-style emoji reactions on a post, independent of up/down votes.
 * Chips toggle the viewer's reaction optimistically with rollback; the "+"
 * opens a lightweight picker (quick grid + free emoji input, no heavy deps).
 */
export function EmojiReactionBar({
  postId,
  reactions,
}: {
  postId: string
  reactions: EmojiReaction[]
}) {
  const t = useTranslations("post")
  const router = useRouter()
  const [items, setItems] = useState<EmojiReaction[]>(reactions)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [custom, setCustom] = useState("")
  const [, startTransition] = useTransition()
  const pickerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!pickerOpen) return
    function onPointerDown(event: PointerEvent) {
      if (!pickerRef.current?.contains(event.target as Node)) setPickerOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setPickerOpen(false)
    }
    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [pickerOpen])

  function applyToggle(list: EmojiReaction[], emoji: string, add: boolean): EmojiReaction[] {
    const existing = list.find((item) => item.emoji === emoji)
    if (add) {
      if (existing) {
        if (existing.viewerReacted) return list
        return list.map((item) =>
          item.emoji === emoji
            ? { ...item, count: item.count + 1, viewerReacted: true }
            : item,
        )
      }
      return [...list, { emoji, count: 1, viewerReacted: true }]
    }
    if (!existing?.viewerReacted) return list
    return list
      .map((item) =>
        item.emoji === emoji
          ? { ...item, count: item.count - 1, viewerReacted: false }
          : item,
      )
      .filter((item) => item.count > 0)
  }

  function toggle(emoji: string, add: boolean) {
    const previous = items
    setItems(applyToggle(items, emoji, add))
    setPickerOpen(false)
    setCustom("")

    startTransition(async () => {
      try {
        const base = `/api/social/posts/${encodeURIComponent(postId)}/emoji`
        const response = await fetch(
          add ? base : `${base}?emoji=${encodeURIComponent(emoji)}`,
          {
            method: add ? "PUT" : "DELETE",
            headers: add ? { "content-type": "application/json" } : undefined,
            body: add ? JSON.stringify({ emoji }) : undefined,
          },
        )
        if (response.status === 401) {
          setItems(previous)
          router.push("/login")
          return
        }
        if (!response.ok) throw new Error("emoji reaction failed")
      } catch {
        setItems(previous)
      }
    })
  }

  function onChipClick(item: EmojiReaction) {
    toggle(item.emoji, !item.viewerReacted)
  }

  function onPick(emoji: string) {
    const existing = items.find((item) => item.emoji === emoji)
    if (existing?.viewerReacted) {
      setPickerOpen(false)
      return
    }
    toggle(emoji, true)
  }

  function onCustomSubmit(event: React.FormEvent) {
    event.preventDefault()
    const emoji = custom.trim()
    if (!emoji) return
    onPick(emoji)
  }

  const atLimit = items.length >= MAX_DISTINCT_EMOJI
  if (items.length === 0 && atLimit) return null

  return (
    <div className="relative flex flex-wrap items-center justify-start gap-1.5">
      {/* "+" leads the row so reactions grow to the right from a fixed left anchor. */}
      {atLimit ? null : (
        <button
          type="button"
          onClick={() => setPickerOpen((open) => !open)}
          aria-expanded={pickerOpen}
          aria-label={t("addReaction")}
          className="inline-flex items-center border border-dashed border-border-gray bg-graphite px-2 py-0.5 font-mono text-xs text-muted transition-colors hover:border-acid hover:text-acid"
        >
          +
        </button>
      )}

      {items.map((item) => (
        <button
          key={item.emoji}
          type="button"
          onClick={() => onChipClick(item)}
          aria-pressed={item.viewerReacted}
          aria-label={item.viewerReacted
            ? t("removeReaction", { emoji: item.emoji })
            : t("addNamedReaction", { emoji: item.emoji })}
          className={cn(
            "inline-flex items-center gap-1.5 border px-2 py-0.5 font-mono text-xs transition-colors",
            item.viewerReacted
              ? "border-acid bg-acid/15 text-acid"
              : "border-border-gray bg-graphite text-dim-white hover:border-acid",
          )}
        >
          <span>{item.emoji}</span>
          <span className="tabular-nums">{item.count}</span>
        </button>
      ))}

      {pickerOpen ? (
        <div
          ref={pickerRef}
          className="absolute right-0 top-full z-20 mt-2 w-64 max-w-[calc(100vw-2rem)] border border-border-gray bg-pitch p-3 shadow-[0_8px_24px_rgba(0,0,0,0.6)]"
        >
          <div className="grid grid-cols-8 gap-1">
            {QUICK_PICKS.map((emoji) => (
              <button
                key={emoji}
                type="button"
                onClick={() => onPick(emoji)}
                aria-label={t("reactWith", { emoji })}
                className="flex h-7 w-7 items-center justify-center text-base hover:bg-graphite"
              >
                {emoji}
              </button>
            ))}
          </div>
          <form onSubmit={onCustomSubmit} className="mt-2 flex gap-1">
            <input
              value={custom}
              onChange={(event) => setCustom(event.target.value)}
              maxLength={32}
              placeholder={t("customEmojiPlaceholder")}
              aria-label={t("customEmoji")}
              className="min-w-0 flex-1 border border-border-gray bg-graphite px-2 py-1 text-sm text-raw-white placeholder:text-muted focus:border-acid focus:outline-none"
            />
            <button
              type="submit"
              disabled={!custom.trim()}
              className="border border-border-gray px-2 py-1 font-mono text-[11px] uppercase tracking-label text-dim-white hover:border-acid hover:text-acid disabled:opacity-40"
            >
              {t("add")}
            </button>
          </form>
        </div>
      ) : null}
    </div>
  )
}
