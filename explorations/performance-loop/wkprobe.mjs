#!/usr/bin/env node
// WKWebView probe: what the native app's engine fetches and when it is ready.
//
//   node explorations/performance-loop/wkprobe.mjs run --corpus PATH \
//     --condition control=/path/to/metab [--condition candidate=/path/to/metab] \
//     [--runs 3] [--scenarios cold,reload,relaunch,hidden-then-show] [--name NAME]
//   node explorations/performance-loop/wkprobe.mjs summarize .bench/wkprobe/NAME/runs.jsonl
//   node explorations/performance-loop/wkprobe.mjs compare .bench/wkprobe/NAME/runs.jsonl \
//     --control control --candidate candidate [--tolerance 1.3]
//   node explorations/performance-loop/wkprobe.mjs clean
//
// Each run starts a fresh server from the condition's `metab`, puts a logging proxy in
// front of it (the request ground truth: WebKit's own APIs do not report subresource
// loads), compiles and runs `wkprobe.swift` against the proxy, and writes one JSONL row.
// macOS only, and the screen must stay unlocked with the display awake: a hidden page
// never finishes its first view, so the screen guard refuses the run instead. See
// README.md, "WKWebView Probe".
import { execFileSync, spawn } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";

const SCHEMA = "wkwebview-probe/v1";
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
const MIN_RUNS = 3;
const SCENARIOS = ["cold", "reload", "relaunch", "hidden-then-show"];
const VISIBLE = new Set(["cold", "reload", "relaunch"]);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// --------------------------------------------------------------------------- utilities

function git(cwd, ...args) {
  try {
    return execFileSync("git", ["-C", cwd, ...args], {
      encoding: "utf8",
      timeout: 10000,
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch (_error) {
    return null;
  }
}

const loadavg = () => os.loadavg().map((v) => Math.round(v * 100) / 100);

const children = new Set();
function track(child) {
  children.add(child);
  child.on("exit", () => children.delete(child));
  return child;
}
function killAll() {
  for (const child of children) {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch (_error) {
      try {
        child.kill("SIGKILL");
      } catch (_ignored) {
        // Already gone.
      }
    }
  }
}
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    killAll();
    cleanLibrary();
    process.exit(130);
  });
}
process.on("exit", killAll);

/** Route family of a request path, for counting how each kind of thing was served. */
function family(urlPath) {
  const p = urlPath.split("?")[0];
  if (/^\/(view|commit|pull|pulls)(\/|$)/.test(p) || p === "/") {
    return "document";
  }
  if (p.startsWith("/static/")) {
    return "static";
  }
  if (p.startsWith("/plugin-static/")) {
    return "plugin_static";
  }
  if (p.startsWith("/kpress-static/")) {
    return "kpress_static";
  }
  if (p === "/api/events") {
    return "stream";
  }
  if (p.startsWith("/api/")) {
    return "data";
  }
  return "other";
}
const FAMILIES = ["document", "static", "plugin_static", "kpress_static", "data"];

// --------------------------------------------------------------------------- provenance

function buildProvenance(metab) {
  const version = execFileSync(metab, ["--version"], {
    encoding: "utf8",
    timeout: 60000,
    cwd: os.tmpdir(),
  }).trim();
  const venv = path.dirname(path.dirname(metab));
  let source = null;
  const libs = path.join(venv, "lib");
  if (fs.existsSync(libs)) {
    for (const py of fs.readdirSync(libs)) {
      const site = path.join(libs, py, "site-packages");
      for (const entry of fs.existsSync(site) ? fs.readdirSync(site) : []) {
        const direct = path.join(site, entry, "direct_url.json");
        if (/^metabrowser-.*\.dist-info$/.test(entry) && fs.existsSync(direct)) {
          const info = JSON.parse(fs.readFileSync(direct, "utf8"));
          if (info.dir_info?.editable && String(info.url).startsWith("file://")) {
            source = decodeURIComponent(new URL(info.url).pathname);
          }
        }
      }
    }
  }
  const status = source ? git(source, "--no-optional-locks", "status", "--porcelain") : null;
  return {
    metab,
    version,
    source,
    commit: source ? git(source, "rev-parse", "HEAD") : null,
    dirty: status === null ? null : status.length > 0,
  };
}

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

