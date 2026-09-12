import { expect, test } from "bun:test"
test("unblock BFF rejects cross-origin and anonymous calls and forwards canonical DELETE", async () => {
  const child = Bun.spawn([process.execPath, "-e", `
    import { mock, expect } from 'bun:test';
    let origin = false, authenticated = false, calls = 0;
    mock.module('@/lib/http/guard', () => ({ assertSameOrigin: async () => origin, requireSession: async () => ({authenticated}) }));
    mock.module('@/lib/auth/product-auth', () => ({ unblockUser: async username => { expect(username).toBe('Żaba'); calls++; return {status:204,body:null}; } }));
    const { DELETE } = await import('./src/app/api/blocks/[username]/route');
    const run = () => DELETE(new Request('http://localhost/api/blocks/Żaba', {method:'DELETE'}), {params:Promise.resolve({username:'Żaba'})});
    expect((await run()).status).toBe(403); expect(calls).toBe(0);
    origin = true; expect((await run()).status).toBe(401); expect(calls).toBe(0);
    authenticated = true; const response = await run(); expect(response.status).toBe(204); expect(await response.text()).toBe(''); expect(calls).toBe(1);
  `], { stdout: "pipe", stderr: "pipe" })
  expect(await child.exited, await new Response(child.stderr).text()).toBe(0)
})
