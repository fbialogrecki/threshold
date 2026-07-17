export type GuardedUsernameResult<I, U> =
  | { kind: "blocked"; response: Response }
  | { kind: "invalid" }
  | { kind: "notFound" }
  | { kind: "resolved"; input: I; user: U }

export async function guardThenResolveUsername<I, U>({
  guard,
  read,
  username,
  resolve,
}: {
  guard: () => Promise<Response | null>
  read: () => Promise<I | null>
  username: (input: I) => string | null
  resolve: (value: string) => Promise<U | null>
}): Promise<GuardedUsernameResult<I, U>> {
  const blocked = await guard()
  if (blocked) return { kind: "blocked", response: blocked }
  const input = await read()
  if (!input) return { kind: "invalid" }
  const value = username(input)?.trim()
  if (!value) return { kind: "invalid" }
  const user = await resolve(value)
  return user ? { kind: "resolved", input, user } : { kind: "notFound" }
}
