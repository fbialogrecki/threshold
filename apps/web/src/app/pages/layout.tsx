import type { ReactNode } from "react"

import { PublicShell } from "@/components/shell/public-shell"

export default function PageProfileLayout({ children }: { children: ReactNode }) {
  return <PublicShell>{children}</PublicShell>
}
