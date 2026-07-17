import { loginHref } from "@/lib/auth/routing"

type RecoveryFetcher = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>

type RecoveryOptions = {
  fetcher?: RecoveryFetcher
  navigate?: (href: string) => void
}

export async function recoverSession(
  callbackUrl: string,
  {
    fetcher = fetch,
    navigate = (href) => window.location.assign(href),
  }: RecoveryOptions = {},
): Promise<void> {
  const target = loginHref(callbackUrl)
  try {
    await fetcher("/api/auth/logout", {
      method: "POST",
      headers: { "content-type": "application/json" },
      credentials: "same-origin",
    })
  } catch {
    // Navigation still reaches a clean login surface if logout is unavailable.
  } finally {
    navigate(target)
  }
}
