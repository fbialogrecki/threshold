import { canonicalCity, cityLabel, type CanonicalCity } from "@/lib/cities"

export type ParsedOnboardingPayload = {
  city: CanonicalCity | null
  preferredScenes: string[]
}

type SocialResponse = { status: number; body: unknown }
type SocialCall = (
  path: string,
  options?: { method?: string; userHeaders?: HeadersInit },
) => Promise<SocialResponse>
type UpdateOnboarding = (payload: {
  city: CanonicalCity
  preferred_scenes: string | null
}) => Promise<SocialResponse>

type CityGroup = {
  slug: string
  city: string
  official: boolean
}

export type CityGroupBootstrapResult =
  | { status: "not_found" | "lookup_failed" }
  | { status: "joined" | "join_failed"; slug: string }

function cleanList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function parseOnboardingPayload(value: unknown): ParsedOnboardingPayload {
  const body = typeof value === "object" && value !== null ? (value as Record<string, unknown>) : {}
  return {
    city: canonicalCity(body.city),
    preferredScenes: cleanList(body.preferredScenes),
  }
}

export function hasRequiredOnboardingCity(
  payload: ParsedOnboardingPayload,
): payload is ParsedOnboardingPayload & { city: CanonicalCity } {
  return payload.city !== null
}

function isCityGroup(value: unknown): value is CityGroup {
  if (typeof value !== "object" || value === null) return false
  const group = value as Record<string, unknown>
  return typeof group.slug === "string"
    && typeof group.city === "string"
    && typeof group.official === "boolean"
}

export async function bootstrapCityGroup(
  city: CanonicalCity,
  userHeaders: HeadersInit,
  call: SocialCall,
): Promise<CityGroupBootstrapResult> {
  let groups: SocialResponse
  try {
    groups = await call("/v1/groups")
  } catch {
    return { status: "lookup_failed" }
  }
  if (groups.status !== 200 || !Array.isArray(groups.body)) return { status: "lookup_failed" }

  const group = groups.body.find(
    (candidate): candidate is CityGroup =>
      isCityGroup(candidate) && candidate.official && candidate.city === city,
  )
  if (!group) return { status: "not_found" }

  try {
    const joined = await call(`/v1/groups/${encodeURIComponent(group.slug)}/membership`, {
      method: "POST",
      userHeaders,
    })
    return { status: joined.status === 200 ? "joined" : "join_failed", slug: group.slug }
  } catch {
    return { status: "join_failed", slug: group.slug }
  }
}

export async function persistOnboarding(
  payload: ParsedOnboardingPayload,
  update: UpdateOnboarding,
  userHeaders: HeadersInit,
  call: SocialCall,
): Promise<{ result: SocialResponse; cityGroup: CityGroupBootstrapResult | null }> {
  if (!payload.city) {
    return { result: { status: 400, body: null }, cityGroup: null }
  }
  const cityGroup = await bootstrapCityGroup(payload.city, userHeaders, call)
  if (cityGroup.status !== "joined") {
    return {
      result: { status: 424, body: null },
      cityGroup,
    }
  }

  const result = await update({
    city: payload.city,
    preferred_scenes: payload.preferredScenes.length === 0
      ? null
      : payload.preferredScenes.join(","),
  })
  return { result, cityGroup }
}

export function onboardingSubmissionSucceeded(status: number): boolean {
  return status >= 200 && status < 300
}

export function buildEmptyFeedSuggestions({
  city,
  preferredScenes,
  locale = "en",
}: {
  city: string | null
  preferredScenes: string | null
  locale?: string
}): string[] {
  const scenes = preferredScenes?.split(",").map((scene) => scene.trim()).filter(Boolean) ?? []
  const displayCity = city ? cityLabel(city, locale) : null
  return [
    displayCity ? `Join official ${displayCity} groups` : "Join an official city group",
    scenes.length > 0 ? `Follow ${scenes.join(" and ")} pages` : "Follow artists, clubs and collectives",
    displayCity ? `Browse upcoming ${displayCity} events` : "Browse upcoming events",
  ]
}
