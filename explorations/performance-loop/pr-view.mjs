// One measured run of a pull request's page or of the Pulls tab, on a GitHub checkout served
// by an installed build, with a cold or a warm cache.
//
//   node explorations/performance-loop/pr-view.mjs --metab BIN --checkout DIR --root DIR \
//     --cache DIR [--fresh-cache] --scenario pr|pulls [--pr N] [--seconds S] [--port P] \
//     [--expect-summary] [--prepare-store N] [--reload] [--git-shim] \
//     [--label L] [--step NAME] [--build-ref SHA] [--out FILE.jsonl]
//
// pr-view-pairs.sh runs it in back-to-back pairs of two builds and pr-view-stats.mjs reads
// the lines it writes. --prepare-store N, after the measurement, asks the same server for
// pull request N's comparison, which in checkout mode attaches the Git store the cache then
// keeps, so a later run on that cache can draw the Diff summary. --reload measures the same
// document again from the same server and browser, a second line (step NAME-reload): the
// long-running server's case, apart from a fresh server's first requests. --git-shim logs
// every git call too, for attribution only: a perl start per git call perturbs timing.
//
// Each run starts its own server (`metab <checkout> --no-open --port P`) with the given
// --cache-dir and a --config-dir under ROOT, and its own headless Chrome with a fresh profile
// under ROOT. --fresh-cache empties the cache first: a cold run. Without it the cache is the
// one an earlier run left, so a warm run is a cold run's cache read by a new server and a new
// browser. Nothing of the reader's own cache or configuration is read or written.
//
// The server runs with a `gh` shim first on PATH that logs each gh call's start, end, exit
// status, and arguments (cut short) before it hands back the real gh's answer, so a run
// counts the gh time and calls a build spent; the shim costs a perl start per call (about
// 10 ms), the same for every build. METABROWSER_REQUEST_LOG=verbose logs every request in
// the server log, kept under ROOT.
//
// In the page, every animation frame records the first frame at which each milestone holds,
// in ms from the document's time origin (navigation start). The selectors are ones every
// measured build has, apart from the Diff summary and the Pulls change line, which arrived
// in #478 and #491; a build without them reports them as null.
//
//   pr     title_any          `.github-pull-title` on screen (the loading heading counts)
//          title              `.github-pull-title-with-state` on screen: the record's title
//          description        the description's `.github-pull-text[data-part="body"]` on screen
//          description_final  ...as rendered Markdown or the empty note, no plain placeholder
//          summary_pending    `.github-pull-summary-pending`, computed visibility visible
//          summary            `.github-pull-summary > .diff-summary` or its `.change-line`
//          complete           the last of title and description_final, and of summary with
//                             --expect-summary (a cache with a Git store: see --prepare-store)
//   pulls  rows[n]            row #n's `a.github-pulls-row` on screen
//          lines[n]           `li.github-pulls-item[data-number] > .github-pulls-entry
//                             > .github-pulls-change` (mb-1z7j; a build before it, in
//                             `.github-pulls-change-group`) with aria-label "Changed files: ..."
//          pending[n]         a `.tally-pending` in that change line, visibility visible
//
// Every 250 ms the recorder also asks GET /api/plugin/github/pulls-prefetch (a build from
// #355 on) and keeps each lane outcome with the page time it was first seen. After the page
// settles, or --seconds pass, it keeps every /api/ resource timing with its Server-Timing,
// then asks each GET /api/plugin/ URL the page asked once more (`replay`, the same server
// with its caches in memory) and records the client time and Server-Timing. One JSON line
// per run goes to --out.
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";
import { CHROME, Connection, sleep } from "./pr-cdp.mjs";

