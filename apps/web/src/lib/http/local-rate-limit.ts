import { isIP } from "node:net"

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
    if (this.windows.size >= this.maxEntries) {
      let earliestResetAt = Number.POSITIVE_INFINITY
      for (const window of this.windows.values()) {
        earliestResetAt = Math.min(earliestResetAt, window.resetAt)
      }
      return {
        allowed: false,
        retryAfterSeconds: Math.max(1, Math.ceil((earliestResetAt - now) / 1_000)),
      }
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

const MAX_TRUSTED_PROXY_DEPTH = 10
const MAX_FORWARDED_HEADER_LENGTH = 1_024

export function resolveTrustedProxyDepth(value: string | undefined): number | undefined {
  if (!value || !/^\d+$/.test(value)) return undefined
  const depth = Number(value)
  return Number.isInteger(depth) && depth >= 1 && depth <= MAX_TRUSTED_PROXY_DEPTH
    ? depth
    : undefined
}

export function requestClientKey(request: Request, trustedProxyDepth?: number): string {
  if (!Number.isInteger(trustedProxyDepth)
    || trustedProxyDepth === undefined
    || trustedProxyDepth < 1
    || trustedProxyDepth > MAX_TRUSTED_PROXY_DEPTH) return "unknown"

  const forwarded = request.headers.get("x-forwarded-for")
  if (!forwarded || forwarded.length > MAX_FORWARDED_HEADER_LENGTH) return "unknown"
  const chain = forwarded.split(",")
  // Select from the proxy-controlled right edge, never the client-controlled
  // left edge. Correctness depends on configuring the actual trusted depth.
  const candidate = chain.at(-trustedProxyDepth)?.trim() ?? "unknown"
  return isIP(candidate) ? candidate : "unknown"
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
  const result = limiter.consume(
    `${scope}:${requestClientKey(request, resolveTrustedProxyDepth(process.env.WEB_TRUSTED_PROXY_DEPTH))}`,
    policy,
  )
  return result.allowed ? null : rateLimitResponse(result.retryAfterSeconds)
}
