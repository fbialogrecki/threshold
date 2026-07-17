"use client"

import { useEffect, useRef, useState, type KeyboardEvent, type TextareaHTMLAttributes } from "react"

import {
  activeMentionTrigger,
  applyMentionSuggestion,
  mentionSearchQuery,
  type MentionSuggestion,
} from "@/lib/mentions/autocomplete"
import { cn } from "@/lib/cn"

type Props = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "value" | "onChange"> & {
  value: string
  onChangeValue: (value: string) => void
}

export function MentionAutocompleteTextarea({
  value,
  onChangeValue,
  className,
  onKeyDown,
  onBlur,
  ...props
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [caret, setCaret] = useState(0)
  const [suggestions, setSuggestions] = useState<MentionSuggestion[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [open, setOpen] = useState(false)
  const trigger = activeMentionTrigger(value, caret)
  const queryKey = trigger ? mentionSearchQuery(trigger) : null

  function rememberCaret(element: HTMLTextAreaElement) {
    setCaret(element.selectionStart ?? element.value.length)
  }

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

  function selectSuggestion(suggestion: MentionSuggestion) {
    const next = applyMentionSuggestion(value, caret, suggestion)
    onChangeValue(next.text)
    setCaret(next.caret)
    setOpen(false)
    window.requestAnimationFrame(() => {
      textareaRef.current?.focus()
      textareaRef.current?.setSelectionRange(next.caret, next.caret)
    })
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
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
        selectSuggestion(suggestions[activeIndex] ?? suggestions[0])
        return
      }
      if (event.key === "Escape") {
        event.preventDefault()
        setOpen(false)
        return
      }
    }
    onKeyDown?.(event)
  }

  return (
    <div className="relative">
      <textarea
        {...props}
        ref={textareaRef}
        value={value}
        onChange={(event) => {
          onChangeValue(event.currentTarget.value)
          rememberCaret(event.currentTarget)
        }}
        onClick={(event) => rememberCaret(event.currentTarget)}
        onKeyUp={(event) => rememberCaret(event.currentTarget)}
        onKeyDown={handleKeyDown}
        onBlur={(event) => {
          window.setTimeout(() => setOpen(false), 120)
          onBlur?.(event)
        }}
        className={className}
      />
      {open && trigger ? (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 border border-border-gray bg-raised shadow-xl">
          {suggestions.map((suggestion, index) => (
            <button
              key={`${suggestion.type}:${suggestion.handle}`}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => selectSuggestion(suggestion)}
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
                {suggestion.type === "event" ? "event" : "target"}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
