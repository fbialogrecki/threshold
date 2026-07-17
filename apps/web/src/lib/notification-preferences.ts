export type NotificationPreferences = {
  mentions_enabled: boolean
  engagement_enabled: boolean
  event_updates_enabled: boolean
  page_updates_enabled: boolean
}

export function notificationPreferencePayload(value: unknown): Partial<NotificationPreferences> {
  if (!value || typeof value !== "object") return {}
  const source = value as Record<string, unknown>
  const payload: Partial<NotificationPreferences> = {}
  for (const key of [
    "mentions_enabled",
    "engagement_enabled",
    "event_updates_enabled",
    "page_updates_enabled",
  ] as const) {
    if (typeof source[key] === "boolean") payload[key] = source[key]
  }
  return payload
}

export function notificationPreferences(value: unknown): NotificationPreferences | null {
  const payload = notificationPreferencePayload(value)
  return Object.keys(payload).length === 4 ? payload as NotificationPreferences : null
}

export type NotificationPreferenceLoad =
  | { status: "ready"; data: NotificationPreferences }
  | { status: "error" }

export function notificationPreferenceLoad(
  status: number | null,
  value: unknown,
): NotificationPreferenceLoad {
  const data = status === 200 ? notificationPreferences(value) : null
  return data ? { status: "ready", data } : { status: "error" }
}
