import { describe, expect, test } from "bun:test"

const load = async (locale: string): Promise<unknown> =>
  JSON.parse(await Bun.file(new URL(`../../messages/${locale}.json`, import.meta.url)).text())

function leafKeys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null) return [prefix]
  return Object.entries(value).flatMap(([key, child]) =>
    leafKeys(child, prefix ? `${prefix}.${key}` : key),
  )
}

describe("message catalogues", () => {
  test("pl and en expose an identical set of keys", async () => {
    const [en, pl] = await Promise.all([load("en"), load("pl")])
    const enKeys = leafKeys(en)
    const plKeys = leafKeys(pl)

    expect(plKeys.filter((key) => !enKeys.includes(key))).toEqual([])
    expect(enKeys.filter((key) => !plKeys.includes(key))).toEqual([])
  })
})