const { values: args } = parseArgs({
  options: {
    metab: { type: "string" },
    checkout: { type: "string" },
    root: { type: "string" },
    cache: { type: "string" },
    "fresh-cache": { type: "boolean", default: false },
    scenario: { type: "string", default: "pr" },
    pr: { type: "string", default: "470" },
    seconds: { type: "string", default: "40" },
    port: { type: "string" },
    label: { type: "string", default: "" },
    "build-ref": { type: "string", default: "" },
    round: { type: "string", default: "" },
    out: { type: "string" },
    "expect-summary": { type: "boolean", default: false },
    "prepare-store": { type: "string" },
    step: { type: "string", default: "" },
    reload: { type: "boolean", default: false },
    "git-shim": { type: "boolean", default: false },
  },
});
for (const name of ["metab", "checkout", "root", "cache"]) {
  if (!args[name]) {
    throw new Error(`--${name} is required`);
  }
}
const scenario = args.scenario;
if (scenario !== "pr" && scenario !== "pulls") {
  throw new Error("--scenario is pr or pulls");
}
const ROOT = path.resolve(String(args.root));
const CACHE = path.resolve(String(args.cache));
// The server starts in ROOT, so a relative --metab or --checkout would resolve there.
const METAB = path.resolve(String(args.metab));
const CHECKOUT = path.resolve(String(args.checkout));
const runId = `${Date.now().toString(36)}-${process.pid}`;
/** A port nothing listens on now, from the kernel, so a run never reaches another server. */
async function freePort() {
  return await new Promise((resolve, reject) => {
    const probe = net.createServer();
    probe.once("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const { port: free } = /** @type {import("node:net").AddressInfo} */ (probe.address());
      probe.close(() => resolve(free));
    });
  });
}
const port = Number(args.port ?? (await freePort()));
const seconds = Number(args.seconds);
const prNumber = Number(args.pr);
const origin = `http://127.0.0.1:${port}`;
const load = () => os.loadavg().map((v) => Math.round(v * 100) / 100);

const result = {
  recorder: "pr-view/v1",
  label: args.label,
  build_ref: args["build-ref"],
  round: args.round,
  version: execFileSync(METAB, ["--version"]).toString().trim(),
  scenario,
  step: args.step,
  pr: scenario === "pr" ? prNumber : null,
  cache: args["fresh-cache"] ? "cold" : "warm",
  started: new Date().toISOString(),
  load_start: load(),
  host: { cpus: os.cpus().length, platform: `${os.platform()} ${os.release()}` },
};

// ── gh and git shims ──────────────────────────────────
const shimDir = path.join(ROOT, `shim-${runId}`);
fs.mkdirSync(shimDir, { recursive: true });
/** @type {Record<string, string>} */
const shimLogs = {};
/** Put a logging `name` first on the server's PATH; it runs the real one and logs the call. */
function shim(name) {
  const real = execFileSync("/usr/bin/which", [name]).toString().trim();
  const log = path.join(ROOT, `${name}-${runId}.log`);
  shimLogs[name] = log;
  fs.writeFileSync(
    path.join(shimDir, name),
    `#!/usr/bin/perl
use strict; use warnings; use Time::HiRes qw(time);
my $real = '${real}'; my $log = '${log}';
my $t0 = time;
my $pid = fork();
if (!defined $pid || $pid == 0) { exec($real, @ARGV) or exit 127; }
for my $s (qw(TERM INT HUP)) { $SIG{$s} = sub { kill $s, $pid; }; }
my $r; do { $r = waitpid($pid, 0); } while ($r == -1 && $!{EINTR});
my $st = $?; my $t1 = time;
my $what = substr(join(' ', @ARGV), 0, 160); $what =~ s/[\\t\\n]/ /g;
if (open(my $fh, '>>', $log)) { printf $fh "%.3f\\t%.3f\\t%d\\t%s\\n", $t0, $t1, $st >> 8, $what; close $fh; }
exit(($st & 127) ? 128 + ($st & 127) : $st >> 8);
`,
    { mode: 0o755 },
  );
}
shim("gh");
if (args["git-shim"]) {
  shim("git");
}

