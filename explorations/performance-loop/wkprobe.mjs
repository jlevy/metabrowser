#!/usr/bin/env node
// WKWebView probe: what the native app's engine fetches and when it is ready.
//
//   node explorations/performance-loop/wkprobe.mjs run --corpus PATH \
//     --condition control=/path/to/metab [--condition candidate=/path/to/metab] \
//     [--runs 3] [--scenarios cold,reload,relaunch,hidden-then-show] [--name NAME]
//   node explorations/performance-loop/wkprobe.mjs summarize .bench/wkprobe/NAME/runs.jsonl
//   node explorations/performance-loop/wkprobe.mjs compare .bench/wkprobe/NAME/runs.jsonl \
//     --control control --candidate candidate [--tolerance 1.3] [--expect SCENARIO.METRIC:lower]
//   node explorations/performance-loop/wkprobe.mjs clean
//
// Each run starts a fresh server from the condition's `metab`, puts a logging proxy in
// front of it (the request ground truth: WebKit's own APIs do not report subresource
// loads), compiles and runs `wkprobe.swift` against the proxy, and writes one JSONL row.
// macOS only, and the screen must stay unlocked with the display awake: a hidden page
// never finishes its first view, so the screen guard refuses the run instead. A series
// and `clean` hold the series lock, because both remove the probe's WebKit data. See
// README.md, "WKWebView Probe". The statistics live in wkprobe-stats.mjs.
import { execFileSync, spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";
import {
  buildProvenance,
  corpusProvenance,
  getJson,
  harnessProvenance,
  provenanceChanges,
  serverFacts,
} from "./provenance.mjs";
import {
  CompareRefusal,
  classify,
  compareProbe,
  FAMILIES,
  formatComparison,
  PROBE_REVISION,
  parseRows,
  relaunchFreshness,
  requestCounts,
  SCHEMA,
  summarize,
} from "./wkprobe-stats.mjs";

const HERE = import.meta.dirname;
const REPO = path.resolve(HERE, "../..");
const BENCH = path.join(REPO, ".bench", "wkprobe");
const SOURCE = path.join(HERE, "wkprobe.swift");
// WebKit files a process's data under its bundle identifier; the probe's embedded
// Info.plist names this one, so cleanup removes exactly what the probe created.
const BUNDLE_ID = "org.metabrowser.perf.wkprobe";
const LIBRARY_DIRS = [
  "WebKit",
  "Caches",
  "HTTPStorages",
  "Saved Application State",
  "Cookies",
  "Preferences",
  "Application Support",
];
const PORTS = [8930, 8939];
// The default series lock: one per user, outside any checkout. A round whose harnesses
// share another lock passes it with --lock.
const DEFAULT_LOCK = path.join(os.tmpdir(), "metabrowser-perf-series.lock");
const SCENARIOS = ["cold", "reload", "relaunch", "hidden-then-show"];
const VISIBLE = new Set(["cold", "reload", "relaunch"]);
const INVENTORY_DEADLINE_MS = 180000;
const PLAIN_WORD = /^(?!\.{1,2}$)[\w.-]+$/;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// --------------------------------------------------------------------------- utilities

const loadavg = () => os.loadavg().map((v) => Math.round(v * 100) / 100);

const children = new Set();
function track(child) {
  children.add(child);
  child.on("exit", () => children.delete(child));
  return child;
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
function killAll() {
  for (const child of children) {
    killGroup(child, "SIGKILL");
  }
}

// Temporary directories a run made, removed however the process ends.
const temps = new Set();
function tempDir(prefix) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  temps.add(dir);
  return dir;
}
function removeTemp(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
  temps.delete(dir);
}
function removeTemps() {
  for (const dir of [...temps]) {
    removeTemp(dir);
  }
}

// --------------------------------------------------------------------------- series lock

// The lock is a directory made with one atomic mkdir, with an `owner` file inside naming
// who holds it. Only the holder removes it. A lock whose owner's process is gone is
// reported as stale, never broken: another harness may write its owner differently.
let heldLock = null;

function lockOwner(dir) {
  try {
    return fs.readFileSync(path.join(dir, "owner"), "utf8").trim();
  } catch (_error) {
    return null;
  }
}
function pidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === "EPERM";
  }
}
function takeLock(dir, what) {
  try {
    fs.mkdirSync(dir, { mode: 0o700 });
  } catch (error) {
    if (error.code !== "EEXIST") {
      throw error;
    }
    const owner = lockOwner(dir);
    const pid = Number(
      (owner ?? "")
        .match(/^(\d+)$|\bpid[=: ]+(\d+)/)
        ?.slice(1)
        .find(Boolean),
    );
    const stale =
      pid > 0 && !pidAlive(pid)
        ? `; its owner, pid ${pid}, is not running: if no series is running, remove ${dir}`
        : "";
    throw new Error(
      `the series lock ${dir} is held${owner ? ` (${owner.split("\n")[0].slice(0, 200)})` : ""}${stale}; ${what} does not run beside another series`,
    );
  }
  heldLock = dir;
  fs.writeFileSync(
    path.join(dir, "owner"),
    `pid ${process.pid}: wkprobe.mjs ${what}, since ${new Date().toISOString()}\n`,
    { mode: 0o600 },
  );
}
function releaseLock() {
  if (!heldLock) {
    return;
  }
  const dir = heldLock;
  heldLock = null;
  if ((lockOwner(dir) ?? "").startsWith(`pid ${process.pid}:`)) {
    fs.rmSync(path.join(dir, "owner"), { force: true });
    try {
      fs.rmdirSync(dir);
    } catch (_error) {
      // Not empty: someone else's file; leave it.
    }
  }
}

