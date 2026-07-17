"use client"

import { useLocale, useTranslations } from "next-intl"
import { useRouter } from "next/navigation"

import { setLocaleCookie } from "@/i18n/actions"
import { LOCALES, type Locale } from "@/i18n/locale"
import { cn } from "@/lib/cn"

export function LocaleSwitcher({ className }: { className?: string }) {
  const locale = useLocale()
  const t = useTranslations("common.locale")
  const router = useRouter()

  async function selectLocale(nextLocale: Locale) {
    if (nextLocale === locale) return
    await setLocaleCookie(nextLocale)
    router.refresh()
  }

  return (
    <div
      role="group"
      aria-label={t("label")}
      className={cn("inline-flex border border-border-gray bg-graphite", className)}
    >
      {LOCALES.slice().reverse().map((nextLocale) => {
        const active = nextLocale === locale
        return (
          <button
            key={nextLocale}
            type="button"
            aria-label={t(active ? "current" : "switchTo", {
              locale: t(nextLocale),
            })}
            aria-pressed={active}
            onClick={() => void selectLocale(nextLocale)}
            className={cn(
              "px-2 py-1 font-mono text-[10px] uppercase tracking-label transition-colors",
              active
                ? "bg-status-neutral-border text-raw-white"
                : "text-muted hover:bg-raised hover:text-raw-white",
            )}
          >
            {nextLocale}
          </button>
        )
      })}
    </div>
  )
}
