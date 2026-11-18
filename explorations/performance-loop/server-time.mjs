#!/usr/bin/env node
// server-time/3: the server's time over one landing, by phase.
//
//   node explorations/performance-loop/server-time.mjs --metab /path/to/metab \
//     --tree /path/to/folder [--path /view/README.md] [--warmup 0] \
//     [--out result.json] [--work .bench/server-time/run-1] [-- METAB_ARG...]
//   node explorations/performance-loop/server-time.mjs --summarize result.json
//
// It starts the build's `metab` on the tree with the verbose request log on, with
// --no-open and any arguments after `--` (`-- --exit-on-eof` starts it as the macOS app
// does), waits for the inventory, and loads the address in headless Chrome: `--warmup`
// unrecorded landings first (default 0, a cold server; a warm reading is labelled so),
// then one measured landing in a fresh profile and one reload of it. For every request
// the server answered in a window it reports the time the server was busy (the union of
// the requests' spans), each phase's total, and the summed latency, from the log, which
// is the one place the end of a streamed body is recorded; the `Server-Timing` headers
// the browser saw are summed beside it as the start-of-response view; and the server
// process's CPU time over the window. Then the measured landing's asset requests are
// fetched again, one at a time, with the Accept-Encoding Chrome sends: a warm serial
// reading, since the server has answered each once already. The record says which
// delivery the start produced, and labels an app's start that was sent gzip.
// See README.md, "Server Time over a Landing".
//
// Untimed by design: nothing here repeats, pairs, or compares. A round that judges a
// change runs it under its own protocol, back to back on both builds.
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";
import { buildProvenance, getJson, harnessProvenance } from "./provenance.mjs";
import {
  checkRecord,
  deliveryOf,
  formatRecord,
  INSTRUMENT,
  inFlight,
  landingAssets,
  parseCpuTime,
  parseLog,
  parseServerTiming,
  procStatTicks,
  SETTLING_EVENTS,
  serialAccount,
  splitAtArrival,
  wholeLinesLength,
  windowAccount,
} from "./server-time-sums.mjs";
import { launchBrowser, sleep } from "./transitions-recorder.mjs";

const REPO = path.resolve(import.meta.dirname, "../..");
const VIEWPORT = { width: 1440, height: 900 };
// Breaks a hung start or load; neither is a speed budget.
const INVENTORY_DEADLINE_MS = 180_000;
const LOAD_TIMEOUT_MS = 60_000;
// How long the network must stay idle, after the load event, for a landing to be over:
// long enough for the on-demand bundles that follow the first tree (shell tools, a
// view's plugin) to have started.
const QUIET_MS = 750;
// For the last log line of a body the browser has already received.
const LOG_SETTLE_MS = 250;
// What Chrome sends for a script on an http origin; the server tests it for "gzip".
const CHROME_ACCEPT_ENCODING = "gzip, deflate, br, zstd";

function usage(message) {
  if (message) {
    console.error(message);
  }
  console.error(
    "usage: server-time.mjs --metab PATH --tree DIR [--path ADDRESS] [--warmup N] " +
      "[--out FILE] [--work DIR] [-- METAB_ARG...]\n" +
      "       server-time.mjs --summarize FILE...",
  );
  process.exit(2);
}

const loadavg = () => os.loadavg().map((v) => Math.round(v * 100) / 100);

// --------------------------------------------------------------------------- server

function freePort() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

function killGroup(child, signal) {
  try {
    process.kill(-child.pid, signal);
  } catch (_error) {
    try {
      child.kill(signal);
    } catch (_ignored) {
      // Already gone.
    }
  }
}

const children = new Set();
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    for (const child of children) {
      killGroup(child, "SIGKILL");
    }
    process.exit(130);
  });
}

