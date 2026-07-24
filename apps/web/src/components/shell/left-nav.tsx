"use client"

import { CalendarDots, House, UsersThree } from "@phosphor-icons/react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { usePathname } from "next/navigation"

import { isNavActive } from "@/components/shell/nav-active"
import { SearchBar } from "@/components/shell/search-bar"
import { cn } from "@/lib/cn"

// Notifications, settings and logout live in the profile dock as icons: they
// are account chrome, not destinations worth a labelled row each.
const NAV_ITEMS = [
  { href: "/app", label: "feed", icon: House },
  { href: "/app/events", label: "events", icon: CalendarDots },
  { href: "/groups", label: "groups", icon: UsersThree },
] as const

export function LeftNav() {
  const pathname = usePathname()
  const navigation = useTranslations("navigation")
  const shell = useTranslations("shell")

  return (
    <div>
      <Link href="/app" className="block">
        <span className="font-display text-2xl tracking-[0.08em] text-raw-white">
          THRESHOLD<span className="text-acid">▮</span>
        </span>
      </Link>

      <div className="mt-6">
        <SearchBar compact />
      </div>

      <nav aria-label={shell("primaryNavigation")} className="mt-4">
        <ul className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => {
            const active = isNavActive(item.href, pathname)
            const Icon = item.icon
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-3 border-l-2 px-3 py-2 font-mono text-sm uppercase tracking-label transition-colors",
                    active
                      ? "border-acid text-acid"
                      : "border-transparent text-dim-white hover:text-raw-white",
                  )}
                >
                  <Icon size={18} weight={active ? "fill" : "regular"} aria-hidden />
                  <span className="flex-1">{navigation(item.label)}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

    </div>
  )
}
