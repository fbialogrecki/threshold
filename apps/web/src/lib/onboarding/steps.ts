import { validPages, type PageDraft } from "@/lib/onboarding/setup"
import { USERNAME_PATTERN } from "@/lib/validation"

export const STEPS = ["identity", "city", "frequencies", "artist", "pages", "access", "done"] as const
export type StepName = (typeof STEPS)[number]

export type Draft = {
  nickname: string
  city: string | null
  scenes: string[]
  isArtist: boolean
  role: string
  artistUrl: string
  pages: PageDraft[]
}

const USERNAME_RE = new RegExp(`^${USERNAME_PATTERN}$`)

export function canContinue(step: StepName, draft: Draft): boolean {
  switch (step) {
    case "identity":
      return USERNAME_RE.test(draft.nickname.trim())
    case "city":
      return draft.city !== null
    case "artist": {
      const url = draft.artistUrl.trim()
      return !draft.isArtist || (draft.role.trim().length > 0 && (!url || /^https?:\/\//.test(url)))
    }
    case "pages":
      return validPages(draft.pages)
    default:
      return true
  }
}

/** An optional step left empty: continuing skips it, so the button says so. */
export function isSkipping(step: StepName, draft: Draft): boolean {
  if (step === "frequencies") return draft.scenes.length === 0
  if (step === "artist") return !draft.isArtist
  if (step === "pages") return draft.pages.length === 0
  return false
}
