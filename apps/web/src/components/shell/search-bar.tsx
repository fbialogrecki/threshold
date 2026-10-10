"use client"

import { MagnifyingGlass } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useEffect, useId, useRef, useState } from "react"

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
  // The sidebar and the search page can both render a bar; ids must differ.
  const id = useId()
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
      <label className="sr-only" htmlFor={id}>
        {t("label")}
      </label>
      <div
        className={cn(
          "flex items-center rounded-control border border-border-gray bg-pitch/70 transition-[border-color,box-shadow] focus-within:border-acid focus-within:shadow-[0_0_0_3px_rgba(198,255,0,0.15)]",
          compact ? "gap-2 px-3 py-2" : "gap-2.5 px-3.5 py-3",
        )}
      >
        <MagnifyingGlass size={compact ? 16 : 18} weight="bold" className="shrink-0 text-muted" aria-hidden />
        <input
          ref={inputRef}
          id={id}
          value={value}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-suggestions`}
          aria-activedescendant={open ? `${id}-option-${activeIndex}` : undefined}
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
          className={cn(
            "w-full min-w-0 bg-transparent text-raw-white placeholder:text-muted focus:outline-none",
            compact ? "text-sm" : "text-base",
          )}
        />
        <kbd
          aria-hidden
          className="hidden rounded-md border border-border-gray px-1.5 py-0.5 font-mono text-[11px] text-muted sm:block"
        >
          /
        </kbd>
      </div>
      {open && trigger ? (
        <div
          id={`${id}-suggestions`}
          role="listbox"
          className="absolute left-0 right-0 top-full z-30 mt-2 animate-step overflow-hidden rounded-control border border-border-gray bg-graphite p-1 shadow-[0_20px_50px_-20px_rgba(0,0,0,0.9)]"
        >
          {suggestions.map((suggestion, index) => (
            <button
              key={`${suggestion.type}:${suggestion.handle}`}
              id={`${id}-option-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => goToSuggestion(suggestion)}
              className={cn(
                "flex w-full items-center justify-between gap-3 rounded-md px-3 py-2.5 text-left text-sm",
                index === activeIndex ? "bg-acid/15 text-raw-white" : "text-raw-white hover:bg-raised",
              )}
            >
              <span className="min-w-0 truncate">
                <span className="font-medium">{suggestion.title}</span>
                {suggestion.subtitle ? (
                  <span className="ml-2 text-muted">{suggestion.subtitle}</span>
                ) : null}
              </span>
              <span className={cn("shrink-0 text-xs", index === activeIndex ? "text-acid" : "text-muted")}>
                {typeT(suggestion.type)}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </form>
  )
}
