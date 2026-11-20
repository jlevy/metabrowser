// Browserless session: what a page tells the event log it saw, and the Details it offers.
//
// The owner asked, 2026-11-19, that a Diff summary still loading "after many seconds" be
// captured, surfaced, and easy to debug (mb-9zp5). static/event-reports.js is the page's
// side: it names each request it sends to /api/ with the page's client ID, notices
// requests slower than `slow_ms` and those still pending at it, freezes of `freeze_ms` or
// more, and waits still running at `late_ms`, and sends them in batches to
// POST /api/event-log/client. Its Details panel reads the event log back.
//
// This runs the production file whole, as the shell loads it, with the clock, timers,
// fetch, and paint injected, and tells each step: what the reporter queued and what it
// sent. The settings are the server's (event_log_reports.browser_settings, with a log
// open); tests/test_event_reports_session.py fails when they differ, checks that every
// body sent here is one the route accepts whole, and runs `--describe` on the answers the
// routes give for a job that never ends, so the Details are read from real answers too.
//
//   node tests/dom/event-reports-session.js                  the story, as JSON
//   node tests/dom/event-reports-session.js --bodies FILE    and the bodies it sent, to FILE
//   node tests/dom/event-reports-session.js --describe FILE  the Details of {failures, page, client}

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sourcePath = path.resolve(__dirname, "../../src/metabrowser/static/event-reports.js");
const source = fs.readFileSync(sourcePath, "utf8");

const PAGE = "k3v9q2zx";
const ORIGIN = "http://localhost:8411";
// event_log_reports.browser_settings(long_lived=server.LONG_LIVED_PATHS) with a log open.
const SETTINGS = Object.freeze({
  log: true,
  off_reason: null,
  route: "/api/event-log/client",
  header: "x-metabrowser-client",
  slow_ms: 2000,
  freeze_ms: 500,
  late_ms: 10000,
  flush_ms: 1000,
  max_batch: 20,
  per_minute: 30,
  long_lived: ["/api/events", "/api/tail", "/api/stream"],
  failure_window_s: 3600,
});

