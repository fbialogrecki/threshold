import { PostComposer } from "@/components/compose/post-composer"

export function ComposeForm({
  groupSlug,
  onPosted,
}: {
  groupSlug?: string
  onPosted?: () => void
}) {
  return (
    <PostComposer
      groupSlug={groupSlug}
      onPosted={onPosted}
      redirectAfterPost={!groupSlug}
    />
  )
}
