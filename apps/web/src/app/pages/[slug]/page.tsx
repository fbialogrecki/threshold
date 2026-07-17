import type { Metadata } from "next"
import { getLocale, getTranslations } from "next-intl/server"
import { notFound } from "next/navigation"

import { EventCard } from "@/components/cards/event-card"
import { FollowButton } from "@/components/profile/follow-button"
import { Avatar } from "@/components/ui/avatar"
import { Card, CardBody, CardHeader } from "@/components/ui/card"
import { MonoLabel } from "@/components/ui/mono-label"
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
    <div className="text-raw-white">
      <header className="flex flex-col gap-4 border-b border-border-gray pb-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex gap-4">
            <Avatar
              name={page.name}
              imageUrl={
                page.avatarMediaAssetId
                  ? mediaDerivativeUrl(page.avatarMediaAssetId, "avatar_512")
                  : null
              }
              size="lg"
            />
            <div>
              <h1 className="font-display text-5xl tracking-wide">{page.name}</h1>
              <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-violet">
                {[t(`types.${page.type}`), page.city ? cityLabel(page.city, locale) : null]
                  .filter(Boolean)
                  .join(" / ")}
              </p>
              <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-muted">
                {t("followers", { count: page.followerCount })}
              </p>
            </div>
          </div>
          {authUnavailable ? null : (
            <FollowButton
              handle={page.slug}
              targetType="page"
              loginHref={anonymousLoginHref}
              initialFollowing={initialFollowing}
            />
          )}
        </header>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <MonoLabel tone="dim">{t("upcoming")}</MonoLabel>
              </CardHeader>
              <CardBody className="flex flex-col gap-3">
                {upcomingEvents.length > 0 ? (
                  upcomingEvents.map((event) => (
                    <EventCard
                      key={event.id}
                      event={event}
                      loginHref={anonymousLoginHref}
                      variant={authUnavailable ? "feed" : "interactive"}
                    />
                  ))
                ) : (
                  <p className="text-sm leading-7 text-muted">{t("noEvents")}</p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <MonoLabel tone="dim">{t("about")}</MonoLabel>
              </CardHeader>
              <CardBody>
                <p className="text-[15px] leading-7 text-dim-white">
                  {page.about || t("noAbout")}
                </p>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <MonoLabel tone="dim">{t("residents")}</MonoLabel>
            </CardHeader>
            <CardBody className="flex flex-col gap-2">
              {page.residents.length === 0 ? (
                <p className="text-sm text-muted">{t("noResidents")}</p>
              ) : (
                page.residents.map((resident) => (
                  <a
                    key={resident.handle}
                    href={`/u/${resident.handle}`}
                    className="font-mono text-xs uppercase tracking-label text-cyan hover:underline"
                  >
                    {resident.displayName} / {t("confirmed")}
                  </a>
                ))
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <MonoLabel tone="dim">{t("links")}</MonoLabel>
            </CardHeader>
            <CardBody className="flex flex-col gap-2">
              {page.links.length === 0 ? (
                <p className="text-sm text-muted">{t("noLinks")}</p>
              ) : (
                page.links.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-mono text-xs uppercase tracking-label text-cyan hover:underline"
                  >
                    {link.label} ↗
                  </a>
                ))
              )}
            </CardBody>
          </Card>
        </div>
    </div>
  )
}
