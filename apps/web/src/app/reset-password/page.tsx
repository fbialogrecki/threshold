import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"

import { AuthShell } from "@/components/auth/auth-shell"
import { ResetPasswordForm } from "@/components/auth/reset-password-form"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("authUtility.metadata")
  return { title: t("resetTitle"), description: t("resetDescription") }
}

export const dynamic = "force-dynamic"

export default async function ResetPasswordPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>
}) {
  const { token } = await searchParams
  return (
    <AuthShell>
      <ResetPasswordForm token={token ?? null} />
    </AuthShell>
  )
}
