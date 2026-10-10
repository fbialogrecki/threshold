import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  Fog,
  Group,
  LineBasicMaterial,
  LineLoop,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  Scene,
  WebGLRenderer,
} from "three"

import type { HeroScene } from "./hero-lifecycle"

const ACID = 0xc6ff00
const PITCH = 0x030303
const RINGS = 14
const SEGMENTS = 160

/**
 * A stack of warped acid rings inside a torus of dust: one draw call per ring
 * plus one for the dust, no textures, no post-processing. Returns null when a
 * WebGL context cannot be created.
 */
export function mountHeroScene(
  canvas: HTMLCanvasElement,
  onLost: () => void,
): HeroScene | null {
  let renderer: WebGLRenderer
  try {
    renderer = new WebGLRenderer({
      canvas,
      alpha: true,
      antialias: true,
      powerPreference: "low-power",
    })
  } catch {
    return null
  }

  const small = canvas.clientWidth < 640
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, small ? 1.5 : 2))
  renderer.setClearColor(PITCH, 0)

  const scene = new Scene()
  scene.fog = new Fog(PITCH, 7, 12.5)
  const camera = new PerspectiveCamera(36, 1, 0.1, 40)
  camera.position.set(0, 0, 9.5)

  const sculpture = new Group()
  sculpture.rotation.set(1.08, 0.18, -0.4)
  scene.add(sculpture)

  const geometries: BufferGeometry[] = []
  const lineMaterial = new LineBasicMaterial({
    color: ACID,
    transparent: true,
    opacity: 0.5,
    blending: AdditiveBlending,
    depthWrite: false,
  })
  for (let ring = 0; ring < RINGS; ring++) {
    const radius = 1.05 + ring * 0.16
    const lift = (ring - RINGS / 2) * 0.07
    const positions = new Float32Array(SEGMENTS * 3)
    for (let i = 0; i < SEGMENTS; i++) {
      const angle = (i / SEGMENTS) * Math.PI * 2
      // Uneven, phase-shifted wobble keeps the stack sculptural, not a target.
      const r = radius * (1 + 0.07 * Math.sin(angle * 3 + ring * 0.7))
      positions[i * 3] = Math.cos(angle) * r
      positions[i * 3 + 1] = Math.sin(angle) * r
      positions[i * 3 + 2] = lift + 0.3 * Math.sin(angle * 2 + ring * 0.45)
    }
    const geometry = new BufferGeometry()
    geometry.setAttribute("position", new BufferAttribute(positions, 3))
    geometries.push(geometry)
    sculpture.add(new LineLoop(geometry, lineMaterial))
  }

  const count = small ? 600 : 1400
  const dust = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    const u = Math.random() * Math.PI * 2
    const v = Math.random() * Math.PI * 2
    const tube = 0.3 + Math.random() * 1.1
    dust[i * 3] = (2.6 + tube * Math.cos(v)) * Math.cos(u)
    dust[i * 3 + 1] = (2.6 + tube * Math.cos(v)) * Math.sin(u)
    dust[i * 3 + 2] = tube * Math.sin(v)
  }
  const dustGeometry = new BufferGeometry()
  dustGeometry.setAttribute("position", new BufferAttribute(dust, 3))
  geometries.push(dustGeometry)
  const dustMaterial = new PointsMaterial({
    color: ACID,
    size: 0.03,
    transparent: true,
    opacity: 0.65,
    blending: AdditiveBlending,
    depthWrite: false,
  })
  const dustCloud = new Points(dustGeometry, dustMaterial)
  sculpture.add(dustCloud)

  let elapsed = 0
  const draw = () => {
    sculpture.rotation.z = -0.4 + elapsed * 0.05
    sculpture.rotation.x = 1.08 + Math.sin(elapsed * 0.22) * 0.07
    dustCloud.rotation.z = elapsed * -0.035
    renderer.render(scene, camera)
  }

  const resize = () => {
    const width = canvas.clientWidth
    const height = canvas.clientHeight
    if (!width || !height) return
    renderer.setSize(width, height, false)
    camera.aspect = width / height
    camera.updateProjectionMatrix()
    draw()
  }
  const resizer = new ResizeObserver(resize)
  resizer.observe(canvas)
  resize()

  let frame = 0
  let last = 0
  const tick = (now: number) => {
    // Clamp so a long background stall resumes smoothly instead of jumping.
    elapsed += Math.min(now - last, 50) / 1000
    last = now
    draw()
    frame = requestAnimationFrame(tick)
  }

  canvas.addEventListener("webglcontextlost", onLost)

  return {
    setRunning(running) {
      if (running && !frame) {
        last = performance.now()
        frame = requestAnimationFrame(tick)
      } else if (!running && frame) {
        cancelAnimationFrame(frame)
        frame = 0
      }
    },
    dispose() {
      cancelAnimationFrame(frame)
      frame = 0
      canvas.removeEventListener("webglcontextlost", onLost)
      resizer.disconnect()
      for (const geometry of geometries) geometry.dispose()
      lineMaterial.dispose()
      dustMaterial.dispose()
      renderer.dispose()
      renderer.forceContextLoss()
    },
  }
}