for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    killAll();
    // Only the lock's holder may remove the probe's data; a reader holds no lock.
    if (heldLock) {
      cleanLibrary();
    }
    removeTemps();
    releaseLock();
    process.exit(130);
  });
}
process.on("exit", () => {
  killAll();
  removeTemps();
  releaseLock();
});

// --------------------------------------------------------------------------- provenance

function hostProvenance() {
  const sw = (flag) => execFileSync("sw_vers", [flag], { encoding: "utf8" }).trim();
  const swiftc = execFileSync("swiftc", ["--version"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  })
    .split("\n")[0]
    .trim();
  return {
    macos: sw("-productVersion"),
    macos_build: sw("-buildVersion"),
    arch: os.arch(),
    cpus: os.cpus().length,
    node: process.version,
    swiftc,
  };
}

/** Whether this `metab` takes --exit-on-eof, so its server dies with this process. */
function supportsExitOnEof(metab) {
  try {
    const help = execFileSync(metab, ["--help"], {
      encoding: "utf8",
      timeout: 60000,
      cwd: os.tmpdir(),
      stdio: ["ignore", "pipe", "ignore"],
      env: { ...process.env, COLUMNS: "200", NO_COLOR: "1", TERM: "dumb" },
    });
    return help.includes("--exit-on-eof");
  } catch (_error) {
    return false;
  }
}

// --------------------------------------------------------------------------- probe binary

const PLIST = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
<key>CFBundleName</key><string>mb-wkprobe</string>
<key>LSAppNapIsDisabled</key><true/>
</dict></plist>
`;

/**
 * Compile the probe once per source, Info.plist, flags, and compiler. The binary is
 * written under a temporary name and renamed, so an interrupted compile leaves nothing
 * that a later run would take for a finished one.
 */
function compileProbe() {
  const swiftc = execFileSync("swiftc", ["--version"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  const flags = ["-O", "-swift-version", "5", "-framework", "AppKit", "-framework", "WebKit"];
  const hash = crypto
    .createHash("sha256")
    .update(fs.readFileSync(SOURCE))
    .update(`\0${PLIST}\0${JSON.stringify(flags)}\0`)
    .update(swiftc)
    .digest("hex")
    .slice(0, 12);
  const dir = path.join(BENCH, "bin");
  const bin = path.join(dir, `mb-wkprobe-${hash}`);
  if (!fs.existsSync(bin)) {
    fs.mkdirSync(dir, { recursive: true });
    const plist = path.join(dir, `Info-${hash}.plist`);
    fs.writeFileSync(plist, PLIST);
    const partial = `${bin}.partial-${process.pid}`;
    try {
      execFileSync(
        "swiftc",
        [
          ...flags,
          "-Xlinker",
          "-sectcreate",
          "-Xlinker",
          "__TEXT",
          "-Xlinker",
          "__info_plist",
          "-Xlinker",
          plist,
          SOURCE,
          "-o",
          partial,
        ],
        { stdio: ["ignore", "inherit", "inherit"], timeout: 300000 },
      );
      fs.renameSync(partial, bin);
    } finally {
      fs.rmSync(partial, { force: true });
    }
  }
  return { bin, hash };
}

/** Every ~/Library entry WebKit or AppKit made for the probe's identifier, removed. */
function cleanLibrary() {
  const removed = [];
  for (const dir of LIBRARY_DIRS) {
    const root = path.join(os.homedir(), "Library", dir);
    let names = [];
    try {
      names = fs.readdirSync(root);
    } catch (_error) {
      continue;
    }
    for (const name of names) {
      if (name === BUNDLE_ID || name.startsWith(`${BUNDLE_ID}.`)) {
        fs.rmSync(path.join(root, name), { recursive: true, force: true, maxRetries: 5 });
        removed.push(`${dir}/${name}`);
      }
    }
  }
  return removed;
}

const BLANK_JOB = {
  base: "http://127.0.0.1:1",
  path: "/",
  subject: "",
  window: "hidden",
  steps: [],
  viewportWidth: 1,
  viewportHeight: 1,
  windowWidth: 1,
  windowHeight: 1,
  readyTimeoutMs: 0,
  settleMs: 0,
  hiddenWaitMs: 0,
};

/** The screen as the probe sees it, from a job with no steps and no window shown. */
async function screenNow(bin) {
  const work = tempDir("mb-wkprobe-screen-");
  try {
    const r = await runProbe(bin, {
      ...BLANK_JOB,
      store: "ephemeral",
      out: path.join(work, "screen.json"),
    });
    return r.out?.screenAtStart ?? null;
  } finally {
    removeTemp(work);
  }
}
const screenUsable = (s) => !!s && !s.locked && !s.displayAsleep && s.onConsole !== false;

function runProbe(bin, job, timeoutMs = 180000) {
  return new Promise((resolve) => {
    const child = track(spawn(bin, [JSON.stringify(job)], { stdio: ["ignore", "ignore", "pipe"] }));
    let stderr = "";
    child.stderr.on("data", (d) => {
      stderr += d;
    });
    const timer = setTimeout(() => child.kill("SIGKILL"), timeoutMs);
    child.on("exit", (code, signal) => {
      clearTimeout(timer);
      let out = null;
      try {
        out = JSON.parse(fs.readFileSync(job.out, "utf8"));
      } catch (_error) {
        out = null;
      }
      resolve({ code, signal, stderr: stderr.slice(-2000), out });
    });
  });
}

// --------------------------------------------------------------------------- server and proxy

function portFree(port) {
  return new Promise((resolve) => {
    const probe = net.createServer();
    probe.once("error", () => resolve(false));
    probe.once("listening", () => probe.close(() => resolve(true)));
    probe.listen(port, "127.0.0.1");
  });
}
async function freePorts(n) {
  const out = [];
  for (let p = PORTS[0]; p <= PORTS[1] && out.length < n; p++) {
    if (await portFree(p)) {
      out.push(p);
    }
  }
  if (out.length < n) {
    throw new Error(`fewer than ${n} free ports in ${PORTS[0]}-${PORTS[1]}`);
  }
  return out;
}

const unescapeHtml = (s) =>
  s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&");

const exited = (child) => child.exitCode !== null || child.signalCode !== null;

async function startServer({ metab, corpus, home, port, logPath, exitOnEof }) {
  const cache = path.join(home, "cache");
  const config = path.join(home, "config");
  fs.mkdirSync(cache, { recursive: true, mode: 0o700 });
  fs.mkdirSync(config, { recursive: true, mode: 0o700 });
  fs.chmodSync(home, 0o700);
  const fd = fs.openSync(logPath, "w", 0o600);
  const started = Date.now();
  let child;
  try {
    // With --exit-on-eof the server watches a stdin pipe this process holds open, so it
    // stops when this process dies, even by SIGKILL; the process group covers the rest.
    child = track(
      spawn(
        metab,
        [
          corpus,
          "--no-open",
          "--port",
          String(port),
          "--cache-dir",
          cache,
          "--config-dir",
          config,
          ...(exitOnEof ? ["--exit-on-eof"] : []),
        ],
        {
          cwd: home,
          detached: true,
          stdio: [exitOnEof ? "pipe" : "ignore", fd, fd],
          env: { ...process.env, METABROWSER_CACHE_DIR: cache, METABROWSER_CONFIG_DIR: config },
        },
      ),
    );
  } finally {
    fs.closeSync(fd);
  }
  let spawnError = null;
  child.once("error", (error) => {
    spawnError = error;
  });
  const server = { child, port, base: `http://127.0.0.1:${port}` };
  try {
    let progress = null;
    // The deadline is wall clock: each poll is bounded by what remains of it.
    const deadline = started + INVENTORY_DEADLINE_MS;
    while (Date.now() < deadline) {
      if (spawnError) {
        throw new Error(`server could not start: ${spawnError.message}`);
      }
      if (exited(child)) {
        throw new Error(
          `server exited (${child.exitCode ?? child.signalCode}): ${fs.readFileSync(logPath, "utf8").slice(-1500)}`,
        );
      }
      try {
        progress = await getJson(
          `${server.base}/api/index/progress`,
          Math.max(500, Math.min(5000, deadline - Date.now())),
        );
        if (progress.complete) {
          break;
        }
      } catch (_error) {
        // Not listening yet.
      }
      await sleep(100);
    }
    if (!progress?.complete) {
      throw new Error(
        `server did not finish its inventory within ${INVENTORY_DEADLINE_MS / 1000} s`,
      );
    }
    const html = await (
      await fetch(`${server.base}/view/`, { signal: AbortSignal.timeout(30000) })
    ).text();
    const m = html.match(/<div class="menu-version">([^<]*)<\/div>/);
    const log = fs.readFileSync(logPath, "utf8");
    return {
      ...server,
      readyMs: Date.now() - started,
      progress,
      served: m ? unescapeHtml(m[1]).trim() : null,
      servingLine: log.split("\n").find((l) => l.startsWith("Serving ")) ?? null,
    };
  } catch (error) {
    // The server is ours from the spawn on: a failed start stops it here, so it cannot
    // keep walking the corpus beside the rest of the series.
    await stopServer(server);
    throw error;
  }
}