async function startServer({ metab, tree, work, serverArgs }) {
  const home = path.join(work, "home");
  const cache = path.join(home, "cache");
  const config = path.join(home, "config");
  fs.mkdirSync(cache, { recursive: true, mode: 0o700 });
  fs.mkdirSync(config, { recursive: true, mode: 0o700 });
  const logPath = path.join(work, "server.log");
  const port = await freePort();
  const fd = fs.openSync(logPath, "w", 0o600);
  let child;
  try {
    child = spawn(
      metab,
      [
        tree,
        "--no-open",
        "--port",
        String(port),
        "--cache-dir",
        cache,
        "--config-dir",
        config,
        ...serverArgs,
      ],
      {
        cwd: home,
        detached: true,
        // A pipe this process holds, as the macOS app holds its server's: a server given
        // --exit-on-eof stops when it closes, and any other ignores it.
        stdio: ["pipe", fd, fd],
        env: {
          ...process.env,
          METABROWSER_REQUEST_LOG: "verbose",
          METABROWSER_LOG_LEVEL: "INFO",
          METABROWSER_CACHE_DIR: cache,
          METABROWSER_CONFIG_DIR: config,
          METABROWSER_RECORD_RECENT: "0",
        },
      },
    );
  } finally {
    fs.closeSync(fd);
  }
  children.add(child);
  child.stdin?.on("error", () => {});
  child.on("exit", () => children.delete(child));
  const stop = async () => {
    if (child.exitCode !== null || child.signalCode !== null) {
      return;
    }
    killGroup(child, "SIGTERM");
    for (let i = 0; i < 50 && child.exitCode === null && child.signalCode === null; i++) {
      await sleep(100);
    }
    if (child.exitCode === null && child.signalCode === null) {
      killGroup(child, "SIGKILL");
    }
  };
  const deadline = Date.now() + INVENTORY_DEADLINE_MS;
  let base = null;
  try {
    while (Date.now() < deadline) {
      if (child.exitCode !== null || child.signalCode !== null) {
        throw new Error(`server exited: ${fs.readFileSync(logPath, "utf8").slice(-1500)}`);
      }
      // The port the server took: it walks upward from the one asked for when that is taken.
      base ??= /Serving .* at (http:\/\/[^/\s]+)/.exec(fs.readFileSync(logPath, "utf8"))?.[1];
      if (base) {
        try {
          const progress = await getJson(`${base}/api/index/progress`, 5000);
          if (progress.complete) {
            // What the server said it sends a loopback client, on the banner line a build
            // that has one prints after its address; null when it printed none.
            const said = /^Compression: (.*)$/m.exec(fs.readFileSync(logPath, "utf8"));
            const server = { child, base, logPath, stop, delivery: said?.[1].trim() ?? null };
            server.cursor = 0;
            readLog(server);
            return server;
          }
        } catch (_error) {
          // Not listening yet.
        }
      }
      await sleep(100);
    }
    throw new Error(`the inventory did not complete within ${INVENTORY_DEADLINE_MS / 1000} s`);
  } catch (error) {
    await stop();
    throw error;
  }
}

/**
 * The whole lines the server has logged since *server*'s cursor, which then moves past
 * them: a line still being written is left for the next read, and no line falls between
 * two windows (review C of #455, C2).
 */
function readLog(server) {
  const fd = fs.openSync(server.logPath, "r");
  try {
    const length = fs.fstatSync(fd).size - server.cursor;
    const buffer = Buffer.alloc(Math.max(0, length));
    const read = fs.readSync(fd, buffer, 0, buffer.length, server.cursor);
    const whole = wholeLinesLength(buffer.subarray(0, read));
    server.cursor += whole;
    return buffer.subarray(0, whole).toString("utf8");
  } finally {
    fs.closeSync(fd);
  }
}

// Clock ticks per second for /proc/<pid>/stat, asked once; 100 on every Linux this runs on.
let clockTicks = null;

/**
 * The process's user and system CPU time so far, in ms, or null: from /proc on Linux, and
 * from `ps -o time=` elsewhere, to the hundredth of a second on macOS. The process's own,
 * not its children's: a Git it ran is not counted.
 */
