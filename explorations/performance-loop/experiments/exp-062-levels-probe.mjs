// exp-062's pilot instrument: dependent request levels in a cold Markdown landing.
//
//   node exp-062-levels-probe.mjs --harness DIR --corpus PATH --pairs N --out FILE \
//     --port 8920 --condition control=PATH/metab --condition candidate=PATH/metab
//
// The transition scenario (transitions.mjs) times shell tools and the first styled view
// but does not count how many round trips deep they are, which H89 also names. This
// probe counts them. Per pair, each condition in turn (the first leads odd pairs): a fresh
// server on --port, its inventory complete; one unrecorded landing in a throwaway Chrome
// profile, so the server is warm; then the measured landing on /view/README.md in a fresh
// profile, so the browser is cold, as the scenario's regime is. Chrome is launched with
// the harness's own launchBrowser and requests are classed with its requestClass.
//
// The level of a request: 1 for one that starts before any network request has ended;
// otherwise 1 + the highest level of a network request that ended before it started. It
// is the longest chain of round trips that do not overlap, ending at that request, so a
// chain fetched one request at a time is as deep as it is long, and requests fetched
// together share a level. A request the browser answered from its memory or disk cache
// (a script read from its preload, say) is not a round trip and takes no part. The
// stream (`/api/events`) and the Pulls catalog's background work are left out: they run
// on their own clocks. The window ends when no other request has started for 3 s, or
// 30 s after the navigation. A level is an upper bound on the true dependency depth: two
// requests that merely happened in sequence count as a chain.
//
// Each row records: the levels of the last shell-tools script and of the last KPress
// stylesheet or script, the highest level, their network end times from the document's
// start, the counts, the build's version line, and the one-minute load average when the
// run started (`load1`) and when its measured landing started (`load1_landing`). Rows
// carry the invocation's `series`, so pairs from two invocations do not share a key.

import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { parseArgs } from "node:util";

const { values } = parseArgs({
  options: {
    harness: { type: "string" },
    corpus: { type: "string" },
    pairs: { type: "string", default: "4" },
    out: { type: "string" },
    port: { type: "string", default: "8920" },
    state: { type: "string" },
    condition: { type: "string", multiple: true },
  },
});
const harness = path.resolve(values.harness);
const { launchBrowser, requestClass } = await import(
  path.join(harness, "explorations/performance-loop/transitions-recorder.mjs")
);
const corpus = path.resolve(values.corpus);
const pairs = Number.parseInt(values.pairs, 10);
const port = Number.parseInt(values.port, 10);
const state = path.resolve(values.state ?? path.join(path.dirname(values.out), "levels-state"));
const conditions = (values.condition ?? []).map((spec) => {
  const at = spec.indexOf("=");
  return { label: spec.slice(0, at), metab: path.resolve(spec.slice(at + 1)) };
});
if (conditions.length !== 2 || !(pairs >= 1) || !values.out) {
  throw new Error("two --condition LABEL=PATH, --pairs N, and --out FILE are required");
}
const SUBJECT = "README.md";
const QUIET_MS = 3000;
const WINDOW_MS = 30000;
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function version(metab) {
  return execFileSync(metab, ["--version"], { encoding: "utf8" }).trim();
}

async function startServer(condition) {
  const home = path.join(state, condition.label);
  const cache = path.join(home, "cache");
  const config = path.join(home, "config");
  fs.mkdirSync(cache, { recursive: true });
  fs.mkdirSync(config, { recursive: true });
  const log = fs.openSync(path.join(home, "server.log"), "w");
  const child = spawn(
    condition.metab,
    [corpus, "--no-open", "--port", String(port), "--cache-dir", cache, "--config-dir", config],
    { cwd: home, detached: true, stdio: ["ignore", log, log] },
  );
  fs.closeSync(log);
  const base = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 120000;
  while (Date.now() < deadline) {
    try {
      const progress = await (
        await fetch(`${base}/api/index/progress`, { signal: AbortSignal.timeout(5000) })
      ).json();
      if (progress.complete) {
        return { child, base };
      }
    } catch (_error) {
      // Not listening yet.
    }
    await sleep(200);
  }
  stopServer({ child });
  throw new Error(`${condition.label}: the server did not finish its inventory`);
}

function stopServer(server) {
  try {
    process.kill(-server.child.pid, "SIGTERM");
  } catch (_error) {
    // Already gone.
  }
}

async function waitStopped(server) {
  for (let i = 0; i < 100 && server.child.exitCode === null; i += 1) {
    await sleep(100);
  }
}

