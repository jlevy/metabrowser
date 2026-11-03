// exp-041, adapted from review E of #284: one measured run of a pull request's Files changed in visible Chrome.
//
// PR_PERF_ROOT=... node pr-page.mjs --build new|old|github --pr URL --number N --files N --scenario load|back|click|jumps
//   [--port P] [--label L] [--out file.jsonl] [--keep-server]
// --keep-server retains the owned server even on failure; its log is ROOT/server-<recorder pid>.log.
//
// Fresh server (metab) and fresh Chrome profile per run. Stamps are performance.now() from the
// navigation start; "painted" is the second animation frame after the element first appeared.
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { CHROME, Connection, sleep } from "./pr-cdp.mjs";

// Final paired recorder: installed frozen wheels, shared public Git cache, fresh process/profile.
// First-screen fill uses native IntersectionObserver membership and DOM-only checks.
const R = process.env.PR_PERF_ROOT;
if (!R) {
  throw new Error("Set PR_PERF_ROOT to the prepared external measurement directory");
}
const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith("--")) {
    const next = process.argv[i + 1];
    if (next !== undefined && !next.startsWith("--")) {
      args[a.slice(2)] = next;
      i++;
    } else {
      args[a.slice(2)] = "1";
    }
  }
}
const build = args.build;
const scenario = args.scenario ?? "load";
const filesExpected = Number(args.files ?? 0);
const port = Number(args.port ?? 9411);
const loadavg = () =>
  execFileSync("/usr/sbin/sysctl", ["-n", "vm.loadavg"])
    .toString()
    .replace(/[{}]/g, "")
    .trim()
    .split(/\s+/)
    .map(Number);
const result = {
  recorder_revision: "actual-rows-v2",
  label: args.label ?? "",
  build,
  scenario,
  pr: args.pr,
  started: new Date().toISOString(),
  load_start: loadavg(),
};

// ── server ────────────────────────────────────────────
let server = null;
async function startServer() {
  const cache = `${R}/public-cache`;
  const cfg = `${R}/cfg`;
  fs.mkdirSync(cfg, { recursive: true, mode: 0o700 });
  fs.mkdirSync(cache, { recursive: true, mode: 0o700 });
  const t0 = Date.now();
  const target = args.folder ?? args.pr;
  // A retained server must own its log descriptor: pipes close when this recorder exits.
  const logPath = path.join(R, `server-${process.pid}.log`);
  const logFd = args["keep-server"] ? fs.openSync(logPath, "w", 0o600) : null;
  try {
    server = spawn(
      R + (build === "new" ? "/candidate-venv/bin/metab" : "/baseline-venv/bin/metab"),
      [target, "--no-open", "--port", String(port), "--cache-dir", cache, "--config-dir", cfg],
      {
        cwd: R,
        detached: true,
        stdio: ["ignore", logFd ?? "pipe", logFd ?? "pipe"],
        env: { ...process.env, METABROWSER_CACHE_DIR: cache, METABROWSER_CONFIG_DIR: cfg },
      },
    );
  } finally {
    if (logFd !== null) {
      fs.closeSync(logFd);
    }
  }
  let log = "";
  server.stdout?.on("data", (d) => (log += d));
  server.stderr?.on("data", (d) => (log += d));
  const serverLog = () => (logFd === null ? log : fs.readFileSync(logPath, "utf8"));
  result.serverLog = serverLog;
  if (logFd !== null) {
    result.retained_server = { pid: server.pid, log: path.basename(logPath) };
  }
  let ready = false;
  for (let i = 0; i < 600; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/api/tree?depth=1`);
      if (r.ok) {
        ready = true;
        break;
      }
    } catch {}
    if (server.exitCode !== null) {
      throw new Error(`server exited: ${serverLog().slice(-2000)}`);
    }
    await sleep(100);
  }
  if (!ready) {
    throw new Error(`server did not become ready: ${serverLog().slice(-2000)}`);
  }
  result.server_ready_ms = Date.now() - t0;
  // E1: --warm QUERY asks the comparison route for one file first, which computes and keeps the
  // comparison's manifest and nothing of the page's own answer: what a server that computed the
  // manifest before the reader asked (review E's E3) would hold. A projection, not this build.
  if (args.warm) {
    const w0 = Date.now();
    const answer = await fetch(`http://127.0.0.1:${port}/api/plugin/diff/comparison?${args.warm}`);
    await answer.arrayBuffer();
    result.warm = { status: answer.status, ms: Date.now() - w0 };
  }
}
function stopServer() {
  if (!server) {
    return;
  }
  try {
    process.kill(-server.pid, "SIGTERM");
  } catch {}
}
function serverRss() {
  try {
    const out = execFileSync("ps", ["-axo", "pid=,ppid=,rss=,command="]).toString();
    const rows = out.split("\n").map((l) => l.trim().split(/\s+/));
    // the python child of uv
    const kids = rows.filter((r) => Number(r[1]) === server.pid);
    return kids.map((r) => Number(r[2]) * 1024);
  } catch {
    return null;
  }
}

