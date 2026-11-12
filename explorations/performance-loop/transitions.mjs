#!/usr/bin/env node
// transition-navigation/v1: the stateful-navigation scenario for UI transitions.
//
//   node explorations/performance-loop/transitions.mjs run --exp exp-058 \
//     --corpus /path/to/frozen/checkout --condition control=/path/to/metab --runs 5
//   node explorations/performance-loop/transitions.mjs summarize .bench/transitions/exp-058/runs.jsonl
//   node explorations/performance-loop/transitions.mjs compare .bench/transitions/exp-058/runs.jsonl \
//     --control control --candidate candidate
//
// Each run starts a fresh server from the condition's `metab` on the corpus, runs every
// journey once unrecorded to warm the server, then runs them again measured, each
// journey in a fresh Chrome profile. One cache and configuration home per condition is
// kept across its runs, so GitHub data is read from cache. A run that cannot prove it
// measured the requested subjects is written with `valid: false` and its refusals, and
// summarize and compare leave it out. See README.md, "Transition Navigation Scenario".
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";
import { JOURNEYS, runJourney, SCENARIO, SUBJECTS } from "./transitions-journeys.mjs";
import { driver, launchBrowser, REGIONS, Refusal, sleep } from "./transitions-recorder.mjs";

const HERE = import.meta.dirname;
const REPO = path.resolve(HERE, "../..");
const BENCH = path.join(REPO, ".bench", "transitions");
const PORTS = [8890, 8899];
const MIN_RUNS = 3;

const REGIME = {
  server:
    "fresh server process per run on an unused port in 8890-8899; one unrecorded warm-up pass of every journey precedes the measured pass, so the server's own caches are warm and the browser's are not",
  browser:
    "fresh Chrome profile per journey (empty HTTP cache, new document), 1440x900 at device scale 1, trusted CDP input",
  github:
    "one cache and configuration directory per condition, kept across that condition's runs; GitHub records are served from cache and refreshed by the server on its own schedule",
};

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

function loadavg() {
  return os.loadavg().map((v) => Math.round(v * 100) / 100);
}

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
    process.exit(130);
  });
}
process.on("exit", killAll);

// --------------------------------------------------------------------------- provenance

/** Identity of one `metab` build: its version line and, for a checkout, commit and state. */
function buildProvenance(metab) {
  const version = execFileSync(metab, ["--version"], {
    encoding: "utf8",
    timeout: 60000,
    cwd: os.tmpdir(),
  }).trim();
  const venv = path.dirname(path.dirname(metab));
  let source = null;
  let editable = false;
  const libs = path.join(venv, "lib");
  if (fs.existsSync(libs)) {
    for (const py of fs.readdirSync(libs)) {
      const site = path.join(libs, py, "site-packages");
      if (!fs.existsSync(site)) {
        continue;
      }
      for (const entry of fs.readdirSync(site)) {
        if (!/^metabrowser-.*\.dist-info$/.test(entry)) {
          continue;
        }
        const direct = path.join(site, entry, "direct_url.json");
        if (fs.existsSync(direct)) {
          const info = JSON.parse(fs.readFileSync(direct, "utf8"));
          editable = Boolean(info.dir_info?.editable);
          if (editable && String(info.url).startsWith("file://")) {
            source = decodeURIComponent(new URL(info.url).pathname);
          }
        }
      }
    }
  }
  const commit = source ? git(source, "rev-parse", "HEAD") : null;
  const status = source ? git(source, "--no-optional-locks", "status", "--porcelain") : null;
  return {
    metab,
    version,
    editable,
    source,
    commit,
    dirty: status === null ? null : status.length > 0,
  };
}

function corpusProvenance(corpus) {
  const status = git(corpus, "--no-optional-locks", "status", "--porcelain");
  return {
    path: corpus,
    commit: git(corpus, "rev-parse", "HEAD"),
    dirty: status === null ? null : status.length > 0,
    // The Commits list walks HEAD and the trunk refs, which the shared checkout moves.
    trunk: git(corpus, "rev-parse", "--verify", "--quiet", "origin/main"),
  };
}

function harnessProvenance() {
  const status = git(REPO, "--no-optional-locks", "status", "--porcelain");
  return {
    commit: git(REPO, "rev-parse", "HEAD"),
    dirty: status === null ? null : status.length > 0,
  };
}

// --------------------------------------------------------------------------- server

function portFree(port) {
  return new Promise((resolve) => {
    const probe = net.createServer();
    probe.once("error", () => resolve(false));
    probe.once("listening", () => probe.close(() => resolve(true)));
    probe.listen(port, "127.0.0.1");
  });
}

