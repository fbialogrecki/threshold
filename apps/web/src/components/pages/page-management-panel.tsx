"use client"

import { ArrowRight, Buildings, Plus } from "@phosphor-icons/react"
import { useLocale, useTranslations } from "next-intl"
import Link from "next/link"
import { useState, useTransition } from "react"

import { Button } from "@/components/ui/button"
import { Field, FormAlert, inputClass, Spinner } from "@/components/ui/field"
import { CITY_OPTIONS, cityLabel } from "@/lib/cities"
import { cn } from "@/lib/cn"
import { displayPageType, pageRole } from "@/lib/page-types"

export type ManagedPage = {
  id: string
  slug: string
  display_name: string
  page_type: string
  city?: string | null
  role: string
}

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
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
      <section aria-labelledby="managed-pages-title" className="min-w-0">
        <h2 id="managed-pages-title" className="flex items-center gap-2 text-lg font-semibold text-raw-white">
          <Buildings size={20} weight="bold" className="text-muted" aria-hidden />
          {t("managedTitle")}
        </h2>
        <div className="mt-3 flex flex-col gap-3">
          {pages.length === 0 ? (
            <p className="rounded-control border border-dashed border-border-gray px-4 py-3 text-sm text-muted">
              {t("empty")}
            </p>
          ) : (
            pages.map((page) => (
              <article
                key={page.id}
                className="flex flex-wrap items-center justify-between gap-4 rounded-surface border border-border-gray bg-graphite/60 p-4 sm:p-5"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-raised px-2.5 py-0.5 text-xs font-medium text-raw-white">
                      {t(`types.${displayPageType(page.page_type)}`)}
                    </span>
                    <span className="rounded-full border border-border-gray px-2.5 py-0.5 text-xs text-dim-white">
                      {t(`roles.${pageRole(page.role)}`)}
                    </span>
                  </div>
                  <h3 className="mt-2 font-display text-2xl leading-tight break-words text-raw-white">
                    {page.display_name}
                  </h3>
                  <p className="mt-0.5 text-[13px] text-muted">
                    <span className="font-mono">/pages/{page.slug}</span>
                    {page.city ? ` · ${cityLabel(page.city, locale)}` : ""}
                  </p>
                </div>
                <Link
                  href={`/pages/${page.slug}`}
                  className="group inline-flex min-h-10 items-center gap-2 rounded-control px-3 text-sm font-semibold text-acid transition-colors hover:bg-raised"
                >
                  {t("view")}
                  <ArrowRight
                    size={14}
                    className="transition-transform duration-200 ease-out-expo group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </Link>
              </article>
            ))
          )}
        </div>
      </section>

      <form
        onSubmit={(event) => { event.preventDefault(); createPage(new FormData(event.currentTarget)) }}
        aria-labelledby="create-page-title"
        className="flex flex-col gap-5 rounded-surface border border-border-gray bg-graphite/60 p-4 sm:p-6"
      >
        <h2 id="create-page-title" className="flex items-center gap-2 text-lg font-semibold text-raw-white">
          <Plus size={20} weight="bold" className="text-acid" aria-hidden />
          {t("createTitle")}
        </h2>
        <fieldset disabled={pending} className="flex min-w-0 flex-col gap-5">
          <Field htmlFor="new-page-name" label={t("displayName")}>
            <input id="new-page-name" name="display_name" className={inputClass} required />
          </Field>
          <Field htmlFor="new-page-slug" label={t("slug")}>
            <input
              id="new-page-slug"
              name="slug"
              placeholder="slug-name"
              autoCapitalize="none"
              spellCheck={false}
              className={cn(inputClass, "font-mono")}
              required
            />
          </Field>
          <Field htmlFor="new-page-type" label={t("type")}>
            <select id="new-page-type" name="page_type" className={inputClass}>
              <option value="club">{t("types.club")}</option>
              <option value="collective">{t("types.collective")}</option>
              <option value="project">{t("types.project")}</option>
              <option value="festival">{t("types.festival")}</option>
            </select>
          </Field>
          <Field htmlFor="new-page-city" label={t("city")}>
            <select id="new-page-city" name="city" className={inputClass}>
              <option value="">{t("chooseCity")}</option>
              {CITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {cityLabel(option.value, locale)}
                </option>
              ))}
            </select>
          </Field>
          <Field htmlFor="new-page-about" label={t("about")}>
            <textarea id="new-page-about" name="about" className={cn(inputClass, "min-h-28")} />
          </Field>
          {error ? <FormAlert>{error}</FormAlert> : null}
          <Button type="submit" variant="primary" size="lg" disabled={pending}>
            {pending ? <Spinner /> : null}
            {pending ? t("creating") : t("create")}
          </Button>
        </fieldset>
      </form>
    </div>
  )
}
