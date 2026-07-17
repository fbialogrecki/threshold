import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import { notFound } from "next/navigation"

import { EventCard } from "@/components/cards/event-card"
import { FollowButton } from "@/components/profile/follow-button"
import { Avatar } from "@/components/ui/avatar"
import { Card, CardBody, CardHeader } from "@/components/ui/card"
import { MonoLabel } from "@/components/ui/mono-label"
import { listEvents } from "@/lib/api/events"
import { getFollowedKeys, followKey, getProfile } from "@/lib/api/users-read"
import {
  hasRequiredOnboarding,
  loginHref,
} from "@/lib/auth/routing"
import { getSessionState } from "@/lib/auth/session"
import { absoluteMediaDerivativeUrl, mediaDerivativeUrl } from "@/lib/media/urls"

export const dynamic = "force-dynamic"

export async function generateMetadata({
  params,
}: {
  params: Promise<{ username: string }>
}): Promise<Metadata> {
  const { username } = await params
  const [profile, t] = await Promise.all([
    getProfile(username),
    getTranslations("publicProfile"),
  ])
  if (!profile) return { title: t("notFound") }

  const description = profile.role
    ? `${profile.role}${profile.location ? ` · ${profile.location}` : ""}. ${profile.bio}`
    : profile.bio || t("metadataFallback", { username: profile.username })
  const image = profile.avatarMediaAssetId
    ? absoluteMediaDerivativeUrl(profile.avatarMediaAssetId, "avatar_512")
    : undefined
  return {
    title: profile.displayName,
    description,
    openGraph: {
      title: profile.displayName,
      description,
      type: "profile",
      ...(image ? { images: [{ url: image }] } : {}),
    },
  }
}

export default async function ArtistProfilePage({
  params,
}: {
  params: Promise<{ username: string }>
}) {
  const { username } = await params
  const [profile, t] = await Promise.all([
    getProfile(username),
    getTranslations("publicProfile"),
  ])
  if (!profile) notFound()

  const sessionState = await getSessionState()
  const isAuthenticated = sessionState.status === "authenticated"
    && hasRequiredOnboarding(sessionState.session)
  const authUnavailable = sessionState.status === "unavailable"
  const anonymousLoginHref = isAuthenticated
    ? undefined
    : loginHref(`/u/${encodeURIComponent(username)}`)
  const targetType = profile.type === "artist" ? "artist" : "consumer"
  const upcomingEvents = profile.artistProfileId
    ? await listEvents({ artistProfileId: profile.artistProfileId, limit: 20, upcoming: true })
    : []

  let initialFollowing = false
  if (isAuthenticated) {
    const followed = await getFollowedKeys()
    initialFollowing = followed.has(followKey(targetType, profile.username))
  }

  return (
    <div className="text-raw-white">
      <header className="flex flex-col gap-4 border-b border-border-gray pb-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex gap-4">
            <Avatar
              name={profile.displayName}
              imageUrl={
                profile.avatarMediaAssetId
                  ? mediaDerivativeUrl(profile.avatarMediaAssetId, "avatar_512")
                  : null
              }
              size="lg"
            />
            <div className="min-w-0">
              <h1 className="break-words font-display text-[clamp(2rem,6vw,3rem)] leading-tight tracking-wide">
                {profile.displayName}
              </h1>
              <p className="font-mono text-[11px] uppercase tracking-label text-muted">
                @{profile.username}
              </p>
              {profile.role || profile.location ? (
                <p className="mt-2 font-mono text-[11px] uppercase tracking-label text-violet">
                  {[profile.role, profile.location].filter(Boolean).join(" / ")}
                </p>
              ) : null}
              <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-muted">
                {t("followers", { count: profile.followerCount })}
              </p>
            </div>
          </div>
          {authUnavailable ? null : (
            <FollowButton
              handle={profile.username}
              targetType={targetType}
              loginHref={anonymousLoginHref}
              initialFollowing={initialFollowing}
            />
          )}
        </header>

        <div
          className={
            profile.links.length > 0
              ? "mt-6 grid gap-6 lg:grid-cols-[1fr_320px]"
              : "mt-6 grid gap-6"
          }
        >
          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader>
                <MonoLabel tone="dim">{t("bio")}</MonoLabel>
              </CardHeader>
              <CardBody>
                <p className="text-[15px] leading-7 text-dim-white">
                  {profile.bio || t("noBio")}
                </p>
              </CardBody>
            </Card>

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

            {profile.residencies.length > 0 ? (
              <Card>
                <CardHeader>
                  <MonoLabel tone="dim">{t("residencies")}</MonoLabel>
                </CardHeader>
                <CardBody className="flex flex-col gap-2">
                  {profile.residencies.map((residency) => (
                    <a
                      key={residency.pageHandle}
                      href={`/pages/${residency.pageHandle}`}
                      className="font-mono text-xs uppercase tracking-label text-cyan hover:underline"
                    >
                      {residency.pageName} / {t("confirmed")}
                    </a>
                  ))}
                </CardBody>
              </Card>
            ) : null}
          </div>

          {profile.links.length > 0 ? (
            <div className="flex flex-col gap-6">
              <Card>
                <CardHeader>
                  <MonoLabel tone="dim">{t("links")}</MonoLabel>
                </CardHeader>
                <CardBody className="flex flex-col gap-2">
                  {profile.links.map((link) => (
                    <a
                      key={link.url}
                      href={link.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-mono text-xs uppercase tracking-label text-cyan hover:underline"
                    >
                      {link.label} ↗
                    </a>
                  ))}
                </CardBody>
              </Card>
            </div>
          ) : null}
        </div>
    </div>
  )
}