let portCursor = 0;
async function pickPort() {
  const count = PORTS[1] - PORTS[0] + 1;
  for (let i = 0; i < count; i++) {
    const port = PORTS[0] + ((portCursor + i) % count);
    if (await portFree(port)) {
      portCursor = (portCursor + i + 1) % count;
      return port;
    }
  }
  throw new Error(`no free port in ${PORTS[0]}-${PORTS[1]}`);
}

async function getJson(url, timeoutMs = 30000) {
  const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) {
    throw new Error(`${url}: HTTP ${response.status}`);
  }
  return response.json();
}

const unescapeHtml = (s) =>
  s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&");

async function startServer({ metab, corpus, home, logPath }) {
  const cache = path.join(home, "cache");
  const config = path.join(home, "config");
  fs.mkdirSync(cache, { recursive: true, mode: 0o700 });
  fs.mkdirSync(config, { recursive: true, mode: 0o700 });
  fs.chmodSync(home, 0o700);
  const port = await pickPort();
  const fd = fs.openSync(logPath, "w", 0o600);
  const started = Date.now();
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
  let progress = null;
  for (let i = 0; i < 1800; i++) {
    if (child.exitCode !== null) {
      throw new Error(`server exited: ${fs.readFileSync(logPath, "utf8").slice(-1500)}`);
    }
    try {
      progress = await getJson(`${base}/api/index/progress`, 5000);
      if (progress.complete) {
        break;
      }
    } catch (_error) {
      // Not listening yet.
    }
    await sleep(100);
  }
  if (!progress?.complete) {
    throw new Error("server did not finish its inventory within 180 s");
  }
  const readyMs = Date.now() - started;
  const html = await (await fetch(`${base}/view/`)).text();
  const match = html.match(/<div class="menu-version">([^<]*)<\/div>/);
  const served = match ? unescapeHtml(match[1]).trim() : null;
  const log = fs.readFileSync(logPath, "utf8");
  const servingLine = log.split("\n").find((l) => l.startsWith("Serving ")) ?? null;
  return { child, port, base, readyMs, progress, served, servingLine };
}

async function stopServer(server) {
  if (!server?.child) {
    return;
  }
  const { child } = server;
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch (_error) {
    // Already gone.
  }
  for (let i = 0; i < 100 && child.exitCode === null && child.signalCode === null; i++) {
    await sleep(100);
  }
  if (child.exitCode === null && child.signalCode === null) {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch (_error) {
      // Already gone.
    }
  }
  for (let i = 0; i < 50 && !(await portFree(server.port)); i++) {
    await sleep(100);
  }
}

/** Facts about the moving parts of the corpus, read from the server before measuring. */
async function serverFacts(base) {
  const facts = {};
  try {
    const log = await getJson(`${base}/api/git/log?limit=1`);
    facts.git_log_head = log.commits?.[0]?.id ?? null;
  } catch (error) {
    facts.git_log_head = `error: ${error.message}`;
  }
  try {
    const closed = await getJson(`${base}/api/plugin/github/pulls?state=closed&limit=1`);
    facts.github = {
      state: closed.state,
      fetched_at: closed.fetched_at,
      filter_totals: closed.filter_totals,
      last_refresh: closed.last_refresh?.outcome ?? null,
    };
  } catch (error) {
    facts.github = `error: ${error.message}`;
  }
  return facts;
}

// --------------------------------------------------------------------------- one run

function logTransition(row) {
  const fmt = (v) => (v === null || v === undefined ? "  n/a" : String(Math.round(v)).padStart(5));
  const flag = row.ok ? "  " : "!!";
  const req = row.requests.byClass;
  console.log(
    `  ${flag} ${row.id.padEnd(40)} ready ${fmt(row.paintedReadyMs)} blank ${String(row.blankFrames).padStart(2)} ph ${row.placeholderVisibleFrames} data ${req.data ?? 0} plug ${req.plugin ?? 0} kp ${req.kpress ?? 0} dup ${row.requests.subjectDuplicates} top ${row.previewTop.removed} moved ${row.movementPx} shift ${row.shifts.count}${row.ok ? "" : `  ${row.refusals.map((r) => r.join(": ")).join(" | ")}`}`,
  );
}