/** A node, enough of one for the Details panel's paint. */
class Node {
  constructor(tag) {
    this.tag = tag;
    this.className = "";
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  append(...nodes) {
    this.children.push(...nodes);
  }
  replaceChildren(...nodes) {
    this.children = [...nodes];
  }
  get textContent() {
    return this.children
      .map((node) => (typeof node === "string" ? node : node.textContent))
      .join("");
  }
  /** The panel as lines: each part's heading, its items indented, and the links. */
  outline() {
    const lines = [];
    for (const node of this.children) {
      if (typeof node === "string") {
        continue;
      }
      if (node.className === "event-log-details-part") {
        for (const child of node.children) {
          if (child.className === "event-log-details-heading") {
            lines.push(child.textContent);
          } else {
            lines.push(...child.children.map((item) => `  ${item.textContent}`));
          }
        }
      } else if (node.className === "event-log-details-links") {
        const links = node.children.filter((child) => typeof child !== "string");
        lines.push(
          `links: ${links
            .map(
              (link) =>
                `${link.textContent} -> ${link.getAttribute("href")} (${link.getAttribute("target")}, ${link.getAttribute("rel")})`,
            )
            .join("; ")}`,
        );
      } else {
        lines.push(`${node.className}: ${node.textContent}`);
      }
    }
    return lines;
  }
}

/** A fresh context with the production file loaded; *globals* are the page's. */
function load(globals = {}) {
  const context = {
    AbortController,
    Array,
    Date,
    Headers,
    JSON,
    Map,
    Math,
    Number,
    Object,
    Promise,
    Set,
    String,
    URL,
    URLSearchParams,
    console,
    crypto: globalThis.crypto,
    document: { createElement: (tag) => new Node(tag), addEventListener() {} },
    ...globals,
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(source, context, { filename: sourcePath });
  return context;
}

/** A clock and the timers it runs, in the order they are due. */
function clock() {
  let now = 0;
  let next = 1;
  const timers = new Map();
  return {
    now: () => now,
    setTimeout(callback, ms) {
      const id = next;
      next += 1;
      timers.set(id, { at: now + ms, callback });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    /** Run the clock *ms* forward, and each timer due on the way. */
    advance(ms) {
      const end = now + ms;
      for (;;) {
        let due = null;
        for (const [id, timer] of timers) {
          if (timer.at <= end && (due === null || timer.at < due[1].at)) {
            due = [id, timer];
          }
        }
        if (due === null) {
          break;
        }
        timers.delete(due[0]);
        now = Math.max(now, due[1].at);
        due[1].callback();
      }
      now = end;
    },
    timers: () => timers.size,
  };
}

/** One report, as a line. */
function line(report) {
  const parts = [report.type, report.event, report.name, report.client, `${report.dur_ms} ms`];
  if (report.outcome !== undefined) {
    parts.push(report.outcome);
  }
  if (report.attrs !== undefined && Object.keys(report.attrs).length > 0) {
    parts.push(JSON.stringify(report.attrs));
  }
  return parts.join(" ");
}

/** The reporter with everything injected, and what it sent; *env* adds to what it is given. */
function reporterFor(api, settings = SETTINGS, env = {}) {
  const time = clock();
  const sent = [];
  const reporter = api.createReporter({
    ...env,
    settings,
    pageId: PAGE,
    origin: ORIGIN,
    path: () => "/pull/7",
    now: time.now,
    setTimeout: time.setTimeout,
    clearTimeout: time.clearTimeout,
    send: (route, body) => {
      sent.push({ route, at: time.now(), body: JSON.parse(body) });
      return Promise.resolve();
    },
    warn: () => {},
  });
  return { reporter, time, sent };
}

/** What was sent since *from*: each body's moment, size, and reports. */
function sentSince(sent, from) {
  return sent.slice(from).map(({ route, at, body }) => ({
    to: route,
    at_ms: at,
    page: body.page,
    path: body.path,
    dropped: body.dropped,
    reports: body.reports.map(line),
  }));
}

async function story() {
  const api = load().MetabrowserEventReports;
  const told = {};
  const bodies = [];
  const keep = (sent) => {
    bodies.push(...sent.map(({ body }) => body));
  };

  // ── Which requests carry the page's ID ───────────────────────────────
  {
    const { reporter } = reporterFor(api);
    const tags = {};
    for (const [label, url, method] of [
      ["a read of a pull request", "/api/plugin/github/pull?number=7", "get"],
      ["a refresh it asks for", `${ORIGIN}/api/plugin/github/pull-refresh`, "POST"],
      ["a static asset", "/static/app.js", "GET"],
      ["another origin", "https://api.github.com/api/x", "GET"],
      ["the server's event stream", "/api/events?topic=x", "GET"],
      ["a live tail", "/api/tail?path=a.log", "GET"],
      ["the reports themselves", "/api/event-log/client", "POST"],
    ]) {
      const tag = reporter.tag(url, method);
      tags[label] = tag === null ? "untagged" : `${tag.id} ${tag.name}`;
    }
    const off = reporterFor(api, { ...SETTINGS, log: false }).reporter;
    tags["with no log on the server"] =
      off.tag("/api/plugin/github/pull?number=7", "GET") === null ? "untagged" : "tagged";
    told.tags = tags;
  }

  // ── The header on the request, and nothing else changed ──────────────
  {
    const { reporter, time } = reporterFor(api);
    const calls = [];
    const fetchImpl = (input, init) => {
      calls.push({ input, init });
      return Promise.resolve({ status: 200, headers: { get: () => null } });
    };
    const wrapped = api.wrapFetch(fetchImpl, reporter);
    const init = { headers: { accept: "application/json" } };
    await wrapped("/api/plugin/github/pull?number=7", init);
    await wrapped("/static/app.js", init);
    await wrapped("/api/tree", { mode: "no-cors" });
    time.advance(SETTINGS.flush_ms);
    const [tagged, untagged, opaque] = calls;
    told.wrapFetch = {
      "a tagged request's headers": Object.fromEntries(tagged.init.headers.entries()),
      "a tagged request's init is a copy": tagged.init !== init,
      "an untagged request's init is the caller's": untagged.init === init,
      "a no-cors request is untagged": opaque.init.headers === undefined,
      "a fast answer queues nothing": reporter.queued().length,
    };
  }

  // ── Requests: fast, slow, pending, failed ────────────────────────────
  {
    const { reporter, time, sent } = reporterFor(api);
    const steps = [];
    const step = (label) => {
      steps.push({ step: label, queued: reporter.queued().map(line), timers: time.timers() });
    };
    const fast = reporter.tag("/api/tree", "GET");
    reporter.started(fast);
    time.advance(150);
    reporter.settled(fast, { status: 200, serverTiming: "srv;dur=120.4" });
    step("a request answered in 150 ms");
    const slow = reporter.tag("/api/plugin/github/pull-files-summary", "GET");
    reporter.started(slow);
    time.advance(1999);
    step("a request 1999 ms on its way");
    time.advance(1);
    step("the same at 2000 ms: still pending, reported open");
    time.advance(500);
    reporter.settled(slow, { status: 200, serverTiming: "cache;desc=hit, srv;dur=2301.24" });
    step("it answers at 2500 ms, with its Server-Timing");
    time.advance(SETTINGS.flush_ms);
    step("a second later, the batch sent");
    for (const [label, result] of [
      ["one that failed on the network", { error: { name: "TypeError" } }],
      ["one the page aborted", { error: { name: "AbortError" } }],
      ["one the server answered 503", { status: 503 }],
      ["one the server answered 404", { status: 404 }],
    ]) {
      const request = reporter.tag("/api/plugin/github/pull?number=7", "GET");
      reporter.started(request);
      time.advance(2600);
      reporter.settled(request, result);
      step(`${label}, after 2600 ms`);
    }
    const stuck = reporter.tag("/api/plugin/github/pull-comparison?number=7", "GET");
    reporter.started(stuck);
    time.advance(4000);
    const unreported = reporter.tag("/api/tree", "GET");
    reporter.started(unreported);
    time.advance(100);
    step("one pending 4.1 s, another 100 ms");
    reporter.leaving();
    step("the page is left: the one reported open never completed, the other is let go");
    keep(sent);
    told.requests = { steps, sent: sentSince(sent, 0) };
  }

  // ── Waits the page shows as loading ──────────────────────────────────
  {
    const { reporter, time, sent } = reporterFor(api);
    const steps = [];
    const lateCalls = [];
    const step = (label) => {
      steps.push({
        step: label,
        queued: reporter.queued().map(line),
        late_told: lateCalls.slice(),
      });
    };
    const quick = reporter.wait("githubPull:diffSummary", { detail: { number: 7 } });
    time.advance(9999);
    quick.end("ok");
    step("a wait that ends at 9999 ms");
    const slow = reporter.wait("githubPull:diffSummary", {
      detail: { number: 7 },
      onLate: (ms) => lateCalls.push(`told late at ${ms} ms`),
    });
    time.advance(10_000);
    step("a wait still running at 10 s");
    time.advance(2500);
    slow.end("ok");
    slow.end("failed");
    step("it ends at 12.5 s, and once only");
    // A wait the page began before the bundle loaded is timed from when it began.
    const begun = time.now() - 4000;
    const deferred = reporter.wait("source:refresh", { startedAt: begun });
    time.advance(5999);
    step("a wait begun 4 s before it was named, 5999 ms after");
    time.advance(1);
    step("6 s after it was named, 10 s after it began");
    const throwing = reporter.wait("githubPull:refresh", {
      onLate: () => {
        throw new Error("a handler that throws");
      },
    });
    time.advance(10_000);
    step("a wait whose late handler throws is still reported");
    reporter.leaving();
    step("the page is left: the late waits never completed");
    deferred.end("ok");
    throwing.end("ok");
    step("ending them after that reports nothing more");
    keep(sent);
    told.waits = { steps, sent: sentSince(sent, 0) };
  }

  // ── A page hidden while it waits ─────────────────────────────────────
  // The page stops polling while it is hidden, so a wait would run late for no fault of
  // the work behind it: its late timer stops while the page is hidden, and its reports
  // say how long it was (A3, review A of #629).
  {
    let hiddenNow = false;
    const { reporter, time, sent } = reporterFor(api, SETTINGS, { hidden: () => hiddenNow });
    const steps = [];
    const lateCalls = [];
    const step = (label) => {
      steps.push({
        step: label,
        queued: reporter.queued().map(line),
        late_told: lateCalls.slice(),
      });
    };
    const hide = (value) => {
      hiddenNow = value;
      reporter.visibility(value);
    };
    const tab = reporter.wait("githubPull:diffSummary", {
      detail: { number: 7 },
      onLate: (ms) => lateCalls.push(`told late at ${ms} ms`),
    });
    time.advance(4000);
    hide(true);
    time.advance(60_000);
    step("shown 4 s, then hidden a minute: not late");
    hide(false);
    time.advance(5999);
    step("shown again 5999 ms: 9999 ms shown in all");
    time.advance(1);
    step("10 s shown: late, with the minute it was hidden");
    time.advance(1000);
    tab.end("ok");
    step("it ends a second later");
    hide(true);
    const begunHidden = reporter.wait("source:refresh");
    time.advance(30_000);
    step("a wait begun while hidden, 30 s on: not late");
    hide(false);
    time.advance(SETTINGS.late_ms);
    step("shown for the late threshold: late");
    hide(true);
    time.advance(5000);
    reporter.leaving();
    begunHidden.end("ok");
    step("hidden 5 s more, then left: never completed, hidden 35 s");
    keep(sent);
    told.hiddenTab = { steps, sent: sentSince(sent, 0) };
  }

  // ── Frozen frames and requests from before the reporter ──────────────
  {
    const { reporter, time, sent } = reporterFor(api);
    reporter.blocked({ duration: 499, startTime: 100 });
    reporter.blocked({
      duration: 812.4,
      startTime: 4321.7,
      blockingDuration: 762.4,
      scripts: [
        { duration: 30, sourceFunctionName: "small", sourceURL: `${ORIGIN}/static/app.js` },
        {
          duration: 700,
          sourceFunctionName: "paintSummaryWait",
          sourceURL: `${ORIGIN}/static/plugins/github/pull-page.js?v=abc`,
          invoker: "TimerHandler:setTimeout",
        },
      ],
    });
    reporter.blocked({ duration: 650, startTime: 9000 });
    reporter.earlier([
      { name: `${ORIGIN}/api/tree?path=`, initiatorType: "fetch", duration: 120 },
      {
        name: `${ORIGIN}/api/plugin/github/pull?number=7`,
        initiatorType: "fetch",
        duration: 3210.55,
        responseStatus: 200,
        serverTiming: [{ name: "srv", duration: 3190.1 }],
      },
      { name: `${ORIGIN}/static/app.js`, initiatorType: "script", duration: 4000 },
      { name: "https://avatars.githubusercontent.com/u/1", initiatorType: "fetch", duration: 4000 },
      { name: `${ORIGIN}/api/events`, initiatorType: "fetch", duration: 60_000 },
      {
        name: `${ORIGIN}/api/plugin/github/pulls`,
        initiatorType: "xmlhttprequest",
        duration: 2000,
      },
    ]);
    time.advance(SETTINGS.flush_ms);
    keep(sent);
    told.blockedAndEarlier = sentSince(sent, 0);
  }

  // ── Batches and the page's own bound ─────────────────────────────────
  {
    const { reporter, time, sent } = reporterFor(api);
    const burst = (count) => {
      for (let index = 0; index < count; index += 1) {
        reporter.blocked({ duration: 600 + index, startTime: index });
      }
    };
    burst(25);
    const atOnce = sent.length;
    time.advance(SETTINGS.flush_ms);
    const afterFlush = sent.length;
    burst(10);
    time.advance(SETTINGS.flush_ms);
    const bodiesInMinute = sent.length;
    time.advance(60_000);
    burst(1);
    time.advance(SETTINGS.flush_ms);
    keep(sent);
    told.batches = {
      "25 reports at once: bodies sent before the flush": atOnce,
      "their sizes": sent.slice(0, afterFlush).map(({ body }) => body.reports.length),
      "10 more in the same minute: reports sent, and dropped": [
        sent
          .slice(afterFlush, bodiesInMinute)
          .reduce((sum, { body }) => sum + body.reports.length, 0),
        sent.slice(afterFlush, bodiesInMinute).reduce((sum, { body }) => sum + body.dropped, 0),
      ],
      "the next minute: reports sent": sent
        .slice(bodiesInMinute)
        .map(({ body }) => body.reports.length),
      "every body's largest size in bytes": Math.max(
        ...sent.map(({ body }) => JSON.stringify(body).length),
      ),
    };
  }

  // ── The shell's install: fetch, freezes, and leaving ─────────────────
  {
    const time = clock();
    const requests = [];
    const listeners = {};
    const observed = [];
    const context = load({
      METABROWSER_SETTINGS: { EVENT_REPORTS: SETTINGS },
      metabrowser: {},
      location: { origin: ORIGIN, pathname: "/pull/7" },
      fetch: (input, init) => {
        requests.push({ input, init });
        return Promise.resolve({ status: 200, headers: { get: () => null } });
      },
      performance: {
        now: time.now,
        getEntriesByType: (type) =>
          type === "resource"
            ? [{ name: `${ORIGIN}/api/tree?path=`, initiatorType: "fetch", duration: 2500 }]
            : [],
      },
      PerformanceObserver: Object.assign(
        class {
          constructor(callback) {
            this.callback = callback;
          }
          observe(options) {
            observed.push({ options, callback: this.callback });
          }
        },
        { supportedEntryTypes: ["longtask", "long-animation-frame"] },
      ),
      setTimeout: time.setTimeout,
      clearTimeout: time.clearTimeout,
      addEventListener: (type, callback) => {
        listeners[type] = callback;
      },
      document: {
        createElement: (tag) => new Node(tag),
        visibilityState: "visible",
        addEventListener: (type, callback) => {
          listeners[`document ${type}`] = callback;
        },
      },
    });
    const sdk = context.metabrowser.eventReports;
    const wrapped = context.window.fetch;
    await wrapped("/api/plugin/github/pull?number=7");
    const late = sdk.wait("githubPull:diffSummary", { detail: { number: 7 } });
    time.advance(SETTINGS.late_ms);
    observed[0].callback({ getEntries: () => [{ duration: 900, startTime: 50 }] });
    context.document.visibilityState = "hidden";
    listeners["document visibilitychange"]();
    const onHide = requests.filter(({ input }) => input === SETTINGS.route).length;
    // Into the back/forward cache: kept, not left, so the wait is not ended; restored, it
    // ends, and that is reported (A9, review A of #629).
    listeners.pagehide({ persisted: true });
    context.document.visibilityState = "visible";
    listeners["document visibilitychange"]();
    late.end("ok");
    // Unloaded: a wait still late is left, never completed.
    const left = sdk.wait("githubPull:refresh");
    time.advance(SETTINGS.late_ms);
    listeners.pagehide({ persisted: false });
    left.end("ok");
    const reportRequests = requests.filter(({ input }) => input === SETTINGS.route);
    keep(reportRequests.map(({ init }) => ({ body: JSON.parse(init.body) })));
    told.install = {
      "the SDK's eventReports": Object.keys(sdk).sort(),
      "its page":
        sdk.page.length === 8 && /^[0-9a-z]+$/.test(sdk.page)
          ? "eight letters and digits"
          : sdk.page,
      "a request through window.fetch carries": [...new Headers(requests[0].init.headers).keys()],
      "freezes observed": observed.map(({ options }) => options),
      "listens for": Object.keys(listeners).sort(),
      "batches sent by the time the page is hidden": onHide,
      "reports are sent with": reportRequests.map(({ init }) => ({
        method: init.method,
        keepalive: init.keepalive,
        credentials: init.credentials,
        type: init.headers["content-type"],
      })),
      "what was sent": reportRequests.flatMap(({ init }) =>
        JSON.parse(init.body).reports.map((report) =>
          line({ ...report, client: report.client === sdk.page ? "<page>" : "<page>-n" }),
        ),
      ),
    };
    const off = load({
      METABROWSER_SETTINGS: { EVENT_REPORTS: { ...SETTINGS, log: false } },
      metabrowser: {},
      location: { origin: ORIGIN, pathname: "/pull/7" },
      fetch: () => Promise.resolve({ status: 200 }),
      performance: { now: time.now },
      setTimeout: time.setTimeout,
      clearTimeout: time.clearTimeout,
    });
    const offFetch = off.fetch;
    told.install["with no log, window.fetch is the page's own"] = off.window.fetch === offFetch;
    told.install["with no log, a wait still says it is late"] = await new Promise((resolve) => {
      off.metabrowser.eventReports.wait("x", { onLate: () => resolve(true) });
      time.advance(SETTINGS.late_ms);
    });
    told.install["with no settings, nothing is installed"] =
      load({ metabrowser: {} }).metabrowser.eventReports === undefined;
  }

  // ── The Details: what the panel says ─────────────────────────────────
  told.details = await details(api);
  told.serverTiming = {
    "srv;dur=12.5": api.serverMs("srv;dur=12.5"),
    "cache;desc=hit, srv;dur=7": api.serverMs("cache;desc=hit, srv;dur=7"),
    "app;dur=3": api.serverMs("app;dur=3"),
    "(none)": api.serverMs(null),
  };
  return { settings: SETTINGS, told, bodies };
}

/**
 * Stand-ins for the routes' answers, in their shapes (tests/golden/
 * cli-api-event-log-failures.tryscript.md and cli-api-event-log.tryscript.md): a refresh job
 * that never ended, started by the page's request; GitHub unreachable at one address; and
 * the page's own wait that never completed.
 */
const FAILURES = {
  state: "present",
  since: "2026-11-19T21:00:00Z",
  failures: 4,
  causes: [
    {
      cause: "connect_timeout",
      count: 3,
      last: "2026-11-19T21:41:10.502Z",
      message:
        "GitHub could not be reached because the connection to api.github.com at 20.172.24.160 timed out after 2 s; other sites are reachable",
      addresses: ["20.172.24.160"],
      examples: [
        {
          ts: "2026-11-19T21:41:10.502Z",
          kind: "subprocess",
          name: "gh api",
          outcome: "timeout",
          dur_ms: 15012.3,
        },
      ],
    },
  ],
  probe: {
    target: "api.github.com:443",
    verdict: "connect_timeout",
    ts: "2026-11-19T21:40:34.100Z",
    addresses: [{ address: "20.172.24.160", result: "timeout", ms: 2001.2 }],
  },
};
const PAGE_LOG = {
  state: "present",
  open: [
    { kind: "loop", name: "event loop", age_ms: 12, client: null },
    { kind: "job", name: "checkout._pull_job", age_ms: 61_004, client: `${PAGE}-3` },
    { kind: "subprocess", name: "gh api", age_ms: 9_000, client: "other123-1" },
  ],
  events: [
    {
      event: "end",
      kind: "browser",
      name: "wait githubPull:diffSummary",
      client: PAGE,
      outcome: "never_completed",
      dur_ms: 61234.5,
      ts: "2026-11-19T21:42:01.000Z",
    },
    {
      event: "open",
      kind: "job",
      name: "checkout._pull_job",
      client: `${PAGE}-3`,
      dur_ms: 32000,
      ts: "2026-11-19T21:41:32.000Z",
    },
    {
      event: "end",
      kind: "request",
      name: "GET /api/tree",
      client: `${PAGE}-1`,
      outcome: "ok",
      dur_ms: 12.5,
      ts: "2026-11-19T21:41:00.000Z",
    },
    {
      event: "end",
      kind: "subprocess",
      name: "gh api",
      client: `${PAGE}-3`,
      outcome: "timeout",
      dur_ms: 15012.3,
      attrs: { cause: "connect_timeout" },
      ts: "2026-11-19T21:41:10.502Z",
    },
  ],
};

async function details(api) {
  const options = { slowMs: SETTINGS.slow_ms, page: PAGE };
  const described = api.describeDetails(FAILURES, PAGE_LOG, options);
  const out = {
    routes: api.detailRoutes({
      client: PAGE,
      since: "2026-11-19T21:00:00Z",
      until: "2026-11-19T21:43:00Z",
    }),
    "a stuck job, GitHub unreachable, and this page's wait": api
      .detailLines(described)
      .map(({ heading, items }) => ({
        heading,
        items: items.map((item) => item.replace(/ · \d{1,2}:\d\d:\d\d.*$/, " · <time>")),
      })),
    "the log off": api.detailLines(
      api.describeDetails(
        { state: "absent", causes: [] },
        { state: "absent", open: [], events: [] },
        options,
      ),
    ),
    "neither route answered": api.detailLines(api.describeDetails(null, null, options)),
    "nothing on record": api.detailLines(
      api.describeDetails(
        { state: "present", causes: [], probe: null },
        { state: "present", open: [], events: [] },
        options,
      ),
    ),
  };
  // The panel: its note while it reads, then its parts and links, from the two routes.
  const asked = [];
  const answers = new Map([
    ["/api/event-log/failures", FAILURES],
    ["/api/event-log", PAGE_LOG],
  ]);
  const fetchImpl = async (route, init) => {
    asked.push({ route, accept: init.headers.accept, signal: init.signal !== undefined });
    const body = answers.get(route.split("?")[0]);
    return { ok: body !== undefined, json: async () => body };
  };
  const panel = new Node("div");
  const painting = api.showDetails(
    panel,
    { client: PAGE, since: FAILURES.since },
    { fetch: fetchImpl, slowMs: 2000 },
  );
  const note = panel.outline();
  await painting;
  out.panel = {
    "while it reads": note,
    asked,
    painted: panel.outline().map((text) => text.replace(/ · \d{1,2}:\d\d:\d\d.*$/, " · <time>")),
  };
  const aborted = new AbortController();
  const left = new Node("div");
  const leaving = api.showDetails(
    left,
    { client: PAGE },
    { fetch: fetchImpl, signal: aborted.signal, slowMs: 2000 },
  );
  aborted.abort();
  await leaving;
  out.panel["closed before the answers"] = left.outline();
  const failing = new Node("div");
  await api.showDetails(
    failing,
    {},
    {
      fetch: async () => {
        throw new TypeError("Failed to fetch");
      },
      slowMs: 2000,
    },
  );
  out.panel["the routes unreachable, no page"] = failing.outline();
  // A server that writes no log: the panel says so and reads nothing, since what the log
  // directory holds is an earlier server's (A8, review A of #629).
  const off = new Node("div");
  const askedBefore = asked.length;
  await api.showDetails(off, { client: PAGE }, { fetch: fetchImpl, slowMs: 2000, log: false });
  out.panel["the log off on this server"] = {
    painted: off.outline(),
    asked: asked.length - askedBefore,
  };
  const reasoned = new Node("div");
  await api.showDetails(
    reasoned,
    { client: PAGE },
    {
      fetch: fetchImpl,
      slowMs: 2000,
      log: false,
      offReason:
        "the folder this server shows is the event log's own, and recording its requests would change the files on screen",
    },
  );
  out.panel["the log off with its reason"] = reasoned.outline();
  return out;
}

async function describeFile(file) {
  const { failures, page, client } = JSON.parse(fs.readFileSync(file, "utf8"));
  const api = load().MetabrowserEventReports;
  return api.detailLines(
    api.describeDetails(failures, page, { slowMs: SETTINGS.slow_ms, page: client }),
  );
}

async function main() {
  const args = process.argv.slice(2);
  if (args[0] === "--describe") {
    process.stdout.write(`${JSON.stringify(await describeFile(args[1]), null, 2)}\n`);
    return;
  }
  const { settings, told, bodies } = await story();
  assert.ok(bodies.length > 0, "the story sent bodies");
  if (args[0] === "--bodies") {
    fs.writeFileSync(args[1], JSON.stringify(bodies));
  }
  process.stdout.write(`${JSON.stringify({ settings, ...told }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
});