/** Land on the subject in a fresh profile; return each request's timing and class. */
async function land(base, profileDir) {
  const browser = await launchBrowser({ profileDir });
  const timing = new Map();
  let lastStart = 0;
  browser.conn.listeners.add((method, params, sid) => {
    const key = `${sid}:${params.requestId}`;
    if (method === "Network.requestWillBeSent") {
      const cls = requestClass(params.request.url, params.type);
      const previous = timing.get(key);
      timing.set(key, {
        url: params.request.url,
        cls,
        start: previous?.start ?? params.timestamp,
        end: null,
        cached: false,
      });
      if (cls !== "stream" && cls !== "background" && cls !== "inline") {
        lastStart = Date.now();
      }
      return;
    }
    const entry =
      timing.get(key) ??
      [...timing.entries()].find(([k]) => k.endsWith(`:${params.requestId}`))?.[1];
    if (!entry) {
      return;
    }
    if (method === "Network.requestServedFromCache") {
      entry.cached = true;
    } else if (method === "Network.responseReceived" && params.response.fromDiskCache) {
      entry.cached = true;
    } else if (method === "Network.loadingFinished" || method === "Network.loadingFailed") {
      entry.end = params.timestamp;
    }
  });
  const navigated = Date.now();
  lastStart = navigated;
  await browser.page.send("Page.navigate", { url: `${base}/view/${SUBJECT}` });
  while (Date.now() - navigated < WINDOW_MS && Date.now() - lastStart < QUIET_MS) {
    await sleep(100);
  }
  const bundles = await browser.page.send("Runtime.evaluate", {
    expression: "JSON.stringify(window.METABROWSER_ASSET_BUNDLES?.['shell-tools'] ?? [])",
    returnByValue: true,
  });
  const shellTools = new Set(
    JSON.parse(bundles.result.value).map((entry) => new URL(entry.src, base).pathname),
  );
  await browser.close();
  return { requests: [...timing.values()], shellTools, windowMs: Date.now() - navigated };
}

function levels(requests) {
  const network = requests
    .filter((r) => !r.cached && !["stream", "background", "inline"].includes(r.cls))
    .sort((a, b) => a.start - b.start);
  const t0 = network[0]?.start ?? 0;
  for (const r of network) {
    let level = 1;
    for (const p of network) {
      if (p !== r && p.end !== null && p.end <= r.start) {
        level = Math.max(level, (p.level ?? 0) + 1);
      }
    }
    r.level = level;
  }
  return { network, t0 };
}

function summary(run) {
  const { network, t0 } = levels(run.requests);
  const pathOf = (r) => new URL(r.url).pathname;
  const tools = network.filter((r) => run.shellTools.has(pathOf(r)));
  const kpress = network.filter(
    (r) => pathOf(r).startsWith("/kpress-static/") && /\.(css|js)$/.test(pathOf(r)),
  );
  const ms = (t) => (t === null ? null : Math.round((t - t0) * 10000) / 10);
  const last = (list, field) =>
    list.length
      ? Math.max(...list.map((r) => (field === "end" ? (r.end ?? r.start) : r.level)))
      : null;
  return {
    levels_shell_tools: last(tools, "level"),
    levels_kpress: last(kpress, "level"),
    levels_max: last(network, "level"),
    shell_tools_end_ms: tools.length ? ms(last(tools, "end")) : null,
    kpress_end_ms: kpress.length ? ms(last(kpress, "end")) : null,
    requests_network: network.length,
    requests_cached: run.requests.filter((r) => r.cached).length,
    shell_tools_requests: tools.length,
    shell_tools_expected: run.shellTools.size,
    kpress_requests: kpress.length,
    window_ms: run.windowMs,
  };
}

const builds = Object.fromEntries(conditions.map((c) => [c.label, version(c.metab)]));
const series = new Date().toISOString().replace(/[:.]/g, "-");
fs.mkdirSync(path.dirname(path.resolve(values.out)), { recursive: true });
for (let pair = 1; pair <= pairs; pair += 1) {
  const order = pair % 2 === 1 ? conditions : [...conditions].reverse();
  for (const condition of order) {
    const load1 = os.loadavg()[0];
    const server = await startServer(condition);
    try {
      const profiles = path.join(state, condition.label, "profiles");
      await land(server.base, path.join(profiles, `warm-up-${series}-${pair}`));
      const load1Landing = os.loadavg()[0];
      const run = await land(server.base, path.join(profiles, `${series}-pair-${pair}`));
      const row = {
        exp: "exp-062",
        instrument: "levels-probe",
        series,
        pair,
        condition: condition.label,
        build: builds[condition.label],
        subject: SUBJECT,
        load1: Math.round(load1 * 100) / 100,
        load1_landing: Math.round(load1Landing * 100) / 100,
        ...summary(run),
      };
      fs.appendFileSync(values.out, `${JSON.stringify(row)}\n`);
      console.log(JSON.stringify(row));
    } finally {
      stopServer(server);
      await waitStopped(server);
    }
  }
}
