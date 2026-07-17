function intlLocale(locale: string): string {
  if (locale === "en") return "en-GB"
  if (locale === "pl") return "pl-PL"
  return locale
}

export function formatEventDate(iso: string, locale = "en"): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ""
  return new Intl.DateTimeFormat(intlLocale(locale), {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(date)
}

export function formatRelative(iso: string, locale = "en", nowIso?: string): string {
  const then = new Date(iso).getTime()
  const now = nowIso ? new Date(nowIso).getTime() : Date.now()
  if (Number.isNaN(then) || Number.isNaN(now)) return ""

  const diffMs = Math.max(0, now - then)
  const minutes = Math.floor(diffMs / 60000)
  const relative = new Intl.RelativeTimeFormat(intlLocale(locale), {
    numeric: "auto",
    style: "narrow",
  })
  if (minutes < 1) return relative.format(0, "second")
  if (minutes < 60) return relative.format(-minutes, "minute")
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return relative.format(-hours, "hour")
  const days = Math.floor(hours / 24)
  if (days < 7) return relative.format(-days, "day")
  const weeks = Math.floor(days / 7)
  return relative.format(-weeks, "week")
}
