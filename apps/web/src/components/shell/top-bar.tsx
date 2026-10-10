"use client"

import { Bell } from "@phosphor-icons/react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { usePathname } from "next/navigation"
import { useCallback, useState } from "react"

import { AccountSheet } from "@/components/shell/account-sheet"
import { isNavActive } from "@/components/shell/nav-active"
import { Avatar } from "@/components/ui/avatar"
import { cn } from "@/lib/cn"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import { unreadBadgeLabel } from "@/lib/notifications"

/**
 * Mobile chrome above the content: the brand mark plus the two destinations a
 * reader needs rarely. Keeping notifications and the account up here leaves the
 * thumb zone below for the things used constantly, and gives the brand a place
 * on a phone, which it previously had only on desktop.
 */
export function TopBar({
  username,
  name,
  avatarMediaAssetId,
  city,
  unreadCount,
}: {
  username: string | null
  name: string
  avatarMediaAssetId: string | null
  city: string | null
  unreadCount: number
}) {
  const navigation = useTranslations("navigation")
  const shell = useTranslations("shell")
  const [sheetOpen, setSheetOpen] = useState(false)
  const notificationsActive = isNavActive("/app/notifications", usePathname())
  const closeSheet = useCallback(() => setSheetOpen(false), [])

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-1 border-b border-border-gray bg-pitch/90 pl-4 pr-2 backdrop-blur-md lg:hidden">
        <Link href="/app" translate="no" className="flex items-center gap-1.5">
          <span className="font-display text-xl tracking-[0.1em] text-raw-white">PERLIMEN</span>
          <span className="size-1.5 rounded-full bg-acid" aria-hidden />
        </Link>
        <span className="flex-1" />
        <Link
          href="/app/notifications"
          aria-current={notificationsActive ? "page" : undefined}
          aria-label={
            unreadCount > 0
              ? navigation("notificationsUnread", { count: unreadCount })
              : navigation("notifications")
          }
          className={cn(
            "relative grid size-11 place-items-center rounded-full transition-colors hover:bg-raised",
            notificationsActive ? "text-acid" : "text-dim-white",
          )}
        >
          <Bell size={21} weight={notificationsActive ? "fill" : "regular"} aria-hidden />
          {unreadCount > 0 ? (
            <span
              aria-hidden
              className="absolute right-1 top-1.5 min-w-[1.125rem] rounded-full bg-acid px-1 text-center text-[10px] font-semibold leading-[1.125rem] text-pitch ring-2 ring-pitch"
            >
              {unreadBadgeLabel(unreadCount)}
            </span>
          ) : null}
        </Link>
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={sheetOpen}
          aria-label={shell("accountNavigation")}
          className="grid size-11 place-items-center rounded-full transition-colors hover:bg-raised"
        >
          <Avatar
            name={name}
            imageUrl={
              avatarMediaAssetId ? mediaDerivativeUrl(avatarMediaAssetId, "avatar_256") : null
            }
            size="sm"
          />
        </button>
      </header>
      {sheetOpen ? (
        <AccountSheet
          username={username}
          name={name}
          avatarMediaAssetId={avatarMediaAssetId}
          city={city}
          onClose={closeSheet}
        />
      ) : null}
    </>
  )
}
