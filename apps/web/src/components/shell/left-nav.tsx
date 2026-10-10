"use client"

import { CalendarDots, House, PencilSimpleLine, UsersThree } from "@phosphor-icons/react"
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
  const composeActive = isNavActive("/app/compose", pathname)

  return (
    <div>
      <Link href="/app" translate="no" className="flex items-center gap-1.5 px-3">
        <span className="font-display text-2xl tracking-[0.1em] text-raw-white">PERLIMEN</span>
        <span className="size-2 rounded-full bg-acid" aria-hidden />
      </Link>

      <div className="mt-6">
        <SearchBar compact />
      </div>

      <nav aria-label={shell("primaryNavigation")} className="mt-5">
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
                    "group relative flex items-center gap-3 rounded-control px-3 py-2.5 text-[15px] font-medium transition-colors",
                    active
                      ? "bg-acid/10 text-acid"
                      : "text-dim-white hover:bg-raised hover:text-raw-white",
                  )}
                >
                  <span
                    aria-hidden
                    className={cn(
                      "absolute inset-y-2 left-0 w-[3px] rounded-full bg-acid transition-transform duration-300 ease-out-expo",
                      active ? "scale-y-100" : "scale-y-0",
                    )}
                  />
                  <Icon
                    size={20}
                    weight={active ? "fill" : "regular"}
                    className="transition-transform duration-200 ease-press group-active:scale-90"
                    aria-hidden
                  />
                  <span className="flex-1">{navigation(item.label)}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      <Link
        href="/app/compose"
        aria-current={composeActive ? "page" : undefined}
        className="mt-4 flex min-h-11 items-center justify-center gap-2 rounded-control bg-acid px-4 text-[15px] font-semibold text-pitch transition-[background-color,scale] duration-150 ease-press hover:bg-acid-bright active:scale-[0.97]"
      >
        <PencilSimpleLine size={18} weight="bold" aria-hidden />
        {navigation("post")}
      </Link>
    </div>
  )
}