// ── server ────────────────────────────────────────────
let server = null;
const serverLog = path.join(ROOT, `server-${runId}.log`);
async function startServer() {
  if (args["fresh-cache"]) {
    fs.rmSync(CACHE, { recursive: true, force: true });
  }
  fs.mkdirSync(CACHE, { recursive: true, mode: 0o700 });
  const cfg = path.join(ROOT, "cfg");
  fs.mkdirSync(cfg, { recursive: true, mode: 0o700 });
  const logFd = fs.openSync(serverLog, "w", 0o600);
  const t0 = Date.now();
  server = spawn(METAB, [CHECKOUT, "--no-open", "--port", String(port), "--cache-dir", CACHE], {
    cwd: ROOT,
    detached: true,
    stdio: ["ignore", logFd, logFd],
    env: {
      ...process.env,
      PATH: `${shimDir}:${process.env.PATH}`,
      METABROWSER_CACHE_DIR: CACHE,
      METABROWSER_CONFIG_DIR: cfg,
      METABROWSER_STATE_DIR: path.join(ROOT, `state-${runId}`),
      METABROWSER_RECORD_RECENT: "0",
      METABROWSER_REQUEST_LOG: "verbose",
    },
  });
  fs.closeSync(logFd);
  let spawnError = null;
  server.on("error", (error) => {
    spawnError = error;
  });
  for (let i = 0; i < 600; i++) {
    if (spawnError !== null) {
      throw new Error(`could not start ${METAB}: ${spawnError}`);
    }
    try {
      const r = await fetch(`${origin}/api/tree?depth=1`);
      // Only our own child's answer counts: one that has exited cannot be what answered.
      if (r.ok && server.exitCode === null && server.signalCode === null) {
        result.server_ready_ms = Date.now() - t0;
        result.server_started_epoch_ms = t0;
        return;
      }
    } catch {}
    if (server.exitCode !== null) {
      break;
    }
    await sleep(100);
  }
  throw new Error(
    `server did not become ready: ${fs.readFileSync(serverLog, "utf8").slice(-2000)}`,
  );
}
/** Stop the server's process group, and kill it if it has not exited within 5 s. */
async function stopServer() {
  if (!server || server.exitCode !== null || server.signalCode !== null) {
    return;
  }
  const exited = new Promise((resolve) => server.once("exit", resolve));
  try {
    process.kill(-server.pid, "SIGTERM");
  } catch {
    return;
  }
  if ((await Promise.race([exited.then(() => true), sleep(5000).then(() => false)])) === false) {
    try {
      process.kill(-server.pid, "SIGKILL");
    } catch {}
  }
}

// ── chrome, headless ──────────────────────────────────
const FLAGS = [
  "--headless=new",
  "--remote-debugging-port=0",
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-background-networking",
  "--disable-component-update",
  "--disable-default-apps",
  "--disable-sync",
  "--disable-domain-reliability",
  "--no-pings",
  "--metrics-recording-only",
  "--password-store=basic",
  "--use-mock-keychain",
  "--disable-renderer-backgrounding",
  "--disable-backgrounding-occluded-windows",
  "--disable-background-timer-throttling",
  "--force-color-profile=srgb",
  "--force-device-scale-factor=1",
  "--window-size=1400,900",
  "--disable-features=Translate,OptimizationHints,MediaRouter,InterestFeedContentSuggestions",
];
let chrome = null;
const profile = path.join(ROOT, `prof-${runId}`);
async function launchChrome() {
  fs.mkdirSync(profile, { recursive: true });
  chrome = spawn(CHROME, [...FLAGS, `--user-data-dir=${profile}`, "about:blank"], {
    stdio: ["ignore", "ignore", "ignore"],
  });
  const portFile = path.join(profile, "DevToolsActivePort");
  for (let i = 0; i < 300; i++) {
    if (fs.existsSync(portFile)) {
      const [p, wsPath] = fs.readFileSync(portFile, "utf8").trim().split("\n");
      if (p && wsPath) {
        const conn = new Connection(`ws://127.0.0.1:${p}${wsPath}`);
        await conn.open();
        return conn;
      }
    }
    await sleep(100);
  }
  throw new Error("Chrome did not expose a DevTools endpoint");
}

