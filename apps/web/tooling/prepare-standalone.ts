import { cpSync, existsSync, rmSync, statSync } from "node:fs";

if (!statSync(".next/standalone/server.js").isFile()) {
  throw new Error("Missing Next standalone server; run next build first");
}
if (!statSync(".next/static").isDirectory()) {
  throw new Error("Missing Next static assets; run next build first");
}

// Next's generated server serves assets from its own standalone directory.
// Replace rather than merge so removed assets cannot survive repackaging.
rmSync(".next/standalone/.next/static", { recursive: true, force: true });
cpSync(".next/static", ".next/standalone/.next/static", { recursive: true });
rmSync(".next/standalone/public", { recursive: true, force: true });
if (existsSync("public")) {
  cpSync("public", ".next/standalone/public", { recursive: true });
}
