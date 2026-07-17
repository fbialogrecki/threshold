/**
 * Active-state matching for routes outside /app: post permalinks highlight
 * Feed, event details highlight Events, and groups stay under /groups.
 */
export function isNavActive(href: string, pathname: string): boolean {
  switch (href) {
    case "/app":
      return pathname === "/app" || pathname === "/posts" || pathname.startsWith("/posts/")
    case "/app/events":
      return (
        pathname === "/app/events" ||
        pathname.startsWith("/app/events/") ||
        pathname === "/events" ||
        pathname.startsWith("/events/")
      )
    default:
      return pathname === href || pathname.startsWith(`${href}/`)
  }
}