// ── chrome, visible ───────────────────────────────────
const FLAGS = [
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
  "--window-position=40,40",
  "--disable-features=Translate,OptimizationHints,MediaRouter,InterestFeedContentSuggestions",
];
let chrome = null;
let chromeConnection = null;
const profile = `${R}/prof-${process.pid}`;
async function launchChrome() {
  fs.rmSync(profile, { recursive: true, force: true });
  fs.mkdirSync(profile, { recursive: true });
  const extra =
    build === "github"
      ? []
      : ["--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost"];
  chrome = spawn(CHROME, [...FLAGS, ...extra, `--user-data-dir=${profile}`, "about:blank"], {
    stdio: ["ignore", "ignore", "pipe"],
  });
  chrome.stderr.on("data", () => {});
  const portFile = path.join(profile, "DevToolsActivePort");
  let ws = null;
  for (let i = 0; i < 300 && !ws; i++) {
    if (fs.existsSync(portFile)) {
      const [p, wsPath] = fs.readFileSync(portFile, "utf8").trim().split("\n");
      if (p && wsPath) {
        ws = `ws://127.0.0.1:${p}${wsPath}`;
      }
    }
    if (!ws) {
      await sleep(100);
    }
  }
  if (ws === null) {
    throw new Error("Chrome did not expose a DevTools endpoint");
  }
  chromeConnection = new Connection(ws);
  await chromeConnection.open();
  execFileSync("osascript", ["-e", 'tell application "Google Chrome" to activate']);
  return chromeConnection;
}
async function closeChrome() {
  try {
    if (chromeConnection !== null) {
      await Promise.race([chromeConnection.send("Browser.close"), sleep(3000)]);
    }
  } catch {}
  chromeConnection?.close();
  if (chrome !== null) {
    for (let i = 0; i < 50 && chrome.exitCode === null && chrome.signalCode === null; i++) {
      await sleep(100);
    }
    if (chrome.exitCode === null && chrome.signalCode === null) {
      chrome.kill("SIGKILL");
    }
  }
  try {
    const out = execFileSync("ps", ["-axo", "pid=,command="]).toString();
    for (const l of out.split("\n")) {
      if (l.includes(`--user-data-dir=${profile}`)) {
        process.kill(Number(l.trim().split(/\s+/)[0]), "SIGKILL");
      }
    }
  } catch {}
  await sleep(300);
  fs.rmSync(profile, { recursive: true, force: true });
}

