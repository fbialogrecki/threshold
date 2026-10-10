import { describe, expect, test } from "bun:test"

import { startHeroVisual, type HeroScene } from "../hero-lifecycle"

class Target {
  listeners = new Map<string, Set<() => void>>()
  addEventListener(type: string, listener: () => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type)!.add(listener)
  }
  removeEventListener(type: string, listener: () => void) {
    this.listeners.get(type)?.delete(listener)
  }
  emit(type: string) {
    for (const listener of this.listeners.get(type) ?? []) listener()
  }
  count() {
    return [...this.listeners.values()].reduce((sum, set) => sum + set.size, 0)
  }
}

function setup({ reduced = false, hidden = false } = {}) {
  const media = Object.assign(new Target(), { matches: reduced })
  const doc = Object.assign(new Target(), { hidden })
  let report: (onscreen: boolean) => void = () => {}
  let observing = false
  const env = {
    matchMedia: () => media,
    document: doc,
    observe(onChange: (onscreen: boolean) => void) {
      report = onChange
      observing = true
      return () => {
        observing = false
      }
    },
  }
  const calls: string[] = []
  const scene: HeroScene = {
    setRunning: (running) => calls.push(running ? "run" : "pause"),
    dispose: () => calls.push("dispose"),
  }
  const live: boolean[] = []
  let loads = 0
  let fail = () => {}
  let resolve: (value: HeroScene | null) => void = () => {}
  const load = (onFail: () => void) => {
    loads++
    fail = onFail
    return new Promise<HeroScene | null>((r) => (resolve = r))
  }
  const stop = startHeroVisual(env, load, (value) => live.push(value))
  return {
    media,
    doc,
    calls,
    live,
    stop,
    scene,
    loads: () => loads,
    onscreen: (value: boolean) => report(value),
    observing: () => observing,
    fail: () => fail(),
    resolve: async (value: HeroScene | null) => {
      resolve(value)
      await Promise.resolve()
    },
  }
}

describe("startHeroVisual", () => {
  test("reduced motion never requests the scene chunk", () => {
    const hero = setup({ reduced: true })
    expect(hero.loads()).toBe(0)
    expect(hero.observing()).toBe(false)
  })

  test("runs only while loaded, visible, on screen and motion allowed", async () => {
    const hero = setup()
    hero.onscreen(true)
    expect(hero.calls).toEqual([])

    await hero.resolve(hero.scene)
    expect(hero.live).toEqual([true])
    expect(hero.calls).toEqual(["run"])

    hero.doc.hidden = true
    hero.doc.emit("visibilitychange")
    hero.doc.hidden = false
    hero.doc.emit("visibilitychange")
    hero.onscreen(false)
    hero.onscreen(true)
    hero.media.matches = true
    hero.media.emit("change")
    expect(hero.calls).toEqual(["run", "pause", "run", "pause", "run", "pause"])
  })

  test("starts paused when the tab is hidden", async () => {
    const hero = setup({ hidden: true })
    hero.onscreen(true)
    await hero.resolve(hero.scene)
    expect(hero.calls).toEqual([])
  })

  test("unsupported WebGL keeps the fallback", async () => {
    const hero = setup()
    hero.onscreen(true)
    await hero.resolve(null)
    expect(hero.live).toEqual([])
    expect(hero.calls).toEqual([])
  })

  test("context loss disposes the scene and returns to the fallback", async () => {
    const hero = setup()
    hero.onscreen(true)
    await hero.resolve(hero.scene)
    hero.fail()
    expect(hero.calls).toEqual(["run", "dispose"])
    expect(hero.live).toEqual([true, false])

    hero.onscreen(false)
    hero.onscreen(true)
    expect(hero.calls).toEqual(["run", "dispose"])
  })

  test("failure while loading cannot revive a late scene", async () => {
    const hero = setup()
    hero.onscreen(true)
    hero.fail()
    await hero.resolve(hero.scene)
    expect(hero.calls).toEqual(["dispose"])
    expect(hero.live).toEqual([false])
  })

  test("unmount before the chunk resolves disposes the late scene", async () => {
    const hero = setup()
    hero.stop()
    await hero.resolve(hero.scene)
    expect(hero.calls).toEqual(["dispose"])
    expect(hero.live).toEqual([])
  })

  test("unmount removes every listener and disposes once", async () => {
    const hero = setup()
    await hero.resolve(hero.scene)
    hero.stop()
    hero.fail()
    expect(hero.calls).toEqual(["dispose"])
    expect(hero.doc.count() + hero.media.count()).toBe(0)
    expect(hero.observing()).toBe(false)
  })
})
