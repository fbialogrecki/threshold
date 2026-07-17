"use client"

import { cn } from "@/lib/cn"

/**
 * Shared presentational core for boost-style signal buttons: a bare up
 * arrow with a counter, no text label (screen readers get ariaLabel).
 * Behavior (endpoints, optimistic state, rollback) stays in the callers.
 */
export function SignalButtonView({
  active,
  count,
  flip,
  onClick,
  ariaLabel,
  ariaDescribedBy,
  disabled = false,
}: {
  active: boolean
  count: number
  flip: boolean
  onClick: () => void
  ariaLabel: string
  ariaDescribedBy?: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      aria-label={ariaLabel}
      aria-describedby={ariaDescribedBy}
      className={cn(
        "group inline-flex items-center gap-2 border bg-graphite px-3 py-1.5 font-mono text-xs uppercase tracking-label transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        active
          ? "border-acid bg-acid text-pitch"
          : "border-border-gray text-dim-white hover:border-acid",
      )}
    >
      <span
        className={cn(
          "transition-transform group-hover:-translate-y-0.5",
          active ? "text-pitch" : "text-acid",
        )}
        aria-hidden
      >
        ↑
      </span>
      <span className={cn("tabular-nums", flip && "threshold-flip inline-block")}>
        {count}
      </span>
    </button>
  )
}
