// The server's time over one page load, by phase: the pure half of server-time.mjs.
//
// The server names the phases of every request's time (`metabrowser.server_timing`):
// `read`, `render`, `git`, `encode`, and any other a route adds. `Server-Timing` can carry
// only what was done by the start of the response, so the totals to the end of each body
// are read from the server's verbose request log, one line per request, and the header
// is kept beside them as the start-of-response view. Functions over parsed lines and
// Resource Timing rows, with no server, browser, or clock, so
// tests/dom/server-time-behavior.mjs drives each of them.
import { requestClass, routeFamily } from "./transitions-recorder.mjs";

// Revision 2 reports the time the server was busy, the union of the requests' spans, and
// calls revision 1's sum of every request's time to the end of its body what it is, the
// summed latency: on one event loop each waiter counts the others' work again (#455 M2).
export const INSTRUMENT = "server-time/2";

/** Route families whose answers are the application's own assets. */
export const ASSET_FAMILIES = ["static", "plugin_static", "kpress_static"];

// One verbose request-log line (`_SlowRequestLogMiddleware` in server.py). A build from
// before `end_ms` gives the end of the body only rounded to the millisecond, in the
// parentheses; such a row says so in `precise`. The path is greedy up to the last
// ` status=`, because a decoded path can hold a space.
const REQUEST_LINE =
  /metabrowser request t=([\d.]+) -> ([\d.]+) \((\d+) ms\) method=(\S+) path=(.*) status=(\S+) bytes=(\d+) start_ms=(\S+) phases=(\S+)(?: end_ms=([\d.]+))?\s*$/;

const round1 = (value) => Math.round(value * 10) / 10;

/** `read:1.2,encode:0.4` as `{read: 1.2, encode: 0.4}`; `-` is no phase. */
export function parsePhases(text) {
  const phases = {};
  if (!text || text === "-") {
    return phases;
  }
  for (const part of text.split(",")) {
    const split = part.lastIndexOf(":");
    const ms = Number(part.slice(split + 1));
    if (split > 0 && Number.isFinite(ms)) {
      const name = part.slice(0, split);
      phases[name] = (phases[name] ?? 0) + ms;
    }
  }
  return phases;
}

/** A `Server-Timing` value as `{srv: 1.2, read: 0.4}`, summing a name given twice. */
export function parseServerTiming(value) {
  const metrics = {};
  for (const part of String(value ?? "").split(",")) {
    const [name, ...params] = part.trim().split(";");
    if (!name) {
      continue;
    }
    const dur = params.map((p) => p.trim()).find((p) => p.startsWith("dur="));
    const ms = dur === undefined ? 0 : Number(dur.slice(4));
    if (Number.isFinite(ms)) {
      metrics[name] = (metrics[name] ?? 0) + ms;
    }
  }
  return metrics;
}

/** One request-log line as a row, or null when the line is not one. */
export function parseRequestLine(line) {
  const m = REQUEST_LINE.exec(line);
  if (m === null) {
    return null;
  }
  const precise = m[10] !== undefined;
  const status = Number(m[6]);
  const start = Number(m[8]);
  return {
    arrived_s: Number(m[1]),
    method: m[4],
    path: m[5],
    status: Number.isFinite(status) ? status : null,
    bytes: Number(m[7]),
    start_ms: Number.isFinite(start) ? start : null,
    end_ms: precise ? Number(m[10]) : Number(m[3]),
    precise,
    phases: parsePhases(m[9]),
  };
}

/** Every request row in a slice of the server's log, in the order they were written. */
export function parseLog(text) {
  const rows = [];
  for (const line of String(text).split("\n")) {
    const row = parseRequestLine(line);
    if (row !== null) {
      rows.push(row);
    }
  }
  return rows;
}

const SHELL = /^\/(?:(?:view|commit|pull)(?:\/|$)|pulls$|$)/;

/**
 * What a logged path fetched: `document` for a shell, `background` for the Pulls catalog
 * work that runs on its own timers after every page load (`requestClass` in
 * transitions-recorder.mjs), else its route family.
 */
export function pathFamily(path) {
  const text = String(path);
  const bare = text.split("?")[0];
  if (SHELL.test(bare)) {
    return "document";
  }
  const url = `http://server${text.startsWith("/") ? "" : "/"}${text}`;
  if (requestClass(url, "") === "background") {
    return "background";
  }
  return routeFamily(url, "");
}

