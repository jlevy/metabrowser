#!/usr/bin/env node

// Loading-tier probe: what one page load fetches, when, and what it paints.
//
// A loading tier is a claim about cost (docs/development.md, "Asset Loading Tiers"),
// and this is the instrument that measures it. It drives stock Chrome over the DevTools
// Protocol with a throwaway profile and loads one address on each named build in turn,
// every load in a browser context of its own so the HTTP cache starts empty. Builds are
// loaded back to back, so a ratio is between two loads taken next to each other.
//
//   node tier-probe.mjs --out probe.jsonl --pairs 8 --path "/view/src/a.py#L40" \
//     --module plugin-sdk-views.js \
//     --build base=http://127.0.0.1:8771 --build after=http://127.0.0.1:8773
//
// Per load it records, as one JSON line:
//
// - every script requested before DOMContentLoaded, with transferred and decoded bytes,
//   which is what `startup_script_requests` and `startup_script_transfer_kb` gate;
// - every script requested at all, so a module that left the startup set is seen where
//   it went;
// - compile and evaluate time of the scripts named by --module, from a trace;
// - first contentful paint, DOMContentLoaded, the first tree row, and, on a file
//   address, when a Source view first appeared, whether it had its line gutter at that
//   moment, and the gutter's width and the code's left edge one frame later;
// - every layout shift with the elements that moved.
//
// The byte counts, request counts, gutter presence, and shift sources do not depend on
// how busy the machine is. The timings do: read them only as pair ratios, and only from
// a quiet machine. Headless Chrome paints offscreen, so its paint timings are not the
// release gate's, which `run.py record` takes from a visible window.

import { spawn } from "node:child_process";
import { appendFileSync, existsSync, mkdtempSync, rmSync } from "node:fs";
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

function parseArgs(argv) {
  const options = { builds: [], modules: [], pairs: 5, path: "/", out: "", done: "" };
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
      options.pairs = Number(value);
    } else if (flag === "--path") {
      options.path = value;
    } else if (flag === "--out") {
      options.out = value;
    } else if (flag === "--done") {
      // A page expression that is true once the load under study has finished, for a
      // view this probe has no rule for.
      options.done = value;
    } else {
      throw new Error(`unknown option ${flag}`);
    }
  }
  if (!options.out || options.builds.length === 0) {
    throw new Error("usage: tier-probe.mjs --out FILE --build NAME=ORIGIN [--build ...]");
  }
  return options;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = sorted.length >> 1;
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

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
    scripts,
  };
})())`;

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
    rmSync(this.profile, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 });
  }
}

async function loadOnce(browser, name, origin, options) {
  const { browserContextId } = await browser.send("Target.createBrowserContext", {
    disposeOnDetach: true,
  });
  const { targetId } = await browser.send("Target.createTarget", {
    url: "about:blank",
    browserContextId,
    ...VIEWPORT,
  });
  const { sessionId } = await browser.send("Target.attachToTarget", { targetId, flatten: true });
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
      traceConfig: { includedCategories: ["devtools.timeline", "v8"] },
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
  await browser.send("Target.disposeBrowserContext", { browserContextId });

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
  return {
    build: name,
    path: options.path,
    complete,
    load1,
    chrome: Browser.version,
    firstContentfulPaintMs: page.probe?.paints?.["first-contentful-paint"] ?? null,
    domContentLoadedMs: page.domContentLoaded,
    firstRowMs: page.probe?.firstRow ?? null,
    source: page.probe?.source ?? null,
    shifts: page.probe?.shifts ?? [],
    startupScriptRequests: startup.length,
    startupScriptTransferBytes: sum(startup, "transferred"),
    startupScriptDecodedBytes: sum(startup, "decoded"),
    moduleInStartupSet: startup.some((script) => named(script.name)),
    moduleEvaluateMs,
    moduleCompileMs,
    allEvaluateCpuMs,
    scripts,
  };
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
      for (const shift of row.shifts) {
        for (const source of shift.sources) {
          shiftSources.set(source, (shiftSources.get(source) ?? 0) + 1);
        }
      }
    }
    console.log(
      `${name}: ${rows.length} loads, startup scripts ${last.startupScriptRequests} requests, ` +
        `${last.startupScriptTransferBytes} bytes transferred ` +
        `(${Math.round(last.startupScriptTransferBytes / 1024)} KB), ` +
        `${last.startupScriptDecodedBytes} decoded; all scripts ${last.scripts.length} requests, ` +
        `${last.scripts.reduce((total, script) => total + script.transferred, 0)} transferred`,
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
    console.log(`  layout shift sources: ${JSON.stringify(Object.fromEntries(shiftSources))}`);
  }
  const [control, ...candidates] = builds.map(([name]) => name);
  const timing = (record, field) =>
    field === "sourcePaintedMs" ? (record.source?.paintedAt ?? null) : record[field];
  for (const candidate of candidates) {
    for (const field of [
      "firstContentfulPaintMs",
      "firstRowMs",
      "domContentLoadedMs",
      "sourcePaintedMs",
    ]) {
      const ratios = [];
      const loads = [];
      for (let pair = 0; pair < options.pairs; pair += 1) {
        const a = records.find((record) => record.pair === pair && record.build === control);
        const b = records.find((record) => record.pair === pair && record.build === candidate);
        if (a?.complete && b?.complete && timing(a, field) && timing(b, field)) {
          ratios.push(timing(b, field) / timing(a, field));
          loads.push(a.load1, b.load1);
        }
      }
      if (ratios.length) {
        console.log(
          `${candidate}/${control} ${field}: median ratio ${median(ratios).toFixed(3)}, ` +
            `pairs ${Math.min(...ratios).toFixed(2)}-${Math.max(...ratios).toFixed(2)}, ` +
            `load ${Math.min(...loads).toFixed(0)}-${Math.max(...loads).toFixed(0)}`,
        );
      }
    }
  }
}

const options = parseArgs(process.argv.slice(2));
const browser = await Browser.launch();
const records = [];
try {
  // One discarded load per build: the first after launch pays for process start.
  for (const [name, origin] of options.builds) {
    await loadOnce(browser, name, origin, options);
  }
  for (let pair = 0; pair < options.pairs; pair += 1) {
    for (const [name, origin] of options.builds) {
      const record = {
        pair,
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
summarize(records, options.builds, options);
