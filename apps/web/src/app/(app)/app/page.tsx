import { getLocale, getTranslations } from "next-intl/server"

import { auth } from "@/auth"
import { FeedComposer } from "@/components/feed/feed-composer"
import { FeedList } from "@/components/feed/feed-list"
import { MonoLabel } from "@/components/ui/mono-label"
import { getFeed } from "@/lib/api/feed"
import { cityLabel } from "@/lib/cities"

export const dynamic = "force-dynamic"

export default async function FeedPage() {
  const [items, session, t, locale] = await Promise.all([
    getFeed(),
    auth(),
    getTranslations("feed"),
    getLocale(),
  ])
  const city = session?.onboarding_preferences?.city ?? null
  const displayCity = city ? cityLabel(city, locale) : null
  const scenes = session?.onboarding_preferences?.preferred_scenes
    ?.split(",")
    .map((scene) => scene.trim())
    .filter(Boolean) ?? []
  const suggestions = [
    displayCity ? t("suggestionCityGroup", { city: displayCity }) : t("suggestionAnyCityGroup"),
    scenes.length > 0 ? t("suggestionScenes", { scenes: scenes.join(" / ") }) : t("suggestionFollows"),
    displayCity ? t("suggestionCityEvents", { city: displayCity }) : t("suggestionEvents"),
  ]

  return (
    <div className="flex flex-col gap-6">
      <header className="border-b border-border-gray pb-4">
        <div>
          <h1 className="font-display text-4xl tracking-wide text-raw-white">
            {t("title")}
          </h1>
          <MonoLabel tone="muted" className="mt-1 block">
            {t("newest")}
          </MonoLabel>
        </div>
      </header>

      <FeedComposer />
      <FeedList items={items} suggestions={suggestions} />
    </div>
  )
}
