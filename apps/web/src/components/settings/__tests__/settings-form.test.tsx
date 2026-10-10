import { expect, test } from "bun:test"
import { NextIntlClientProvider } from "next-intl"
import { AppRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime"
import { renderToStaticMarkup } from "react-dom/server"

import { SettingsForm } from "../settings-form"
import en from "../../../../messages/en.json"
import pl from "../../../../messages/pl.json"

const router = { bfcacheId: "test", push() {}, refresh() {}, replace() {}, back() {}, forward() {}, prefetch() {} }

function render(messages = en) {
  return renderToStaticMarkup(
    <AppRouterContext.Provider value={router}>
      <NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}>
        <SettingsForm
          initial={{
            username: "Żaba_92",
            displayName: "",
            bio: "",
            city: "Warsaw",
            avatarMediaAssetId: "",
            isArtist: false,
            role: "",
            location: "",
            links: [],
          }}
          notificationPreferences={{ status: "error" }}
        />
      </NextIntlClientProvider>
    </AppRouterContext.Provider>,
  )
}

test("identity keeps the stored username case and the delete confirmation starts closed", () => {
  for (const messages of [en, pl]) {
    const html = render(messages)
    expect(html).toContain('value="Żaba_92"')
    expect(html).toContain('maxLength="30"')
    // Erasure needs an explicit open step before the typed confirmation exists.
    expect(html).not.toContain('id="set-confirm-delete"')
    expect(html).toContain(messages.settings.account.deleteAction)
    expect(html).not.toContain(messages.settings.account.permanentDelete)
  }
})
