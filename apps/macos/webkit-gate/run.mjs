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
// for both engines), serves the repository root for the committed diff benchmark pages,
// compiles webkit-driver from WebKitDriver.swift and the app's web view sources, then runs
// each case as pairs: Chrome then WebKit, then WebKit then Chrome, alternating, each
// sample a fresh browser with a cold cache at the app's 1200 x 820 content size. Both
// engines run probe.js, so they time the same intervals with the same code. Results go to
// attic/webkit-gate/<UTC time>/: meta.json (machine, versions, corpora), samples.jsonl
// (every record), summary.json, and summary.md, the table docs/large-content-rendering.md
// quotes.
//
// A pair passes when WebKit's value is under 1.3 times Chrome's; a metric passes when
// every pair does, the rule of the 2026-11-08 packaging brief, except that a pair of times
// both under TIMER_FLOOR_MS is reported and not judged. Needs macOS, Xcode's swiftc,
// Google Chrome, Node 24 (for its WebSocket), and a logged-in session; it keeps the
// display awake while it runs.
import { execFile, spawn } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { CHROME, Connection, sleep } from "../../../explorations/performance-loop/pr-cdp.mjs";

const run = promisify(execFile);
const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP = path.resolve(HERE, "..");
const ROOT = path.resolve(APP, "..", "..");
const WIDTH = 1200;
const HEIGHT = 820;
const PASS_RATIO = 1.3;
// WebKit coarsens performance.now() to 1 ms (Chrome: 0.1 ms), so a pair whose two times
// are both under five of those steps has no meaningful ratio. It is reported, not judged.
const TIMER_FLOOR_MS = 5;
const SAMPLE_TIMEOUT_MS = 300_000;
// How long the probe waits for a view to change before it fails the sample.
const DOM_TIMEOUT_MS = 120_000;
const KIB = 1024;
const MIB = 1024 * KIB;

// ── Options ─────────────────────────────────────────────────────

