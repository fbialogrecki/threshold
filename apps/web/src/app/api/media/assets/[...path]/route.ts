import { fetchMediaAsset, MediaServiceConfigurationError } from "@/lib/media/client"

export const dynamic = "force-dynamic"

type RouteContext = { params: Promise<{ path: string[] }> }

function isSafeMediaPath(path: string[]) {
  return path.every((segment) => {
    try {
      const decoded = decodeURIComponent(segment)
      return decoded !== "." && decoded !== ".." && !decoded.includes("/")
    } catch {
      return false
    }
  })
}

export async function GET(_request: Request, { params }: RouteContext) {
  const { path } = await params
  if (!isSafeMediaPath(path)) {
    return Response.json(
      { error: "asset not found" },
      { status: 404, headers: { "cache-control": "no-store" } },
    )
  }
  const assetPath = path.map(encodeURIComponent).join("/")
  try {
    return await fetchMediaAsset(assetPath)
  } catch (error) {
    if (error instanceof MediaServiceConfigurationError) {
      return Response.json(
        { error: "media service URL is not configured" },
        { status: 503, headers: { "cache-control": "no-store" } },
      )
    }
    throw error
  }
}
