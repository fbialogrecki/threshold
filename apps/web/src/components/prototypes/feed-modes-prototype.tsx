"use client"

import type { ReactNode, TouchEvent, WheelEvent } from "react"
import { useEffect, useRef, useState } from "react"

import { cn } from "@/lib/cn"

type Mode = "classic" | "focus" | "compact"

type PrototypeItem = {
  id: string
  kind: "post" | "event" | "update"
  source: string
  handle: string
  city: string
  age: string
  title: string
  body: string
  tags: string[]
  event?: string
  stats: {
    comments: number
    reactions: number
    boosts?: number
  }
  imageTone?: "cyan" | "violet" | "acid" | "orange"
  comments: Array<{ author: string; body: string }>
}

const ITEMS: PrototypeItem[] = [
  {
    id: "p1",
    kind: "post",
    source: "Kolektyw Szum",
    handle: "@szum_waw",
    city: "Warszawa",
    age: "12 min",
    title: "Basement set notes after last night",
    body: "Krótki zapis po secie: mniej dropów, więcej napięcia. Kto był do końca, ten wie. Pytanie do ludzi z parkietu: drugi live-act siadł czy był za gęsty?",
    tags: ["discussion", "techno", "post-show"],
    stats: { comments: 18, reactions: 42 },
    imageTone: "cyan",
    comments: [
      { author: "@ola", body: "Drugi live był najlepszy, tylko potrzebował 10 minut rozbiegu." },
      { author: "@marcin", body: "Za gęsty początek. Końcówka super." },
      { author: "@szum_waw", body: "Właśnie o taki feedback chodzi. Dzięki." },
    ],
  },
  {
    id: "e1",
    kind: "event",
    source: "Hydrozagadka",
    handle: "@hydro_club",
    city: "Warszawa",
    age: "38 min",
    title: "Friday: LOW CEILING / high pressure",
    body: "Nowy event od obserwowanego klubu. Public location, limitowana pojemność, line-up bez headlinera na plakacie. Pełny opis i boost dostępne na stronie wydarzenia.",
    tags: ["event", "club", "friday"],
    event: "LOW CEILING / high pressure",
    stats: { comments: 7, reactions: 31, boosts: 14 },
    imageTone: "violet",
    comments: [
      { author: "@kuba", body: "Czy drugi room też działa?" },
      { author: "@hydro_club", body: "Tak, ale bez osobnego wejścia." },
      { author: "@nina", body: "Line-up reveal kiedy?" },
    ],
  },
  {
    id: "p2",
    kind: "post",
    source: "Maja R",
    handle: "@maja_r",
    city: "Kraków",
    age: "1 h",
    title: "Track ID thread: closing tool",
    body: "Szukam ID ostatniego numeru z setu @noce. Wokal wchodził po długim breaku, tempo około 138, brzmiało jak stary dubplate po remasterze.",
    tags: ["track-id", "community", "krakow"],
    stats: { comments: 26, reactions: 19 },
    imageTone: "acid",
    comments: [
      { author: "@tomek", body: "To mogło być Rhyw - Engine Track, ale pitch mocno w górę." },
      { author: "@noce", body: "Blisko. Wyślę ID po weekendzie." },
      { author: "@maja_r", body: "Zapisuję, dzięki." },
    ],
  },
  {
    id: "u1",
    kind: "update",
    source: "Jasna 1",
    handle: "@jasna1",
    city: "Warszawa",
    age: "2 h",
    title: "Organizer update: door flow",
    body: "Wejście dziś od bocznej bramy. Guestlist i QR check-in osobną kolejką. Nie budujemy publicznej listy zapisów — dostęp dodaje organizator lub DJ z własnej puli.",
    tags: ["organizer", "access", "qr"],
    event: "Room 02",
    stats: { comments: 9, reactions: 27 },
    imageTone: "orange",
    comments: [
      { author: "@ania", body: "Czy plus-one wchodzi na ten sam QR?" },
      { author: "@jasna1", body: "Nie, każdy user ma osobny token." },
      { author: "@door", body: "Minimalne dane na bramce, bez eksportu listy." },
    ],
  },
]

