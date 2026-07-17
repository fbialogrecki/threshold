import type { ReactNode } from "react"

import { ButtonLink } from "@/components/ui/button"

export function EmptyState({
  title,
  body,
  actionLabel,
  actionHref,
  eyebrow = "[ empty ]",
  children,
}: {
  title: string
  body: string
  actionLabel?: string
  actionHref?: string
  eyebrow?: string
  children?: ReactNode
}) {
  return (
    <div className="flex flex-col items-start gap-4 border border-dashed border-border-gray bg-graphite p-8">
      <p className="font-mono text-[10px] uppercase tracking-cta text-muted">
        {eyebrow}
      </p>
      <h2 className="font-display text-3xl uppercase tracking-wide text-dim-white">
        {title}
      </h2>
      <p className="max-w-md text-sm leading-7 text-muted">{body}</p>
      {actionLabel && actionHref ? (
        <ButtonLink href={actionHref} variant="secondary">
          {actionLabel}
        </ButtonLink>
      ) : null}
      {children}
    </div>
  )
}
