import { proxyEventsGet, proxyEventsMutation } from "@/lib/events/client"

export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  return proxyEventsGet("/v1/events", request)
}

export async function POST(request: Request) {
  return proxyEventsMutation(request, "/v1/events", "POST")
}
