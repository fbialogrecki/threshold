import type { Metadata } from "next"
import { redirect } from "next/navigation"

import { auth } from "@/auth"

export const metadata: Metadata = {
  title: "Feed mode prototype | Threshold",
  description: "Compare classic, focus, and compact feed modes for Threshold discovery.",
}

export default async function FeedModesPrototypeRedirectPage() {
  const session = await auth()
  redirect(
    session?.user
      ? "/app/prototypes/feed-modes"
      : "/login?callbackUrl=%2Fprototypes%2Ffeed-modes",
  )
}
