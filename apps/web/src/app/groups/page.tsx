import { ArrowRight, SealCheck } from "@phosphor-icons/react/ssr"
import type { Metadata } from "next"
import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"
import { redirect } from "next/navigation"

import { auth } from "@/auth"
import { AppShell } from "@/components/shell/app-shell"
import { EmptyState } from "@/components/ui/empty-state"
import { PageHeader } from "@/components/ui/page-header"
import { getGroupsResult } from "@/lib/api/social-read"
import { cityLabel } from "@/lib/cities"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("groups.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function GroupsPage() {
  const session = await auth()
  if (!session?.user) redirect("/login?callbackUrl=%2Fgroups")
  const [result, t, locale] = await Promise.all([
    getGroupsResult(),
    getTranslations("groups"),
    getLocale(),
  ])

  return (
    <AppShell session={session}>
      <div className="flex flex-col gap-6 text-raw-white">
        <PageHeader title={t("title")} subtitle={t("subtitle")} />

        {result.error ? (
          <EmptyState
            tone="error"
            title={t("loadErrorTitle")}
            body={t("loadErrorBody")}
            eyebrow={t("errorEyebrow")}
            actionLabel={t("retry")}
            actionHref="/groups"
          />
        ) : result.items.length === 0 ? (
          <EmptyState
            title={t("emptyTitle")}
            body={t("emptyBody")}
            eyebrow={t("emptyEyebrow")}
            actionLabel={t("backToFeed")}
            actionHref="/app"
          />
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {result.items.map((group) => (
              <li key={group.id}>
                <Link
                  href={`/groups/${group.slug}`}
                  className="group flex h-full flex-col justify-between gap-6 rounded-surface border border-border-gray bg-graphite/60 p-5 transition-colors hover:border-acid/60"
                >
                  <span className="min-w-0">
                    {group.official ? (
                      <span className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-acid/10 px-2.5 py-0.5 text-xs font-semibold text-acid">
                        <SealCheck size={14} weight="fill" aria-hidden />
                        {t("official")}
                      </span>
                    ) : null}
                    <span className="block font-display text-2xl leading-tight break-words text-raw-white">
                      {group.name}
                    </span>
                  </span>
                  <span className="flex items-center justify-between gap-3 text-sm text-dim-white">
                    <span className="min-w-0 truncate">
                      {[cityLabel(group.city, locale), group.sceneTag]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                    <ArrowRight
                      size={18}
                      weight="bold"
                      aria-hidden
                      className="shrink-0 text-muted transition-[color,translate] duration-200 ease-out-expo group-hover:translate-x-0.5 group-hover:text-acid"
                    />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
