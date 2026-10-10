import { ArrowLeft } from "@phosphor-icons/react/ssr"
import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"

import { auth } from "@/auth"
import { PostCard } from "@/components/cards/post-card"
import { AppShell } from "@/components/shell/app-shell"
import { getComments, getPost } from "@/lib/api/social-read"
import { profileName } from "@/lib/profile-name"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("post")
  // The root template appends the brand, so the title stays bare.
  return { title: t("permalinkTitle") }
}

export default async function PostDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const session = await auth()
  if (!session?.user) {
    redirect(`/login?callbackUrl=${encodeURIComponent(`/posts/${id}`)}`)
  }

  const post = await getPost(id)
  if (!post) notFound()

  // SSR comments feed the inline section directly: no client refetch on load.
  const [comments, t, navigation] = await Promise.all([
    getComments(id),
    getTranslations("post"),
    getTranslations("navigation"),
  ])

  return (
    <AppShell session={session}>
      <div className="flex flex-col gap-4">
        <Link
          href="/app"
          className="inline-flex w-fit items-center gap-2 text-sm text-muted transition-colors hover:text-raw-white"
        >
          <ArrowLeft size={14} weight="bold" aria-hidden />
          {navigation("feed")}
        </Link>
        {/* The card already shows the author; the heading names the page for assistive tech. */}
        <h1 className="sr-only">{t("permalinkHeading", { name: profileName(post.author) })}</h1>
        <PostCard
          post={post}
          initialComments={comments}
          commentsDefaultOpen
          redirectHomeOnDelete
        />
      </div>
    </AppShell>
  )
}
