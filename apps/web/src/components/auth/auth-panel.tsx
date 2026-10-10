import type { ReactNode } from "react"

import { cn } from "@/lib/cn"

export const authSurfaceClass =
  "rounded-surface border border-border-gray bg-graphite/90 shadow-[0_30px_80px_-40px_rgba(0,0,0,0.9)] backdrop-blur"

/** A single-column card for the short utility flows (reset, verify). */
export function AuthPanel({
  title,
  caption,
  children,
}: {
  title: string
  caption?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={cn("w-full max-w-md animate-rise p-6 sm:p-8", authSurfaceClass)}>
      <h1 className="font-display text-3xl leading-none tracking-[0.02em] sm:text-4xl">{title}</h1>
      {caption ? <p className="mt-3 text-[15px] leading-7 text-dim-white">{caption}</p> : null}
      {children}
    </section>
  )
}
