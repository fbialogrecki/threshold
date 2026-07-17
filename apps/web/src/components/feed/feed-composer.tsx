import { PostComposer } from "@/components/compose/post-composer"

/** Desktop-only inline composer; mobile uses /app/compose. */
export function FeedComposer() {
  return (
    <div className="hidden lg:block">
      <PostComposer compact />
    </div>
  )
}