async function cpuMs(pid) {
  try {
    const ticks = procStatTicks(fs.readFileSync(`/proc/${pid}/stat`, "utf8"));
    if (ticks !== null) {
      clockTicks ??= Number(spawnSync("getconf", ["CLK_TCK"], { encoding: "utf8" }).stdout) || 100;
      return Math.round((ticks * 1000) / clockTicks);
    }
  } catch (_error) {
    // Not Linux: ask ps.
  }
  return new Promise((resolve) => {
    const ps = spawn("ps", ["-o", "time=", "-p", String(pid)], {
      stdio: ["ignore", "pipe", "ignore"],
    });
    let text = "";
    ps.stdout.on("data", (chunk) => {
      text += chunk;
    });
    ps.on("close", () => resolve(parseCpuTime(text)));
    ps.on("error", () => resolve(null));
  });
}

const cpuSpent = (before, after) => (before === null || after === null ? null : after - before);

function residentKb(pid) {
  try {
    const out = fs.readFileSync(`/proc/${pid}/status`, "utf8");
    return Number(/VmRSS:\s+(\d+)/.exec(out)?.[1] ?? NaN) || null;
  } catch (_error) {
    // Not Linux: ask ps.
  }
  return new Promise((resolve) => {
    const ps = spawn("ps", ["-o", "rss=", "-p", String(pid)], {
      stdio: ["ignore", "pipe", "ignore"],
    });
    let text = "";
    ps.stdout.on("data", (chunk) => {
      text += chunk;
    });
    ps.on("close", () => resolve(Number(text.trim()) || null));
    ps.on("error", () => resolve(null));
  });
}

// --------------------------------------------------------------------------- browser

// Resource Timing keeps 250 entries unless asked for more; a landing on a large folder
// can make that many.
const BUFFER_SOURCE = "performance.setResourceTimingBufferSize(5000);";

// The page's own record of what it fetched, and when DOMContentLoaded ended.
const READ_TIMING = `(() => {
  const nav = performance.getEntriesByType("navigation")[0];
  const dcl = nav ? nav.domContentLoadedEventEnd : null;
  const st = (e) => Object.fromEntries((e.serverTiming || []).map((s) => [s.name, s.duration]));
  const rows = performance.getEntriesByType("resource").map((e) => ({
    url: e.name, startTime: e.startTime, transferSize: e.transferSize,
    encodedBodySize: e.encodedBodySize, decodedBodySize: e.decodedBodySize,
    serverTiming: st(e), before_dcl: dcl === null ? null : e.startTime < dcl,
  }));
  if (nav) {
    rows.unshift({ url: nav.name, startTime: 0, transferSize: nav.transferSize,
      encodedBodySize: nav.encodedBodySize, decodedBodySize: nav.decodedBodySize,
      serverTiming: st(nav), before_dcl: true });
  }
  return JSON.stringify({ rows, dcl_ms: dcl, load_ms: nav ? nav.loadEventEnd : null });
})()`;

/** Navigate (or reload) and wait for the load event and then a quiet network. */
async function land(browser, go) {
  const from = browser.net.length;
  const loaded = browser.page.once("Page.loadEventFired", () => true, LOAD_TIMEOUT_MS);
  await go();
  const started = Date.now();
  let settled = false;
  let pending = [];
  try {
    await loaded;
    let quietSince = Date.now();
    while (Date.now() - started < LOAD_TIMEOUT_MS) {
      pending = browser.net.slice(from).filter((entry) => inFlight(entry, browser.settledIds));
      if (pending.length > 0) {
        quietSince = Date.now();
      } else if (Date.now() - quietSince >= QUIET_MS) {
        settled = true;
        break;
      }
      await sleep(50);
    }
  } catch (_error) {
    // No load event within the bound: the window is still read, and says it did not settle.
  }
  const { result } = await browser.page.send("Runtime.evaluate", {
    expression: READ_TIMING,
    returnByValue: true,
  });
  // What kept a landing that did not settle from settling, so a reader can tell a slow
  // request from one the browser never reported finished.
  const unsettled = settled ? [] : pending.map((e) => ({ url: e.url, kind: e.kind, type: e.type }));
  return { settled, unsettled, ...JSON.parse(result.value) };
}

