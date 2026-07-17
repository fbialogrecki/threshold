import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"

import { EventFollowButton } from "@/components/event/follow-button"
import { BoostButton } from "@/components/ui/boost-button"
import { ButtonLink } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { MonoLabel } from "@/components/ui/mono-label"
import { StatusBadge } from "@/components/ui/status-badge"
import { TagRow } from "@/components/ui/tag"
import { cityLabel } from "@/lib/cities"
import { formatEventDate } from "@/lib/format"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import { safeInternalHref } from "@/lib/safe-href"
import type { LocationMode, ThresholdEvent } from "@/lib/types"

const LOCATION_STATUS: Record<LocationMode, string> = {
  public_location: "public",
  secret_location: "secret",
  tba: "tba",
}

export async function EventCard({
  event,
  variant = "interactive",
  loginHref,
}: {
  event: ThresholdEvent
  variant?: "interactive" | "feed"
  loginHref?: string
}) {
  const [locale, t] = await Promise.all([getLocale(), getTranslations("eventCard")])
  const city = event.city ? cityLabel(event.city, locale) : null
  const posterUrl = event.poster_media_asset_id
    ? mediaDerivativeUrl(event.poster_media_asset_id, "post_1280")
    : null
  const locationLabel = t(`location.${event.location_mode}`)

  return (
    <Card as="article" className="border-l-2 border-l-violet">
      <div className="flex items-center justify-between border-b border-border-gray px-4 py-2">
        <MonoLabel tone="violet">{t("event")}</MonoLabel>
        <MonoLabel tone="muted">{city ?? "—"}</MonoLabel>
      </div>

      {posterUrl ? (
        <Link href={`/events/${event.slug}`} className="block border-b border-border-gray bg-raised">
          <img
            src={posterUrl}
            alt={event.title}
            width={820}
            height={1025}
            loading="lazy"
            decoding="async"
            className="aspect-[4/5] max-h-[36rem] w-full object-cover"
          />
        </Link>
      ) : null}

      <div className="px-4 py-4">
        <Link href={`/events/${event.slug}`}>
          <h3 className="font-display text-4xl leading-[0.95] tracking-wide text-raw-white hover:text-acid">
            {event.title}
          </h3>
        </Link>

        <div className="mt-3 flex flex-wrap items-stretch gap-2">
          <div className="border border-border-gray bg-raised px-3 py-1.5">
            <p className="font-mono text-xs uppercase tracking-label text-raw-white">
              {formatEventDate(event.starts_at, locale)}
            </p>
          </div>
          <StatusBadge
            className="self-center"
            status={LOCATION_STATUS[event.location_mode]}
            label={`${locationLabel} · ${city ?? t("tba")}`}
          />
        </div>

        {event.venue_name && event.location_mode !== "secret_location" ? (
          <p className="mt-3 text-sm text-dim-white">
            <span className="font-mono text-[11px] uppercase tracking-label text-muted">
              {t("venue")}:{" "}
            </span>
            {event.venue_name}
          </p>
        ) : null}

        {event.lineup.length > 0 ? (
          <div className="mt-3 text-sm text-dim-white">
            <span className="font-mono text-[11px] uppercase tracking-label text-muted">
              {t("lineup")}:{" "}
            </span>
            {event.lineup.map((item, index) => {
              const name = typeof item === "string" ? item : item.display_name ?? item.name
              const targetUrl =
                typeof item === "string" ? null : safeInternalHref(item.target_url)
              return (
                <span key={`${name}-${index}`}>
                  {index > 0 ? " / " : null}
                  {targetUrl ? (
                    <Link href={targetUrl} className="text-cyan hover:underline">
                      {name}
                    </Link>
                  ) : (
                    name
                  )}
                </span>
              )
            })}
          </div>
        ) : null}

        <TagRow className="mt-3" tags={event.genres} />

        <div className="mt-4 flex items-center justify-between gap-4 border-t border-border-gray pt-3">
          <div className="flex items-center gap-2">
            <ButtonLink href={`/events/${event.slug}`} variant="secondary">
              {t("view")} →
            </ButtonLink>
            {variant === "interactive" ? (
              <EventFollowButton
                slug={event.slug}
                initialFollowing={event.is_following}
                loginHref={loginHref}
              />
            ) : null}
          </div>
          {variant === "interactive" ? (
            <BoostButton
              targetId={event.slug}
              initialCount={event.boost_count}
              initialBoosted={event.is_boosting}
              loginHref={loginHref}
            />
          ) : null}
        </div>
      </div>
    </Card>
  )
}
