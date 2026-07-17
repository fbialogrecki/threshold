import { cn } from "@/lib/cn"

/** Brutalist skeleton: flat pulsing blocks, no rounded corners. */
function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("animate-pulse border border-border-gray bg-raised", className)}
    />
  )
}

/** Card-shaped placeholder roughly matching feed card heights. */
function SkeletonCard() {
  return (
    <div className="border border-border-gray bg-graphite p-4">
      <div className="flex gap-3">
        <Skeleton className="h-10 w-10 shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-1/5" />
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
      </div>
      <div className="mt-4 flex justify-between">
        <Skeleton className="h-7 w-24" />
        <Skeleton className="h-7 w-28" />
      </div>
    </div>
  )
}

/** Full feed-page placeholder with the signature mono loading line. */
export function SkeletonFeed({ label, ariaLabel }: { label: string; ariaLabel: string }) {
  return (
    <div className="flex flex-col gap-6" role="status" aria-label={ariaLabel}>
      <Skeleton className="h-10 w-full" />
      <div>
        <Skeleton className="h-9 w-56" />
        <p className="mt-2 font-mono text-[10px] uppercase tracking-label text-muted">
          {label}
          <span className="landing-cursor text-acid">▮</span>
        </p>
      </div>
      <div className="flex flex-col gap-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    </div>
  )
}
