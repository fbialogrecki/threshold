import type { ReactNode } from "react"

import { cn } from "@/lib/cn"

export function Card({
  children,
  className,
  as: Tag = "div",
}: {
  children: ReactNode
  className?: string
  as?: "div" | "article" | "section" | "aside"
}) {
  return (
    <Tag className={cn("border border-border-gray bg-graphite", className)}>
      {children}
    </Tag>
  )
}

export function CardHeader({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex items-center justify-between border-b border-border-gray px-4 py-3",
        className,
      )}
    >
      {children}
    </div>
  )
}

export function CardBody({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={cn("px-4 py-4", className)}>{children}</div>
}
