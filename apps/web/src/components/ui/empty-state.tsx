import type { ReactNode } from "react"

import { ButtonLink } from "@/components/ui/button"
import { cn } from "@/lib/cn"

/**
 * Honest empty and failure states. `error` marks a load failure in orange
 * (something is incomplete), never the destructive red.
 */
export function EmptyState({
  title,
  body,
  actionLabel,
  actionHref,
  eyebrow,
  tone = "empty",
  children,
}: {
  title: string
  body: string
  actionLabel?: string
  actionHref?: string
  eyebrow?: string
  tone?: "empty" | "error"
  children?: ReactNode
}) {
  return (
    <div
      role={tone === "error" ? "status" : undefined}
      className={cn(
        "flex animate-step flex-col items-start gap-3 rounded-surface border p-6 sm:p-8",
        tone === "error"
          ? "border-orange/40 bg-orange/5"
          : "border-border-gray bg-graphite/60",
      )}
    >
      {eyebrow ? (
        <p className="flex items-center gap-2 text-[13px] font-medium text-muted">
          <span
            aria-hidden
            className={cn(
              "size-1.5 rounded-full",
              tone === "error" ? "bg-orange" : "bg-status-neutral-border",
            )}
          />
          {eyebrow}
        </p>
      ) : null}
      <h2 className="text-xl font-semibold text-raw-white sm:text-2xl">{title}</h2>
      <p className="max-w-[52ch] text-[15px] leading-7 text-dim-white">{body}</p>
      {actionLabel && actionHref ? (
        <ButtonLink
          href={actionHref}
          size="lg"
          variant={tone === "error" ? "secondary" : "primary"}
          className="mt-2"
        >
          {actionLabel}
        </ButtonLink>
      ) : null}
      {children}
    </div>
  )
}