async function pass({ base, journeys, headed, profileRoot, expectedVersion, quiet }) {
  const out = [];
  for (const name of journeys) {
    const rows = [];
    const journey = { name, ok: true, error: null, refusals: [], transitions: rows };
    const profileDir = path.join(profileRoot, `${process.pid}-${name}-${Date.now()}`);
    let browser = null;
    try {
      browser = await launchBrowser({ profileDir, headed });
      track(browser.chrome);
      journey.chrome = browser.version.product;
      const d = driver(browser);
      await runJourney(name, d, base, rows, { log: quiet ? null : logTransition });
      const served = await d.evaluate(
        `(document.querySelector(".menu-version") || {}).textContent || null`,
      );
      if (served?.trim() !== expectedVersion) {
        journey.refusals.push(["build_identity", `page reports ${served}`]);
      }
      journey.alertsAtEnd = await d.evaluate(
        `Array.from(document.querySelectorAll('#preview-pane [role="alert"], #tree-content [role="alert"]')).filter((e) => e.getBoundingClientRect().height > 0).map((e) => e.textContent.trim().slice(0, 160))`,
      );
      if (journey.alertsAtEnd.length) {
        journey.refusals.push(["rendered_errors", journey.alertsAtEnd[0]]);
      }
    } catch (error) {
      journey.error = error instanceof Refusal ? error.message : String(error.stack || error);
      journey.refusals.push([
        error instanceof Refusal ? error.guard : "journey_error",
        error instanceof Refusal ? error.detail : String(error.message || error),
      ]);
    } finally {
      if (browser) {
        journey.exceptions = browser.exceptions.slice(0, 10);
        journey.exceptionCount = browser.exceptions.length;
        journey.consoleErrorCount = browser.consoleErrors.length;
        journey.consoleErrors = browser.consoleErrors.slice(0, 5);
        if (browser.exceptions.length) {
          journey.refusals.push(["page_exceptions", browser.exceptions[0].text]);
        }
        await browser.close();
      }
    }
    for (const row of rows) {
      for (const [guard, detail] of row.refusals) {
        journey.refusals.push([guard, `${row.id}: ${detail}`]);
      }
    }
    journey.ok = journey.refusals.length === 0;
    if (!quiet) {
      console.log(
        `  journey ${name}: ${rows.length} transitions${journey.ok ? "" : `, REFUSED: ${journey.refusals.map((r) => r.join(": ")).join(" | ")}`}`,
      );
    }
    out.push(journey);
  }
  return out;
}

async function oneRun(options) {
  const { exp, series, condition, runIndex, pairIndex, corpus, journeys, headed, warmup } = options;
  const expDir = path.join(BENCH, exp);
  const home = path.join(expDir, "state", condition.label);
  fs.mkdirSync(home, { recursive: true, mode: 0o700 });
  const logDir = path.join(expDir, "logs");
  fs.mkdirSync(logDir, { recursive: true });
  const profileRoot = path.join(expDir, "profiles");
  fs.mkdirSync(profileRoot, { recursive: true });
  const row = {
    schema: SCENARIO,
    exp,
    series,
    condition: condition.label,
    run: runIndex,
    pair: pairIndex,
    started_at: new Date().toISOString(),
    load_start: loadavg(),
    build: buildProvenance(condition.metab),
    harness: harnessProvenance(),
    corpus: corpusProvenance(corpus),
    host: {
      platform: `${os.type()} ${os.release()} ${os.arch()}`,
      cpus: os.cpus().length,
      node: process.version,
    },
    viewport: "1440x900",
    headed,
    regime: REGIME,
    regions: Object.fromEntries(Object.entries(REGIONS).map(([k, v]) => [k, v.track])),
    journeys_requested: journeys,
    refusals: [],
  };
  console.log(
    `\n== ${exp} ${condition.label} run ${runIndex} (pair ${pairIndex}) load ${row.load_start.join(" ")}`,
  );
  let server = null;
  try {
    const logPath = path.join(logDir, `${series}-${condition.label}-run${runIndex}.log`);
    server = await startServer({ metab: condition.metab, corpus, home, logPath });
    row.server = {
      port: server.port,
      ready_ms: server.readyMs,
      served_version: server.served,
      serving_line: server.servingLine,
      indexed_files: server.progress.indexed_files,
      log: path.relative(REPO, logPath),
    };
    if (server.served !== row.build.version) {
      row.refusals.push([
        "build_identity",
        `server reports ${server.served}, ${condition.metab} --version says ${row.build.version}`,
      ]);
    }
    if (!server.servingLine?.includes(`${corpus} at http://127.0.0.1:${server.port}/`)) {
      row.refusals.push(["build_identity", `unexpected serving line ${server.servingLine}`]);
    }
    row.facts = await serverFacts(server.base);
    if (warmup) {
      console.log("  warm-up pass (unrecorded)");
      const warm = await pass({
        base: server.base,
        journeys,
        headed,
        profileRoot,
        expectedVersion: row.build.version,
        quiet: true,
      });
      row.warmup = warm.map((j) => ({
        name: j.name,
        ok: j.ok,
        transitions: j.transitions.length,
        refusals: j.refusals.slice(0, 6),
      }));
    }
    console.log("  measured pass");
    row.journeys = await pass({
      base: server.base,
      journeys,
      headed,
      profileRoot,
      expectedVersion: row.build.version,
      quiet: false,
    });
    row.chrome = row.journeys.find((j) => j.chrome)?.chrome ?? null;
    for (const j of row.journeys) {
      for (const [guard, detail] of j.refusals) {
        row.refusals.push([guard, `${j.name}: ${detail}`]);
      }
    }
  } catch (error) {
    row.refusals.push(["run_error", String(error.stack || error).slice(0, 2000)]);
  } finally {
    await stopServer(server);
  }
  row.load_end = loadavg();
  row.finished_at = new Date().toISOString();
  row.valid = row.refusals.length === 0;
  console.log(
    `== ${condition.label} run ${runIndex}: ${row.valid ? "valid" : `REFUSED (${row.refusals.length})`} load ${row.load_end.join(" ")}`,
  );
  return row;
}

