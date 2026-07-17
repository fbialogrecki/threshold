import { LockKey, MapPin } from "@phosphor-icons/react/ssr"
import { getLocale, getTranslations } from "next-intl/server"

import { Card, CardBody, CardHeader } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import { cityLabel } from "@/lib/cities"
import type { ThresholdEvent } from "@/lib/types"

export async function LocationStates({ event }: { event: ThresholdEvent }) {
  const [t, locale] = await Promise.all([
    getTranslations("eventDetail.location"),
    getLocale(),
  ])
  const city = event.city ? cityLabel(event.city, locale) : t("undisclosed")

  if (event.location_mode === "public_location") {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <MapPin size={18} weight="bold" className="text-cyan" aria-hidden />
            <h2 className="font-display text-2xl tracking-wide">{t("title")}</h2>
          </div>
          <StatusBadge status="public" label={t("public")} />
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          {event.venue_name ? (
            <p className="text-lg text-raw-white">{event.venue_name}</p>
          ) : null}
          {event.address ? (
            <p className="text-sm text-dim-white">{event.address}</p>
          ) : null}
        </CardBody>
      </Card>
    )
  }

  if (event.location_mode === "tba") {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <MapPin size={18} weight="bold" className="text-status-neutral" aria-hidden />
            <h2 className="font-display text-2xl tracking-wide">{t("title")}</h2>
          </div>
          <StatusBadge status="neutral" label={t("tba")} />
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          <p className="text-lg text-raw-white">{city}</p>
          <p className="text-sm leading-7 text-dim-white">
            {t("tbaBody")}
          </p>
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <LockKey size={18} weight="bold" className="text-violet" aria-hidden />
          <h2 className="font-display text-2xl tracking-wide">{t("title")}</h2>
        </div>
        <StatusBadge status="secret" label={t("secret")} />
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        <p className="text-sm leading-7 text-dim-white">
          {t("secretBody")}
        </p>
        <p className="font-mono text-[11px] uppercase tracking-label text-muted">
          {t("city", { city })}
        </p>
      </CardBody>
    </Card>
  )
}