async function stopServer(server) {
  if (!server?.child) {
    return;
  }
  const { child } = server;
  killGroup(child, "SIGTERM");
  for (let i = 0; i < 100 && !exited(child); i++) {
    await sleep(100);
  }
  if (!exited(child)) {
    killGroup(child, "SIGKILL");
  }
  for (let i = 0; i < 50 && !(await portFree(server.port)); i++) {
    await sleep(100);
  }
}

/**
 * A pass-through reverse proxy that logs every request: method, path, status,
 * conditional headers, bytes, and the upstream cache headers. GET /__mark?step=&at=
 * records a marker and answers 204 without reaching the server. Headers, `Host`
 * included, pass unchanged, so the server sees the origin the page has.
 */
function startProxy(listenPort, upstreamPort) {
  const log = [];
  const agent = new http.Agent({ keepAlive: true, maxSockets: 64 });
  const server = http.createServer((req, res) => {
    const t = Date.now();
    if (req.url.startsWith("/__mark")) {
      const u = new URL(req.url, "http://x");
      log.push({ mark: u.searchParams.get("step"), at: u.searchParams.get("at"), t });
      res.writeHead(204);
      res.end();
      return;
    }
    const entry = {
      t,
      method: req.method,
      url: req.url,
      inm: Boolean(req.headers["if-none-match"]),
      ims: Boolean(req.headers["if-modified-since"]),
      status: null,
      bytes: 0,
    };
    log.push(entry);
    const up = http.request(
      {
        host: "127.0.0.1",
        port: upstreamPort,
        method: req.method,
        path: req.url,
        headers: req.headers,
        agent,
      },
      (ur) => {
        entry.status = ur.statusCode;
        entry.cc = ur.headers["cache-control"] ?? null;
        entry.lm = ur.headers["last-modified"] ?? null;
        entry.etag = Boolean(ur.headers.etag);
        res.writeHead(ur.statusCode, ur.headers);
        ur.on("data", (c) => {
          entry.bytes += c.length;
          res.write(c);
        });
        ur.on("end", () => res.end());
      },
    );
    up.on("error", (e) => {
      entry.status = 502;
      try {
        res.writeHead(502);
        res.end(String(e));
      } catch (_error) {
        // The client went away.
      }
    });
    res.on("close", () => {
      if (!res.writableEnded) {
        up.destroy();
      }
    });
    req.pipe(up);
  });
  server.keepAliveTimeout = 60000;
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(listenPort, "127.0.0.1", () => {
      server.off("error", reject);
      resolve({
        log,
        base: `http://127.0.0.1:${listenPort}`,
        close: () =>
          new Promise((r) => {
            server.closeAllConnections?.();
            server.close(() => r());
          }),
      });
    });
  });
}