/** A browser URL as the request log writes it: the decoded path, then the raw query. */
export function logPathOf(url) {
  const u = new URL(url);
  let pathname = u.pathname;
  try {
    pathname = decodeURIComponent(pathname);
  } catch (_error) {
    // A malformed escape is logged as the server decoded it, which this cannot know.
  }
  return `${pathname}${u.search}`;
}

/**
 * How long at least one of *rows* was being answered: the union of each request's span,
 * from its arrival to the end of its body, in milliseconds. This is the server's time over
 * a window; the sum of the spans counts every request's wait for the others again. The
 * arrival is logged to the millisecond, so a span is placed to within one.
 */
export function busyMs(rows) {
  const spans = rows
    .filter((row) => Number.isFinite(row.arrived_s))
    .map((row) => [row.arrived_s * 1000, row.arrived_s * 1000 + row.end_ms])
    .sort((a, b) => a[0] - b[0]);
  let total = 0;
  let open = null;
  for (const [from, to] of spans) {
    if (open === null || from > open[1]) {
      if (open !== null) {
        total += open[1] - open[0];
      }
      open = [from, to];
    } else {
      open[1] = Math.max(open[1], to);
    }
  }
  return open === null ? total : total + open[1] - open[0];
}

/**
 * The server's time over *rows*: how many; `busy_ms`, the union of their spans
 * ({@link busyMs}), which is the server time a window cost; `latency_ms`, the sum of every
 * request's time to the end of its body, which counts concurrent requests' waits for each
 * other and so measures contention, not work; the time to the start of every response;
 * each phase's total, which is work wherever it ran; and `unattributed_ms`, the summed
 * latency less every phase's, which can be negative because phases that ran side by side
 * are each counted in full. `coarse` counts rows whose end was logged only to the
 * millisecond, by a build from before `end_ms`.
 */
export function sumRows(rows) {
  const phases = {};
  let end = 0;
  let start = 0;
  let bytes = 0;
  let coarse = 0;
  for (const row of rows) {
    end += row.end_ms;
    start += row.start_ms ?? 0;
    bytes += row.bytes;
    if (!row.precise) {
      coarse += 1;
    }
    for (const [name, ms] of Object.entries(row.phases)) {
      phases[name] = (phases[name] ?? 0) + ms;
    }
  }
  const phased = Object.values(phases).reduce((a, b) => a + b, 0);
  return {
    count: rows.length,
    busy_ms: round1(busyMs(rows)),
    latency_ms: round1(end),
    start_ms: round1(start),
    phases: Object.fromEntries(
      Object.entries(phases)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([name, ms]) => [name, round1(ms)]),
    ),
    unattributed_ms: round1(end - phased),
    bytes,
    coarse,
  };
}

/** {@link sumRows} for each route family present, by name. */
export function sumByFamily(rows) {
  const groups = new Map();
  for (const row of rows) {
    const family = pathFamily(row.path);
    if (!groups.has(family)) {
      groups.set(family, []);
    }
    groups.get(family).push(row);
  }
  return Object.fromEntries(
    [...groups.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([family, list]) => [family, sumRows(list)]),
  );
}

export const isAssetPath = (path) => ASSET_FAMILIES.includes(pathFamily(path));

/**
 * Pair each logged row with the browser's own record of the same request: the first
 * unpaired Resource Timing row with the same logged path, in order. Resource Timing does
 * not record a method, so a POST pairs by its path too. Returns the logged rows with
 * `browser` (null when none matched: a worker's request, which the page's timeline does
 * not hold) and the browser rows no log line answered, which are requests the browser's
 * cache served, or a stream the log leaves out.
 */
export function pairRows(logRows, browserRows) {
  const waiting = new Map();
  for (const b of browserRows) {
    const key = logPathOf(b.url);
    if (!waiting.has(key)) {
      waiting.set(key, []);
    }
    waiting.get(key).push(b);
  }
  const paired = logRows.map((row) => {
    const queue = waiting.get(row.path);
    const browser = queue?.length ? queue.shift() : null;
    return { ...row, browser };
  });
  const unanswered = [...waiting.values()].flat();
  return { rows: paired, unanswered };
}

