"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { recoverSession } from "@/lib/auth/recovery"
import {
  currentPageHref,
} from "@/lib/auth/routing"
import { mutationErrorKey } from "@/lib/auth/status"
import { cn } from "@/lib/cn"

type FollowTargetType = "artist" | "consumer" | "page"

export function FollowButton({
  handle,
  targetType,
  loginHref,
  initialFollowing = false,
}: {
  handle: string
  targetType: FollowTargetType
  loginHref?: string
  initialFollowing?: boolean
}) {
  const t = useTranslations("profileActions")
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
        const response = await fetch("/api/follow", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ handle, targetType, follow: next }),
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
        aria-describedby={error ? `profile-follow-error-${handle}` : undefined}
        disabled={pending}
        className={cn(
          "border px-4 py-2 font-mono text-xs uppercase tracking-label transition-colors disabled:opacity-50",
          following
            ? "border-acid bg-acid text-pitch"
            : "border-acid text-acid hover:bg-acid hover:text-pitch",
        )}
      >
        {following ? t("following") : t("follow")}
      </button>
      {error ? (
        <p
          id={`profile-follow-error-${handle}`}
          role="alert"
          className="max-w-56 text-xs leading-5 text-error"
        >
          {error}
        </p>
      ) : null}
    </div>
  )
}