/** Proxy entries between a step's start and end marks. */
function stepEntries(log, step, from) {
  const start = log.findIndex((e, i) => i >= from && e.mark === step && e.at === "start");
  const end = log.findIndex((e, i) => i > start && e.mark === step && e.at === "end");
  if (start < 0 || end < 0) {
    return null;
  }
  return { entries: log.slice(start + 1, end).filter((e) => !e.mark), next: end + 1 };
}

// --------------------------------------------------------------------------- one run

const present = (v) => v !== null && v !== undefined;

function scenarioRow(name, stepOut, entries, ctx) {
  const facts = stepOut?.facts ?? {};
  const refusals = [];
  const { proxy, page } = requestCounts(entries, facts.resources);
  const screens = [stepOut?.screenBefore, stepOut?.screenAfter].filter(Boolean);
  for (const s of screens) {
    if (s.locked || s.displayAsleep || s.onConsole === false) {
      refusals.push([
        "screen",
        `locked ${s.locked}, display asleep ${s.displayAsleep}, on console ${s.onConsole}`,
      ]);
      break;
    }
  }
  if (!stepOut) {
    refusals.push(["probe", ctx.probeError ?? "the probe wrote no result for this step"]);
    return { name, refusals, proxy, page };
  }
  if (entries === null) {
    refusals.push(["marks", "the proxy did not log this step's start and end marks"]);
  }
  const vis = facts.vis ?? [];
  if (!(stepOut.raf >= 30)) {
    refusals.push(["raf", `${stepOut.raf} animation frames per second`]);
  }
  const out = { name, refusals };
  if (VISIBLE.has(name)) {
    if (vis.some(([, v]) => v !== "visible") || facts.visibility !== "visible") {
      refusals.push([
        "visibility",
        `visibility ${vis.map((v) => v[1]).join(",")} then ${facts.visibility}`,
      ]);
    }
    if (!present(stepOut.readyMs)) {
      refusals.push(["converged", "the subject never became ready"]);
    }
    Object.assign(out, {
      readyMs: stepOut.readyMs ?? null,
      mountedMs: stepOut.mountedMs ?? null,
    });
  } else {
    // The page clock's mark just before the show splits the visibility history: hidden
    // before it, and visible from the show to the end of the step.
    const chain = stepOut.showChain ?? null;
    const t0 = chain?.t0 ?? Number.POSITIVE_INFINITY;
    const before = vis.filter(([t]) => t < t0).map((v) => v[1]);
    const after = vis.filter(([t]) => t >= t0).map((v) => v[1]);
    if (
      stepOut.visibilityHidden !== "hidden" ||
      before.some((v) => v !== "hidden") ||
      stepOut.visibilityShown !== "visible" ||
      after.some((v) => v !== "visible") ||
      facts.visibility !== "visible"
    ) {
      refusals.push([
        "visibility",
        `hidden phase ${stepOut.visibilityHidden} (${before.join(",")}), shown ${stepOut.visibilityShown} (${after.join(",")}), at the end ${facts.visibility}`,
      ]);
    }
    const since = (v) => (present(v) && chain ? Math.round(v - chain.t0) : null);
    const painted = since(chain?.painted);
    if (painted === null) {
      refusals.push(["converged", "no painted frame with ready content after the show"]);
    }
    Object.assign(out, {
      hiddenMounted: present(stepOut.hiddenMountedMs),
      hiddenMountedMs: stepOut.hiddenMountedMs ?? null,
      hiddenReady: stepOut.hiddenReady === true,
      hiddenReadyMs: stepOut.hiddenReadyMs ?? null,
      showToPaintedReadyMs: painted,
      showToFirstFrameMs: since(chain?.firstFrame),
      showToReadyFrameMs: since(chain?.readyFrame),
      showToReadyDomMs: stepOut.showToReadyDomMs ?? null,
      showToVisibleMs: stepOut.showToVisibleMs ?? null,
      showToPaintedReadyNativeMs: stepOut.showToPaintedReadyNativeMs ?? null,
      showFrames: chain ? { visible: chain.frames, hidden: chain.hiddenFrames } : null,
      rafHidden: stepOut.rafHidden,
    });
  }
  if (facts.version !== ctx.version) {
    refusals.push(["build_identity", `page reports ${facts.version}, expected ${ctx.version}`]);
  }
  if (facts.w !== ctx.viewport[0] || facts.h !== ctx.viewport[1]) {
    refusals.push(["viewport", `${facts.w}x${facts.h}, requested ${ctx.viewport.join("x")}`]);
  }
  if ((facts.errors ?? []).length) {
    refusals.push(["page_exceptions", facts.errors[0]]);
  }
  if ((facts.alerts ?? []).length) {
    refusals.push(["rendered_errors", facts.alerts[0]]);
  }
  return {
    ...out,
    commitMs: stepOut.commitMs ?? null,
    finishMs: stepOut.finishMs ?? null,
    raf: stepOut.raf,
    dpr: facts.dpr ?? null,
    navType: facts.navType ?? null,
    fcp: facts.fcp ?? null,
    dcl: facts.dcl ?? null,
    visibility: vis,
    screen: screens,
    proxy,
    page,
    // What the page says it loaded: path, initiator, transfer, encoded, and decoded bytes.
    resources: (facts.resources ?? [])
      .slice(0, 300)
      .map((r) => [r[0].slice(0, 100), r[2], r[3], r[4]]),
    requests: (entries ?? []).slice(0, 200).map((e) => ({
      m: e.method === "GET" ? undefined : e.method,
      u: e.url.slice(0, 120),
      st: e.status,
      c: e.inm || e.ims ? 1 : undefined,
    })),
  };
}