// ── in-page sampler ───────────────────────────────────
const SAMPLER = `(() => {
  const S = { scenario: ${JSON.stringify(scenario)}, expectSummary: ${args["expect-summary"]}, marks: {}, rows: {}, lines: {}, pending: {}, labels: {}, pendingNow: 0,
    trail: [], summaryRow: false, changeGroup: false, viewport: null, visibility: null };
  window.__pv = S;
  const onScreen = (el) => {
    if (!el || !el.isConnected) { return false; }
    const cs = getComputedStyle(el);
    if (cs.visibility !== "visible" || cs.display === "none") { return false; }
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
  };
  const mark = (name, t) => { if (!(name in S.marks)) { S.marks[name] = Math.round(t); } };
  const pr = (t) => {
    const title = document.querySelector(".github-pull-title");
    if (onScreen(title)) { mark("title_any", t); }
    if (onScreen(document.querySelector(".github-pull-title-with-state"))) { mark("title", t); }
    const body = document.querySelector('.github-pull-text[data-part="body"]');
    if (onScreen(body)) {
      mark("description", t);
      if (!body.querySelector(":scope > .github-pull-plain") && body.querySelector(":scope > .metabrowser-kpress-host, :scope > .github-pull-empty")) {
        mark("description_final", t);
      }
    }
    const row = document.querySelector(".github-pull-summary");
    if (row) { S.summaryRow = true; }
    const pend = document.querySelector(".github-pull-summary-pending");
    const pv = onScreen(pend);
    if (pv) { mark("summary_pending", t); }
    const sum = document.querySelector(".github-pull-summary > .diff-summary, .github-pull-summary .change-line");
    const sv = onScreen(sum);
    if (sv) { mark("summary", t); }
    const st = (pv ? "P" : "") + (sv ? "S" : "") + (body ? "D" : "") + (title ? "T" : "");
    const last = S.trail[S.trail.length - 1];
    if (!last || last[1] !== st) { S.trail.push([Math.round(t), st]); }
    const need = ["title", "description_final"].concat(S.expectSummary && S.summaryRow ? ["summary"] : []);
    if (need.every((n) => n in S.marks)) { mark("complete", Math.max(...need.map((n) => S.marks[n]))); }
  };
  const pulls = (t) => {
    let shown = 0, lined = 0, pendingNow = 0;
    for (const a of document.querySelectorAll("a.github-pulls-row[data-number]")) {
      const n = a.dataset.number;
      if (!(n in S.rows) && onScreen(a)) { S.rows[n] = Math.round(t); }
      if (!(n in S.rows)) { continue; }
      shown++;
      const li = a.closest("li.github-pulls-item");
      // A pair's older build may hold the line in its own group, before mb-1z7j's item zone.
      const c = li && li.matches("[data-number]") ? li.querySelector(":scope > .github-pulls-entry > .github-pulls-change, :scope > .github-pulls-change-group > .github-pulls-change") : null;
      if (li && li.querySelector(":scope > .github-pulls-change-group")) { S.changeGroup = true; }
      if (!c) { continue; }
      if (!(n in S.lines) && (c.getAttribute("aria-label") || "").startsWith("Changed files:") && onScreen(c)) { S.lines[n] = Math.round(t); }
      S.labels[n] = c.getAttribute("aria-label") || "";
      const pv = onScreen(c.querySelector(".tally-pending"));
      if (pv) { pendingNow++; }
      if (!(n in S.pending) && pv) { S.pending[n] = Math.round(t); }
      if (n in S.lines) { lined++; }
    }
    if (shown > 0) { mark("first_row", Math.min(...Object.values(S.rows))); }
    S.pendingNow = pendingNow;
    const st = shown + "/" + lined + "/" + pendingNow;
    const last = S.trail[S.trail.length - 1];
    if (!last || last[1] !== st) { S.trail.push([Math.round(t), st]); }
  };
  const loop = (t) => {
    try {
      S.viewport = [innerWidth, innerHeight];
      S.visibility = document.visibilityState;
      if (S.scenario === "pr") { pr(performance.now()); } else { pulls(performance.now()); }
    } catch (e) { S.error = String(e); }
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
})();`;

