import type { ReactNode } from "react"

import { PublicShell } from "@/components/shell/public-shell"

export default function EventDetailLayout({ children }: { children: ReactNode }) {
  return <PublicShell wide>{children}</PublicShell>
}
