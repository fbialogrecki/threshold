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
      className="fixed inset-x-0 bottom-0 z-40 flex items-stretch border-t border-border-gray bg-pitch/90 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur-md lg:hidden"
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
            "grid size-12 touch-manipulation place-items-center rounded-full bg-acid text-pitch shadow-[0_8px_24px_-10px_rgba(198,255,0,0.7)] transition-[scale,background-color] duration-150 ease-press hover:bg-acid-bright active:scale-90",
            composeActive && "ring-2 ring-raw-white ring-offset-2 ring-offset-pitch",
          )}
        >
          <Plus size={22} weight="bold" aria-hidden />
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
        "group flex min-h-14 min-w-0 flex-1 touch-manipulation flex-col items-center justify-center gap-1 rounded-control py-1.5 text-[11px] font-medium",
        active ? "text-raw-white" : "text-muted hover:text-dim-white",
      )}
    >
      <span
        className={cn(
          "grid h-7 w-12 place-items-center rounded-full transition-[background-color,color,scale] duration-200 ease-press group-active:scale-90",
          active ? "bg-acid/15 text-acid" : "",
        )}
      >
        <Icon size={20} weight={active ? "fill" : "regular"} aria-hidden />
      </span>
      <span className="w-full text-center leading-tight [overflow-wrap:anywhere]">{label}</span>
    </Link>
  )
}
