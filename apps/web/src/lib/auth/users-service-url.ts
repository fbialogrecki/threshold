export class UsersServiceConfigurationError extends Error {
  constructor(message = "USERS_SERVICE_URL is not configured") {
    super(message)
    this.name = "UsersServiceConfigurationError"
  }
}

export function resolveUsersServiceUrl(value: string | undefined): string {
  if (!value?.trim()) {
    throw new UsersServiceConfigurationError()
  }
  return value.replace(/\/$/, "")
}
