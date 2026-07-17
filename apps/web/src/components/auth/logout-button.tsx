"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { cn } from "@/lib/cn"

/**
 * Logs out via the product-auth BFF (revokes the session in `users` and clears
 * the bridged cookies), then sends the user back to the public login screen.
 */
export function LogoutButton({ className }: { className?: string }) {
  const router = useRouter()
  const t = useTranslations("auth")
  const [pending, setPending] = useState(false)

  async function onClick() {
    setPending(true)
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "same-origin",
      })
    } catch {
      // Cookies are cleared best-effort; navigate away regardless.
    }
    router.push("/login")
    router.refresh()
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className={cn(
        "font-mono text-[11px] uppercase tracking-label text-muted transition-colors hover:text-orange disabled:opacity-50",
        className,
      )}
    >
      {pending ? "…" : t("logout")}
    </button>
  )
}
