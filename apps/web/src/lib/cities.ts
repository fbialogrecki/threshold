export const CITY_OPTIONS = [
  { value: "Warsaw", labels: { en: "Warsaw", pl: "Warszawa" } },
  { value: "Wroclaw", labels: { en: "Wroclaw", pl: "Wrocław" } },
  { value: "Berlin", labels: { en: "Berlin", pl: "Berlin" } },
  { value: "Krakow", labels: { en: "Krakow", pl: "Kraków" } },
  { value: "Lodz", labels: { en: "Lodz", pl: "Łódź" } },
  { value: "Poznan", labels: { en: "Poznan", pl: "Poznań" } },
] as const

export type CanonicalCity = (typeof CITY_OPTIONS)[number]["value"]
export type CityLocale = keyof (typeof CITY_OPTIONS)[number]["labels"]

export function canonicalCity(value: unknown): CanonicalCity | null {
  if (typeof value !== "string") return null
  const input = value.trim()
  return CITY_OPTIONS.find(
    (city) =>
      city.value === input
      || Object.values(city.labels).some((label) => label === input),
  )?.value ?? null
}

export function cityLabel(value: string, locale: string = "en"): string {
  const city = CITY_OPTIONS.find((option) => option.value === value)
  return city?.labels[locale === "pl" ? "pl" : "en"] ?? value
}
