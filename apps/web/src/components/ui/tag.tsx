import Link from "next/link"

import { cn } from "@/lib/cn"

function Tag({
  label,
  href,
  className,
}: {
  label: string
  href?: string
  className?: string
}) {
  const classes = cn(
    "inline-block border border-border-gray bg-raised px-2 py-0.5 font-mono text-[11px] uppercase tracking-label text-dim-white",
    href && "hover:border-violet hover:text-violet",
    className,
  )

  const text = label.startsWith("#") ? label : `#${label}`

  if (href) {
    return (
      <Link className={classes} href={href}>
        {text}
      </Link>
    )
  }

  return <span className={classes}>{text}</span>
}

export function TagRow({
  tags,
  className,
}: {
  tags: string[]
  className?: string
}) {
  if (tags.length === 0) return null
  return (
    <div className={cn("flex flex-wrap gap-1.5", className)}>
      {tags.map((tag) => (
        <Tag
          key={tag}
          label={tag}
          href={`/app/search?q=${encodeURIComponent(`#${tag}`)}`}
        />
      ))}
    </div>
  )
}
