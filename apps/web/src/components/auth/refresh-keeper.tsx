"use client"

import { useEffect } from "react"

/**
 * Keeps the short-lived product-auth session cookie fresh while the app is
 * open. Server Components cannot rotate cookies, so this client component
 * proactively hits the same-origin refresh BFF on an interval and whenever the
 * tab regains focus. Mounted once inside the authenticated app shell.
 */
const REFRESH_INTERVAL_MS = 10 * 60 * 1000

export function RefreshKeeper() {
  useEffect(() => {
    let cancelled = false

    async function refresh() {
      if (cancelled) return
      try {
        await fetch("/api/auth/refresh", {
          method: "POST",
          headers: { "content-type": "application/json" },
          // Same-origin so the browser sends the HttpOnly refresh cookie.
          credentials: "same-origin",
        })
      } catch {
        // Network hiccup: the next interval / focus tick retries.
      }
    }

    const interval = setInterval(refresh, REFRESH_INTERVAL_MS)

    function onVisible() {
      if (document.visibilityState === "visible") void refresh()
    }
    document.addEventListener("visibilitychange", onVisible)

    return () => {
      cancelled = true
      clearInterval(interval)
      document.removeEventListener("visibilitychange", onVisible)
    }
  }, [])

  return null
}
