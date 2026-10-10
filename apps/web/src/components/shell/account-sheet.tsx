"use client"

import { GearSix, SignOut, UserCircle, X } from "@phosphor-icons/react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { useEffect, useId, useRef } from "react"

import { LogoutButton } from "@/components/auth/logout-button"
import { Avatar } from "@/components/ui/avatar"
import { mediaDerivativeUrl } from "@/lib/media/urls"

/**
 * Account actions on mobile: profile, settings and logout. Language moved into
 * Settings, so this is the only place a phone can reach logout; it stays a
 * sheet with its own focus trap and only its trigger moved to the top bar.
 * Escape and backdrop click close it; focus is restored on unmount.
 */
export function AccountSheet({
  username,
  name,
  avatarMediaAssetId,
  city,
  onClose,
}: {
  username: string | null
  name: string
  avatarMediaAssetId: string | null
  city: string | null
  onClose: () => void
}) {
  const sheetRef = useRef<HTMLDivElement | null>(null)
  const titleId = useId()
  const navigation = useTranslations("navigation")
  const actions = useTranslations("actions")
  const shell = useTranslations("shell")
  const auth = useTranslations("auth")

  useEffect(() => {
    const sheet = sheetRef.current
    const previousFocus = document.activeElement as HTMLElement | null
    const previousOverflow = document.body.style.overflow
    const focusables = () =>
      Array.from(
        sheet?.querySelectorAll<HTMLElement>("a[href], button:not([disabled])") ?? [],
      )
    document.body.style.overflow = "hidden"
    const frame = window.requestAnimationFrame(() => focusables()[0]?.focus())

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key !== "Tab") return
      const items = focusables()
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (!sheet?.contains(document.activeElement)) {
        event.preventDefault()
        const target = event.shiftKey ? last : first
        target.focus()
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    document.addEventListener("keydown", onKeyDown)
    return () => {
      window.cancelAnimationFrame(frame)
      document.removeEventListener("keydown", onKeyDown)
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus()
    }
  }, [onClose])

  const linkClass =
    "flex min-h-12 items-center gap-3 rounded-control px-3 text-[15px] font-medium text-raw-white transition-colors hover:bg-raised"

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        type="button"
        aria-label={shell("closeAccountMenu")}
        onClick={onClose}
        className="absolute inset-0 animate-fade bg-pitch/80 backdrop-blur-sm"
      />
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="absolute inset-x-0 bottom-0 animate-sheet overscroll-contain rounded-t-surface border-t border-border-gray bg-graphite px-2 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-2"
      >
        <span aria-hidden className="mx-auto mb-1 block h-1 w-10 rounded-full bg-status-neutral-border" />
        <div className="flex items-center justify-between border-b border-border-gray px-2 pb-3 pt-2">
          <div className="flex min-w-0 items-center gap-3">
            <Avatar
              name={name}
              imageUrl={
                avatarMediaAssetId ? mediaDerivativeUrl(avatarMediaAssetId, "avatar_256") : null
              }
              size="sm"
            />
            <div className="min-w-0">
              <p id={titleId} className="truncate text-[15px] font-semibold text-raw-white">
                {name || navigation("you")}
              </p>
              {city ? <p className="truncate text-[13px] text-muted">{city}</p> : null}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={actions("close")}
            className="grid size-11 place-items-center rounded-full text-muted transition-colors hover:bg-raised hover:text-raw-white focus-visible:text-raw-white"
          >
            <X size={18} weight="bold" aria-hidden />
          </button>
        </div>
        <nav aria-label={shell("accountNavigation")} className="flex flex-col gap-0.5 pt-2">
          {username ? (
            <Link
              href={`/u/${encodeURIComponent(username)}`}
              className={linkClass}
              onClick={onClose}
            >
              <UserCircle size={20} className="text-muted" aria-hidden />
              {navigation("profile")}
            </Link>
          ) : null}
          <Link href="/app/settings" className={linkClass} onClick={onClose}>
            <GearSix size={20} className="text-muted" aria-hidden />
            {navigation("settings")}
          </Link>
          <LogoutButton className="flex min-h-12 w-full items-center gap-3 rounded-control px-3 text-left text-[15px] font-medium text-dim-white transition-colors hover:bg-raised hover:text-orange">
            <SignOut size={20} aria-hidden />
            {auth("logout")}
          </LogoutButton>
        </nav>
      </div>
    </div>
  )
}
