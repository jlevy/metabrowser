#!/usr/bin/env node
// The WebKit measurement gate: the large-content cases of docs/large-content-rendering.md,
// run in back-to-back pairs in Chrome and in the app's WKWebView on one machine.
//
//   make macos-webkit-gate                               # every case, 5 pairs
//   make macos-webkit-gate PAIRS=3 CASES=source-16mib     # some cases
//   node apps/macos/webkit-gate/run.mjs --pairs 3 --cases source-16mib,clamp
//   node apps/macos/webkit-gate/run.mjs --checks         # window.print() and drop only
//   node apps/macos/webkit-gate/run.mjs --summarize DIR  # recompute a run's summary
//
// It writes deterministic corpora, serves them with this checkout's `metab` (one server
// for both engines), serves the committed diff benchmark pages and only the files they
// load (static-server.mjs), builds webkit-driver, the app package's WebKitDriver target,
// then runs each case as pairs: Chrome then WebKit, then WebKit then Chrome, alternating,
// each sample a fresh browser with a cold cache at a fixed 1200 x 820 content size, the
// size the app's windows opened at before they were sized to the screen.
// Both engines run probe.js, so they time the same intervals with the same code. Results
// go to attic/webkit-gate/<UTC time>/: meta.json (machine, versions, corpora),
// samples.jsonl (every record), summary.json, and summary.md, the table
// docs/large-content-rendering.md quotes. Every process and listener a run starts is
// stopped when the run ends: normally, by an error, by an uncaught exception, or by
// SIGHUP, SIGINT, or SIGTERM (processes.mjs). A harness killed outright stops nothing
// itself: metab ends with its stdin, as webkit-driver does while measuring, a driver
// check runs on to its own end, at most 600 s, and a Chrome sample in progress is left
// running.
//
// A pair passes when WebKit's value is under 1.3 times Chrome's; a metric passes when
// every pair does, the rule of the 2026-11-08 packaging brief, except that a pair of times
// both under TIMER_FLOOR_MS is reported and not judged, and a metric missing from any
// pair is incomplete (summary.mjs). Needs macOS, Xcode's Swift, Google Chrome, Node 24
// (for its WebSocket), and a logged-in session; it keeps the display awake while it runs.
import { execFile, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { CHROME, Connection, sleep } from "../../../explorations/performance-loop/pr-cdp.mjs";
import { Cleanup, cleanUpBeforeExit, startMetab, terminate, within } from "./processes.mjs";
import { BENCHMARK_ASSETS, startStatic } from "./static-server.mjs";
import { markdown, summarize } from "./summary.mjs";

/**
 * @typedef {import("./summary.mjs").Metric} Metric
 * @typedef {import("./summary.mjs").Sample} Sample
 * @typedef {import("./summary.mjs").RunMeta} RunMeta
 * @typedef {import("../../../explorations/performance-loop/pr-cdp.mjs").Session} Session
 * @typedef {{
 *   pairs: number, warmup: number, cases: string[] | null, checks: boolean,
 *   summarize: string | null, metab: string, out: string
 * }} Options
 * @typedef {{ metab: string, static: string }} Servers
 * @typedef {any} ProbeRecord A record probe.js or webkit-driver printed: JSON, whose shape
 *   each case's metrics function reads.
 * @typedef {{
 *   url: (servers: Servers) => string, config: Record<string, unknown>,
 *   metrics: (record: ProbeRecord) => Metric[], diagnostic?: boolean
 * }} CaseDefinition
 */

const run = promisify(execFile);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP = path.resolve(HERE, "..");
const ROOT = path.resolve(APP, "..", "..");
const WIDTH = 1200;
const HEIGHT = 820;
const SAMPLE_TIMEOUT_MS = 300_000;
// A safety bound on the print check, far past the few pages its document needs.
const PRINT_PAGE_LIMIT = 50;
// How long the probe waits for a view to change before it fails the sample.
const DOM_TIMEOUT_MS = 120_000;
const KIB = 1024;
const MIB = 1024 * KIB;

// ── Options ─────────────────────────────────────────────────────

/**
 * @param {string[]} argv
 * @returns {Options}
 */
function parseArguments(argv) {
  /** @type {Options} */
  const options = {
    pairs: 5,
    warmup: 1,
    cases: null,
    checks: false,
    summarize: null,
    metab: path.join(ROOT, ".venv", "bin", "metab"),
    out: path.join(ROOT, "attic", "webkit-gate", new Date().toISOString().replace(/[:.]/g, "-")),
  };
  for (let index = 0; index < argv.length; index += 1) {
    const flag = argv[index];
    const value = () => {
      index += 1;
      if (index >= argv.length) {
        throw new Error(`${flag} needs a value`);
      }
      return argv[index];
    };
    if (flag === "--pairs") {
      options.pairs = Number.parseInt(value(), 10);
    } else if (flag === "--warmup") {
      options.warmup = Number.parseInt(value(), 10);
    } else if (flag === "--cases") {
      options.cases = value().split(",");
    } else if (flag === "--summarize") {
      options.summarize = path.resolve(value());
    } else if (flag === "--checks") {
      options.checks = true;
    } else if (flag === "--metab") {
      options.metab = path.resolve(value());
    } else if (flag === "--out") {
      options.out = path.resolve(value());
    } else {
      throw new Error(`unknown option ${flag}`);
    }
  }
  if (!(options.pairs >= 1)) {
    throw new Error("--pairs must be at least 1");
  }
  return options;
}

// ── Corpora ─────────────────────────────────────────────────────

/**
 * Tracked files matching the pathspecs, sorted, so a corpus depends only on the checkout.
 * @param {...string} pathspecs
 */
async function trackedText(...pathspecs) {
  const { stdout } = await run("git", ["-C", ROOT, "ls-files", "-z", "--", ...pathspecs], {
    maxBuffer: 64 * MIB,
  });
  const files = stdout
    .split("\0")
    .filter((name) => name && !name.includes("/vendor/") && !name.endsWith(".min.js"))
    .sort();
  if (files.length === 0) {
    throw new Error(`no tracked files match ${pathspecs.join(" ")}`);
  }
  return files.map((name) => fs.readFileSync(path.join(ROOT, name), "utf8")).join("\n");
}

/**
 * `text` repeated to `bytes`, cut back to the last newline so every line is whole.
 * @param {string} text
 * @param {number} bytes
 */
function repeatToLines(text, bytes) {
  const unit = Buffer.from(text.endsWith("\n") ? text : `${text}\n`, "utf8");
  const buffer = Buffer.alloc(bytes + unit.length);
  for (let offset = 0; offset < bytes; offset += unit.length) {
    unit.copy(buffer, offset);
  }
  const cut = buffer.lastIndexOf(0x0a, bytes - 1);
  return buffer.subarray(0, cut + 1);
}

/**
 * One line of `text` with its newlines replaced, exactly `bytes` long.
 * @param {string} text
 * @param {number} bytes
 */
function repeatToOneLine(text, bytes) {
  const unit = Buffer.from(text.replace(/[\r\n]+/g, " ").replace(/[^\x20-\x7e]/g, " "), "latin1");
  const buffer = Buffer.alloc(bytes);
  for (let offset = 0; offset < bytes; offset += unit.length) {
    unit.copy(buffer, offset);
  }
  return buffer;
}

/**
 * Bytes shaped like an executable: a Mach-O magic number and a zero-filled header page,
 * which the server's NUL sniff classifies as binary, then 4 KiB pages of random bytes,
 * zero fill, or text, chosen by a fixed-seed xorshift generator. With `randomPercent` 0
 * there are no random pages, so the bytes switch between text and byte codes so seldom
 * that the binary view keeps its two-tone accent (DEFAULT_ACCENT_RUN_BUDGET).
 * @param {number} bytes
 * @param {string} text
 * @param {number} seed
 */
function binaryCorpus(bytes, text, seed, randomPercent = 45) {
  let state = seed >>> 0;
  const next = () => {
    state ^= state << 13;
    state >>>= 0;
    state ^= state >>> 17;
    state ^= state << 5;
    state >>>= 0;
    return state;
  };
  const pool = Buffer.from(text, "utf8");
  const buffer = Buffer.alloc(bytes);
  buffer.writeUInt32LE(0xfeedfacf, 0);
  for (let page = 4 * KIB; page < bytes; page += 4 * KIB) {
    const end = Math.min(page + 4 * KIB, bytes);
    const kind = next() % 100;
    if (kind < randomPercent) {
      for (let index = page; index < end; index += 1) {
        buffer[index] = next() & 0xff;
      }
    } else if (kind >= 65) {
      const start = next() % (pool.length - 4 * KIB);
      pool.copy(buffer, page, start, start + (end - page));
    }
  }
  return buffer;
}

/**
 * Short keys and many numbers: about 300,000 highlight.js spans in 512 KiB, past the
 * dense end of the 29,000 to 170,000 spans the 512 KiB bound was measured over.
 */
function denseJson() {
  const records = [];
  for (let index = 0; index < 12_000; index += 1) {
    records.push(
      `{"a":${index},"b":${index % 97}.5,"c":[${index % 7},${index % 11},${index % 13}],"d":true,"e":null},`,
    );
  }
  return `[\n${records.join("\n")}\n]\n`;
}

/**
 * Writes every corpus under `directory` and returns each one's size and SHA-256.
 * @param {string} directory
 */
async function writeCorpora(directory) {
  fs.mkdirSync(path.join(directory, "folder"), { recursive: true });
  const source = await trackedText("src/metabrowser/*.py", "src/metabrowser/static/*.js");
  const corpora = {
    "source-16mib.txt": repeatToLines(source, 16 * MIB),
    "minified-2mib.txt": repeatToOneLine(
      fs.readFileSync(path.join(ROOT, "src/metabrowser/static/vendor/highlight.min.js"), "utf8"),
      2 * MIB,
    ),
    "binary-32mib.bin": binaryCorpus(32 * MIB, source, 0x9e3779b9),
    "binary-8mib.bin": binaryCorpus(8 * MIB, source, 0x85ebca6b),
    "binary-accent-8mib.bin": binaryCorpus(8 * MIB, source, 0xc2b2ae35, 0),
    "highlight-512kib.yaml": repeatToLines(await trackedText("*.yml", "*.yaml"), 512 * KIB),
    "highlight-512kib.md": repeatToLines(await trackedText("docs/*.md"), 512 * KIB),
    "highlight-512kib.json": repeatToLines(await trackedText("tests/fixtures/*.json"), 512 * KIB),
    "highlight-512kib-dense.json": repeatToLines(denseJson(), 512 * KIB),
    "highlight-512kib.ts": repeatToLines(
      await trackedText("src/metabrowser/static/*.js", "src/metabrowser/static/*.ts"),
      512 * KIB,
    ),
    "print-check.md": Buffer.from(
      `# Print check\n\n${(await trackedText("docs/large-content-rendering.md")).slice(0, 6000)}\n`,
    ),
    "folder/inside.txt": Buffer.from("A file inside a folder, for the drop check.\n"),
  };
  /** @type {Record<string, { bytes: number, sha256: string }>} */
  const manifest = {};
  for (const [name, bytes] of Object.entries(corpora)) {
    fs.writeFileSync(path.join(directory, name), bytes);
    manifest[name] = {
      bytes: bytes.length,
      sha256: createHash("sha256").update(bytes).digest("hex"),
    };
  }
  return manifest;
}

// ── Engines ─────────────────────────────────────────────────────

/**
 * Physical footprint of one process, total and without its graphics surfaces, and its priority.
 * @param {number | null | undefined} pid
 */
async function footprint(pid) {
  if (!pid) {
    return null;
  }
  const { stdout } = await run("/usr/bin/footprint", ["-f", "bytes", "-p", String(pid)]);
  const total = Number(/Footprint: (\d+) B/.exec(stdout)?.[1] ?? Number.NaN);
  let graphics = 0;
  for (const match of stdout.matchAll(/^\s*(\d+) B\s.*\(graphics\)\s*$/gm)) {
    graphics += Number(match[1]);
  }
  // The scheduling priority, so a record shows whether the system had demoted the process.
  const priority = (await run("ps", ["-o", "pri=", "-p", String(pid)])).stdout.trim();
  return {
    pid,
    priority: Number(priority),
    total_bytes: total,
    graphics_bytes: graphics,
    other_bytes: total - graphics,
  };
}

/**
 * webkit-driver: the app package's WebKitDriver target (driver/WebKitDriver.swift), built
 * by SwiftPM against the app's own ShellCore and ShellViews, optimized as the app is.
 */
async function buildDriver() {
  const swift = ["build", "--package-path", APP, "-c", "release"];
  await run("swift", [...swift, "--product", "WebKitDriver"]);
  const { stdout } = await run("swift", [...swift, "--show-bin-path"]);
  return path.join(stdout.trim(), "WebKitDriver");
}

const CHROME_FLAGS = [
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-extensions",
  "--disable-component-update",
  "--disable-background-networking",
  "--disable-sync",
  "--disable-default-apps",
  "--disable-breakpad",
  "--disable-search-engine-choice-screen",
  "--use-mock-keychain",
  "--password-store=basic",
  // The window may sit behind others; none of these may slow or pause the page.
  "--disable-backgrounding-occluded-windows",
  "--disable-renderer-backgrounding",
  "--disable-background-timer-throttling",
  "--window-position=0,0",
  `--window-size=${WIDTH},${HEIGHT + 200}`,
];

/**
 * Runs `use(connection, page)` in a fresh Chrome with a scratch profile, its page at the
 * app's content size, then closes the browser and removes the profile. `cleanup` owns the
 * browser while it runs, so a crash anywhere in the harness still stops it.
 * @template T
 * @param {string} scratch
 * @param {Cleanup} cleanup
 * @param {(connection: Connection, page: Session) => Promise<T>} use
 * @returns {Promise<T>}
 */
async function withChrome(scratch, cleanup, use) {
  const profile = fs.mkdtempSync(path.join(scratch, "chrome-profile-"));
  const child = spawn(
    CHROME,
    [...CHROME_FLAGS, `--user-data-dir=${profile}`, "--remote-debugging-port=0", "about:blank"],
    { stdio: "ignore" },
  );
  // Chrome has no stdin to lose when the harness dies, so the run owns it from here: a
  // crash stops it and removes its profile, as the finally below does for every ordinary
  // ending.
  const release = cleanup.add(async () => {
    await terminate(child);
    fs.rmSync(profile, { recursive: true, force: true });
  });
  const exited = new Promise((resolve) => child.on("exit", resolve));
  // Set by the error listener, so typed as the union rather than narrowed to null.
  let spawnError = /** @type {Error | null} */ (null);
  child.on("error", (error) => {
    spawnError = error;
  });
  let connection = /** @type {Connection | null} */ (null);
  try {
    const portFile = path.join(profile, "DevToolsActivePort");
    for (let waited = 0; !fs.existsSync(portFile); waited += 100) {
      if (spawnError) {
        throw new Error(`Chrome did not start: ${spawnError.message}`, { cause: spawnError });
      }
      if (waited > 30_000) {
        throw new Error("Chrome did not open its DevTools port");
      }
      await sleep(100);
    }
    await sleep(100);
    const [port, socketPath] = fs.readFileSync(portFile, "utf8").trim().split("\n");
    connection = new Connection(`ws://127.0.0.1:${port}${socketPath}`);
    await connection.open();
    /** @type {{ targetInfos: { type: string, targetId: string }[] }} */
    const { targetInfos } = await connection.send("Target.getTargets");
    const target = targetInfos.find((info) => info.type === "page");
    if (!target) {
      throw new Error("Chrome opened no page");
    }
    const { sessionId } = await connection.send("Target.attachToTarget", {
      targetId: target.targetId,
      flatten: true,
    });
    const page = connection.adopt(sessionId, target.targetId);
    await page.send("Page.enable");
    await page.send("Emulation.setDeviceMetricsOverride", {
      width: WIDTH,
      height: HEIGHT,
      deviceScaleFactor: 0,
      mobile: false,
    });
    await page.send("Emulation.setFocusEmulationEnabled", { enabled: true });
    await page.send("Page.bringToFront");
    return await use(connection, page);
  } finally {
    try {
      await connection?.send("Browser.close", {}, undefined, 10_000);
    } catch {
      // The browser is killed below if it did not close.
    }
    connection?.close();
    // Browser.close usually ends it; if it has not after 10 s, SIGTERM, then SIGKILL.
    if (child.pid !== undefined && !(await within(exited, 10_000))) {
      await terminate(child);
    }
    fs.rmSync(profile, { recursive: true, force: true });
    release();
  }
}

/**
 * Navigates `page` to `url` and resolves after its load event.
 * @param {Session} page
 * @param {string} url
 */
async function navigate(page, url) {
  const loadFired = page.once("Page.loadEventFired", () => true, SAMPLE_TIMEOUT_MS);
  await page.send("Page.navigate", { url });
  await loadFired;
}

/**
 * One sample in a fresh Chrome: the probe's record, its renderer's footprint, and the
 * browser's version.
 * @param {string} url
 * @param {string} script
 * @param {string} scratch
 * @param {Cleanup} cleanup
 * @returns {Promise<ProbeRecord>}
 */
function chromeSample(url, script, scratch, cleanup) {
  return withChrome(scratch, cleanup, async (connection, page) => {
    await page.send("Page.addScriptToEvaluateOnNewDocument", { source: script });
    await navigate(page, url);
    const evaluated = await page.send(
      "Runtime.evaluate",
      {
        expression: "globalThis.__webkitGate.done.then((record) => JSON.stringify(record))",
        awaitPromise: true,
        returnByValue: true,
      },
      SAMPLE_TIMEOUT_MS,
    );
    if (evaluated.exceptionDetails) {
      throw new Error(
        evaluated.exceptionDetails.exception?.description || evaluated.exceptionDetails.text,
      );
    }
    const record = JSON.parse(evaluated.result.value);
    /** @type {{ processInfo: { type: string, id: number, cpuTime: number }[] }} */
    const { processInfo } = await connection.send("SystemInfo.getProcessInfo");
    // The page did nearly all of the renderer work in this browser, so its renderer has
    // the most CPU time.
    const renderer = processInfo
      .filter((info) => info.type === "renderer")
      .sort((a, b) => b.cpuTime - a.cpuTime)[0];
    record.footprint = await footprint(renderer?.id);
    const version = await connection.send("Browser.getVersion");
    record.engine = { name: "Chrome", product: version.product, revision: version.revision };
    return record;
  });
}

/**
 * Chrome's print of the same page to PDF, beside WebKit's, for the print check.
 * @param {string} url
 * @param {string} pdfPath
 * @param {string} scratch
 * @param {Cleanup} cleanup
 */
function chromePrint(url, pdfPath, scratch, cleanup) {
  return withChrome(scratch, cleanup, async (_connection, page) => {
    await navigate(page, url);
    // The view renders after the load event; give it the time the WebKit check waits.
    await sleep(3000);
    const { data } = await page.send("Page.printToPDF", { preferCSSPageSize: true });
    const bytes = Buffer.from(data, "base64");
    fs.writeFileSync(pdfPath, bytes);
    const pages = bytes.toString("latin1").match(/\/Type\s*\/Page[^s]/g)?.length ?? 0;
    return { pdf: path.basename(pdfPath), pdf_bytes: bytes.length, pdf_pages: pages };
  });
}

/**
 * Runs webkit-driver and returns its first stdout line as JSON, after `onRecord`.
 * `cleanup` owns the driver while it runs.
 * @param {string} driver
 * @param {string[]} args
 * @param {Cleanup} cleanup
 * @param {(record: ProbeRecord) => Promise<void>} [onRecord]
 * @returns {Promise<ProbeRecord>}
 */
function driverRun(driver, args, cleanup, onRecord = async () => {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(driver, args, { stdio: ["pipe", "pipe", "pipe"] });
    const release = cleanup.add(() => terminate(child));
    let stdout = "";
    let stderr = "";
    /** @type {ProbeRecord} */
    let record = null;
    const timer = setTimeout(() => child.kill("SIGKILL"), SAMPLE_TIMEOUT_MS);
    child.stderr.on("data", (data) => {
      stderr += data;
    });
    child.stdout.on("data", async (data) => {
      stdout += data;
      const newline = stdout.indexOf("\n");
      if (record !== null || newline < 0) {
        return;
      }
      try {
        record = JSON.parse(stdout.slice(0, newline));
        await onRecord(record);
      } catch (error) {
        reject(error);
      }
      child.stdin.end();
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      release();
      reject(new Error(`webkit-driver did not start: ${error.message}`, { cause: error }));
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      release();
      if (code === 0 && record !== null) {
        resolve(record);
      } else {
        reject(new Error(`webkit-driver exited with ${code}: ${stderr.trim()}`));
      }
    });
  });
}

