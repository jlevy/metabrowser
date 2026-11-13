#!/usr/bin/env node
import { spawn } from "node:child_process";
// transition-navigation/v1: the stateful-navigation scenario for UI transitions.
//
//   node explorations/performance-loop/transitions.mjs run --exp exp-058 \
//     --corpus /path/to/standalone/clone --condition control=/path/to/metab --runs 6
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
import fs from "node:fs";
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
import { JOURNEYS, runJourney, SUBJECTS } from "./transitions-journeys.mjs";
import { driver, launchBrowser, REGIONS, Refusal, sleep } from "./transitions-recorder.mjs";
import {
  CompareRefusal,
  compareRuns,
  formatComparison,
  parseRows,
  SCENARIO,
  SCENARIO_REVISION,
  sampleRow,
  summarize,
  summarizeJson,
} from "./transitions-stats.mjs";

const HERE = import.meta.dirname;
const REPO = path.resolve(HERE, "../..");
// TRANSITIONS_BENCH moves the state, log, and profile directories, for the tests.
const BENCH = process.env.TRANSITIONS_BENCH
  ? path.resolve(process.env.TRANSITIONS_BENCH)
  : path.join(REPO, ".bench", "transitions");
const PORTS = [8890, 8899];

const REGIME = {
  server:
    "fresh server process per run on an unused port in 8890-8899; one unrecorded warm-up pass of every journey precedes the measured pass, so the server's own caches are warm and the browser's are not",
  browser:
    "fresh Chrome profile per journey (empty HTTP cache, new document), 1440x900 at device scale 1, trusted CDP input",
  github:
    "one cache and configuration directory per condition, kept across that condition's runs; GitHub records are served from cache and refreshed by the server on its own schedule",
};

// --------------------------------------------------------------------------- utilities

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
for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => {
    killAll();
    process.exit(130);
  });
}
process.on("exit", killAll);

const sameJson = (a, b) => JSON.stringify(a) === JSON.stringify(b);

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

const unescapeHtml = (s) =>
  s
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#x27;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&");

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

const INVENTORY_DEADLINE_MS = 180000;

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
      if (child.exitCode !== null || child.signalCode !== null) {
        throw new Error(`server exited: ${fs.readFileSync(logPath, "utf8").slice(-1500)}`);
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
    const readyMs = Date.now() - started;
    const html = await (
      await fetch(`${server.base}/view/`, { signal: AbortSignal.timeout(30000) })
    ).text();
    const match = html.match(/<div class="menu-version">([^<]*)<\/div>/);
    const served = match ? unescapeHtml(match[1]).trim() : null;
    const log = fs.readFileSync(logPath, "utf8");
    const servingLine = log.split("\n").find((l) => l.startsWith("Serving ")) ?? null;
    return { ...server, readyMs, progress, served, servingLine };
  } catch (error) {
    // The server is ours from the spawn on: a failed start stops it here, so it cannot
    // keep the port or its state directory into the condition's next run.
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
  for (let i = 0; i < 100 && child.exitCode === null && child.signalCode === null; i++) {
    await sleep(100);
  }
  if (child.exitCode === null && child.signalCode === null) {
    killGroup(child, "SIGKILL");
  }
  for (let i = 0; i < 50 && !(await portFree(server.port)); i++) {
    await sleep(100);
  }
}

// --------------------------------------------------------------------------- one run

function logTransition(row) {
  const fmt = (v) => (v === null || v === undefined ? "  n/a" : String(Math.round(v)).padStart(5));
  const flag = row.ok ? "  " : "!!";
  const req = row.requests.byClass;
  const extra = [
    ...Object.entries(row.milestones ?? {}).map(([k, v]) => ` ${k} ${fmt(v).trim()}`),
    row.list ? ` listBelowSel ${row.list.rowsReplacedBelowSelection}` : "",
    row.movementByGroup?.tree?.path ? ` tree ${row.movementByGroup.tree.path}` : "",
    row.movementByGroup?.palette?.path ? ` palette ${row.movementByGroup.palette.path}` : "",
    row.requests.postBytes ? ` post ${row.requests.postBytes}B` : "",
    row.inputSpanMs ? ` afterLast ${fmt(row.readyAfterLastInputMs).trim()}` : "",
  ].join("");
  console.log(
    `  ${flag} ${row.id.padEnd(40)} ready ${fmt(row.paintedReadyMs)} settled ${fmt(row.settledMs)} blank ${String(row.blankFrames).padStart(2)} ph ${row.placeholderVisibleFrames} data ${req.data ?? 0} plug ${req.plugin ?? 0} kp ${req.kpress ?? 0} dup ${row.requests.subjectDuplicates} top ${row.previewTop.removed} moved ${row.movementPathPx} shift ${row.shifts.count}${extra}${row.ok ? "" : `  ${row.refusals.map((r) => r.join(": ")).join(" | ")}`}`,
  );
}

