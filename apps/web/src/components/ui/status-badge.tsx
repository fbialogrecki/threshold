import { cn } from "@/lib/cn"

type Tone = "acid" | "violet" | "orange" | "cyan" | "error" | "muted"

const STATUS_TONE: Record<string, Tone> = {
  approved: "acid",
  confirmed: "acid",
  granted: "acid",
  online: "acid",
  verified: "acid",
  public: "cyan",
  system: "cyan",
  secret: "violet",
  pending: "orange",
  tba: "muted",
  rejected: "error",
  revoked: "error",
  error: "error",
  locked: "muted",
  ended: "muted",
}

const TONE_CLASS: Record<Tone, string> = {
  acid: "border-acid text-acid",
  violet: "border-violet text-violet",
  orange: "border-orange text-orange",
  cyan: "border-cyan text-cyan",
  error: "border-error text-error",
  muted: "border-status-neutral-border text-status-neutral",
}

export function StatusBadge({
  status,
  label,
  className,
  pulse,
}: {
  status: string
  label?: string
  className?: string
  /** show a pulsing dot — defaults on for "pending" to signal awaiting review */
  pulse?: boolean
}) {
  const key = status.toLowerCase()
  const tone = STATUS_TONE[key] ?? "muted"
  const showPulse = pulse ?? key === "pending"

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border bg-graphite px-2 py-0.5 font-mono text-[11px] uppercase tracking-label",
        TONE_CLASS[tone],
        className,
      )}
    >
      {showPulse ? (
        <span aria-hidden className="threshold-pulse text-current">
          ●
        </span>
      ) : null}
      {label ?? status}
    </span>
  )
}
