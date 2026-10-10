import { describe, expect, test } from "bun:test"

import { canContinue, isSkipping, type Draft } from "../steps"

const draft: Draft = {
  nickname: "Żaba_92",
  city: null,
  scenes: [],
  isArtist: false,
  role: "DJ",
  artistUrl: "",
  pages: [],
}

describe("canContinue", () => {
  test("identity keeps the explicit username set and length", () => {
    expect(canContinue("identity", draft)).toBe(true)
    expect(canContinue("identity", { ...draft, nickname: "  NightCrawler  " })).toBe(true)
    expect(canContinue("identity", { ...draft, nickname: "ab" })).toBe(false)
    expect(canContinue("identity", { ...draft, nickname: "a".repeat(31) })).toBe(false)
    // Cyrillic "а" lookalike and spaces stay out.
    expect(canContinue("identity", { ...draft, nickname: "nаme" })).toBe(false)
    expect(canContinue("identity", { ...draft, nickname: "night crawler" })).toBe(false)
  })

  test("city is required", () => {
    expect(canContinue("city", draft)).toBe(false)
    expect(canContinue("city", { ...draft, city: "Warsaw" })).toBe(true)
  })

  test("artist profile needs a role and an http(s) link when given", () => {
    const artist = { ...draft, isArtist: true }
    expect(canContinue("artist", draft)).toBe(true)
    expect(canContinue("artist", artist)).toBe(true)
    expect(canContinue("artist", { ...artist, role: " " })).toBe(false)
    expect(canContinue("artist", { ...artist, artistUrl: "javascript:alert(1)" })).toBe(false)
    expect(canContinue("artist", { ...artist, artistUrl: "https://example.org" })).toBe(true)
  })

  test("pages must be valid and unique", () => {
    const page = { display_name: "Club", slug: "club", page_type: "club" as const, about: "" }
    expect(canContinue("pages", { ...draft, pages: [page] })).toBe(true)
    expect(canContinue("pages", { ...draft, pages: [page, page] })).toBe(false)
    expect(canContinue("pages", { ...draft, pages: [{ ...page, slug: "Bad Slug" }] })).toBe(false)
  })
})

describe("isSkipping", () => {
  test("only optional steps left empty count as skipped", () => {
    expect(isSkipping("frequencies", draft)).toBe(true)
    expect(isSkipping("frequencies", { ...draft, scenes: ["techno"] })).toBe(false)
    expect(isSkipping("artist", draft)).toBe(true)
    expect(isSkipping("artist", { ...draft, isArtist: true })).toBe(false)
    expect(isSkipping("pages", draft)).toBe(true)
    expect(isSkipping("identity", draft)).toBe(false)
    expect(isSkipping("city", draft)).toBe(false)
    expect(isSkipping("access", draft)).toBe(false)
  })
})
