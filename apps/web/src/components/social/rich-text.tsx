import Link from "next/link"

import { safeInternalHref } from "@/lib/safe-href"
import type { MentionRef } from "@/lib/types"

function mentionHref(mention: MentionRef): string {
  const safeTarget = safeInternalHref(mention.targetUrl)
  if (safeTarget) return safeTarget
  if (mention.mentionType === "event") return `/events/${mention.targetHandle}`
  if (mention.mentionType === "page") return `/pages/${mention.targetHandle}`
  return `/u/${mention.targetHandle}`
}

export function RichText({ text, mentions }: { text: string; mentions: MentionRef[] }) {
  const ranges = mentions
    .filter(
      (mention) =>
        mention.startIndex !== null &&
        mention.endIndex !== null &&
        mention.startIndex >= 0 &&
        mention.endIndex > mention.startIndex &&
        mention.endIndex <= text.length,
    )
    .sort((a, b) => (a.startIndex ?? 0) - (b.startIndex ?? 0))

  if (ranges.length === 0) return <>{text}</>

  const parts: React.ReactNode[] = []
  let cursor = 0
  for (const mention of ranges) {
    const start = mention.startIndex ?? 0
    const end = mention.endIndex ?? start
    if (start < cursor) continue
    if (start > cursor) parts.push(text.slice(cursor, start))
    parts.push(
      <Link key={`${mention.mentionType}:${mention.targetHandle}:${start}`} href={mentionHref(mention)} className="text-acid hover:underline">
        {text.slice(start, end)}
      </Link>,
    )
    cursor = end
  }
  if (cursor < text.length) parts.push(text.slice(cursor))
  return <>{parts}</>
}
