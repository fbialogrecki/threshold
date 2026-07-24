"use client"

import { CalendarDots, House, MagnifyingGlass, Plus, UsersThree } from "@phosphor-icons/react"
import Link from "next/link"
import { useTranslations } from "next-intl"
import { usePathname } from "next/navigation"

import { isNavActive } from "@/components/shell/nav-active"
import { cn } from "@/lib/cn"

/*
  Thumb-zone navigation: the destinations a reader uses constantly, plus writing
  as the one primary action, centred. Notifications and the account live in the
  top bar because they are reached far less often. The set matches the desktop
  rail, so the two breakpoints teach one model instead of two.
*/
const ITEMS = [
  { href: "/app", label: "feed", icon: House },
  { href: "/app/events", label: "events", icon: CalendarDots },
  { href: "/app/search", label: "search", icon: MagnifyingGlass },
  { href: "/groups", label: "groups", icon: UsersThree },
] as const

export function MobileNav() {
  const pathname = usePathname()
  const navigation = useTranslations("navigation")
  const shell = useTranslations("shell")
  const composeActive = isNavActive("/app/compose", pathname)

  return (
    <nav
      aria-label={shell("mobileNavigation")}
      className="fixed inset-x-0 bottom-0 z-40 flex items-stretch border-t border-border-gray bg-pitch pb-[env(safe-area-inset-bottom)] lg:hidden"
    >
      {ITEMS.slice(0, 2).map((item) => (
        <NavItem key={item.href} {...item} pathname={pathname} label={navigation(item.label)} />
      ))}

      <div className="flex flex-1 items-center justify-center py-2">
        <Link
          href="/app/compose"
          aria-current={composeActive ? "page" : undefined}
          aria-label={navigation("post")}
          className={cn(
            "flex h-10 w-10 items-center justify-center border transition-colors focus-visible:outline-2 focus-visible:outline-acid",
            composeActive
              ? "border-acid bg-acid text-pitch"
              : "border-acid text-acid hover:bg-acid hover:text-pitch",
          )}
        >
          <Plus size={20} weight="bold" aria-hidden />
        </Link>
      </div>

      {ITEMS.slice(2).map((item) => (
        <NavItem key={item.href} {...item} pathname={pathname} label={navigation(item.label)} />
      ))}
    </nav>
  )
}

function NavItem({
  href,
  icon: Icon,
  label,
  pathname,
}: {
  href: string
  icon: typeof House
  label: string
  pathname: string
}) {
  const active = isNavActive(href, pathname)
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex min-w-0 flex-1 flex-col items-center gap-1 py-2 font-mono text-[10px] uppercase tracking-label focus-visible:outline-2 focus-visible:outline-acid",
        active ? "text-acid" : "text-muted",
      )}
    >
      <Icon size={19} weight={active ? "fill" : "regular"} aria-hidden />
      <span className="w-full text-center leading-tight [overflow-wrap:anywhere]">{label}</span>
    </Link>
  )
}
