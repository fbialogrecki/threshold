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
    // People are named by their username alone, without an @.
    dispatch({ type: "select", label: result.handle })
    onSelect(result)
  }

  const activeOptionId = state.open && state.results.length > 0
    ? `${listId}-option-${state.activeIndex}`
    : undefined

  return (
    <div className="relative">
      <label
        htmlFor={inputId}
        className="mb-2 block text-sm font-medium text-raw-white"
      >
        {label ?? t("guestSearchLabel")}
      </label>
      <div className="flex items-center gap-2 rounded-control border border-border-gray bg-pitch px-3.5 transition-[border-color,box-shadow] focus-within:border-acid focus-within:shadow-[0_0_0_3px_rgba(198,255,0,0.18)]">
        <MagnifyingGlass size={16} weight="bold" className="shrink-0 text-muted" aria-hidden />
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
          className="min-w-0 flex-1 bg-transparent py-3 text-base text-raw-white placeholder:text-muted focus:outline-none"
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
        <div
          id={listId}
          role="listbox"
          className="absolute z-30 mt-2 w-full overflow-hidden rounded-control border border-border-gray bg-graphite p-1 shadow-[0_20px_50px_-20px_rgba(0,0,0,0.9)]"
        >
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
                "flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left",
                index === state.activeIndex ? "bg-acid/15 text-raw-white" : "text-raw-white hover:bg-raised",
              )}
            >
              <User size={16} weight="bold" className={index === state.activeIndex ? "text-acid" : "text-muted"} aria-hidden />
              <span className="min-w-0 truncate text-[15px] font-medium">{result.handle}</span>
            </button>
          ))}
        </div>
      ) : state.status === "loading" ? (
        <p className="mt-2 text-[13px] text-muted" role="status">
          {t("guestSearchLoading")}
        </p>
      ) : state.status === "error" ? (
        <p className="mt-2 text-[13px] text-orange" role="alert">
          {t("guestSearchError")}
        </p>
      ) : state.status === "success" && state.results.length === 0 ? (
        <p className="mt-2 text-[13px] text-muted">
          {t("guestSearchEmpty")}
        </p>
      ) : null}
    </div>
  )
}
