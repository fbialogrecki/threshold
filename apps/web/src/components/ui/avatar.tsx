import { cn } from "@/lib/cn"

function initials(name: string): string {
  const parts = name.replace(/[@#]/g, "").trim().split(/\s+/)
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/**
 * Initials-based avatar. No media service yet, so we never render remote
 * images here; this keeps the build independent of `media`/`sharp`.
 */
export function Avatar({
  name,
  imageUrl,
  size = "md",
  className,
}: {
  name: string
  imageUrl?: string | null
  size?: "sm" | "md" | "lg"
  className?: string
}) {
  const sizeClass = {
    sm: "h-8 w-8 text-[11px]",
    md: "h-10 w-10 text-xs",
    lg: "h-20 w-20 text-2xl",
  }[size]

  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden border border-border-gray bg-raised font-mono uppercase tracking-[0.1em] text-dim-white",
        sizeClass,
        className,
      )}
    >
      {imageUrl ? (
        <img src={imageUrl} alt="" className="h-full w-full object-cover" />
      ) : (
        initials(name)
      )}
    </span>
  )
}