/**
 * One sample in webkit-driver: the probe's record and its web content process's footprint.
 * @param {string} driver
 * @param {string} url
 * @param {string} script
 * @param {string} scratch
 * @param {Cleanup} cleanup
 */
async function webkitSample(driver, url, script, scratch, cleanup) {
  const scriptPath = path.join(scratch, "probe-injected.js");
  fs.writeFileSync(scriptPath, script);
  return driverRun(driver, ["measure", url, scriptPath], cleanup, async (record) => {
    record.footprint = await footprint(record.web_process_pid);
  });
}

// ── Cases ───────────────────────────────────────────────────────

// The source view's growth sequence: a 2 MiB first window, then Load more doubling to 8 MiB.
const APPEND_CHUNKS = [2 * MIB, 2 * MIB, 4 * MIB, 8 * MIB];

const HIGHLIGHT_CORPORA = [
  { language: "yaml", file: "highlight-512kib.yaml" },
  { language: "markdown", file: "highlight-512kib.md" },
  { language: "json", file: "highlight-512kib.json" },
  { language: "json", file: "highlight-512kib-dense.json" },
  { language: "typescript", file: "highlight-512kib.ts" },
];

/**
 * Each case: where it loads, what the probe runs, and the metrics it reports.
 * @type {Record<string, CaseDefinition>}
 */
