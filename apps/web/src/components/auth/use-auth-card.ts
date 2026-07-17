"use client"

import { useTranslations } from "next-intl"
import { useRouter } from "next/navigation"
import { type FormEvent, useState } from "react"

import {
  authenticatedHref,
  onboardingHref,
} from "@/lib/auth/routing"
import { validateRegistration } from "@/lib/validation"

type Mode = "login" | "register"
type ErrorField = "username" | "email" | "password" | "credentials" | null

export function useAuthCard({
  initialMode,
  callbackUrl,
}: {
  initialMode: Mode
  callbackUrl: string
}) {
  const router = useRouter()
  const t = useTranslations("authFlow.errors")
  const [mode, setMode] = useState<Mode>(initialMode)
  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [errorField, setErrorField] = useState<ErrorField>(null)
  const [loading, setLoading] = useState(false)

  const isRegister = mode === "register"

  function switchMode(next: Mode) {
    setMode(next)
    setError(null)
    setErrorField(null)
    setPassword("")
  }

  function clearFieldError(field: Exclude<ErrorField, "credentials" | null>) {
    if (errorField === field || errorField === "credentials") setErrorField(null)
  }

  async function credentialsLogin(target: string) {
    let res: Response
    try {
      res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          emailOrUsername: username.trim().toLowerCase(),
          password,
        }),
      })
    } catch {
      setError(t("network"))
      setErrorField(null)
      return false
    }
    if (!res.ok) {
      setError(
        res.status === 401
          ? t("invalidCredentials")
          : res.status === 429
            ? t("rateLimited")
            : t("serviceUnavailable"),
      )
      setErrorField(res.status === 401 ? "credentials" : null)
      return false
    }
    const session = (await res.json().catch(() => ({}))) as Parameters<
      typeof authenticatedHref
    >[0]
    router.push(authenticatedHref(session, target))
    router.refresh()
    return true
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setErrorField(null)
    setLoading(true)
    try {
      if (isRegister) {
        const check = validateRegistration({ username, email, password })
        if (!check.ok) {
          setError(t(check.error))
          setErrorField(
            check.error === "username" || check.error === "reservedUsername"
              ? "username"
              : check.error === "email"
                ? "email"
                : check.error === "displayName"
                  ? null
                  : "password",
          )
          return
        }
        let res: Response
        try {
          res = await fetch("/api/auth/register", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ username, email, password }),
          })
        } catch {
          setError(t("network"))
          return
        }
        if (!res.ok) {
          setError(
            res.status === 409
              ? t("accountExists")
              : res.status === 429
                ? t("rateLimited")
                : res.status === 422
                  ? t("password")
                  : t("serviceUnavailable"),
          )
          setErrorField(
            res.status === 422
              ? "password"
              : res.status === 409
                ? "username"
                : null,
          )
          return
        }
        router.push(onboardingHref(callbackUrl))
        router.refresh()
        return
      }

      await credentialsLogin(callbackUrl)
    } finally {
      setLoading(false)
    }
  }

  return {
    mode,
    isRegister,
    username,
    setUsername,
    email,
    setEmail,
    password,
    setPassword,
    error,
    errorField,
    loading,
    clearFieldError,
    switchMode,
    onSubmit,
  }
}
