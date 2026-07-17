import { describe, expect, it } from "bun:test"

import {
  authenticatedHref,
  currentPageHref,
  hasRequiredOnboarding,
  loginHref,
  onboardingHref,
} from "@/lib/auth/routing"

describe("auth routing", () => {
  it("requires a supported persisted city", () => {
    expect(hasRequiredOnboarding({ onboarding_preferences: null })).toBeFalse()
    expect(hasRequiredOnboarding({
      onboarding_preferences: { city: "Unknown" },
    })).toBeFalse()
    expect(hasRequiredOnboarding({
      onboarding_preferences: { city: "Wroclaw" },
    })).toBeTrue()
  })

  it("routes incomplete accounts through onboarding while preserving callbacks", () => {
    expect(authenticatedHref(
      { onboarding_preferences: { city: null } },
      "/events/night?tab=lineup",
    )).toBe("/onboarding?callbackUrl=%2Fevents%2Fnight%3Ftab%3Dlineup")
  })

  it("keeps safe callbacks for complete accounts and blocks redirect loops", () => {
    const complete = {
      onboarding_preferences: { city: "Warsaw" },
    }
    expect(authenticatedHref(complete, "/pages/club")).toBe("/pages/club")
    expect(authenticatedHref(complete, "/onboarding")).toBe("/app")
    expect(authenticatedHref(complete, "https://evil.test")).toBe("/app")
  })

  it("builds encoded login and onboarding links", () => {
    expect(loginHref("/u/night?tab=events")).toBe(
      "/login?callbackUrl=%2Fu%2Fnight%3Ftab%3Devents",
    )
    expect(onboardingHref("//evil.test")).toBe(
      "/onboarding?callbackUrl=%2Fapp",
    )
    expect(loginHref("/%252F%252Fevil.test")).toBe(
      "/login?callbackUrl=%2Fapp",
    )
  })

  it("preserves the current nested app path, query and hash", () => {
    expect(currentPageHref("/app/settings", "?tab=account", "#sessions")).toBe(
      "/app/settings?tab=account#sessions",
    )
    expect(currentPageHref("//evil.test", "", "")).toBe("/app")
  })
})
