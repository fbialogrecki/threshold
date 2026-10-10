"use client"

import { Megaphone } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { FormAlert, inputClass, Spinner } from "@/components/ui/field"
import { cn } from "@/lib/cn"

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
    <form
      id="event-update-form"
      action={submit}
      className="mt-4 flex flex-col gap-3 rounded-surface border border-border-gray bg-graphite/60 p-4 sm:p-5"
    >
      <div>
        <h3 className="flex items-center gap-2 text-base font-semibold text-raw-white">
          <Megaphone size={18} weight="bold" className="text-acid" aria-hidden />
          {t("formTitle")}
        </h3>
        <p className="mt-1 text-[13px] text-muted">{t("formHint")}</p>
      </div>
      <textarea
        name="body"
        aria-label={t("formLabel")}
        required
        maxLength={2000}
        placeholder={t("formPlaceholder")}
        className={cn(inputClass, "min-h-28")}
      />
      {error ? <FormAlert>{error}</FormAlert> : null}
      <Button type="submit" variant="primary" size="sm" className="self-start" disabled={pending}>
        {pending ? <Spinner /> : null}
        {pending ? t("publishing") : t("publish")}
      </Button>
    </form>
  )
}
