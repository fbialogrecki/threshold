"use client"

import { Bell, GearSix, SignOut } from "@phosphor-icons/react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { usePathname } from "next/navigation"

import { LogoutButton } from "@/components/auth/logout-button"
import { isNavActive } from "@/components/shell/nav-active"
import { cn } from "@/lib/cn"

const ACTION = "p-1.5 transition-colors"

/**
 * Account chrome beside the profile identity. Unread count reads as a mark
 * rather than a number: the exact figure belongs on the notifications page,
 * and the label carries it for screen readers.
 */
export function DockActions({ unreadCount }: { unreadCount: number }) {
  const pathname = usePathname()
  const navigation = useTranslations("navigation")
  const notificationsActive = isNavActive("/app/notifications", pathname)
  const settingsActive = isNavActive("/app/settings", pathname)

  return (
    <div className="flex shrink-0 items-center">
      <Link
        href="/app/notifications"
        aria-current={notificationsActive ? "page" : undefined}
        aria-label={
          unreadCount > 0
            ? navigation("notificationsUnread", { count: unreadCount })
            : navigation("notifications")
        }
        className={cn(
          ACTION,
          "relative hover:text-acid focus-visible:text-acid",
          notificationsActive ? "text-acid" : "text-muted",
        )}
      >
        <Bell size={20} weight={notificationsActive ? "fill" : "bold"} aria-hidden />
        {unreadCount > 0 ? (
          <span aria-hidden className="absolute right-1 top-1 h-1.5 w-1.5 bg-acid" />
        ) : null}
      </Link>

      <Link
        href="/app/settings"
        aria-current={settingsActive ? "page" : undefined}
        aria-label={navigation("settings")}
        className={cn(
          ACTION,
          "hover:text-acid focus-visible:text-acid",
          settingsActive ? "text-acid" : "text-muted",
        )}
      >
        <GearSix size={20} weight="bold" aria-hidden />
      </Link>

      <LogoutButton className={cn(ACTION, "text-muted hover:text-orange focus-visible:text-orange")}>
        <SignOut size={20} weight="bold" aria-hidden />
      </LogoutButton>
    </div>
  )
}