function parseArguments(argv) {
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

/** Tracked files matching the pathspecs, sorted, so a corpus depends only on the checkout. */
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

/** `text` repeated to `bytes`, cut back to the last newline so every line is whole. */
function repeatToLines(text, bytes) {
  const unit = Buffer.from(text.endsWith("\n") ? text : `${text}\n`, "utf8");
  const buffer = Buffer.alloc(bytes + unit.length);
  for (let offset = 0; offset < bytes; offset += unit.length) {
    unit.copy(buffer, offset);
  }
  const cut = buffer.lastIndexOf(0x0a, bytes - 1);
  return buffer.subarray(0, cut + 1);
}

/** One line of `text` with its newlines replaced, exactly `bytes` long. */
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
 * zero fill, or text, chosen by a fixed-seed xorshift generator.
 */
function binaryCorpus(bytes, text, seed) {
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
    if (kind < 45) {
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
    "highlight-512kib.yaml": repeatToLines(await trackedText("*.yml", "*.yaml"), 512 * KIB),
    "highlight-512kib.md": repeatToLines(await trackedText("docs/*.md"), 512 * KIB),
    "highlight-512kib.json": repeatToLines(await trackedText("tests/fixtures/*.json"), 512 * KIB),
    "highlight-512kib.ts": repeatToLines(
      await trackedText("src/metabrowser/static/*.js", "src/metabrowser/static/*.ts"),
      512 * KIB,
    ),
    "print-check.md": Buffer.from(
      `# Print check\n\n${(await trackedText("docs/large-content-rendering.md")).slice(0, 6000)}\n`,
    ),
    "folder/inside.txt": Buffer.from("A file inside a folder, for the drop check.\n"),
  };
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

// ── Servers ─────────────────────────────────────────────────────

/** `metab ROOT` on a free port, with its own cache and configuration directories. */
async function startMetab(binary, root, scratch) {
  const port = await freePort();
  const child = spawn(
    binary,
    [
      root,
      "--port",
      String(port),
      "--no-open",
      "--cache-dir",
      path.join(scratch, "cache"),
      "--config-dir",
      path.join(scratch, "config"),
    ],
    { stdio: ["ignore", "pipe", "pipe"] },
  );
  let log = "";
  const ready = new Promise((resolve, reject) => {
    const onData = (data) => {
      log += data;
      const match = /Serving .* at (http:\/\/127\.0\.0\.1:\d+)\/view\//.exec(log);
      if (match) {
        resolve(match[1]);
      }
    };
    child.stdout.on("data", onData);
    child.stderr.on("data", onData);
    child.on("exit", (code) =>
      reject(new Error(`metab exited with ${code} before serving:\n${log}`)),
    );
  });
  const origin = await Promise.race([
    ready,
    sleep(60_000).then(() => {
      throw new Error(`metab did not announce a URL in 60 s:\n${log}`);
    }),
  ]);
  return { origin, child };
}

const MIME = {
  ".css": "text/css",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript",
  ".json": "application/json",
  ".mjs": "text/javascript",
};

/** The repository root, read-only, for the committed benchmark pages and their modules. */
async function startStatic(corpus) {
  const server = http.createServer((request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    if (pathname === "/__gate/blank.html") {
      response.writeHead(200, { "content-type": MIME[".html"] });
      response.end("<!doctype html><title>blank</title><body></body>");
      return;
    }
    const [base, relative] = pathname.startsWith("/__gate/corpus/")
      ? [corpus, pathname.slice("/__gate/corpus/".length)]
      : [ROOT, pathname];
    const file = path.resolve(base, `./${relative}`);
    if (
      !file.startsWith(`${base}${path.sep}`) ||
      !fs.statSync(file, { throwIfNoEntry: false })?.isFile()
    ) {
      response.writeHead(404).end();
      return;
    }
    response.writeHead(200, {
      "cache-control": "no-store",
      "content-type": MIME[path.extname(file)] || "application/octet-stream",
    });
    fs.createReadStream(file).pipe(response);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return { origin: `http://127.0.0.1:${server.address().port}`, server };
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = http.createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

// ── Engines ─────────────────────────────────────────────────────

/** Physical footprint of one process, total and without its graphics surfaces. */
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
  return { pid, total_bytes: total, graphics_bytes: graphics, other_bytes: total - graphics };
}

async function buildDriver() {
  const output = path.join(APP, "build", "webkit-gate", "webkit-driver");
  const sources = [
    path.join(HERE, "WebKitDriver.swift"),
    path.join(APP, "Sources/Metabrowser/WebContainerView.swift"),
    path.join(APP, "Sources/ShellCore/Web/WebConfiguration.swift"),
    path.join(APP, "Sources/ShellCore/Web/NavigationPolicy.swift"),
  ];
  fs.mkdirSync(path.dirname(output), { recursive: true });
  await run("xcrun", [
    "swiftc",
    "-parse-as-library",
    "-swift-version",
    "6",
    "-default-isolation",
    "MainActor",
    "-O",
    "-o",
    output,
    ...sources,
  ]);
  return output;
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

async function chromeSample(url, script, scratch) {
  const profile = fs.mkdtempSync(path.join(scratch, "chrome-profile-"));
  const child = spawn(
    CHROME,
    [...CHROME_FLAGS, `--user-data-dir=${profile}`, "--remote-debugging-port=0", "about:blank"],
    { stdio: "ignore" },
  );
  const exited = new Promise((resolve) => child.on("exit", resolve));
  let connection = null;
  try {
    const portFile = path.join(profile, "DevToolsActivePort");
    for (let waited = 0; !fs.existsSync(portFile); waited += 100) {
      if (waited > 30_000) {
        throw new Error("Chrome did not open its DevTools port");
      }
      await sleep(100);
    }
    await sleep(100);
    const [port, socketPath] = fs.readFileSync(portFile, "utf8").trim().split("\n");
    connection = new Connection(`ws://127.0.0.1:${port}${socketPath}`);
    await connection.open();
    const { targetInfos } = await connection.send("Target.getTargets");
    const target = targetInfos.find((info) => info.type === "page");
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
    await page.send("Page.addScriptToEvaluateOnNewDocument", { source: script });
    await page.send("Page.bringToFront");
    const loadFired = page.once("Page.loadEventFired", () => true, SAMPLE_TIMEOUT_MS);
    await page.send("Page.navigate", { url });
    await loadFired;
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
  } finally {
    try {
      await connection?.send("Browser.close", {}, undefined, 10_000);
    } catch {
      // The browser is killed below if it did not close.
    }
    connection?.close();
    await Promise.race([exited, sleep(10_000)]);
    if (child.exitCode === null) {
      child.kill("SIGKILL");
      await exited;
    }
    fs.rmSync(profile, { recursive: true, force: true });
  }
}

/** Runs webkit-driver and returns its first stdout line as JSON, after `onRecord`. */
function driverRun(driver, args, onRecord = async () => {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(driver, args, { stdio: ["pipe", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
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
    child.on("exit", (code) => {
      clearTimeout(timer);
      if (code === 0 && record !== null) {
        resolve(record);
      } else {
        reject(new Error(`webkit-driver exited with ${code}: ${stderr.trim()}`));
      }
    });
  });
}

async function webkitSample(driver, url, script, scratch) {
  const scriptPath = path.join(scratch, "probe-injected.js");
  fs.writeFileSync(scriptPath, script);
  return driverRun(driver, ["measure", url, scriptPath], async (record) => {
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
  { language: "typescript", file: "highlight-512kib.ts" },
];

/** Each case: where it loads, what the probe runs, and the metrics it reports. */
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
  "highlight-512kib": {
    url: (servers) => `${servers.metab}/view/`,
    config: { case: "highlight", corpora: HIGHLIGHT_CORPORA },
    metrics: (record) => {
      const metrics = [];
      for (const sample of record.result.samples) {
        metrics.push(gated(`${sample.language} highlight + layout (ms)`, sample.elapsed_ms));
        metrics.push(counted(`${sample.language} token spans`, sample.token_spans));
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
          Math.max(...result.layout_switches_ms.map((sample) => sample.settled)),
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
      record.result.samples.map((sample) =>
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

function appendMetrics(record) {
  return record.result.steps.flatMap((step) => [
    gated(`to ${mib(step.characters)} Mi chars: append to laid out (ms)`, step.layout_ms),
    gated(`to ${mib(step.characters)} Mi chars: append to next frame (ms)`, step.frame_ms),
  ]);
}

/** A cost the gate compares as a ratio. */
function gated(name, value) {
  return { name, value, gated: true };
}

/** A count or size, reported beside the costs and not held to the ratio. */
function counted(name, value) {
  return { name, value, gated: false };
}

function mib(bytes) {
  return Math.round((bytes / MIB) * 10) / 10;
}

function viewMetrics(record) {
  const { open, clicks, scroll, dom_elements: elements } = record.result;
  const metrics = [
    gated("open: response end to laid out (ms)", open.after_response_ms),
    gated("open: navigation to laid out (ms)", open.layout_ms),
    gated("open: navigation to next frame (ms)", open.frame_ms),
  ];
  clicks.forEach((click, index) => {
    const label = `Load more ${index + 1}`;
    metrics.push(gated(`${label}: response end to laid out (ms)`, click.after_response_ms));
    metrics.push(gated(`${label}: click to next frame (ms)`, click.frame_ms));
  });
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

// ── Summary ─────────────────────────────────────────────────────

const median = (values) => {
  const sorted = values.filter((value) => typeof value === "number").sort((a, b) => a - b);
  if (sorted.length === 0) {
    return null;
  }
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

const fixed = (value, digits = 1) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "–";

function summarize(samples) {
  const summary = [];
  for (const caseName of [...new Set(samples.map((sample) => sample.case))]) {
    const pairs = new Map();
    for (const sample of samples.filter((entry) => entry.case === caseName && !entry.warmup)) {
      const pair = pairs.get(sample.pair) ?? {};
      pair[sample.engine] = sample;
      pairs.set(sample.pair, pair);
    }
    const metricNames = [];
    const values = new Map();
    for (const [pairIndex, pair] of pairs) {
      for (const engine of ["chrome", "webkit"]) {
        for (const metric of pair[engine]?.metrics ?? []) {
          if (!values.has(metric.name)) {
            metricNames.push(metric.name);
            values.set(metric.name, { gated: metric.gated, pairs: new Map() });
          }
          const entry = values.get(metric.name);
          const pairValues = entry.pairs.get(pairIndex) ?? {};
          pairValues[engine] = metric.value;
          entry.pairs.set(pairIndex, pairValues);
        }
      }
    }
    const rows = metricNames.map((name) => {
      const { gated: isGated, pairs: byPair } = values.get(name);
      const chrome = [...byPair.values()].map((pair) => pair.chrome);
      const webkit = [...byPair.values()].map((pair) => pair.webkit);
      const ratios = [...byPair.values()]
        .filter((pair) => typeof pair.chrome === "number" && typeof pair.webkit === "number")
        .map((pair) =>
          pair.chrome > 0 ? pair.webkit / pair.chrome : pair.webkit > 0 ? Infinity : 1,
        );
      const complete = ratios.length === byPair.size && ratios.length > 0;
      const judged = [...byPair.values()]
        .filter((pair) => typeof pair.chrome === "number" && typeof pair.webkit === "number")
        .filter(
          (pair) => !name.endsWith("(ms)") || Math.max(pair.chrome, pair.webkit) >= TIMER_FLOOR_MS,
        )
        .map((pair) => (pair.chrome > 0 ? pair.webkit / pair.chrome : Infinity));
      return {
        name,
        gated: isGated,
        chrome,
        webkit,
        ratios: ratios.map((ratio) => Math.round(ratio * 100) / 100),
        chrome_median: median(chrome),
        webkit_median: median(webkit),
        median_ratio: median(ratios),
        max_ratio: ratios.length ? Math.max(...ratios) : null,
        verdict: !isGated
          ? "reported"
          : !complete
            ? "incomplete"
            : judged.length === 0
              ? `under ${TIMER_FLOOR_MS} ms`
              : judged.every((ratio) => ratio < PASS_RATIO)
                ? "pass"
                : "FAIL",
        judged_pairs: judged.length,
      };
    });
    const diagnostic = CASES[caseName]?.diagnostic === true;
    for (const row of rows) {
      if (diagnostic && row.verdict !== "reported") {
        row.verdict =
          row.verdict === "incomplete"
            ? "diagnostic, incomplete"
            : `diagnostic, ${row.verdict === "FAIL" ? "over" : "under"} ${PASS_RATIO}x`;
      }
    }
    const failures = samples
      .filter((entry) => entry.case === caseName && entry.error)
      .map(
        (entry) =>
          `${entry.engine}${entry.warmup ? " warm-up" : ` pair ${entry.pair + 1}`}: ${entry.error}`,
      );
    summary.push({ case: caseName, diagnostic, pairs: pairs.size, rows, failures });
  }
  return summary;
}

function markdown(summary, meta) {
  const lines = [
    `Run ${meta.started} to ${meta.finished}: ${meta.machine}; macOS ${meta.macos};`,
    `${meta.chrome}; WebKit ${meta.webkit}; ${meta.metab}; commit ${meta.commit};`,
    `load average ${meta.load_start.join(", ")} at the start and ${meta.load_end.join(", ")} at the end.`,
    "",
  ];
  for (const { case: caseName, pairs, rows, failures } of summary) {
    lines.push(`### ${caseName} (${pairs} pairs)`, "");
    for (const failure of failures) {
      lines.push(`- Failed sample, ${failure}`);
    }
    if (failures.length) {
      lines.push("");
    }
    lines.push("| Metric | Chrome median | WebKit median | Pair ratios | Verdict |");
    lines.push("| --- | ---: | ---: | --- | --- |");
    for (const row of rows) {
      const ratios = row.gated ? row.ratios.map((ratio) => fixed(ratio, 2)).join(", ") : "";
      lines.push(
        `| ${row.name} | ${fixed(row.chrome_median)} | ${fixed(row.webkit_median)} | ${ratios} | ${row.verdict} |`,
      );
    }
    lines.push("");
  }
  return lines.join("\n");
}

// ── Main ────────────────────────────────────────────────────────

async function machineFacts(metab) {
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

async function runChecks(driver, servers, corpus) {
  const print = await driverRun(driver, [
    "print",
    `${servers.metab}/view/print-check.md`,
    path.join(path.dirname(corpus), "print-check.pdf"),
  ]);
  const drop = await driverRun(driver, [
    "drop",
    `${servers.metab}/view/`,
    path.join(corpus, "print-check.md"),
    path.join(corpus, "folder"),
  ]);
  return { print, drop };
}

/** Writes summary.json and summary.md for a run's samples and returns the Markdown. */
function writeSummary(out, meta, samples) {
  const summary = summarize(samples);
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
  if (options.summarize) {
    // Recompute the summary of a finished run from its records.
    const read = (name) => fs.readFileSync(path.join(options.summarize, name), "utf8");
    const samples = read("samples.jsonl")
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    console.log(writeSummary(options.summarize, JSON.parse(read("meta.json")), samples));
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
  fs.mkdirSync(options.out, { recursive: true });
  const corpus = path.join(options.out, "corpus");
  const scratch = path.join(options.out, "scratch");
  fs.mkdirSync(scratch, { recursive: true });
  const probe = fs.readFileSync(path.join(HERE, "probe.js"), "utf8");
  console.error(`webkit-gate: writing corpora and building webkit-driver in ${options.out}`);
  const [manifest, driver] = await Promise.all([writeCorpora(corpus), buildDriver()]);
  const metab = await startMetab(options.metab, corpus, scratch);
  const files = await startStatic(corpus);
  const servers = { metab: metab.origin, static: files.origin };
  const meta = {
    ...(await machineFacts(options.metab)),
    started: new Date().toISOString(),
    load_start: loadAverage(),
    pairs: options.pairs,
    viewport: `${WIDTH} x ${HEIGHT}`,
    corpora: manifest,
  };
  fs.writeFileSync(path.join(options.out, "meta.json"), `${JSON.stringify(meta, null, 2)}\n`);
  try {
    if (options.checks) {
      const checks = await runChecks(driver, servers, corpus);
      fs.writeFileSync(
        path.join(options.out, "checks.json"),
        `${JSON.stringify(checks, null, 2)}\n`,
      );
      console.log(JSON.stringify(checks, null, 2));
      return;
    }
    const samplesPath = path.join(options.out, "samples.jsonl");
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
        const order = index % 2 === 0 ? ["chrome", "webkit"] : ["webkit", "chrome"];
        for (const engine of order) {
          const load = loadAverage();
          const locked = await screenLocked();
          const startedAt = Date.now();
          // A failed sample is recorded and leaves its pair incomplete; the run goes on.
          let record = null;
          let error = null;
          let metrics = [];
          try {
            record =
              engine === "chrome"
                ? await chromeSample(url, script, scratch)
                : await webkitSample(driver, url, script, scratch);
            metrics = definition.metrics(record);
          } catch (caught) {
            error = String(caught?.message || caught);
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
  } finally {
    metab.child.kill("SIGTERM");
    files.server.close();
  }
}

main().catch((error) => {
  console.error(`webkit-gate: ${error.stack || error}`);
  process.exitCode = 1;
});
