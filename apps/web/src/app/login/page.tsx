import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import { redirect } from "next/navigation"

import { auth } from "@/auth"
import { AuthCard } from "@/components/auth/auth-card"
import { authenticatedHref } from "@/lib/auth/routing"
import { safeInternalHref } from "@/lib/safe-href"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("authFlow.metadata")
  return { title: t("loginTitle"), description: t("loginDescription") }
}

export const dynamic = "force-dynamic"

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string }>
}) {
  const { callbackUrl } = await searchParams
  const safeCallback = safeInternalHref(callbackUrl, "/app") ?? "/app"
  const session = await auth()
  if (session?.user) redirect(authenticatedHref(session, safeCallback))

  return (
    <main className="flex min-h-screen items-center justify-center bg-pitch px-6 text-raw-white">
      <AuthCard initialMode="login" callbackUrl={safeCallback} />
    </main>
  )
}
