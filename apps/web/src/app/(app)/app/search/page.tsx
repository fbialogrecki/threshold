import {
  Buildings,
  CalendarDots,
  MagnifyingGlass,
  UserCircle,
  UsersThree,
} from "@phosphor-icons/react/ssr"
import type { Metadata } from "next"
import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"

import { SearchBar } from "@/components/shell/search-bar"
import { EmptyState } from "@/components/ui/empty-state"
import { MonoLabel } from "@/components/ui/mono-label"
import { searchWithStatus } from "@/lib/api/search"
import { cn } from "@/lib/cn"
import { groupSearchResults, searchSuggestions } from "@/lib/search/grouping"
import type { SearchResultType } from "@/lib/types"

export const dynamic = "force-dynamic"

const TYPES: SearchResultType[] = [
  "artist",
  "consumer",
  "club",
  "collective",
  "project",
  "festival",
  "group",
  "event",
]

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("searchPage.metadata")
  return { title: t("title"), description: t("description") }
}

function buildHref(q: string, type?: SearchResultType): string {
  const params = new URLSearchParams()
  if (q) params.set("q", q)
  if (type) params.set("type", type)
  const qs = params.toString()
  return qs ? `/app/search?${qs}` : "/app/search"
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; type?: string }>
}) {
  const params = await searchParams
  const q = params.q ?? ""
  const type = TYPES.find((value) => value === params.type)
  const [t, locale] = await Promise.all([
    getTranslations("searchPage"),
    getLocale(),
  ])
  const result = await searchWithStatus(q, type, locale)
  const groups = groupSearchResults(result.items)
  const suggestions = searchSuggestions()

  return (
    <div className="flex flex-col gap-6">
      <header className="border-b border-border-gray pb-4">
        <h1 className="flex items-center gap-3 font-display text-4xl tracking-wide text-raw-white">
          <MagnifyingGlass size={34} weight="bold" aria-hidden />
          {t("title")}
        </h1>
        <MonoLabel tone="muted" className="mt-1 block">{t("subtitle")}</MonoLabel>
      </header>
      <SearchBar initialQuery={q} />

      <nav aria-label={t("filterLabel")} className="flex flex-wrap gap-1">
        <Link
          href={buildHref(q)}
          aria-current={!type ? "page" : undefined}
          className={cn(
            "border px-3 py-1.5 font-mono text-[11px] uppercase tracking-label",
            !type ? "border-acid text-acid" : "border-border-gray text-muted hover:text-raw-white",
          )}
        >
          {t("filters.all")}
        </Link>
        {TYPES.map((filter) => (
          <Link
            key={filter}
            href={buildHref(q, filter)}
            aria-current={type === filter ? "page" : undefined}
            className={cn(
              "border px-3 py-1.5 font-mono text-[11px] uppercase tracking-label",
              type === filter
                ? "border-acid text-acid"
                : "border-border-gray text-muted hover:text-raw-white",
            )}
          >
            {t(`filters.${filter}`)}
          </Link>
        ))}
      </nav>

      {result.error ? (
        <EmptyState
          title={t("loadErrorTitle")}
          eyebrow={t("errorEyebrow")}
          body={t("loadErrorBody")}
          actionLabel={t("retry")}
          actionHref={buildHref(q, type)}
        />
      ) : result.items.length === 0 ? (
        <EmptyState
          title={q ? t("noResults") : t("emptyTitle")}
          eyebrow={t("emptyEyebrow")}
          body={
            q
              ? t("noResultsBody", { query: q })
              : t("emptyBody")
          }
        >
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {suggestions.map((suggestion) => (
              <Link
                key={suggestion.id}
                href={suggestion.href}
                className="border border-border-gray px-3 py-1.5 font-mono text-[11px] uppercase tracking-label text-muted hover:border-acid hover:text-acid"
              >
                {t(`suggestions.${suggestion.id}`)}
              </Link>
            ))}
          </div>
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-5">
          {groups.map((group) => (
            <section key={group.id} className="flex flex-col gap-2">
              <MonoLabel tone="muted">
                <span className="inline-flex items-center gap-2">
                  {group.id === "profiles" ? <UserCircle size={15} weight="bold" aria-hidden /> : null}
                  {group.id === "pages" ? <Buildings size={15} weight="bold" aria-hidden /> : null}
                  {group.id === "groups" ? <UsersThree size={15} weight="bold" aria-hidden /> : null}
                  {group.id === "events" ? <CalendarDots size={15} weight="bold" aria-hidden /> : null}
                  {t(`groups.${group.id}`)}
                </span>
              </MonoLabel>
              <ul className="divide-y divide-border-gray border border-border-gray bg-graphite">
                {group.items.map((result) => (
                  <li key={`${result.type}-${result.href}`}>
                    <Link
                      href={result.href}
                      className="flex items-center justify-between gap-4 px-4 py-3 hover:bg-raised"
                    >
                      <span>
                        <span className="font-display text-lg tracking-wide text-raw-white">
                          {result.title}
                        </span>
                        <span className="ml-2 font-mono text-[11px] uppercase tracking-label text-muted">
                          {result.subtitle}
                        </span>
                      </span>
                      <MonoLabel tone="muted">{t(`filters.${result.type}`)}</MonoLabel>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
