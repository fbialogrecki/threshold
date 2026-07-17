import { ArrowLeft } from "@phosphor-icons/react/ssr"
import type { Metadata } from "next"
import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import { auth } from "@/auth"
import { PostCard } from "@/components/cards/post-card"
import { ComposeForm } from "@/components/compose/compose-form"
import { JoinButton } from "@/components/groups/join-button"
import { AppShell } from "@/components/shell/app-shell"
import { EmptyState } from "@/components/ui/empty-state"
import { MonoLabel } from "@/components/ui/mono-label"
import {
  getGroupPostsResult,
  getGroupResult,
  getMyGroupSlugsResult,
} from "@/lib/api/social-read"
import { cityLabel } from "@/lib/cities"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("groupDetail.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function GroupDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const session = await auth()
  if (!session?.user) {
    redirect(`/login?callbackUrl=${encodeURIComponent(`/groups/${slug}`)}`)
  }

  const [groupResult, t, locale] = await Promise.all([
    getGroupResult(slug),
    getTranslations("groupDetail"),
    getLocale(),
  ])
  if (groupResult.status === "notFound") notFound()
  if (groupResult.status === "error") {
    return (
      <AppShell session={session}>
        <EmptyState
          title={t("loadErrorTitle")}
          body={t("loadErrorBody")}
          eyebrow={t("errorEyebrow")}
          actionLabel={t("retry")}
          actionHref={`/groups/${slug}`}
        />
      </AppShell>
    )
  }
  const group = groupResult.group
  const [postResult, membershipResult] = await Promise.all([
    getGroupPostsResult(slug),
    getMyGroupSlugsResult(),
  ])
  if (postResult.error || membershipResult.error) {
    return (
      <AppShell session={session}>
        <EmptyState
          title={t("loadErrorTitle")}
          body={t("loadErrorBody")}
          eyebrow={t("errorEyebrow")}
          actionLabel={t("retry")}
          actionHref={`/groups/${slug}`}
        />
      </AppShell>
    )
  }
  const joined = membershipResult.items.includes(slug)

  return (
    <AppShell session={session}>
      <div className="text-raw-white">
        <Link
          href="/groups"
          className="font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid"
        >
          <span className="inline-flex items-center gap-2">
            <ArrowLeft size={14} weight="bold" aria-hidden />
            {t("back")}
          </span>
        </Link>

        <header className="mt-6 flex flex-col gap-4 border-b border-border-gray pb-6 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <span className="flex items-center gap-2">
              <h1 className="font-display text-5xl tracking-wide">{group.name}</h1>
              {group.official ? <MonoLabel tone="acid">{t("official")}</MonoLabel> : null}
            </span>
            <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-violet">
              {[cityLabel(group.city, locale), group.sceneTag].filter(Boolean).join(" / ")}
            </p>
          </div>
          <JoinButton slug={group.slug} isAuthenticated initialJoined={joined} />
        </header>

        {joined ? (
          <div className="mt-6">
            <ComposeForm groupSlug={group.slug} />
          </div>
        ) : null}

        <div className="mt-6 flex flex-col gap-4">
          {postResult.items.length === 0 ? (
            <div className="border border-dashed border-border-gray bg-graphite p-8">
              <h2 className="font-display text-2xl tracking-wide text-dim-white">
                {t("emptyTitle")}
              </h2>
              <p className="mt-2 max-w-md text-sm leading-7 text-muted">
                {joined
                  ? t("emptyJoined")
                  : t("emptyNotJoined")}
              </p>
            </div>
          ) : (
            postResult.items.map((post) => <PostCard key={post.id} post={post} />)
          )}
        </div>
      </div>
    </AppShell>
  )
}
