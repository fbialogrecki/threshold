import { describe, expect, it } from "bun:test"

import { buildProfilePayload } from "@/lib/settings/profile"

const values = {
  displayName: " DJ One ",
  username: " dj-one ",
  bio: " bio ",
  city: "Warsaw",
  avatarMediaAssetId: "",
}

describe("buildProfilePayload", () => {
  it("omits an empty or unchanged avatar id", () => {
    expect(buildProfilePayload(values, "")).toEqual({
      display_name: "DJ One",
      username: "dj-one",
      bio: "bio",
      city: "Warsaw",
    })
    expect(buildProfilePayload({ ...values, avatarMediaAssetId: "asset-1" }, "asset-1"))
      .not.toHaveProperty("avatar_media_asset_id")
  })

  it("includes a newly uploaded avatar id", () => {
    expect(buildProfilePayload({ ...values, avatarMediaAssetId: " asset-2 " }, "asset-1"))
      .toHaveProperty("avatar_media_asset_id", "asset-2")
  })
})
