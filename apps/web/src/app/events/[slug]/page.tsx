import type { Metadata } from "next"
import {
  Buildings,
  CalendarDots,
  MapPin,
  Megaphone,
  MusicNotes,
  TextAlignLeft,
} from "@phosphor-icons/react/ssr"
import { getLocale, getTranslations } from "next-intl/server"
import Image from "next/image"
import Link from "next/link"
import { notFound } from "next/navigation"
import { cache } from "react"

import { EventUpdateCard } from "@/components/cards/event-update-card"
import {
  DjGuestTools,
  DoorCheckIn,
  DoorStaffManager,
  ManagerGuestlist,
  QuotaControls,
} from "@/components/event/event-access-tools"
import { EventUpdateForm } from "@/components/event/event-update-form"
import { EventFollowButton } from "@/components/event/follow-button"
import { GuestAccessCard } from "@/components/event/guest-access-card"
import { LocationStates } from "@/components/event/location-states"
import { BoostButton } from "@/components/ui/boost-button"
import { StatusBadge } from "@/components/ui/status-badge"
import { TagRow } from "@/components/ui/tag"
import {
  getDoorStaff,
  getEvent,
  getEventViewerContext,
  getManagerGuestlist,
  listEventUpdates,
} from "@/lib/api/events"
import { getOrganizerRefs } from "@/lib/api/users-read"
import { hasRequiredOnboarding } from "@/lib/auth/routing"
import { cityLabel } from "@/lib/cities"
import {
  eventAccessSurfaces,
  eventLoginHref,
  lineupArtistChoices,
  viewerArtistChoices,
} from "@/lib/events/access"
import { formatEventDate } from "@/lib/format"
import { getSessionState } from "@/lib/auth/session"
import { absoluteMediaDerivativeUrl, mediaDerivativeUrl } from "@/lib/media/urls"
import { safeInternalHref } from "@/lib/safe-href"

export const dynamic = "force-dynamic"
const getEventCached = cache(getEvent)

type Params = Promise<{ slug: string }>

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { slug } = await params
  const [event, t] = await Promise.all([
    getEventCached(slug),
    getTranslations("eventDetail"),
  ])
  if (!event) return { title: t("notFound") }

  const image = event.poster_media_asset_id
    ? absoluteMediaDerivativeUrl(event.poster_media_asset_id, "post_1280")
    : undefined

  return {
    title: event.title,
    description: event.description ?? undefined,
    openGraph: {
      title: event.title,
      description: event.description ?? undefined,
      type: "website",
      ...(image ? { images: [{ url: image }] } : {}),
    },
  }
}

