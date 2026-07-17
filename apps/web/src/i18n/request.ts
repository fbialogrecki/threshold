import { getRequestConfig } from "next-intl/server"
import { cookies, headers } from "next/headers"

import en from "../../messages/en.json"
import pl from "../../messages/pl.json"
import { LOCALE_COOKIE, resolveLocale } from "./locale"

type CatalogShape<T> = T extends Record<string, unknown>
  ? { [Key in keyof T]: CatalogShape<T[Key]> }
  : T extends string
    ? string
    : never

type ExactCatalogShape<Reference, Candidate> =
  CatalogShape<Reference> extends CatalogShape<Candidate>
    ? CatalogShape<Candidate> extends CatalogShape<Reference>
      ? Candidate
      : never
    : never

const checkedPl: ExactCatalogShape<typeof en, typeof pl> = pl
const messages = { en, pl: checkedPl }

export default getRequestConfig(async () => {
  const [cookieStore, headerStore] = await Promise.all([cookies(), headers()])
  const locale = resolveLocale(
    cookieStore.get(LOCALE_COOKIE)?.value,
    headerStore.get("accept-language"),
  )

  return { locale, messages: messages[locale] }
})