const CASES = {
  "source-16mib": {
    url: (servers) => `${servers.metab}/view/source-16mib.txt`,
    config: { case: "source" },
    metrics: viewMetrics,
  },
  "source-minified-2mib": {
    url: (servers) => `${servers.metab}/view/minified-2mib.txt`,
    config: { case: "source" },
    metrics: viewMetrics,
  },
  "binary-32mib": {
    url: (servers) => `${servers.metab}/view/binary-32mib.bin`,
    config: { case: "binary" },
    metrics: viewMetrics,
  },
  "binary-8mib": {
    url: (servers) => `${servers.metab}/view/binary-8mib.bin`,
    config: { case: "binary" },
    metrics: viewMetrics,
  },
  "binary-accent-8mib": {
    url: (servers) => `${servers.metab}/view/binary-accent-8mib.bin`,
    config: { case: "binary" },
    metrics: viewMetrics,
  },
  "highlight-512kib": {
    url: (servers) => `${servers.metab}/view/`,
    config: { case: "highlight", corpora: HIGHLIGHT_CORPORA },
    metrics: (record) => {
      /** @type {Metric[]} */
      const metrics = [];
      for (const sample of record.result.samples) {
        metrics.push(gated(`${sample.file} highlight + layout (ms)`, sample.elapsed_ms));
        metrics.push(counted(`${sample.file} token spans`, sample.token_spans));
      }
      return metrics;
    },
  },
  "diff-layout": {
    url: (servers) => `${servers.static}/explorations/diff-layout/benchmark.html`,
    config: {
      case: "benchmark",
      resultKey: "diffLayoutBenchmarkResult",
      errorKey: "diffLayoutBenchmarkError",
    },
    metrics: (record) => {
      const result = record.result;
      return [
        gated("mount, 1,000 files (ms)", result.mount_ms),
        gated("median blocking switch (ms)", result.median_blocking_switch_ms),
        gated("max blocking switch (ms)", result.max_blocking_switch_ms),
        gated(
          "slowest settled switch (ms)",
          Math.max(
            ...result.layout_switches_ms.map(
              /** @param {{ settled: number }} sample */ (sample) => sample.settled,
            ),
          ),
        ),
        counted("mounted elements", result.dom_elements),
      ];
    },
  },
  "diff-intraline": {
    url: (servers) => `${servers.static}/explorations/diff-intraline/benchmark.html`,
    config: {
      case: "benchmark",
      resultKey: "diffIntralineBenchmarkResult",
      errorKey: "diffIntralineBenchmarkError",
    },
    metrics: (record) =>
      record.result.samples.map(
        /** @param {{ name: string, status: string, elapsed_ms: number }} sample */ (sample) =>
          gated(`${sample.name}, ${sample.status} (ms)`, sample.elapsed_ms),
      ),
  },
  clamp: {
    url: (servers) => `${servers.static}/__gate/blank.html`,
    config: { case: "clamp" },
    metrics: (record) => [
      counted("height of a 100,000,000 px div (px)", record.result.bounding_px),
    ],
  },
  "diagnostic-append-text": {
    diagnostic: true,
    url: (servers) => `${servers.static}/__gate/blank.html`,
    config: {
      case: "appendLayout",
      mode: "single",
      corpusUrl: "/__gate/corpus/source-16mib.txt",
      chunks: APPEND_CHUNKS,
    },
    metrics: appendMetrics,
  },
  "diagnostic-append-split": {
    diagnostic: true,
    url: (servers) => `${servers.static}/__gate/blank.html`,
    config: {
      case: "appendLayout",
      mode: "split",
      corpusUrl: "/__gate/corpus/source-16mib.txt",
      chunks: APPEND_CHUNKS,
    },
    metrics: appendMetrics,
  },
  "diagnostic-append-blocks": {
    diagnostic: true,
    url: (servers) => `${servers.static}/__gate/blank.html`,
    config: {
      case: "appendLayout",
      mode: "blocks",
      corpusUrl: "/__gate/corpus/source-16mib.txt",
      chunks: APPEND_CHUNKS,
    },
    metrics: appendMetrics,
  },
};

