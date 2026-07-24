/*
  The username is the only public name a person has, so it keeps the case its
  owner types. The set is explicit rather than \p{L}: a broad class would admit
  Cyrillic and Greek lookalikes, which is the impersonation route the server's
  diacritic folding exists to close.
*/
export const USERNAME_PATTERN = "[A-Za-z0-9_.\\-ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,30}"
const USERNAME_RE = new RegExp(`^${USERNAME_PATTERN}$`)
const RESERVED_USERNAMES = new Set(["admin", "root", "support", "threshold"])

/** Mirrors `fold_username` in the users service: case and diacritics folded. */
function foldUsername(username: string): string {
  return username
    .trim()
    .toLowerCase()
    .replaceAll("ł", "l")
    .normalize("NFKD")
    .replace(/\p{Mn}/gu, "")
}
export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
export const MIN_PASSWORD = 12
export const MAX_PASSWORD = 1024

type RegistrationInput = {
  username: string
  email: string
  password: string
  displayName?: string
}

export type PasswordStrength = {
  /** 0 (empty) to 4 (strong). */
  score: number
  label: string
}

/**
 * Lightweight password strength heuristic for the registration UI. Not a
 * security control (the real minimum is enforced by validateRegistration); it
 * only nudges users toward stronger passwords.
 */
export function passwordStrength(password: string): PasswordStrength {
  if (!password) return { score: 0, label: "" }
  if (password.length < MIN_PASSWORD) return { score: 1, label: "Too short" }

  let points = 1
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) points++
  if (/\d/.test(password)) points++
  if (/[^A-Za-z0-9\s]/.test(password)) points++

  const score = Math.min(points, 4)
  const label = ["", "Weak", "Fair", "Good", "Strong"][score]
  return { score, label }
}

export type RegistrationCheck =
  | { ok: true; value: RegistrationInput }
  | {
      ok: false
      error:
        | "username"
        | "reservedUsername"
        | "email"
        | "passwordLength"
        | "passwordTooLong"
        | "passwordLowercase"
        | "passwordUppercase"
        | "passwordDigit"
        | "passwordSymbol"
        | "displayName"
    }

export type PasswordPolicyError =
  | "passwordLength"
  | "passwordTooLong"
  | "passwordLowercase"
  | "passwordUppercase"
  | "passwordDigit"
  | "passwordSymbol"

export function passwordPolicyError(
  password: string,
): PasswordPolicyError | null {
  if (password.length < MIN_PASSWORD) return "passwordLength"
  if (password.length > MAX_PASSWORD) return "passwordTooLong"
  if (!/[a-z]/.test(password)) return "passwordLowercase"
  if (!/[A-Z]/.test(password)) return "passwordUppercase"
  if (!/\d/.test(password)) return "passwordDigit"
  if (!/[^A-Za-z0-9\s]/.test(password)) return "passwordSymbol"
  return null
}

/**
 * Pure registration validation shared by the auth form and the BFF route, so
 * the server never trusts the client check alone.
 */
export function validateRegistration(raw: {
  username?: unknown
  email?: unknown
  password?: unknown
  displayName?: unknown
}): RegistrationCheck {
  const username = typeof raw.username === "string" ? raw.username.trim() : ""
  const email = typeof raw.email === "string" ? raw.email.trim() : ""
  const password = typeof raw.password === "string" ? raw.password : ""
  const displayName =
    typeof raw.displayName === "string" ? raw.displayName.trim() : ""

  if (!USERNAME_RE.test(username)) {
    return { ok: false, error: "username" }
  }
  // Folded before the check, so `ądmin` cannot claim the normalised `admin`.
  if (RESERVED_USERNAMES.has(foldUsername(username).replace(/^[_.-]+|[_.-]+$/g, ""))) {
    return { ok: false, error: "reservedUsername" }
  }
  if (!EMAIL_RE.test(email)) {
    return { ok: false, error: "email" }
  }
  const passwordError = passwordPolicyError(password)
  if (passwordError) return { ok: false, error: passwordError }
  if (displayName.length > 120) return { ok: false, error: "displayName" }

  return {
    ok: true,
    value: {
      username,
      email,
      password,
      displayName: displayName || undefined,
    },
  }
}
