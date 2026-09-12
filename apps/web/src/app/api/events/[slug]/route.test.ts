import { expect, test } from "bun:test"

test("event PATCH delegates to the authenticated mutation proxy with encoded slug", async () => {
  // Module mocks run in a subprocess so other service-client tests retain real exports.
  const child = Bun.spawn([process.execPath, "-e", `
    import { mock, expect } from 'bun:test';
    mock.module('@/lib/events/client', () => ({ proxyEventsGet() {}, proxyEventsMutation: async (request, path, method) => {
      expect(path).toBe('/v1/events/a%2Fb'); expect(method).toBe('PATCH');
      expect(await request.json()).toEqual({title: 'Changed'});
      return Response.json({error: 'forbidden'}, {status: 403});
    }}));
    const { PATCH } = await import('./src/app/api/events/[slug]/route');
    expect(typeof PATCH).toBe('function');
    const response = await PATCH(new Request('http://localhost/api/events/a', {method:'PATCH', body:JSON.stringify({title:'Changed'})}), {params:Promise.resolve({slug:'a/b'})});
    expect(response.status).toBe(403);
  `], { stdout: "pipe", stderr: "pipe" })
  const stderr = await new Response(child.stderr).text()
  expect(await child.exited, stderr).toBe(0)
})