// ── recorder, injected before any page script ──────────
const RECORDER = `(() => {
  const T = { marks: {}, painted: {}, longtasks: [], lcp: 0, cls: 0, expected: ${filesExpected}, site: ${JSON.stringify(build === "github" ? "github" : "metab")} };
  window.__rec = T;
  const now = () => performance.now();
  // E1: what the first screen shows when the first line paints: files on screen with rows, and
  // files on screen still holding reserved space (a held or deferred body with no rows yet).
  const screenState = () => {
    const out = { drawn: 0, waiting: 0 };
    for (const s of document.querySelectorAll(".diff-file")) {
      const r = s.getBoundingClientRect();
      if (r.bottom <= 0 || r.top >= innerHeight) continue;
      if (s.querySelector(".diff-line-text, .diff-split-row")) out.drawn += 1;
      else if (s.querySelector(".diff-file-body")?.style.minHeight || s.querySelector(".diff-file-body")?.style.getPropertyValue("--diff-reserved-height")) out.waiting += 1;
    }
    return out;
  };
  T.screenState = screenState;
  const paint = (name, t) => {
    if (T.marks[name] !== undefined) return;
    T.marks[name] = t ?? now();
    requestAnimationFrame(() => requestAnimationFrame(() => {
      T.painted[name] = now();
      if (name === "firstLine" && T.site !== "github") T.firstScreen = screenState();
    }));
  };
  T.paint = paint;
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) T.longtasks.push([Math.round(e.startTime), Math.round(e.duration)]); }).observe({ type: "longtask", buffered: true }); } catch {}
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) T.lcp = e.startTime; }).observe({ type: "largest-contentful-paint", buffered: true }); } catch {}
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) T.cls += e.value; }).observe({ type: "layout-shift", buffered: true }); } catch {}
  const sel = T.site === "github"
    ? { title: ".gh-header-title, h1, [data-testid=issue-title], .markdown-title", bar: ".file-header", line: ".blob-code-inner" }
    : { title: ".github-pull-title", bar: ".diff-file-bar", line: ".diff-line-text, .diff-split-row" };
  T.sel = sel;
  let fillObserver = null;
  const visible = new Set();
  const fillCheck = () => {
    if (T.marks.firstViewportFilled !== undefined || T.marks.firstLine === undefined || !visible.size) return;
    let drawn = 0;
    for (const section of visible) {
      const body = section.querySelector(".diff-file-body");
      const rows = section.querySelector(".diff-line-text, .diff-split-row");
      if (rows) drawn++;
      else if (body && (body.style.minHeight || body.style.getPropertyValue("--diff-reserved-height")) && !section.classList.contains("is-collapsed")) return;
    }
    if (!drawn) return;
    paint("firstViewportFilled");
    fillObserver?.disconnect();
  };
  const startFill = () => {
    if (fillObserver || T.marks.firstViewportFilled !== undefined || T.site === "github") return;
    const root = document.querySelector(".diff-root:not([data-old])");
    const pane = root?.closest("[data-kpress-viewport]");
    if (!root || !pane || !root.querySelector(".diff-file")) return;
    fillObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) visible.add(entry.target);
        else visible.delete(entry.target);
      }
      fillCheck();
    }, { root: pane });
    for (const section of root.querySelectorAll(".diff-file")) fillObserver.observe(section);
  };
  let bars = null;
  T.check = () => {
    const t = now();
    if (T.marks.title === undefined && document.querySelector(sel.title)) paint("title", t);
    if (T.marks.firstBar === undefined && document.querySelector(sel.bar)) paint("firstBar", t);
    if (T.marks.firstLine === undefined && document.querySelector(sel.line)) paint("firstLine", t);
    if (T.marks.summary === undefined && document.querySelector(".diff-summary, #files_bucket .toc-diff-stats, .diffbar")) paint("summary", t);
    if (T.marks.allBars === undefined && T.expected > 0 && T.marks.firstBar !== undefined) {
      const n = document.querySelectorAll(sel.bar).length;
      T.maxBars = Math.max(T.maxBars ?? 0, n);
      if (n >= T.expected) paint("allBars", t);
    }
  };
  const probeCss = ${JSON.stringify(args.css ?? "")};
  let styled = !probeCss;
  new MutationObserver(() => {
    if (!styled && document.head) { const s = document.createElement("style"); s.textContent = probeCss; document.head.append(s); styled = true; }
    T.check(); startFill(); fillCheck();
  }).observe(document, { childList: true, subtree: true });
})();`;

async function evaluate(page, expr, awaitPromise = true) {
  const r = await page.send(
    "Runtime.evaluate",
    { expression: expr, awaitPromise, returnByValue: true },
    120000,
  );
  if (r.exceptionDetails) {
    throw new Error(`eval failed: ${JSON.stringify(r.exceptionDetails).slice(0, 500)}`);
  }
  return r.result.value;
}

