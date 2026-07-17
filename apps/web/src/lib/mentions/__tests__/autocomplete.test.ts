import { describe, expect, it } from "bun:test"

import {
  activeMentionTrigger,
  applyMentionSuggestion,
  mentionSearchQuery,
  mentionTokenForSuggestion,
  suggestionMatchesMarker,
  type MentionSuggestion,
} from "@/lib/mentions/autocomplete"

const artist: MentionSuggestion = {
  type: "artist",
  title: "DJ One",
  subtitle: "Warsaw",
  href: "/u/dj-one",
  handle: "dj-one",
}

const event: MentionSuggestion = {
  type: "event",
  title: "Bass Theory",
  subtitle: "Berlin",
  href: "/events/bass-theory",
  handle: "bass-theory",
}

const group: MentionSuggestion = {
  type: "group",
  title: "Warsaw Techno",
  subtitle: "Warsaw",
  href: "/groups/warsaw-techno",
  handle: "warsaw-techno",
}

describe("activeMentionTrigger", () => {
  it("detects @ and # tokens at the caret", () => {
    expect(activeMentionTrigger("hi @dj", 6)).toEqual({ marker: "@", query: "dj", start: 3, end: 6 })
    expect(activeMentionTrigger("go #bass", 8)).toEqual({ marker: "#", query: "bass", start: 3, end: 8 })
  })

  it("ignores email, url and mid-word false positives", () => {
    expect(activeMentionTrigger("mail a@b", 8)).toBeNull()
    expect(activeMentionTrigger("https://x.test/#bass", 20)).toBeNull()
    expect(activeMentionTrigger("abc@dj", 6)).toBeNull()
  })

  it("rejects token chars outside handle alphabet", () => {
    expect(activeMentionTrigger("hi @dj.one", 10)).toBeNull()
  })
})

describe("mention helpers", () => {
  it("builds search queries with marker prefixes", () => {
    expect(mentionSearchQuery({ marker: "@", query: "dj", start: 0, end: 3 })).toBe("@dj")
    expect(mentionSearchQuery({ marker: "#", query: "bass", start: 0, end: 5 })).toBe("#bass")
  })

  it("builds insertion tokens by target type", () => {
    expect(mentionTokenForSuggestion(artist)).toBe("@dj-one")
    expect(mentionTokenForSuggestion(event)).toBe("#bass-theory")
  })

  it("replaces only the active token and appends a space", () => {
    expect(applyMentionSuggestion("hello @dj world", 9, artist)).toEqual({
      text: "hello @dj-one world",
      caret: 14,
    })
  })

  it("keeps @ suggestions to profiles/pages and # suggestions to events", () => {
    expect(suggestionMatchesMarker(artist, "@")).toBe(true)
    expect(suggestionMatchesMarker(event, "#")).toBe(true)
    expect(suggestionMatchesMarker(group, "@")).toBe(false)
    expect(suggestionMatchesMarker(artist, "#")).toBe(false)
  })
})
