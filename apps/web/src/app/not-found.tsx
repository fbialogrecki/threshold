import { getTranslations } from "next-intl/server"

import { AuthPanel } from "@/components/auth/auth-panel"
import { AuthShell } from "@/components/auth/auth-shell"
import { ButtonLink } from "@/components/ui/button"

export default async function NotFound() {
  const t = await getTranslations("errorPages")
  return (
    <AuthShell>
      <AuthPanel title={t("notFoundTitle")} caption={t("notFoundBody")}>
        <p className="mt-5 font-mono text-xs text-muted">404</p>
        <ButtonLink href="/" variant="primary" size="lg" className="mt-6 w-full">
          {t("home")}
        </ButtonLink>
      </AuthPanel>
    </AuthShell>
  )
}
