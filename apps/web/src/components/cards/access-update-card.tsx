import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"

import { Card } from "@/components/ui/card"
import { MonoLabel } from "@/components/ui/mono-label"
import { StatusBadge } from "@/components/ui/status-badge"
import { formatRelative } from "@/lib/format"
import type { AccessUpdate } from "@/lib/types"

/**
 * Unique Threshold card type: the feed surfaces changes to the viewer's own
 * access status, not just posts. This reinforces the access-first product.
 */
export async function AccessUpdateCard({ update }: { update: AccessUpdate }) {
  const [locale, t] = await Promise.all([getLocale(), getTranslations("feed")])
  return (
    <Card as="article" className="border-l-2 border-l-acid">
      <div className="flex items-center justify-between border-b border-border-gray px-4 py-2">
        <MonoLabel tone="cyan">{t("accessUpdate")}</MonoLabel>
        <MonoLabel tone="muted">{formatRelative(update.createdAtIso, locale)}</MonoLabel>
      </div>

      <div className="px-4 py-4">
        <p className="font-mono text-[11px] uppercase tracking-label text-muted">
          {t("thresholdSystem")}
        </p>
        <p className="mt-2 text-[15px] leading-7 text-raw-white">{update.note}</p>

        <div className="mt-4 flex items-center justify-between">
          <Link
            href={`/events/${update.event.slug}`}
            className="font-mono text-[11px] uppercase tracking-label text-cyan hover:underline"
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
