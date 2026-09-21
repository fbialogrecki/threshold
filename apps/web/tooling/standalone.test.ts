import { afterEach, expect, test } from "bun:test";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import pkg from "../package.json";

const roots: string[] = [];
function fixture() {
  const root = mkdtempSync(join(tmpdir(), "web-standalone-test-"));
  roots.push(root);
  writeFileSync(join(root, "package.json"), JSON.stringify({ scripts: pkg.scripts }));
  return root;
}
function write(root: string, path: string, content: string) {
  const target = join(root, path);
  mkdirSync(join(target, ".."), { recursive: true });
  writeFileSync(target, content);
}
function start(root: string) {
  return Bun.spawnSync([process.execPath, "run", "start"], {
    cwd: root,
    env: { PATH: process.env.PATH!, NODE_ENV: "production", AUTH_COOKIE_SECURE: "true" },
    timeout: 5000,
  });
}
afterEach(() => {
  for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

test("start executes the generated standalone entrypoint with Bun", () => {
  const root = fixture();
  write(root, ".next/standalone/server.js", 'console.log(`standalone:${!!process.versions.bun}`);');
  const result = start(root);
  expect(result.stderr.toString()).not.toContain("Module not found");
  expect(result.exitCode).toBe(0);
  expect(result.stdout.toString().trim()).toBe("standalone:true");
});

function prepare(root: string) {
  return Bun.spawnSync([process.execPath, join(import.meta.dir, "prepare-standalone.ts")], {
    cwd: root,
    env: { PATH: process.env.PATH! },
    timeout: 5000,
  });
}

test("packaging copies static assets into standalone without requiring public", () => {
  const root = fixture();
  write(root, ".next/standalone/server.js", "// generated entrypoint");
  write(root, ".next/static/chunks/app.js", "static fixture");
  const result = prepare(root);
  expect(result.exitCode).toBe(0);
  expect(readFileSync(join(root, ".next/standalone/.next/static/chunks/app.js"), "utf8")).toBe("static fixture");
});

test("packaging includes optional public files", () => {
  const root = fixture();
  write(root, ".next/standalone/server.js", "// generated entrypoint");
  write(root, ".next/static/chunks/app.js", "static fixture");
  write(root, "public/nested/fixture.txt", "public fixture");
  expect(prepare(root).exitCode).toBe(0);
  expect(readFileSync(join(root, ".next/standalone/public/nested/fixture.txt"), "utf8")).toBe("public fixture");
});

test("packaging rejects a missing generated server", () => {
  const root = fixture();
  write(root, ".next/static/chunks/app.js", "static fixture");
  expect(prepare(root).exitCode).not.toBe(0);
});

test("packaging rejects missing static output", () => {
  const root = fixture();
  write(root, ".next/standalone/server.js", "// generated entrypoint");
  expect(prepare(root).exitCode).not.toBe(0);
});

test("repackaging removes obsolete assets, including a removed public directory", () => {
  const root = fixture();
  write(root, ".next/standalone/server.js", "// generated entrypoint");
  write(root, ".next/static/chunks/app.js", "static fixture");
  write(root, "public/fixture.txt", "public fixture");
  expect(prepare(root).exitCode).toBe(0);
  rmSync(join(root, "public"), { recursive: true });
  rmSync(join(root, ".next/static/chunks/app.js"));
  write(root, ".next/static/chunks/new.js", "new fixture");
  expect(prepare(root).exitCode).toBe(0);
  expect(existsSync(join(root, ".next/standalone/public"))).toBe(false);
  expect(existsSync(join(root, ".next/standalone/.next/static/chunks/app.js"))).toBe(false);
  expect(readFileSync(join(root, ".next/standalone/.next/static/chunks/new.js"), "utf8")).toBe("new fixture");
});

test("build prepares assets only after a successful Next build", () => {
  expect(pkg.scripts.build).toBe("bun --bun next build && bun tooling/prepare-standalone.ts");
});

test("start fails without a built artifact instead of rebuilding", () => {
  const result = start(fixture());
  expect(result.exitCode).not.toBe(0);
  expect(result.stderr.toString()).toContain("Module not found");
});
