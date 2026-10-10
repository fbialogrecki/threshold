import type { Metadata } from "next"
import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"
import { notFound } from "next/navigation"

import { EventCard } from "@/components/cards/event-card"
import { FollowButton } from "@/components/profile/follow-button"
import {
  EmptyNote,
  ExternalLinks,
  ProfileHeader,
  ProfileSection,
} from "@/components/profile/profile-blocks"
import { Avatar } from "@/components/ui/avatar"
import { listEvents } from "@/lib/api/events"
import { getPage } from "@/lib/api/users-read"
import {
  hasRequiredOnboarding,
  loginHref,
} from "@/lib/auth/routing"
import { getSessionState } from "@/lib/auth/session"
import { cityLabel } from "@/lib/cities"
import { absoluteMediaDerivativeUrl, mediaDerivativeUrl } from "@/lib/media/urls"

export const dynamic = "force-dynamic"

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>
}): Promise<Metadata> {
  const { slug } = await params
  const [page, t, locale] = await Promise.all([
    getPage(slug),
    getTranslations("publicPage"),
    getLocale(),
  ])
  if (!page) return { title: t("notFound") }

  const description = page.about
    || t("metadataFallback", {
      name: page.name,
      type: t(`types.${page.type}`),
      city: page.city ? cityLabel(page.city, locale) : t("unknownCity"),
    })
  const image = page.avatarMediaAssetId
    ? absoluteMediaDerivativeUrl(page.avatarMediaAssetId, "avatar_512")
    : undefined
  return {
    title: page.name,
    description,
    openGraph: {
      title: page.name,
      description,
      type: "profile",
      ...(image ? { images: [{ url: image }] } : {}),
    },
  }
}

export default async function PageProfileView({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const [page, t, locale] = await Promise.all([
    getPage(slug),
    getTranslations("publicPage"),
    getLocale(),
  ])
  if (!page) notFound()
  const upcomingEvents = await listEvents({ pageId: page.id, limit: 20, upcoming: true })

  const sessionState = await getSessionState()
  const isAuthenticated = sessionState.status === "authenticated"
    && hasRequiredOnboarding(sessionState.session)
  const authUnavailable = sessionState.status === "unavailable"
  const anonymousLoginHref = isAuthenticated
    ? undefined
    : loginHref(`/pages/${encodeURIComponent(slug)}`)

  const initialFollowing = isAuthenticated && page.isFollowing

  return (
    <div className="flex flex-col gap-8 text-raw-white">
      <ProfileHeader
        avatar={(
          <Avatar
            name={page.name}
            imageUrl={
              page.avatarMediaAssetId
                ? mediaDerivativeUrl(page.avatarMediaAssetId, "avatar_512")
                : null
            }
            size="lg"
          />
        )}
        actions={authUnavailable ? null : (
          <FollowButton
            handle={page.slug}
            targetType="page"
            loginHref={anonymousLoginHref}
            initialFollowing={initialFollowing}
          />
        )}
      >
        {/* Pages are entities: their own display name, in display type. */}
        <h1 className="font-display text-[clamp(1.75rem,10cqi,3.5rem)] leading-[0.95] break-words">{page.name}</h1>
        <p className="mt-2 flex flex-wrap items-center gap-2 text-[15px] text-dim-white">
          <span className="rounded-full bg-raised px-2.5 py-0.5 text-[13px] font-medium capitalize text-raw-white">
            {t(`types.${page.type}`)}
          </span>
          {page.city ? <span>{cityLabel(page.city, locale)}</span> : null}
        </p>
        <p className="mt-1.5 text-[13px] text-muted">
          {t("followers", { count: page.followerCount })}
        </p>
      </ProfileHeader>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-w-0 flex-col gap-8">
          <ProfileSection title={t("about")}>
            {page.about ? (
              <p className="max-w-[65ch] whitespace-pre-wrap break-words text-[15px] leading-7 text-dim-white">
                {page.about}
              </p>
            ) : (
              <EmptyNote>{t("noAbout")}</EmptyNote>
            )}
          </ProfileSection>

          <ProfileSection title={t("upcoming")}>
            {upcomingEvents.length > 0 ? (
              <ul className="flex flex-col gap-3">
                {upcomingEvents.map((event) => (
                  <li key={event.id}>
                    <EventCard
                      event={event}
                      loginHref={anonymousLoginHref}
                      variant={authUnavailable ? "feed" : "interactive"}
                    />
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyNote>{t("noEvents")}</EmptyNote>
            )}
          </ProfileSection>
        </div>

        <aside className="flex min-w-0 flex-col gap-8">
          <ProfileSection title={t("residents")}>
            {page.residents.length === 0 ? (
              <EmptyNote>{t("noResidents")}</EmptyNote>
            ) : (
              <ul className="flex flex-col gap-2">
                {page.residents.map((resident) => (
                  <li key={resident.handle}>
                    {/* Residents are people: their username, natural case, no @. */}
                    <Link
                      href={`/u/${encodeURIComponent(resident.handle)}`}
                      className="flex items-center justify-between gap-3 rounded-control border border-border-gray bg-graphite/60 px-4 py-3 transition-colors hover:border-acid"
                    >
                      <span className="min-w-0 truncate text-[15px] font-semibold">{resident.handle}</span>
                      <span className="shrink-0 text-xs text-muted">{t("confirmed")}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </ProfileSection>

          <ProfileSection title={t("links")}>
            {page.links.length === 0 ? (
              <EmptyNote>{t("noLinks")}</EmptyNote>
            ) : (
              <ExternalLinks links={page.links} />
            )}
          </ProfileSection>
        </aside>
      </div>
    </div>
  )
}