/**
 * The landing's asset requests that reached the server, from a window's account rows, in
 * the order the browser made them, each with whether it started before
 * `DOMContentLoaded` ended, as the startup budgets' probe decides it
 * (`startupScriptResources` in probe.js). A row the browser has no record of sorts last.
 */
export function landingAssets(accountRows) {
  return accountRows
    .filter((row) => isAssetPath(row.path) && row.method === "GET")
    .map((row) => ({
      path: row.path,
      start_time: row.start_time ?? null,
      before_dcl: row.before_dcl ?? null,
    }))
    .sort((a, b) => (a.start_time ?? Infinity) - (b.start_time ?? Infinity));
}

/** The sum of each `Server-Timing` metric over *browserRows*, and how many carried one. */
export function sumHeaders(browserRows) {
  const metrics = {};
  let count = 0;
  for (const b of browserRows) {
    if (!b.serverTiming || Object.keys(b.serverTiming).length === 0) {
      continue;
    }
    count += 1;
    for (const [name, ms] of Object.entries(b.serverTiming)) {
      metrics[name] = (metrics[name] ?? 0) + ms;
    }
  }
  return {
    count,
    metrics: Object.fromEntries(
      Object.entries(metrics)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([name, ms]) => [name, round1(ms)]),
    ),
  };
}

/**
 * One window's account: every logged request in it, summed, without the background
 * Pulls work (`foreground`), by family, over the assets, and over the assets requested
 * before `DOMContentLoaded`; the start-of-response headers the browser saw; and how the
 * log and the browser's record paired.
 */
export function windowAccount(logRows, browserRows) {
  const { rows, unanswered } = pairRows(logRows, browserRows);
  const assets = rows.filter((row) => isAssetPath(row.path));
  return {
    totals: sumRows(rows),
    foreground: sumRows(rows.filter((row) => pathFamily(row.path) !== "background")),
    by_family: sumByFamily(rows),
    assets: sumRows(assets),
    assets_before_dcl: sumRows(assets.filter((row) => row.browser?.before_dcl === true)),
    // Only the responses the server sent in this window: a cached answer keeps the
    // Server-Timing of the response it was stored from.
    headers: sumHeaders(rows.filter((row) => row.browser !== null).map((row) => row.browser)),
    browser_requests: browserRows.length,
    browser_unanswered: unanswered.length,
    log_unpaired: rows.filter((row) => row.browser === null).length,
    rows: rows.map((row) => ({
      method: row.method,
      path: row.path,
      family: pathFamily(row.path),
      status: row.status,
      bytes: row.bytes,
      start_ms: row.start_ms,
      end_ms: row.end_ms,
      phases: row.phases,
      before_dcl: row.browser?.before_dcl ?? null,
      start_time: row.browser?.startTime ?? null,
      transfer_bytes: row.browser?.transferSize ?? null,
      decoded_bytes: row.browser?.decodedBodySize ?? null,
      header: row.browser?.serverTiming ?? null,
    })),
  };
}

/**
 * The serial pass: the landing's assets fetched again one at a time, and the server's
 * time for each from the log. `before_dcl` sums the ones the landing requested before
 * `DOMContentLoaded`. A logged row is matched to the asset it answers by path, in order,
 * and a row that answers none, such as a page's timer still running, is counted apart.
 */
export function serialAccount(assets, logRows) {
  const { rows: all } = pairRows(
    logRows,
    assets.map((a) => ({ url: `http://server${a.path}`, before_dcl: a.before_dcl })),
  );
  const rows = all.filter((row) => row.browser !== null);
  return {
    requested: assets.length,
    totals: sumRows(rows),
    before_dcl: sumRows(rows.filter((row) => row.browser?.before_dcl === true)),
    log_unpaired: all.length - rows.length,
  };
}

/** Requests that stay open by design, which a landing does not wait for. */
export const LONG_LIVED = ["/api/events", "/api/stream"];

/**
 * Whether a request the browser made is still open, so a landing has not settled.
 *
 * The Pulls catalog's background work runs on its own timers after every load, so the
 * network is never quiet while it is counted; it is summed, as `background`, not waited for.
 * `settledIds` are the request IDs some session has said ended.
 */
