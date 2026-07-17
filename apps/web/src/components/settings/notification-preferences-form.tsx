"use client"

import { useTranslations } from "next-intl"
import { useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import {
  notificationPreferenceLoad,
  type NotificationPreferenceLoad,
  type NotificationPreferences,
} from "@/lib/notification-preferences"

export function NotificationPreferencesForm({
  initial,
}: {
  initial: NotificationPreferenceLoad
}) {
  const t = useTranslations("settings.notifications")
  const initialData = initial.status === "ready" ? initial.data : null
  const [preferences, setPreferences] = useState<NotificationPreferences | null>(initialData)
  const [saved, setSaved] = useState<NotificationPreferences | null>(initialData)
  const [status, setStatus] = useState(initialData ? "" : t("loadError"))
  const [pending, startTransition] = useTransition()
  const dirty = preferences !== null && saved !== null
    && JSON.stringify(preferences) !== JSON.stringify(saved)

  function retry() {
    setStatus("")
    startTransition(async () => {
      try {
        const response = await fetch("/api/notifications/preferences")
        const body: unknown = await response.json().catch(() => null)
        const loaded = notificationPreferenceLoad(response.status, body)
        if (loaded.status !== "ready") throw new Error()
        setPreferences(loaded.data)
        setSaved(loaded.data)
      } catch {
        setStatus(t("loadError"))
      }
    })
  }

  function save() {
    if (!preferences) return
    setStatus("")
    startTransition(async () => {
      try {
        const response = await fetch("/api/notifications/preferences", {
          method: "PUT",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(preferences),
        })
        const body: unknown = await response.json().catch(() => null)
        const loaded = notificationPreferenceLoad(response.status, body)
        if (loaded.status !== "ready") throw new Error()
        setPreferences(loaded.data)
        setSaved(loaded.data)
        setStatus(t("saved"))
      } catch {
        setStatus(t("saveError"))
      }
    })
  }

  if (!preferences) {
    return (
      <div
        aria-busy={pending}
        className="flex flex-wrap items-center justify-between gap-3 border border-error/40 bg-pitch p-4"
      >
        <p role="alert" className="text-sm text-error">{status || t("loadError")}</p>
        <Button type="button" variant="secondary" disabled={pending} onClick={retry}>
          {pending ? t("retrying") : t("retry")}
        </Button>
      </div>
    )
  }

  const fields = [
    "mentions_enabled",
    "engagement_enabled",
    "event_updates_enabled",
    "page_updates_enabled",
  ] as const

  return (
    <fieldset
      disabled={pending}
      aria-busy={pending}
      className="flex min-w-0 flex-col gap-4 disabled:opacity-70"
    >
      {fields.map((field) => (
        <label
          key={field}
          className="flex cursor-pointer items-start justify-between gap-4 border border-border-gray bg-pitch p-4"
        >
          <span>
            <span className="block font-mono text-[11px] uppercase tracking-label text-raw-white">
              {t(`${field}.title`)}
            </span>
            <span className="mt-1 block text-sm leading-6 text-muted">
              {t(`${field}.body`)}
            </span>
          </span>
          <input
            type="checkbox"
            checked={preferences[field]}
            onChange={(event) => setPreferences((current) =>
              current ? { ...current, [field]: event.target.checked } : current,
            )}
            className="mt-1 h-5 w-5 accent-acid"
          />
        </label>
      ))}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border-gray pt-4">
        <p aria-live="polite" className="text-sm text-muted">
          {pending ? t("saving") : status}
        </p>
        <Button type="button" variant="primary" disabled={!dirty || pending} onClick={save}>
          {pending ? t("saving") : t("save")}
        </Button>
      </div>
    </fieldset>
  )
}
