import type { ReactNode } from "react"

import { AuthServiceUnavailable } from "@/components/auth/auth-service-unavailable"
import { RouteRedirect } from "@/components/auth/route-redirect"
import { VerifyEmailBanner } from "@/components/auth/verify-email-banner"
import { AppShell } from "@/components/shell/app-shell"
import { hasRequiredOnboarding } from "@/lib/auth/routing"
import { getSessionState } from "@/lib/auth/session"

export default async function AppShellLayout({
  children,
}: {
  children: ReactNode
}) {
  // The whole authenticated section is gated here, in one place: logged-out
  // users never see the authed UI / mock access data.
  const state = await getSessionState()
  if (state.status === "unavailable") return <AuthServiceUnavailable />
  // Server Components cannot clear cookies or see the browser hash; the
  // redirect route handles both without exposing protected content.
  if (state.status === "anonymous") return <RouteRedirect destination="login" />
  if (state.status === "invalid") return <RouteRedirect destination="recover" />
  const session = state.session
  if (!hasRequiredOnboarding(session)) {
    return <RouteRedirect destination="onboarding" />
  }

  return (
    <AppShell
      session={session}
      banner={session.user.email_verified ? null : <VerifyEmailBanner />}
    >
      {children}
    </AppShell>
  )
}
