import type { ReactNode } from "react"
import { getLocale, getTranslations } from "next-intl/server"

import { RefreshKeeper } from "@/components/auth/refresh-keeper"
import { MobileNav } from "@/components/shell/mobile-nav"
import { Sidebar } from "@/components/shell/sidebar"
import { TopBar } from "@/components/shell/top-bar"
import { notificationUnreadCount as fetchNotificationUnreadCount } from "@/lib/auth/product-auth"
import type { Session } from "@/lib/auth/session"
import { cityLabel } from "@/lib/cities"
import { cn } from "@/lib/cn"
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
  const [locale, unreadResult, t] = await Promise.all([
    getLocale(),
    fetchNotificationUnreadCount().catch(() => null),
    getTranslations("shell"),
  ])
  const unreadCount = unreadResult?.status === 200
    ? notificationUnreadCount(unreadResult.body)
    : 0
  // One public name per person: the unique username. The profile display name
  // survives only as a fallback for accounts that never had a username.
  const name =
    session.user.username?.trim() || session.consumer_profile?.display_name?.trim() || ""
  const avatarMediaAssetId = session.consumer_profile?.avatar_media_asset_id ?? null
  const storedCity = session.onboarding_preferences?.city?.trim()
  const city = storedCity ? cityLabel(storedCity, locale) : null

  return (
    <div className="flex min-h-screen bg-pitch">
      <a
        href="#app-content"
        className="skip-link rounded-control border border-acid bg-pitch px-4 py-2 text-sm font-semibold text-acid"
      >
        {t("skipToContent")}
      </a>
      <RefreshKeeper />
      <Sidebar session={session} unreadCount={unreadCount} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          username={session.user.username}
          name={name}
          avatarMediaAssetId={avatarMediaAssetId}
          city={city}
          unreadCount={unreadCount}
        />
        {banner}
        <main
          id="app-content"
          tabIndex={-1}
          className="flex-1 px-4 pb-[calc(6rem+env(safe-area-inset-bottom))] pt-4 outline-none sm:px-6 sm:pt-6 lg:px-10 lg:pb-12 lg:pt-8"
        >
          {/*
            No entry animation here: a filling animation makes this wrapper a
            stacking context, which would trap page modals under the nav.
          */}
          <div className={cn("mx-auto w-full", wide ? "max-w-event-detail" : "max-w-feed")}>
            {children}
          </div>
        </main>
      </div>
      <MobileNav />
    </div>
  )
}
