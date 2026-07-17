export function mediaCacheControl(status: number): string {
  return status >= 200 && status < 300
    ? "public, max-age=31536000, immutable"
    : "no-store"
}
