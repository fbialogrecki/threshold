import type { Metadata } from "next"

import { FeedModesPrototype } from "@/components/prototypes/feed-modes-prototype"

export const metadata: Metadata = {
  title: "Feed mode prototype | Perlimen",
  description: "Compare classic, focus, and compact feed modes for Perlimen discovery.",
}

export default function FeedModesPrototypePage() {
  return <FeedModesPrototype />
}
