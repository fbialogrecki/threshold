import { CalendarBlank, MapPin, Question, UsersThree } from "@phosphor-icons/react/ssr"
import type { ReactNode } from "react"

import type { LocationMode } from "@/lib/types"

/*
  One value column for event facts.

  Two rules keep it aligned no matter what the content does. Every `dl` child is
  a `div` wrapper holding `dt` and `dd`, because mixing wrappers with bare `dd`
  is invalid HTML. And the icon sits in a box whose height equals the value's
  line-height, so it centres on the first line and a wrapped value never drags
  it out of the grid.

  Every value is plain sans at one size. Protection reads from the padlock and
  full-contrast text rather than uppercase mono, so the three rows share a
  single rhythm instead of one row being twice as tall as its neighbours.
*/

function Fact({
  icon,
  label,
  children,
}: {
  icon: ReactNode
  label: string
  children: ReactNode
}) {
  return (
    <div className="grid grid-cols-[1rem_minmax(0,1fr)] gap-x-2">
      <span className="flex h-6 items-center justify-center">{icon}</span>
      <dt className="sr-only">{label}</dt>
      <dd className="text-sm leading-6">{children}</dd>
    </div>
  )
}

export function EventFacts({
  date,
  locationMode,
  venue,
  lineup,
  labels,
  className,
}: {
  date: string
  locationMode: LocationMode
  /** venue line for public events; ignored for secret and TBA */
  venue: string
  lineup?: ReactNode
  labels: {
    date: string
    location: string
    lineup: string
    secretLocation: string
    locationTba: string
  }
  className?: string
}) {
  return (
    <dl className={className ? `grid gap-2 ${className}` : "grid gap-2"}>
      <Fact
        label={labels.date}
        icon={<CalendarBlank size={16} className="text-muted" aria-hidden />}
      >
        <span className="text-dim-white">{date}</span>
      </Fact>

      {locationMode === "secret_location" ? (
        <Fact
          label={labels.location}
          icon={<LockGlyph />}
        >
          <span className="text-raw-white">{labels.secretLocation}</span>
        </Fact>
      ) : locationMode === "tba" ? (
        <Fact
          label={labels.location}
          icon={<Question size={16} className="text-orange" aria-hidden />}
        >
          <span className="text-orange">{labels.locationTba}</span>
        </Fact>
      ) : (
        <Fact
          label={labels.location}
          icon={<MapPin size={16} className="text-muted" aria-hidden />}
        >
          <span className="text-dim-white">{venue || labels.locationTba}</span>
        </Fact>
      )}

      {lineup ? (
        <Fact
          label={labels.lineup}
          icon={<UsersThree size={16} className="text-muted" aria-hidden />}
        >
          <span className="text-dim-white">{lineup}</span>
        </Fact>
      ) : null}
    </dl>
  )
}

/** Protection marker: full contrast plus a padlock, never a hue. */
function LockGlyph() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden className="text-raw-white">
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
