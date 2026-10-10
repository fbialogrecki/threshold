"use client"

import { useTranslations } from "next-intl"
import { useCallback, useEffect, useRef, useState } from "react"

import { Button } from "@/components/ui/button"

type Crop = { x: number; y: number; size: number }

const MIN_SIZE = 48
const GRID_COLOR = "rgba(255,255,255,0.35)"
const OVERLAY_COLOR = "rgba(0,0,0,0.65)"

export function AvatarCropModal({
  file,
  onConfirm,
  onCancel,
}: {
  file: File
  onConfirm: (blob: Blob) => void
  onCancel: () => void
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [imgLoaded, setImgLoaded] = useState(false)
  const [crop, setCrop] = useState<Crop>({ x: 0, y: 0, size: 0 })
  const [dispW, setDispW] = useState(0)
  const [dispH, setDispH] = useState(0)
  const dragRef = useRef<"move" | "resize" | null>(null)
  const dragStartRef = useRef<{ mx: number; my: number; cx: number; cy: number; cs: number } | null>(null)
  const t = useTranslations("settings.crop")

  useEffect(() => {
    if (!imgLoaded) return
    const dialog = dialogRef.current
    dialog?.showModal()
    return () => dialog?.close()
  }, [imgLoaded])

  // Load image
  useEffect(() => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      imgRef.current = img
      setImgLoaded(true)
    }
    img.src = url
    return () => URL.revokeObjectURL(url)
  }, [file])

  // Compute display dimensions + initial centered square crop
  useEffect(() => {
    if (!imgLoaded || !imgRef.current) return
    const img = imgRef.current
    const maxDim = Math.max(MIN_SIZE, Math.min(480, document.documentElement.clientWidth - 96))
    const ratio = Math.min(maxDim / img.width, maxDim / img.height, 1)
    const w = Math.round(img.width * ratio)
    const h = Math.round(img.height * ratio)
    setDispW(w)
    setDispH(h)
    const size = Math.min(w, h)
    setCrop({ x: (w - size) / 2, y: (h - size) / 2, size })
  }, [imgLoaded])

  const scale = useCallback(() => {
    if (!imgRef.current) return 1
    return dispW / imgRef.current.width
  }, [dispW])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    const img = imgRef.current
    if (!canvas || !img) return
    canvas.width = dispW
    canvas.height = dispH
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    ctx.drawImage(img, 0, 0, dispW, dispH)

    // Dark overlay outside crop
    ctx.fillStyle = OVERLAY_COLOR
    ctx.fillRect(0, 0, dispW, dispH)

    // Clear crop area — redraw image portion
    ctx.save()
    ctx.beginPath()
    ctx.rect(crop.x, crop.y, crop.size, crop.size)
    ctx.clip()
    ctx.drawImage(img, 0, 0, dispW, dispH)
    ctx.restore()

    // Crop border
    ctx.strokeStyle = "rgba(255,255,255,0.9)"
    ctx.lineWidth = 2
    ctx.strokeRect(crop.x, crop.y, crop.size, crop.size)

    // Rule-of-thirds grid
    ctx.strokeStyle = GRID_COLOR
    ctx.lineWidth = 1
    for (let i = 1; i < 3; i++) {
      const vx = crop.x + (crop.size * i) / 3
      ctx.beginPath(); ctx.moveTo(vx, crop.y); ctx.lineTo(vx, crop.y + crop.size); ctx.stroke()
      const hy = crop.y + (crop.size * i) / 3
      ctx.beginPath(); ctx.moveTo(crop.x, hy); ctx.lineTo(crop.x + crop.size, hy); ctx.stroke()
    }

    // Resize handle (bottom-right corner)
    const hx = crop.x + crop.size
    const hy = crop.y + crop.size
    ctx.fillStyle = "rgba(255,255,255,0.9)"
    ctx.fillRect(hx - 8, hy - 8, 8, 8)
  }, [crop, dispW, dispH])

  useEffect(() => { draw() }, [draw])

  function hitTest(mx: number, my: number): "resize" | "move" | null {
    const { x, y, size } = crop
    if (mx >= x + size - 12 && mx <= x + size + 4 && my >= y + size - 12 && my <= y + size + 4) return "resize"
    if (mx >= x && mx <= x + size && my >= y && my <= y + size) return "move"
    return null
  }

  function onPointerDown(e: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const hit = hitTest(mx, my)
    if (!hit) return
    dragRef.current = hit
    dragStartRef.current = { mx, my, cx: crop.x, cy: crop.y, cs: crop.size }
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!dragRef.current || !dragStartRef.current) return
    const rect = canvasRef.current!.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const start = dragStartRef.current
    const dx = mx - start.mx
    const dy = my - start.my

    if (dragRef.current === "move") {
      setCrop((c) => ({
        ...c,
        x: Math.max(0, Math.min(dispW - c.size, start.cx + dx)),
        y: Math.max(0, Math.min(dispH - c.size, start.cy + dy)),
      }))
    } else if (dragRef.current === "resize") {
      const delta = Math.max(dx, dy)
      const newSize = Math.max(MIN_SIZE, Math.min(dispW - start.cx, dispH - start.cy, start.cs + delta))
      setCrop((c) => ({ ...c, size: newSize }))
    }
  }

  function onPointerUp() {
    dragRef.current = null
    dragStartRef.current = null
  }

  function confirm() {
    const img = imgRef.current
    if (!img) return
    const s = scale()
    // Source crop in original image coordinates
    const sx = crop.x / s
    const sy = crop.y / s
    const sw = crop.size / s
    const sh = crop.size / s
    // Output: 512x512 (matches avatar_512 derivative)
    const out = document.createElement("canvas")
    out.width = 512
    out.height = 512
    const ctx = out.getContext("2d")!
    ctx.drawImage(img, sx, sy, sw, sh, 0, 0, 512, 512)
    out.toBlob((blob) => {
      if (blob) onConfirm(blob)
    }, "image/webp", 0.92)
  }

  if (!imgLoaded) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80">
        <p role="status" className="text-sm text-dim-white">{t("loading")}</p>
      </div>
    )
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="avatar-crop-title"
      className="m-auto max-w-[calc(100%-2rem)] bg-transparent p-0 text-raw-white backdrop:bg-black/80 backdrop:backdrop-blur-sm"
      onCancel={onCancel}
      onClick={(event) => { if (event.target === event.currentTarget) onCancel() }}
    >
      <div
        className="flex max-w-full animate-fade flex-col gap-4 rounded-surface border border-border-gray bg-graphite p-5 sm:p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div>
          <h2 id="avatar-crop-title" className="text-lg font-semibold text-raw-white">{t("title")}</h2>
          <p className="mt-1 text-sm text-dim-white">{t("help")}</p>
        </div>
        <div className="flex justify-center overflow-hidden rounded-control">
          <canvas
            ref={canvasRef}
            className="cursor-move touch-none"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            {t("cancel")}
          </Button>
          <Button type="button" variant="primary" size="sm" autoFocus onClick={confirm}>
            {t("save")}
          </Button>
        </div>
      </div>
    </dialog>
  )
}