// ── one run ───────────────────────────────────────────
const lane = { available: null, seen: new Map(), keys: new Set(), last: null };
async function pollLane(timeOrigin) {
  try {
    const r = await fetch(`${origin}/api/plugin/github/pulls-prefetch`);
    if (r.status === 404) {
      lane.available = false;
      return;
    }
    const body = await r.json();
    lane.available = true;
    lane.last = body;
    const now = Math.round(Date.now() - timeOrigin);
    for (const x of body.recent ?? []) {
      const key = `${x.kind}:${x.number}:${x.outcome}:${x.at}`;
      if (!lane.keys.has(key)) {
        lane.keys.add(key);
        lane.seen.set(key, {
          kind: x.kind,
          number: x.number,
          outcome: x.outcome,
          at: x.at,
          seen_ms: now,
        });
      }
    }
  } catch {}
}

function serverTiming(header) {
  /** @type {Record<string, number | string>} */
  const out = {};
  for (const part of (header || "").split(",")) {
    const [name, ...rest] = part.trim().split(";");
    if (!name) {
      continue;
    }
    for (const r of rest) {
      const [k, v] = r.trim().split("=");
      if (k === "dur") {
        out[name] = Number(v);
      } else if (k === "desc") {
        out[`${name}_desc`] = (v || "").replace(/"/g, "");
      }
    }
  }
  return out;
}

function readShimLog(name, timeOrigin) {
  const log = shimLogs[name];
  if (!log || !fs.existsSync(log)) {
    return [];
  }
  return fs
    .readFileSync(log, "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      const [t0, t1, rc, what] = line.split("\t");
      return {
        start_ms: Math.round(Number(t0) * 1000 - timeOrigin),
        ms: Math.round((Number(t1) - Number(t0)) * 1000),
        rc: Number(rc),
        what: (what || "").slice(0, 120),
      };
    });
}

// After the measurement, on the same server: a reader's own comparison request for
// pull request *n* (`{"number", "retry": true, "comparison": true}`, which every measured
// build accepts), which in checkout mode attaches the Git store the cache keeps. It waits
// until GET pull names a comparison for *n*, so the next server on this cache starts with a
// store, as an everyday cache has one.
async function prepareStore(n) {
  const t0 = Date.now();
  const post = await fetch(`${origin}/api/plugin/github/pull-refresh`, {
    method: "POST",
    headers: { "content-type": "application/json", origin },
    body: JSON.stringify({ number: n, retry: true, comparison: true }),
  });
  const out = { number: n, status: post.status, refresh: (await post.json())?.refresh ?? null };
  while (Date.now() - t0 < 120000) {
    await sleep(500);
    try {
      const env = await (await fetch(`${origin}/api/plugin/github/pull?number=${n}`)).json();
      if (env?.comparison_route || env?.record?.comparison) {
        out.ms = Date.now() - t0;
        out.attached = true;
        return out;
      }
    } catch {}
  }
  out.ms = Date.now() - t0;
  out.attached = false;
  return out;
}

/**
 * Load *url* in *page* and record into *rec* until the page settles or --seconds pass.
 * Returns the page's time origin, in epoch ms.
 */
