import type { SearchResult } from "@/lib/types"

export type GuestSearchState = {
  query: string
  requestId: number
  status: "idle" | "loading" | "success" | "error"
  results: SearchResult[]
  activeIndex: number
  open: boolean
}

export type GuestSearchAction =
  | { type: "query"; query: string; requestId: number }
  | { type: "success"; requestId: number; results: SearchResult[] }
  | { type: "error"; requestId: number }
  | { type: "move"; direction: 1 | -1 }
  | { type: "open" | "close" }
  | { type: "select"; label: string }

export const initialGuestSearchState: GuestSearchState = {
  query: "",
  requestId: 0,
  status: "idle",
  results: [],
  activeIndex: 0,
  open: false,
}

export function guestSearchReducer(
  state: GuestSearchState,
  action: GuestSearchAction,
): GuestSearchState {
  if (action.type === "query") {
    const loading = action.query.trim().length >= 2
    return {
      ...state,
      query: action.query,
      requestId: action.requestId,
      status: loading ? "loading" : "idle",
      results: [],
      activeIndex: 0,
      open: false,
    }
  }
  if (action.type === "success") {
    if (action.requestId !== state.requestId) return state
    return {
      ...state,
      status: "success",
      results: action.results,
      activeIndex: 0,
      open: action.results.length > 0,
    }
  }
  if (action.type === "error") {
    return action.requestId === state.requestId
      ? { ...state, status: "error", results: [], activeIndex: 0, open: false }
      : state
  }
  if (action.type === "move") {
    if (state.results.length === 0) return state
    return {
      ...state,
      activeIndex: (
        state.activeIndex + action.direction + state.results.length
      ) % state.results.length,
    }
  }
  if (action.type === "select") {
    return { ...state, query: action.label, open: false }
  }
  return { ...state, open: action.type === "open" && state.results.length > 0 }
}
