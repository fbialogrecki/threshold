"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { SignalButtonView } from "@/components/ui/signal-button-view"
import { recoverSession } from "@/lib/auth/recovery"
import {
  currentPageHref,
} from "@/lib/auth/routing"
import { mutationErrorKey } from "@/lib/auth/status"

export function BoostButton({
  targetId,
  initialCount,
  initialBoosted = false,
  loginHref,
}: {
  targetId: string
  initialCount: number
  initialBoosted?: boolean
  loginHref?: string
}) {
  const t = useTranslations("eventCard")
  const router = useRouter()
  const [count, setCount] = useState(initialCount)
  const [boosted, setBoosted] = useState(initialBoosted)
  const [flip, setFlip] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, startTransition] = useTransition()

  function handleBoost() {
    if (pending) return
    setError(null)
    if (loginHref) {
      router.push(loginHref)
      return
    }
    const next = !boosted
    setBoosted(next)
    setCount((value) => value + (next ? 1 : -1))
    if (next) {
      setFlip(true)
      window.setTimeout(() => setFlip(false), 320)
    }

    startTransition(async () => {
      try {
        const response = await fetch(`/api/events/${encodeURIComponent(targetId)}/boost`, {
          method: next ? "POST" : "DELETE",
        })
        if (response.status === 401) {
          setBoosted(!next)
          setCount((value) => value + (next ? -1 : 1))
          await recoverSession(currentPageHref(
            window.location.pathname,
            window.location.search,
            window.location.hash,
          ))
          return
        }
        if (!response.ok) {
          setBoosted(!next)
          setCount((value) => value + (next ? -1 : 1))
          setError(t(`errors.${mutationErrorKey(response.status)}`))
        }
      } catch {
        setBoosted(!next)
        setCount((value) => value + (next ? -1 : 1))
        setError(t("errors.network"))
      }
    })
  }

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <SignalButtonView
        active={boosted}
        count={count}
        flip={flip}
        onClick={handleBoost}
        disabled={pending}
        ariaLabel={boosted ? t("boosted") : t("boost")}
        ariaDescribedBy={error ? `event-boost-error-${targetId}` : undefined}
      />
      {error ? (
        <p
          id={`event-boost-error-${targetId}`}
          role="alert"
          className="max-w-56 text-xs leading-5 text-error"
        >
          {error}
        </p>
      ) : null}
    </div>
  )
}
