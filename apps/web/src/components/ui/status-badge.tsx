import { cn } from "@/lib/cn"

/*
  Colour doctrine: acid affirms, violet dissents (votes only), orange flags
  something incomplete, and protection is signalled by maximum contrast plus a
  padlock rather than a hue. That frees violet for the vote axis and stops the
  same colour from meaning access in one place and a downvote in another.
*/
type Tone = "affirm" | "protected" | "attention" | "neutral" | "error"

const STATUS_TONE: Record<string, Tone> = {
  approved: "protected",
  granted: "protected",
  secret: "protected",
  confirmed: "affirm",
  online: "affirm",
  verified: "affirm",
  unread: "affirm",
  read: "neutral",
  public: "neutral",
  system: "neutral",
  pending: "neutral",
  locked: "neutral",
  ended: "neutral",
  tba: "attention",
  rejected: "error",
  revoked: "error",
  error: "error",
}

const TONE_CLASS: Record<Tone, string> = {
  affirm: "border-acid text-acid",
  protected: "border-raw-white text-raw-white",
  attention: "border-orange text-orange",
  neutral: "border-status-neutral-border text-status-neutral",
  error: "border-error text-error",
}

/** Inline so the badge works in both Server and Client Components. */
function PadlockGlyph() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" aria-hidden className="shrink-0">
      <path
        d="M6 11h12v10H6zM9 11V7.5a3 3 0 0 1 6 0V11"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
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
  const tone = STATUS_TONE[key] ?? "neutral"
  const showPulse = pulse ?? key === "pending"

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border px-2 py-0.5 font-mono text-[11px] uppercase tracking-label",
        TONE_CLASS[tone],
        className,
      )}
    >
      {tone === "protected" ? <PadlockGlyph /> : null}
      {showPulse ? (
        <span aria-hidden className="threshold-pulse text-current">
          ●
        </span>
      ) : null}
      {label ?? status}
    </span>
  )
}
