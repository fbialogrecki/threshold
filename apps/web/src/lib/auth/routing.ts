import { canonicalCity } from "@/lib/cities"
import { safeInternalHref } from "@/lib/safe-href"

type OnboardingSession = {
  onboarding_preferences?: {
    city?: string | null
  } | null
}

function callbackHref(value: string | null | undefined): string {
  const href = safeInternalHref(value, "/app") ?? "/app"
  return href.startsWith("/onboarding") ? "/app" : href
}

export function hasRequiredOnboarding(session: OnboardingSession): boolean {
  return canonicalCity(session.onboarding_preferences?.city) !== null
}

export function loginHref(callbackUrl: string): string {
  return `/login?callbackUrl=${encodeURIComponent(callbackHref(callbackUrl))}`
}

export function onboardingHref(callbackUrl?: string | null): string {
  return `/onboarding?callbackUrl=${encodeURIComponent(callbackHref(callbackUrl))}`
}

export function authenticatedHref(
  session: OnboardingSession,
  callbackUrl?: string | null,
): string {
  const callback = callbackHref(callbackUrl)
  return hasRequiredOnboarding(session) ? callback : onboardingHref(callback)
}

export function currentPageHref(
  pathname: string,
  search = "",
  hash = "",
): string {
  return safeInternalHref(`${pathname}${search}${hash}`, "/app") ?? "/app"
}
