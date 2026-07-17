"use client"

import {
  Bell,
  CalendarDots,
  House,
  Plus,
  UserCircle,
  X,
} from "@phosphor-icons/react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { usePathname } from "next/navigation"
import { useCallback, useEffect, useId, useRef, useState } from "react"

import { LogoutButton } from "@/components/auth/logout-button"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { isNavActive } from "@/components/shell/nav-active"
import { Avatar } from "@/components/ui/avatar"
import { cn } from "@/lib/cn"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import { unreadBadgeLabel } from "@/lib/notifications"

const ITEMS = [
  { href: "/app", label: "feed", icon: House },
  { href: "/app/events", label: "events", icon: CalendarDots },
  { href: "/app/compose", label: "post", icon: Plus },
  { href: "/app/notifications", label: "notifications", icon: Bell },
] as const

/**
 * Bottom sheet behind "You": account actions stay out of the five-item bar.
 * Escape and backdrop click close it; focus is trapped and restored.
 */
function YouSheet({
  username,
  displayName,
  avatarMediaAssetId,
  city,
  onClose,
}: {
  username: string | null
  displayName: string
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
    "flex items-center justify-between border-b border-border-gray px-4 py-3.5 font-mono text-sm uppercase tracking-label text-dim-white hover:bg-raised hover:text-raw-white"

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
        className="absolute inset-x-0 bottom-0 border-t-2 border-acid bg-graphite pb-[env(safe-area-inset-bottom)]"
      >
        <div className="flex items-center justify-between border-b border-border-gray px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <Avatar
              name={displayName}
              imageUrl={
                avatarMediaAssetId
                  ? mediaDerivativeUrl(avatarMediaAssetId, "avatar_256")
                  : null
              }
              size="sm"
            />
            <div className="min-w-0">
              <p
                id={titleId}
                className="truncate font-display text-lg tracking-wide text-raw-white"
              >
                {displayName || navigation("you")}
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
            <Link href={`/u/${encodeURIComponent(username)}`} className={linkClass} onClick={onClose}>
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

export function MobileNav({
  username,
  displayName,
  avatarMediaAssetId,
  city,
  unreadCount,
}: {
  username: string | null
  displayName: string
  avatarMediaAssetId: string | null
  city: string | null
  unreadCount: number
}) {
  const pathname = usePathname()
  const [sheetOpen, setSheetOpen] = useState(false)
  const navigation = useTranslations("navigation")
  const shell = useTranslations("shell")
  const closeSheet = useCallback(() => setSheetOpen(false), [])

  const profileHref = username ? `/u/${encodeURIComponent(username)}` : null
  const youActive =
    isNavActive("/app/settings", pathname) ||
    (profileHref ? isNavActive(profileHref, pathname) : false)

  return (
    <>
      <nav
        aria-label={shell("mobileNavigation")}
        className="fixed inset-x-0 bottom-0 z-40 flex border-t border-border-gray bg-graphite pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        {ITEMS.map((item) => {
          const active = isNavActive(item.href, pathname)
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              aria-label={
                item.href === "/app/notifications" && unreadCount > 0
                  ? navigation("notificationsUnread", { count: unreadCount })
                  : undefined
              }
              className={cn(
                "flex min-w-0 flex-1 flex-col items-center gap-1 py-2 font-mono text-[10px] uppercase tracking-label focus-visible:outline-2 focus-visible:outline-acid",
                active ? "text-acid" : "text-muted",
              )}
            >
              <span className="relative">
                <Icon size={19} weight={active ? "fill" : "regular"} aria-hidden />
                {item.href === "/app/notifications" && unreadCount > 0 ? (
                  <span
                    aria-hidden
                    className="absolute -right-3 -top-2 min-w-4 bg-acid px-1 text-center text-[9px] leading-4 text-pitch"
                  >
                    {unreadBadgeLabel(unreadCount)}
                  </span>
                ) : null}
              </span>
              <span className="w-full text-center leading-tight [overflow-wrap:anywhere]">
                {navigation(item.label)}
              </span>
            </Link>
          )
        })}
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={sheetOpen}
          className={cn(
            "flex min-w-0 flex-1 flex-col items-center gap-1 py-2 font-mono text-[10px] uppercase tracking-label focus-visible:outline-2 focus-visible:outline-acid",
            youActive || sheetOpen ? "text-acid" : "text-muted",
          )}
        >
          <UserCircle
            size={19}
            weight={youActive || sheetOpen ? "fill" : "regular"}
            aria-hidden
          />
          <span className="w-full text-center leading-tight [overflow-wrap:anywhere]">
            {navigation("you")}
          </span>
        </button>
      </nav>
      {sheetOpen ? (
        <YouSheet
          username={username}
          displayName={displayName}
          avatarMediaAssetId={avatarMediaAssetId}
          city={city}
          onClose={closeSheet}
        />
      ) : null}
    </>
  )
}
