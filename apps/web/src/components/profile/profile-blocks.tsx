import { ArrowUpRight } from "@phosphor-icons/react/ssr"
import type { ReactNode } from "react"

import { cn } from "@/lib/cn"

/** Header surface shared by person and Page profiles. */
export function ProfileHeader({
  avatar,
  children,
  actions,
}: {
  avatar: ReactNode
  children: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-5 rounded-surface border border-border-gray bg-[radial-gradient(30rem_16rem_at_100%_0%,rgba(198,255,0,0.06),transparent_70%)] p-5 sm:flex-row sm:items-end sm:justify-between sm:p-7">
      <div className="flex min-w-0 flex-1 items-start gap-4 sm:items-center sm:gap-5">
        {avatar}
        <div className="@container min-w-0 flex-1">{children}</div>
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </header>
  )
}

export function ProfileSection({
  title,
  children,
  className,
}: {
  title: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn("min-w-0", className)}>
      <h2 className="text-lg font-semibold text-raw-white">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-control border border-dashed border-border-gray px-4 py-3 text-sm text-muted">
      {children}
    </p>
  )
}

/** External links open in a new tab and say so with the arrow, not with copy. */
export function ExternalLinks({ links }: { links: { label: string; url: string }[] }) {
  return (
    <ul className="flex flex-wrap gap-2">
      {links.map((link) => (
        <li key={link.url} className="min-w-0 max-w-full">
          <a
            href={link.url}
            target="_blank"
            rel="noreferrer"
            className="group inline-flex min-h-10 max-w-full items-center gap-2 rounded-full border border-border-gray px-4 text-sm font-medium text-raw-white transition-colors hover:border-acid hover:text-acid"
          >
            <span className="truncate">{link.label}</span>
            <ArrowUpRight
              size={14}
              className="shrink-0 transition-transform duration-200 ease-out-expo group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              aria-hidden
            />
          </a>
        </li>
      ))}
    </ul>
  )
}
