export type ReportTarget = { type: "post" | "comment" | "profile"; target: string }
export const REPORT_REASONS = ["spam", "harassment", "hate_speech", "violence", "other"] as const

export function safetyAllowed(viewerId: string | null, targetUserId: string): boolean {
  return Boolean(viewerId && targetUserId && viewerId !== targetUserId)
}

export async function reportContent(target: ReportTarget, reason: string, note: string, request: (input: string, init?: RequestInit) => Promise<Response> = fetch): Promise<void> {
  if (!target.target.trim() || target.target.length > 150 || !reason.trim() || reason.length > 80 || note.length > (target.type === "profile" ? 2000 : 1000)) throw new Error("invalid report")
  const profile = target.type === "profile"
  const response = await request(profile ? "/api/reports" : "/api/social/reports", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ target_type: target.type, [profile ? "target_handle" : "target_id"]: target.target, reason, note: note.trim() || null }),
  })
  if (!response.ok) throw new Error(`report failed: ${response.status}`)
}

export async function setAccountBlocked(username: string, blocked: boolean, request: (input: string, init?: RequestInit) => Promise<Response> = fetch): Promise<void> {
  const response = await request(blocked ? "/api/blocks" : `/api/blocks/${encodeURIComponent(username)}`, blocked
    ? { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ username }) }
    : { method: "DELETE" })
  if (!response.ok) throw new Error(`block failed: ${response.status}`)
}
