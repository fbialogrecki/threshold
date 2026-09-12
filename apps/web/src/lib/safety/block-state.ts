import "server-only"
import { resolveUsersServiceUrl } from "@/lib/auth/users-service-url"

export async function getAccountBlockState(viewerId: string, targetUserId: string, request: (input: string, init?: RequestInit) => Promise<Response> = fetch): Promise<boolean | null> {
  try {
    const token = process.env.THRESHOLD_INTERNAL_TOKEN
    if (!token || !viewerId || !targetUserId) return null
    const base = resolveUsersServiceUrl(process.env.USERS_SERVICE_URL)
    const response = await request(`${base}/internal/v1/users/${encodeURIComponent(viewerId)}/blocks/${encodeURIComponent(targetUserId)}`, {
      headers: { "X-Threshold-Internal-Token": token, accept: "application/json" }, cache: "no-store",
    })
    if (!response.ok) return null
    const body = await response.json()
    return typeof body?.blocked === "boolean" ? body.blocked : null
  } catch { return null }
}
