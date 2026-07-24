"use client"

import { DotsThree, PencilSimple, Trash } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useEffect, useRef, useState } from "react"

/**
 * Owner controls for a post or comment, behind a disclosure. Keeping edit and
 * especially delete out of the identity line stops a destructive action from
 * sitting one tap away from the author's name, and gives the name the room it
 * needs on narrow screens. Delete confirms inside the menu.
 */
export function OwnerMenu({
  onEdit,
  onDelete,
  pending = false,
}: {
  onEdit: () => void
  onDelete: () => void
  pending?: boolean
}) {
  const t = useTranslations("post")
  // One state, so closing the menu cannot leave a stale confirm step behind.
  const [mode, setMode] = useState<"closed" | "actions" | "confirm">("closed")
  const containerRef = useRef<HTMLDivElement | null>(null)
  const open = mode !== "closed"

  useEffect(() => {
    if (!open) return
    function onPointerDown(event: PointerEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setMode("closed")
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setMode("closed")
    }
    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [open])

  const itemClass =
    "flex w-full items-center gap-2 px-3 py-2.5 text-left font-mono text-[11px] uppercase tracking-label"

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setMode((value) => (value === "closed" ? "actions" : "closed"))}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={t("ownerActions")}
        className="flex h-7 w-7 items-center justify-center text-muted transition-colors hover:text-raw-white focus-visible:text-raw-white"
      >
        <DotsThree size={20} weight="bold" aria-hidden />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-8 z-20 w-40 border border-border-gray bg-pitch"
        >
          {mode === "confirm" ? (
            <>
              <p className="border-b border-border-gray px-3 py-2.5 font-mono text-[11px] uppercase tracking-label text-error">
                {t("deleteConfirm")}
              </p>
              <button
                type="button"
                role="menuitem"
                onClick={onDelete}
                disabled={pending}
                className={`${itemClass} text-error hover:text-raw-white disabled:opacity-50`}
              >
                <Trash size={13} aria-hidden />
                {pending ? t("deleting") : t("yes")}
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => setMode("actions")}
                className={`${itemClass} border-t border-border-gray text-dim-white hover:text-raw-white`}
              >
                {t("no")}
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMode("closed")
                  onEdit()
                }}
                className={`${itemClass} text-dim-white hover:text-acid`}
              >
                <PencilSimple size={13} aria-hidden />
                {t("edit")}
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => setMode("confirm")}
                className={`${itemClass} border-t border-border-gray text-error hover:text-raw-white`}
              >
                <Trash size={13} aria-hidden />
                {t("delete")}
              </button>
            </>
          )}
        </div>
      ) : null}
    </div>
  )
}
