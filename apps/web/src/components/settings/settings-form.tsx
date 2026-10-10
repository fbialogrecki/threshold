"use client"

import { Camera, Plus, Trash, WarningOctagon, X } from "@phosphor-icons/react"
import { useLocale, useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useEffect, useState, useTransition } from "react"

import { LocaleSwitcher } from "@/components/i18n/locale-switcher"
import { AvatarCropModal } from "@/components/media/avatar-crop-modal"
import { NotificationPreferencesForm } from "@/components/settings/notification-preferences-form"
import { Avatar } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { inputClass, Spinner } from "@/components/ui/field"
import { CITY_OPTIONS, cityLabel } from "@/lib/cities"
import { cn } from "@/lib/cn"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import type { NotificationPreferenceLoad } from "@/lib/notification-preferences"
import { buildProfilePayload } from "@/lib/settings/profile"

type Status = { kind: "idle" | "ok" | "error"; message?: string }

export type SettingsInitial = {
  username: string
  displayName: string
  bio: string
  city: string
  avatarMediaAssetId: string
  isArtist: boolean
  role: string
  location: string
  links: { label: string; url: string }[]
}

const labelClass = "text-sm font-medium text-raw-white"
const hintClass = "text-[13px] leading-5 text-muted"

const SECTIONS = [
  "profile",
  "artist",
  "notifications",
  "language",
  "account",
] as const

/* ---------------------------------------------------------------- helpers */

function Field({
  id,
  label,
  hint,
  counter,
  children,
}: {
  id: string
  label: string
  hint?: string
  counter?: { value: number; max: number }
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3">
        <label className={labelClass} htmlFor={id}>
          {label}
        </label>
        {counter ? (
          <span
            className={cn(
              "font-mono text-xs tabular-nums",
              counter.value > counter.max * 0.9 ? "text-orange" : "text-muted",
            )}
          >
            {counter.value}/{counter.max}
          </span>
        ) : null}
      </div>
      {children}
      {hint ? <p className={hintClass}>{hint}</p> : null}
    </div>
  )
}

/**
 * Section footer with explicit-save best practices: the save button is only
 * enabled when something changed, dirty state is announced, and a Discard
 * action restores the last saved values.
 */
function SaveRow({
  dirty,
  pending,
  status,
  saveLabel,
  unsavedLabel,
  discardLabel,
  savingLabel,
  onDiscard,
}: {
  dirty: boolean
  pending: boolean
  status: Status
  saveLabel: string
  unsavedLabel: string
  discardLabel: string
  savingLabel: string
  onDiscard: () => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border-gray pt-4">
      <p
        aria-live="polite"
        className={cn(
          "flex items-center gap-2 text-sm",
          status.kind === "ok" && !dirty
            ? "text-acid"
            : status.kind === "error"
              ? "text-orange"
              : dirty
                ? "text-raw-white"
                : "text-muted",
        )}
      >
        {dirty && status.kind !== "error" ? (
          <span aria-hidden className="size-2 rounded-full bg-orange" />
        ) : null}
        {status.kind === "error"
          ? status.message
          : dirty
            ? unsavedLabel
            : status.kind === "ok"
              ? status.message
              : " "}
      </p>
      <div className="flex items-center gap-2">
        {dirty ? (
          <Button type="button" variant="ghost" size="sm" onClick={onDiscard} disabled={pending}>
            {discardLabel}
          </Button>
        ) : null}
        <Button type="submit" variant="primary" size="sm" disabled={!dirty || pending}>
          {pending ? <Spinner /> : null}
          {pending ? savingLabel : saveLabel}
        </Button>
      </div>
    </div>
  )
}

function SectionCard({
  id,
  title,
  description,
  tone = "default",
  children,
}: {
  id: string
  title: string
  description: string
  tone?: "default" | "danger"
  children: React.ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className={cn(
        "scroll-mt-24 rounded-surface border",
        tone === "danger" ? "border-error/50 bg-error/5" : "border-border-gray bg-graphite/60",
      )}
    >
      <header
        className={cn(
          "border-b px-5 py-4 sm:px-6",
          tone === "danger" ? "border-error/30" : "border-border-gray",
        )}
      >
        <h2
          id={`${id}-heading`}
          className={cn(
            "flex items-center gap-2 text-lg font-semibold",
            tone === "danger" ? "text-error" : "text-raw-white",
          )}
        >
          {tone === "danger" ? <WarningOctagon size={20} weight="bold" aria-hidden /> : null}
          {title}
        </h2>
        <p className="mt-1 text-sm leading-6 text-dim-white">{description}</p>
      </header>
      <div className="px-5 py-5 sm:px-6">{children}</div>
    </section>
  )
}

