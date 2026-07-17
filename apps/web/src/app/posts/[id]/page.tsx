import type { Metadata } from "next"
import { notFound, redirect } from "next/navigation"

import { auth } from "@/auth"
import { PostCard } from "@/components/cards/post-card"
import { AppShell } from "@/components/shell/app-shell"
import { getComments, getPost } from "@/lib/api/social-read"

export const dynamic = "force-dynamic"

export const metadata: Metadata = {
  title: "Post | Threshold",
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
  const comments = await getComments(id)

  return (
    <AppShell session={session}>
      <div className="flex flex-col gap-6">
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
