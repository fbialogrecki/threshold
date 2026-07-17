import type { SearchResult } from "@/lib/types"

export type MentionMarker = "@" | "#"

export type MentionTrigger = {
  marker: MentionMarker
  query: string
  start: number
  end: number
}

export type MentionSuggestion = SearchResult & {
  handle: string
}

const TOKEN_RE = /^[A-Za-z0-9_-]{0,64}$/

export function activeMentionTrigger(text: string, caret: number): MentionTrigger | null {
  const safeCaret = Math.max(0, Math.min(caret, text.length))
  const before = text.slice(0, safeCaret)
  const tokenStart = Math.max(
    before.lastIndexOf(" "),
    before.lastIndexOf("\n"),
    before.lastIndexOf("\t"),
  ) + 1
  const token = before.slice(tokenStart)
  const marker = token[0]

  if (marker !== "@" && marker !== "#") return null
  if (tokenStart > 0 && !/\s/.test(text[tokenStart - 1] ?? "")) return null

  const query = token.slice(1)
  if (!TOKEN_RE.test(query)) return null

  return { marker, query, start: tokenStart, end: safeCaret }
}

export function mentionSearchQuery(trigger: MentionTrigger): string {
  return `${trigger.marker}${trigger.query}`
}

export function mentionTokenForSuggestion(suggestion: MentionSuggestion): string {
  return suggestion.type === "event" ? `#${suggestion.handle}` : `@${suggestion.handle}`
}

export function applyMentionSuggestion(
  text: string,
  caret: number,
  suggestion: MentionSuggestion,
): { text: string; caret: number } {
  const trigger = activeMentionTrigger(text, caret)
  if (!trigger) return { text, caret }

  const token = `${mentionTokenForSuggestion(suggestion)} `
  const tailStart = text[trigger.end] === " " ? trigger.end + 1 : trigger.end
  const next = `${text.slice(0, trigger.start)}${token}${text.slice(tailStart)}`
  return { text: next, caret: trigger.start + token.length }
}

export function suggestionMatchesMarker(
  suggestion: MentionSuggestion,
  marker: MentionMarker,
): boolean {
  return marker === "#"
    ? suggestion.type === "event"
    : suggestion.type !== "event" && suggestion.type !== "group"
}
