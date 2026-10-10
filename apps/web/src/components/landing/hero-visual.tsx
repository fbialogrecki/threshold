"use client"

import { useEffect, useRef, useState } from "react"

import { cn } from "@/lib/cn"

import { startHeroVisual } from "./hero-lifecycle"

/**
 * Decorative only. The CSS rings are the server-rendered state and the
 * fallback for reduced motion, missing WebGL, a failed chunk or a lost
 * context; the canvas fades in over them once three.js has drawn a frame.
 */
export function HeroVisual({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [live, setLive] = useState(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    return startHeroVisual(
      {
        matchMedia: (query) => window.matchMedia(query),
        document,
        observe(onChange) {
          const observer = new IntersectionObserver(([entry]) =>
            onChange(entry.isIntersecting),
          )
          observer.observe(canvas)
          return () => observer.disconnect()
        },
      },
      (fail) => import("./hero-scene").then((mod) => mod.mountHeroScene(canvas, fail)),
      setLive,
    )
  }, [])

  return (
    <div aria-hidden className={cn("hero-visual pointer-events-none", className)}>
      <div className={cn("hero-fallback", live && "opacity-0")} />
      <canvas
        ref={canvasRef}
        className={cn("hero-canvas", live ? "opacity-100" : "opacity-0")}
      />
    </div>
  )
}
