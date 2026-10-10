export type EmptyFeedAction =
  | { key: "suggestionCityGroup" | "suggestionCityEvents"; values: { city: string }; href: string }
  | { key: "suggestionScenes"; values: { scenes: string }; href: string }
  | { key: "suggestionAnyCityGroup" | "suggestionFollows" | "suggestionEvents"; href: string }

/**
 * Next steps for an empty Feed, each pointing at a real discovery route.
 * Scene preferences search by their first tag, the same `#tag` query tag
 * chips already link to.
 */
export function emptyFeedActions(city: string | null, scenes: string[]): EmptyFeedAction[] {
  return [
    city
      ? { key: "suggestionCityGroup", values: { city }, href: "/groups" }
      : { key: "suggestionAnyCityGroup", href: "/groups" },
    scenes.length > 0
      ? {
          key: "suggestionScenes",
          values: { scenes: scenes.join(" / ") },
          href: `/app/search?q=${encodeURIComponent(`#${scenes[0]}`)}`,
        }
      : { key: "suggestionFollows", href: "/app/search" },
    city
      ? { key: "suggestionCityEvents", values: { city }, href: "/app/events" }
      : { key: "suggestionEvents", href: "/app/events" },
  ]
}
