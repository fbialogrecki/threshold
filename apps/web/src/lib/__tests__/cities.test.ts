import { describe, expect, it } from "bun:test"

import { canonicalCity, cityLabel, CITY_OPTIONS } from "../cities"

describe("canonical cities", () => {
  it("keeps every supported canonical and display pair", () => {
    expect(CITY_OPTIONS).toEqual([
      { value: "Warsaw", labels: { en: "Warsaw", pl: "Warszawa" } },
      { value: "Wroclaw", labels: { en: "Wroclaw", pl: "Wrocław" } },
      { value: "Berlin", labels: { en: "Berlin", pl: "Berlin" } },
      { value: "Krakow", labels: { en: "Krakow", pl: "Kraków" } },
      { value: "Lodz", labels: { en: "Lodz", pl: "Łódź" } },
      { value: "Poznan", labels: { en: "Poznan", pl: "Poznań" } },
    ])
  })

  it("accepts persisted canonical values and localized display forms", () => {
    for (const city of CITY_OPTIONS) {
      expect(canonicalCity(city.value)).toBe(city.value)
      expect(canonicalCity(city.labels.en)).toBe(city.value)
      expect(canonicalCity(city.labels.pl)).toBe(city.value)
      expect(cityLabel(city.value, "en")).toBe(city.labels.en)
      expect(cityLabel(city.value, "pl")).toBe(city.labels.pl)
    }
  })

  it("falls back to English labels for unknown locales", () => {
    expect(cityLabel("Warsaw", "de")).toBe("Warsaw")
    expect(cityLabel("Unknown", "pl")).toBe("Unknown")
  })
})