async function cmdRun(argv) {
  const { values } = parseArgs({
    args: argv,
    options: {
      exp: { type: "string" },
      corpus: { type: "string" },
      condition: { type: "string", multiple: true },
      runs: { type: "string", default: "5" },
      journeys: { type: "string" },
      out: { type: "string" },
      headed: { type: "boolean", default: false },
      "no-warmup": { type: "boolean", default: false },
      order: { type: "string", default: "alternate" },
    },
  });
  if (!values.exp || !/^exp-[0-9]{3}$/.test(values.exp)) {
    throw new Error("--exp exp-NNN is required");
  }
  if (!values.corpus) {
    throw new Error("--corpus PATH is required: a frozen checkout to serve");
  }
  const corpus = path.resolve(values.corpus);
  const conditions = (values.condition ?? []).map((spec) => {
    const at = spec.indexOf("=");
    if (at <= 0) {
      throw new Error(`--condition LABEL=PATH/TO/metab, got ${spec}`);
    }
    const label = spec.slice(0, at);
    const metab = path.resolve(spec.slice(at + 1));
    if (!/^[\w.-]+$/.test(label)) {
      throw new Error(`condition label ${label} must be a plain word`);
    }
    if (!fs.existsSync(metab)) {
      throw new Error(`${metab} does not exist`);
    }
    return { label, metab };
  });
  if (conditions.length < 1 || conditions.length > 2) {
    throw new Error("give one or two --condition LABEL=PATH");
  }
  if (!["alternate", "fixed"].includes(values.order)) {
    throw new Error("--order is alternate or fixed");
  }
  const runs = Number.parseInt(values.runs, 10);
  if (!(runs >= 1)) {
    throw new Error("--runs must be a positive integer");
  }
  const journeys = values.journeys ? values.journeys.split(",") : Object.keys(JOURNEYS);
  for (const j of journeys) {
    if (!JOURNEYS[j]) {
      throw new Error(`unknown journey ${j}; known: ${Object.keys(JOURNEYS).join(",")}`);
    }
  }
  const outFile = values.out
    ? path.resolve(values.out)
    : path.join(BENCH, values.exp, "runs.jsonl");
  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  const series = new Date().toISOString().replace(/[:.]/g, "-");
  console.log(
    `${SCENARIO} ${values.exp} series ${series}: ${runs} run(s) x ${conditions.map((c) => c.label).join(", ")}, journeys ${journeys.join(",")}, ${values.headed ? "headed" : "headless"}, writing ${path.relative(REPO, outFile)}`,
  );
  let refused = 0;
  // Run numbers continue across series written to the same file, one sequence per label.
  const runCount = {};
  if (fs.existsSync(outFile)) {
    for (const row of readRows(outFile)) {
      runCount[row.condition] = Math.max(runCount[row.condition] ?? 0, row.run ?? 0);
    }
  }
  for (let pair = 0; pair < runs; pair++) {
    const order =
      conditions.length === 2 && values.order === "alternate" && pair % 2 === 1
        ? [conditions[1], conditions[0]]
        : conditions;
    for (const condition of order) {
      runCount[condition.label] = (runCount[condition.label] ?? 0) + 1;
      const row = await oneRun({
        exp: values.exp,
        series,
        condition,
        runIndex: runCount[condition.label],
        pairIndex: pair + 1,
        corpus,
        journeys,
        headed: values.headed,
        warmup: !values["no-warmup"],
      });
      fs.appendFileSync(outFile, `${JSON.stringify(row)}\n`);
      if (!row.valid) {
        refused += 1;
      }
    }
  }
  console.log(`\nwrote ${path.relative(REPO, outFile)}; ${refused} run(s) refused`);
  return refused === 0 ? 0 : 1;
}