/**
 * @param {ProbeRecord} record
 * @returns {Metric[]}
 */
function appendMetrics(record) {
  return record.result.steps.flatMap(
    /** @param {{ characters: number, layout_ms: number, frame_ms: number }} step */ (step) => [
      gated(`to ${mib(step.characters)} Mi chars: append to laid out (ms)`, step.layout_ms),
      gated(`to ${mib(step.characters)} Mi chars: append to next frame (ms)`, step.frame_ms),
    ],
  );
}

/**
 * A cost the gate compares as a ratio.
 * @param {string} name
 * @param {unknown} value
 * @returns {Metric}
 */
function gated(name, value) {
  return { name, value, gated: true };
}

/**
 * A count or size, reported beside the costs and not held to the ratio.
 * @param {string} name
 * @param {unknown} value
 * @returns {Metric}
 */
function counted(name, value) {
  return { name, value, gated: false };
}

/** @param {number} bytes */
function mib(bytes) {
  return Math.round((bytes / MIB) * 10) / 10;
}

/**
 * @param {ProbeRecord} record
 * @returns {Metric[]}
 */
function viewMetrics(record) {
  const { open, clicks, scroll, dom_elements: elements } = record.result;
  /** @type {Metric[]} */
  const metrics = [
    gated("open: response end to laid out (ms)", open.after_response_ms),
    gated("open: navigation to laid out (ms)", open.layout_ms),
    gated("open: navigation to next frame (ms)", open.frame_ms),
  ];
  clicks.forEach(
    /**
     * @param {{ after_response_ms: number, frame_ms: number }} click
     * @param {number} index
     */
    (click, index) => {
      const label = `Load more ${index + 1}`;
      metrics.push(gated(`${label}: response end to laid out (ms)`, click.after_response_ms));
      metrics.push(gated(`${label}: click to next frame (ms)`, click.frame_ms));
    },
  );
  for (const sample of scroll.samples) {
    metrics.push(gated(`scroll to ${sample.to * 100}%: frame work (ms)`, sample.work_ms));
  }
  if (record.footprint) {
    metrics.push(
      gated("renderer footprint without graphics (MiB)", mib(record.footprint.other_bytes)),
    );
    metrics.push(counted("renderer footprint, total (MiB)", mib(record.footprint.total_bytes)));
  }
  metrics.push(counted("DOM elements", elements));
  metrics.push(counted("scroll height (px)", scroll.scroll_height));
  return metrics;
}

