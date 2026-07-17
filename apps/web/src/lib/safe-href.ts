export function safeInternalHref(
  value: string | null | undefined,
  fallback: string | null = null,
) {
  if (!value) return fallback
  if (/[\u0000-\u001f\u007f\\]/.test(value)) return fallback
  const href = value.trim()
  if (!href.startsWith("/")) return fallback

  let decoded = href
  let stable = false
  for (let depth = 0; depth < 8; depth++) {
    if (
      decoded.startsWith("//")
      || /[\u0000-\u001f\u007f\\]/.test(decoded)
    ) {
      return fallback
    }
    try {
      const next = decodeURIComponent(decoded)
      if (next === decoded) {
        stable = true
        break
      }
      decoded = next
    } catch {
      return fallback
    }
  }
  if (!stable) return fallback

  const base = "https://threshold.invalid"
  try {
    if (new URL(href, base).origin !== base) return fallback
  } catch {
    return fallback
  }
  return href
}