// --------------------------------------------------------------------------- statistics

const METRICS = [
  { key: "painted_ready_ms", kind: "time", get: (t) => t.paintedReadyMs },
  { key: "blank_frames", kind: "count", get: (t) => t.blankFrames },
  { key: "placeholder_visible_frames", kind: "count", get: (t) => t.placeholderVisibleFrames },
  {
    key: "nav_placeholder_visible_frames",
    kind: "count",
    get: (t) => t.navPlaceholderVisibleFrames,
  },
  { key: "requests_data", kind: "count", get: (t) => t.requests.byClass.data ?? 0 },
  { key: "requests_plugin", kind: "count", get: (t) => t.requests.byClass.plugin ?? 0 },
  { key: "requests_static", kind: "count", get: (t) => t.requests.byClass.static ?? 0 },
  { key: "requests_kpress", kind: "count", get: (t) => t.requests.byClass.kpress ?? 0 },
  { key: "requests_background", kind: "count", get: (t) => t.requests.byClass.background ?? 0 },
  { key: "subject_duplicates", kind: "count", get: (t) => t.requests.subjectDuplicates },
  { key: "preview_top_replaced", kind: "count", get: (t) => t.previewTop.removed },
  { key: "shift_count", kind: "count", get: (t) => t.shifts.count },
  { key: "shift_sum_no_input", kind: "value", get: (t) => t.shifts.sumNoInput },
  { key: "region_movement_px", kind: "count", get: (t) => t.movementPx },
  { key: "long_task_max_ms", kind: "time", get: (t) => t.longTasks.maxMs },
  { key: "dom_nodes_end", kind: "count", get: (t) => t.dom.end },
];

function median(xs) {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function readRows(file) {
  const rows = [];
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    if (line.trim()) {
      const row = JSON.parse(line);
      if (row.schema !== SCENARIO) {
        throw new Error(`${file} holds a ${row.schema} row; this reads ${SCENARIO}`);
      }
      rows.push(row);
    }
  }
  return rows;
}

/** Valid runs per condition, refusing to pool runs of different builds under one label. */
function groupConditions(rows, { allowMixed = false } = {}) {
  const out = new Map();
  for (const row of rows) {
    if (!out.has(row.condition)) {
      out.set(row.condition, { label: row.condition, valid: [], refused: [] });
    }
    const c = out.get(row.condition);
    (row.valid ? c.valid : c.refused).push(row);
  }
  for (const c of out.values()) {
    const identities = new Set(
      c.valid.map((r) => `${r.build.version} ${r.build.commit} ${r.build.dirty}`),
    );
    if (identities.size > 1 && !allowMixed) {
      throw new Error(
        `condition ${c.label} pools ${identities.size} builds: ${[...identities].join(" / ")}`,
      );
    }
  }
  return out;
}

/** transition id -> metric key -> values across the condition's valid runs. */
function collect(condition) {
  const byId = new Map();
  for (const run of condition.valid) {
    for (const journey of run.journeys ?? []) {
      for (const t of journey.transitions) {
        if (!byId.has(t.id)) {
          byId.set(t.id, { id: t.id, subjects: new Set(), values: {} });
        }
        const entry = byId.get(t.id);
        entry.subjects.add(t.subject);
        for (const m of METRICS) {
          const v = m.get(t);
          if (v !== null && v !== undefined) {
            entry.values[m.key] ??= [];
            entry.values[m.key].push(v);
          }
        }
      }
    }
  }
  return byId;
}

function stat(xs) {
  if (!xs?.length) {
    return null;
  }
  return { n: xs.length, median: median(xs), min: Math.min(...xs), max: Math.max(...xs) };
}

// Times are frame-clock readings quantized to about 16.7 ms, so whole milliseconds.
function fmtNum(v, kind) {
  if (kind === "value") {
    return v.toFixed(4);
  }
  if (kind === "time") {
    return String(Math.round(v));
  }
  return Math.abs(v - Math.round(v)) < 1e-9 ? String(Math.round(v)) : v.toFixed(1);
}

