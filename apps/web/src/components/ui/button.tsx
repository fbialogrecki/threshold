import Link from "next/link"
import type { ButtonHTMLAttributes, ReactNode } from "react"

import { cn } from "@/lib/cn"

type Variant = "primary" | "secondary" | "danger" | "ghost"

const VARIANT_CLASS: Record<Variant, string> = {
  primary:
    "border-acid bg-acid text-pitch hover:bg-[#d4ff3a] focus-visible:bg-[#d4ff3a]",
  secondary:
    "border-border-gray bg-transparent text-raw-white hover:border-acid hover:text-acid",
  danger:
    "border-error bg-transparent text-error hover:bg-error hover:text-pitch",
  ghost:
    "border-transparent bg-transparent text-dim-white hover:text-raw-white",
}

const baseClass =
  "inline-flex items-center justify-center gap-2 border px-4 py-2 font-mono text-xs uppercase tracking-cta transition-colors disabled:cursor-not-allowed disabled:opacity-50"

export function Button({
  children,
  variant = "secondary",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode
  variant?: Variant
}) {
  return (
    <button className={cn(baseClass, VARIANT_CLASS[variant], className)} {...props}>
      {children}
    </button>
  )
}

export function ButtonLink({
  children,
  href,
  variant = "secondary",
  className,
}: {
  children: ReactNode
  href: string
  variant?: Variant
  className?: string
}) {
  return (
    <Link
      className={cn(baseClass, VARIANT_CLASS[variant], className)}
      href={href}
    >
      {children}
    </Link>
  )
}
