import { ArrowRight, Buildings, CalendarDots, UserCircle, UsersThree } from "@phosphor-icons/react/ssr"
import type { Metadata } from "next"
import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"

import { SearchBar } from "@/components/shell/search-bar"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
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

const GROUP_ICON = {
  profiles: UserCircle,
  pages: Buildings,
  groups: UsersThree,
  events: CalendarDots,
} as const

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

function FilterChip({ href, active, children }: { href: string; active: boolean; children: string }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "inline-flex min-h-9 items-center rounded-full border px-3.5 text-[13px] font-medium transition-colors",
        active
          ? "border-acid bg-acid/10 text-acid"
          : "border-border-gray text-dim-white hover:border-status-neutral-border hover:text-raw-white",
      )}
    >
      {children}
    </Link>
  )
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
    <div className="flex flex-col gap-5">
      <PageHeader title={t("title")} subtitle={t("subtitle")} />
      <SearchBar initialQuery={q} />

      <nav aria-label={t("filterLabel")} className="flex flex-wrap gap-2">
        <FilterChip href={buildHref(q)} active={!type}>
          {t("filters.all")}
        </FilterChip>
        {TYPES.map((filter) => (
          <FilterChip key={filter} href={buildHref(q, filter)} active={type === filter}>
            {t(`filters.${filter}`)}
          </FilterChip>
        ))}
      </nav>

      {result.error ? (
        <EmptyState
          tone="error"
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
          body={q ? t("noResultsBody", { query: q }) : t("emptyBody")}
        >
          <ul className="mt-2 flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <li key={suggestion.id}>
                <Link
                  href={suggestion.href}
                  className="group inline-flex min-h-10 items-center gap-2 rounded-control border border-border-gray bg-pitch/60 px-3.5 text-sm font-medium text-raw-white transition-colors hover:border-acid"
                >
                  {t(`suggestions.${suggestion.id}`)}
                  <ArrowRight
                    size={14}
                    className="text-acid transition-transform duration-200 ease-out-expo group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </Link>
              </li>
            ))}
          </ul>
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-6">
          {groups.map((group) => {
            const Icon = GROUP_ICON[group.id]
            return (
              <section key={group.id} aria-labelledby={`search-group-${group.id}`}>
                <h2
                  id={`search-group-${group.id}`}
                  className="flex items-center gap-2 text-sm font-semibold text-dim-white"
                >
                  <Icon size={16} weight="bold" className="text-muted" aria-hidden />
                  {t(`groups.${group.id}`)}
                </h2>
                <ul className="mt-2 divide-y divide-border-gray overflow-hidden rounded-surface border border-border-gray bg-graphite/60">
                  {group.items.map((item) => (
                    <li key={`${item.type}-${item.href}`}>
                      <Link
                        href={item.href}
                        className="group flex items-center justify-between gap-4 px-4 py-3.5 transition-colors hover:bg-raised"
                      >
                        <span className="min-w-0">
                          {/* People keep their own case; entities take display type. */}
                          <span
                            className={cn(
                              "block truncate text-raw-white group-hover:text-acid",
                              group.id === "profiles"
                                ? "text-[15px] font-semibold"
                                : "font-display text-lg leading-tight",
                            )}
                          >
                            {item.title}
                          </span>
                          {item.subtitle ? (
                            <span className="mt-0.5 block truncate text-[13px] text-muted">
                              {item.subtitle}
                            </span>
                          ) : null}
                        </span>
                        <span className="shrink-0 rounded-full bg-raised px-2.5 py-0.5 text-xs text-dim-white">
                          {t(`filters.${item.type}`)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            )
          })}
        </div>
      )}
    </div>
  )
}