// ── Main ────────────────────────────────────────────────────────

/**
 * The machine, OS, engine, server, and checkout versions a run records.
 * @param {string} metab
 */
async function machineFacts(metab) {
  /** @param {string} name */
  const sysctl = async (name) => (await run("sysctl", ["-n", name])).stdout.trim();
  const [model, cpu, memory] = await Promise.all([
    sysctl("hw.model"),
    sysctl("machdep.cpu.brand_string"),
    sysctl("hw.memsize"),
  ]);
  const macos = (await run("sw_vers", ["-productVersion"])).stdout.trim();
  const build = (await run("sw_vers", ["-buildVersion"])).stdout.trim();
  const chrome = (await run(CHROME, ["--version"])).stdout.trim();
  const webkit = (
    await run("defaults", [
      "read",
      "/System/Library/Frameworks/WebKit.framework/Resources/Info",
      "CFBundleVersion",
    ])
  ).stdout.trim();
  const metabVersion = (await run(metab, ["--version"])).stdout.trim();
  const commit = (await run("git", ["-C", ROOT, "rev-parse", "--short=12", "HEAD"])).stdout.trim();
  return {
    machine: `${model}, ${cpu}, ${Math.round(Number(memory) / 1024 ** 3)} GB`,
    macos: `${macos} (${build})`,
    chrome,
    webkit,
    metab: metabVersion,
    commit,
    cores: os.cpus().length,
  };
}

