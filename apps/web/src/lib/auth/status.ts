export type SessionStatus =
  | "authenticated"
  | "anonymous"
  | "invalid"
  | "unavailable"

export function sessionStatus(
  hasSessionCookie: boolean,
  upstreamStatus?: number,
): SessionStatus {
  if (!hasSessionCookie) return "anonymous"
  if (upstreamStatus === 401) return "invalid"
  return upstreamStatus === 200 ? "authenticated" : "unavailable"
}

export function resetRequestStatus(upstreamStatus: number | null): 200 | 429 | 503 {
  if (upstreamStatus === null || upstreamStatus === 200) return 200
  return upstreamStatus === 429 ? 429 : 503
}

export function loginResponseStatus(upstreamStatus: number): 200 | 401 | 429 | 503 {
  if (upstreamStatus === 200 || upstreamStatus === 401 || upstreamStatus === 429) {
    return upstreamStatus
  }
  return 503
}

export type MutationErrorKey =
  | "forbidden"
  | "notFound"
  | "rateLimited"
  | "serviceUnavailable"

export function mutationErrorKey(status: number): MutationErrorKey {
  if (status === 403) return "forbidden"
  if (status === 404) return "notFound"
  if (status === 429) return "rateLimited"
  return "serviceUnavailable"
}
