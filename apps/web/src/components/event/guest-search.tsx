"use client"

import { MagnifyingGlass, User } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useEffect, useId, useReducer, useRef } from "react"

import { cn } from "@/lib/cn"
import {
  guestSearchReducer,
  initialGuestSearchState,
} from "@/lib/events/guest-search-state"
import type { SearchResult } from "@/lib/types"

export type GuestSelection = Pick<SearchResult, "handle" | "title" | "type">

export function GuestSearch({
  disabled,
  label,
  onSelect,
  placeholder,
}: {
  disabled?: boolean
  label?: string
  onSelect: (guest: GuestSelection | null) => void
  placeholder?: string
}) {
  const t = useTranslations("eventDetail.access")
  const inputId = useId()
  const listId = useId()
  const requestRef = useRef(0)
  const [state, dispatch] = useReducer(guestSearchReducer, initialGuestSearchState)

  useEffect(() => {
    if (state.status !== "loading") return
    const value = state.query.trim()
    const requestId = state.requestId
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(
          `/api/search/mentions?q=${encodeURIComponent(`@${value}`)}`,
          { signal: controller.signal },
        )
        if (!response.ok) throw new Error("search failed")
        const body: unknown = await response.json()
        const people = Array.isArray(body)
          ? (body as SearchResult[]).filter(({ type }) => type === "consumer" || type === "artist")
          : []
        dispatch({ type: "success", requestId, results: people })
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          dispatch({ type: "error", requestId })
        }
      }
    }, 150)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [state.query, state.requestId, state.status])

  function select(result: SearchResult) {
    dispatch({ type: "select", label: `@${result.handle} · ${result.title}` })
    onSelect(result)
  }

  const activeOptionId = state.open && state.results.length > 0
    ? `${listId}-option-${state.activeIndex}`
    : undefined

  return (
    <div className="relative">
      <label
        htmlFor={inputId}
        className="mb-1 block font-mono text-[11px] uppercase tracking-label text-muted"
      >
        {label ?? t("guestSearchLabel")}
      </label>
      <div className="flex items-center gap-2 border border-border-gray bg-graphite px-3 focus-within:border-acid">
        <MagnifyingGlass size={16} weight="bold" className="text-muted" aria-hidden />
        <input
          id={inputId}
          type="search"
          value={state.query}
          disabled={disabled}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={state.open}
          aria-controls={listId}
          aria-activedescendant={activeOptionId}
          placeholder={placeholder ?? t("guestSearchPlaceholder")}
          className="min-w-0 flex-1 bg-transparent py-2.5 text-sm text-raw-white placeholder:text-muted"
          onChange={(event) => {
            const value = event.target.value
            requestRef.current += 1
            dispatch({ type: "query", query: value, requestId: requestRef.current })
            onSelect(null)
          }}
          onFocus={() => dispatch({ type: "open" })}
          onBlur={() => window.setTimeout(() => dispatch({ type: "close" }), 120)}
          onKeyDown={(event) => {
            if (!state.open || state.results.length === 0) return
            if (event.key === "ArrowDown") {
              event.preventDefault()
              dispatch({ type: "move", direction: 1 })
            } else if (event.key === "ArrowUp") {
              event.preventDefault()
              dispatch({ type: "move", direction: -1 })
            } else if (event.key === "Enter") {
              event.preventDefault()
              select(state.results[state.activeIndex] ?? state.results[0])
            } else if (event.key === "Escape") {
              dispatch({ type: "close" })
            }
          }}
        />
      </div>
      {state.open ? (
        <div id={listId} role="listbox" className="absolute z-30 mt-1 w-full border border-border-gray bg-raised">
          {state.results.map((result, index) => (
            <button
              id={`${listId}-option-${index}`}
              key={`${result.type}:${result.handle}`}
              type="button"
              role="option"
              aria-selected={index === state.activeIndex}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => select(result)}
              className={cn(
                "flex w-full items-center gap-3 px-3 py-2 text-left",
                index === state.activeIndex ? "bg-acid text-pitch" : "text-raw-white hover:bg-graphite",
              )}
            >
              <User size={16} weight="bold" aria-hidden />
              <span className="min-w-0">
                <span className="block truncate text-sm">{result.title}</span>
                <span className="block truncate font-mono text-[11px] uppercase tracking-label opacity-70">
                  @{result.handle}
                </span>
              </span>
            </button>
          ))}
        </div>
      ) : state.status === "loading" ? (
        <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-muted" role="status">
          {t("guestSearchLoading")}
        </p>
      ) : state.status === "error" ? (
        <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-error" role="alert">
          {t("guestSearchError")}
        </p>
      ) : state.status === "success" && state.results.length === 0 ? (
        <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-muted">
          {t("guestSearchEmpty")}
        </p>
      ) : null}
    </div>
  )
}
