import { SafetyActions } from "@/components/social/safety-actions"
import { safetyAllowed } from "@/lib/safety/actions"
import { getAccountBlockState } from "@/lib/safety/block-state"
import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
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
    title: profile.username,
    description,
    openGraph: {
      title: profile.username,
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
  const viewerId = isAuthenticated ? sessionState.session.user.id : null
  const canUseSafety = safetyAllowed(viewerId, profile.id) && Boolean(profile.username)
  const blocked = canUseSafety ? await getAccountBlockState(viewerId!, profile.id) : null
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

  // Anonymised accounts have no username left, so the label stands in for it.
  const name = profile.username || t("deletedAccount")

  return (
    <div className="flex flex-col gap-8 text-raw-white">
      <div>
        <ProfileHeader
          avatar={(
            <Avatar
              name={name}
              imageUrl={
                profile.avatarMediaAssetId
                  ? mediaDerivativeUrl(profile.avatarMediaAssetId, "avatar_512")
                  : null
              }
              size="lg"
            />
          )}
          actions={authUnavailable ? null : (
            <FollowButton
              handle={profile.username}
              targetType={targetType}
              loginHref={anonymousLoginHref}
              initialFollowing={initialFollowing}
            />
          )}
        >
          {/* One public name: the unique username, in the case its owner chose. */}
          <h1 className="break-words text-[clamp(1.5rem,10cqi,2.25rem)] font-semibold leading-tight">
            {name}
          </h1>
          {profile.role || profile.location ? (
            <p className="mt-1.5 text-[15px] text-dim-white">
              {[profile.role, profile.location].filter(Boolean).join(" · ")}
            </p>
          ) : null}
          <p className="mt-1 text-[13px] text-muted">
            {t("followers", { count: profile.followerCount })}
          </p>
        </ProfileHeader>

        <SafetyActions key={`${profile.id}:${blocked}`} allowed={canUseSafety} target={{ type: "profile", target: profile.username }} username={profile.username} initialBlocked={blocked} />
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-w-0 flex-col gap-8">
          <ProfileSection title={t("bio")}>
            {profile.bio ? (
              <p className="max-w-[65ch] whitespace-pre-wrap break-words text-[15px] leading-7 text-dim-white">
                {profile.bio}
              </p>
            ) : (
              <EmptyNote>{t("noBio")}</EmptyNote>
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

        {profile.residencies.length > 0 || profile.links.length > 0 ? (
          <aside className="flex min-w-0 flex-col gap-8">
            {profile.residencies.length > 0 ? (
              <ProfileSection title={t("residencies")}>
                <ul className="flex flex-col gap-2">
                  {profile.residencies.map((residency) => (
                    <li key={residency.pageHandle}>
                      <Link
                        href={`/pages/${residency.pageHandle}`}
                        className="flex items-center justify-between gap-3 rounded-control border border-border-gray bg-graphite/60 px-4 py-3 transition-colors hover:border-acid"
                      >
                        <span className="min-w-0 truncate font-display text-base">{residency.pageName}</span>
                        <span className="shrink-0 text-xs text-muted">{t("confirmed")}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </ProfileSection>
            ) : null}
            {profile.links.length > 0 ? (
              <ProfileSection title={t("links")}>
                <ExternalLinks links={profile.links} />
              </ProfileSection>
            ) : null}
          </aside>
        ) : null}
      </div>
    </div>
  )
}