async function main() {
  try {
    if (build !== "github") {
      await startServer();
    }
    const conn = await launchChrome();
    await measure(conn);
  } finally {
    try {
      await closeChrome();
    } finally {
      if (args["keep-server"]) {
        server?.unref();
      } else {
        stopServer();
      }
    }
  }
  delete result.serverLog;
  const line = JSON.stringify(result);
  if (args.out) {
    fs.appendFileSync(args.out, `${line}\n`);
  }
  console.log(line);
}

async function measure(conn) {
  const isGithub = build === "github";
  const targets = await conn.send("Target.getTargets");
  const t = targets.targetInfos.find((x) => x.type === "page");
  const { sessionId } = await conn.send("Target.attachToTarget", {
    targetId: t.targetId,
    flatten: true,
  });
  const page = conn.adopt(sessionId, t.targetId);
  await page.send("Page.enable");
  await page.send("Network.enable");
  await page.send("Runtime.enable");
  result.page_exceptions = [];
  page.on("Runtime.exceptionThrown", (event) =>
    result.page_exceptions.push(event.exceptionDetails.text),
  );
  await page.send("Page.bringToFront");
  await page.send("Page.addScriptToEvaluateOnNewDocument", { source: RECORDER });
  // request bookkeeping
  const reqs = new Map();
  const _navT0 = { wall: 0 };
  page.on("Network.requestWillBeSent", (p) => {
    reqs.set(p.requestId, { url: p.request.url, start: p.timestamp, type: p.type });
  });
  page.on("Network.responseReceived", (p) => {
    const r = reqs.get(p.requestId);
    if (r) {
      r.status = p.response.status;
      r.fromCache = p.response.fromDiskCache || p.response.fromPrefetchCache || false;
      r.serverTiming =
        p.response.headers?.["server-timing"] ?? p.response.headers?.["Server-Timing"];
      r.cacheControl =
        p.response.headers?.["cache-control"] ?? p.response.headers?.["Cache-Control"];
    }
  });
  page.on("Network.loadingFinished", (p) => {
    const r = reqs.get(p.requestId);
    if (r) {
      r.end = p.timestamp;
      r.encoded = p.encodedDataLength;
    }
  });
  page.on("Network.requestServedFromCache", (p) => {
    const r = reqs.get(p.requestId);
    if (r) {
      r.memoryCache = true;
    }
  });

  const base = isGithub ? args.pr : `http://127.0.0.1:${port}`;
  const number = args.number;
  const filesUrl = isGithub
    ? `${args.pr}/files`
    : args.urlpath
      ? `${base}${args.urlpath}`
      : `${base}/pull/${number}/files`;
  const convUrl = isGithub ? args.pr : `${base}/pull/${number}`;

  const waitSettled = async (key, timeoutMs, quietMs = 600) => {
    const deadline = Date.now() + timeoutMs;
    let last = -1;
    let lastChange = Date.now();
    while (Date.now() < deadline) {
      const st = await evaluate(
        page,
        `(() => { const T = window.__rec; T && T.check(); return T ? JSON.stringify({ m: T.marks, p: T.painted, lt: T.longtasks.length }) : null; })()`,
        false,
      );
      if (st) {
        const s = JSON.parse(st);
        const done = key.every((k) => s.p[k] !== undefined);
        if (s.lt !== last) {
          last = s.lt;
          lastChange = Date.now();
        }
        if (done && Date.now() - lastChange >= quietMs) {
          return true;
        }
      }
      await sleep(100);
    }
    return false;
  };

  const comparisonReqs = () =>
    [...reqs.values()].filter(
      (r) =>
        r.url.includes("/api/plugin/diff/comparison") ||
        r.url.includes("/api/plugin/github/pull-comparison"),
    );

  if (
    scenario === "load" ||
    scenario === "back" ||
    scenario === "jumps" ||
    scenario === "full" ||
    scenario === "hold"
  ) {
    await page.send("Page.navigate", { url: filesUrl });
    const keys = filesExpected > 0 ? ["firstLine", "allBars"] : ["firstLine"];
    result.settled = await waitSettled(keys, isGithub ? 60000 : 90000);
    const rec = JSON.parse(
      await evaluate(
        page,
        `JSON.stringify({ firstViewportFilled: __rec.painted.firstViewportFilled ?? null, firstScreen: __rec.firstScreen ?? null, drawnFiles: [...document.querySelectorAll(".diff-file")].filter((s) => s.querySelector(".diff-line-text, .diff-split-row")).length, marks: __rec.marks, painted: __rec.painted, longtasks: __rec.longtasks, lcp: __rec.lcp, cls: __rec.cls, maxBars: __rec.maxBars, vis: document.visibilityState, focus: document.hasFocus(), nodes: document.getElementsByTagName("*").length, bars: document.querySelectorAll(__rec.sel.bar).length, lines: document.querySelectorAll(__rec.sel.line).length, heap: performance.memory ? performance.memory.usedJSHeapSize : null, partial: document.querySelector(".diff-partial-note")?.textContent ?? null, nav: performance.getEntriesByType("navigation")[0]?.responseStart })`,
        false,
      ),
    );
    result.load = rec;
    const lts = rec.longtasks.filter(
      ([s]) => s <= (rec.painted.allBars ?? rec.painted.firstLine ?? 1e9) + 2000,
    );
    result.load_summary = {
      title: rec.painted.title,
      firstBar: rec.painted.firstBar,
      firstLine: rec.painted.firstLine,
      firstViewportFilled: rec.firstViewportFilled,
      allBars: rec.painted.allBars,
      longest_task: Math.max(0, ...lts.map(([, d]) => d)),
      long_tasks: lts.length,
      tbt: lts.reduce((a, [, d]) => a + Math.max(0, d - 50), 0),
      nodes: rec.nodes,
      firstScreen: rec.firstScreen,
      drawnFiles: rec.drawnFiles,
      bars: rec.bars,
      vis: rec.vis,
      focus: rec.focus,
      partial: rec.partial,
    };
    const cmp = comparisonReqs();
    result.comparison_requests = cmp.map((r) => ({
      url: r.url.replace(/^https?:\/\/[^/]+/, ""),
      ms: r.end && r.start ? Math.round((r.end - r.start) * 1000) : null,
      status: r.status,
      encoded: r.encoded,
      st: r.serverTiming,
      cc: r.cacheControl,
      cache: r.fromCache || r.memoryCache || false,
    }));
    result.requests = reqs.size;
    result.transferred = [...reqs.values()].reduce((a, r) => a + (r.encoded ?? 0), 0);
  }

  if (scenario === "back" || scenario === "full") {
    // Files changed -> Conversation by a trusted click on its tab, then Back.
    // E1: --scroll N first puts file N at the pane's top, 37 px into it, as a reader would
    // have scrolled there, so Back has a place deep in the page to restore.
    const placeExpr = `(() => { const pane = document.querySelector('.diff-root')?.closest('[data-kpress-viewport]'); if (!pane) return null; const top = pane.getBoundingClientRect().top; const sections = [...document.querySelectorAll('.diff-root:not([data-old]) .diff-file')]; const i = sections.findIndex((s) => s.getBoundingClientRect().bottom > top); return i < 0 ? null : { index: i, offset: Math.round(top - sections[i].getBoundingClientRect().top) }; })()`;
    let placeBefore = null;
    if (args.scroll) {
      await evaluate(
        page,
        `(() => { const s = document.querySelectorAll('.diff-file')[${Number(args.scroll)}]; const pane = s.closest('[data-kpress-viewport]'); pane.dispatchEvent(new WheelEvent('wheel', { bubbles: true })); pane.scrollTop += s.getBoundingClientRect().top - pane.getBoundingClientRect().top + 37; return true; })()`,
        false,
      );
      await sleep(2000);
      placeBefore = await evaluate(page, placeExpr, false);
    }
    if (args.scroll) {
      // The tabs are scrolled off the pane, so a click at their place would land in the diff:
      // go to Conversation through the page's handle, which moves the address as a click does.
      await evaluate(
        page,
        `(() => { window.metabrowser.debug.pullPage().setTab(""); return true; })()`,
        false,
      );
    } else {
      const tab = await evaluate(
        page,
        `(() => { const a = [...document.querySelectorAll('a[role=tab]')].find((x) => x.textContent.trim().startsWith('Conversation')); if (!a) return null; const r = a.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`,
        false,
      );
      await click(page, tab);
    }
    await sleep(600);
    const before = reqs.size;
    await evaluate(
      page,
      `(() => { for (const r of document.querySelectorAll('.diff-root')) r.dataset.old = '1'; const T = window.__rec; T.back0 = performance.now(); T.backLine = undefined; const complete = () => { const s = T.screenState(); if (s.waiting === 0 && s.drawn > 0) { T.backComplete = performance.now(); return; } if (performance.now() - T.back0 < 10000) requestAnimationFrame(complete); }; const obs = new MutationObserver(() => { if (T.backLine === undefined && document.querySelector('.diff-root:not([data-old]) .diff-line-text, .diff-root:not([data-old]) .diff-split-row')) { T.backLine = performance.now(); requestAnimationFrame(() => requestAnimationFrame(() => { T.backPainted = performance.now(); obs.disconnect(); complete(); })); } }); obs.observe(document, { childList: true, subtree: true }); window.__lt0 = T.longtasks.length; history.back(); return true; })()`,
      false,
    );
    for (let i = 0; i < 300; i++) {
      const v = await evaluate(page, `window.__rec.backPainted ?? null`, false);
      if (v !== null) {
        break;
      }
      await sleep(100);
    }
    await sleep(600);
    const b = JSON.parse(
      await evaluate(
        page,
        `JSON.stringify({ t0: __rec.back0, line: __rec.backLine, painted: __rec.backPainted, complete: __rec.backComplete ?? null, lts: __rec.longtasks.slice(window.__lt0), path: location.pathname, place: ${placeExpr} })`,
        false,
      ),
    );
    const after = [...reqs.values()]
      .slice(before)
      .filter(
        (r) =>
          r.url.includes("/api/plugin/diff/comparison") ||
          r.url.includes("/api/plugin/github/pull-comparison"),
      );
    result.back = {
      first_line_ms:
        b.painted !== undefined && b.painted !== null ? Math.round(b.painted - b.t0) : null,
      screen_complete_ms: b.complete === null ? null : Math.round(b.complete - b.t0),
      longest_task: Math.max(0, ...b.lts.map(([, d]) => d)),
      path: b.path,
      place_before: placeBefore,
      place_after: b.place,
      comparison_requests_after: after.map((r) => ({
        status: r.status,
        cache: r.fromCache || r.memoryCache || false,
        ms: r.end ? Math.round((r.end - r.start) * 1000) : null,
      })),
    };
  }

  if (scenario === "click" || scenario === "full") {
    await page.send("Page.navigate", { url: convUrl });
    await waitSettled(["title"], 30000, 700);
    await sleep(500);
    const before = reqs.size;
    const tab = await evaluate(
      page,
      `(() => { const a = [...document.querySelectorAll('a[role=tab]')].find((x) => x.textContent.trim().startsWith('Files')); if (!a) return null; const r = a.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`,
      false,
    );
    await evaluate(
      page,
      `(() => { const T = window.__rec; T.click0 = null; window.addEventListener('pointerdown', () => { T.click0 = performance.now(); }, { capture: true, once: true }); const obs = new MutationObserver(() => { if (T.click0 !== null && T.clickLine === undefined && document.querySelector('.diff-line-text, .diff-split-row')) { T.clickLine = performance.now(); requestAnimationFrame(() => requestAnimationFrame(() => { T.clickPainted = performance.now(); obs.disconnect(); })); } }); obs.observe(document, { childList: true, subtree: true }); window.__lt0 = T.longtasks.length; return true; })()`,
      false,
    );
    await click(page, tab);
    for (let i = 0; i < 300; i++) {
      const v = await evaluate(page, `window.__rec.clickPainted ?? null`, false);
      if (v !== null) {
        break;
      }
      await sleep(100);
    }
    await sleep(600);
    const c = JSON.parse(
      await evaluate(
        page,
        `JSON.stringify({ t0: __rec.click0, painted: __rec.clickPainted, lts: __rec.longtasks.slice(window.__lt0), vis: document.visibilityState })`,
        false,
      ),
    );
    const after = [...reqs.values()]
      .slice(before)
      .filter(
        (r) =>
          r.url.includes("/api/plugin/diff/comparison") ||
          r.url.includes("/api/plugin/github/pull-comparison"),
      );
    const all = comparisonReqs();
    result.click = {
      first_line_ms: c.painted ? Math.round(c.painted - c.t0) : null,
      longest_task: Math.max(0, ...c.lts.map(([, d]) => d)),
      vis: c.vis,
      comparison_requests_after_click: after.length,
      comparison_requests_total: all.length,
    };
  }

  if (scenario === "jumps" || scenario === "full" || scenario === "hold") {
    result.jumps = await runJumps(page, reqs);
  }

  if (!isGithub) {
    result.rss = serverRss();
  }
  result.load_end = loadavg();
}

