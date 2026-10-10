import { getLocale, getTranslations } from "next-intl/server"

import { auth } from "@/auth"
import { FeedComposer } from "@/components/feed/feed-composer"
import { FeedList } from "@/components/feed/feed-list"
import { getFeed } from "@/lib/api/feed"
import { cityLabel } from "@/lib/cities"
import { emptyFeedActions } from "@/lib/feed/empty-actions"

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
  const suggestions = emptyFeedActions(displayCity, scenes).map((action) => ({
    label: "values" in action ? t(action.key, action.values) : t(action.key),
    href: action.href,
  }))

  // The visible title is gone: the active nav state and the brand mark already
  // say where you are. Screen readers still need the landmark, so it stays.
  return (
    <div className="flex flex-col gap-4">
      <h1 className="sr-only">{t("title")}</h1>
      <FeedComposer />
      <FeedList items={items} suggestions={suggestions} />
    </div>
  )
}
