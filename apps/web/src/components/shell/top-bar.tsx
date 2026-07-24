"use client"

import { Bell } from "@phosphor-icons/react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { useCallback, useState } from "react"

import { AccountSheet } from "@/components/shell/account-sheet"
import { Avatar } from "@/components/ui/avatar"
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
  const closeSheet = useCallback(() => setSheetOpen(false), [])

  return (
    <>
      <header className="sticky top-0 z-30 flex h-12 shrink-0 items-center gap-3 border-b border-border-gray bg-pitch px-4 lg:hidden">
        <Link href="/app" className="font-display text-2xl text-raw-white">
          Threshold<span className="text-acid">▮</span>
        </Link>
        <span className="flex-1" />
        <Link
          href="/app/notifications"
          aria-label={
            unreadCount > 0
              ? navigation("notificationsUnread", { count: unreadCount })
              : navigation("notifications")
          }
          className="relative p-1 text-muted hover:text-raw-white focus-visible:text-raw-white"
        >
          <Bell size={19} aria-hidden />
          {unreadCount > 0 ? (
            <span
              aria-hidden
              className="absolute -right-1 -top-1 min-w-4 bg-acid px-1 text-center font-mono text-[9px] leading-4 text-pitch"
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
          className="p-0.5"
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
