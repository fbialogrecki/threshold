import { expect, test } from "bun:test"
import { renderToStaticMarkup } from "react-dom/server"
import { NextIntlClientProvider } from "next-intl"
import { AppRouterContext } from "next/dist/shared/lib/app-router-context.shared-runtime"
import { SafetyActions } from "../safety-actions"
import en from "../../../../messages/en.json"
import pl from "../../../../messages/pl.json"
const router = { bfcacheId: "test", push() {}, refresh() {}, replace() {}, back() {}, forward() {}, prefetch() {} }
function render(allowed: boolean, blocked: boolean | null, messages = en) {
  return renderToStaticMarkup(<AppRouterContext.Provider value={router}><NextIntlClientProvider locale="en" timeZone="UTC" messages={messages}><SafetyActions allowed={allowed} target={{ type: "profile", target: "Other" }} username="Other" initialBlocked={blocked} /></NextIntlClientProvider></AppRouterContext.Provider>)
}
test("self/anonymous actions render nothing", () => { expect(render(false, false)).toBe("") })
test("safety disclosure is discoverable and canonical blocked state offers reversal in EN/PL", () => {
  expect(render(true, true)).toContain("Unblock account")
  expect(render(true, false)).toContain("Block account")
  expect(render(true, true, pl)).toContain("Odblokuj konto")
  expect(render(true, false)).toContain("Report")
  expect(render(true, null)).toContain("Could not load block status")
})
