import { ArrowRight } from "@phosphor-icons/react/ssr"
import { getTranslations } from "next-intl/server"
import Link from "next/link"

import { AccessUpdateCard } from "@/components/cards/access-update-card"
import { EventCard } from "@/components/cards/event-card"
import { EventUpdateCard } from "@/components/cards/event-update-card"
import { PostCard } from "@/components/cards/post-card"
import { EmptyState } from "@/components/ui/empty-state"
import type { FeedItem } from "@/lib/types"

export async function FeedList({
  items,
  suggestions = [],
}: {
  items: FeedItem[]
  suggestions?: { label: string; href: string }[]
}) {
  const t = await getTranslations("feed")
  if (items.length === 0) {
    return (
      <EmptyState
        title={t("emptyTitle")}
        body={t("emptyBody")}
        actionLabel={t("emptyAction")}
        actionHref="/app/search"
        eyebrow={t("emptyEyebrow")}
      >
        {suggestions.length > 0 ? (
          <ul className="mt-3 grid w-full gap-2 sm:grid-cols-3">
            {suggestions.map((suggestion) => (
              <li key={suggestion.href}>
                <Link
                  href={suggestion.href}
                  className="group flex h-full items-start justify-between gap-3 rounded-control border border-border-gray bg-pitch/60 p-4 text-[15px] leading-6 text-raw-white transition-colors hover:border-acid"
                >
                  {suggestion.label}
                  <ArrowRight
                    size={16}
                    className="mt-1 shrink-0 text-acid transition-transform duration-200 ease-out-expo group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </EmptyState>
    )
  }

  // Chronological, newest first, exactly as delivered: no reordering here.
  return (
    <div className="flex flex-col gap-3">
      {items.map((item) => {
        switch (item.kind) {
          case "post":
            return <PostCard key={item.post.id} post={item.post} />
          case "event":
            return <EventCard key={item.event.slug} event={item.event} variant="feed" />
          case "access_update":
            return <AccessUpdateCard key={item.update.id} update={item.update} />
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
