import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"

import { Card } from "@/components/ui/card"
import { MonoLabel } from "@/components/ui/mono-label"
import { formatRelative } from "@/lib/format"
import type { EventUpdate } from "@/lib/types"

export async function EventUpdateCard({ update }: { update: EventUpdate }) {
  const [locale, t] = await Promise.all([getLocale(), getTranslations("feed")])
  return (
    <Card as="article" className="border-l-2 border-l-violet">
      <div className="flex items-center justify-between border-b border-border-gray px-4 py-2">
        <MonoLabel tone="violet">{t("eventUpdate")}</MonoLabel>
        <MonoLabel tone="muted">{formatRelative(update.createdAtIso, locale)}</MonoLabel>
      </div>
      <div className="px-4 py-4">
        <Link href={`/events/${update.event.slug}`}>
          <h3 className="font-display text-2xl tracking-wide text-raw-white hover:text-acid">
            {update.event.title}
          </h3>
        </Link>
        <p className="mt-3 text-[15px] leading-7 text-dim-white">{update.body}</p>
      </div>
    </Card>
  )
}