async function measure(page, url, rec) {
  const evaluate = async (expression) =>
    (await page.send("Runtime.evaluate", { expression, returnByValue: true })).result?.value;
  rec.url_path = new URL(url).pathname;
  rec.load_navigate = load();
  lane.seen = new Map();
  await page.send("Page.navigate", { url });
  let timeOrigin = null;
  const t0 = Date.now();
  let settledSince = null;
  while (Date.now() - t0 < seconds * 1000) {
    await sleep(250);
    if (timeOrigin === null) {
      const o = await evaluate(`window.__pv ? performance.timeOrigin : null`);
      timeOrigin = typeof o === "number" && o >= t0 - 1000 ? o : null;
    }
    if (timeOrigin === null) {
      continue;
    }
    await pollLane(timeOrigin);
    const s = await evaluate(
      `window.__pv ? JSON.stringify({ m: window.__pv.marks, rows: Object.keys(window.__pv.rows).length, lines: Object.keys(window.__pv.lines).length, pendingNow: window.__pv.pendingNow, cg: window.__pv.changeGroup }) : null`,
    );
    if (!s) {
      continue;
    }
    const st = JSON.parse(s);
    const done =
      scenario === "pr"
        ? "complete" in st.m
        : st.rows > 0 &&
          (st.cg
            ? st.lines > 0 && st.pendingNow === 0
            : Date.now() - timeOrigin > (st.m.first_row ?? 0) + 3000);
    if (done) {
      settledSince ??= Date.now();
      if (Date.now() - settledSince >= 1500) {
        break;
      }
    } else {
      settledSince = null;
    }
  }
  rec.timed_out = settledSince === null;
  rec.load_end = load();
  const pv = JSON.parse(await evaluate(`JSON.stringify(window.__pv)`));
  rec.viewport = pv.viewport;
  rec.visibility = pv.visibility;
  rec.marks = pv.marks;
  rec.trail = pv.trail;
  if (pv.error) {
    rec.sampler_error = pv.error;
  }
  if (scenario === "pr") {
    rec.summary_row = pv.summaryRow;
  } else {
    rec.change_group = pv.changeGroup;
    rec.rows = pv.rows;
    rec.lines = pv.lines;
    rec.pending = pv.pending;
    rec.labels = pv.labels;
    const lines = Object.values(pv.lines);
    rec.marks.last_line = lines.length ? Math.max(...lines) : null;
    rec.marks.last_row = Object.values(pv.rows).length ? Math.max(...Object.values(pv.rows)) : null;
  }
  rec.api = JSON.parse(
    await evaluate(`JSON.stringify(performance.getEntriesByType("resource")
      .filter((e) => e.name.includes("/api/"))
      .map((e) => ({ path: e.name.replace(location.origin, ""), start: Math.round(e.startTime),
        end: Math.round(e.responseEnd), ms: Math.round(e.duration), bytes: e.transferSize,
        timing: Object.fromEntries((e.serverTiming || []).map((s) => [s.name, Math.round(s.duration * 10) / 10])) })))`),
  );
  rec.time_origin_epoch_ms = timeOrigin;
  rec.end_ms = timeOrigin === null ? null : Math.round(Date.now() - timeOrigin);
  await pollLane(timeOrigin ?? Date.now());
  rec.lane = {
    available: lane.available,
    outcomes: [...lane.seen.values()],
    queue: lane.last?.queue ?? null,
  };
  return timeOrigin;
}

/** The server half: each GET the page made of a plugin route, once more, serially. */
async function replayRoutes(api) {
  const replay = [];
  const seen = new Set();
  for (const e of api) {
    const p = e.path.split("#")[0];
    if (!p.startsWith("/api/plugin/") || seen.has(p) || p.includes("pulls-prefetch")) {
      continue;
    }
    if (seen.size >= 40) {
      break;
    }
    seen.add(p);
    const r0 = performance.now();
    try {
      const ctl = new AbortController();
      const timer = setTimeout(() => ctl.abort(), 10000);
      const r = await fetch(`${origin}${p}`, {
        headers: { "accept-encoding": "gzip" },
        signal: ctl.signal,
      });
      const body = await r.arrayBuffer();
      clearTimeout(timer);
      replay.push({
        path: p.slice(0, 200),
        status: r.status,
        ms: Math.round((performance.now() - r0) * 10) / 10,
        bytes: body.byteLength,
        timing: serverTiming(r.headers.get("server-timing")),
      });
    } catch (error) {
      replay.push({ path: p.slice(0, 200), error: String(error) });
    }
  }
  return replay;
}

