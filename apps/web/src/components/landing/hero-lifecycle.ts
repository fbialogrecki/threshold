export interface HeroScene {
  setRunning(running: boolean): void
  dispose(): void
}

interface Listenable {
  addEventListener(type: string, listener: () => void): void
  removeEventListener(type: string, listener: () => void): void
}

export interface HeroEnv {
  matchMedia(query: string): Listenable & { matches: boolean }
  document: Listenable & { hidden: boolean }
  /** Reports whether the hero is on screen; returns its own teardown. */
  observe(onChange: (onscreen: boolean) => void): () => void
}

export const REDUCED_MOTION = "(prefers-reduced-motion: reduce)"

/**
 * Owns the landing hero's WebGL lifecycle. Reduced motion is checked before
 * the scene chunk is requested, so those visitors never download three.js.
 * The loop runs only while the tab is visible, the hero is on screen and
 * motion is still allowed. `load` resolves null when WebGL is unavailable and
 * receives `fail` for context loss; both leave the static fallback in place.
 */
export function startHeroVisual(
  env: HeroEnv,
  load: (fail: () => void) => Promise<HeroScene | null>,
  onLive: (live: boolean) => void,
): () => void {
  const reduced = env.matchMedia(REDUCED_MOTION)
  if (reduced.matches) return () => {}

  let scene: HeroScene | null = null
  let stopped = false
  let failed = false
  let running = false
  let visible = !env.document.hidden
  let onscreen = false
  let motion = true

  const sync = () => {
    const next = scene !== null && visible && onscreen && motion
    if (next === running) return
    running = next
    scene?.setRunning(next)
  }
  const teardown = () => {
    scene?.dispose()
    scene = null
    running = false
  }
  const fail = () => {
    if (stopped) return
    failed = true
    teardown()
    onLive(false)
  }
  const onVisibility = () => {
    visible = !env.document.hidden
    sync()
  }
  const onMotion = () => {
    motion = !reduced.matches
    sync()
  }

  env.document.addEventListener("visibilitychange", onVisibility)
  reduced.addEventListener("change", onMotion)
  const unobserve = env.observe((next) => {
    onscreen = next
    sync()
  })

  load(fail).then(
    (loaded) => {
      if (stopped || failed) {
        loaded?.dispose()
        return
      }
      if (!loaded) return
      scene = loaded
      onLive(true)
      sync()
    },
    // A failed chunk load keeps the fallback; nothing to clean up.
    () => {},
  )

  return () => {
    stopped = true
    env.document.removeEventListener("visibilitychange", onVisibility)
    reduced.removeEventListener("change", onMotion)
    unobserve()
    teardown()
  }
}