/**
 * The log since the last read, split at *startS*: the rows that arrived in the window,
 * and how many arrived before it and are left out. The read starts where the last one
 * ended, so a straggler of the window before, logged after that window was read, is
 * counted here as having arrived before this one rather than lost.
 */
function windowRows(server, startS) {
  const { inside, before } = splitAtArrival(parseLog(readLog(server)), startS);
  return { rows: inside, arrivedBefore: before.length };
}

async function measureWindow(server, browser, go) {
  const cpuBefore = await cpuMs(server.child.pid);
  const startS = Date.now() / 1000;
  const timing = await land(browser, go);
  await sleep(LOG_SETTLE_MS);
  const cpuAfter = await cpuMs(server.child.pid);
  const { rows, arrivedBefore } = windowRows(server, startS);
  return {
    settled: timing.settled,
    unsettled: timing.unsettled,
    dcl_ms: timing.dcl_ms === null ? null : Math.round(timing.dcl_ms),
    load_ms: timing.load_ms === null ? null : Math.round(timing.load_ms),
    cpu_ms: cpuSpent(cpuBefore, cpuAfter),
    arrived_before: arrivedBefore,
    account: windowAccount(rows, timing.rows),
  };
}

async function freshBrowser(work, name) {
  const browser = await launchBrowser({
    profileDir: path.join(work, `profile-${name}`),
    ...VIEWPORT,
  });
  await browser.page.send("Page.addScriptToEvaluateOnNewDocument", { source: BUFFER_SOURCE });
  const settledIds = new Set();
  browser.conn.listeners.add((method, params) => {
    if (SETTLING_EVENTS.has(method) && params?.requestId) {
      settledIds.add(params.requestId);
    }
  });
  return { ...browser, settledIds };
}

// --------------------------------------------------------------------------- serial pass

function fetchOnce(base, assetPath, acceptEncoding) {
  return new Promise((resolve, reject) => {
    const request = http.get(
      `${base}${assetPath}`,
      { headers: { "accept-encoding": acceptEncoding, accept: "*/*" }, agent: false },
      (response) => {
        response.on("data", () => {});
        response.on("end", () =>
          resolve({
            status: response.statusCode,
            encoding: response.headers["content-encoding"] ?? "identity",
            header: parseServerTiming(response.headers["server-timing"]),
          }),
        );
        response.on("error", reject);
      },
    );
    request.on("error", reject);
    request.setTimeout(LOAD_TIMEOUT_MS, () => request.destroy(new Error("timed out")));
  });
}

async function serialPass(server, assets, acceptEncoding) {
  const cpuBefore = await cpuMs(server.child.pid);
  const startS = Date.now() / 1000;
  const encodings = {};
  for (const asset of assets) {
    const answer = await fetchOnce(server.base, asset.path, acceptEncoding);
    encodings[answer.encoding] = (encodings[answer.encoding] ?? 0) + 1;
  }
  await sleep(LOG_SETTLE_MS);
  const cpuAfter = await cpuMs(server.child.pid);
  const { rows, arrivedBefore } = windowRows(server, startS);
  return {
    accept_encoding: acceptEncoding,
    encodings,
    cpu_ms: cpuSpent(cpuBefore, cpuAfter),
    arrived_before: arrivedBefore,
    ...serialAccount(assets, rows),
  };
}

// --------------------------------------------------------------------------- main

