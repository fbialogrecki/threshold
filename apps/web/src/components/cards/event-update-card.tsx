import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"

import { Card } from "@/components/ui/card"
import { MonoLabel } from "@/components/ui/mono-label"
import { formatRelative } from "@/lib/format"
import type { EventUpdate } from "@/lib/types"

export async function EventUpdateCard({ update }: { update: EventUpdate }) {
  const [locale, t] = await Promise.all([getLocale(), getTranslations("feed")])
  return (
    <Card as="article">
      <div className="flex items-center justify-between gap-3 border-b border-border-gray px-4 py-2.5 sm:px-5">
        <MonoLabel tone="muted">{t("eventUpdate")}</MonoLabel>
        <time dateTime={update.createdAtIso} className="text-[13px] text-muted">
          {formatRelative(update.createdAtIso, locale)}
        </time>
      </div>
      <div className="px-4 py-4 sm:px-5">
        <Link href={`/events/${update.event.slug}`}>
          <h3 className="font-display text-2xl break-words text-raw-white transition-colors hover:text-acid">
            {update.event.title}
          </h3>
        </Link>
        <p className="mt-3 text-[15px] leading-7 text-dim-white">{update.body}</p>
      </div>
    </Card>
  )
}
