// The first GitHub route answers of a fresh server on a warm cache, without a browser.
//
//   node explorations/performance-loop/pr-view-first-routes.mjs --metab BIN --checkout DIR \
//     --cache DIR --root DIR --pr N [--label L] [--out FILE.jsonl]
//
// Starts `metab <checkout> --no-open` on an existing cache (one pr-view.mjs left), waits for
// /api/tree, then asks what a pull request's page asks first, at once: GET pull?number=N,
// GET stacks, and GET pulls?state=open&limit=100; then each once more, serially. It records
// each answer's client time and Server-Timing. Nothing here asks GitHub: these GETs answer
// from the cache alone.
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";
import { sleep } from "./pr-cdp.mjs";

const { values: a } = parseArgs({
  options: {
    metab: { type: "string" },
    checkout: { type: "string" },
    cache: { type: "string" },
    root: { type: "string" },
    pr: { type: "string", default: "487" },
    label: { type: "string", default: "" },
    out: { type: "string" },
  },
});
for (const name of ["metab", "checkout", "cache", "root"]) {
  if (!a[name]) {
    throw new Error(`--${name} is required`);
  }
}
const metab = path.resolve(String(a.metab));
// A port nothing listens on now, from the kernel, so the run never reaches another server.
const port = await new Promise((resolve, reject) => {
  const probe = net.createServer();
  probe.once("error", reject);
  probe.listen(0, "127.0.0.1", () => {
    const { port: free } = /** @type {import("node:net").AddressInfo} */ (probe.address());
    probe.close(() => resolve(free));
  });
});
const origin = `http://127.0.0.1:${port}`;
const cfg = path.join(String(a.root), "cfg");
fs.mkdirSync(cfg, { recursive: true, mode: 0o700 });
const server = spawn(
  metab,
  [
    path.resolve(String(a.checkout)),
    "--no-open",
    "--port",
    String(port),
    "--cache-dir",
    String(a.cache),
  ],
  {
    detached: true,
    stdio: "ignore",
    env: { ...process.env, METABROWSER_CACHE_DIR: String(a.cache), METABROWSER_CONFIG_DIR: cfg },
  },
);
const timing = (h) =>
  Object.fromEntries(
    (h || "")
      .split(",")
      .map((p) => p.trim().split(";"))
      .filter(([n]) => n)
      .map(([n, ...rest]) => [
        n,
        Number((rest.find((r) => r.trim().startsWith("dur=")) || "dur=").split("=")[1]),
      ]),
  );
async function get(p) {
  const t0 = performance.now();
  const r = await fetch(`${origin}${p}`, { headers: { "accept-encoding": "gzip" } });
  await r.arrayBuffer();
  return {
    path: p,
    status: r.status,
    ms: Math.round(performance.now() - t0),
    timing: timing(r.headers.get("server-timing")),
  };
}
const out = {
  label: a.label,
  version: execFileSync(metab, ["--version"]).toString().trim(),
  load: os.loadavg()[0],
  started: new Date().toISOString(),
};
try {
  const t0 = Date.now();
  for (let i = 0; i < 600; i++) {
    try {
      if ((await fetch(`${origin}/api/tree?depth=1`)).ok && server.exitCode === null) {
        break;
      }
    } catch {}
    if (server.exitCode !== null) {
      throw new Error(`the server exited with status ${server.exitCode}`);
    }
    await sleep(100);
  }
  out.ready_ms = Date.now() - t0;
  const paths = [
    `/api/plugin/github/pull?number=${a.pr}`,
    "/api/plugin/github/stacks",
    "/api/plugin/github/pulls?state=open&limit=100",
  ];
  out.first = await Promise.all(paths.map(get));
  out.again = [];
  for (const p of paths) {
    out.again.push(await get(p));
  }
} finally {
  try {
    process.kill(-server.pid, "SIGTERM");
  } catch {}
}
if (a.out) {
  fs.appendFileSync(String(a.out), `${JSON.stringify(out)}\n`);
}
console.log(
  `${out.label} load=${out.load.toFixed(1)} first: ${out.first.map((x) => `${x.path.split("/").pop().slice(0, 14)} ${x.ms}ms srv=${x.timing.srv}`).join(", ")} | again: ${out.again.map((x) => x.ms).join(", ")}`,
);