// --------------------------------------------------------------------------- probe binary

/** Compile the probe once per source and compiler, with the identifying Info.plist. */
function compileProbe() {
  const swiftc = execFileSync("swiftc", ["--version"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  const hash = crypto
    .createHash("sha256")
    .update(fs.readFileSync(SOURCE))
    .update(swiftc)
    .digest("hex")
    .slice(0, 12);
  const dir = path.join(BENCH, "bin");
  const bin = path.join(dir, `mb-wkprobe-${hash}`);
  if (!fs.existsSync(bin)) {
    fs.mkdirSync(dir, { recursive: true });
    const plist = path.join(dir, "Info.plist");
    fs.writeFileSync(
      plist,
      `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
<key>CFBundleName</key><string>mb-wkprobe</string>
</dict></plist>
`,
    );
    execFileSync(
      "swiftc",
      [
        "-O",
        "-swift-version",
        "5",
        "-framework",
        "AppKit",
        "-framework",
        "WebKit",
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
        bin,
      ],
      { stdio: ["ignore", "inherit", "inherit"], timeout: 300000 },
    );
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

/** The screen as the probe sees it, from a job with no steps and no window shown. */
async function screenNow(bin) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "mb-wkprobe-screen-"));
  try {
    const r = await runProbe(bin, {
      base: "http://127.0.0.1:1",
      path: "/",
      subject: "",
      store: "ephemeral",
      window: "hidden",
      steps: [],
      out: path.join(work, "screen.json"),
      viewportWidth: 1,
      viewportHeight: 1,
      windowWidth: 1,
      windowHeight: 1,
      readyTimeoutMs: 0,
      settleMs: 0,
      hiddenWaitMs: 0,
    });
    return r.out?.screenAtStart ?? null;
  } finally {
    fs.rmSync(work, { recursive: true, force: true });
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

async function startServer({ metab, corpus, home, port, logPath }) {
  const cache = path.join(home, "cache");
  const config = path.join(home, "config");
  fs.mkdirSync(cache, { recursive: true, mode: 0o700 });
  fs.mkdirSync(config, { recursive: true, mode: 0o700 });
  fs.chmodSync(home, 0o700);
  const fd = fs.openSync(logPath, "w", 0o600);
  let child;
  try {
    child = track(
      spawn(
        metab,
        [corpus, "--no-open", "--port", String(port), "--cache-dir", cache, "--config-dir", config],
        {
          cwd: home,
          detached: true,
          stdio: ["ignore", fd, fd],
          env: { ...process.env, METABROWSER_CACHE_DIR: cache, METABROWSER_CONFIG_DIR: config },
        },
      ),
    );
  } finally {
    fs.closeSync(fd);
  }
  const base = `http://127.0.0.1:${port}`;
  for (let i = 0; i < 1800; i++) {
    if (child.exitCode !== null) {
      throw new Error(`server exited: ${fs.readFileSync(logPath, "utf8").slice(-1500)}`);
    }
    try {
      const r = await fetch(`${base}/api/index/progress`, { signal: AbortSignal.timeout(5000) });
      if (r.ok && (await r.json()).complete) {
        const html = await (await fetch(`${base}/view/`)).text();
        const m = html.match(/<div class="menu-version">([^<]*)<\/div>/);
        return { child, port, base, served: m ? unescapeHtml(m[1]).trim() : null };
      }
    } catch (_error) {
      // Not listening yet.
    }
    await sleep(100);
  }
  throw new Error("server did not finish its inventory within 180 s");
}

async function stopServer(server) {
  if (!server?.child) {
    return;
  }
  try {
    process.kill(-server.child.pid, "SIGTERM");
  } catch (_error) {
    // Already gone.
  }
  for (let i = 0; i < 100 && server.child.exitCode === null; i++) {
    await sleep(100);
  }
  if (server.child.exitCode === null) {
    try {
      process.kill(-server.child.pid, "SIGKILL");
    } catch (_error) {
      // Already gone.
    }
  }
}

/**
 * A pass-through reverse proxy that logs every request: method, path, status,
 * conditional headers, bytes, and the upstream cache headers. GET /__mark?step=&at=
 * records a marker and answers 204 without reaching the server.
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
    const headers = { ...req.headers, host: `127.0.0.1:${upstreamPort}` };
    const up = http.request(
      { host: "127.0.0.1", port: upstreamPort, method: req.method, path: req.url, headers, agent },
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
  return new Promise((resolve) => {
    server.listen(listenPort, "127.0.0.1", () =>
      resolve({
        log,
        base: `http://127.0.0.1:${listenPort}`,
        close: () =>
          new Promise((r) => {
            server.closeAllConnections?.();
            server.close(() => r());
          }),
      }),
    );
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

function scenarioRow(name, stepOut, entries, ctx) {
  const facts = stepOut?.facts ?? {};
  const refusals = [];
  const proxy = { total: 0, conditional: 0, byFamily: {} };
  for (const e of entries ?? []) {
    proxy.total += 1;
    if (e.inm || e.ims) {
      proxy.conditional += 1;
    }
    const f = family(e.url);
    proxy.byFamily[f] ??= { network: 0, revalidated: 0, error: 0 };
    const d = e.status === 304 ? "revalidated" : e.status && e.status < 400 ? "network" : "error";
    proxy.byFamily[f][d] += 1;
  }
  // Resource Timing names everything the page loaded; the proxy names everything that
  // reached the network. A page entry with no matching proxy request in the step was
  // served from WebKit's cache. (WebKit's own sizes cannot say so: a disk-cache hit after
  // a relaunch can report a non-zero transferSize.) Proxy requests the page does not list
  // are the document, worker scripts, and the event stream.
  const page = { entries: 0, byFamily: {} };
  const reached = new Map();
  for (const e of entries ?? []) {
    reached.set(e.url, (reached.get(e.url) ?? 0) + 1);
  }
  for (const [u] of facts.resources ?? []) {
    page.entries += 1;
    const f = family(u);
    page.byFamily[f] ??= { entries: 0, cache: 0 };
    page.byFamily[f].entries += 1;
    const n = reached.get(u) ?? 0;
    if (n > 0) {
      reached.set(u, n - 1);
    } else {
      page.byFamily[f].cache += 1;
    }
  }
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
  const vis = (facts.vis ?? []).map((v) => v[1]);
  if (VISIBLE.has(name)) {
    if (vis.some((v) => v !== "visible") || facts.visibility !== "visible") {
      refusals.push(["visibility", `visibility ${vis.join(",")} then ${facts.visibility}`]);
    }
    if (stepOut.readyMs === null || stepOut.readyMs === undefined) {
      refusals.push(["converged", "the subject never became ready"]);
    }
    if (!(stepOut.raf >= 30)) {
      refusals.push(["raf", `${stepOut.raf} animation frames per second`]);
    }
  } else {
    if (stepOut.visibilityHidden !== "hidden" || stepOut.visibilityShown !== "visible") {
      refusals.push([
        "visibility",
        `hidden phase ${stepOut.visibilityHidden}, shown ${stepOut.visibilityShown}`,
      ]);
    }
    if (stepOut.hiddenMountedMs === null || stepOut.hiddenMountedMs === undefined) {
      refusals.push(["converged", "the first view did not mount while hidden"]);
    }
    if (stepOut.showToReadyMs === null || stepOut.showToReadyMs === undefined) {
      refusals.push(["converged", "the subject never became ready after showing"]);
    }
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
    name,
    refusals,
    readyMs: stepOut.readyMs ?? null,
    mountedMs: stepOut.mountedMs ?? null,
    commitMs: stepOut.commitMs ?? null,
    finishMs: stepOut.finishMs ?? null,
    hiddenMountedMs: stepOut.hiddenMountedMs,
    hiddenReady: stepOut.hiddenReady,
    hiddenReadyMs: stepOut.hiddenReadyMs,
    showToReadyMs: stepOut.showToReadyMs,
    rafHidden: stepOut.rafHidden,
    raf: stepOut.raf,
    navType: facts.navType ?? null,
    fcp: facts.fcp ?? null,
    dcl: facts.dcl ?? null,
    visibility: facts.vis ?? [],
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
  const preflight = options.preflight !== false;
  const dir = path.join(BENCH, name);
  const home = path.join(dir, "state", condition.label);
  fs.mkdirSync(home, { recursive: true, mode: 0o700 });
  fs.mkdirSync(path.join(dir, "logs"), { recursive: true });
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "mb-wkprobe-"));
  const row = {
    schema: SCHEMA,
    name,
    series,
    condition: condition.label,
    run: runIndex,
    pair: pairIndex,
    started_at: new Date().toISOString(),
    load_start: loadavg(),
    build: buildProvenance(condition.metab),
    harness: (() => {
      const status = git(REPO, "--no-optional-locks", "status", "--porcelain");
      return { commit: git(REPO, "rev-parse", "HEAD"), dirty: status ? status.length > 0 : false };
    })(),
    corpus: { commit: git(corpus, "rev-parse", "HEAD") },
    host: hostProvenance(),
    probe: { binary: path.basename(bin), bundle_id: BUNDLE_ID },
    viewport: viewport.join("x"),
    scenarios_requested: scenarios,
    scenarios: {},
    refusals: [],
  };
  console.log(`\n== ${name} ${condition.label} run ${runIndex} load ${row.load_start.join(" ")}`);
  // A locked screen or a sleeping display hides every page, so a run that starts that
  // way is refused before it starts a server.
  const screen = preflight ? await screenNow(bin) : null;
  if (preflight && !screenUsable(screen)) {
    row.refusals.push(["screen", `before the run: ${JSON.stringify(screen)}`]);
    row.library_removed = cleanLibrary();
    row.load_end = loadavg();
    row.finished_at = new Date().toISOString();
    row.valid = false;
    console.log(
      `== ${condition.label} run ${runIndex}: REFUSED (screen ${JSON.stringify(screen)})`,
    );
    return row;
  }
  let server = null;
  let proxy = null;
  const stores = [];
  try {
    const [serverPort, proxyPort] = await freePorts(2);
    server = await startServer({
      metab: condition.metab,
      corpus,
      home,
      port: serverPort,
      logPath: path.join(dir, "logs", `${series}-${condition.label}-run${runIndex}.log`),
    });
    if (server.served !== row.build.version) {
      row.refusals.push(["build_identity", `server reports ${server.served}`]);
    }
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
    });
    const ctx = { version: row.build.version, viewport };
    const launches = {};
    const launch = async (label, j) => {
      const t = Date.now();
      const r = await runProbe(bin, j);
      launches[label] = { started: t, code: r.code, signal: r.signal };
      if (r.out?.env) {
        row.webkit = r.out.env;
      }
      if (!r.out || r.code !== 0) {
        row.refusals.push(["probe", `${label}: exit ${r.code} ${r.signal ?? ""} ${r.stderr}`]);
      } else {
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
    const take = (out, label, stepName) => {
      const s = out?.steps?.find((x) => x.step === stepName) ?? null;
      const got = stepEntries(proxy.log, stepName, cursor);
      if (got) {
        cursor = got.next;
      }
      return { s, entries: got ? got.entries : null, label };
    };
    const store = crypto.randomUUID().toUpperCase();
    stores.push(store);
    const wantA = scenarios.some((s) => s !== "hidden-then-show");
    if (wantA) {
      const steps = ["load", ...(scenarios.includes("reload") ? ["reload"] : [])];
      const a = await launch("first", job(store, "visible", steps, "first"));
      const cold = take(a.out, "first", "load");
      if (scenarios.includes("cold")) {
        row.scenarios.cold = scenarioRow("cold", cold.s, cold.entries, ctx);
      }
      if (scenarios.includes("reload")) {
        const re = take(a.out, "first", "reload");
        row.scenarios.reload = scenarioRow("reload", re.s, re.entries, ctx);
      }
    }
    if (scenarios.includes("relaunch")) {
      const b = await launch("relaunch", job(store, "visible", ["load"], "relaunch"));
      const re = take(b.out, "relaunch", "load");
      row.scenarios.relaunch = scenarioRow("relaunch", re.s, re.entries, ctx);
      row.scenarios.relaunch.sinceFirstLaunchS = launches.first
        ? Math.round((launches.relaunch.started - launches.first.started) / 100) / 10
        : null;
    }
    if (scenarios.includes("hidden-then-show")) {
      const c = await launch("hidden", job(store, "hidden", ["hidden-load-show"], "hidden"));
      const h = take(c.out, "hidden", "hidden-load-show");
      row.scenarios["hidden-then-show"] = scenarioRow("hidden-then-show", h.s, h.entries, ctx);
    }
    // How long WebKit may treat the stamped assets as fresh without asking: 10% of the
    // age their Last-Modified gives them, when no Cache-Control says otherwise.
    const ages = proxy.log
      .filter((e) => e.lm && family(e.url ?? "") === "static")
      .map((e) => Math.round((e.t - Date.parse(e.lm)) / 1000));
    if (ages.length) {
      row.static_last_modified_age_s = [Math.min(...ages), Math.max(...ages)];
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
        base: "http://127.0.0.1:1",
        path: "/",
        subject: "",
        store: `remove:${store}`,
        window: "hidden",
        steps: [],
        out: path.join(work, `remove-${store}.json`),
        viewportWidth: 1,
        viewportHeight: 1,
        windowWidth: 1,
        windowHeight: 1,
        readyTimeoutMs: 0,
        settleMs: 0,
        hiddenWaitMs: 0,
      });
    }
    await proxy?.close();
    await stopServer(server);
    row.library_removed = cleanLibrary();
    fs.rmSync(work, { recursive: true, force: true });
  }
  row.load_end = loadavg();
  row.finished_at = new Date().toISOString();
  row.valid = row.refusals.length === 0;
  for (const sc of Object.values(row.scenarios)) {
    const fam = (f) => {
      const p = sc.proxy.byFamily[f] ?? {};
      const c = sc.page.byFamily[f]?.cache ?? 0;
      return `${f.replace("_static", "")} ${p.network ?? 0}/${p.revalidated ?? 0}/${c}`;
    };
    console.log(
      `  ${sc.refusals.length ? "!!" : "  "} ${sc.name.padEnd(17)} ready ${String(sc.readyMs ?? sc.showToReadyMs ?? "n/a").padStart(5)} requests ${String(sc.proxy.total).padStart(3)} (net/reval/cache: ${FAMILIES.map(fam).join(", ")})${sc.hiddenMountedMs !== undefined ? ` hidden mounted ${sc.hiddenMountedMs} ready while hidden ${sc.hiddenReady} show-to-ready ${sc.showToReadyMs}` : ""}${sc.refusals.length ? `  ${sc.refusals.map((r) => r.join(": ")).join(" | ")}` : ""}`,
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
      "wait-for-screen": { type: "string", default: "0" },
      // Diagnostic only: run with the screen locked, so every scenario's own screen
      // guard refuses it; used to exercise the other guards while nobody is at the Mac.
      "no-preflight": { type: "boolean", default: false },
    },
  });
  if (!values.corpus) {
    throw new Error("--corpus PATH is required");
  }
  const corpus = path.resolve(values.corpus);
  const conditions = (values.condition ?? []).map((spec) => {
    const at = spec.indexOf("=");
    const label = spec.slice(0, at);
    const metab = path.resolve(spec.slice(at + 1));
    if (at <= 0 || !/^[\w.-]+$/.test(label) || !fs.existsSync(metab)) {
      throw new Error(`--condition LABEL=PATH/TO/metab, got ${spec}`);
    }
    return { label, metab };
  });
  if (conditions.length < 1 || conditions.length > 2) {
    throw new Error("give one or two --condition LABEL=PATH");
  }
  if (!/^[\w.-]+$/.test(values.name)) {
    throw new Error("--name must be a plain word");
  }
  const scenarios = values.scenarios.split(",");
  for (const s of scenarios) {
    if (!SCENARIOS.includes(s)) {
      throw new Error(`unknown scenario ${s}; known: ${SCENARIOS.join(",")}`);
    }
  }
  const viewport = values.viewport.split("x").map(Number);
  if (!(viewport[0] >= 1440 && viewport[1] >= 900)) {
    throw new Error("--viewport must be at least 1440x900, the size the counts are taken at");
  }
  const runs = Number.parseInt(values.runs, 10);
  const outFile = values.out
    ? path.resolve(values.out)
    : path.join(BENCH, values.name, "runs.jsonl");
  fs.mkdirSync(path.dirname(outFile), { recursive: true });
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
    `${SCHEMA} ${values.name} series ${series}: ${runs} run(s) x ${conditions.map((c) => c.label).join(", ")}, scenarios ${scenarios.join(",")}, probe ${hash}`,
  );
  const count = {};
  if (fs.existsSync(outFile)) {
    for (const r of readRows(outFile)) {
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
        preflight: !values["no-preflight"],
      });
      fs.appendFileSync(outFile, `${JSON.stringify(row)}\n`);
      refused += row.valid ? 0 : 1;
    }
  }
  console.log(`\nwrote ${path.relative(REPO, outFile)}; ${refused} run(s) refused`);
  return refused ? 1 : 0;
}

// --------------------------------------------------------------------------- statistics

function metricsOf(row) {
  const out = {};
  for (const [name, sc] of Object.entries(row.scenarios ?? {})) {
    const put = (key, kind, v) => {
      if (v !== null && v !== undefined) {
        out[`${name}.${key}`] = { kind, v };
      }
    };
    put("ready_ms", "time", sc.readyMs);
    put("mounted_ms", "time", sc.mountedMs);
    put("commit_ms", "time", sc.commitMs);
    put("hidden_mounted_ms", "time", sc.hiddenMountedMs);
    put("show_to_ready_ms", "time", sc.showToReadyMs);
    put(
      "ready_while_hidden",
      "count",
      sc.hiddenReady === undefined ? null : sc.hiddenReady ? 1 : 0,
    );
    put("requests", "count", sc.proxy.total);
    put("conditional_requests", "count", sc.proxy.conditional);
    for (const f of FAMILIES) {
      put(`${f}_network`, "count", sc.proxy.byFamily[f]?.network ?? 0);
      put(`${f}_revalidated`, "count", sc.proxy.byFamily[f]?.revalidated ?? 0);
      put(`${f}_cache`, "count", sc.page.byFamily[f]?.cache ?? 0);
    }
  }
  return out;
}

function readRows(file) {
  return fs
    .readFileSync(file, "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => {
      const r = JSON.parse(l);
      if (r.schema !== SCHEMA) {
        throw new Error(`${file} holds a ${r.schema} row; this reads ${SCHEMA}`);
      }
      return r;
    });
}

function groupConditions(rows) {
  const out = new Map();
  for (const r of rows) {
    if (!out.has(r.condition)) {
      out.set(r.condition, { label: r.condition, valid: [], refused: [] });
    }
    out.get(r.condition)[r.valid ? "valid" : "refused"].push(r);
  }
  for (const c of out.values()) {
    const ids = new Set(
      c.valid.map((r) => `${r.build.version} ${r.build.commit} ${r.build.dirty}`),
    );
    if (ids.size > 1) {
      throw new Error(`condition ${c.label} pools ${ids.size} builds: ${[...ids].join(" / ")}`);
    }
  }
  return out;
}

function collect(condition) {
  const values = new Map();
  for (const r of condition.valid) {
    for (const [k, { kind, v }] of Object.entries(metricsOf(r))) {
      if (!values.has(k)) {
        values.set(k, { kind, xs: [] });
      }
      values.get(k).xs.push(v);
    }
  }
  return values;
}

function stat(xs) {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return {
    n: s.length,
    median: s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2,
    min: s[0],
    max: s[s.length - 1],
  };
}
const fmt = (s, kind) =>
  kind === "time"
    ? `${Math.round(s.median)} (${Math.round(s.min)}–${Math.round(s.max)})`
    : s.min === s.max
      ? `${s.min}`
      : `${s.min}–${s.max}`;
const firstLine = (s) => String(s).split("\n")[0].slice(0, 200);

function cmdSummarize(argv) {
  const { positionals } = parseArgs({ args: argv, allowPositionals: true, options: {} });
  if (positionals.length !== 1) {
    throw new Error("summarize RUNS.jsonl");
  }
  const lines = [];
  for (const c of groupConditions(readRows(positionals[0])).values()) {
    const loads = c.valid.flatMap((r) => [r.load_start[0], r.load_end[0]]);
    const wk = c.valid[0]?.webkit;
    lines.push(`### Condition \`${c.label}\``, "");
    lines.push(
      `${c.valid.length} valid run(s), ${c.refused.length} refused; ${c.valid[0]?.build.version ?? "no valid run"}; macOS ${c.valid[0]?.host.macos ?? "?"}, WebKit ${wk?.webkitVersion ?? "?"}; load average (1 min) ${loads.length ? `${Math.min(...loads)}–${Math.max(...loads)}` : "n/a"}.`,
      "",
    );
    for (const r of c.refused) {
      lines.push(
        `- refused run ${r.run}: ${r.refusals
          .slice(0, 3)
          .map((x) => firstLine(x.join(": ")))
          .join(" | ")}`,
      );
    }
    if (c.refused.length) {
      lines.push("");
    }
    const values = collect(c);
    const names = [...new Set([...values.keys()].map((k) => k.split(".")[0]))];
    lines.push(
      "| Scenario | Ready ms | Requests | Conditional | network / revalidated / cache by family |",
    );
    lines.push("| --- | ---: | ---: | ---: | --- |");
    for (const n of names) {
      const g = (k) => values.get(`${n}.${k}`);
      const ready = g("show_to_ready_ms") ?? g("ready_ms");
      const fams = FAMILIES.map((f) => {
        const parts = ["network", "revalidated", "cache"].map((d) => {
          const v = g(`${f}_${d}`);
          return v ? fmt(stat(v.xs), "count") : "n/a";
        });
        return `${f.replace("_static", "-static")} ${parts.join(" / ")}`;
      }).join("; ");
      lines.push(
        `| \`${n}\`${g("show_to_ready_ms") ? " (show to ready)" : ""} | ${ready ? fmt(stat(ready.xs), "time") : "n/a"} | ${g("requests") ? fmt(stat(g("requests").xs), "count") : "n/a"} | ${g("conditional_requests") ? fmt(stat(g("conditional_requests").xs), "count") : "n/a"} | ${fams} |`,
      );
    }
    const h = (k) => values.get(`hidden-then-show.${k}`);
    if (h("hidden_mounted_ms")) {
      lines.push(
        "",
        `Hidden then shown: mounted while hidden at ${fmt(stat(h("hidden_mounted_ms").xs), "time")} ms; ready while hidden in ${h("ready_while_hidden").xs.filter((x) => x).length} of ${h("ready_while_hidden").xs.length} runs; show to ready ${h("show_to_ready_ms") ? fmt(stat(h("show_to_ready_ms").xs), "time") : "n/a"} ms.`,
      );
    }
    lines.push("");
  }
  process.stdout.write(`${lines.join("\n")}\n`);
  return 0;
}

// The accept rule of the performance loop: ranges apart at three or more runs per
// condition, and for a time also a ratio beyond the tolerance (1.3 rough cut, never 2x).
function cmdCompare(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      control: { type: "string" },
      candidate: { type: "string" },
      tolerance: { type: "string", default: "1.3" },
    },
  });
  if (positionals.length !== 1) {
    throw new Error("compare RUNS.jsonl --control LABEL --candidate LABEL");
  }
  const tolerance = Number.parseFloat(values.tolerance);
  if (!(tolerance > 1 && tolerance < 2)) {
    throw new Error("--tolerance must be above 1 and below 2 (1.3 rough cut; never 2x)");
  }
  const groups = groupConditions(readRows(positionals[0]));
  const labels = [...groups.keys()];
  const A = groups.get(values.control ?? labels[0]);
  const B = groups.get(values.candidate ?? labels[1]);
  if (!A || !B || A === B) {
    throw new Error(`need two distinct conditions; found ${labels.join(", ")}`);
  }
  for (const c of [A, B]) {
    if (c.valid.length < MIN_RUNS) {
      throw new Error(
        `condition ${c.label} has ${c.valid.length} valid run(s); compare needs ${MIN_RUNS}`,
      );
    }
  }
  const all = [...A.valid, ...B.valid];
  const notes = [];
  for (const [what, get] of [
    ["corpus commits", (r) => r.corpus.commit],
    ["WebKit versions", (r) => r.webkit?.webkitVersion],
    ["harness commits", (r) => r.harness.commit],
  ]) {
    const set = new Set(all.map(get));
    if (set.size > 1) {
      if (what === "corpus commits") {
        throw new Error(`the conditions were measured on different corpora: ${[...set]}`);
      }
      notes.push(`runs used ${set.size} ${what}: ${[...set].join(", ")}`);
    }
  }
  const ca = collect(A);
  const cb = collect(B);
  const lines = [
    `### \`${B.label}\` against \`${A.label}\` in WKWebView`,
    "",
    `${A.valid.length} and ${B.valid.length} valid runs (${A.refused.length} and ${B.refused.length} refused). Tolerance ${tolerance}x for times; counts are judged on their ranges.`,
    "",
    ...notes.map((n) => `- ${n}`),
    ...(notes.length ? [""] : []),
    "| Metric | Control | Candidate | Ratio | Verdict |",
    "| --- | ---: | ---: | ---: | --- |",
  ];
  let apart = 0;
  for (const [k, va] of ca) {
    const vb = cb.get(k);
    if (!vb) {
      continue;
    }
    const sa = stat(va.xs);
    const sb = stat(vb.xs);
    const overlap = !(sb.min > sa.max || sb.max < sa.min);
    const ratio = sa.median > 0 ? sb.median / sa.median : null;
    let verdict = "no detected difference";
    if (!overlap) {
      apart += 1;
      const dir = sb.median > sa.median ? "higher" : "lower";
      verdict =
        va.kind === "time"
          ? ratio !== null && (ratio >= tolerance || ratio <= 1 / tolerance)
            ? `${dir}, beyond the ${tolerance}x tolerance`
            : `${dir}, ranges apart but within the ${tolerance}x tolerance (not a result)`
          : `${dir}, ranges apart`;
    }
    if (!overlap || sa.median !== 0 || sb.median !== 0) {
      lines.push(
        `| \`${k}\` | ${fmt(sa, va.kind)} | ${fmt(sb, va.kind)} | ${ratio === null ? "n/a" : `${ratio.toFixed(2)}x`} | ${verdict} |`,
      );
    }
  }
  lines.push("", `${apart} metric(s) with non-overlapping ranges.`);
  process.stdout.write(`${lines.join("\n")}\n`);
  return 0;
}

function cmdClean() {
  const removed = cleanLibrary();
  console.log(removed.length ? `removed ${removed.join(", ")}` : "nothing to remove");
  return 0;
}

const USAGE = `usage:
  wkprobe.mjs run --corpus PATH --condition LABEL=PATH/TO/metab [--condition LABEL=PATH]
                  [--runs 3] [--scenarios ${SCENARIOS.join(",")}] [--name NAME] [--out FILE]
  wkprobe.mjs summarize RUNS.jsonl
  wkprobe.mjs compare RUNS.jsonl --control LABEL --candidate LABEL [--tolerance 1.3]
  wkprobe.mjs clean     (remove the probe's data stores and caches under ~/Library)`;

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
