import type { ReactNode } from "react"

/** Route title for the app shell: display type for the place, sans for the explanation. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="font-display text-3xl leading-none tracking-[0.01em] text-raw-white sm:text-4xl">
          {title}
        </h1>
        {subtitle ? <p className="mt-2 text-[15px] text-dim-white">{subtitle}</p> : null}
      </div>
      {actions}
    </header>
  )
}