const MODES: Array<{ id: Mode; label: string; note: string }> = [
  { id: "classic", label: "Classic", note: "standard chronological scan" },
  { id: "focus", label: "Focus", note: "one card, one decision" },
  { id: "compact", label: "Compact", note: "dense fast scan" },
]

export function FeedModesPrototype() {
  const [mode, setMode] = useState<Mode>("focus")
  const [activeIndex, setActiveIndex] = useState(0)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const touchStart = useRef<number | null>(null)
  const wheelLock = useRef(false)

  const activeItem = ITEMS[activeIndex]
  const expanded = expandedId === activeItem.id

  function move(delta: number) {
    setExpandedId(null)
    setActiveIndex((current) => Math.min(ITEMS.length - 1, Math.max(0, current + delta)))
  }

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setExpandedId(null)
        return
      }
      if (mode !== "focus" || expandedId) return
      if (["ArrowDown", "PageDown", "j", "J"].includes(event.key)) {
        event.preventDefault()
        move(1)
      }
      if (["ArrowUp", "PageUp", "k", "K"].includes(event.key)) {
        event.preventDefault()
        move(-1)
      }
    }

    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [mode, expandedId])

  function handleWheel(event: WheelEvent) {
    if (mode !== "focus" || expandedId || Math.abs(event.deltaY) < 24 || wheelLock.current) return
    event.preventDefault()
    wheelLock.current = true
    move(event.deltaY > 0 ? 1 : -1)
    window.setTimeout(() => {
      wheelLock.current = false
    }, 420)
  }

  function handleTouchEnd(event: TouchEvent) {
    if (mode !== "focus" || expandedId || touchStart.current === null) return
    const delta = touchStart.current - event.changedTouches[0].clientY
    touchStart.current = null
    if (Math.abs(delta) < 48) return
    move(delta > 0 ? 1 : -1)
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="border-b border-border-gray pb-4">
        <p className="font-mono text-[11px] uppercase tracking-label text-acid">Prototype / not live feed</p>
        <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="font-display text-4xl tracking-wide text-raw-white">Feed Mode Lab</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-dim-white">
              Same fixture items, three presentation modes. Compare speed of scanning vs focus and discussion depth.
              Chronological order only. No autoplay, no ranking, no For You logic.
            </p>
          </div>
          <div className="grid grid-cols-3 border border-border-gray bg-graphite p-1">
            {MODES.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setMode(item.id)
                  setExpandedId(null)
                }}
                className={cn(
                  "px-3 py-2 text-left font-mono text-[11px] uppercase tracking-label transition-colors",
                  mode === item.id ? "bg-acid text-pitch" : "text-dim-white hover:bg-raised hover:text-raw-white",
                )}
              >
                <span className="block">{item.label}</span>
                <span className="hidden text-[9px] normal-case tracking-normal sm:block">{item.note}</span>
              </button>
            ))}
          </div>
        </div>
      </header>

      <section className="grid gap-3 border border-border-gray bg-graphite p-4 sm:grid-cols-3">
        <Question title="Classic">
          Czy szybciej łapiesz, co nowego, czy tylko skanujesz bez wejścia w rozmowę?
        </Question>
        <Question title="Focus">
          Czy jeden materiał na ekran daje więcej uwagi, czy pachnie zbyt mocno TikTokiem?
        </Question>
        <Question title="Compact">
          Czy power-user potrzebuje gęstej listy jako fallback do szybkiego przeglądu?
        </Question>
      </section>

      {mode === "classic" ? <ClassicMode /> : null}
      {mode === "focus" ? (
        <FocusMode
          item={activeItem}
          index={activeIndex}
          expanded={expanded}
          onPrevious={() => move(-1)}
          onNext={() => move(1)}
          onToggleExpand={() => setExpandedId(expanded ? null : activeItem.id)}
          onWheel={handleWheel}
          onTouchStart={(event) => {
            touchStart.current = event.touches[0].clientY
          }}
          onTouchEnd={handleTouchEnd}
        />
      ) : null}
      {mode === "compact" ? <CompactMode onPick={(index) => { setActiveIndex(index); setMode("focus") }} /> : null}
    </div>
  )
}

