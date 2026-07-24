import type { ReactNode } from "react"

import { cn } from "@/lib/cn"

/**
 * The single source of truth for mono metadata labels.
 * Sizes: xs (10px, least important only), sm (11px, default), md (12px).
 * Tracking comes from the global scale (--tracking-label).
 *
 * `protected` is the marker for withheld or gated things: full contrast rather
 * than a hue, so violet stays with the vote axis and cyan stays out of statuses.
 */
export function MonoLabel({
  children,
  className,
  tone = "muted",
  size = "sm",
}: {
  children: ReactNode
  className?: string
  tone?: "muted" | "dim" | "protected" | "acid" | "violet" | "orange" | "cyan" | "error"
  size?: "xs" | "sm" | "md"
}) {
  const toneClass = {
    muted: "text-muted",
    dim: "text-dim-white",
    protected: "text-raw-white",
    acid: "text-acid",
    violet: "text-violet",
    orange: "text-orange",
    cyan: "text-cyan",
    error: "text-error",
  }[tone]

  const sizeClass = {
    xs: "text-[10px]",
    sm: "text-[11px]",
    md: "text-xs",
  }[size]

  return (
    <span
      className={cn(
        "font-mono uppercase tracking-label",
        sizeClass,
        toneClass,
        className,
      )}
    >
      {children}
    </span>
  )
}