async function oneRun(options) {
  const { name, series, condition, runIndex, pairIndex, corpus, scenarios, viewport, bin } =
    options;
  const { flags } = options;
  const dir = path.join(BENCH, name);
  const home = path.join(dir, "state", condition.label);
  fs.mkdirSync(home, { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.join(dir, "logs"), { recursive: true });
  const work = tempDir("mb-wkprobe-");
  const row = {
    schema: SCHEMA,
    probe_revision: PROBE_REVISION,
    name,
    series,
    condition: condition.label,
    run: runIndex,
    pair: pairIndex,
    started_at: new Date().toISOString(),
    load_start: loadavg(),
    build: buildProvenance(condition.metab),
    harness: harnessProvenance(),
    corpus: corpusProvenance(corpus),
    host: hostProvenance(),
    probe: { binary: path.basename(bin), bundle_id: BUNDLE_ID },
    viewport: viewport.join("x"),
    regime_flags: flags,
    scenarios_requested: scenarios,
    scenarios: {},
    refusals: [],
  };
  if (row.build.dirty === true && !row.build.content) {
    row.refusals.push(["build_identity", "a dirty build whose content could not be identified"]);
  }
  console.log(
    `\n== ${name} ${condition.label} run ${runIndex} (pair ${pairIndex}) load ${row.load_start.join(" ")}`,
  );
  let server = null;
  let proxy = null;
  const stores = [];
  // A file under the probe's own ~/Library name, which every cleanup removes: if it is
  // gone after a launch, the stores were wiped under this run, and it is refused.
  const sentinel = path.join(
    os.homedir(),
    "Library",
    "Caches",
    `${BUNDLE_ID}.run-${crypto.randomUUID()}`,
  );
  try {
    // A locked screen or a sleeping display hides every page, so a run that starts that
    // way is refused before it starts a server.
    const screen = flags.no_preflight ? null : await screenNow(bin);
    if (!flags.no_preflight && !screenUsable(screen)) {
      row.refusals.push(["screen", `before the run: ${JSON.stringify(screen)}`]);
      console.log(
        `== ${condition.label} run ${runIndex}: REFUSED (screen ${JSON.stringify(screen)})`,
      );
      return row;
    }
    fs.mkdirSync(path.dirname(sentinel), { recursive: true });
    fs.writeFileSync(sentinel, `${name} ${series} ${condition.label} run ${runIndex}\n`);
    const intact = (when) => {
      if (!fs.existsSync(sentinel)) {
        row.refusals.push([
          "store_wiped",
          `the probe's ~/Library data was removed ${when}: another series or a clean ran`,
        ]);
        return false;
      }
      return true;
    };
    const [serverPort, proxyPort] = await freePorts(2);
    server = await startServer({
      metab: condition.metab,
      corpus,
      home,
      port: serverPort,
      logPath: path.join(dir, "logs", `${series}-${condition.label}-run${runIndex}.log`),
      exitOnEof: condition.exitOnEof,
    });
    row.server = {
      port: serverPort,
      ready_ms: server.readyMs,
      served_version: server.served,
      indexed_files: server.progress.indexed_files,
      exit_on_eof: condition.exitOnEof,
    };
    if (server.served !== row.build.version) {
      row.refusals.push(["build_identity", `server reports ${server.served}`]);
    }
    if (!server.servingLine?.includes(`${corpus} at http://127.0.0.1:${serverPort}/`)) {
      row.refusals.push(["build_identity", "the server's serving line names another tree or port"]);
    }
    row.facts = await serverFacts(server.base);
    proxy = await startProxy(proxyPort, serverPort);
    row.ports = { server: serverPort, proxy: proxyPort };
    const job = (store, windowMode, steps, outName) => ({
      base: proxy.base,
      path: "/view/README.md",
      subject: "README.md",
      store,
      window: windowMode,
      steps,
      out: path.join(work, `${outName}.json`),
      viewportWidth: viewport[0],
      viewportHeight: viewport[1],
      windowWidth: 160,
      windowHeight: 100,
      readyTimeoutMs: 20000,
      settleMs: 1500,
      hiddenWaitMs: 5000,
      exitDelayMs: flags.exit_delay_ms,
    });
    const ctx = { version: row.build.version, viewport };
    const launches = {};
    const launch = async (label, j) => {
      const started = Date.now();
      const r = await runProbe(bin, j);
      launches[label] = { started, ended: Date.now(), code: r.code, signal: r.signal };
      if (r.out?.env) {
        row.webkit = r.out.env;
        if (r.out.env.bundleIdentifier !== BUNDLE_ID) {
          row.refusals.push([
            "bundle_identity",
            `${label}: the probe ran as ${r.out.env.bundleIdentifier || "no bundle identifier"}, so WebKit filed its data elsewhere`,
          ]);
        }
      }
      if (!r.out || r.code !== 0) {
        row.refusals.push(["probe", `${label}: exit ${r.code} ${r.signal ?? ""} ${r.stderr}`]);
      } else {
        if (r.out.offlineRules !== "on") {
          row.refusals.push(["offline_rules", `${label}: ${r.out.offlineRules}`]);
        }
        if (r.out.terminations) {
          row.refusals.push(["webcontent_terminated", `${label}: ${r.out.terminations}`]);
        }
        if (r.out.navigationErrors?.length) {
          row.refusals.push(["navigation", `${label}: ${r.out.navigationErrors[0]}`]);
        }
      }
      return r;
    };
    // The warm-up load fills the server's own caches from a throwaway ephemeral store.
    console.log("  warm-up launch (unrecorded)");
    await launch("warmup", job("ephemeral", "visible", ["load"], "warmup"));
    let cursor = proxy.log.length;
    const take = (out, stepName) => {
      const s = out?.steps?.find((x) => x.step === stepName) ?? null;
      const got = stepEntries(proxy.log, stepName, cursor);
      if (got) {
        cursor = got.next;
      }
      return { s, entries: got ? got.entries : null };
    };
    const newStore = () => {
      const id = crypto.randomUUID().toUpperCase();
      stores.push(id);
      return id;
    };
    const store = newStore();
    let firstLog = null;
    if (scenarios.some((s) => VISIBLE.has(s))) {
      const steps = ["load", ...(scenarios.includes("reload") ? ["reload"] : [])];
      const from = proxy.log.length;
      const a = await launch("first", job(store, "visible", steps, "first"));
      firstLog = proxy.log.slice(from);
      const cold = take(a.out, "load");
      if (scenarios.includes("cold")) {
        row.scenarios.cold = scenarioRow("cold", cold.s, cold.entries, ctx);
      }
      if (scenarios.includes("reload")) {
        const re = take(a.out, "reload");
        row.scenarios.reload = scenarioRow("reload", re.s, re.entries, ctx);
      }
    }
    if (scenarios.includes("relaunch") && intact("before the relaunch")) {
      const b = await launch("relaunch", job(store, "visible", ["load"], "relaunch"));
      const re = take(b.out, "load");
      row.scenarios.relaunch = scenarioRow("relaunch", re.s, re.entries, ctx);
      row.scenarios.relaunch.sinceFirstLaunchS =
        Math.round((launches.relaunch.started - launches.first.started) / 100) / 10;
      row.scenarios.relaunch.sinceFirstExitS =
        Math.round((launches.relaunch.started - launches.first.ended) / 100) / 10;
      row.relaunch_freshness = relaunchFreshness(firstLog, launches.relaunch.started);
      intact("during the relaunch");
    }
    if (scenarios.includes("hidden-then-show")) {
      // A store of its own, new and empty, so what this scenario measures does not
      // depend on which other scenarios ran before it.
      const c = await launch("hidden", job(newStore(), "hidden", ["hidden-load-show"], "hidden"));
      const h = take(c.out, "hidden-load-show");
      row.scenarios["hidden-then-show"] = scenarioRow("hidden-then-show", h.s, h.entries, ctx);
      intact("during the hidden launch");
    }
    // How old the stamped assets were when served: WebKit keeps one without
    // Cache-Control fresh for a tenth of that age (relaunch_freshness has the detail).
    const ages = proxy.log
      .filter((e) => e.lm && classify(e.url ?? "").family === "static")
      .map((e) => Math.round((e.t - Date.parse(e.lm)) / 1000));
    if (ages.length) {
      row.static_last_modified_age_s = [Math.min(...ages), Math.max(...ages)];
    }
    const dprs = new Set(Object.values(row.scenarios).map((sc) => sc.dpr));
    row.device_pixel_ratio = dprs.size === 1 ? [...dprs][0] : [...dprs];
    if (dprs.size > 1) {
      row.refusals.push(["viewport", `device pixel ratios ${[...dprs].join(", ")}`]);
    }
    for (const sc of Object.values(row.scenarios)) {
      for (const [guard, detail] of sc.refusals) {
        row.refusals.push([guard, `${sc.name}: ${detail}`]);
      }
    }
  } catch (error) {
    row.refusals.push(["run_error", String(error.stack || error).slice(0, 2000)]);
  } finally {
    for (const store of stores) {
      await runProbe(bin, {
        ...BLANK_JOB,
        store: `remove:${store}`,
        out: path.join(work, `remove-${store}.json`),
      });
    }
    await proxy?.close();
    await stopServer(server);
    row.library_removed = cleanLibrary();
    removeTemp(work);
    // Provenance again at the end: an editable build serves its files live and a corpus
    // can be moved under the server, and either would make this run a mixture.
    try {
      row.build_end = buildProvenance(condition.metab);
      row.corpus_end = corpusProvenance(corpus);
      row.refusals.push(
        ...provenanceChanges(
          { build: row.build, corpus: row.corpus },
          { build: row.build_end, corpus: row.corpus_end },
        ),
      );
    } catch (error) {
      row.refusals.push(["build_changed", `provenance unreadable at the end: ${error.message}`]);
    }
    row.load_end = loadavg();
    row.finished_at = new Date().toISOString();
    row.valid = row.refusals.length === 0;
  }
  for (const sc of Object.values(row.scenarios)) {
    const fam = (f) => {
      const p = sc.proxy.byFamily[f] ?? {};
      const c = sc.page.byFamily[f]?.cache ?? 0;
      return `${f.replace("_static", "")} ${p.network ?? 0}/${p.revalidated ?? 0}/${c}`;
    };
    const ready = sc.readyMs ?? sc.showToPaintedReadyMs ?? "n/a";
    const hidden =
      sc.name === "hidden-then-show"
        ? ` mounted while hidden ${sc.hiddenMountedMs ?? "never"}, ready while hidden ${sc.hiddenReady}, show to first frame ${sc.showToFirstFrameMs}`
        : "";
    console.log(
      `  ${sc.refusals.length ? "!!" : "  "} ${sc.name.padEnd(17)} ready ${String(ready).padStart(5)} requests ${String(sc.proxy.total).padStart(3)} +${sc.proxy.byClass.background ?? 0} background (net/reval/cache: ${FAMILIES.map(fam).join(", ")})${hidden}${sc.refusals.length ? `  ${sc.refusals.map((r) => r.join(": ")).join(" | ")}` : ""}`,
    );
  }
  console.log(
    `== ${condition.label} run ${runIndex}: ${row.valid ? "valid" : `REFUSED (${row.refusals.length})`}`,
  );
  return row;
}

async function cmdRun(argv) {
  if (process.platform !== "darwin") {
    throw new Error("the WKWebView probe runs on macOS only");
  }
  const { values } = parseArgs({
    args: argv,
    options: {
      corpus: { type: "string" },
      condition: { type: "string", multiple: true },
      runs: { type: "string", default: "3" },
      scenarios: { type: "string", default: SCENARIOS.join(",") },
      name: { type: "string", default: "adhoc" },
      out: { type: "string" },
      viewport: { type: "string", default: "1440x900" },
      lock: { type: "string", default: DEFAULT_LOCK },
      "wait-for-screen": { type: "string", default: "0" },
      // Diagnostic only: skip the screen check before each run. With the screen locked,
      // every scenario's own screen guard then refuses, which exercises the other guards
      // while nobody is at the Mac; the row records it, and compare notes it.
      "no-preflight": { type: "boolean", default: false },
      // Diagnostic only: keep each probe process alive this long after it writes its
      // result, to test whether the relaunch depends on unflushed cache writes.
      "exit-delay-ms": { type: "string", default: "0" },
    },
  });
  if (!values.corpus) {
    throw new Error("--corpus PATH is required");
  }
  const corpus = path.resolve(values.corpus);
  const corpus0 = corpusProvenance(corpus);
  if (!corpus0.commit) {
    throw new Error(`${corpus} is not a Git checkout; the corpus needs a commit identity`);
  }
  if (corpus0.dirty !== false) {
    throw new Error(`${corpus} has uncommitted changes; serve a clean corpus`);
  }
  if (!fs.existsSync(path.join(corpus, "README.md"))) {
    throw new Error(`${corpus} has no README.md at its root, the probe's fixed subject`);
  }
  const conditions = (values.condition ?? []).map((spec) => {
    const at = spec.indexOf("=");
    const label = spec.slice(0, Math.max(at, 0));
    const metab = path.resolve(spec.slice(at + 1));
    if (at <= 0 || !PLAIN_WORD.test(label) || !fs.existsSync(metab)) {
      throw new Error(`--condition LABEL=PATH/TO/metab with a plain-word label, got ${spec}`);
    }
    return { label, metab };
  });
  if (conditions.length < 1 || conditions.length > 2) {
    throw new Error("give one or two --condition LABEL=PATH");
  }
  if (new Set(conditions.map((c) => c.label)).size !== conditions.length) {
    throw new Error("give each --condition its own label");
  }
  if (!PLAIN_WORD.test(values.name)) {
    throw new Error("--name must be a plain word");
  }
  const scenarios = values.scenarios.split(",");
  for (const s of scenarios) {
    if (!SCENARIOS.includes(s)) {
      throw new Error(`unknown scenario ${s}; known: ${SCENARIOS.join(",")}`);
    }
  }
  const viewport = /^\d+x\d+$/.test(values.viewport) ? values.viewport.split("x").map(Number) : [];
  if (!(viewport[0] >= 1440 && viewport[1] >= 900)) {
    throw new Error("--viewport WxH must be at least 1440x900, the size the counts are taken at");
  }
  const runs = /^\d+$/.test(values.runs) ? Number(values.runs) : 0;
  if (!(runs >= 1)) {
    throw new Error("--runs must be a positive integer");
  }
  const exitDelay = /^\d+$/.test(values["exit-delay-ms"]) ? Number(values["exit-delay-ms"]) : -1;
  if (exitDelay < 0 || exitDelay > 60000) {
    throw new Error("--exit-delay-ms must be a whole number of milliseconds up to 60000");
  }
  const flags = { no_preflight: values["no-preflight"], exit_delay_ms: exitDelay };
  const outFile = values.out
    ? path.resolve(values.out)
    : path.join(BENCH, values.name, "runs.jsonl");
  takeLock(path.resolve(values.lock), `run --name ${values.name}`);
  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  for (const c of conditions) {
    c.exitOnEof = supportsExitOnEof(c.metab);
    if (!c.exitOnEof) {
      console.log(
        `${c.label}: this metab has no --exit-on-eof; its server is stopped by process group only`,
      );
    }
  }
  const { bin, hash } = compileProbe();
  // Optionally wait for an unlocked screen and a lit display before the first run.
  const waitS = Number.parseInt(values["wait-for-screen"], 10) || 0;
  for (let waited = 0; waited < waitS && !screenUsable(await screenNow(bin)); waited += 30) {
    if (waited === 0) {
      console.log(`waiting up to ${waitS} s for an unlocked screen and a lit display`);
    }
    await sleep(30000);
  }
  const leftover = cleanLibrary();
  if (leftover.length) {
    console.log(`removed probe data left by an earlier run: ${leftover.join(", ")}`);
  }
  const series = new Date().toISOString().replace(/[:.]/g, "-");
  console.log(
    `${SCHEMA} r${PROBE_REVISION} ${values.name} series ${series}: ${runs} run(s) x ${conditions.map((c) => c.label).join(", ")}, scenarios ${scenarios.join(",")}, probe ${hash}, lock ${values.lock}`,
  );
  const count = {};
  if (fs.existsSync(outFile)) {
    for (const r of parseRows(fs.readFileSync(outFile, "utf8"), outFile)) {
      count[r.condition] = Math.max(count[r.condition] ?? 0, r.run ?? 0);
    }
  }
  let refused = 0;
  for (let pair = 0; pair < runs; pair++) {
    const order =
      conditions.length === 2 && pair % 2 === 1 ? [conditions[1], conditions[0]] : conditions;
    for (const condition of order) {
      count[condition.label] = (count[condition.label] ?? 0) + 1;
      const row = await oneRun({
        name: values.name,
        series,
        condition,
        runIndex: count[condition.label],
        pairIndex: pair + 1,
        corpus,
        scenarios,
        viewport,
        bin,
        flags,
      });
      fs.appendFileSync(outFile, `${JSON.stringify(row)}\n`);
      refused += row.valid ? 0 : 1;
    }
  }
  console.log(`\nwrote ${path.relative(REPO, outFile)}; ${refused} run(s) refused`);
  return refused ? 1 : 0;
}

// --------------------------------------------------------------------------- reading

const readRows = (file) => parseRows(fs.readFileSync(file, "utf8"), file);
const print = (lines) => process.stdout.write(`${lines.join("\n")}\n`);

function cmdSummarize(argv) {
  const { positionals } = parseArgs({ args: argv, allowPositionals: true, options: {} });
  if (positionals.length !== 1) {
    throw new CompareRefusal("summarize RUNS.jsonl");
  }
  print(summarize(readRows(positionals[0])));
  return 0;
}

function cmdCompare(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      control: { type: "string" },
      candidate: { type: "string" },
      tolerance: { type: "string", default: "1.3" },
      expect: { type: "string", multiple: true },
      format: { type: "string", default: "markdown" },
    },
  });
  if (positionals.length !== 1) {
    throw new CompareRefusal("compare RUNS.jsonl --control LABEL --candidate LABEL");
  }
  const result = compareProbe(readRows(positionals[0]), {
    control: values.control,
    candidate: values.candidate,
    tolerance: Number.parseFloat(values.tolerance),
    expect: values.expect ?? [],
  });
  if (values.format === "json") {
    const { control, candidate, ...rest } = result;
    console.log(
      JSON.stringify(
        { control: control.label, candidate: candidate.label, ...rest },
        (_k, v) => (v === Number.POSITIVE_INFINITY ? "Infinity" : v),
        1,
      ),
    );
  } else {
    print(formatComparison(result));
  }
  return result.exitCode;
}

