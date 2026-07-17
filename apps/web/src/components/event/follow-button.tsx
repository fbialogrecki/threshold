"use client"

import { Bell, BellRinging } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { recoverSession } from "@/lib/auth/recovery"
import {
  currentPageHref,
} from "@/lib/auth/routing"
import { mutationErrorKey } from "@/lib/auth/status"
import { cn } from "@/lib/cn"

export function EventFollowButton({
  slug,
  initialFollowing = false,
  loginHref,
}: {
  slug: string
  initialFollowing?: boolean
  loginHref?: string
}) {
  const t = useTranslations("eventCard")
  const router = useRouter()
  const [following, setFollowing] = useState(initialFollowing)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  function onClick() {
    if (pending) return
    setError(null)
    if (loginHref) {
      router.push(loginHref)
      return
    }
    const next = !following
    setFollowing(next)
    startTransition(async () => {
      try {
        const response = await fetch(`/api/events/${encodeURIComponent(slug)}/follow`, {
          method: next ? "POST" : "DELETE",
        })
        if (response.status === 401) {
          setFollowing(!next)
          await recoverSession(currentPageHref(
            window.location.pathname,
            window.location.search,
            window.location.hash,
          ))
          return
        }
        if (!response.ok) {
          setFollowing(!next)
          setError(t(`errors.${mutationErrorKey(response.status)}`))
        }
      } catch {
        setFollowing(!next)
        setError(t("errors.network"))
      }
    })
  }

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={onClick}
        aria-pressed={following}
        aria-describedby={error ? `event-follow-error-${slug}` : undefined}
        disabled={pending}
        className={cn(
          "inline-flex items-center gap-2 border px-4 py-2 font-mono text-xs uppercase tracking-label transition-colors disabled:opacity-50",
          following
            ? "border-violet bg-violet text-pitch"
            : "border-violet text-violet hover:bg-violet hover:text-pitch",
        )}
      >
        {following
          ? <BellRinging size={16} weight="bold" aria-hidden />
          : <Bell size={16} weight="bold" aria-hidden />}
        {following ? t("following") : t("follow")}
      </button>
      {error ? (
        <p
          id={`event-follow-error-${slug}`}
          role="alert"
          className="max-w-56 text-xs leading-5 text-error"
        >
          {error}
        </p>
      ) : null}
    </div>
  )
}
