// The gate's static server: the committed diff benchmark pages and the files they load,
// the generated corpus, and a blank page, on loopback. It serves those files and nothing
// else in the checkout, each only while its real path stays under its own root, and only
// to requests addressed to its own 127.0.0.1 origin. Every failure inside a request,
// from a malformed path to a file that cannot be read, becomes an error response, never an
// exception that would end the harness. static-server.test.mjs covers it.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { pipeline } from "node:stream";

/** @typedef {import("./processes.mjs").Cleanup} Cleanup */

/**
 * The files the committed diff benchmark pages load, relative to the checkout: the pages
 * themselves (run.mjs's diff-layout and diff-intraline cases), their stylesheets, and the
 * modules they import. static-server.test.mjs follows the pages' imports and fails if this
 * list misses a file or names one they do not load.
 */
export const BENCHMARK_ASSETS = Object.freeze([
  "explorations/diff-intraline/benchmark.html",
  "explorations/diff-layout/benchmark.html",
  "src/metabrowser/builtin_plugins/diff/diff-intraline.js",
  "src/metabrowser/builtin_plugins/diff/diff-model.js",
  "src/metabrowser/builtin_plugins/diff/diff-render-model.js",
  "src/metabrowser/builtin_plugins/diff/diff-syntax.js",
  "src/metabrowser/builtin_plugins/diff/diff-view.js",
  "src/metabrowser/builtin_plugins/diff/styles.css",
  "src/metabrowser/static/styles.css",
]);

const BLANK_PAGE = "/__gate/blank.html";
const CORPUS_PREFIX = "/__gate/corpus/";

/** @type {Record<string, string>} */
const MIME = {
  ".css": "text/css",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".json": "application/json",
  ".mjs": "text/javascript",
};

/**
 * Ends `response` with `status` and no body, or, once a body has begun, cuts it off.
 * @param {http.ServerResponse} response
 * @param {number} status
 */
function refuse(response, status) {
  if (response.headersSent) {
    response.destroy();
    return;
  }
  response.writeHead(status, { "cache-control": "no-store", "content-length": 0 }).end();
}

/**
 * Starts the server on a free loopback port, closed by `cleanup` from the moment it is
 * created. `assets` are checkout-relative paths under `root`; `corpusFiles` are names
 * under `corpus`, served at /__gate/corpus/NAME.
 * @param {{
 *   root: string, assets: readonly string[], corpus: string,
 *   corpusFiles: readonly string[], cleanup: Cleanup
 * }} options
 * @returns {Promise<{ origin: string, server: http.Server }>}
 */
export async function startStatic({ root, assets, corpus, corpusFiles, cleanup }) {
  // Each URL path names one file under one root; anything else is not found. The roots'
  // real paths are taken once, and a file is served only if its own stays inside.
  const [realRoot, realCorpus] = await Promise.all([
    fs.promises.realpath(root),
    fs.promises.realpath(corpus),
  ]);
  /** @type {Map<string, { base: string, name: string }>} */
  const files = new Map([
    ...assets.map((name) => /** @type {const} */ ([`/${name}`, { base: realRoot, name }])),
    ...corpusFiles.map(
      (name) => /** @type {const} */ ([`${CORPUS_PREFIX}${name}`, { base: realCorpus, name }]),
    ),
  ]);
  let host = "";

  /**
   * @param {http.IncomingMessage} request
   * @param {http.ServerResponse} response
   */
  async function serve(request, response) {
    // The two engines address it as http://127.0.0.1:PORT; a request naming any other
    // host, as a page on another origin can make a browser send, is not for this server.
    if (request.headers.host !== host) {
      refuse(response, 421);
      return;
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      refuse(response, 405);
      return;
    }
    // Matched as sent, not decoded: every served path is plain ASCII, so a malformed
    // escape such as `/%` is just a path that names nothing.
    const { pathname } = new URL(request.url ?? "/", "http://127.0.0.1");
    if (pathname === BLANK_PAGE) {
      response.writeHead(200, { "cache-control": "no-store", "content-type": MIME[".html"] });
      response.end(request.method === "HEAD" ? undefined : "<!doctype html><title>blank</title>");
      return;
    }
    const entry = files.get(pathname);
    if (!entry) {
      refuse(response, 404);
      return;
    }
    const real = await fs.promises.realpath(path.join(entry.base, entry.name));
    if (!real.startsWith(`${entry.base}${path.sep}`)) {
      refuse(response, 404);
      return;
    }
    const handle = await fs.promises.open(real, "r");
    const stat = await handle.stat().catch(async (error) => {
      await handle.close();
      throw error;
    });
    if (!stat.isFile()) {
      await handle.close();
      refuse(response, 404);
      return;
    }
    response.writeHead(200, {
      "cache-control": "no-store",
      "content-length": stat.size,
      "content-type": MIME[path.extname(real)] || "application/octet-stream",
    });
    if (request.method === "HEAD") {
      await handle.close();
      response.end();
      return;
    }
    // A read that fails partway cuts the response off; pipeline closes the file either way.
    pipeline(handle.createReadStream(), response, (error) => {
      if (error) {
        response.destroy();
      }
    });
  }

  const server = http.createServer((request, response) => {
    serve(request, response).catch((error) => {
      // A file that is gone or unreadable is an answer, not a crash.
      refuse(response, error?.code === "ENOENT" || error?.code === "ENOTDIR" ? 404 : 500);
    });
  });
  // A client that drops its connection mid-request is no error of the server's.
  server.on("clientError", (_error, socket) => socket.destroy());
  cleanup.add(
    () =>
      /** @type {Promise<void>} */ (
        new Promise((resolve) => {
          // A browser's idle keep-alive connections would hold close() open.
          server.closeAllConnections();
          server.close(() => resolve());
        })
      ),
  );
  /** @type {Promise<void>} */
  const listening = new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve());
  });
  await listening;
  // A server listening on a TCP port reports its address as an AddressInfo.
  const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
  host = `127.0.0.1:${port}`;
  return { origin: `http://${host}`, server };
}
