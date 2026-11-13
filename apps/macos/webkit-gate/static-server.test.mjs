// The gate's static server against a scratch checkout: what it serves, what it refuses,
// and that a bad request or an unreadable file leaves it serving. `make test` in
// apps/macos runs it with `node --test`.
import assert from "node:assert/strict";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { Cleanup } from "./processes.mjs";
import * as server from "./static-server.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const work = fs.mkdtempSync(path.join(os.tmpdir(), "webkit-gate-static-"));
const root = path.join(work, "root");
const corpus = path.join(work, "corpus");
const outside = path.join(work, "outside");

/**
 * @param {string} file
 * @param {string} text
 */
function write(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
}

write(path.join(root, "explorations/bench/benchmark.html"), "<!doctype html><p>bench</p>");
write(path.join(root, "src/app.js"), "export const app = 1;\n");
write(path.join(root, ".env"), "TOKEN=hidden\n");
write(path.join(root, "notes.txt"), "not listed\n");
write(path.join(root, "unreadable.js"), "export {};\n");
write(path.join(root, "src/swap.js"), "export const swap = 1;\n");
write(path.join(root, "swapdir/file.js"), "export const file = 1;\n");
write(path.join(root, "elsewhere/file.js"), "elsewhere, not listed\n");
write(path.join(outside, "secret.txt"), "outside the root\n");
write(path.join(corpus, "source.txt"), "corpus\n");
fs.symlinkSync(outside, path.join(root, "escape"));
fs.symlinkSync(path.join(outside, "secret.txt"), path.join(corpus, "leak.txt"));
fs.symlinkSync("../notes.txt", path.join(root, "src/alias.js"));

const assets = [
  "explorations/bench/benchmark.html",
  "src/app.js",
  "escape/secret.txt",
  "unreadable.js",
  "src/alias.js",
  "src/swap.js",
  "swapdir/file.js",
];
const corpusFiles = ["source.txt", "leak.txt"];

const cleanup = new Cleanup();
/** @type {string} */
let origin = "";
before(async () => {
  ({ origin } = await server.startStatic({ root, assets, corpus, corpusFiles, cleanup }));
  // Readable when the server starts, so it is a listed file that later cannot be read.
  fs.chmodSync(path.join(root, "unreadable.js"), 0o000);
});
after(async () => {
  await cleanup.run();
  fs.chmodSync(path.join(root, "unreadable.js"), 0o600);
  fs.rmSync(work, { recursive: true, force: true });
});

/**
 * One request on a fresh connection; `host` replaces the Host header.
 * @param {string} base
 * @param {string} pathname
 * @param {{ host?: string, method?: string }} [options]
 * @returns {Promise<{ status: number, type: string, body: string }>}
 */
function request(base, pathname, { host, method = "GET" } = {}) {
  const url = new URL(base);
  return new Promise((resolve, reject) => {
    const outgoing = http.request(
      {
        host: url.hostname,
        port: url.port,
        path: pathname,
        method,
        agent: false,
        headers: host ? { host } : {},
      },
      (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", () =>
          resolve({
            status: response.statusCode ?? 0,
            type: String(response.headers["content-type"] ?? ""),
            body,
          }),
        );
      },
    );
    outgoing.on("error", reject);
    outgoing.end();
  });
}

test("serves each listed asset, each corpus file, and the blank page", async () => {
  const page = await request(origin, "/explorations/bench/benchmark.html");
  assert.equal(page.status, 200);
  assert.match(page.type, /^text\/html/);
  assert.equal((await request(origin, "/src/app.js")).body, "export const app = 1;\n");
  assert.equal((await request(origin, "/__gate/corpus/source.txt")).body, "corpus\n");
  assert.equal((await request(origin, "/__gate/blank.html")).status, 200);
});

test("refuses a hidden or unlisted file", async () => {
  for (const pathname of ["/.env", "/notes.txt", "/src/", "/__gate/corpus/../notes.txt"]) {
    assert.equal((await request(origin, pathname)).status, 404, pathname);
  }
});

test("refuses a listed path that a symlink takes outside its root", async () => {
  for (const pathname of ["/escape/secret.txt", "/__gate/corpus/leak.txt"]) {
    const answer = await request(origin, pathname);
    assert.equal(answer.status, 404, pathname);
    assert.doesNotMatch(answer.body, /outside the root/, pathname);
  }
});

test("refuses a listed path that a symlink in its root points at an unlisted file", async () => {
  const answer = await request(origin, "/src/alias.js");
  assert.equal(answer.status, 404);
  assert.doesNotMatch(answer.body, /not listed/);
});

