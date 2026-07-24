"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState, type ReactNode } from "react"

import { cn } from "@/lib/cn"

/**
 * Logs out via the product-auth BFF (revokes the session in `users` and clears
 * the bridged cookies), then sends the user back to the public login screen.
 *
 * Pass children to render a glyph instead of the word; the label then moves to
 * `aria-label` so the control stays announceable.
 */
export function LogoutButton({
  className,
  children,
}: {
  className?: string
  children?: ReactNode
}) {
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
      aria-label={children ? t("logout") : undefined}
      className={cn(
        children
          ? "transition-colors disabled:opacity-50"
          : "font-mono text-[11px] uppercase tracking-label text-muted transition-colors hover:text-orange disabled:opacity-50",
        className,
      )}
    >
      {children ?? (pending ? "…" : t("logout"))}
    </button>
  )
}
