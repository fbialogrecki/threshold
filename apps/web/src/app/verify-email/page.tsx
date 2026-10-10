import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { AuthShell } from "@/components/auth/auth-shell"
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
    <AuthShell>
      <VerifyEmailForm token={token ?? null} />
    </AuthShell>
  )
}