test("refuses a listed file, or one in a listed directory, replaced after it was checked", async () => {
  // The server checks each file when it starts, so replacing one now falls between that
  // check and the open, every time.
  for (const pathname of ["/src/swap.js", "/swapdir/file.js"]) {
    assert.equal((await request(origin, pathname)).status, 200, `${pathname} before`);
  }
  fs.rmSync(path.join(root, "src/swap.js"));
  fs.symlinkSync("../notes.txt", path.join(root, "src/swap.js"));
  fs.renameSync(path.join(root, "swapdir"), path.join(root, "swapdir-checked"));
  fs.symlinkSync("elsewhere", path.join(root, "swapdir"));
  for (const pathname of ["/src/swap.js", "/swapdir/file.js"]) {
    const answer = await request(origin, pathname);
    assert.equal(answer.status, 404, pathname);
    assert.doesNotMatch(answer.body, /not listed/, pathname);
  }
});

test("refuses a request for any host but its own loopback address", async () => {
  const port = new URL(origin).port;
  for (const host of ["evil.example", `evil.example:${port}`, `localhost:${port}`]) {
    assert.equal((await request(origin, "/src/app.js", { host })).status, 421, host);
  }
  assert.equal((await request(origin, "/src/app.js", { host: `127.0.0.1:${port}` })).status, 200);
});

test("refuses a method other than GET and HEAD", async () => {
  assert.equal((await request(origin, "/src/app.js", { method: "POST" })).status, 405);
  const head = await request(origin, "/src/app.js", { method: "HEAD" });
  assert.equal(head.status, 200);
  assert.equal(head.body, "");
});

test("answers a malformed path and keeps serving", async () => {
  for (const pathname of ["/%", "/%E0%A4%A", "/src/%"]) {
    const status = (await request(origin, pathname)).status;
    assert.ok(status === 400 || status === 404, `${pathname}: ${status}`);
  }
  assert.equal((await request(origin, "/src/app.js")).status, 200);
});

test("answers a file it cannot read and keeps serving", {
  skip: process.getuid?.() === 0,
}, async () => {
  assert.equal((await request(origin, "/unreadable.js")).status, 500);
  assert.equal((await request(origin, "/src/app.js")).status, 200);
});

test("Cleanup closes it, so nothing keeps the harness open", async () => {
  const own = new Cleanup();
  const started = await server.startStatic({ root, assets, corpus, corpusFiles, cleanup: own });
  assert.equal((await request(started.origin, "/src/app.js")).status, 200);
  assert.deepEqual(await own.run(), []);
  assert.equal(started.server.listening, false);
  await assert.rejects(request(started.origin, "/src/app.js"), /ECONNREFUSED/);
});

/**
 * The checkout-relative files `file` loads: stylesheets, scripts, module imports, and
 * fetched files.
 * @param {string} file
 */
function loads(file) {
  const text = fs.readFileSync(path.join(ROOT, file), "utf8");
  const specifiers = [
    ...text.matchAll(
      /(?:href|src)="([^"]+)"|(?:\bfrom|^\s*import|\bfetch\(\s*)\s*["']([^"']+)["']/gm,
    ),
  ].map((match) => match[1] ?? match[2]);
  // A file the page loads is named by a path; prose such as `from "a filter"` is not.
  return specifiers
    .filter((specifier) => /^\.{0,2}\//.test(specifier))
    .map((specifier) =>
      specifier.startsWith("/")
        ? specifier.slice(1)
        : path.posix.normalize(path.posix.join(path.posix.dirname(file), specifier)),
    );
}

test("the asset list holds every file the benchmark pages load", () => {
  const listed = new Set(server.BENCHMARK_ASSETS);
  const pages = server.BENCHMARK_ASSETS.filter((name) => name.endsWith(".html"));
  assert.deepEqual(pages.sort(), [
    "explorations/diff-intraline/benchmark.html",
    "explorations/diff-layout/benchmark.html",
  ]);
  const queue = [...pages];
  const seen = new Set();
  for (let file = queue.shift(); file !== undefined; file = queue.shift()) {
    if (seen.has(file)) {
      continue;
    }
    seen.add(file);
    assert.ok(listed.has(file), `${file} is loaded but not in BENCHMARK_ASSETS`);
    queue.push(...loads(file));
  }
  assert.deepEqual([...listed].sort(), [...seen].sort(), "every listed file is loaded");
});
