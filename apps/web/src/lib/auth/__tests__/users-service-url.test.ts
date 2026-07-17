import { describe, expect, it } from "bun:test"

import {
  resolveUsersServiceUrl,
  UsersServiceConfigurationError,
} from "@/lib/auth/users-service-url"

describe("users service URL config", () => {
  it("requires USERS_SERVICE_URL for product auth", () => {
    expect(() => resolveUsersServiceUrl(undefined)).toThrow(
      UsersServiceConfigurationError,
    )
    expect(() => resolveUsersServiceUrl("")).toThrow(
      UsersServiceConfigurationError,
    )
  })

  it("normalizes a configured users service URL", () => {
    expect(resolveUsersServiceUrl("http://users.example.test/")).toBe(
      "http://users.example.test",
    )
  })
})