function cmdClean(argv) {
  const { values } = parseArgs({
    args: argv,
    options: { lock: { type: "string", default: DEFAULT_LOCK } },
  });
  takeLock(path.resolve(values.lock), "clean");
  const removed = cleanLibrary();
  console.log(removed.length ? `removed ${removed.join(", ")}` : "nothing to remove");
  return 0;
}

const USAGE = `usage:
  wkprobe.mjs run --corpus PATH --condition LABEL=PATH/TO/metab [--condition LABEL=PATH]
                  [--runs 3] [--scenarios ${SCENARIOS.join(",")}] [--name NAME] [--out FILE]
                  [--viewport 1440x900] [--wait-for-screen SECONDS] [--lock DIR]
                  [--no-preflight] [--exit-delay-ms MS]   (the last two are diagnostics)
  wkprobe.mjs summarize RUNS.jsonl
  wkprobe.mjs compare RUNS.jsonl --control LABEL --candidate LABEL [--tolerance 1.3]
                  [--expect SCENARIO.METRIC:lower|higher]... [--format markdown|json]
  wkprobe.mjs clean [--lock DIR]   (remove the probe's data stores and caches under ~/Library)
run and clean hold the series lock (default ${DEFAULT_LOCK}) and refuse while another holds it.
compare exits 0 when complete with no wrong-way result, 1 on a wrong-way result, a gap, or
an expectation not met, and 2 when it refuses.`;

const [mode, ...rest] = process.argv.slice(2);
const commands = { run: cmdRun, summarize: cmdSummarize, compare: cmdCompare, clean: cmdClean };
if (!commands[mode]) {
  console.error(USAGE);
  process.exit(2);
}
try {
  process.exitCode = await commands[mode](rest);
} catch (error) {
  console.error(`wkprobe.mjs ${mode}: ${error.message}`);
  process.exitCode = 2;
}