function Question({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-label text-muted">Judge / {title}</p>
      <p className="mt-1 text-sm leading-5 text-dim-white">{children}</p>
    </div>
  )
}

function ClassicMode() {
  return (
    <div className="flex flex-col gap-4" aria-label="Classic chronological feed prototype">
      {ITEMS.map((item) => <PrototypeCard key={item.id} item={item} layout="classic" />)}
    </div>
  )
}

function FocusMode({
  item,
  index,
  expanded,
  onPrevious,
  onNext,
  onToggleExpand,
  onWheel,
  onTouchStart,
  onTouchEnd,
}: {
  item: PrototypeItem
  index: number
  expanded: boolean
  onPrevious: () => void
  onNext: () => void
  onToggleExpand: () => void
  onWheel: (event: WheelEvent) => void
  onTouchStart: (event: TouchEvent) => void
  onTouchEnd: (event: TouchEvent) => void
}) {
  return (
    <section
      aria-label="Focus feed prototype"
      onWheel={onWheel}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
      className="min-h-[72vh] border border-border-gray bg-pitch p-2 outline-none"
      tabIndex={0}
    >
      <div className="mb-2 flex items-center justify-between gap-2 font-mono text-[10px] uppercase tracking-label text-muted">
        <span>Item {index + 1}/{ITEMS.length} / chronological deck</span>
        <span>Wheel · swipe · J/K · arrows</span>
      </div>

      <div className="grid min-h-[64vh] gap-3 lg:grid-cols-[1fr_190px]">
        <PrototypeCard item={item} layout="focus" expanded={expanded} onToggleExpand={onToggleExpand} />
        <aside className="flex flex-row gap-2 lg:flex-col">
          <button
            type="button"
            onClick={onPrevious}
            disabled={index === 0}
            className="flex-1 border border-border-gray px-3 py-3 font-mono text-[11px] uppercase tracking-label text-dim-white disabled:opacity-30 enabled:hover:border-acid enabled:hover:text-acid"
          >
            ↑ Previous
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={index === ITEMS.length - 1}
            className="flex-1 border border-border-gray px-3 py-3 font-mono text-[11px] uppercase tracking-label text-dim-white disabled:opacity-30 enabled:hover:border-acid enabled:hover:text-acid"
          >
            ↓ Next
          </button>
          <div className="hidden border border-border-gray p-3 lg:block">
            <p className="font-mono text-[10px] uppercase tracking-label text-muted">State rule</p>
            <p className="mt-2 text-xs leading-5 text-dim-white">
              Expanded discussion owns scroll. Collapse before deck navigation resumes.
            </p>
          </div>
        </aside>
      </div>
    </section>
  )
}

function CompactMode({ onPick }: { onPick: (index: number) => void }) {
  return (
    <div className="border border-border-gray bg-graphite" aria-label="Compact scan feed prototype">
      {ITEMS.map((item, index) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onPick(index)}
          className="grid w-full gap-2 border-b border-border-gray px-3 py-3 text-left last:border-b-0 hover:bg-raised sm:grid-cols-[90px_1fr_auto] sm:items-center"
        >
          <span className="font-mono text-[10px] uppercase tracking-label text-muted">{item.age} / {item.city}</span>
          <span>
            <span className="block font-display text-xl leading-none tracking-wide text-raw-white">{item.title}</span>
            <span className="mt-1 line-clamp-1 block text-xs text-dim-white">{item.source}: {item.body}</span>
          </span>
          <span className="font-mono text-[10px] uppercase tracking-label text-muted">
            {item.stats.comments} comments · {item.stats.reactions} reacts
          </span>
        </button>
      ))}
    </div>
  )
}

