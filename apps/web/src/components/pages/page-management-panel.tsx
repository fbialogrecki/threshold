"use client"

import { Buildings, Plus } from "@phosphor-icons/react"
import { useLocale, useTranslations } from "next-intl"
import Link from "next/link"
import { useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import { CITY_OPTIONS, cityLabel } from "@/lib/cities"
import { displayPageType, pageRole } from "@/lib/page-types"

export type ManagedPage = {
  id: string
  slug: string
  display_name: string
  page_type: string
  city?: string | null
  role: string
}

const inputClass = "border border-border-gray bg-pitch p-3 text-sm text-raw-white focus:border-acid focus:outline-none"

export function PageManagementPanel({
  pages,
}: {
  pages: ManagedPage[]
}) {
  const locale = useLocale()
  const t = useTranslations("organizerPages")
  const [pending, startTransition] = useTransition()
  const [error, setError] = useState("")

  function createPage(formData: FormData) {
    setError("")
    startTransition(async () => {
      try {
        const response = await fetch("/api/pages", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            slug: String(formData.get("slug") ?? ""),
            display_name: String(formData.get("display_name") ?? ""),
            page_type: String(formData.get("page_type") ?? "club"),
            city: String(formData.get("city") ?? ""),
            about: String(formData.get("about") ?? ""),
          }),
        })
        if (!response.ok) throw new Error()
        window.location.reload()
      } catch {
        setError(t("createError"))
      }
    })
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_24rem]">
      <section className="border border-border-gray bg-graphite p-4">
        <h2 className="flex items-center gap-2 font-display text-2xl text-raw-white">
          <Buildings size={22} weight="bold" aria-hidden />
          {t("managedTitle")}
        </h2>
        <div className="mt-4 flex flex-col gap-3">
          {pages.length === 0 ? (
            <p className="text-sm text-muted">{t("empty")}</p>
          ) : (
            pages.map((page) => (
              <article key={page.id} className="border border-border-gray bg-pitch p-4">
                <p className="font-mono text-[11px] uppercase tracking-label text-muted">
                  {t(`types.${displayPageType(page.page_type)}`)} · {t(`roles.${pageRole(page.role)}`)}
                </p>
                <h3 className="mt-1 font-display text-xl text-raw-white">{page.display_name}</h3>
                <p className="font-mono text-xs text-dim-white">
                  /{page.slug} {page.city ? `· ${cityLabel(page.city, locale)}` : ""}
                </p>
                <Link
                  href={`/pages/${page.slug}`}
                  className="mt-3 inline-block font-mono text-[11px] uppercase tracking-label text-cyan hover:underline"
                >
                  {t("view")} →
                </Link>
              </article>
            ))
          )}
        </div>
      </section>

      <form action={createPage} className="flex flex-col gap-3 border border-border-gray bg-graphite p-4">
        <h2 className="flex items-center gap-2 font-display text-2xl text-raw-white">
          <Plus size={22} weight="bold" aria-hidden />
          {t("createTitle")}
        </h2>
        <label className="font-mono text-[11px] uppercase tracking-label text-dim-white">
          {t("displayName")}
          <input name="display_name" className={`${inputClass} mt-1 w-full`} required />
        </label>
        <label className="font-mono text-[11px] uppercase tracking-label text-dim-white">
          {t("slug")}
          <input name="slug" placeholder="slug-name" className={`${inputClass} mt-1 w-full font-mono`} required />
        </label>
        <label className="font-mono text-[11px] uppercase tracking-label text-dim-white">
          {t("type")}
          <select name="page_type" className={`${inputClass} mt-1 w-full font-mono`}>
          <option value="club">{t("types.club")}</option>
          <option value="collective">{t("types.collective")}</option>
          <option value="project">{t("types.project")}</option>
          <option value="festival">{t("types.festival")}</option>
        </select>
        </label>
        <label className="font-mono text-[11px] uppercase tracking-label text-dim-white">
          {t("city")}
          <select name="city" className={`${inputClass} mt-1 w-full`}>
            <option value="">{t("chooseCity")}</option>
            {CITY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {cityLabel(option.value, locale)}
              </option>
            ))}
          </select>
        </label>
        <label className="font-mono text-[11px] uppercase tracking-label text-dim-white">
          {t("about")}
          <textarea name="about" className={`${inputClass} mt-1 min-h-28 w-full`} />
        </label>
        {error ? <p role="alert" className="font-mono text-xs uppercase tracking-label text-alert">{error}</p> : null}
        <Button type="submit" disabled={pending}>{pending ? t("creating") : t("create")} →</Button>
      </form>
    </div>
  )
}