const firstLine = (s) => String(s).split("\n")[0].slice(0, 200);
const print = (lines) => process.stdout.write(`${lines.join("\n")}\n`);

function fmtStat(s, kind) {
  if (!s) {
    return "n/a";
  }
  if (kind === "time") {
    return `${fmtNum(s.median, kind)} (${fmtNum(s.min, kind)}–${fmtNum(s.max, kind)})`;
  }
  return s.min === s.max ? fmtNum(s.min, kind) : `${fmtNum(s.min, kind)}–${fmtNum(s.max, kind)}`;
}

const metric = (key) => METRICS.find((m) => m.key === key);

function loadRange(runs) {
  const all = runs.flatMap((r) => [r.load_start?.[0], r.load_end?.[0]]).filter((v) => v != null);
  return all.length ? `${Math.min(...all)}–${Math.max(...all)}` : "n/a";
}

const TABLES = [
  {
    title: "Time and frames",
    columns: [
      ["painted_ready_ms", "Painted ready ms, median (range)"],
      ["blank_frames", "Blank frames"],
      ["placeholder_visible_frames", "Visible placeholder frames"],
      ["nav_placeholder_visible_frames", "Nav placeholder frames"],
      ["long_task_max_ms", "Longest task ms, median (range)"],
    ],
  },
  {
    title: "Requests",
    columns: [
      ["requests_data", "Data"],
      ["requests_plugin", "Plugin modules"],
      ["requests_static", "Static"],
      ["requests_kpress", "KPress"],
      ["requests_background", "Background"],
      ["subject_duplicates", "Subject duplicates"],
    ],
  },
  {
    title: "Stability and DOM",
    columns: [
      ["preview_top_replaced", "Preview top nodes replaced"],
      ["shift_count", "Layout shifts"],
      ["shift_sum_no_input", "Shift without input"],
      ["region_movement_px", "Region movement px"],
      ["dom_nodes_end", "DOM nodes after"],
    ],
  },
];

function summaryTables(condition) {
  const byId = collect(condition);
  const lines = [];
  for (const table of TABLES) {
    lines.push(`#### ${table.title}`, "");
    lines.push(`| Transition | ${table.columns.map((c) => c[1]).join(" | ")} |`);
    lines.push(`| --- | ${table.columns.map(() => "---:").join(" | ")} |`);
    for (const entry of byId.values()) {
      const cells = table.columns.map(([key]) =>
        fmtStat(stat(entry.values[key]), metric(key).kind),
      );
      lines.push(`| \`${entry.id}\` | ${cells.join(" | ")} |`);
    }
    lines.push("");
  }
  return lines;
}

