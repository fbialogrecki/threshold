"use client"

import { X } from "@phosphor-icons/react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { useEffect, useId, useRef } from "react"

import { LogoutButton } from "@/components/auth/logout-button"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { Avatar } from "@/components/ui/avatar"
import { mediaDerivativeUrl } from "@/lib/media/urls"

/**
 * Account actions on mobile: profile, settings, language and logout. This is
 * the only place a phone can reach logout and the locale switcher, so it stays
 * a sheet with its own focus trap; only its trigger moved to the top bar.
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
    "flex items-center justify-between border-b border-border-gray px-4 py-3.5 font-mono text-sm uppercase tracking-label text-dim-white hover:text-acid"

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        type="button"
        aria-label={shell("closeAccountMenu")}
        onClick={onClose}
        className="absolute inset-0 bg-pitch/80"
      />
      <div
        ref={sheetRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="absolute inset-x-0 bottom-0 border-t-2 border-acid bg-pitch pb-[env(safe-area-inset-bottom)]"
      >
        <div className="flex items-center justify-between border-b border-border-gray px-4 py-3">
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
              {city ? (
                <p className="truncate font-mono text-[10px] uppercase tracking-label text-muted">
                  {city}
                </p>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <LocaleSwitcher />
            <button
              type="button"
              onClick={onClose}
              aria-label={actions("close")}
              className="p-2 text-muted hover:text-raw-white focus-visible:text-raw-white"
            >
              <X size={18} weight="bold" aria-hidden />
            </button>
          </div>
        </div>
        <nav aria-label={shell("accountNavigation")}>
          {username ? (
            <Link
              href={`/u/${encodeURIComponent(username)}`}
              className={linkClass}
              onClick={onClose}
            >
              {navigation("profile")} <span aria-hidden>→</span>
            </Link>
          ) : null}
          <Link href="/app/settings" className={linkClass} onClick={onClose}>
            {navigation("settings")} <span aria-hidden>→</span>
          </Link>
          <div className="px-4 py-3.5">
            <LogoutButton className="text-sm" />
          </div>
        </nav>
      </div>
    </div>
  )
}