async function pass({ base, journeys, headed, profileRoot, expectedVersion, quiet, keepGoing }) {
  const out = [];
  for (const name of journeys) {
    const rows = [];
    const facts = {};
    const journey = { name, ok: true, error: null, refusals: [], transitions: rows, facts };
    const profileDir = path.join(profileRoot, `${process.pid}-${name}-${Date.now()}`);
    let browser = null;
    try {
      browser = await launchBrowser({ profileDir, headed, onSpawn: track });
      journey.chrome = browser.version.product;
      const d = driver(browser);
      await runJourney(name, d, base, rows, {
        log: quiet ? null : logTransition,
        keepGoing,
        facts,
        loadavg: () => loadavg()[0],
      });
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
    if (!quiet || !journey.ok) {
      console.log(
        `  journey ${name}: ${rows.length} transitions${journey.ok ? "" : `, REFUSED: ${journey.refusals.map((r) => r.join(": ")).join(" | ")}`}`,
      );
    }
    out.push(journey);
    // The run is invalid from its first refusal on, so the pass stops there.
    if (!journey.ok && !keepGoing) {
      break;
    }
  }
  return out;
}

async function oneRun(options) {
  const { exp, series, condition, runIndex, pairIndex, corpus, journeys, headed, warmup } = options;
  const { keepGoing, subset } = options;
  const expDir = path.join(BENCH, exp);
  const home = path.join(expDir, "state", condition.label);
  fs.mkdirSync(home, { recursive: true, mode: 0o700 });
  const logDir = path.join(expDir, "logs");
  fs.mkdirSync(logDir, { recursive: true });
  const profileRoot = path.join(expDir, "profiles");
  fs.mkdirSync(profileRoot, { recursive: true });
  const row = {
    schema: SCENARIO,
    // 3 redefined the clocks and the frame accounting (every frame read after its own
    // layout, painted ready at the ready frame's presentation, counts over the whole
    // window). 4 reads a worker's 304 as revalidated, takes a region's first rendered
    // match, and skips hidden and off-screen subtrees when looking for content.
    // REVISION_NOTES in transitions-stats.mjs says what each older revision differs in.
    scenario_revision: SCENARIO_REVISION,
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
    regime_flags: { headed, no_warmup: !warmup, journey_subset: subset, keep_going: keepGoing },
    regime: REGIME,
    regions: Object.fromEntries(Object.entries(REGIONS).map(([k, v]) => [k, v.track])),
    journeys_requested: journeys,
    refusals: [],
  };
  if (row.build.dirty === true && !row.build.content) {
    row.refusals.push(["build_identity", "a dirty build whose content could not be identified"]);
  }
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
        `server reports ${server.served}, ${path.basename(condition.metab)} --version says ${row.build.version}`,
      ]);
    }
    if (!server.servingLine?.includes(`${corpus} at http://127.0.0.1:${server.port}/`)) {
      row.refusals.push(["build_identity", "the server's serving line names another tree or port"]);
    }
    row.facts = await serverFacts(server.base);
    if (warmup && (keepGoing || row.refusals.length === 0)) {
      console.log("  warm-up pass (unrecorded)");
      const warm = await pass({
        base: server.base,
        journeys,
        headed,
        profileRoot,
        expectedVersion: row.build.version,
        quiet: true,
        keepGoing,
      });
      row.warmup = warm.map((j) => ({
        name: j.name,
        ok: j.ok,
        transitions: j.transitions.length,
        refusals: j.refusals.slice(0, 6),
      }));
      // A warm-up that refused leaves the server in an unknown state: the run is refused.
      for (const j of warm) {
        for (const [guard, detail] of j.refusals.slice(0, 3)) {
          row.refusals.push([`warmup_${guard}`, `${j.name}: ${detail}`]);
        }
      }
    }
    if (keepGoing || row.refusals.length === 0) {
      console.log("  measured pass");
      row.journeys = await pass({
        base: server.base,
        journeys,
        headed,
        profileRoot,
        expectedVersion: row.build.version,
        quiet: false,
        keepGoing,
      });
      row.chrome = row.journeys.find((j) => j.chrome)?.chrome ?? null;
      for (const j of row.journeys) {
        for (const [guard, detail] of j.refusals) {
          row.refusals.push([guard, `${j.name}: ${detail}`]);
        }
      }
    }
  } catch (error) {
    row.refusals.push(["run_error", String(error.stack || error).slice(0, 2000)]);
  } finally {
    await stopServer(server);
  }
  // Provenance again at the end: an editable build serves its files live and a corpus
  // can be moved under the server, and either would make this run a mixture.
  row.build_end = buildProvenance(condition.metab);
  row.corpus_end = corpusProvenance(corpus);
  row.refusals.push(
    ...provenanceChanges(
      { build: row.build, corpus: row.corpus },
      { build: row.build_end, corpus: row.corpus_end },
    ),
  );
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
      "keep-going": { type: "boolean", default: false },
      order: { type: "string", default: "alternate" },
    },
  });
  if (!values.exp || !/^exp-[0-9]{3}$/.test(values.exp)) {
    throw new Error("--exp exp-NNN is required");
  }
  if (!values.corpus) {
    throw new Error("--corpus PATH is required: a standalone clone to serve");
  }
  const corpus = path.resolve(values.corpus);
  const corpus0 = corpusProvenance(corpus);
  if (!corpus0.commit) {
    throw new Error(`${corpus} is not a Git checkout; the corpus needs a commit identity`);
  }
  if (corpus0.dirty !== false) {
    throw new Error(`${corpus} has uncommitted changes; serve a clean corpus`);
  }
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
  const subset = !sameJson(journeys, Object.keys(JOURNEYS));
  // A diagnostic run writes beside the standard file, never into it, unless --out says so.
  const standard = !subset && !values.headed && !values["no-warmup"] && !values["keep-going"];
  const outFile = values.out
    ? path.resolve(values.out)
    : path.join(BENCH, values.exp, standard ? "runs.jsonl" : "diagnostic.jsonl");
  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  const series = new Date().toISOString().replace(/[:.]/g, "-");
  console.log(
    `${SCENARIO} r${SCENARIO_REVISION} ${values.exp} series ${series}: ${runs} run(s) x ${conditions.map((c) => c.label).join(", ")}, journeys ${journeys.join(",")}, ${values.headed ? "headed" : "headless"}, writing ${path.relative(REPO, outFile)}`,
  );
  if (!standard) {
    console.log(
      `NOT THE STANDARD REGIME: ${[subset && "a journey subset", values.headed && "headed", values["no-warmup"] && "no warm-up pass", values["keep-going"] && "keep going past refusals"].filter(Boolean).join(", ")}; compare notes it and refuses to mix it with standard runs`,
    );
  }
  let refused = 0;
  // Run numbers continue across series written to the same file, one sequence per label.
  const runCount = {};
  if (fs.existsSync(outFile)) {
    for (const row of parseRows(fs.readFileSync(outFile, "utf8"), outFile)) {
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
        keepGoing: values["keep-going"],
        subset,
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

// --------------------------------------------------------------------------- reading

const readRows = (file) => parseRows(fs.readFileSync(file, "utf8"), file);
const print = (lines) => process.stdout.write(`${lines.join("\n")}\n`);

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
    throw new CompareRefusal("summarize RUNS.jsonl");
  }
  const options = { condition: values.condition ?? null, allowMixed: values["allow-mixed"] };
  const rows = readRows(positionals[0]);
  if (values.format === "json") {
    console.log(JSON.stringify(summarizeJson(rows, options), null, 1));
  } else {
    print(summarize(rows, options));
  }
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
      expect: { type: "string", multiple: true },
    },
  });
  if (positionals.length !== 1) {
    throw new CompareRefusal("compare RUNS.jsonl --control LABEL --candidate LABEL | --aa LABEL");
  }
  const result = compareRuns(readRows(positionals[0]), {
    control: values.control,
    candidate: values.candidate,
    aa: values.aa,
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

/** Keep only what summarize and compare read, so a round can commit its samples. */
function cmdSamples(argv) {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: { out: { type: "string" } },
  });
  if (positionals.length !== 1 || !values.out) {
    throw new CompareRefusal("samples RUNS.jsonl --out FILE");
  }
  const lines = readRows(positionals[0]).map((r) => JSON.stringify(sampleRow(r)));
  fs.writeFileSync(values.out, `${lines.join("\n")}\n`);
  console.log(`wrote ${lines.length} row(s) to ${values.out}`);
  return 0;
}

// --------------------------------------------------------------------------- main

const USAGE = `usage:
  transitions.mjs run --exp exp-NNN --corpus PATH --condition LABEL=PATH/TO/metab
                      [--condition LABEL=PATH/TO/metab] [--runs 5] [--journeys a,b]
                      [--headed] [--no-warmup] [--keep-going] [--order alternate|fixed]
                      [--out FILE]
  transitions.mjs summarize RUNS.jsonl [--condition LABEL] [--format markdown|json]
  transitions.mjs compare RUNS.jsonl --control LABEL --candidate LABEL [--tolerance 1.3]
                      [--expect TRANSITION:METRIC:lower|higher]... [--format markdown|json]
  transitions.mjs compare RUNS.jsonl --aa LABEL      (odd against even runs of one build)
  transitions.mjs samples RUNS.jsonl --out FILE      (the fields summarize and compare read)
compare exits 0 when complete with no wrong-way result, 1 on a wrong-way result, a gap, or
an expectation not met (an A/A only on a gap), and 2 when it refuses.
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