/** Whether the login session's screen is locked, recorded with every sample. */
async function screenLocked() {
  const { stdout } = await run("ioreg", ["-n", "Root", "-d1"], { maxBuffer: 16 * MIB });
  const match = /"CGSSessionScreenIsLocked"=(Yes|No)/.exec(stdout);
  return match ? match[1] === "Yes" : false;
}

const loadAverage = () => os.loadavg().map((value) => Math.round(value * 10) / 10);

/**
 * window.print() and File > Print in WebKit, Chrome's print of the same page, and drops
 * of a file and a folder on the app's web view. The PDFs land beside the corpus.
 * @param {string} driver
 * @param {Servers} servers
 * @param {string} corpus
 * @param {string} scratch
 * @param {Cleanup} cleanup
 */
async function runChecks(driver, servers, corpus, scratch, cleanup) {
  const out = path.dirname(corpus);
  const url = `${servers.metab}/view/print-check.md`;
  const print = await driverRun(
    driver,
    ["print", url, path.join(out, "print-webkit.pdf"), String(PRINT_PAGE_LIMIT)],
    cleanup,
  );
  const chromePrinted = await chromePrint(
    url,
    path.join(out, "print-chrome.pdf"),
    scratch,
    cleanup,
  );
  const drop = await driverRun(
    driver,
    [
      "drop",
      `${servers.metab}/view/`,
      path.join(corpus, "print-check.md"),
      path.join(corpus, "folder"),
    ],
    cleanup,
  );
  return { print, chrome_print: chromePrinted, drop };
}

