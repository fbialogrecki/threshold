function publicBaseUrl(): string {
  return (process.env.NEXTAUTH_URL ?? "http://127.0.0.1:3000").replace(/\/$/, "")
}

export function mediaDerivativeUrl(assetId: string, derivative: string): string {
  return `/api/media/assets/assets/${encodeURIComponent(assetId)}/${derivative}.webp`
}

export function absoluteMediaDerivativeUrl(assetId: string, derivative: string): string {
  return `${publicBaseUrl()}${mediaDerivativeUrl(assetId, derivative)}`
}
