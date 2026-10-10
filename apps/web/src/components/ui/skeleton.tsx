import { cn } from "@/lib/cn"

/** Filled placeholder blocks; the pulse stops under reduced motion. */
function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-control bg-raised", className)} />
}

/** Card-shaped placeholder roughly matching feed card heights. */
function SkeletonCard() {
  return (
    <div className="rounded-surface border border-border-gray bg-graphite/60 p-4 sm:p-5">
      <div className="flex gap-3">
        <Skeleton className="size-10 shrink-0 rounded-full" />
        <div className="flex-1 space-y-2 pt-1">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-1/5" />
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
      </div>
      <div className="mt-5 flex justify-between">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-8 w-28" />
      </div>
    </div>
  )
}

export function SkeletonFeed({ label, ariaLabel }: { label: string; ariaLabel: string }) {
  return (
    <div className="flex flex-col gap-3" role="status" aria-label={ariaLabel}>
      <p className="text-sm text-muted">{label}</p>
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
    </div>
  )
}
