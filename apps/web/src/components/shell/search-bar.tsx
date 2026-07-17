"use client"

import { MagnifyingGlass } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useEffect, useRef, useState } from "react"

import {
  activeMentionTrigger,
  mentionSearchQuery,
  type MentionSuggestion,
} from "@/lib/mentions/autocomplete"
import { cn } from "@/lib/cn"

export function SearchBar({
  initialQuery = "",
  compact = false,
}: {
  initialQuery?: string
  /** Slim sidebar variant: tighter paddings, short placeholder, no kbd hint. */
  compact?: boolean
}) {
  const router = useRouter()
  const t = useTranslations("shell.search")
  const typeT = useTranslations("searchPage.filters")
  const inputRef = useRef<HTMLInputElement>(null)
  const [value, setValue] = useState(initialQuery)
  const [caret, setCaret] = useState(initialQuery.length)
  const [suggestions, setSuggestions] = useState<MentionSuggestion[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [open, setOpen] = useState(false)
  const trigger = activeMentionTrigger(value, caret)
  const queryKey = trigger ? mentionSearchQuery(trigger) : null

  // "/" focuses search, command-line style. Guards: never steal focus while
  // the user is typing elsewhere, never hijack shortcuts or IME composition.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "/") return
      if (event.ctrlKey || event.metaKey || event.altKey) return
      if (event.isComposing) return
      const target = event.target as HTMLElement | null
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return
      }
      event.preventDefault()
      inputRef.current?.focus()
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  useEffect(() => {
    if (!queryKey) return

    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/search/mentions?q=${encodeURIComponent(queryKey)}`,
          { signal: controller.signal },
        )
        if (!response.ok) throw new Error("mention search failed")
        const body: unknown = await response.json()
        setSuggestions(Array.isArray(body) ? (body as MentionSuggestion[]) : [])
        setActiveIndex(0)
        setOpen(Array.isArray(body) && body.length > 0)
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setSuggestions([])
          setOpen(false)
        }
      }
    }, 120)

    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [queryKey])

  function goToSuggestion(suggestion: MentionSuggestion) {
    setOpen(false)
    setValue(suggestion.type === "event" ? `#${suggestion.handle}` : `@${suggestion.handle}`)
    router.push(suggestion.href)
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    const q = value.trim()
    router.push(q ? `/app/search?q=${encodeURIComponent(q)}` : "/app/search")
  }

  return (
    <form onSubmit={onSubmit} className="relative w-full" role="search">
      <label className="sr-only" htmlFor="threshold-search">
        {t("label")}
      </label>
      <div
        className={
          compact
            ? "flex items-center gap-1.5 border border-border-gray bg-raised px-2 py-1.5 focus-within:border-acid"
            : "flex items-center gap-2 border border-border-gray bg-raised px-3 py-2 focus-within:border-acid"
        }
      >
        <MagnifyingGlass size={16} weight="bold" className="shrink-0 text-muted" aria-hidden />
        <input
          ref={inputRef}
          id="threshold-search"
          value={value}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls="threshold-search-suggestions"
          aria-activedescendant={open ? `threshold-search-option-${activeIndex}` : undefined}
          onChange={(event) => {
            setValue(event.target.value)
            setCaret(event.target.selectionStart ?? event.target.value.length)
          }}
          onClick={(event) => setCaret(event.currentTarget.selectionStart ?? event.currentTarget.value.length)}
          onKeyUp={(event) => setCaret(event.currentTarget.selectionStart ?? event.currentTarget.value.length)}
          onKeyDown={(event) => {
            if (open && suggestions.length > 0) {
              if (event.key === "ArrowDown") {
                event.preventDefault()
                setActiveIndex((index) => (index + 1) % suggestions.length)
                return
              }
              if (event.key === "ArrowUp") {
                event.preventDefault()
                setActiveIndex((index) => (index - 1 + suggestions.length) % suggestions.length)
                return
              }
              if (event.key === "Enter" || event.key === "Tab") {
                event.preventDefault()
                goToSuggestion(suggestions[activeIndex] ?? suggestions[0])
                return
              }
              if (event.key === "Escape") {
                event.preventDefault()
                setOpen(false)
              }
            }
          }}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          placeholder={t(compact ? "compactPlaceholder" : "placeholder")}
          className={
            compact
              ? "w-full bg-transparent font-mono text-xs text-raw-white placeholder:text-muted focus:outline-none"
              : "w-full bg-transparent font-mono text-sm text-raw-white placeholder:text-muted focus:outline-none"
          }
        />
        {compact ? null : (
          <kbd
            aria-hidden
            className="hidden border border-border-gray px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-label text-muted sm:block"
          >
            /
          </kbd>
        )}
      </div>
      {open && trigger ? (
        <div
          id="threshold-search-suggestions"
          role="listbox"
          className="absolute left-0 right-0 top-full z-30 mt-1 border border-border-gray bg-raised shadow-xl"
        >
          {suggestions.map((suggestion, index) => (
            <button
              key={`${suggestion.type}:${suggestion.handle}`}
              id={`threshold-search-option-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => goToSuggestion(suggestion)}
              className={cn(
                "flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm",
                index === activeIndex ? "bg-acid text-pitch" : "text-raw-white hover:bg-graphite",
              )}
            >
              <span>
                <span className="font-medium">{suggestion.title}</span>
                {suggestion.subtitle ? (
                  <span className={index === activeIndex ? "ml-2 text-pitch/70" : "ml-2 text-muted"}>
                    {suggestion.subtitle}
                  </span>
                ) : null}
              </span>
              <span className="font-mono text-[11px] uppercase tracking-label">
                {typeT(suggestion.type)}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </form>
  )
}
