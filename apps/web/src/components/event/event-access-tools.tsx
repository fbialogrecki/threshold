"use client"

import {
  CheckCircle,
  DoorOpen,
  IdentificationCard,
  Scan,
  SlidersHorizontal,
  Trash,
  UserPlus,
  UsersThree,
} from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { GuestSearch, type GuestSelection } from "@/components/event/guest-search"
import { Button } from "@/components/ui/button"
import { Card, CardBody, CardHeader } from "@/components/ui/card"
import { FormAlert, inputClass, Spinner } from "@/components/ui/field"
import { StatusBadge } from "@/components/ui/status-badge"
import { cn } from "@/lib/cn"
import {
  checkInErrorKey,
  mutationFailure,
  personName,
  type LineupArtistChoice,
  type MinimalCheckInResponse,
} from "@/lib/events/access"
import type {
  DoorStaffAssignment,
  EventViewerContext,
  GuestQuota,
  ManagerGuestlistEntry,
} from "@/lib/types"

type AccessErrorKey =
  | "mutationUnauthorized"
  | "mutationForbidden"
  | "mutationNotFound"
  | "mutationError"
  | "guestAddError"
  | "quotaFull"
  | "quotaError"
  | "checkInError"

function mutationErrorKey(
  status: number,
  fallback: AccessErrorKey,
  conflict: AccessErrorKey = fallback,
): AccessErrorKey {
  const failure = mutationFailure(status)
  if (failure === "unauthorized") return "mutationUnauthorized"
  if (failure === "forbidden") return "mutationForbidden"
  if (failure === "notFound") return "mutationNotFound"
  if (failure === "conflict") return conflict
  return fallback
}

function AddGuestForm({
  artistProfileId,
  onAdded,
  slug,
}: {
  artistProfileId?: string
  onAdded?: () => void
  slug: string
}) {
  const t = useTranslations("eventDetail.access")
  const [pending, setPending] = useState(false)
  const [selected, setSelected] = useState<GuestSelection | null>(null)
  const [message, setMessage] = useState("")
  const [searchKey, setSearchKey] = useState(0)

  async function addGuest() {
    if (!selected) return
    setMessage("")
    setPending(true)
    try {
      const response = await fetch(`/api/events/${encodeURIComponent(slug)}/guestlist`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          username: selected.handle,
          ...(artistProfileId ? { artist_profile_id: artistProfileId } : {}),
        }),
      })
      if (!response.ok) {
        setMessage(t(mutationErrorKey(response.status, "guestAddError", "quotaFull")))
        return
      }
      setSelected(null)
      setSearchKey((value) => value + 1)
      setMessage(t("guestAdded"))
      onAdded?.()
    } catch {
      setMessage(t("networkError"))
    } finally {
      setPending(false)
    }
  }

  return (
    <div>
      <GuestSearch key={searchKey} disabled={pending} onSelect={setSelected} />
      <Button type="button" size="sm" className="mt-3" disabled={pending || !selected} onClick={addGuest}>
        {pending ? <Spinner /> : <UserPlus size={17} weight="bold" aria-hidden />}
        {pending ? t("addingGuest") : t("addGuest")}
      </Button>
      {message ? (
        <p className="mt-2 text-sm text-dim-white" role="status">
          {message}
        </p>
      ) : null}
    </div>
  )
}

