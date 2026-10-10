import { ArrowLeft, SealCheck } from "@phosphor-icons/react/ssr"
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
          tone="error"
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
          tone="error"
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
          className="inline-flex items-center gap-2 text-sm text-muted transition-colors hover:text-raw-white"
        >
          <ArrowLeft size={14} weight="bold" aria-hidden />
          {t("back")}
        </Link>

        <header className="mt-4 flex flex-col gap-5 rounded-surface border border-border-gray bg-[radial-gradient(28rem_14rem_at_100%_0%,rgba(198,255,0,0.07),transparent_70%)] p-5 sm:flex-row sm:items-end sm:justify-between sm:p-7">
          <div className="min-w-0">
            {group.official ? (
              <span className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-acid/10 px-2.5 py-0.5 text-xs font-semibold text-acid">
                <SealCheck size={14} weight="fill" aria-hidden />
                {t("official")}
              </span>
            ) : null}
            <h1 className="font-display text-4xl leading-[0.95] break-words sm:text-5xl">{group.name}</h1>
            {/* City and scene are metadata, not a status: no hue. */}
            <p className="mt-2 text-[15px] text-dim-white">
              {[cityLabel(group.city, locale), group.sceneTag].filter(Boolean).join(" · ")}
            </p>
          </div>
          <JoinButton slug={group.slug} isAuthenticated initialJoined={joined} />
        </header>

        {joined ? (
          <div className="mt-5">
            <ComposeForm groupSlug={group.slug} />
          </div>
        ) : null}

        <h2 className="sr-only">{t("discussion")}</h2>
        <div className="mt-5">
          {postResult.items.length === 0 ? (
            <EmptyState
              title={t("emptyTitle")}
              body={joined ? t("emptyJoined") : t("emptyNotJoined")}
              eyebrow={t("emptyEyebrow")}
            />
          ) : (
            <div className="flex flex-col gap-3">
              {postResult.items.map((post) => (
                <PostCard key={post.id} post={post} />
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