/**
 * Writes summary.json and summary.md for a run's samples and returns the Markdown.
 * @param {string} out
 * @param {RunMeta & { pairs?: unknown, cases?: string[] }} meta
 * @param {Sample[]} samples
 */
function writeSummary(out, meta, samples) {
  const summary = summarize(samples, {
    pairs: meta.pairs,
    // The runs docs/large-content-rendering.md quotes predate meta.cases, so their summary
    // covers the cases they sampled.
    cases: meta.cases ?? [],
    diagnostic: (caseName) => CASES[caseName]?.diagnostic === true,
  });
  fs.writeFileSync(
    path.join(out, "summary.json"),
    `${JSON.stringify({ meta, summary }, null, 2)}\n`,
  );
  const table = markdown(summary, meta);
  fs.writeFileSync(path.join(out, "summary.md"), `${table}\n`);
  return table;
}

async function main() {
  const options = parseArguments(process.argv.slice(2));
  const finished = options.summarize;
  if (finished) {
    // Recompute the summary of a finished run from its records.
    /** @param {string} name */
    const read = (name) => fs.readFileSync(path.join(finished, name), "utf8");
    const samples = read("samples.jsonl")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    console.log(writeSummary(finished, JSON.parse(read("meta.json")), samples));
    return;
  }
  // A page on a sleeping display gets no frames in WebKit, so keep the display awake
  // (and wake it) for as long as this process runs.
  spawn("/usr/bin/caffeinate", ["-d", "-i", "-u", "-w", String(process.pid)], {
    detached: true,
    stdio: "ignore",
  }).unref();
  const caseNames = options.cases ?? Object.keys(CASES);
  for (const name of caseNames) {
    if (!CASES[name]) {
      throw new Error(`unknown case ${name}; cases: ${Object.keys(CASES).join(", ")}`);
    }
  }
  // Every process and listener the run starts is stopped here when the run ends, or by
  // cleanUpBeforeExit when an uncaught exception or a signal ends the harness first.
  const cleanup = new Cleanup();
  const restoreDefaults = cleanUpBeforeExit(cleanup);
  try {
    await measure(options, caseNames, cleanup);
  } finally {
    for (const error of await cleanup.run()) {
      console.error(
        `webkit-gate: while stopping: ${(error instanceof Error && error.stack) || error}`,
      );
      process.exitCode = 1;
    }
    restoreDefaults();
  }
}

