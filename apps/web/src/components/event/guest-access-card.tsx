"use client"

import { ArrowClockwise, CheckCircle, QrCode, X } from "@phosphor-icons/react"
import { useLocale, useTranslations } from "next-intl"
import { useEffect, useReducer, useRef } from "react"
import { QRCodeSVG } from "qrcode.react"

import { Button } from "@/components/ui/button"
import { Card, CardBody, CardHeader } from "@/components/ui/card"
import { StatusBadge } from "@/components/ui/status-badge"
import {
  initialQrState,
  qrExpired,
  qrExpiryDelay,
  qrReducer,
} from "@/lib/events/qr-lifecycle"
import type { EventGuestAccess } from "@/lib/types"

export function GuestAccessCard({
  access,
  canMintQr,
  slug,
}: {
  access: EventGuestAccess
  canMintQr: boolean
  slug: string
}) {
  const t = useTranslations("eventDetail.access")
  const locale = useLocale()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const controllerRef = useRef<AbortController | null>(null)
  const generationRef = useRef(0)
  const [qr, dispatch] = useReducer(qrReducer, initialQrState)

  function clearQr() {
    controllerRef.current?.abort()
    controllerRef.current = null
    generationRef.current += 1
    dispatch({ type: "clear", generation: generationRef.current })
  }

  async function mintQr() {
    controllerRef.current?.abort()
    const controller = new AbortController()
    const generation = generationRef.current + 1
    generationRef.current = generation
    controllerRef.current = controller
    dispatch({ type: "begin", generation })
    try {
      const response = await fetch(
        `/api/events/${encodeURIComponent(slug)}/guestlist/me/qr-token`,
        { method: "POST", signal: controller.signal },
      )
      if (!response.ok) throw new Error("qr request failed")
      const body = await response.json() as { token?: unknown; expires_at?: unknown }
      if (typeof body.token !== "string" || typeof body.expires_at !== "string") {
        throw new Error("invalid qr response")
      }
      dispatch(
        qrExpired(body.expires_at)
          ? { type: "expire", generation }
          : { type: "resolve", generation, token: body.token, expiresAt: body.expires_at },
      )
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        dispatch({ type: "reject", generation })
      }
    } finally {
      if (generationRef.current === generation) controllerRef.current = null
    }
  }

  function openQr() {
    dialogRef.current?.showModal()
    mintQr()
  }

  useEffect(() => () => {
    controllerRef.current?.abort()
    generationRef.current += 1
  }, [])

  useEffect(() => {
    if (qr.status !== "ready") return
    const delay = qrExpiryDelay(qr.expiresAt)
    const timer = window.setTimeout(
      () => dispatch({ type: "expire", generation: qr.generation }),
      delay,
    )
    return () => window.clearTimeout(timer)
  }, [qr])

  return (
    <>
      <Card as="section" className="border-l-2 border-l-acid">
        <CardHeader>
          <div className="flex items-center gap-2">
            <CheckCircle size={18} weight="fill" className="text-acid" aria-hidden />
            <h2 className="font-display text-2xl tracking-wide text-raw-white">
              {t("approvedTitle")}
            </h2>
          </div>
          <StatusBadge status="guestlist" label={t("guestlistBadge")} />
        </CardHeader>
        <CardBody>
          <p className="text-sm leading-6 text-dim-white">
            {access.checked_in_at ? t("checkedInBody") : t("approvedBody")}
          </p>
          {canMintQr ? (
            <Button type="button" variant="primary" className="mt-4" onClick={openQr}>
              <QrCode size={17} weight="bold" aria-hidden />
              {t("showQr")}
            </Button>
          ) : null}
        </CardBody>
      </Card>

      <dialog
        ref={dialogRef}
        aria-labelledby="guest-qr-title"
        onClose={clearQr}
        className="m-auto w-[min(92vw,28rem)] border border-border-gray bg-graphite p-0 text-raw-white backdrop:bg-black/85"
      >
        <div className="flex items-center justify-between border-b border-border-gray px-4 py-3">
          <h2 id="guest-qr-title" className="font-display text-3xl tracking-wide">
            {t("qrTitle")}
          </h2>
          <button
            type="button"
            autoFocus
            aria-label={t("closeQr")}
            className="p-2 text-muted hover:text-raw-white"
            onClick={() => dialogRef.current?.close()}
          >
            <X size={20} weight="bold" aria-hidden />
          </button>
        </div>
        <div className="flex min-h-80 flex-col items-center justify-center gap-4 p-6 text-center">
          {qr.status === "ready" ? (
            <>
              <div className="bg-white p-3">
                <QRCodeSVG
                  value={qr.token}
                  size={240}
                  level="M"
                  marginSize={2}
                  title={t("qrTitle")}
                  aria-label={t("qrTitle")}
                />
              </div>
              <p className="font-mono text-xs uppercase tracking-label text-muted">
                {t("qrExpires", {
                  time: new Intl.DateTimeFormat(locale, { timeStyle: "medium" }).format(
                    new Date(qr.expiresAt),
                  ),
                })}
              </p>
            </>
          ) : (
            <p className="font-mono text-xs uppercase tracking-label text-muted" role="status">
              {qr.status === "loading"
                ? t("qrLoading")
                : qr.status === "expired"
                  ? t("qrExpired")
                  : qr.status === "error"
                    ? t("qrError")
                    : ""}
            </p>
          )}
          <Button type="button" disabled={qr.status === "loading"} onClick={mintQr}>
            <ArrowClockwise size={17} weight="bold" aria-hidden />
            {t("refreshQr")}
          </Button>
        </div>
      </dialog>
    </>
  )
}
