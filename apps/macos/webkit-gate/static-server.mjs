// The gate's static server: the committed diff benchmark pages and the files they load,
// the generated corpus, and a blank page, on loopback. It serves those files and nothing
// else in the checkout, each only if what it opens is the very plain file, with no symlink
// on its path, that it found there when it started, and only to requests addressed to its
// own 127.0.0.1 origin. Every failure inside a request, from a malformed path to a file
// that cannot be read, becomes an error response, never an exception that would end the
// harness. static-server.test.mjs covers it.
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { pipeline } from "node:stream";

/** @typedef {import("./processes.mjs").Cleanup} Cleanup */

/**
 * The files the committed diff benchmark pages load, relative to the checkout: the pages
 * themselves (run.mjs's diff-layout and diff-intraline cases), their stylesheets, the
 * modules they import, and the diff corpus the layout page fetches. static-server.test.mjs
 * follows the pages' references and fails if this list misses a file or names one they
 * do not load.
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
  "src/metabrowser/data/file-diff-format/file-diff-conformance.json",
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

// Never through a final symlink, and without waiting on a FIFO put in a file's place.
const OPEN_FLAGS = fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK;

/**
 * Whether `error` is the operating system's, as a missing or unreadable file raises.
 * @param {unknown} error
 */
function isSystemError(error) {
  return (
    error instanceof Error &&
    typeof (/** @type {NodeJS.ErrnoException} */ (error).errno) === "number"
  );
}

/**
 * The device and inode of the plain file at `file`, or null if the server may not serve
 * it: `file` must be its own real path, with no symlink anywhere on it, and what an open
 * reaches must be what the path names. It opens first and checks after, so a symlink
 * swapped in or out between the two steps is caught either way.
 * @param {string} file an absolute path under a root's real path
 * @returns {Promise<{ dev: bigint, ino: bigint } | null>}
 */
async function identify(file) {
  /** @type {fs.promises.FileHandle | undefined} */
  let handle;
  try {
    handle = await fs.promises.open(file, OPEN_FLAGS);
    const opened = await handle.stat({ bigint: true });
    const real = await fs.promises.realpath(file);
    const named = await fs.promises.stat(file, { bigint: true });
    const same = named.dev === opened.dev && named.ino === opened.ino;
    return opened.isFile() && real === file && same ? { dev: opened.dev, ino: opened.ino } : null;
  } catch (error) {
    if (isSystemError(error)) {
      return null;
    }
    throw error;
  } finally {
    await handle?.close();
  }
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
  // Each URL path names one file under one root; anything else is not found. Each file is
  // identified once, here: one that is missing, is not a plain file, or has a symlink on
  // its path is never served, and one replaced while the run goes on is refused.
  const [realRoot, realCorpus] = await Promise.all([
    fs.promises.realpath(root),
    fs.promises.realpath(corpus),
  ]);
  /** @type {[string, string, string][]} URL path, root, and name under it */
  const listed = [
    ...assets.map((name) => /** @type {[string, string, string]} */ ([`/${name}`, realRoot, name])),
    ...corpusFiles.map(
      (name) =>
        /** @type {[string, string, string]} */ ([`${CORPUS_PREFIX}${name}`, realCorpus, name]),
    ),
  ];
  /** @type {Map<string, { file: string, dev: bigint, ino: bigint }>} */
  const files = new Map();
  await Promise.all(
    listed.map(async ([pathname, base, name]) => {
      const file = path.join(base, name);
      const identity = file.startsWith(`${base}${path.sep}`) ? await identify(file) : null;
      if (identity) {
        files.set(pathname, { file, ...identity });
      }
    }),
  );
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
    // The open does not follow a symlink put in the file's place, and the file it reaches
    // must be the one identified at startup, so a symlink put in place of a directory
    // above it, which the open does follow, reaches some other file and is refused.
    const handle = await fs.promises.open(entry.file, OPEN_FLAGS);
    const stat = await handle.stat({ bigint: true }).catch(async (error) => {
      await handle.close();
      throw error;
    });
    if (!stat.isFile() || stat.dev !== entry.dev || stat.ino !== entry.ino) {
      await handle.close();
      refuse(response, 404);
      return;
    }
    response.writeHead(200, {
      "cache-control": "no-store",
      "content-length": String(stat.size),
      "content-type": MIME[path.extname(entry.file)] || "application/octet-stream",
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
      // A file that is gone, unreadable, or now a symlink is an answer, not a crash.
      refuse(response, ["ENOENT", "ENOTDIR", "ELOOP"].includes(error?.code) ? 404 : 500);
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
