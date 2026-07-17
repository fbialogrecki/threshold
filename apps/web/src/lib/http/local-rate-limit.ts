export type RateLimitPolicy = {
  limit: number
  windowMs: number
}

type RateLimitResult =
  | { allowed: true }
  | { allowed: false; retryAfterSeconds: number }

type Window = { count: number; resetAt: number }

/**
 * Bounded, single-instance fixed-window limiter. It intentionally has no claim
 * to distributed enforcement: each Next process has an independent map and a
 * restart clears it. Keep service/edge limits enabled for multi-replica/public
 * deployments.
 */
export class LocalFixedWindowRateLimiter {
  private readonly windows = new Map<string, Window>()
  private readonly maxEntries: number
  private readonly now: () => number

  constructor(options: { maxEntries: number; now?: () => number }) {
    if (!Number.isInteger(options.maxEntries) || options.maxEntries < 1) {
      throw new Error("maxEntries must be a positive integer")
    }
    this.maxEntries = options.maxEntries
    this.now = options.now ?? Date.now
  }

  get size(): number {
    return this.windows.size
  }

  consume(key: string, policy: RateLimitPolicy): RateLimitResult {
    const now = this.now()
    const current = this.windows.get(key)
    if (current && current.resetAt > now) {
      if (current.count >= policy.limit) {
        return {
          allowed: false,
          retryAfterSeconds: Math.max(1, Math.ceil((current.resetAt - now) / 1_000)),
        }
      }
      current.count += 1
      return { allowed: true }
    }

    if (current) this.windows.delete(key)
    this.pruneExpired(now)
    while (this.windows.size >= this.maxEntries) {
      const oldest = this.windows.keys().next().value as string | undefined
      if (oldest === undefined) break
      this.windows.delete(oldest)
    }
    this.windows.set(key, { count: 1, resetAt: now + policy.windowMs })
    return { allowed: true }
  }

  private pruneExpired(now: number): void {
    for (const [key, window] of this.windows) {
      if (window.resetAt <= now) this.windows.delete(key)
    }
  }
}

export const LOCAL_ABUSE_POLICIES = {
  login: { limit: 10, windowMs: 15 * 60_000 },
  register: { limit: 5, windowMs: 60 * 60_000 },
  passwordResetRequest: { limit: 5, windowMs: 60 * 60_000 },
  passwordResetConfirm: { limit: 10, windowMs: 15 * 60_000 },
  emailVerificationRequest: { limit: 5, windowMs: 60 * 60_000 },
  emailVerificationConfirm: { limit: 10, windowMs: 15 * 60_000 },
  report: { limit: 20, windowMs: 60 * 60_000 },
} as const satisfies Record<string, RateLimitPolicy>

const limiter = new LocalFixedWindowRateLimiter({ maxEntries: 10_000 })

export function requestClientKey(request: Request): string {
  const candidate = request.headers.get("x-forwarded-for")?.split(",", 1)[0]?.trim()
    || request.headers.get("x-real-ip")?.trim()
    || "unknown"
  return /^[0-9a-f:.]{1,64}$/i.test(candidate) ? candidate : "unknown"
}

export function rateLimitResponse(retryAfterSeconds: number): Response {
  return Response.json(
    { error: "too many attempts" },
    {
      status: 429,
      headers: { "Retry-After": String(Math.max(1, Math.ceil(retryAfterSeconds))) },
    },
  )
}

export function enforceLocalRateLimit(
  request: Request,
  scope: string,
  policy: RateLimitPolicy,
): Response | null {
  const result = limiter.consume(`${scope}:${requestClientKey(request)}`, policy)
  return result.allowed ? null : rateLimitResponse(result.retryAfterSeconds)
}
