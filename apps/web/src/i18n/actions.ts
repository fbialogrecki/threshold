"use server"

import { cookies } from "next/headers"

import { isLocale, LOCALE_COOKIE } from "./locale"

export async function setLocaleCookie(locale: string) {
  if (!isLocale(locale)) throw new Error("Unsupported locale")

  const cookieStore = await cookies()
  cookieStore.set(LOCALE_COOKIE, locale, {
    maxAge: 60 * 60 * 24 * 365,
    path: "/",
    sameSite: "lax",
  })
}
