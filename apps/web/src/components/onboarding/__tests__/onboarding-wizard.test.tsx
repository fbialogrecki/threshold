import { expect, test } from "bun:test"
import { NextIntlClientProvider } from "next-intl"
import { AppRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime"
import { renderToStaticMarkup } from "react-dom/server"

import { OnboardingWizard } from "../onboarding-wizard"
import en from "../../../../messages/en.json"
import pl from "../../../../messages/pl.json"

const router = { bfcacheId: "test", push() {}, refresh() {}, replace() {}, back() {}, forward() {}, prefetch() {} }

function render(nickname: string, messages = en) {
  return renderToStaticMarkup(
    <AppRouterContext.Provider value={router}>
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}>
        <OnboardingWizard defaultNickname={nickname} />
      </NextIntlClientProvider>
    </AppRouterContext.Provider>,
  )
}

test("first step keeps the registered name in its own case and gates Next on the policy", () => {
  for (const messages of [en, pl]) {
    const valid = render("Żaba", messages)
    expect(valid).toContain('value="Żaba"')
    expect(valid).toContain('for="onboarding-nickname"')
    expect(valid).toContain('aria-current="step"')
    expect(valid).not.toContain('disabled=""')

    expect(render("Ża", messages)).toContain('disabled=""')
  }
})
