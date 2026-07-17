export function isUnsupportedEndpoint(status: number): boolean {
  return status === 404 || status === 405
}