export function inFlight(entry, settledIds) {
  if (["inline", "stream", "background"].includes(entry.cls)) {
    return false;
  }
  if (LONG_LIVED.some((p) => entry.url.includes(p))) {
    return false;
  }
  // A dedicated worker's script is requested on the page's session and answered, from the
  // server or the cache, on the worker's, so its page entry never hears how it ended; any
  // session's word for its request ID settles it. The server's log, read after the quiet,
  // is what says where each body ended.
  if (settledIds.has(entry.id)) {
    return false;
  }
  const answered = entry.status !== null || entry.netStatus !== null;
  return !answered && entry.encoded === null && entry.failed === null && entry.cache !== "memory";
}

/** The DevTools events that end a request, on whichever session they arrive. */
export const SETTLING_EVENTS = new Set([
  "Network.loadingFinished",
  "Network.loadingFailed",
  "Network.requestServedFromCache",
  "Network.responseReceived",
]);

const PHASE_ORDER = ["read", "render", "git", "encode"];

/** The phase columns a table shows: the four named ones, then any other seen, by name. */
export function phaseColumns(sums) {
  const seen = new Set();
  for (const sum of sums) {
    for (const name of Object.keys(sum.phases)) {
      seen.add(name);
    }
  }
  const others = [...seen].filter((name) => !PHASE_ORDER.includes(name)).sort();
  return [...PHASE_ORDER, ...others];
}

const cell = (value, width) => String(value).padStart(width);

/** One window's sums as a text table: a row per family, then the assets and the total. */
export function formatWindow(title, account) {
  const named = [
    ...Object.entries(account.by_family),
    ["assets", account.assets],
    ["assets<dcl", account.assets_before_dcl],
    ["foreground", account.foreground],
    ["total", account.totals],
  ];
  const columns = phaseColumns(named.map(([, sum]) => sum));
  const head = [
    "".padEnd(14),
    cell("n", 4),
    cell("busy", 8),
    cell("latency", 9),
    ...columns.map((name) => cell(name, 8)),
    cell("other", 8),
  ].join(" ");
  const lines = [title, head];
  for (const [name, sum] of named) {
    lines.push(
      [
        name.padEnd(14),
        cell(sum.count, 4),
        cell(sum.busy_ms.toFixed(1), 8),
        cell(sum.latency_ms.toFixed(1), 9),
        ...columns.map((c) => cell((sum.phases[c] ?? 0).toFixed(1), 8)),
        cell(sum.unattributed_ms.toFixed(1), 8),
      ].join(" "),
    );
  }
  const coarse = account.totals.coarse;
  if (coarse > 0) {
    lines.push(`  ${coarse} of ${account.totals.count} rows logged their end only to the ms`);
  }
  lines.push(
    `  header sums (start of response, ${account.headers.count} responses): ` +
      (Object.entries(account.headers.metrics)
        .map(([name, ms]) => `${name} ${ms.toFixed(1)}`)
        .join(", ") || "none"),
  );
  lines.push(
    `  paired: ${account.log_unpaired} logged rows without a browser record, ` +
      `${account.browser_unanswered} of ${account.browser_requests} browser records without a log line`,
  );
  return lines.join("\n");
}

/** A whole record (the JSON server-time.mjs writes) as text. */
export function formatRecord(record) {
  const out = [
    `${record.instrument} ${record.build?.version ?? "?"} at ${record.address}` +
      (record.server_args?.length ? ` (server ${record.server_args.join(" ")})` : "") +
      `, ${record.warmup ? `warm server: ${record.warmup} unrecorded landing(s) first` : "cold server"}`,
    "busy is the server's time (the union of the requests' spans); latency sums every request's time to its last byte, so it counts each concurrent request's wait for the others again",
  ];
  for (const [name, landing] of Object.entries(record.landings ?? {})) {
    out.push(
      formatWindow(
        `${name}: settled ${landing.settled ? "yes" : "no"}, load ${landing.load_ms ?? "?"} ms`,
        landing.account,
      ),
    );
  }
  if (record.serial) {
    const s = record.serial;
    out.push(
      `serial, warm (each asset the landing fetched, fetched again): ${s.requested} assets, ` +
        `${s.totals.busy_ms.toFixed(1)} ms busy ` +
        `(${s.before_dcl.count} before DOMContentLoaded: ${s.before_dcl.busy_ms.toFixed(1)} ms); ` +
        Object.entries(s.totals.phases)
          .map(([name, ms]) => `${name} ${ms.toFixed(1)}`)
          .join(", "),
    );
  }
  return out.join("\n\n");
}
