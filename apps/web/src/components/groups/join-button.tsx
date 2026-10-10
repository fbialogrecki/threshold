"use client"

import { Check, Plus } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { Spinner } from "@/components/ui/field"
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
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <button
        type="button"
        onClick={onClick}
        aria-pressed={joined}
        disabled={pending}
        className={cn(
          "inline-flex min-h-11 items-center gap-2 rounded-control border px-5 text-[15px] font-semibold transition-[color,background-color,border-color,scale] duration-150 ease-press active:scale-[0.97] disabled:opacity-60",
          joined
            ? "border-acid/50 bg-acid/10 text-acid hover:border-acid"
            : "border-acid bg-acid text-pitch hover:bg-acid-bright",
        )}
      >
        {pending ? (
          <Spinner />
        ) : joined ? (
          <Check size={16} weight="bold" aria-hidden />
        ) : (
          <Plus size={16} weight="bold" aria-hidden />
        )}
        {pending ? t("pending") : t(joined ? "joined" : "join")}
      </button>
      {error ? <p role="alert" className="max-w-64 text-sm text-orange">{error}</p> : null}
    </div>
  )
}