export default async function EventPage({ params }: { params: Params }) {
  const { slug } = await params
  const [event, updates, sessionState, locale, t] = await Promise.all([
    getEventCached(slug),
    listEventUpdates(slug),
    getSessionState(),
    getLocale(),
    getTranslations("eventDetail"),
  ])
  if (!event) notFound()

  const isAuthenticated = sessionState.status === "authenticated"
    && hasRequiredOnboarding(sessionState.session)
  const [viewerContext, organizerRefs] = await Promise.all([
    isAuthenticated ? getEventViewerContext(slug) : null,
    event.page_id ? getOrganizerRefs([event.page_id]) : [],
  ])
  const accessSurfaces = eventAccessSurfaces(viewerContext)
  const [guestlist, doorStaff] = await Promise.all([
    accessSurfaces.managerGuestlist ? getManagerGuestlist(slug) : [],
    accessSurfaces.doorStaffManagement ? getDoorStaff(slug) : [],
  ])
  const organizer = organizerRefs[0]
  const organizerHref = safeInternalHref(organizer?.target_url)
  const lineupArtists = lineupArtistChoices(event.lineup)
  const djArtists = viewerContext ? viewerArtistChoices(event.lineup, viewerContext) : []
  const posterUrl = event.poster_media_asset_id
    ? mediaDerivativeUrl(event.poster_media_asset_id, "post_1280")
    : null
  const city = event.city ? cityLabel(event.city, locale) : t("tba")
  const loginHref = isAuthenticated
    ? undefined
    : eventLoginHref(event.slug)
  const authUnavailable = sessionState.status === "unavailable"
  const locationStatus = event.location_mode === "secret_location"
    ? "secret"
    : event.location_mode === "tba"
      ? "tba"
      : "public"

  return (
    <article className="mx-auto w-full max-w-event-detail">
      <header className="grid gap-6 border-b border-border-gray pb-8 md:grid-cols-[minmax(17rem,0.88fr)_minmax(0,1.12fr)] md:items-start">
        <div className="border border-border-gray bg-graphite">
          {posterUrl ? (
            <Image
              src={posterUrl}
              alt={t("posterAlt", { title: event.title })}
              width={640}
              height={800}
              priority
              sizes="(min-width: 768px) 42vw, 100vw"
              className="aspect-[4/5] h-auto max-h-[46rem] w-full object-cover"
            />
          ) : (
            <div className="flex aspect-[4/5] items-center justify-center p-6 text-center font-mono text-xs uppercase tracking-label text-muted">
              {t("noPoster")}
            </div>
          )}
        </div>

        <div className="flex min-h-full flex-col">
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status="event" label={t("event")} />
            <StatusBadge
              status={locationStatus}
              label={t(`location.badge.${event.location_mode}`)}
            />
            {viewerContext?.active_guest_access ? (
              <StatusBadge status="guestlist" label={t("access.guestlistBadge")} />
            ) : null}
          </div>
          <h1 className="mt-4 font-display text-5xl leading-[0.92] tracking-wide text-raw-white sm:text-6xl lg:text-7xl">
            {event.title}
          </h1>

          <dl className="mt-6 divide-y divide-border-gray border-y border-border-gray">
            <div className="flex items-start gap-3 py-3">
              <CalendarDots size={19} weight="bold" className="mt-0.5 shrink-0 text-acid" aria-hidden />
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-label text-muted">{t("date")}</dt>
                <dd className="mt-0.5 text-sm text-raw-white">{formatEventDate(event.starts_at, locale)}</dd>
              </div>
            </div>
            <div className="flex items-start gap-3 py-3">
              <MapPin size={19} weight="bold" className="mt-0.5 shrink-0 text-cyan" aria-hidden />
              <div>
                <dt className="font-mono text-[10px] uppercase tracking-label text-muted">{t("city")}</dt>
                <dd className="mt-0.5 text-sm text-raw-white">{city}</dd>
              </div>
            </div>
            {organizer ? (
              <div className="flex items-start gap-3 py-3">
                <Buildings size={19} weight="bold" className="mt-0.5 shrink-0 text-dim-white" aria-hidden />
                <div>
                  <dt className="font-mono text-[10px] uppercase tracking-label text-muted">{t("organizer")}</dt>
                  <dd className="mt-0.5 text-sm text-raw-white">
                    {organizerHref ? (
                      <Link href={organizerHref} className="hover:text-acid hover:underline">
                        {organizer.display_name}
                      </Link>
                    ) : organizer.display_name}
                  </dd>
                </div>
              </div>
            ) : null}
          </dl>

          {authUnavailable ? null : (
            <div className="mt-auto flex flex-wrap items-center gap-3 pt-6">
              <EventFollowButton
                slug={event.slug}
                initialFollowing={event.is_following}
                loginHref={loginHref}
              />
              <BoostButton
                targetId={event.slug}
                initialCount={event.boost_count}
                initialBoosted={event.is_boosting}
                loginHref={loginHref}
              />
            </div>
          )}
        </div>
      </header>

      {event.description ? (
        <section className="mt-8 border-b border-border-gray pb-8">
          <h2 className="flex items-center gap-2 font-mono text-xs uppercase tracking-cta text-raw-white">
            <TextAlignLeft size={18} weight="bold" aria-hidden />
            {t("description")}
          </h2>
          <p className="mt-4 whitespace-pre-wrap text-base leading-8 text-dim-white">{event.description}</p>
        </section>
      ) : null}

      <div className="grid gap-8 border-b border-border-gray py-8 md:grid-cols-2">
        {event.lineup.length > 0 ? (
          <section>
            <h2 className="flex items-center gap-2 font-mono text-xs uppercase tracking-cta text-raw-white">
              <MusicNotes size={18} weight="bold" aria-hidden />
              {t("lineup")}
            </h2>
            <p className="mt-4 text-sm leading-7 text-dim-white">
              {event.lineup.map((item, index) => {
                const name = typeof item === "string" ? item : item.display_name ?? item.name
                const targetUrl = typeof item === "string" ? null : safeInternalHref(item.target_url)
                return (
                  <span key={`${name}-${index}`}>
                    {index > 0 ? " / " : null}
                    {targetUrl ? (
                      <Link href={targetUrl} className="text-cyan hover:underline">{name}</Link>
                    ) : name}
                  </span>
                )
              })}
            </p>
          </section>
        ) : null}
        {event.genres.length > 0 ? (
          <section>
            <h2 className="font-mono text-xs uppercase tracking-cta text-raw-white">{t("genres")}</h2>
            <TagRow className="mt-4" tags={event.genres} />
          </section>
        ) : null}
      </div>

      <section className="mt-8">
        <LocationStates event={event} />
      </section>

      {accessSurfaces.guest && viewerContext?.active_guest_access ? (
        <div className="mt-6">
          <GuestAccessCard
            access={viewerContext.active_guest_access}
            canMintQr={viewerContext.can_mint_qr}
            slug={event.slug}
          />
        </div>
      ) : null}

      {accessSurfaces.managerGuestlist ? (
        <div className="mt-6">
          <ManagerGuestlist entries={guestlist} slug={event.slug} />
        </div>
      ) : null}
      {accessSurfaces.doorStaffManagement ? (
        <div className="mt-6">
          <DoorStaffManager assignments={doorStaff} slug={event.slug} />
        </div>
      ) : null}
      {accessSurfaces.quotas && viewerContext ? (
        <div className="mt-6">
          <QuotaControls
            artists={lineupArtists}
            quotas={viewerContext.quota_summaries}
            slug={event.slug}
          />
        </div>
      ) : null}
      {accessSurfaces.djGuests && viewerContext && djArtists.length > 0 ? (
        <div className="mt-6">
          <DjGuestTools
            artists={djArtists}
            context={viewerContext}
            slug={event.slug}
          />
        </div>
      ) : null}
      {accessSurfaces.checkIn ? (
        <div className="mt-6">
          <DoorCheckIn slug={event.slug} />
        </div>
      ) : null}

      <section className="mt-10">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 font-mono text-xs uppercase tracking-cta text-raw-white">
            <Megaphone size={18} weight="bold" aria-hidden />
            {t("updates.title")}
          </h2>
          <StatusBadge status="public" label={t("updates.public")} />
        </div>
        {accessSurfaces.postUpdate ? <EventUpdateForm slug={event.slug} /> : null}
        <div className="mt-4 flex flex-col gap-3">
          {updates.length > 0 ? (
            updates.map((update) => <EventUpdateCard key={update.id} update={update} />)
          ) : (
            <p className="border border-border-gray bg-graphite p-4 text-sm text-muted">
              {t("updates.empty")}
            </p>
          )}
        </div>
      </section>
    </article>
  )
}
