#!/usr/bin/env node

// Loading-tier probe: what one page load fetches, when, and what it paints.
//
// A loading tier is a claim about cost (docs/development.md, "Asset Loading Tiers"),
// and this is the instrument that measures it. It drives stock Chrome over the DevTools
// Protocol with a throwaway profile and loads one address on each named build in turn,
// every load in a browser context of its own so the HTTP cache starts empty. Builds are
// loaded back to back, so a ratio is between two loads taken next to each other. Each
// pair rotates the order by one, so over a multiple of as many pairs as there are builds
// every build takes every position equally often; each record names its position.
//
//   node tier-probe.mjs --out probe.jsonl --pairs 8 --path "/view/src/a.py#L40" \
//     --module plugin-sdk-views.js \
//     --build base=http://127.0.0.1:8771 --build after=http://127.0.0.1:8773
//
// The first --build is the control. The summary compares every other build with it, pair
// by pair: the median paired difference of each timing, with a 95% bootstrap interval
// (5,000 resamples, seeded, so the same records give the same interval), and, where the
// two builds' startup scripts transfer different bytes, that difference per transferred
// KB. `--summarize FILE` prints the summary of records already written, without a
// browser; `--control NAME` there compares with another build, as a slope between two
// candidates needs.
//
//   node tier-probe.mjs --summarize probe.jsonl --control stripped
//
// A file that keeps several series names each record's `series`, and `--series NAME`
// reads one of them, as the committed samples of experiments/exp-084 are read.
//
// Three options change the conditions of every load:
//
// - `--network LATENCY:DOWN:UP` emulates a link (milliseconds per request, kilobits per
//   second down and up), as `metab --remote` puts an SSH tunnel between the browser and
//   the server;
// - `--cpu RATE` slows the page's CPU by that factor;
// - `--warm N` loads each build N times first in Chrome's default profile and measures
//   there, so the HTTP cache and V8's code cache are filled as a returning reader's are.
//
// Per load it records, as one JSON line:
//
// - every script requested before DOMContentLoaded, with transferred and decoded bytes,
//   which is what `startup_script_requests` and `startup_script_transfer_kb` gate;
// - every script requested at all, so a module that left the startup set is seen where
//   it went;
// - compile and evaluate time of the scripts named by --module, from a trace;
// - what the startup scripts cost to the first tree row, from the same trace: when their
//   last byte arrived, their background (streamed) parse, their main-thread compile and
//   evaluate, lazy function compiles and parses, and main-thread busy time; and how many
//   times a startup script was evaluated again after that row, as a bundle that lists
//   one does;
// - first contentful paint, DOMContentLoaded, the first tree row and the frame after it,
//   and, on a file address, when a Source view first appeared, whether it had its line
//   gutter at that moment, and the gutter's width and the code's left edge one frame
//   later;
// - every layout shift with the elements that moved.
//
// The byte counts, request counts, gutter presence, and shift sources do not depend on
// how busy the machine is. The timings do: read them only as pair ratios or paired
// differences, and only from a quiet machine. Headless Chrome paints offscreen, so its
// paint timings are not the release gate's, which `run.py record` takes from a visible
// window.

import { spawn } from "node:child_process";
import { appendFileSync, existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const CHROME_CANDIDATES = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
];
const VIEWPORT = { width: 1280, height: 900 };
// Breaks a hung load; it is not a speed budget.
const LOAD_TIMEOUT_MS = 60_000;
// Long enough for the on-demand chain that follows the first tree to land, so a
// module that moved out of the startup set is still seen.
const SETTLE_MS = 600;
const POLL_MS = 20;

// A count or a rate, refused unless it is one: Number("x") is NaN, and NaN compares false
// with everything, so a load would quietly run unthrottled or skip its warm-up.
function numberOption(flag, value, { integer = false, minimum }) {
  const number = Number(value);
  if (value.trim() === "" || !Number.isFinite(number) || number < minimum) {
    throw new Error(`${flag} is a number of at least ${minimum}, not ${JSON.stringify(value)}`);
  }
  if (integer && !Number.isInteger(number)) {
    throw new Error(`${flag} is a whole number, not ${JSON.stringify(value)}`);
  }
  return number;
}

