export type SafeFailureMetadata = {
  service: "users" | "social" | "events" | "media"
  operation: string
  kind: "configuration" | "unavailable" | "invalid_response"
}

type LogSink = (entry: Record<string, string>) => void

/**
 * Deliberately ignores the caught value. Error messages/stacks can contain
 * credentials, email addresses, bearer tokens, URLs, or raw upstream bodies.
 */
export function safeLogFailure(
  metadata: SafeFailureMetadata,
  error: unknown,
  sink: LogSink = (entry) => console.error(entry),
): void {
  void error
  sink({ event: "upstream_request_failed", ...metadata })
}
