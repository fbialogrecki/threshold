export const LOCALE_COOKIE = "threshold_locale"
export const DEFAULT_LOCALE = "en"
export const LOCALES = ["en", "pl"] as const

export type Locale = (typeof LOCALES)[number]

export function isLocale(value: string | null | undefined): value is Locale {
  return LOCALES.includes(value as Locale)
}

export function resolveLocale(
  cookieLocale: string | null | undefined,
  acceptLanguage: string | null | undefined,
): Locale {
  if (isLocale(cookieLocale)) return cookieLocale

  const preferred = (acceptLanguage ?? "")
    .split(",")
    .map((entry, index) => {
      const [tag, ...parameters] = entry.trim().toLowerCase().split(";")
      const locale = tag.split("-")[0]
      const qualityParameter = parameters.find((parameter) =>
        parameter.trim().startsWith("q="),
      )
      const quality = qualityParameter
        ? Number(qualityParameter.trim().slice(2))
        : 1

      return { index, locale, quality }
    })
    .filter(
      ({ locale, quality }) =>
        isLocale(locale) &&
        Number.isFinite(quality) &&
        quality > 0 &&
        quality <= 1,
    )
    .sort((a, b) => b.quality - a.quality || a.index - b.index)[0]?.locale

  return isLocale(preferred) ? preferred : DEFAULT_LOCALE
}