function parseArgs(argv) {
  const options = {
    builds: [],
    modules: [],
    pairs: 5,
    path: "/",
    out: "",
    done: "",
    network: "",
    cpu: 1,
    warm: 0,
    summarize: "",
    control: "",
    series: "",
  };
  for (let index = 0; index < argv.length; index += 2) {
    const [flag, value] = [argv[index], argv[index + 1]];
    if (value === undefined) {
      throw new Error(`${flag} needs a value`);
    }
    if (flag === "--build") {
      const split = value.indexOf("=");
      options.builds.push([value.slice(0, split), value.slice(split + 1)]);
    } else if (flag === "--module") {
      options.modules.push(value);
    } else if (flag === "--pairs") {
      options.pairs = numberOption(flag, value, { integer: true, minimum: 1 });
    } else if (flag === "--path") {
      options.path = value;
    } else if (flag === "--out") {
      options.out = value;
    } else if (flag === "--network") {
      if (!/^\d+:\d+:\d+$/.test(value)) {
        throw new Error("--network is LATENCY_MS:DOWN_KBPS:UP_KBPS, such as 80:20000:5000");
      }
      options.network = value;
    } else if (flag === "--cpu") {
      // DevTools takes 1 as no slowdown; a rate below it is not a CPU it can emulate.
      options.cpu = numberOption(flag, value, { minimum: 1 });
    } else if (flag === "--warm") {
      options.warm = numberOption(flag, value, { integer: true, minimum: 0 });
    } else if (flag === "--done") {
      // A page expression that is true once the load under study has finished, for a
      // view this probe has no rule for.
      options.done = value;
    } else if (flag === "--summarize") {
      options.summarize = value;
    } else if (flag === "--control") {
      options.control = value;
    } else if (flag === "--series") {
      options.series = value;
    } else {
      throw new Error(`unknown option ${flag}`);
    }
  }
  if (options.summarize) {
    return options;
  }
  if (options.control || options.series) {
    throw new Error(
      "--control and --series are for --summarize; a run's control is its first --build",
    );
  }
  if (!options.out || options.builds.length === 0) {
    throw new Error(
      "usage: tier-probe.mjs --out FILE --build NAME=ORIGIN [--build ...]\n" +
        "       tier-probe.mjs --summarize FILE [--series NAME] [--control NAME]",
    );
  }
  return options;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = sorted.length >> 1;
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

const BOOTSTRAP_RESAMPLES = 5000;
const BOOTSTRAP_SEED = 20261112;

// mulberry32: a small seeded generator, so a summary of the same records prints the same
// interval every time it is run.
function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let mixed = Math.imul(state ^ (state >>> 15), state | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

// The 95% percentile bootstrap interval of the median of `values`.
function medianInterval(values) {
  const random = seeded(BOOTSTRAP_SEED);
  const medians = [];
  for (let resample = 0; resample < BOOTSTRAP_RESAMPLES; resample += 1) {
    medians.push(median(Array.from(values, () => values[Math.floor(random() * values.length)])));
  }
  medians.sort((a, b) => a - b);
  const at = (quantile) => medians[Math.round(quantile * (medians.length - 1))];
  return [at(0.025), at(0.975)];
}

// "+6.60 (+2.80 to +12.60)": a median and its interval, as the summary prints each. A
// difference carries its sign; a ratio does not.
function withInterval(values, digits, { signed = true } = {}) {
  const format = (value) => (signed && value >= 0 ? "+" : "") + value.toFixed(digits);
  const [low, high] = medianInterval(values);
  return `${format(median(values))} (${format(low)} to ${format(high)})`;
}

// Runs in the page before any of its scripts.
const PAGE_PROBE = `(() => {
  const probe = (window.__tierProbe = { paints: {}, shifts: [], source: null, firstRow: null });
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) probe.paints[entry.name] = entry.startTime;
  }).observe({ type: "paint", buffered: true });
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      probe.shifts.push({
        at: entry.startTime,
        value: entry.value,
        hadRecentInput: entry.hadRecentInput,
        sources: (entry.sources || []).map((source) => {
          const node = source.node;
          const element = node && node.nodeType === 1 ? node : node && node.parentElement;
          if (!element) return "?";
          return element.id
            ? "#" + element.id
            : element.tagName.toLowerCase() + "." + String(element.className).split(" ")[0];
        }),
      });
    }
  }).observe({ type: "layout-shift", buffered: true });
  const look = () => {
    if (!probe.firstRow && document.querySelector("#tree-content [data-path]")) {
      probe.firstRow = performance.now();
      // The mark puts the row on the trace's clock, which bounds the main-thread sums.
      performance.mark("tier-probe-first-row");
      requestAnimationFrame(() => {
        probe.firstRowFrame = performance.now();
      });
    }
    const pre = !probe.source && document.querySelector(".metabrowser-source-lines");
    if (pre) {
      probe.source = {
        at: performance.now(),
        gutter: !!pre.querySelector(".source-line-numbers"),
        paintedAt: null,
        gutterWidth: null,
        codeLeft: null,
      };
      // Two frames on: what was painted, not what was inserted.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const gutter = document.querySelector(".metabrowser-source-lines .source-line-numbers");
        const code = document.querySelector(".metabrowser-source-lines code:not([hidden])");
        probe.source.paintedAt = performance.now();
        probe.source.gutterWidth = gutter ? gutter.getBoundingClientRect().width : 0;
        probe.source.codeLeft = code ? code.getBoundingClientRect().left : null;
      }));
    }
  };
  new MutationObserver(look).observe(document, { childList: true, subtree: true });
})();`;

const PAGE_REPORT = `JSON.stringify((() => {
  const navigation = performance.getEntriesByType("navigation")[0];
  const scripts = performance
    .getEntriesByType("resource")
    .filter((resource) => new URL(resource.name).pathname.endsWith(".js"))
    .map((resource) => ({
      name: new URL(resource.name).pathname,
      start: resource.startTime,
      end: resource.responseEnd,
      transferred: resource.transferSize,
      decoded: resource.decodedBodySize,
    }));
  return {
    probe: window.__tierProbe || null,
    domContentLoaded: navigation ? navigation.domContentLoadedEventEnd : null,
    htmlResponseEnd: navigation ? navigation.responseEnd : null,
    scripts,
  };
})())`;

// What the trace records of a startup script's cost. Chrome streams a classic script's
// parse onto a worker while it downloads (v8.parseOnBackground), so the main thread
// compiles only what streaming left (v8.compile), runs its top level (EvaluateScript),
// and compiles each function the first time it runs (V8.CompileCode around
// V8.ParseFunction).
const TRACE_CATEGORIES = [
  "devtools.timeline",
  "disabled-by-default-devtools.timeline",
  "v8",
  "disabled-by-default-v8.compile",
  "blink.user_timing",
  "toplevel",
  "__metadata",
];

class Browser {
  static async launch() {
    const executable = process.env.CHROME || CHROME_CANDIDATES.find((path_) => existsSync(path_));
    if (!executable) {
      throw new Error("no Chrome found; set CHROME to its executable");
    }
    const profile = mkdtempSync(path.join(os.tmpdir(), "metab-tier-probe-"));
    const port = 9300 + Math.floor(Math.random() * 500);
    const child = spawn(
      executable,
      [
        "--headless=new",
        `--remote-debugging-port=${port}`,
        `--user-data-dir=${profile}`,
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-background-networking",
        `--window-size=${VIEWPORT.width},${VIEWPORT.height}`,
        "about:blank",
      ],
      { stdio: "ignore" },
    );
    let endpoint = null;
    for (let attempt = 0; attempt < 150 && !endpoint; attempt += 1) {
      try {
        const version = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json();
        endpoint = version.webSocketDebuggerUrl;
        Browser.version = version.Browser;
      } catch {
        await sleep(100);
      }
    }
    if (!endpoint) {
      child.kill();
      throw new Error("Chrome did not open its DevTools endpoint");
    }
    const socket = new WebSocket(endpoint);
    await new Promise((resolve, reject) => {
      socket.onopen = resolve;
      socket.onerror = reject;
    });
    return new Browser(child, profile, socket);
  }

  constructor(child, profile, socket) {
    this.child = child;
    this.profile = profile;
    this.socket = socket;
    this.nextId = 0;
    this.pending = new Map();
    this.listeners = new Set();
    socket.onmessage = (message) => {
      const data = JSON.parse(message.data);
      const waiting = data.id ? this.pending.get(data.id) : null;
      if (waiting) {
        this.pending.delete(data.id);
        waiting(data);
        return;
      }
      for (const listener of this.listeners) {
        listener(data);
      }
    };
  }

  send(method, params = {}, sessionId = undefined) {
    return new Promise((resolve, reject) => {
      const id = ++this.nextId;
      this.pending.set(id, (data) =>
        data.error ? reject(new Error(`${method}: ${data.error.message}`)) : resolve(data.result),
      );
      this.socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }

  async close() {
    const exited = new Promise((resolve) => this.child.once("exit", resolve));
    await this.send("Browser.close").catch(() => {});
    this.socket.close();
    this.child.kill();
    // Chrome still writes to its profile while it exits; removing it sooner fails.
    await Promise.race([exited, sleep(5000)]);
    // On a loaded host Chrome can outlive SIGTERM, and its handle keeps this process
    // running after the summary.
    if (this.child.exitCode === null && this.child.signalCode === null) {
      this.child.kill("SIGKILL");
      await Promise.race([exited, sleep(5000)]);
    }
    rmSync(this.profile, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 });
  }
}

async function emulate(browser, sessionId, options) {
  if (options.network) {
    const [latency, downKbps, upKbps] = options.network.split(":").map(Number);
    await browser.send("Network.enable", {}, sessionId);
    await browser.send(
      "Network.emulateNetworkConditions",
      {
        offline: false,
        latency,
        downloadThroughput: (downKbps * 1000) / 8,
        uploadThroughput: (upKbps * 1000) / 8,
      },
      sessionId,
    );
  }
  if (options.cpu > 1) {
    await browser.send("Emulation.setCPUThrottlingRate", { rate: options.cpu }, sessionId);
  }
}

// The startup scripts' cost, from the load's trace; see TRACE_CATEGORIES.
function startupCost(events, startupNames, origin, firstRowMs) {
  const pathOf = (url) => {
    try {
      return new URL(url).pathname;
    } catch {
      return "";
    }
  };
  // The renderer's main thread is the one that evaluated the page's scripts.
  const evaluations = new Map();
  for (const event of events) {
    if (event.name === "EvaluateScript") {
      const key = `${event.pid}:${event.tid}`;
      evaluations.set(key, (evaluations.get(key) ?? 0) + 1);
    }
  }
  const main = [...evaluations.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
  const onMain = (event) => `${event.pid}:${event.tid}` === main;
  let navigationStart = null;
  let firstRowAt = Number.POSITIVE_INFINITY;
  for (const event of events) {
    if (event.name === "navigationStart" && onMain(event)) {
      if ((event.args?.data?.documentLoaderURL ?? "").startsWith(origin)) {
        navigationStart = event.ts;
      }
    } else if (event.name === "tier-probe-first-row") {
      firstRowAt = event.ts;
    }
  }
  if (firstRowAt === Number.POSITIVE_INFINITY && navigationStart !== null && firstRowMs) {
    firstRowAt = navigationStart + firstRowMs * 1000;
  }
  const cost = {
    backgroundParseMs: 0,
    mainCompileMs: 0,
    evaluateMs: 0,
    lazyCompileMs: 0,
    lazyParseMs: 0,
    mainBusyToFirstRowMs: 0,
    streamed: 0,
    compiled: 0,
    codeCacheConsumed: 0,
    // A script made a startup script that stays in an on-demand bundle runs again when
    // the bundle loads. That run is not a startup cost, and is counted here instead.
    evaluatedAfterFirstRow: 0,
  };
  const ms = (event) => (event.dur ?? 0) / 1000;
  for (const event of events) {
    if (event.ph !== "X") {
      continue;
    }
    const startup = startupNames.has(pathOf(event.args?.data?.url ?? event.args?.fileName ?? ""));
    // Every sum stops at the first row, as the cost it reads does. A worker's events are
    // on the same trace clock as the main thread's.
    const toFirstRow = event.ts >= (navigationStart ?? 0) && event.ts <= firstRowAt;
    if (event.name === "v8.parseOnBackground") {
      cost.backgroundParseMs += startup && toFirstRow ? ms(event) : 0;
    } else if (!onMain(event)) {
      continue;
    } else if (event.name === "EvaluateScript" && startup && !toFirstRow) {
      cost.evaluatedAfterFirstRow += 1;
    } else if (!toFirstRow) {
      continue;
    } else if (event.name === "v8.compile" && startup) {
      cost.mainCompileMs += ms(event);
      cost.compiled += 1;
      cost.streamed += event.args?.data?.streamed ? 1 : 0;
      cost.codeCacheConsumed += event.args?.data?.consumedCacheSize ? 1 : 0;
    } else if (event.name === "EvaluateScript" && startup) {
      cost.evaluateMs += ms(event);
    } else {
      if (event.name === "V8.CompileCode") {
        cost.lazyCompileMs += ms(event);
      } else if (event.name === "V8.ParseFunction") {
        cost.lazyParseMs += ms(event);
      } else if (event.name === "RunTask") {
        cost.mainBusyToFirstRowMs += ms(event);
      }
    }
  }
  return cost;
}

async function loadOnce(browser, name, origin, options) {
  // A warm series loads in the default profile, whose caches the warm-up loads filled.
  const { browserContextId } =
    options.warm > 0
      ? { browserContextId: undefined }
      : await browser.send("Target.createBrowserContext", { disposeOnDetach: true });
  const { targetId } = await browser.send("Target.createTarget", {
    url: "about:blank",
    // Only a new window takes a size in the default profile.
    ...(browserContextId ? { browserContextId } : { newWindow: true }),
    ...VIEWPORT,
  });
  const { sessionId } = await browser.send("Target.attachToTarget", { targetId, flatten: true });
  await emulate(browser, sessionId, options);
  const events = [];
  let finishTrace = () => {};
  const traced = new Promise((resolve) => {
    finishTrace = resolve;
  });
  const listener = (data) => {
    if (data.sessionId !== sessionId) {
      return;
    }
    if (data.method === "Tracing.dataCollected") {
      events.push(...data.params.value);
    } else if (data.method === "Tracing.tracingComplete") {
      finishTrace();
    }
  };
  browser.listeners.add(listener);
  await browser.send("Page.enable", {}, sessionId);
  await browser.send("Runtime.enable", {}, sessionId);
  await browser.send("Page.addScriptToEvaluateOnNewDocument", { source: PAGE_PROBE }, sessionId);
  await browser.send(
    "Tracing.start",
    {
      transferMode: "ReportEvents",
      traceConfig: { includedCategories: TRACE_CATEGORIES },
    },
    sessionId,
  );
  const evaluate = async (expression) => {
    const result = await browser.send(
      "Runtime.evaluate",
      { expression, awaitPromise: true, returnByValue: true },
      sessionId,
    );
    return result.result?.value;
  };
  const load1 = os.loadavg()[0];
  await browser.send("Page.navigate", { url: origin + options.path }, sessionId);
  const onFile = options.path.startsWith("/view/") && !options.path.split("#")[0].endsWith("/");
  const done =
    options.done ||
    (onFile
      ? "!!(window.__tierProbe && window.__tierProbe.source && window.__tierProbe.source.paintedAt)"
      : "!!(window.__tierProbe && window.__tierProbe.firstRow && document.readyState === 'complete')");
  const started = Date.now();
  let complete = false;
  while (!complete && Date.now() - started < LOAD_TIMEOUT_MS) {
    complete = (await evaluate(done)) === true;
    if (!complete) {
      await sleep(POLL_MS);
    }
  }
  await sleep(SETTLE_MS);
  const page = JSON.parse((await evaluate(PAGE_REPORT)) ?? "{}");
  await browser.send("Tracing.end", {}, sessionId);
  await traced;
  browser.listeners.delete(listener);
  await browser.send("Target.closeTarget", { targetId });
  if (browserContextId) {
    await browser.send("Target.disposeBrowserContext", { browserContextId });
  }

  const named = (url) => options.modules.some((module_) => url.includes(module_));
  let moduleEvaluateMs = 0;
  let moduleCompileMs = 0;
  let allEvaluateCpuMs = 0;
  for (const event of events) {
    if (event.ph !== "X") {
      continue;
    }
    const url = event.args?.data?.url ?? event.args?.fileName ?? "";
    if (event.name === "EvaluateScript") {
      allEvaluateCpuMs += (event.tdur ?? 0) / 1000;
      if (named(url)) {
        moduleEvaluateMs += (event.dur ?? 0) / 1000;
      }
    } else if (event.name === "v8.compile" && named(url)) {
      moduleCompileMs += (event.dur ?? 0) / 1000;
    }
  }
  const scripts = page.scripts ?? [];
  const startup = scripts.filter(
    (script) => script.start < page.domContentLoaded && !script.name.includes("/static/vendor/"),
  );
  const sum = (list, field) => list.reduce((total, script) => total + script[field], 0);
  const firstRowMs = page.probe?.firstRow ?? null;
  return {
    build: name,
    path: options.path,
    network: options.network || null,
    cpu: options.cpu,
    warm: options.warm,
    complete,
    load1,
    chrome: Browser.version,
    firstContentfulPaintMs: page.probe?.paints?.["first-contentful-paint"] ?? null,
    domContentLoadedMs: page.domContentLoaded,
    firstRowMs,
    firstRowFrameMs: page.probe?.firstRowFrame ?? null,
    htmlResponseEndMs: page.htmlResponseEnd ?? null,
    source: page.probe?.source ?? null,
    shifts: page.probe?.shifts ?? [],
    startupScriptRequests: startup.length,
    startupScriptTransferBytes: sum(startup, "transferred"),
    startupScriptDecodedBytes: sum(startup, "decoded"),
    // A script read from the HTTP cache reports no transfer.
    startupScriptsFromCache: startup.filter((script) => script.transferred === 0).length,
    startupScriptsLastByteMs: startup.length ? Math.max(...startup.map((s) => s.end)) : null,
    startupCost: startupCost(
      events,
      new Set(startup.map((script) => script.name)),
      origin,
      firstRowMs,
    ),
    moduleInStartupSet: startup.some((script) => named(script.name)),
    moduleEvaluateMs,
    moduleCompileMs,
    allEvaluateCpuMs,
    scripts,
  };
}

// The timings a startup comparison reads, as [label, value of a record]. A record that
// lacks one, such as a sample kept without its trace sums, is left out of that timing.
const COST_TIMINGS = [
  ["firstRowMs", (record) => record.firstRowMs],
  ["startupScriptsLastByteMs", (record) => record.startupScriptsLastByteMs],
  ["backgroundParseMs", (record) => record.startupCost?.backgroundParseMs],
  ["mainCompileMs", (record) => record.startupCost?.mainCompileMs],
  ["evaluateMs", (record) => record.startupCost?.evaluateMs],
  ["lazyCompileMs", (record) => record.startupCost?.lazyCompileMs],
  ["mainBusyToFirstRowMs", (record) => record.startupCost?.mainBusyToFirstRowMs],
];

// Each record's place in its pair's load order: the one it recorded, or, for a record
// written before the probe recorded it, its place among its pair's records in the file,
// which is the order they were loaded in.
function positions(records) {
  const seen = new Map();
  return records.map((record) => {
    const place = seen.get(record.pair) ?? 0;
    seen.set(record.pair, place + 1);
    return record.position ?? place;
  });
}

// [control record, candidate record] for each pair in which both loads completed.
function pairsOf(records, control, candidate) {
  const pairs = [];
  for (const pair of new Set(records.map((record) => record.pair))) {
    const a = records.find((record) => record.pair === pair && record.build === control);
    const b = records.find((record) => record.pair === pair && record.build === candidate);
    if (a?.complete && b?.complete) {
      pairs.push([a, b]);
    }
  }
  return pairs;
}

function summarize(records, builds, options) {
  for (const [name] of builds) {
    const rows = records.filter((record) => record.build === name && record.complete);
    if (rows.length === 0) {
      console.log(`${name}: no complete load`);
      continue;
    }
    const last = rows.at(-1);
    const shiftSources = new Map();
    for (const row of rows) {
      for (const shift of row.shifts ?? []) {
        for (const source of shift.sources) {
          shiftSources.set(source, (shiftSources.get(source) ?? 0) + 1);
        }
      }
    }
    console.log(
      `${name}: ${rows.length} loads, startup scripts ${last.startupScriptRequests} requests, ` +
        `${last.startupScriptTransferBytes} bytes transferred ` +
        `(${Math.round(last.startupScriptTransferBytes / 1024)} KB), ` +
        `${last.startupScriptDecodedBytes} decoded` +
        (last.scripts
          ? `; all scripts ${last.scripts.length} requests, ` +
            `${last.scripts.reduce((total, script) => total + script.transferred, 0)} transferred`
          : ""),
    );
    if (options.modules.length) {
      console.log(
        `  ${options.modules.join(", ")}: in the startup set ${last.moduleInStartupSet}; ` +
          `compile+evaluate median ` +
          `${median(rows.map((row) => row.moduleEvaluateMs + row.moduleCompileMs)).toFixed(2)} ms`,
      );
    }
    const sources = rows.map((row) => row.source).filter(Boolean);
    if (sources.length) {
      console.log(
        `  Source view appeared with its gutter in ` +
          `${sources.filter((source) => source.gutter).length}/${sources.length} loads; ` +
          `gutter width ${[...new Set(sources.map((source) => source.gutterWidth))].join(", ")}; ` +
          `code left edge ${[...new Set(sources.map((source) => source.codeLeft))].join(", ")}`,
      );
    }
    if (shiftSources.size) {
      console.log(`  layout shift sources: ${JSON.stringify(Object.fromEntries(shiftSources))}`);
    }
    const cost = last.startupCost;
    console.log(
      `  startup scripts: ${last.startupScriptsFromCache} from the HTTP cache, ` +
        (cost
          ? `${cost.streamed}/${cost.compiled} streamed, ${cost.codeCacheConsumed} from the ` +
            `code cache, ${cost.evaluatedAfterFirstRow ?? 0} evaluated again after the first ` +
            `row; `
          : "") +
        `medians ` +
        COST_TIMINGS.map(
          ([label, value]) =>
            `${label} ${median(rows.map(value).filter(Number.isFinite))?.toFixed(1)}`,
        ).join(", "),
    );
  }
  // A load's place in its pair can move its timing. Rotation over a multiple of as many
  // pairs as there are builds gives every build every place equally often; reversing
  // the order every other pair, as records before rotation did, leaves the middle builds
  // of three or more never first or last. Only a balanced series shows the effect of a
  // place on its own, as the median first row at each place over all builds.
  const placed = positions(records);
  const places = new Map(builds.map(([name]) => [name, new Map()]));
  const byPlace = new Map();
  records.forEach((record, index) => {
    const counts = places.get(record.build);
    if (!counts || !record.complete) {
      return;
    }
    counts.set(placed[index], (counts.get(placed[index]) ?? 0) + 1);
    if (Number.isFinite(record.firstRowMs)) {
      byPlace.set(placed[index], [...(byPlace.get(placed[index]) ?? []), record.firstRowMs]);
    }
  });
  const tallies = [...places.values()].flatMap((counts) =>
    builds.map((_, place) => counts.get(place) ?? 0),
  );
  const balanced = tallies.every((tally) => tally === tallies[0]);
  console.log(
    `positions in the pair${balanced ? ", balanced" : ", not balanced"}: ` +
      [...places.entries()]
        .map(
          ([name, counts]) =>
            `${name} ` +
            [...counts.entries()]
              .sort((a, b) => a[0] - b[0])
              .map(([place, count]) => `${place}x${count}`)
              .join(" "),
        )
        .join("; ") +
      (balanced
        ? `; firstRowMs median by position ` +
          [...byPlace.entries()]
            .sort((a, b) => a[0] - b[0])
            .map(([place, values]) => `${place}: ${median(values).toFixed(1)}`)
            .join(", ")
        : ""),
  );
  const [control, ...candidates] = builds.map(([name]) => name);
  const timing = (record, field) =>
    field === "sourcePaintedMs" ? (record.source?.paintedAt ?? null) : record[field];
  for (const candidate of candidates) {
    const pairs = pairsOf(records, control, candidate);
    for (const field of [
      "firstContentfulPaintMs",
      "firstRowMs",
      "domContentLoadedMs",
      "sourcePaintedMs",
    ]) {
      const usable = pairs.filter(([a, b]) => timing(a, field) && timing(b, field));
      if (usable.length) {
        const ratios = usable.map(([a, b]) => timing(b, field) / timing(a, field));
        const loads = usable.flatMap(([a, b]) => [a.load1, b.load1]);
        console.log(
          `${candidate}/${control} ${field}: median ratio ` +
            `${withInterval(ratios, 3, { signed: false })}, ` +
            `pairs ${Math.min(...ratios).toFixed(2)}-${Math.max(...ratios).toFixed(2)}, ` +
            `load ${Math.min(...loads).toFixed(0)}-${Math.max(...loads).toFixed(0)}`,
        );
      }
    }
    // A cost in milliseconds compares as a paired difference: a ratio of two small
    // numbers says little. Divided by the pair's difference in transferred startup
    // bytes, it is what a KB of them cost, which is how a byte ceiling is read.
    for (const [label, value] of COST_TIMINGS) {
      const usable = pairs.filter(
        ([a, b]) => Number.isFinite(value(a)) && Number.isFinite(value(b)),
      );
      if (!usable.length) {
        continue;
      }
      const differences = usable.map(([a, b]) => value(b) - value(a));
      const kilobytes = usable.map(
        ([a, b]) => (b.startupScriptTransferBytes - a.startupScriptTransferBytes) / 1024,
      );
      const perKb = kilobytes.every((kb) => kb !== 0)
        ? `, ${withInterval(
            differences.map((difference, index) => difference / kilobytes[index]),
            3,
          )} ms per transferred KB`
        : "";
      console.log(
        `${candidate}-${control} ${label}: median difference ` +
          `${withInterval(differences, 2)} ms over ${differences.length} pairs${perKb}`,
      );
    }
  }
}

// Records already written, and their builds in the order the first pair loaded them,
// which puts a run's control first; --control puts another build there. A file that
// keeps several series, each record naming its own, is read one --series at a time.
function recorded(file, control, series) {
  const all = readFileSync(file, "utf8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
  const named = [...new Set(all.map((record) => record.series).filter(Boolean))];
  if (series && !named.includes(series)) {
    throw new Error(`--series ${series} is not in ${file}: ${named.join(", ") || "none"}`);
  }
  if (!series && named.length > 1) {
    throw new Error(`${file} holds several series; name one with --series: ${named.join(", ")}`);
  }
  const records = series ? all.filter((record) => record.series === series) : all;
  const names = [...new Set(records.map((record) => record.build))];
  if (control && !names.includes(control)) {
    throw new Error(`--control ${control} is not a build in ${file}: ${names.join(", ")}`);
  }
  const ordered = control ? [control, ...names.filter((name) => name !== control)] : names;
  return { records, builds: ordered.map((name) => [name, ""]) };
}

async function run(options) {
  const builds = options.builds;
  if (options.pairs % builds.length) {
    console.warn(
      `--pairs ${options.pairs} is not a multiple of the ${builds.length} builds, ` +
        `so some builds take some positions in a pair more often than others`,
    );
  }
  const browser = await Browser.launch();
  const records = [];
  try {
    // Discarded loads per build: the first after launch pays for process start, and a
    // warm series fills the caches. V8 writes a script's code cache on its second run.
    for (const [name, origin] of builds) {
      for (let load = 0; load < Math.max(1, options.warm); load += 1) {
        await loadOnce(browser, name, origin, options);
      }
    }
    for (let pair = 0; pair < options.pairs; pair += 1) {
      // Rotated by one each pair: over as many pairs as there are builds, every build
      // loads once in every position, and with two builds this alternates them.
      const shift = pair % builds.length;
      const order = [...builds.slice(shift), ...builds.slice(0, shift)];
      for (const [position, [name, origin]] of order.entries()) {
        const record = {
          pair,
          position,
          recordedAt: Date.now() / 1000,
          ...(await loadOnce(browser, name, origin, options)),
        };
        records.push(record);
        appendFileSync(options.out, `${JSON.stringify(record)}\n`);
        console.log(
          `pair ${pair} ${name} load=${record.load1.toFixed(0)} complete=${record.complete}`,
        );
      }
    }
  } finally {
    await browser.close();
  }
  return records;
}

const options = parseArgs(process.argv.slice(2));
if (options.summarize) {
  const { records, builds } = recorded(options.summarize, options.control, options.series);
  summarize(records, builds, options);
} else {
  summarize(await run(options), options.builds, options);
}
