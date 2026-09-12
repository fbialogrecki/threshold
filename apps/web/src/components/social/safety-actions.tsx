"use client"

import { useRef, useState, type FormEvent } from "react"
import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { REPORT_REASONS, reportContent, setAccountBlocked, type ReportTarget } from "@/lib/safety/actions"

export function SafetyActions({ allowed, target, username, initialBlocked = null }: {
  allowed: boolean; target: ReportTarget; username?: string; initialBlocked?: boolean | null
}) {
  const t = useTranslations("safety")
  const router = useRouter()
  const [reportOpen, setReportOpen] = useState(false)
  const [reason, setReason] = useState<string>("spam")
  const [note, setNote] = useState("")
  const [blocked, setBlocked] = useState(initialBlocked)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")
  const [status, setStatus] = useState("")
  const busy = useRef(false)
  if (!allowed) return null

  async function run(action: () => Promise<void>) {
    if (busy.current) return
    busy.current = true
    setPending(true)
    setError("")
    setStatus("")
    try { await action() } catch { setError(t("failed")) } finally { busy.current = false; setPending(false) }
  }
  function report(e: FormEvent) {
    e.preventDefault()
    void run(async () => {
      await reportContent(target, reason, note)
      setStatus(t("reported"))
      setReportOpen(false)
    })
  }
  function block() {
    if (!username || blocked === null) return
    void run(async () => {
      await setAccountBlocked(username, !blocked)
      setBlocked(!blocked)
      setStatus(t(blocked ? "unblocked" : "blocked"))
      router.refresh()
    })
  }
  const buttonClass = "font-mono text-[11px] uppercase tracking-label text-muted hover:text-acid disabled:opacity-50"
  return <details className="mt-3 border-t border-border-gray pt-2">
    <summary className={`${buttonClass} cursor-pointer`}>{t("actions")}</summary>
    <div className="mt-3 flex flex-col gap-3">
      <button type="button" disabled={pending} aria-expanded={reportOpen} onClick={() => { setReportOpen(!reportOpen); setStatus("") }} className={`${buttonClass} self-start`}>{t("report")}</button>
      {reportOpen ? <form onSubmit={report} className="flex flex-col gap-3">
        <p className="text-sm text-muted">{t("reportHelp")}</p>
        <label className="flex flex-col gap-1 text-sm">{t("reason")}<select required value={reason} disabled={pending} onChange={e => setReason(e.target.value)} className="border border-border-gray bg-pitch p-2">{REPORT_REASONS.map(reason => <option key={reason} value={reason}>{t(`reasons.${reason}`)}</option>)}</select></label>
        <label className="flex flex-col gap-1 text-sm">{t("note")}<textarea value={note} disabled={pending} maxLength={target.type === "profile" ? 2000 : 1000} rows={3} onChange={e => setNote(e.target.value)} className="border border-border-gray bg-pitch p-2" /></label>
        <button type="submit" disabled={pending} className={`${buttonClass} self-start`}>{t(pending ? "working" : "sendReport")}</button>
      </form> : null}
      {username ? blocked === null ? <p role="status" className="text-sm text-muted">{t("blockUnknown")} <button type="button" onClick={() => router.refresh()} className={buttonClass}>{t("retry")}</button></p> : <>
        <p className="text-sm text-muted">{t("blockHelp")}</p>
        <button type="button" disabled={pending} onClick={block} className={`${buttonClass} self-start`}>{t(blocked ? "unblock" : "block")}</button>
      </> : null}
      {error ? <p role="alert" className="text-sm text-error">{error}</p> : null}
      {status ? <p role="status" className="text-sm text-acid">{status}</p> : null}
    </div>
  </details>
}
