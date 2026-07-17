import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { VerifyEmailForm } from "@/components/auth/verify-email-form"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("authUtility.metadata")
  return { title: t("verifyTitle"), description: t("verifyDescription") }
}

export const dynamic = "force-dynamic"

export default async function VerifyEmailPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>
}) {
  const { token } = await searchParams
  return (
    <main className="flex min-h-screen items-center justify-center bg-pitch px-6 text-raw-white">
      <VerifyEmailForm token={token ?? null} />
    </main>
  )
}
