import { LockKey, MapPin } from "@phosphor-icons/react/ssr"
import { getLocale, getTranslations } from "next-intl/server"

import { Card, CardBody, CardHeader } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import { cityLabel } from "@/lib/cities"
import type { PerlimenEvent } from "@/lib/types"

export async function LocationStates({ event }: { event: PerlimenEvent }) {
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
            <MapPin size={18} weight="bold" className="text-muted" aria-hidden />
            <h2 className="text-lg font-semibold">{t("title")}</h2>
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
            <h2 className="text-lg font-semibold">{t("title")}</h2>
          </div>
          <StatusBadge status="tba" label={t("tba")} />
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
          {/* Protection reads as full contrast plus a padlock; violet is the downvote. */}
          <LockKey size={18} weight="bold" className="text-raw-white" aria-hidden />
          <h2 className="text-lg font-semibold">{t("title")}</h2>
        </div>
        <StatusBadge status="secret" label={t("secret")} />
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        <p className="text-sm leading-7 text-dim-white">
          {t("secretBody")}
        </p>
        <p className="text-sm text-muted">
          {t("city", { city })}
        </p>
      </CardBody>
    </Card>
  )
}
