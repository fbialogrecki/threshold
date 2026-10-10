import type { ReactNode } from "react"
import Link from "next/link"
import { getLocale, getTranslations } from "next-intl/server"

import { DockActions } from "@/components/shell/dock-actions"
import { LeftNav } from "@/components/shell/left-nav"
import { Avatar } from "@/components/ui/avatar"
import { MonoLabel } from "@/components/ui/mono-label"
import { StatusBadge } from "@/components/ui/status-badge"
import { getTonight, getYourAccess } from "@/lib/api/rail"
import type { Session } from "@/lib/auth/session"
import { cityLabel } from "@/lib/cities"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import type { LocationMode } from "@/lib/types"

/*
  Location modes under the revised colour doctrine: a known address is not a
  status and gets no hue, a missing one is flagged orange, and a withheld one
  reads from full contrast plus the padlock on its badge. Violet is reserved
  for the vote axis.
*/
const LOCATION_TONE: Record<LocationMode, "muted" | "protected" | "orange"> = {
  public_location: "muted",
  secret_location: "protected",
  tba: "orange",
}

const RAIL_ITEM =
  "block rounded-control px-3 py-2.5 transition-colors hover:bg-raised focus-visible:bg-raised"

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
  const [yourAccess, tonight, t, locale] = await Promise.all([
    getYourAccess(),
    getTonight(),
    getTranslations("shell"),
    getLocale(),
  ])

  const storedCity = session.onboarding_preferences?.city?.trim()
  const city = storedCity ? cityLabel(storedCity, locale) : null
  // One public name per person: the unique username.
  const name =
    session.user.username?.trim() || session.consumer_profile?.display_name?.trim() || ""
  const avatarMediaAssetId = session.consumer_profile?.avatar_media_asset_id ?? null

  // Approved access first: unlocked doors outrank waiting rooms.
  const sortedAccess = [...yourAccess].sort((a, b) =>
    a.state === b.state ? 0 : a.state === "approved" ? -1 : 1,
  )

  return (
    <aside
      aria-label={t("sidebar")}
      className="sticky top-0 hidden h-screen w-[17rem] shrink-0 flex-col overflow-hidden border-r border-border-gray bg-[linear-gradient(180deg,var(--color-graphite),var(--color-pitch)_70%)] lg:flex"
    >
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-5 pt-6">
        <LeftNav />

        {/*
          Empty sections collapse instead of drawing a titled box around a
          bordered hint. The rail should not charge its width for placeholders.
        */}
        <div className="mt-7 flex flex-col gap-6 border-t border-border-gray pt-6">
          {sortedAccess.length > 0 ? (
            <Section title={t("privateAccess")}>
              {sortedAccess.map((item) => (
                <Link key={item.event.slug} href={`/events/${item.event.slug}`} className={RAIL_ITEM}>
                  <p className="font-display text-base leading-tight text-raw-white">
                    {item.event.title}
                  </p>
                  <p className="mt-1 text-xs text-muted">
                    {t(`location.${item.locationMode}`)} · {item.dateText}
                  </p>
                  <StatusBadge className="mt-2" status={item.state} />
                </Link>
              ))}
            </Section>
          ) : null}

          {tonight.length > 0 ? (
            <Section
              title={city ? `${t("tonight")} · ${city}` : t("tonight")}
              href="/app/events"
              hrefLabel={t("all")}
            >
              {tonight.map((item) => (
                <Link key={item.event.slug} href={`/events/${item.event.slug}`} className={RAIL_ITEM}>
                  <MonoLabel size="xs" tone={LOCATION_TONE[item.locationMode]}>
                    {t(`location.${item.locationMode}`)}
                  </MonoLabel>
                  <p className="mt-0.5 font-display text-base leading-tight text-raw-white">
                    {item.event.title}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-muted">{item.venueText}</p>
                </Link>
              ))}
            </Section>
          ) : null}

          {sortedAccess.length === 0 && tonight.length === 0 ? (
            <p className="px-3 text-[13px] leading-5 text-muted">{t("railQuiet")}</p>
          ) : null}
        </div>
      </div>

      <div className="shrink-0 border-t border-border-gray p-3">
        <div className="flex items-center gap-2.5 rounded-control bg-raised/60 p-2">
          <Avatar
            name={name}
            size="sm"
            imageUrl={
              avatarMediaAssetId
                ? mediaDerivativeUrl(avatarMediaAssetId, "avatar_256")
                : null
            }
          />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-raw-white">{name}</p>
            {city ? <p className="truncate text-xs text-muted">{city}</p> : null}
          </div>
          <DockActions unreadCount={unreadCount} />
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
      <div className="flex items-center justify-between px-3">
        <h2 className="text-xs font-semibold uppercase tracking-[0.12em] text-muted">{title}</h2>
        {href && hrefLabel ? (
          <Link href={href} className="text-xs font-medium text-dim-white transition-colors hover:text-acid">
            {hrefLabel}
          </Link>
        ) : null}
      </div>
      <div className="mt-2 flex flex-col gap-0.5">{children}</div>
    </section>
  )
}
