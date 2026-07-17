import type { ReactNode } from "react"

import { cn } from "@/lib/cn"

/**
 * The single source of truth for mono metadata labels.
 * Sizes: xs (10px, least important only), sm (11px, default), md (12px).
 * Tracking comes from the global scale (--tracking-label).
 */
export function MonoLabel({
  children,
  className,
  tone = "muted",
  size = "sm",
}: {
  children: ReactNode
  className?: string
  tone?: "muted" | "dim" | "acid" | "violet" | "orange" | "cyan" | "error"
  size?: "xs" | "sm" | "md"
}) {
  const toneClass = {
    muted: "text-muted",
    dim: "text-dim-white",
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