async function click(page, xy) {
  if (!xy) {
    throw new Error("no target to click");
  }
  const [x, y] = xy;
  await page.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  await page.send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    x,
    y,
    button: "left",
    clickCount: 1,
  });
  await page.send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    x,
    y,
    button: "left",
    clickCount: 1,
  });
}

// Jumps through the page's own handle, as a list would call it.
async function runJumps(page, reqs) {
  const out = {};
  const has = await evaluate(
    page,
    `typeof window.metabrowser?.debug?.pullPage?.()?.scrollToFile === "function"`,
    false,
  );
  out.api = has;
  const paths = JSON.parse(
    await evaluate(
      page,
      `JSON.stringify([...document.querySelectorAll('.diff-file')].map((s) => s.querySelector('.diff-file-path')?.textContent ?? ''))`,
      false,
    ),
  );
  out.files = paths.length;
  const fileReqs = () =>
    [...reqs.values()].filter(
      (r) =>
        (r.url.includes("/api/plugin/diff/comparison") ||
          r.url.includes("/api/plugin/github/pull-comparison")) &&
        r.url.includes("file="),
    );
  const one = async (index) => {
    const before = fileReqs().length;
    const expr = `(async () => {
      const sections = [...document.querySelectorAll('.diff-file')];
      const section = sections[${index}];
      const lines = () => section.querySelector('.diff-line-text, .diff-split-row');
      const hadLines = !!lines();
      const lt0 = __rec.longtasks.length;
      const t0 = performance.now();
      let answer = null;
      const page = window.metabrowser?.debug?.pullPage?.();
      if (page && typeof page.scrollToFile === 'function') {
        const path = (section.querySelector('.diff-file-path')?.textContent ?? '').split(' → ').pop();
        answer = page.scrollToFile(path);
      } else {
        section.scrollIntoView();
      }
      const bar = section.querySelector('.diff-file-bar');
      const onScreen = () => { const r = bar.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; };
      let barT = null, linesT = null;
      await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
      if (onScreen()) barT = performance.now() - t0;
      const deadline = t0 + 20000;
      while (linesT === null && performance.now() < deadline) {
        if (lines()) { await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res))); linesT = performance.now() - t0; break; }
        await new Promise((res) => setTimeout(res, 5));
      }
      const top0 = bar.getBoundingClientRect().top;
      let maxDrift = 0;
      for (let i = 0; i < 20; i++) { await new Promise((res) => setTimeout(res, 50)); maxDrift = Math.max(maxDrift, Math.abs(bar.getBoundingClientRect().top - top0)); }
      return JSON.stringify({ index: ${index}, kind: answer?.kind ?? null, availability: answer?.availability ?? null, hadLines, bar: barT, lines: linesT, top0, maxDrift, lts: __rec.longtasks.slice(lt0).map(([, d]) => d) });
    })()`;
    const r = JSON.parse(await evaluate(page, expr));
    r.requests = fileReqs().length - before;
    return r;
  };
  const n = paths.length;
  if (scenario !== "hold") {
    out.hydrated = await one(7);
    await sleep(100);
    out.deferred = await one(Math.floor(n / 2));
    await sleep(100);
    out.deferred2 = await one(Math.floor(n * 0.3));
    await sleep(100);
    out.last = await one(n - 1);
    await sleep(100);
  }
  // held key: 90 steps at 33 ms from a deferred file
  const start = Math.floor(n * 0.6);
  const before = fileReqs().length;
  await evaluate(
    page,
    `(() => {
    const sections = [...document.querySelectorAll('.diff-file')];
    const handle = window.metabrowser.debug.pullPage();
    const state = window.__trustedHold = { stamps: [], delays: [], trusted: [], lt0: __rec.longtasks.length, up: null };
    state.down = (event) => {
      if (event.key !== 'ArrowDown' || state.stamps.length >= 90) return;
      event.preventDefault();
      const index = ${start} + state.stamps.length;
      if (index >= sections.length) return;
      const now = performance.now();
      state.stamps.push(now); state.delays.push(now - event.timeStamp); state.trusted.push(event.isTrusted);
      const path = (sections[index].querySelector('.diff-file-path')?.textContent ?? '').split(' → ').pop();
      handle.scrollToFile(path);
    };
    state.upHandler = (event) => { if (event.key === 'ArrowDown') state.up = performance.now(); };
    document.addEventListener('keydown', state.down, true);
    document.addEventListener('keyup', state.upHandler, true);
    return true;
  })()`,
    false,
  );
  const hostStarted = Date.now();
  for (let index = 0; index < Math.min(90, n - start); index++) {
    await sleep(Math.max(0, hostStarted + index * 33 - Date.now()));
    await page.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "ArrowDown",
      code: "ArrowDown",
      windowsVirtualKeyCode: 40,
      autoRepeat: index > 0,
    });
  }
  await page.send("Input.dispatchKeyEvent", {
    type: "keyUp",
    key: "ArrowDown",
    code: "ArrowDown",
    windowsVirtualKeyCode: 40,
  });
  const inflightAtKeyup = fileReqs()
    .slice(before)
    .filter((r) => r.end === undefined).length;
  const requestsAtKeyup = fileReqs().length - before;
  const held = JSON.parse(
    await evaluate(
      page,
      `(async () => {
    const state = window.__trustedHold;
    document.removeEventListener('keydown', state.down, true);
    document.removeEventListener('keyup', state.upHandler, true);
    const sections = [...document.querySelectorAll('.diff-file')];
    const last = sections[Math.min(sections.length - 1, ${start} + state.stamps.length - 1)];
    let rest = null;
    while (performance.now() - state.up < 20000) {
      if (last.querySelector('.diff-line-text, .diff-split-row, .diff-availability')) {
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        rest = performance.now() - state.up; break;
      }
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
    const sectionRest = rest;
    let rowsRest = last.querySelector('.diff-line-text, .diff-split-row') ? rest : null;
    while (rowsRest === null && performance.now() - state.up < 20000) {
      if (last.querySelector('.diff-line-text, .diff-split-row')) {
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        rowsRest = performance.now() - state.up; break;
      }
      await new Promise((resolve) => setTimeout(resolve, 5));
    }
    const gaps = state.stamps.slice(1).map((stamp, index) => stamp - state.stamps[index]).sort((a,b) => a-b);
    const delays = state.delays.sort((a,b) => a-b);
    return JSON.stringify({ steps: state.stamps.length, trusted: state.trusted.every(Boolean), step_median: gaps[Math.floor(gaps.length/2)], step_p95: gaps[Math.floor(gaps.length*.95)], input_delay_p95: delays[Math.floor(delays.length*.95)], resting_section_after_keyup: sectionRest, resting_lines_after_keyup: rowsRest, lts: __rec.longtasks.slice(state.lt0).map(([,d])=>d) });
  })()`,
    ),
  );
  held.requests_at_keyup = requestsAtKeyup;
  held.in_flight_at_keyup = inflightAtKeyup;
  held.requests = fileReqs().length - before;
  const inflight = fileReqs()
    .slice(before)
    .filter((r) => r.end === undefined && r.status === undefined).length;
  held.in_flight_at_end = inflight;
  await sleep(600);
  held.requests_after_settle = fileReqs().length - before;
  out.held = held;
  return out;
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