function cmdSummarize(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      condition: { type: "string" },
      format: { type: "string", default: "markdown" },
      "allow-mixed": { type: "boolean", default: false },
    },
  });
  if (positionals.length !== 1) {
    throw new Error("summarize RUNS.jsonl");
  }
  const conditions = groupConditions(readRows(positionals[0]), {
    allowMixed: values["allow-mixed"],
  });
  const selected = [...conditions.values()].filter(
    (c) => !values.condition || c.label === values.condition,
  );
  if (values.format === "json") {
    const out = {};
    for (const c of selected) {
      out[c.label] = Object.fromEntries(
        [...collect(c).values()].map((e) => [
          e.id,
          {
            subjects: [...e.subjects],
            ...Object.fromEntries(Object.entries(e.values).map(([k, v]) => [k, stat(v)])),
          },
        ]),
      );
    }
    console.log(JSON.stringify(out, null, 1));
    return 0;
  }
  const out = [];
  for (const c of selected) {
    const builds = [...new Set(c.valid.map((r) => r.build.version))];
    out.push(`### Condition \`${c.label}\``, "");
    out.push(
      `${c.valid.length} valid run(s), ${c.refused.length} refused; build ${builds.join(", ") || "n/a"}; load average (1 min) ${loadRange(c.valid)} at run start and end.`,
      "",
    );
    for (const r of c.refused) {
      out.push(
        `- refused run ${r.run} (${r.series}): ${r.refusals
          .slice(0, 3)
          .map((x) => firstLine(x.join(": ")))
          .join(" | ")}`,
      );
    }
    const drift = [...collect(c).values()].filter((e) => e.subjects.size > 1);
    for (const e of drift) {
      out.push(`- subject drift in \`${e.id}\`: ${[...e.subjects].join(", ")}`);
    }
    if (c.refused.length || drift.length) {
      out.push("");
    }
    out.push(...summaryTables(c));
  }
  print(out);
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
      format: { type: "string", default: "markdown" },
      aa: { type: "string" },
    },
  });
  if (positionals.length !== 1) {
    throw new Error("compare RUNS.jsonl --control LABEL --candidate LABEL | --aa LABEL");
  }
  const tolerance = Number.parseFloat(values.tolerance);
  if (!(tolerance > 1 && tolerance < 2)) {
    throw new Error("--tolerance must be above 1 and below 2 (1.3 rough cut; never 2x)");
  }
  let rows = readRows(positionals[0]);
  if (values.aa) {
    // An A/A comparison: one condition's runs in recorded order, odd against even, which
    // measures the instrument's own resolution on that build.
    rows = rows
      .filter((r) => r.condition === values.aa && r.valid)
      .map((r, i) => ({ ...r, condition: `${values.aa}.${i % 2 === 0 ? "odd" : "even"}` }));
    values.control = `${values.aa}.odd`;
    values.candidate = `${values.aa}.even`;
  }
  const conditions = groupConditions(rows);
  const labels = [...conditions.keys()];
  const A = conditions.get(values.control ?? labels[0]);
  const B = conditions.get(values.candidate ?? labels[1]);
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
  const corpora = new Set(all.map((r) => r.corpus.commit));
  if (corpora.size !== 1) {
    throw new Error(`the conditions were measured on different corpora: ${[...corpora]}`);
  }
  const notes = [];
  const harnesses = new Set(all.map((r) => r.harness.commit));
  if (harnesses.size > 1) {
    notes.push(`runs used ${harnesses.size} harness commits: ${[...harnesses].join(", ")}`);
  }
  const chromes = new Set(all.flatMap((r) => (r.journeys ?? []).map((j) => j.chrome)));
  if (chromes.size > 1) {
    notes.push(`runs used ${chromes.size} Chrome versions: ${[...chromes].join(", ")}`);
  }
  const idA = `${A.valid[0].build.version} ${A.valid[0].build.commit} ${A.valid[0].build.dirty}`;
  const idB = `${B.valid[0].build.version} ${B.valid[0].build.commit} ${B.valid[0].build.dirty}`;
  if (idA === idB) {
    notes.push(
      values.aa
        ? `A/A comparison of ${values.aa}: odd-numbered valid runs against even-numbered ones`
        : "both conditions report the same build identity: this is an A/A comparison",
    );
  }
  const ca = collect(A);
  const cb = collect(B);
  const findings = [];
  const rowsOut = [];
  const every = [];
  for (const [id, ea] of ca) {
    const eb = cb.get(id);
    if (!eb) {
      continue;
    }
    for (const m of METRICS) {
      const sa = stat(ea.values[m.key]);
      const sb = stat(eb.values[m.key]);
      if (!sa || !sb) {
        continue;
      }
      const overlap = !(sb.min > sa.max || sb.max < sa.min);
      const ratio = sa.median > 0 ? sb.median / sa.median : null;
      let verdict = "no detected difference";
      if (!overlap) {
        const direction = sb.median > sa.median ? "higher" : "lower";
        if (m.kind === "time") {
          const beyond = ratio !== null && (ratio >= tolerance || ratio <= 1 / tolerance);
          verdict = beyond
            ? `${direction}, beyond the ${tolerance}x tolerance`
            : `${direction}, ranges apart but within the ${tolerance}x tolerance (not a result)`;
        } else {
          verdict = `${direction}, ranges apart`;
        }
        findings.push({ id, metric: m.key, kind: m.kind, sa, sb, ratio, verdict });
      }
      every.push({ id, metric: m.key, control: sa, candidate: sb, ratio, overlap, verdict });
      if (m.key === "painted_ready_ms") {
        rowsOut.push({ id, sa, sb, ratio, overlap, verdict });
      }
    }
  }
  if (values.format === "json") {
    console.log(
      JSON.stringify(
        { control: A.label, candidate: B.label, tolerance, notes, findings, all: every },
        null,
        1,
      ),
    );
    return 0;
  }
  const out = [
    `### \`${B.label}\` against \`${A.label}\``,
    "",
    `${A.valid.length} and ${B.valid.length} valid runs (${A.refused.length} and ${B.refused.length} refused). Load average (1 min) ${loadRange(A.valid)} and ${loadRange(B.valid)}. Tolerance ${tolerance}x for times; counts are judged on their ranges.`,
    "",
  ];
  for (const n of notes) {
    out.push(`- ${n}`);
  }
  if (notes.length) {
    out.push("");
  }
  out.push(
    `| Transition | ${A.label} painted ready ms | ${B.label} painted ready ms | Ratio | Verdict |`,
    "| --- | ---: | ---: | ---: | --- |",
  );
  for (const r of rowsOut) {
    out.push(
      `| \`${r.id}\` | ${fmtStat(r.sa, "time")} | ${fmtStat(r.sb, "time")} | ${r.ratio === null ? "n/a" : `${r.ratio.toFixed(2)}x`} | ${r.verdict} |`,
    );
  }
  out.push("");
  if (!findings.length) {
    out.push("No metric has non-overlapping ranges between the two conditions.");
  } else {
    out.push(`Metrics with non-overlapping ranges (${findings.length}):`, "");
    for (const f of findings) {
      out.push(
        `- \`${f.id}\` ${f.metric}: ${fmtStat(f.sa, f.kind)} → ${fmtStat(f.sb, f.kind)}${f.ratio !== null && f.kind === "time" ? ` (${f.ratio.toFixed(2)}x)` : ""}; ${f.verdict}`,
      );
    }
  }
  print(out);
  return 0;
}

