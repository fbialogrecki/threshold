import Link from "next/link"
import type { ButtonHTMLAttributes, ReactNode } from "react"

import { cn } from "@/lib/cn"

type Variant = "primary" | "secondary" | "danger" | "ghost"
type Size = "md" | "lg"

const VARIANT_CLASS: Record<Variant, string> = {
  primary:
    "border-acid bg-acid text-pitch hover:bg-acid-bright focus-visible:bg-acid-bright",
  secondary:
    "border-border-gray bg-transparent text-raw-white hover:border-acid hover:text-acid",
  danger:
    "border-error bg-transparent text-error hover:bg-error hover:text-pitch",
  ghost:
    "border-transparent bg-transparent text-dim-white hover:text-raw-white",
}

// `md` is the original square mono control. `lg` is the modern shape: a
// readable sans label, rounded corners and a short press response.
const SIZE_CLASS: Record<Size, string> = {
  md: "px-4 py-2 font-mono text-xs uppercase tracking-cta transition-colors",
  lg: "min-h-12 rounded-control px-6 py-3 text-[15px] font-semibold transition-[color,background-color,border-color,scale] duration-150 ease-press active:scale-[0.97]",
}

const baseClass =
  "inline-flex items-center justify-center gap-2 border disabled:cursor-not-allowed disabled:opacity-50"

export function Button({
  children,
  variant = "secondary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode
  variant?: Variant
  size?: Size
}) {
  return (
    <button
      className={cn(baseClass, SIZE_CLASS[size], VARIANT_CLASS[variant], className)}
      {...props}
    >
      {children}
    </button>
  )
}

export function ButtonLink({
  children,
  href,
  variant = "secondary",
  size = "md",
  className,
}: {
  children: ReactNode
  href: string
  variant?: Variant
  size?: Size
  className?: string
}) {
  return (
    <Link
      className={cn(baseClass, SIZE_CLASS[size], VARIANT_CLASS[variant], className)}
      href={href}
    >
      {children}
    </Link>
  )
}
