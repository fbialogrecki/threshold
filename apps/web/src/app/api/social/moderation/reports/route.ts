import { proxySocialGet } from "@/lib/social/route-handlers"

export const dynamic = "force-dynamic"

export function GET(request: Request) {
  return proxySocialGet("/v1/moderation/reports", request, { requireUser: true })
}