export function ManagerGuestlist({
  entries,
  slug,
}: {
  entries: ManagerGuestlistEntry[]
  slug: string
}) {
  const t = useTranslations("eventDetail.access")
  const router = useRouter()
  const [pendingId, setPendingId] = useState("")
  const [message, setMessage] = useState("")

  async function removeGuest(guestUserId: string) {
    if (pendingId) return
    setPendingId(guestUserId)
    setMessage("")
    try {
      const response = await fetch(
        `/api/events/${encodeURIComponent(slug)}/guestlist/${encodeURIComponent(guestUserId)}`,
        { method: "DELETE" },
      )
      setMessage(response.ok
        ? t("guestRemoved")
        : t(mutationErrorKey(response.status, "mutationError")))
      if (response.ok) router.refresh()
    } catch {
      setMessage(t("networkError"))
    } finally {
      setPendingId("")
    }
  }

  return (
    <Card as="section">
      <CardHeader>
        <div className="flex items-center gap-2">
          <UsersThree size={19} weight="bold" className="text-raw-white" aria-hidden />
          <h2 className="text-lg font-semibold">{t("managerTitle")}</h2>
        </div>
        <StatusBadge status="guestlist" label={t("guestlistBadge")} />
      </CardHeader>
      <CardBody className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(18rem,0.7fr)]">
        <div>
          <h3 className="mb-3 text-sm font-semibold text-dim-white">
            {t("guestlistCount", { count: entries.filter(({ status }) => status === "active").length })}
          </h3>
          <div className="divide-y divide-border-gray overflow-hidden rounded-control border border-border-gray bg-pitch/60">
            {entries.length > 0 ? entries.map((entry) => (
              <div key={entry.id} className="flex items-center justify-between gap-3 px-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-[15px] font-semibold text-raw-white">{personName(entry)}</p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[13px] text-muted">
                    {t(entry.source === "dj" ? "sourceDj" : "sourceOrganizer")}
                    {entry.checked_in_at ? (
                      <span className="inline-flex items-center gap-1 text-acid">
                        <CheckCircle size={14} weight="fill" aria-hidden />
                        {t("checkedIn")}
                      </span>
                    ) : null}
                  </p>
                </div>
                {entry.status === "active" ? (
                  <button
                    type="button"
                    disabled={!!pendingId}
                    aria-label={t("removeGuestNamed", { name: personName(entry) })}
                    className="grid size-10 shrink-0 place-items-center rounded-control border border-error/60 text-error transition-colors hover:bg-error hover:text-pitch disabled:opacity-50"
                    onClick={() => removeGuest(entry.guest_user_id)}
                  >
                    <Trash size={16} weight="bold" aria-hidden />
                  </button>
                ) : (
                  <StatusBadge status="removed" label={t("removed")} />
                )}
              </div>
            )) : (
              <p className="p-3 text-sm text-muted">{t("guestlistEmpty")}</p>
            )}
          </div>
          {message ? <p className="mt-2 text-sm text-muted" role="status">{message}</p> : null}
        </div>
        <div>
          <h3 className="mb-3 text-sm font-semibold text-dim-white">
            {t("addGuestTitle")}
          </h3>
          <AddGuestForm slug={slug} onAdded={() => router.refresh()} />
        </div>
      </CardBody>
    </Card>
  )
}

export function DjGuestTools({
  artists,
  context,
  slug,
}: {
  artists: LineupArtistChoice[]
  context: EventViewerContext
  slug: string
}) {
  const t = useTranslations("eventDetail.access")
  const router = useRouter()
  const [artistId, setArtistId] = useState(artists[0]?.id ?? "")
  const owned = context.viewer_lineup_artists.find(
    ({ artist_profile_id }) => artist_profile_id === artistId,
  )

  if (artists.length === 0) return null

  return (
    <Card as="section">
      <CardHeader>
        <div className="flex items-center gap-2">
          <UserPlus size={18} weight="bold" className="text-raw-white" aria-hidden />
          <h2 className="text-lg font-semibold">{t("djTitle")}</h2>
        </div>
        <StatusBadge status="guestlist" label={t("guestlistBadge")} />
      </CardHeader>
      <CardBody>
        {artists.length > 1 ? (
          <label className="mb-4 block text-sm font-medium text-raw-white">
            {t("lineupArtist")}
            <select
              value={artistId}
              className={cn(inputClass, "mt-2")}
              onChange={(event) => setArtistId(event.target.value)}
            >
              {artists.map((artist) => <option key={artist.id} value={artist.id}>{artist.name}</option>)}
            </select>
          </label>
        ) : (
          <p className="mb-3 text-[15px] font-semibold text-raw-white">{artists[0].name}</p>
        )}
        <QuotaSummary quota={owned?.quota ?? null} />
        {owned?.quota && owned.quota.remaining > 0 ? (
          <div className="mt-4">
            <AddGuestForm
              artistProfileId={artistId}
              slug={slug}
              onAdded={() => router.refresh()}
            />
          </div>
        ) : (
          <p className="mt-3 text-sm text-muted">{t(owned?.quota ? "quotaFull" : "quotaUnassigned")}</p>
        )}
      </CardBody>
    </Card>
  )
}

function QuotaSummary({ quota }: { quota: GuestQuota | null }) {
  const t = useTranslations("eventDetail.access")
  return quota ? (
    <dl className="grid grid-cols-3 gap-2">
      {(["quota", "used", "remaining"] as const).map((key) => (
        <div key={key} className="rounded-control bg-raised p-3">
          <dt className="text-xs text-muted">{t(key)}</dt>
          <dd className={cn("mt-1 text-2xl font-semibold tabular-nums", key === "remaining" && quota.remaining === 0 ? "text-orange" : "text-raw-white")}>
            {quota[key]}
          </dd>
        </div>
      ))}
    </dl>
  ) : null
}

