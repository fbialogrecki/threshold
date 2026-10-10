import { describe, expect, test } from "bun:test"
import { NextIntlClientProvider } from "next-intl"
import { AppRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime"
import { renderToStaticMarkup } from "react-dom/server"

import { AuthCard } from "../auth-card"
import en from "../../../../messages/en.json"
import pl from "../../../../messages/pl.json"

const router = { bfcacheId: "test", push() {}, refresh() {}, replace() {}, back() {}, forward() {}, prefetch() {} }

function render(mode: "login" | "register", messages = en) {
  return renderToStaticMarkup(
    <AppRouterContext.Provider value={router}>
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}>
        <AuthCard initialMode={mode} callbackUrl="/app" />
      </NextIntlClientProvider>
    </AppRouterContext.Provider>,
  )
}

function input(html: string, id: string): string {
  return html.match(new RegExp(`<input[^>]*id="${id}"[^>]*>`))?.[0] ?? ""
}

describe("AuthCard", () => {
  test("register keeps the username policy, new-password hints and the journey", () => {
    for (const messages of [en, pl]) {
      const html = render("register", messages)
      const username = input(html, "auth-username")
      expect(username).toContain('maxLength="30"')
      expect(username).toContain('pattern="[A-Za-z0-9_.\\-ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]{3,30}"')
      expect(username).toContain('autoCapitalize="none"')
      expect(input(html, "auth-email")).toContain('type="email"')
      const password = input(html, "auth-password")
      expect(password).toContain('type="password"')
      expect(password).toContain('autoComplete="new-password"')
      expect(password).toContain('minLength="12"')
      expect(html).toContain('for="auth-username"')
      expect(html).toContain('aria-current="step"')
      expect(html).not.toContain('href="/reset-password"')
    }
  })

  test("login accepts email or nickname and offers recovery", () => {
    const html = render("login")
    const username = input(html, "auth-username")
    expect(username).not.toContain("pattern=")
    expect(username).toContain('maxLength="320"')
    expect(input(html, "auth-email")).toBe("")
    expect(input(html, "auth-password")).toContain('autoComplete="current-password"')
    expect(html).toContain('href="/reset-password"')
    expect(html).toContain('aria-pressed="true"')
    expect(html).not.toContain('aria-current="step"')
  })
})