/** The calls of *name* (gh or git) that started in *rec*'s window, from its shim's log. */
function shimWindow(name, rec, from) {
  const all = readShimLog(name, rec.time_origin_epoch_ms ?? Date.now());
  const list = all.filter(
    (c) => c.start_ms >= from && (rec.end_ms === null || c.start_ms < rec.end_ms),
  );
  return {
    calls: list.length,
    total_ms: list.reduce((s, c) => s + c.ms, 0),
    failed: list.filter((c) => c.rc !== 0).length,
    list: list.slice(0, 400),
  };
}

const records = [result];
let conn = null;
try {
  await startServer();
  conn = await launchChrome();
  const page = await conn.newPage("about:blank");
  await page.send("Page.enable");
  await page.send("Page.addScriptToEvaluateOnNewDocument", { source: SAMPLER });
  const url = scenario === "pr" ? `${origin}/pull/${prNumber}` : `${origin}/pulls`;
  await measure(page, url, result);
  // Every call since the server started is the first load's, startup included.
  result.gh = shimWindow("gh", result, Number.NEGATIVE_INFINITY);
  if (args["git-shim"]) {
    result.git = shimWindow("git", result, Number.NEGATIVE_INFINITY);
  }
  result.replay = await replayRoutes(result.api);
  if (args.reload) {
    // The same document loaded again in the same browser, from the same server: its
    // caches in memory, the browser's HTTP cache warm. What a reader who reloads, or opens
    // the page again in another tab, waits for.
    const again = {
      ...Object.fromEntries(
        Object.entries(result).filter(([k]) =>
          ["recorder", "label", "build_ref", "round", "version", "scenario", "pr", "host"].includes(
            k,
          ),
        ),
      ),
      step: `${args.step || scenario}-reload`,
      cache: result.cache,
      reload_of: result.started,
      started: new Date().toISOString(),
      load_start: load(),
      server_ready_ms: result.server_ready_ms,
    };
    records.push(again);
    await measure(page, url, again);
    again.gh = shimWindow("gh", again, 0);
    if (args["git-shim"]) {
      again.git = shimWindow("git", again, 0);
    }
  }
  if (args["prepare-store"]) {
    result.prepare_store = await prepareStore(Number(args["prepare-store"]));
  }
} catch (error) {
  records[records.length - 1].error = String(error?.stack ?? error);
} finally {
  try {
    conn?.close();
  } catch {}
  try {
    chrome?.kill("SIGKILL");
  } catch {}
  await stopServer();
  fs.rmSync(profile, { recursive: true, force: true });
  fs.rmSync(shimDir, { recursive: true, force: true });
  for (const log of Object.values(shimLogs)) {
    fs.rmSync(log, { force: true });
  }
}
let failed = false;
for (const rec of records) {
  rec.server_log = path.basename(serverLog);
  if (args.out) {
    fs.appendFileSync(String(args.out), `${JSON.stringify(rec)}\n`);
  }
  failed ||= Boolean(rec.error);
  console.log(
    `${rec.label} ${rec.step || rec.cache} ${scenario} ${rec.version} load=${rec.load_start?.[0]} ` +
      `marks=${JSON.stringify(rec.marks ?? {})} gh=${rec.gh?.calls}/${rec.gh?.total_ms}ms` +
      `${rec.timed_out ? " TIMED-OUT" : ""}${rec.error ? ` ERROR ${rec.error.slice(0, 300)}` : ""}`,
  );
}
process.exit(failed ? 1 : 0);
