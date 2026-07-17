import type { ReactNode } from "react"
import { getLocale } from "next-intl/server"

import { RefreshKeeper } from "@/components/auth/refresh-keeper"
import { MobileNav } from "@/components/shell/mobile-nav"
import { Sidebar } from "@/components/shell/sidebar"
import { notificationUnreadCount as fetchNotificationUnreadCount } from "@/lib/auth/product-auth"
import type { Session } from "@/lib/auth/session"
import { cityLabel } from "@/lib/cities"
import { notificationUnreadCount } from "@/lib/notifications"

/**
 * Shared authenticated shell: desktop sidebar, mobile bottom nav, session
 * refresh keeper and the content wrapper. Used by the (app) section and by
 * signed-in views outside it, including groups, posts, and public details.
 */
export async function AppShell({
  children,
  banner,
  session,
  wide = false,
}: {
  children: ReactNode
  /** optional strip above the content (e.g. verify-email banner) */
  banner?: ReactNode
  session: Session
  wide?: boolean
}) {
  const [locale, unreadResult] = await Promise.all([
    getLocale(),
    fetchNotificationUnreadCount().catch(() => null),
  ])
  const unreadCount = unreadResult?.status === 200
    ? notificationUnreadCount(unreadResult.body)
    : 0
  const displayName =
    session.consumer_profile?.display_name?.trim() || session.user.username || ""
  const avatarMediaAssetId = session.consumer_profile?.avatar_media_asset_id ?? null
  const storedCity = session.onboarding_preferences?.city?.trim()
  const city = storedCity ? cityLabel(storedCity, locale) : null

  return (
    <div className="flex min-h-screen bg-pitch">
      <RefreshKeeper />
      <Sidebar session={session} unreadCount={unreadCount} />
      <main className="flex-1 px-4 pb-[calc(6rem+env(safe-area-inset-bottom))] pt-6 sm:px-6 lg:px-10 lg:pb-8">
        {banner}
        <div className={wide ? "mx-auto w-full max-w-event-detail" : "mx-auto w-full max-w-feed"}>
          {children}
        </div>
      </main>
      <MobileNav
        username={session.user.username}
        displayName={displayName}
        avatarMediaAssetId={avatarMediaAssetId}
        city={city}
        unreadCount={unreadCount}
      />
    </div>
  )
}
