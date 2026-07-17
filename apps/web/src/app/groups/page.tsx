import { ArrowRight, UsersThree } from "@phosphor-icons/react/ssr"
import type { Metadata } from "next"
import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"
import { redirect } from "next/navigation"

import { auth } from "@/auth"
import { AppShell } from "@/components/shell/app-shell"
import { EmptyState } from "@/components/ui/empty-state"
import { MonoLabel } from "@/components/ui/mono-label"
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
      <div className="text-raw-white">
        <header className="border-b border-border-gray pb-4">
          <h1 className="flex items-center gap-3 font-display text-5xl tracking-wide">
            <UsersThree size={40} weight="bold" aria-hidden />
            {t("title")}
          </h1>
          <MonoLabel tone="muted" className="mt-1 block">
            {t("subtitle")}
          </MonoLabel>
        </header>

        {result.error ? (
          <div className="mt-6">
            <EmptyState
              title={t("loadErrorTitle")}
              body={t("loadErrorBody")}
              eyebrow={t("errorEyebrow")}
              actionLabel={t("retry")}
              actionHref="/groups"
            />
          </div>
        ) : result.items.length === 0 ? (
          <div className="mt-6">
            <EmptyState
              title={t("emptyTitle")}
              body={t("emptyBody")}
              eyebrow={t("emptyEyebrow")}
              actionLabel={t("backToFeed")}
              actionHref="/app"
            />
          </div>
        ) : (
          <ul className="mt-6 divide-y divide-border-gray border border-border-gray bg-graphite">
            {result.items.map((group) => (
              <li key={group.id}>
                <Link
                  href={`/groups/${group.slug}`}
                  className="flex items-center justify-between gap-4 px-4 py-4 hover:bg-raised"
                >
                  <span>
                    <span className="flex items-center gap-2">
                      <span className="font-display text-xl tracking-wide text-raw-white">
                        {group.name}
                      </span>
                      {group.official ? (
                        <MonoLabel tone="acid">{t("official")}</MonoLabel>
                      ) : null}
                    </span>
                    <span className="mt-1 block font-mono text-[11px] uppercase tracking-label text-muted">
                      {[cityLabel(group.city, locale), group.sceneTag].filter(Boolean).join(" / ")}
                    </span>
                  </span>
                  <ArrowRight size={18} weight="bold" aria-hidden className="text-muted" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