function PrototypeCard({
  item,
  layout,
  expanded = false,
  onToggleExpand,
}: {
  item: PrototypeItem
  layout: "classic" | "focus"
  expanded?: boolean
  onToggleExpand?: () => void
}) {
  const focus = layout === "focus"
  return (
    <article className={cn(
      "flex flex-col border border-border-gray bg-graphite",
      item.kind === "event" && "border-l-2 border-l-violet",
      item.kind === "update" && "border-l-2 border-l-orange",
      focus && "min-h-full",
    )}>
      <div className="flex items-start justify-between gap-3 border-b border-border-gray px-4 py-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-label text-acid">{item.kind} / {item.city}</p>
          <h2 className={cn("mt-1 font-display tracking-wide text-raw-white", focus ? "text-4xl leading-[0.95]" : "text-3xl leading-none")}>{item.title}</h2>
          <p className="mt-1 font-mono text-[11px] text-muted">{item.source} · {item.handle} · {item.age}</p>
        </div>
        <span className="border border-border-gray px-2 py-1 font-mono text-[10px] uppercase tracking-label text-muted">
          proto
        </span>
      </div>

      <div className={cn("grid gap-4 p-4", focus && "flex-1 content-start")}>
        <div className={cn(
          "flex min-h-32 items-center justify-center border border-border-gray bg-raised",
          item.imageTone === "cyan" && "shadow-[inset_0_0_0_1px_rgba(34,211,238,0.18)]",
          item.imageTone === "violet" && "shadow-[inset_0_0_0_1px_rgba(167,139,250,0.2)]",
          item.imageTone === "acid" && "shadow-[inset_0_0_0_1px_rgba(204,255,0,0.18)]",
          item.imageTone === "orange" && "shadow-[inset_0_0_0_1px_rgba(251,146,60,0.18)]",
          focus ? "min-h-[220px]" : "min-h-[140px]",
        )}>
          <span className="font-mono text-[10px] uppercase tracking-[0.35em] text-muted">media / poster placeholder</span>
        </div>

        <p className={cn("leading-7 text-dim-white", focus ? "text-lg" : "text-sm")}>{item.body}</p>

        {item.event ? (
          <div className="w-fit border border-border-gray px-2 py-1 font-mono text-[11px] uppercase tracking-label text-cyan">
            re: {item.event}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {item.tags.map((tag) => (
            <span key={tag} className="border border-border-gray px-2 py-1 font-mono text-[10px] uppercase tracking-label text-muted">#{tag}</span>
          ))}
        </div>
      </div>

      <footer className="mt-auto border-t border-border-gray px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex gap-2 font-mono text-[11px] uppercase tracking-label text-muted">
            <span>{item.stats.comments} comments</span>
            <span>{item.stats.reactions} reactions</span>
            {item.stats.boosts ? <span>{item.stats.boosts} boosts</span> : null}
          </div>
          <button
            type="button"
            onClick={onToggleExpand}
            className="border border-border-gray px-3 py-2 font-mono text-[11px] uppercase tracking-label text-dim-white hover:border-acid hover:text-acid"
          >
            {expanded ? "Collapse discussion" : "Expand discussion"}
          </button>
        </div>

        {expanded ? <Discussion item={item} /> : null}
      </footer>
    </article>
  )
}

function Discussion({ item }: { item: PrototypeItem }) {
  return (
    <div className="mt-3 max-h-[280px] overflow-y-auto border border-border-gray bg-pitch p-3" tabIndex={0}>
      <p className="font-mono text-[10px] uppercase tracking-label text-muted">
        Discussion scroll area / does not advance Focus Feed
      </p>
      <div className="mt-3 flex flex-col gap-3">
        {item.comments.concat(item.comments).map((comment, index) => (
          <div key={`${comment.author}-${index}`} className="border-l-2 border-border-gray pl-3">
            <p className="font-mono text-[10px] uppercase tracking-label text-acid">{comment.author}</p>
            <p className="mt-1 text-sm leading-6 text-dim-white">{comment.body}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