export function QuotaControls({
  artists,
  quotas,
  slug,
}: {
  artists: LineupArtistChoice[]
  quotas: GuestQuota[]
  slug: string
}) {
  const t = useTranslations("eventDetail.access")
  const router = useRouter()
  const [pendingArtistId, setPendingArtistId] = useState("")
  const [message, setMessage] = useState("")

  async function saveQuota(artistId: string, formData: FormData) {
    if (pendingArtistId) return
    const quota = Number(formData.get("quota"))
    setMessage("")
    setPendingArtistId(artistId)
    try {
      const response = await fetch(
        `/api/events/${encodeURIComponent(slug)}/guestlist/quotas/${encodeURIComponent(artistId)}`,
        {
          method: "PUT",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ quota }),
        },
      )
      setMessage(response.ok
        ? t("quotaSaved")
        : t(mutationErrorKey(response.status, "quotaError")))
      if (response.ok) router.refresh()
    } catch {
      setMessage(t("networkError"))
    } finally {
      setPendingArtistId("")
    }
  }

  if (artists.length === 0) return null
  const quotasByArtist = new Map(quotas.map((quota) => [quota.artist_profile_id, quota]))

  return (
    <Card as="section">
      <CardHeader>
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={18} weight="bold" aria-hidden />
          <h2 className="text-lg font-semibold">{t("quotaControlsTitle")}</h2>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        {artists.map((artist) => {
          const quota = quotasByArtist.get(artist.id)
          return (
            <form
              key={artist.id}
              action={(data) => saveQuota(artist.id, data)}
              className="grid gap-3 rounded-control border border-border-gray bg-pitch/60 p-3 sm:grid-cols-[1fr_auto_auto] sm:items-end"
            >
              <div className="min-w-0">
                <p className="truncate text-[15px] font-semibold text-raw-white">{artist.name}</p>
                <p className="text-[13px] text-muted">
                  {t("quotaUsage", { used: quota?.used ?? 0, quota: quota?.quota ?? 0 })}
                </p>
              </div>
              <label className="text-sm font-medium text-raw-white">
                {t("quota")}
                <input
                  name="quota"
                  type="number"
                  min="0"
                  max="500"
                  required
                  defaultValue={quota?.quota ?? 0}
                  className={cn(inputClass, "mt-2 block w-28 tabular-nums")}
                />
              </label>
              <Button type="submit" size="sm" disabled={!!pendingArtistId}>
                {pendingArtistId === artist.id ? <Spinner /> : null}
                {t("saveQuota")}
              </Button>
            </form>
          )
        })}
        {message ? <p className="text-sm text-muted" role="status">{message}</p> : null}
      </CardBody>
    </Card>
  )
}

export function DoorStaffManager({
  assignments,
  slug,
}: {
  assignments: DoorStaffAssignment[]
  slug: string
}) {
  const t = useTranslations("eventDetail.access")
  const router = useRouter()
  const [selected, setSelected] = useState<GuestSelection | null>(null)
  const [assigning, setAssigning] = useState(false)
  const [revokingId, setRevokingId] = useState("")
  const [message, setMessage] = useState("")
  const [searchKey, setSearchKey] = useState(0)
  const busy = assigning || !!revokingId

  async function assign() {
    if (!selected || busy) return
    setAssigning(true)
    setMessage("")
    try {
      const response = await fetch(
        `/api/events/${encodeURIComponent(slug)}/door-staff/by-username/${encodeURIComponent(selected.handle)}`,
        { method: "PUT" },
      )
      if (!response.ok) {
        setMessage(t(mutationErrorKey(response.status, "mutationError")))
        return
      }
      setSelected(null)
      setSearchKey((value) => value + 1)
      setMessage(t("doorStaffAssigned"))
      router.refresh()
    } catch {
      setMessage(t("networkError"))
    } finally {
      setAssigning(false)
    }
  }

  async function revoke(assignmentId: string) {
    if (busy) return
    setRevokingId(assignmentId)
    setMessage("")
    try {
      const response = await fetch(
        `/api/events/${encodeURIComponent(slug)}/door-staff/${encodeURIComponent(assignmentId)}`,
        { method: "DELETE" },
      )
      setMessage(response.ok
        ? t("doorStaffRevoked")
        : t(mutationErrorKey(response.status, "mutationError")))
      if (response.ok) router.refresh()
    } catch {
      setMessage(t("networkError"))
    } finally {
      setRevokingId("")
    }
  }

  return (
    <Card as="section">
      <CardHeader>
        <div className="flex items-center gap-2">
          <IdentificationCard size={19} weight="bold" aria-hidden />
          <h2 className="text-lg font-semibold">{t("doorStaffTitle")}</h2>
        </div>
        <StatusBadge status="private" label={t("managerOnly")} />
      </CardHeader>
      <CardBody className="grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-3 text-sm font-semibold text-dim-white">
            {t("doorStaffCurrent")}
          </h3>
          <div className="divide-y divide-border-gray overflow-hidden rounded-control border border-border-gray bg-pitch/60">
            {assignments.length > 0 ? assignments.map((assignment) => (
              <div key={assignment.id} className="flex items-center justify-between gap-3 px-3 py-3">
                <p className="min-w-0 truncate text-[15px] font-semibold text-raw-white">
                  {personName(assignment) || t("doorStaffUnavailable")}
                </p>
                <button
                  type="button"
                  disabled={busy}
                  aria-label={t("revokeDoorStaffNamed", {
                    name: personName(assignment) || t("doorStaffUnavailable"),
                  })}
                  className="grid size-10 shrink-0 place-items-center rounded-control border border-error/60 text-error transition-colors hover:bg-error hover:text-pitch disabled:opacity-50"
                  onClick={() => revoke(assignment.id)}
                >
                  <Trash size={16} weight="bold" aria-hidden />
                </button>
              </div>
            )) : (
              <p className="p-3 text-sm text-muted">{t("doorStaffEmpty")}</p>
            )}
          </div>
        </div>
        <div>
          <h3 className="mb-3 text-sm font-semibold text-dim-white">
            {t("assignDoorStaff")}
          </h3>
          <GuestSearch
            key={searchKey}
            disabled={busy}
            label={t("doorStaffSearchLabel")}
            placeholder={t("doorStaffSearchPlaceholder")}
            onSelect={setSelected}
          />
          <Button type="button" size="sm" className="mt-3" disabled={busy || !selected} onClick={assign}>
            {assigning ? <Spinner /> : <IdentificationCard size={17} weight="bold" aria-hidden />}
            {assigning ? t("assigningDoorStaff") : t("assignDoorStaff")}
          </Button>
        </div>
        {message ? <p className="text-sm text-muted lg:col-span-2" role="status">{message}</p> : null}
      </CardBody>
    </Card>
  )
}

