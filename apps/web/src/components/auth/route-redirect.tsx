"use client"

import { useTranslations } from "next-intl"
import { usePathname, useRouter } from "next/navigation"
import { useEffect } from "react"

import {
  currentPageHref,
  loginHref,
  onboardingHref,
} from "@/lib/auth/routing"
import { recoverSession } from "@/lib/auth/recovery"

export function RouteRedirect({
  destination,
}: {
  destination: "login" | "recover" | "onboarding"
}) {
  const pathname = usePathname()
  const router = useRouter()
  const t = useTranslations("authFlow")

  useEffect(() => {
    const current = currentPageHref(
      pathname,
      window.location.search,
      window.location.hash,
    )
    if (destination === "recover") {
      void recoverSession(current, {
        navigate: (href) => window.location.replace(href),
      })
    } else if (destination === "login") {
      window.location.replace(loginHref(current))
    } else {
      router.replace(onboardingHref(current))
    }
  }, [destination, pathname, router])

  return (
    <main className="flex min-h-screen items-center justify-center bg-pitch text-raw-white">
      <p role="status" className="font-mono text-xs uppercase tracking-label text-muted">
        {t("redirecting")}
      </p>
    </main>
  )
}
