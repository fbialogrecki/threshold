export type QrState = {
  generation: number
  status: "idle" | "loading" | "ready" | "error" | "expired"
  token: string
  expiresAt: string
}

export type QrAction =
  | { type: "begin"; generation: number }
  | { type: "resolve"; generation: number; token: string; expiresAt: string }
  | { type: "reject"; generation: number }
  | { type: "clear"; generation: number }
  | { type: "expire"; generation: number }

export const initialQrState: QrState = {
  generation: 0,
  status: "idle",
  token: "",
  expiresAt: "",
}

export function qrExpired(expiresAt: string, now = Date.now()): boolean {
  const expires = new Date(expiresAt).getTime()
  return !Number.isFinite(expires) || expires <= now
}

export function qrExpiryDelay(expiresAt: string, now = Date.now()): number {
  return Math.max(0, new Date(expiresAt).getTime() - now)
}

export function qrReducer(state: QrState, action: QrAction): QrState {
  if (action.type === "begin") {
    return { generation: action.generation, status: "loading", token: "", expiresAt: "" }
  }
  if (action.type === "clear") {
    return { generation: action.generation, status: "idle", token: "", expiresAt: "" }
  }
  if (action.generation !== state.generation) return state
  if (action.type === "resolve") {
    return {
      generation: action.generation,
      status: "ready",
      token: action.token,
      expiresAt: action.expiresAt,
    }
  }
  return {
    generation: state.generation,
    status: action.type === "expire" ? "expired" : "error",
    token: "",
    expiresAt: "",
  }
}