/** Keep only what summarize and compare read, so a round can commit its samples. */
function cmdSamples(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: { out: { type: "string" } },
  });
  if (positionals.length !== 1 || !values.out) {
    throw new Error("samples RUNS.jsonl --out FILE");
  }
  const keep = (t) => ({
    id: t.id,
    subject: t.subject,
    ok: t.ok,
    paintedReadyMs: t.paintedReadyMs,
    blankFrames: t.blankFrames,
    placeholderVisibleFrames: t.placeholderVisibleFrames,
    navPlaceholderVisibleFrames: t.navPlaceholderVisibleFrames,
    movementPx: t.movementPx,
    requests: { byClass: t.requests.byClass, subjectDuplicates: t.requests.subjectDuplicates },
    previewTop: { removed: t.previewTop.removed },
    shifts: { count: t.shifts.count, sumNoInput: t.shifts.sumNoInput },
    longTasks: { maxMs: t.longTasks.maxMs },
    dom: { end: t.dom.end },
  });
  const lines = readRows(positionals[0]).map((r) => {
    const { journeys, warmup: _warmup, regime: _regime, regions: _regions, ...rest } = r;
    const scrub = (p) => (typeof p === "string" ? path.basename(p) : p);
    return JSON.stringify({
      ...rest,
      build: { ...rest.build, metab: scrub(rest.build.metab), source: scrub(rest.build.source) },
      corpus: { ...rest.corpus, path: scrub(rest.corpus.path) },
      server: rest.server
        ? { ...rest.server, serving_line: undefined, log: undefined }
        : rest.server,
      journeys: (journeys ?? []).map((j) => ({
        name: j.name,
        ok: j.ok,
        chrome: j.chrome,
        refusals: j.refusals,
        transitions: j.transitions.map(keep),
      })),
    });
  });
  fs.writeFileSync(values.out, `${lines.join("\n")}\n`);
  console.log(`wrote ${lines.length} row(s) to ${values.out}`);
  return 0;
}

// --------------------------------------------------------------------------- main

const USAGE = `usage:
  transitions.mjs run --exp exp-NNN --corpus PATH --condition LABEL=PATH/TO/metab
                      [--condition LABEL=PATH/TO/metab] [--runs 5] [--journeys a,b]
                      [--headed] [--no-warmup] [--order alternate|fixed] [--out FILE]
  transitions.mjs summarize RUNS.jsonl [--condition LABEL] [--format markdown|json]
  transitions.mjs compare RUNS.jsonl --control LABEL --candidate LABEL [--tolerance 1.3]
  transitions.mjs compare RUNS.jsonl --aa LABEL      (odd against even runs of one build)
  transitions.mjs samples RUNS.jsonl --out FILE      (the fields summarize and compare read)
journeys: ${Object.keys(JOURNEYS).join(", ")}
subjects: ${JSON.stringify(SUBJECTS).slice(0, 120)}...`;

const [mode, ...rest] = process.argv.slice(2);
const commands = { run: cmdRun, summarize: cmdSummarize, compare: cmdCompare, samples: cmdSamples };
if (!commands[mode]) {
  console.error(USAGE);
  process.exit(2);
}
try {
  process.exitCode = await commands[mode](rest);
} catch (error) {
  console.error(`transitions.mjs ${mode}: ${error.message}`);
  process.exitCode = 2;
}
