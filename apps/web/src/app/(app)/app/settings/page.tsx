import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { SettingsForm, type SettingsInitial } from "@/components/settings/settings-form"
import { EmptyState } from "@/components/ui/empty-state"
import { MonoLabel } from "@/components/ui/mono-label"
import { getNotificationPreferences, me } from "@/lib/auth/product-auth"
import { notificationPreferenceLoad } from "@/lib/notification-preferences"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("settings.metadata")
  return { title: t("title"), description: t("description") }
}

type ProfileBody = {
  user?: { username?: string | null }
  consumer_profile?: { display_name?: string | null; bio?: string | null; avatar_media_asset_id?: string | null }
  onboarding_preferences?: { city?: string | null }
  artist_profile?: {
    role?: string | null
    location?: string | null
    links?: { label?: string; url?: string }[]
  } | null
}

export default async function SettingsPage() {
  const [response, preferenceResponse, t] = await Promise.all([
    me().catch(() => null),
    getNotificationPreferences().catch(() => null),
    getTranslations("settings"),
  ])
  if (
    !response
    || response.status !== 200
    || typeof response.body !== "object"
    || response.body === null
  ) {
    return (
      <EmptyState
        eyebrow={t("loadErrorEyebrow")}
        title={t("loadErrorTitle")}
        body={t("loadErrorBody")}
        actionLabel={t("retry")}
        actionHref="/app/settings"
      />
    )
  }
  const body = response.body as ProfileBody
  const preferences = notificationPreferenceLoad(
    preferenceResponse?.status ?? null,
    preferenceResponse?.body,
  )

  const artist = body?.artist_profile ?? null
  const initial: SettingsInitial = {
    username: body?.user?.username ?? "",
    displayName: body?.consumer_profile?.display_name ?? "",
    bio: body?.consumer_profile?.bio ?? "",
    city: body?.onboarding_preferences?.city ?? "",
    avatarMediaAssetId: body?.consumer_profile?.avatar_media_asset_id ?? "",
    isArtist: artist !== null,
    role: artist?.role ?? "",
    location: artist?.location ?? "",
    links: (artist?.links ?? [])
      .map((l) => ({ label: l.label ?? "", url: l.url ?? "" }))
      .filter((l) => l.label && l.url),
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header className="border-b border-border-gray pb-4">
        <h1 className="font-display text-4xl tracking-wide text-raw-white">
          {t("title")}
        </h1>
        <MonoLabel tone="muted" className="mt-1 block">
          {t("subtitle")}
        </MonoLabel>
      </header>

      <SettingsForm initial={initial} notificationPreferences={preferences} />
    </div>
  )
}
