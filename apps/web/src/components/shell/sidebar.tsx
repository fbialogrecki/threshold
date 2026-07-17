import type { ReactNode } from "react"
import Link from "next/link"
import { GearSix } from "@phosphor-icons/react/ssr"
import { getLocale, getTranslations } from "next-intl/server"

import { LogoutButton } from "@/components/auth/logout-button"
import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { LeftNav } from "@/components/shell/left-nav"
import { Avatar } from "@/components/ui/avatar"
import { MonoLabel } from "@/components/ui/mono-label"
import { StatusBadge } from "@/components/ui/status-badge"
import { getTonight, getYourAccess } from "@/lib/api/rail"
import type { Session } from "@/lib/auth/session"
import { cityLabel } from "@/lib/cities"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import type { LocationMode } from "@/lib/types"

const LOCATION_TONE: Record<LocationMode, "cyan" | "violet" | "orange"> = {
  public_location: "cyan",
  secret_location: "violet",
  tba: "orange",
}

/**
 * Single desktop rail: primary navigation and real access data scroll while
 * the signed-in profile dock stays available at the bottom.
 */
export async function Sidebar({
  session,
  unreadCount,
}: {
  session: Session
  unreadCount: number
}) {
  const [yourAccess, tonight, t, navigation, locale] = await Promise.all([
    getYourAccess(),
    getTonight(),
    getTranslations("shell"),
    getTranslations("navigation"),
    getLocale(),
  ])

  const storedCity = session.onboarding_preferences?.city?.trim()
  const city = storedCity ? cityLabel(storedCity, locale) : null
  const displayName =
    session.consumer_profile?.display_name?.trim() || session.user.username || ""
  const avatarMediaAssetId = session.consumer_profile?.avatar_media_asset_id ?? null

  // Approved access first: unlocked doors outrank waiting rooms.
  const sortedAccess = [...yourAccess].sort((a, b) =>
    a.state === b.state ? 0 : a.state === "approved" ? -1 : 1,
  )

  return (
    <aside
      aria-label={t("primaryNavigation")}
      className="sticky top-0 hidden h-screen w-[280px] shrink-0 flex-col overflow-hidden border-r border-border-gray bg-graphite lg:flex"
    >
      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        <LeftNav unreadCount={unreadCount} />

        <div className="mt-10 flex flex-col gap-8 border-t-2 border-border-gray pt-6">
          <Section title={t("privateAccess")}>
            {sortedAccess.length === 0 ? (
              <EmptyHint>{t("privateAccessEmpty")}</EmptyHint>
            ) : (
              sortedAccess.map((item) => (
                <Link
                  key={item.event.slug}
                  href={`/events/${item.event.slug}`}
                  className="block border-l-2 border-border-gray pl-3 hover:border-acid"
                >
                  <p className="font-display text-base leading-tight tracking-wide text-raw-white">
                    {item.event.title}
                  </p>
                  <MonoLabel size="xs" className="mt-0.5 block">
                    {t(`location.${item.locationMode}`)} / {item.dateText}
                  </MonoLabel>
                  <StatusBadge className="mt-1.5" status={item.state} />
                </Link>
              ))
            )}
          </Section>

          <Section
            title={city ? `${t("tonight")} / ${city}` : t("tonight")}
            href="/app/events"
            hrefLabel={t("all")}
          >
            {tonight.length === 0 ? (
              <EmptyHint>{t("tonightEmpty")}</EmptyHint>
            ) : (
              tonight.map((item) => (
                <Link
                  key={item.event.slug}
                  href={`/events/${item.event.slug}`}
                  className="block"
                >
                  <MonoLabel size="xs" tone={LOCATION_TONE[item.locationMode]}>
                    {t(`location.${item.locationMode}`)}
                  </MonoLabel>
                  <p className="mt-0.5 font-display text-base leading-tight tracking-wide text-raw-white">
                    {item.event.title}
                  </p>
                  <MonoLabel size="xs" className="block">
                    {item.venueText}
                  </MonoLabel>
                </Link>
              ))
            )}
          </Section>
        </div>
      </div>

      <div className="shrink-0 border-t-2 border-border-gray bg-pitch/40 p-4">
        <div className="flex items-center gap-3">
          <Avatar
            name={displayName}
            imageUrl={
              avatarMediaAssetId
                ? mediaDerivativeUrl(avatarMediaAssetId, "avatar_256")
                : null
            }
          />
          <div className="min-w-0 flex-1">
            <p className="truncate font-display text-lg tracking-wide text-raw-white">
              {displayName}
            </p>
            {city ? (
              <p className="truncate font-mono text-[10px] uppercase tracking-label text-muted">
                {city}
              </p>
            ) : null}
          </div>
          <Link
            href="/app/settings"
            aria-label={navigation("settings")}
            className="p-2 text-muted transition-colors hover:text-acid focus-visible:text-acid"
          >
            <GearSix size={20} weight="bold" aria-hidden />
          </Link>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <LocaleSwitcher />
          <LogoutButton />
        </div>
      </div>
    </aside>
  )
}

function Section({
  title,
  href,
  hrefLabel,
  children,
}: {
  title: string
  href?: string
  hrefLabel?: string
  children: ReactNode
}) {
  return (
    <section>
      <div className="flex items-center justify-between">
        <MonoLabel tone="dim" className="tracking-cta">
          {title}
        </MonoLabel>
        {href && hrefLabel ? (
          <Link
            href={href}
            className="font-mono text-[10px] uppercase tracking-label text-muted hover:text-acid"
          >
            {hrefLabel}
          </Link>
        ) : null}
      </div>
      <div className="mt-3 flex flex-col gap-3.5">{children}</div>
    </section>
  )
}

function EmptyHint({ children }: { children: ReactNode }) {
  return (
    <p className="border-l-2 border-border-gray pl-3 font-mono text-[10px] uppercase leading-relaxed tracking-label text-muted">
      {children}
    </p>
  )
}
