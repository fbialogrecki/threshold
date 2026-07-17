"use client"

import { Megaphone } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { Button } from "@/components/ui/button"

export function EventUpdateForm({ slug }: { slug: string }) {
  const t = useTranslations("eventDetail.updates")
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")

  async function submit(formData: FormData) {
    setError("")
    setPending(true)
    try {
      const response = await fetch(`/api/events/${encodeURIComponent(slug)}/updates`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ body: String(formData.get("body") ?? "") }),
      })
      if (!response.ok) {
        setError(response.status === 403 ? t("forbidden") : t("error"))
        return
      }
      const form = document.getElementById("event-update-form") as HTMLFormElement | null
      form?.reset()
      router.refresh()
    } catch {
      setError(t("networkError"))
    } finally {
      setPending(false)
    }
  }

  return (
    <form id="event-update-form" action={submit} className="mt-6 border border-border-gray bg-graphite p-4">
      <h2 className="flex items-center gap-2 font-display text-2xl text-raw-white">
        <Megaphone size={19} weight="bold" aria-hidden />
        {t("formTitle")}
      </h2>
      <p className="mt-1 font-mono text-[11px] uppercase tracking-label text-muted">
        {t("formHint")}
      </p>
      <textarea
        name="body"
        aria-label={t("formLabel")}
        required
        maxLength={2000}
        placeholder={t("formPlaceholder")}
        className="mt-4 min-h-28 w-full border border-border-gray bg-pitch p-3 text-sm text-raw-white"
      />
      {error ? <p className="mt-2 font-mono text-xs uppercase tracking-label text-alert">{error}</p> : null}
      <Button type="submit" className="mt-3" disabled={pending}>
        {pending ? t("publishing") : t("publish")}
      </Button>
    </form>
  )
}