export function DoorCheckIn({ slug }: { slug: string }) {
  const t = useTranslations("eventDetail.access")
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState("")
  const [result, setResult] = useState<MinimalCheckInResponse | null>(null)

  async function checkIn(formData: FormData) {
    setMessage("")
    setResult(null)
    setPending(true)
    try {
      const response = await fetch(`/api/events/${encodeURIComponent(slug)}/check-in`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token: String(formData.get("token") ?? "").trim() }),
      })
      if (!response.ok) {
        setMessage(t(checkInErrorKey(response.status)))
        return
      }
      setResult(await response.json() as MinimalCheckInResponse)
      const form = document.getElementById(`door-check-in-${slug}`) as HTMLFormElement | null
      form?.reset()
    } catch {
      setMessage(t("networkError"))
    } finally {
      setPending(false)
    }
  }

  return (
    <Card as="section">
      <CardHeader>
        <div className="flex items-center gap-2">
          <DoorOpen size={19} weight="bold" aria-hidden />
          <h2 className="text-lg font-semibold">{t("doorTitle")}</h2>
        </div>
        <StatusBadge status="private" label={t("doorStaffOnly")} />
      </CardHeader>
      <CardBody>
        <form id={`door-check-in-${slug}`} action={checkIn}>
          <label className="block text-sm font-medium text-raw-white">
            {t("scannerLabel")}
            <div className="mt-2 flex items-center gap-2 rounded-control border border-border-gray bg-pitch px-3.5 transition-[border-color,box-shadow] focus-within:border-acid focus-within:shadow-[0_0_0_3px_rgba(198,255,0,0.18)]">
              <Scan size={18} weight="bold" className="shrink-0 text-muted" aria-hidden />
              <input
                name="token"
                required
                minLength={20}
                maxLength={240}
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
                placeholder={t("scannerPlaceholder")}
                className="min-w-0 flex-1 bg-transparent py-3 font-mono text-base text-raw-white placeholder:font-sans placeholder:text-muted focus:outline-none"
              />
            </div>
          </label>
          <p className="mt-2 text-[13px] leading-5 text-muted">
            {t("scannerHelp")}
          </p>
          <Button type="submit" variant="primary" size="lg" className="mt-4 w-full sm:w-auto" disabled={pending}>
            {pending ? <Spinner /> : <Scan size={18} weight="bold" aria-hidden />}
            {pending ? t("checkingIn") : t("checkIn")}
          </Button>
        </form>
        {result ? (
          // Minimal confirmation only: the name and the state, nothing else about the guest.
          <div className="mt-4 flex animate-step items-center gap-3 rounded-control border border-acid/50 bg-acid/10 p-4" role="status">
            <CheckCircle size={28} weight="fill" className="shrink-0 text-acid" aria-hidden />
            <div className="min-w-0">
              <p className="truncate text-xl font-semibold text-raw-white">{personName(result)}</p>
              <p className="text-sm text-acid">{t("checkedIn")}</p>
            </div>
          </div>
        ) : message ? (
          <div className="mt-4">
            <FormAlert>{message}</FormAlert>
          </div>
        ) : null}
      </CardBody>
    </Card>
  )
}
