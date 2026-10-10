import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"

import { Card } from "@/components/ui/card"
import { MonoLabel } from "@/components/ui/mono-label"
import { StatusBadge } from "@/components/ui/status-badge"
import { formatRelative } from "@/lib/format"
import type { AccessUpdate } from "@/lib/types"

/**
 * Unique Perlimen card type: the feed surfaces changes to the viewer's own
 * access status, not just posts. This reinforces the access-first product.
 */
export async function AccessUpdateCard({ update }: { update: AccessUpdate }) {
  const [locale, t] = await Promise.all([getLocale(), getTranslations("feed")])
  return (
    <Card as="article">
      <div className="flex items-center justify-between gap-3 border-b border-border-gray px-4 py-2.5 sm:px-5">
        <MonoLabel tone="protected">{t("accessUpdate")}</MonoLabel>
        <time dateTime={update.createdAtIso} className="text-[13px] text-muted">
          {formatRelative(update.createdAtIso, locale)}
        </time>
      </div>

      <div className="px-4 py-4 sm:px-5">
        <p className="text-[13px] text-muted">{t("perlimenSystem")}</p>
        <p className="mt-1.5 text-[15px] leading-7 text-raw-white">{update.note}</p>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <Link
            href={`/events/${update.event.slug}`}
            className="text-sm font-semibold text-acid transition-colors hover:text-raw-white"
          >
            {t("viewDetails")} →
          </Link>
          <StatusBadge
            status={update.state}
            label={t(`accessState.${update.state}`)}
          />
        </div>
      </div>
    </Card>
  )
}