/* -------------------------------------------------------------- scrollspy */

function SettingsNav() {
  const t = useTranslations("settings")
  const [active, setActive] = useState<string>(SECTIONS[0])

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        // Highlight the topmost section currently in the reading band.
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]) setActive(visible[0].target.id)
      },
      { rootMargin: "-20% 0px -65% 0px" },
    )
    for (const section of SECTIONS) {
      const node = document.getElementById(section)
      if (node) observer.observe(node)
    }
    return () => observer.disconnect()
  }, [])

  return (
    <nav aria-label={t("sectionNavigation")} className="min-w-0 lg:sticky lg:top-8">
      {/* Scrolls inside itself on phones, so five translated labels never widen the page. */}
      <ul className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 lg:mx-0 lg:flex-col lg:overflow-visible lg:px-0">
        {SECTIONS.map((section) => (
          <li key={section} className="shrink-0">
            <a
              href={`#${section}`}
              aria-current={active === section ? "true" : undefined}
              className={cn(
                "flex min-h-10 items-center rounded-control px-3.5 text-sm font-medium transition-colors",
                active === section
                  ? section === "account"
                    ? "bg-error/10 text-error"
                    : "bg-acid/10 text-acid"
                  : section === "account"
                    ? "text-dim-white hover:bg-raised hover:text-error"
                    : "text-dim-white hover:bg-raised hover:text-raw-white",
              )}
            >
              {t(`sections.${section}`)}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/* ------------------------------------------------------------------ form */

export function SettingsForm({
  initial,
  notificationPreferences,
}: {
  initial: SettingsInitial
  notificationPreferences: NotificationPreferenceLoad
}) {
  const router = useRouter()
  const locale = useLocale()
  const t = useTranslations("settings")

  // Saved snapshots drive dirty detection; they advance on successful save.
  const [savedProfile, setSavedProfile] = useState({
    displayName: initial.displayName,
    username: initial.username,
    bio: initial.bio,
    city: initial.city,
    avatarMediaAssetId: initial.avatarMediaAssetId,
  })
  const [displayName, setDisplayName] = useState(initial.displayName)
  const [username, setUsername] = useState(initial.username)
  const [bio, setBio] = useState(initial.bio)
  const [city, setCity] = useState(initial.city)
  const [avatarMediaAssetId, setAvatarMediaAssetId] = useState(initial.avatarMediaAssetId)
  const [avatarUploadPending, startAvatarUpload] = useTransition()
  const [cropFile, setCropFile] = useState<File | null>(null)
  const [profileStatus, setProfileStatus] = useState<Status>({ kind: "idle" })
  const [profilePending, startProfile] = useTransition()

  const profileDirty =
    displayName !== savedProfile.displayName ||
    username !== savedProfile.username ||
    bio !== savedProfile.bio ||
    city !== savedProfile.city ||
    avatarMediaAssetId !== savedProfile.avatarMediaAssetId

  const [savedArtist, setSavedArtist] = useState({
    role: initial.role,
    location: initial.location,
    links: initial.links,
  })
  const [artistOpen, setArtistOpen] = useState(initial.isArtist)
  const [role, setRole] = useState(initial.role)
  const [location, setLocation] = useState(initial.location)
  const [links, setLinks] = useState<{ label: string; url: string }[]>(
    initial.links.length > 0 ? initial.links : [{ label: "", url: "" }],
  )
  const [artistStatus, setArtistStatus] = useState<Status>({ kind: "idle" })
  const [artistPending, startArtist] = useTransition()

  const artistDirty =
    role !== savedArtist.role ||
    location !== savedArtist.location ||
    JSON.stringify(links.filter((l) => l.label || l.url)) !==
      JSON.stringify(savedArtist.links)

  const [dangerOpen, setDangerOpen] = useState(false)
  const [confirm, setConfirm] = useState("")
  const [deleteStatus, setDeleteStatus] = useState<Status>({ kind: "idle" })
  const [deletePending, startDelete] = useTransition()

  function saveProfile(event: React.FormEvent) {
    event.preventDefault()
    setProfileStatus({ kind: "idle" })
    startProfile(async () => {
      const payload = buildProfilePayload({
        displayName,
        username,
        bio,
        city,
        avatarMediaAssetId,
      }, savedProfile.avatarMediaAssetId)
      try {
        const response = await fetch("/api/me/profile", {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        })
        if (response.ok) {
          setSavedProfile({
            displayName: payload.display_name,
            username: payload.username,
            bio: payload.bio,
            city: payload.city,
            avatarMediaAssetId: avatarMediaAssetId,
          })
          setProfileStatus({ kind: "ok", message: t("status.saved") })
          router.refresh()
        } else if (response.status === 409) {
          setProfileStatus({ kind: "error", message: t("errors.usernameTaken") })
        } else {
          setProfileStatus({ kind: "error", message: t("errors.profileSave") })
        }
      } catch {
        setProfileStatus({ kind: "error", message: t("errors.profileSave") })
      }
    })
  }

  function discardProfile() {
    setDisplayName(savedProfile.displayName)
    setUsername(savedProfile.username)
    setBio(savedProfile.bio)
    setCity(savedProfile.city)
    setAvatarMediaAssetId(savedProfile.avatarMediaAssetId)
    setProfileStatus({ kind: "idle" })
  }

  function uploadAvatar(blob: Blob) {
    setCropFile(null)
    const formData = new FormData()
    formData.set("context", "user_avatar")
    formData.set("file", blob, "avatar.webp")
    setProfileStatus({ kind: "idle" })
    startAvatarUpload(async () => {
      try {
        const response = await fetch("/api/media/assets", { method: "POST", body: formData })
        if (!response.ok) throw new Error()
        const asset = (await response.json()) as { id?: string }
        if (typeof asset.id !== "string") throw new Error()
        setAvatarMediaAssetId(asset.id)
        setProfileStatus({ kind: "ok", message: t("status.avatarUploaded") })
      } catch {
        setProfileStatus({ kind: "error", message: t("errors.avatarUpload") })
      }
    })
  }

  function saveArtist(event: React.FormEvent) {
    event.preventDefault()
    setArtistStatus({ kind: "idle" })
    const cleanLinks = links
      .map((l) => ({ label: l.label.trim(), url: l.url.trim() }))
      .filter((l) => l.label && /^https?:\/\//.test(l.url))
    startArtist(async () => {
      try {
        const response = await fetch("/api/me/artist", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            role: role.trim(),
            location: location.trim(),
            links: cleanLinks,
          }),
        })
        if (!response.ok) throw new Error()
        setSavedArtist({ role: role.trim(), location: location.trim(), links: cleanLinks })
        setArtistStatus({ kind: "ok", message: t("status.saved") })
        router.refresh()
      } catch {
        setArtistStatus({ kind: "error", message: t("errors.artistSave") })
      }
    })
  }

  function discardArtist() {
    setRole(savedArtist.role)
    setLocation(savedArtist.location)
    setLinks(savedArtist.links.length > 0 ? savedArtist.links : [{ label: "", url: "" }])
    setArtistStatus({ kind: "idle" })
  }

  function deleteAccount() {
    setDeleteStatus({ kind: "idle" })
    startDelete(async () => {
      try {
        const response = await fetch("/api/me", { method: "DELETE" })
        if (!response.ok) throw new Error()
        router.push("/")
        router.refresh()
      } catch {
        setDeleteStatus({ kind: "error", message: t("errors.accountDelete") })
      }
    })
  }

  function updateLink(index: number, key: "label" | "url", value: string) {
    setLinks((current) =>
      current.map((link, i) => (i === index ? { ...link, [key]: value } : link)),
    )
  }

  function removeLink(index: number) {
    setLinks((current) =>
      current.length === 1
        ? [{ label: "", url: "" }]
        : current.filter((_, i) => i !== index),
    )
  }

  return (
    <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[11rem_minmax(0,1fr)] lg:items-start lg:gap-10">
      <SettingsNav />

      <div className="flex min-w-0 flex-col gap-6">
        {/* ------------------------------------------------------ profile */}
        <SectionCard
          id="profile"
          title={t("profile.title")}
          description={t("profile.description")}
        >
          <form onSubmit={saveProfile} className="flex flex-col gap-5">
            {/* Live identity preview: feedback before committing changes. */}
            <div className="flex flex-wrap items-center gap-4 rounded-control bg-pitch/60 p-4">
              <Avatar
                name={username || "?"}
                imageUrl={avatarMediaAssetId ? mediaDerivativeUrl(avatarMediaAssetId, "avatar_256") : null}
                size="lg"
                className={avatarUploadPending ? "animate-pulse" : undefined}
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xl font-semibold text-raw-white">
                  {username || t("profile.previewUsername")}
                </p>
                <p className="mt-0.5 truncate font-mono text-xs text-muted">/u/{username || "…"}</p>
              </div>
              <label className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-control border border-border-gray px-3.5 text-sm font-medium text-raw-white transition-colors hover:border-acid hover:text-acid has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-acid has-[:disabled]:cursor-wait has-[:disabled]:opacity-60">
                {avatarUploadPending ? <Spinner /> : <Camera size={18} aria-hidden />}
                {avatarUploadPending ? t("profile.uploading") : t("profile.uploadAvatar")}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  className="sr-only"
                  disabled={avatarUploadPending}
                  onChange={(event) => {
                    const f = event.currentTarget.files?.[0]
                    if (f) setCropFile(f)
                    event.currentTarget.value = ""
                  }}
                />
              </label>
            </div>

            {/*
              The username is the only public name now, so the separate display
              name field is gone. Its value stays in state and in the payload
              until the field is retired from the users service.
            */}
            <Field
              id="set-username"
              label={t("profile.username")}
              hint={t("profile.publicAddress", { username: username || "…" })}
            >
              <input
                id="set-username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={inputClass}
                maxLength={30}
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
              />
            </Field>

            <Field
              id="set-bio"
              label={t("profile.bio")}
              hint={t("profile.bioHint")}
              counter={{ value: bio.length, max: 2000 }}
            >
              <textarea
                id="set-bio"
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={4}
                maxLength={2000}
                placeholder={t("profile.bioPlaceholder")}
                className={cn(inputClass, "resize-y")}
              />
            </Field>

            <Field
              id="set-city"
              label={t("profile.city")}
              hint={t("profile.cityHint")}
            >
              <select
                id="set-city"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className={inputClass}
              >
                <option value="">{t("profile.chooseCity")}</option>
                {CITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {cityLabel(option.value, locale)}
                  </option>
                ))}
              </select>
            </Field>

            <SaveRow
              dirty={profileDirty}
              pending={profilePending}
              status={profileStatus}
              saveLabel={t("profile.save")}
              unsavedLabel={t("status.unsaved")}
              discardLabel={t("actions.discard")}
              savingLabel={t("actions.saving")}
              onDiscard={discardProfile}
            />
          </form>
        </SectionCard>

        {/* ------------------------------------------------------- artist */}
        <SectionCard
          id="artist"
          title={t(initial.isArtist ? "artist.title" : "artist.createTitle")}
          description={
            initial.isArtist
              ? t("artist.description")
              : t("artist.createDescription")
          }
        >
          {!artistOpen ? (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-prose text-[15px] leading-7 text-dim-white">
                {t("artist.intro")}
              </p>
              <Button type="button" variant="secondary" size="sm" onClick={() => setArtistOpen(true)}>
                {t("artist.setup")}
              </Button>
            </div>
          ) : (
            <form onSubmit={saveArtist} className="flex flex-col gap-5">
              <div className="grid gap-5 sm:grid-cols-2">
                <Field id="set-role" label={t("artist.role")} hint={t("artist.roleHint")}>
                  <input
                    id="set-role"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    placeholder={t("artist.rolePlaceholder")}
                    className={inputClass}
                    maxLength={120}
                  />
                </Field>
                <Field id="set-location" label={t("artist.location")}>
                  <input
                    id="set-location"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder={t("artist.locationPlaceholder")}
                    className={inputClass}
                    maxLength={120}
                  />
                </Field>
              </div>

              <fieldset className="flex min-w-0 flex-col gap-3">
                <legend className={labelClass}>{t("artist.links")}</legend>
                <p className={hintClass}>{t("artist.linksHint")}</p>
                {links.map((link, index) => (
                  <div
                    key={index}
                    className="grid grid-cols-[minmax(0,1fr)_auto] gap-2 sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)_auto]"
                  >
                    <input
                      aria-label={t("artist.linkLabel", { number: index + 1 })}
                      value={link.label}
                      onChange={(e) => updateLink(index, "label", e.target.value)}
                      placeholder={t("artist.linkPlaceholder")}
                      className={cn(inputClass, "col-span-2 sm:col-span-1")}
                    />
                    <input
                      aria-label={t("artist.linkUrl", { number: index + 1 })}
                      value={link.url}
                      onChange={(e) => updateLink(index, "url", e.target.value)}
                      placeholder="https://…"
                      inputMode="url"
                      autoCapitalize="none"
                      spellCheck={false}
                      className={inputClass}
                    />
                    <button
                      type="button"
                      aria-label={t("artist.removeLink", { number: index + 1 })}
                      onClick={() => removeLink(index)}
                      className="grid size-12 shrink-0 place-items-center rounded-control border border-border-gray text-muted transition-colors hover:border-status-neutral-border hover:text-raw-white"
                    >
                      <X size={16} weight="bold" aria-hidden />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setLinks((c) => [...c, { label: "", url: "" }])}
                  className="inline-flex min-h-10 w-fit items-center gap-2 rounded-control px-3 text-sm font-medium text-dim-white transition-colors hover:bg-raised hover:text-acid"
                >
                  <Plus size={16} weight="bold" aria-hidden />
                  {t("artist.addLink")}
                </button>
              </fieldset>

              <SaveRow
                dirty={artistDirty}
                pending={artistPending}
                status={artistStatus}
                saveLabel={t(initial.isArtist ? "artist.save" : "artist.create")}
                unsavedLabel={t("status.unsaved")}
                discardLabel={t("actions.discard")}
                savingLabel={t("actions.saving")}
                onDiscard={discardArtist}
              />
            </form>
          )}
        </SectionCard>

        <SectionCard
          id="notifications"
          title={t("notifications.title")}
          description={t("notifications.description")}
        >
          <NotificationPreferencesForm initial={notificationPreferences} />
        </SectionCard>

        {/* Applies on selection, so it stays out of the explicit-save forms. */}
        <SectionCard
          id="language"
          title={t("language.title")}
          description={t("language.description")}
        >
          <LocaleSwitcher />
        </SectionCard>

        {/* ------------------------------------------------------ account */}
        <div aria-hidden className="mt-4 border-t border-dashed border-error/30" />
        <SectionCard
          id="account"
          title={t("account.title")}
          description={t("account.description")}
          tone="danger"
        >
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[15px] font-semibold text-raw-white">
                  {t("account.deleteTitle")}
                </p>
                <p className="mt-1 max-w-prose text-sm leading-6 text-dim-white">
                  {t("account.deleteBody")}
                </p>
              </div>
              {!dangerOpen ? (
                <Button type="button" variant="danger" size="sm" onClick={() => setDangerOpen(true)}>
                  <Trash size={16} weight="bold" aria-hidden />
                  {t("account.deleteAction")}
                </Button>
              ) : null}
            </div>

            {dangerOpen ? (
              <div className="flex animate-step flex-col gap-3 rounded-control border border-error/50 bg-pitch p-4">
                <label
                  htmlFor="set-confirm-delete"
                  className="text-sm leading-6 text-dim-white"
                >
                  {t.rich("account.confirm", {
                    code: (chunks) => <span className="font-mono font-semibold text-error">{chunks}</span>,
                  })}
                </label>
                <input
                  id="set-confirm-delete"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="DELETE"
                  autoFocus
                  autoComplete="off"
                  autoCapitalize="characters"
                  spellCheck={false}
                  aria-describedby={deleteStatus.kind === "error" ? "set-delete-error" : undefined}
                  className={cn(inputClass, "max-w-xs font-mono")}
                />
                {deleteStatus.kind === "error" ? (
                  <p id="set-delete-error" role="alert" className="text-sm text-error">
                    {deleteStatus.message}
                  </p>
                ) : null}
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    disabled={confirm !== "DELETE" || deletePending}
                    onClick={deleteAccount}
                  >
                    {deletePending ? <Spinner /> : null}
                    {deletePending ? t("account.deleting") : t("account.permanentDelete")}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setDangerOpen(false)
                      setConfirm("")
                      setDeleteStatus({ kind: "idle" })
                    }}
                  >
                    {t("actions.cancel")}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </SectionCard>
      </div>
      {cropFile && (
        <AvatarCropModal
          file={cropFile}
          onConfirm={uploadAvatar}
          onCancel={() => setCropFile(null)}
        />
      )}
    </div>
  )
}
