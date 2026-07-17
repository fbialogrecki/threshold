"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { cn } from "@/lib/cn"

export function JoinButton({
  slug,
  isAuthenticated,
  initialJoined = false,
}: {
  slug: string
  isAuthenticated: boolean
  initialJoined?: boolean
}) {
  const router = useRouter()
  const t = useTranslations("groupDetail.membership")
  const [joined, setJoined] = useState(initialJoined)
  const [error, setError] = useState("")
  const [pending, startTransition] = useTransition()

  function onClick() {
    if (!isAuthenticated) {
      router.push("/login")
      return
    }

    const next = !joined
    setError("")
    setJoined(next)
    startTransition(async () => {
      try {
        const response = await fetch(
          `/api/social/groups/${encodeURIComponent(slug)}/membership`,
          { method: next ? "POST" : "DELETE" },
        )
        if (!response.ok) throw new Error("membership failed")
        router.refresh()
      } catch {
        setJoined(!next)
        setError(t("error"))
      }
    })
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        type="button"
        onClick={onClick}
        aria-pressed={joined}
        disabled={pending}
        className={cn(
          "border px-4 py-2 font-mono text-xs uppercase tracking-label transition-colors disabled:opacity-50",
          joined
            ? "border-acid bg-acid text-pitch"
            : "border-acid text-acid hover:bg-acid hover:text-pitch",
        )}
      >
        {pending ? t("pending") : t(joined ? "joined" : "join")}
      </button>
      {error ? <p role="alert" className="text-xs text-error">{error}</p> : null}
    </div>
  )
}
