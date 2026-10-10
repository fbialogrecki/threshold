import type { ReactNode } from "react"

import { cn } from "@/lib/cn"

/**
 * Text inputs are 16px so mobile browsers do not zoom on focus. Focus and
 * invalid states live on the border because the global focus ring is off for
 * fields (see globals.css).
 */
export const inputClass =
  "w-full rounded-control border border-border-gray bg-pitch px-3.5 py-3 text-base text-raw-white placeholder:text-muted transition-[border-color,box-shadow] duration-150 hover:border-status-neutral-border focus:border-acid focus:shadow-[0_0_0_3px_rgba(198,255,0,0.18)] focus:outline-none aria-[invalid=true]:border-orange"

export function Field({
  htmlFor,
  label,
  hint,
  help,
  helpId,
  children,
  className,
}: {
  htmlFor: string
  label: ReactNode
  hint?: ReactNode
  help?: ReactNode
  helpId?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <label
        htmlFor={htmlFor}
        className="flex items-baseline justify-between gap-3 text-sm font-medium text-raw-white"
      >
        {label}
        {hint ? <span className="text-xs font-normal text-muted">{hint}</span> : null}
      </label>
      {children}
      {help ? (
        <p id={helpId} className="text-[13px] leading-5 text-muted">
          {help}
        </p>
      ) : null}
    </div>
  )
}

export function FormAlert({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <p
      id={id}
      role="alert"
      className="flex animate-step gap-3 rounded-control border border-orange/50 bg-orange/10 px-3.5 py-3 text-sm leading-6 text-raw-white"
    >
      <span
        aria-hidden
        className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-orange text-xs font-bold text-pitch"
      >
        !
      </span>
      {children}
    </p>
  )
}

export function Spinner() {
  return (
    <span
      aria-hidden
      className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent"
    />
  )
}
