import { proxySocialMutation } from "@/lib/social/route-handlers"
import { LOCAL_ABUSE_POLICIES } from "@/lib/http/local-rate-limit"

export const dynamic = "force-dynamic"

export function POST(request: Request) {
  return proxySocialMutation(request, "/v1/reports", "POST", {
    localRateLimit: { scope: "social-report", policy: LOCAL_ABUSE_POLICIES.report },
  })
}