async function run(options) {
  const metab = path.resolve(options.metab);
  const tree = path.resolve(options.tree);
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const work = path.resolve(options.work ?? path.join(REPO, ".bench", "server-time", stamp));
  fs.mkdirSync(work, { recursive: true, mode: 0o700 });
  const warmup = Number(options.warmup ?? "0");
  if (!Number.isInteger(warmup) || warmup < 0) {
    usage(`--warmup is a whole number, not ${JSON.stringify(options.warmup)}`);
  }
  const record = {
    instrument: INSTRUMENT,
    started_at: new Date().toISOString(),
    harness: harnessProvenance(),
    build: buildProvenance(metab),
    tree,
    address: options.path,
    server_args: options.serverArgs,
    warmup,
    loadavg_start: loadavg(),
  };
  const server = await startServer({
    metab,
    tree,
    work,
    serverArgs: options.serverArgs,
  });
  try {
    record.server_delivery = server.delivery;
    // Once the inventory is complete and before any landing, so the end's reading less
    // this one is what the landings left held (review B of #455, B9).
    record.server_rss_kb_start = await residentKb(server.child.pid);
    const url = `${server.base}${options.path}`;
    record.warmups = [];
    for (let i = 0; i < warmup; i++) {
      const browser = await freshBrowser(work, `warmup-${i}`);
      try {
        const { settled, unsettled } = await land(browser, () =>
          browser.page.send("Page.navigate", { url }),
        );
        record.warmups.push({ settled, unsettled });
      } finally {
        await browser.close();
      }
    }
    // The warm-ups' own rows are not the measured landing's. A straggler logged after
    // this read is read with the landing and counted as having arrived before it.
    await sleep(LOG_SETTLE_MS);
    readLog(server);
    const browser = await freshBrowser(work, "measured");
    try {
      record.chrome = browser.version.product;
      const landing = await measureWindow(server, browser, () =>
        browser.page.send("Page.navigate", { url }),
      );
      const reload = await measureWindow(server, browser, () => browser.page.send("Page.reload"));
      record.landings = { landing, reload };
    } finally {
      await browser.close();
    }
    // With the page closed, so none of its timers adds a request to the pass.
    const assets = landingAssets(record.landings.landing.account.rows);
    record.serial = await serialPass(server, assets, options["accept-encoding"]);
    record.server_rss_kb = await residentKb(server.child.pid);
    record.delivery = deliveryOf(record);
  } finally {
    await server.stop();
  }
  record.loadavg_end = loadavg();
  const out = path.resolve(options.out ?? path.join(work, "server-time.json"));
  fs.writeFileSync(out, `${JSON.stringify(record, null, 2)}\n`);
  console.log(formatRecord(record));
  console.log(`\nwrote ${out}`);
}

async function main() {
  // Arguments for metab follow `--`: as an option's value, `--exit-on-eof` would read as
  // an option of this command.
  const argv = process.argv.slice(2);
  const split = argv.indexOf("--");
  const serverArgs = split < 0 ? [] : argv.slice(split + 1);
  const { values, positionals } = parseArgs({
    args: split < 0 ? argv : argv.slice(0, split),
    options: {
      metab: { type: "string" },
      tree: { type: "string" },
      path: { type: "string", default: "/view/" },
      warmup: { type: "string", default: "0" },
      "accept-encoding": { type: "string", default: CHROME_ACCEPT_ENCODING },
      out: { type: "string" },
      work: { type: "string" },
      summarize: { type: "boolean", default: false },
    },
    allowPositionals: true,
  });
  if (values.summarize) {
    if (positionals.length === 0) {
      usage("--summarize needs a result file");
    }
    for (const file of positionals) {
      let record;
      try {
        record = checkRecord(JSON.parse(fs.readFileSync(file, "utf8")), file);
      } catch (error) {
        usage(error.message);
      }
      console.log(formatRecord(record));
    }
    return;
  }
  if (!values.metab || !values.tree) {
    usage("--metab and --tree are required");
  }
  if (!values.path.startsWith("/")) {
    usage("--path is an address on the server, starting with /");
  }
  await run({ ...values, serverArgs });
}

await main();
