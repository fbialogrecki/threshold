import { expect, test } from "bun:test"

import { emptyFeedActions } from "../empty-actions"

test("a known city and scenes lead to the city group, a scene search and city events", () => {
  expect(emptyFeedActions("Warszawa", ["techno", "ebm"])).toEqual([
    { key: "suggestionCityGroup", values: { city: "Warszawa" }, href: "/groups" },
    { key: "suggestionScenes", values: { scenes: "techno / ebm" }, href: "/app/search?q=%23techno" },
    { key: "suggestionCityEvents", values: { city: "Warszawa" }, href: "/app/events" },
  ])
})

test("without preferences every action still points at a real route", () => {
  expect(emptyFeedActions(null, []).map((action) => [action.key, action.href])).toEqual([
    ["suggestionAnyCityGroup", "/groups"],
    ["suggestionFollows", "/app/search"],
    ["suggestionEvents", "/app/events"],
  ])
})
