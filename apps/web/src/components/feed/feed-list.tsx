import { getTranslations } from "next-intl/server"

import { AccessUpdateCard } from "@/components/cards/access-update-card"
import { EventCard } from "@/components/cards/event-card"
import { EventUpdateCard } from "@/components/cards/event-update-card"
import { PostCard } from "@/components/cards/post-card"
import { EmptyState } from "@/components/ui/empty-state"
import type { FeedItem } from "@/lib/types"

export async function FeedList({ items, suggestions = [] }: { items: FeedItem[]; suggestions?: string[] }) {
  const t = await getTranslations("feed")
  if (items.length === 0) {
    return (
      <div className="flex flex-col gap-3">
        <EmptyState
          title={t("emptyTitle")}
          body={t("emptyBody")}
          actionLabel={t("emptyAction")}
          actionHref="/app/search"
          eyebrow={t("emptyEyebrow")}
        />
        {suggestions.length > 0 ? (
          <ul className="border border-border-gray bg-graphite p-4 font-mono text-[11px] uppercase tracking-label text-muted">
            {suggestions.map((suggestion) => (
              <li key={suggestion} className="py-1 text-dim-white">
                {suggestion}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {items.map((item) => {
        switch (item.kind) {
          case "post":
            return <PostCard key={item.post.id} post={item.post} />
          case "event":
            return <EventCard key={item.event.slug} event={item.event} variant="feed" />
          case "access_update":
            return (
              <AccessUpdateCard key={item.update.id} update={item.update} />
            )
          case "event_update":
            return <EventUpdateCard key={item.update.id} update={item.update} />
          case "residency_update":
          case "lineup_update":
          case "guestlist_update":
            return null
        }
      })}
    </div>
  )
}
