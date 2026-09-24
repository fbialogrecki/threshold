import { onboardingSubmissionSucceeded } from "@/lib/onboarding/plan"

type PageDraft = {
  display_name: string
  slug: string
  page_type: "club" | "collective" | "project" | "festival"
  about: string
}

type Setup = {
  username: string
  city: string
  scenes: string[]
  artist: { role: string; location: string; url: string } | null
  pages: PageDraft[]
}

type Step = "identity" | "artist" | "pages" | "access"
type ErrorKey = "nameTaken" | "profile" | "artist" | "pageTaken" | "page" | "pageInvalid" | "save" | "network"
export type SetupResult = { ok: true } | { ok: false; step: Step; error: ErrorKey }

export function validPages(pages: PageDraft[]): boolean {
  const slugs = pages.map((page) => page.slug.trim().toLowerCase())
  return new Set(slugs).size === slugs.length && pages.every((page) =>
    page.display_name.trim().length > 0
    && page.display_name.trim().length <= 160
    && /^[a-z0-9-]{2,120}$/.test(page.slug.trim().toLowerCase())
    && page.about.length <= 2000,
  )
}

export async function saveSetup(
  setup: Setup,
  createdSlugs: Set<string>,
  request: typeof fetch = fetch,
): Promise<SetupResult> {
  async function post(url: string, body: object, method = "POST") {
    return request(url, {
      method,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    })
  }

  if (!validPages(setup.pages)) return { ok: false, step: "pages", error: "pageInvalid" }
  const name = setup.username.trim().replace(/^@/, "")
  let step: Step = "identity"
  try {
    if (name) {
      const profile = await post("/api/me/profile", { username: name }, "PATCH")
      if (!profile.ok) {
        return { ok: false, step: "identity", error: profile.status === 409 ? "nameTaken" : "profile" }
      }
    }
    step = "artist"
    if (setup.artist) {
      const artist = await post("/api/me/artist", {
        role: setup.artist.role.trim(),
        location: setup.artist.location.trim(),
        links: setup.artist.url.trim()
          ? [{ label: "Website", url: setup.artist.url.trim() }]
          : [],
      })
      if (!artist.ok) return { ok: false, step: "artist", error: "artist" }
    }
    step = "pages"
    for (const page of setup.pages) {
      const slug = page.slug.trim().toLowerCase()
      const savedKey = `${slug}:${page.display_name.trim()}:${page.page_type}`
      if (createdSlugs.has(savedKey)) continue
      const result = await post("/api/pages", {
        slug,
        display_name: page.display_name.trim(),
        page_type: page.page_type,
        city: setup.city,
        about: page.about.trim(),
      })
      if (!result.ok) {
        if (result.status !== 409) return { ok: false, step: "pages", error: "page" }
        // A lost response after a successful create is safe to retry only if this user owns the Page.
        const owned = await request("/api/pages")
        if (!owned.ok) return { ok: false, step: "pages", error: "page" }
        const pages: unknown = await owned.json()
        if (!Array.isArray(pages) || !pages.some((entry: unknown) => {
          if (typeof entry !== "object" || entry === null) return false
          const item = entry as Record<string, unknown>
          return item.slug === slug && item.display_name === page.display_name.trim()
            && item.page_type === page.page_type
        })) return { ok: false, step: "pages", error: "pageTaken" }
      }
      createdSlugs.add(savedKey)
    }
    step = "access"
    const onboarding = await post("/api/onboarding", {
      city: setup.city,
      preferredScenes: setup.scenes,
    })
    if (!onboardingSubmissionSucceeded(onboarding.status)) {
      return { ok: false, step: "access", error: "save" }
    }
    return { ok: true }
  } catch {
    return { ok: false, step, error: "network" }
  }
}
