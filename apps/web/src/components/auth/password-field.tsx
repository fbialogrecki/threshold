"use client"

import { Eye, EyeSlash } from "@phosphor-icons/react"
import { useTranslations } from "next-intl"
import { useState } from "react"

import { Field, inputClass } from "@/components/ui/field"
import { cn } from "@/lib/cn"
import { passwordStrength } from "@/lib/validation"

const STRENGTH_KEY = ["tooShort", "tooShort", "fair", "good", "strong"] as const

/**
 * Password input with hold-to-reveal: the value is visible only while the
 * button is held (pointer or Enter/Space), so it never stays on screen.
 */
export function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
  showStrength,
  help,
  required,
  minLength,
  maxLength,
  ariaInvalid,
  errorId,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete: "current-password" | "new-password"
  showStrength?: boolean
  help?: string
  required?: boolean
  minLength?: number
  maxLength?: number
  ariaInvalid?: boolean
  errorId?: string
}) {
  const t = useTranslations("authFlow")
  const [reveal, setReveal] = useState(false)
  const strength = showStrength && value ? passwordStrength(value) : null
  const helpId = help ? `${id}-help` : undefined
  const strengthId = strength ? `${id}-strength` : undefined

  return (
    <Field htmlFor={id} label={label} hint={t("revealHint")} help={help} helpId={helpId}>
      <div className="relative">
        <input
          id={id}
          type={reveal ? "text" : "password"}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          required={required}
          minLength={minLength}
          maxLength={maxLength}
          aria-invalid={ariaInvalid || undefined}
          aria-describedby={[helpId, strengthId, errorId].filter(Boolean).join(" ") || undefined}
          className={cn(inputClass, "pr-12")}
        />
        <button
          type="button"
          aria-label={t("revealLabel")}
          aria-pressed={reveal}
          onPointerDown={(event) => {
            event.preventDefault()
            setReveal(true)
          }}
          onPointerUp={() => setReveal(false)}
          onPointerLeave={() => setReveal(false)}
          onPointerCancel={() => setReveal(false)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault()
              setReveal(true)
            }
          }}
          onKeyUp={(event) => {
            if (event.key === "Enter" || event.key === " ") setReveal(false)
          }}
          onBlur={() => setReveal(false)}
          className={cn(
            "absolute inset-y-1 right-1 grid w-10 place-items-center rounded-[0.5rem] transition-colors",
            reveal ? "bg-acid/15 text-acid" : "text-muted hover:text-raw-white",
          )}
        >
          {reveal ? <Eye size={18} aria-hidden /> : <EyeSlash size={18} aria-hidden />}
        </button>
      </div>
      {strength ? (
        <div id={strengthId} className="flex items-center gap-3">
          <div className="flex flex-1 gap-1" aria-hidden>
            {[1, 2, 3, 4].map((level) => (
              <span
                key={level}
                className={cn(
                  "h-1 flex-1 rounded-full transition-colors duration-300",
                  level > strength.score
                    ? "bg-border-gray"
                    : strength.score >= 3
                      ? "bg-acid"
                      : "bg-orange",
                )}
              />
            ))}
          </div>
          <span className="text-[13px] text-muted">
            {t("strength.label")}:{" "}
            <span className={strength.score >= 3 ? "text-acid" : "text-orange"}>
              {t(`strength.${STRENGTH_KEY[strength.score]}`)}
            </span>
          </span>
        </div>
      ) : null}
    </Field>
  )
}