/**
 * The run itself: corpora, driver, servers, then the checks or every case's pairs.
 * @param {Options} options
 * @param {string[]} caseNames
 * @param {Cleanup} cleanup
 */
async function measure(options, caseNames, cleanup) {
  fs.mkdirSync(options.out, { recursive: true });
  const corpus = path.join(options.out, "corpus");
  const scratch = path.join(options.out, "scratch");
  fs.mkdirSync(scratch, { recursive: true });
  const probe = fs.readFileSync(path.join(HERE, "probe.js"), "utf8");
  console.error(`webkit-gate: writing corpora and building webkit-driver in ${options.out}`);
  const [manifest, driver] = await Promise.all([writeCorpora(corpus), buildDriver()]);
  const metab = await startMetab(options.metab, corpus, scratch, { cleanup });
  const files = await startStatic({
    root: ROOT,
    assets: BENCHMARK_ASSETS,
    corpus,
    corpusFiles: Object.keys(manifest),
    cleanup,
  });
  const servers = { metab: metab.origin, static: files.origin };
  /**
   * @type {RunMeta & {
   *   pairs: number, cases: string[], viewport: string, cores: number,
   *   corpora: Record<string, { bytes: number, sha256: string }>
   * }}
   */
  const meta = {
    ...(await machineFacts(options.metab)),
    started: new Date().toISOString(),
    load_start: loadAverage(),
    pairs: options.pairs,
    cases: caseNames,
    viewport: `${WIDTH} x ${HEIGHT}`,
    corpora: manifest,
  };
  fs.writeFileSync(path.join(options.out, "meta.json"), `${JSON.stringify(meta, null, 2)}\n`);
  if (options.checks) {
    const checks = await runChecks(driver, servers, corpus, scratch, cleanup);
    fs.writeFileSync(path.join(options.out, "checks.json"), `${JSON.stringify(checks, null, 2)}\n`);
    console.log(JSON.stringify(checks, null, 2));
    return;
  }
  const samplesPath = path.join(options.out, "samples.jsonl");
  /** @type {Sample[]} */
  const samples = [];
  for (const caseName of caseNames) {
    const definition = CASES[caseName];
    const url = definition.url(servers);
    const script = `globalThis.__webkitGateConfig = ${JSON.stringify({
      ...definition.config,
      timeoutMs: DOM_TIMEOUT_MS,
    })};\n${probe}`;
    const total = options.warmup + options.pairs;
    for (let index = 0; index < total; index += 1) {
      const warmup = index < options.warmup;
      const pair = index - options.warmup;
      /** @type {import("./summary.mjs").Engine[]} */
      const order = index % 2 === 0 ? ["chrome", "webkit"] : ["webkit", "chrome"];
      for (const engine of order) {
        const load = loadAverage();
        const locked = await screenLocked();
        const startedAt = Date.now();
        // A failed sample is recorded and leaves its pair incomplete; the run goes on.
        /** @type {ProbeRecord} */
        let record = null;
        /** @type {string | null} */
        let error = null;
        /** @type {Metric[]} */
        let metrics = [];
        try {
          record =
            engine === "chrome"
              ? await chromeSample(url, script, scratch, cleanup)
              : await webkitSample(driver, url, script, scratch, cleanup);
          metrics = definition.metrics(record);
        } catch (caught) {
          error = String((caught instanceof Error && caught.message) || caught);
        }
        const sample = {
          case: caseName,
          engine,
          pair: warmup ? null : pair,
          warmup,
          load_average: load,
          screen_locked: locked,
          wall_ms: Date.now() - startedAt,
          error,
          record,
          metrics,
        };
        samples.push(sample);
        fs.appendFileSync(samplesPath, `${JSON.stringify(sample)}\n`);
        console.error(
          `webkit-gate: ${caseName} ${warmup ? "warm-up" : `pair ${pair + 1}`} ${engine} ` +
            `in ${sample.wall_ms} ms at load ${load[0]}${locked ? ", screen locked" : ""}` +
            (error ? `: FAILED: ${error}` : ""),
        );
      }
    }
  }
  meta.finished = new Date().toISOString();
  meta.load_end = loadAverage();
  fs.writeFileSync(path.join(options.out, "meta.json"), `${JSON.stringify(meta, null, 2)}\n`);
  console.log(writeSummary(options.out, meta, samples));
}

main().catch((error) => {
  console.error(`webkit-gate: ${error.stack || error}`);
  process.exitCode = 1;
});
