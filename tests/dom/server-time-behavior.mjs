// The server-time instrument's own logic, browserless: request-log lines from builds with
// and without `end_ms`, Server-Timing values, route families, pairing logged rows with
// Resource Timing rows, a window's sums by phase and family, the landing's assets in
// request order, and the serial pass. Imports the exact module server-time.mjs runs; no
// server, Chrome, or clock is used.
import assert from "node:assert/strict";
import path from "node:path";

const HERE = import.meta.dirname;
const LOOP = path.resolve(HERE, "../../explorations/performance-loop");
const {
  formatRecord,
  landingAssets,
  logPathOf,
  pairRows,
  parseLog,
  parsePhases,
  parseRequestLine,
  parseServerTiming,
  pathFamily,
  serialAccount,
  sumByFamily,
  sumRows,
  windowAccount,
} = await import(path.join(LOOP, "server-time-sums.mjs"));

let checks = 0;
const check = (name, fn) => {
  try {
    fn();
  } catch (error) {
    throw new Error(`${name}: ${error.message}`, { cause: error });
  }
  checks += 1;
};

const PREFIX = "23:32:42 metabrowser.server | ";
const line = (fields, end = "") =>
  `${PREFIX}metabrowser request t=1794727962.321 -> 1794727962.324 (${fields.rounded} ms) ` +
  `method=${fields.method ?? "GET"} path=${fields.path} status=${fields.status ?? 200} ` +
  `bytes=${fields.bytes ?? 100} start_ms=${fields.start ?? 1} phases=${fields.phases ?? "-"}${end}`;

check("a line with end_ms is read to the tenth", () => {
  const row = parseRequestLine(
    line({ path: "/static/app.js?v=ab", rounded: 3, phases: "read:1.2,encode:0.4" }, " end_ms=2.6"),
  );
  assert.equal(row.end_ms, 2.6);
  assert.equal(row.precise, true);
  assert.equal(row.path, "/static/app.js?v=ab");
  assert.deepEqual(row.phases, { read: 1.2, encode: 0.4 });
  assert.equal(row.start_ms, 1);
});

check("a build from before end_ms is read to the millisecond and says so", () => {
  const row = parseRequestLine(line({ path: "/api/tree?depth=0", rounded: 3 }));
  assert.equal(row.end_ms, 3);
  assert.equal(row.precise, false);
  assert.deepEqual(row.phases, {});
});

check("a decoded path with spaces, a missing status, and a missing start", () => {
  const row = parseRequestLine(
    line({ path: "/view/my notes.md", rounded: 0, status: "None", start: "-" }, " end_ms=0.4"),
  );
  assert.equal(row.path, "/view/my notes.md");
  assert.equal(row.status, null);
  assert.equal(row.start_ms, null);
});

check("other log lines are not rows", () => {
  const text = [
    "Serving /tmp/x at http://127.0.0.1:50139/view/",
    `${PREFIX}inventory walker complete: status=complete elapsed=12ms`,
    line({ path: "/api/tree", rounded: 1 }, " end_ms=0.9"),
    "",
  ].join("\n");
  assert.equal(parseLog(text).length, 1);
});

check("phases and Server-Timing values", () => {
  assert.deepEqual(parsePhases("-"), {});
  assert.deepEqual(parsePhases("git:2.0,git:1.5"), { git: 3.5 });
  assert.deepEqual(parseServerTiming("srv;dur=6.5, read;dur=1.2, encode;dur=0.4"), {
    srv: 6.5,
    read: 1.2,
    encode: 0.4,
  });
  assert.deepEqual(parseServerTiming('cache;desc="hit", srv;dur=1'), { cache: 0, srv: 1 });
  assert.deepEqual(parseServerTiming(undefined), {});
});

check("route families of logged paths", () => {
  assert.equal(pathFamily("/view/"), "document");
  assert.equal(pathFamily("/view/a/b.md"), "document");
  assert.equal(pathFamily("/"), "document");
  assert.equal(pathFamily("/pulls"), "document");
  assert.equal(pathFamily("/pull/7"), "document");
  assert.equal(pathFamily("/static/app.js?v=1"), "static");
  assert.equal(pathFamily("/plugin-static/markdown/@ab/index.js"), "plugin_static");
  assert.equal(pathFamily("/kpress-static/@ab/v1/css/a.css"), "kpress_static");
  assert.equal(pathFamily("/api/tree?depth=0"), "data");
  assert.equal(pathFamily("/api/plugin/github/pull-cores-prepare"), "background");
  assert.equal(pathFamily("/api/plugin/github/pulls?state=all&limit=8&after=9"), "background");
  assert.equal(pathFamily("/api/plugin/github/pulls?state=open&limit=8"), "data");
  // A path that only begins like a shell is not one.
  assert.equal(pathFamily("/viewer.js"), "other");
});

check("a browser URL is written as the log writes it", () => {
  assert.equal(
    logPathOf("http://127.0.0.1:8000/view/my%20notes.md?x=%20"),
    "/view/my notes.md?x=%20",
  );
  assert.equal(logPathOf("http://127.0.0.1:8000/static/a.js?v=1"), "/static/a.js?v=1");
});

check("rows are summed by phase, with the rest unattributed and the coarse ones counted", () => {
  const rows = [
    {
      method: "GET",
      path: "/static/a.js",
      bytes: 10,
      start_ms: 1,
      end_ms: 2.5,
      precise: true,
      phases: { encode: 1 },
    },
    {
      method: "GET",
      path: "/api/x",
      bytes: 5,
      start_ms: 2,
      end_ms: 4,
      precise: false,
      phases: { read: 1, git: 0.5 },
    },
  ];
  const sum = sumRows(rows);
  assert.deepEqual(sum, {
    count: 2,
    end_ms: 6.5,
    start_ms: 3,
    phases: { encode: 1, git: 0.5, read: 1 },
    unattributed_ms: 4,
    bytes: 15,
    coarse: 1,
  });
  assert.deepEqual(Object.keys(sumByFamily(rows)), ["data", "static"]);
  // Phases that ran side by side are each counted in full, so the rest can go below zero.
  const overlapped = sumRows([{ ...rows[0], end_ms: 1, phases: { read: 1, git: 1 } }]);
  assert.equal(overlapped.unattributed_ms, -1);
});

const B = "http://127.0.0.1:8000";

check("logged rows pair with Resource Timing rows by path, in order", () => {
  const logRows = [
    { method: "GET", path: "/static/a.js?v=1" },
    { method: "GET", path: "/static/a.js?v=1" },
    { method: "POST", path: "/api/kpress/render?path=a.md" },
    { method: "GET", path: "/plugin-static/m/@ab/worker.js" },
  ];
  const browserRows = [
    { url: `${B}/static/a.js?v=1`, startTime: 5 },
    { url: `${B}/static/a.js?v=1`, startTime: 9 },
    { url: `${B}/api/kpress/render?path=a.md`, startTime: 20 },
    { url: `${B}/static/cached.js?v=2`, startTime: 3 },
  ];
  const { rows, unanswered } = pairRows(logRows, browserRows);
  assert.deepEqual(
    rows.map((row) => row.browser?.startTime ?? null),
    [5, 9, 20, null],
  );
  assert.deepEqual(
    unanswered.map((b) => b.url),
    [`${B}/static/cached.js?v=2`],
  );
});

const LOG = [
  line({ path: "/view/a.md", rounded: 9, phases: "encode:1.0" }, " end_ms=9.0"),
  line({ path: "/static/app.js?v=1", rounded: 4, phases: "encode:3.0" }, " end_ms=4.0"),
  line(
    { path: "/plugin-static/m/@ab/index.js", rounded: 2, phases: "read:0.5,encode:1.0" },
    " end_ms=2.0",
  ),
  line({ path: "/static/tools.js?v=2", rounded: 3, phases: "encode:2.0" }, " end_ms=3.0"),
  line({ path: "/api/tree?depth=0", rounded: 1, phases: "encode:0.2" }, " end_ms=1.0"),
  line(
    { method: "POST", path: "/api/plugin/github/pull-cores-prepare", rounded: 5 },
    " end_ms=5.0",
  ),
].join("\n");
const TIMING = [
  { url: `${B}/view/a.md`, startTime: 0, before_dcl: true, serverTiming: { srv: 8, encode: 1 } },
  {
    url: `${B}/static/app.js?v=1`,
    startTime: 10,
    before_dcl: true,
    serverTiming: { srv: 3, encode: 3 },
    transferSize: 900,
  },
  {
    url: `${B}/plugin-static/m/@ab/index.js`,
    startTime: 40,
    before_dcl: false,
    serverTiming: { srv: 2, read: 0.5, encode: 1 },
  },
  {
    url: `${B}/static/tools.js?v=2`,
    startTime: 30,
    before_dcl: false,
    serverTiming: { srv: 2.5, encode: 2 },
  },
  {
    url: `${B}/api/tree?depth=0`,
    startTime: 12,
    before_dcl: true,
    serverTiming: { srv: 1, encode: 0.2 },
  },
  {
    url: `${B}/api/plugin/github/pull-cores-prepare`,
    startTime: 50,
    before_dcl: false,
    serverTiming: { srv: 5 },
  },
  // Answered from the cache: it keeps the Server-Timing it was stored with.
  {
    url: `${B}/static/cached.js?v=3`,
    startTime: 11,
    before_dcl: true,
    serverTiming: { srv: 7, encode: 4 },
    transferSize: 0,
  },
];

check("a window is summed in full, without the background work, and over its assets", () => {
  const account = windowAccount(parseLog(LOG), TIMING);
  assert.equal(account.totals.count, 6);
  assert.equal(account.totals.end_ms, 24);
  assert.equal(account.foreground.count, 5);
  assert.equal(account.foreground.end_ms, 19);
  assert.equal(account.assets.count, 3);
  assert.equal(account.assets.end_ms, 9);
  assert.deepEqual(account.assets.phases, { encode: 6, read: 0.5 });
  assert.equal(account.assets_before_dcl.count, 1);
  assert.equal(account.assets_before_dcl.end_ms, 4);
  assert.deepEqual(Object.keys(account.by_family), [
    "background",
    "data",
    "document",
    "plugin_static",
    "static",
  ]);
  // The cached answer's stored header is not this window's server time.
  assert.equal(account.headers.count, 6);
  assert.equal(account.headers.metrics.srv, 21.5);
  assert.equal(account.browser_unanswered, 1);
  assert.equal(account.log_unpaired, 0);
});

check("the landing's assets come in the order the browser requested them", () => {
  const account = windowAccount(parseLog(LOG), TIMING);
  assert.deepEqual(landingAssets(account.rows), [
    { path: "/static/app.js?v=1", start_time: 10, before_dcl: true },
    { path: "/static/tools.js?v=2", start_time: 30, before_dcl: false },
    { path: "/plugin-static/m/@ab/index.js", start_time: 40, before_dcl: false },
  ]);
});

check("the serial pass counts the assets it fetched and sets any other request apart", () => {
  const assets = [
    { path: "/static/app.js?v=1", before_dcl: true },
    { path: "/static/tools.js?v=2", before_dcl: false },
  ];
  const serial = serialAccount(
    assets,
    parseLog(
      [
        line({ path: "/static/app.js?v=1", rounded: 1, phases: "encode:0.6" }, " end_ms=0.8"),
        line({ path: "/api/plugin/github/pulls?state=all&limit=8", rounded: 3 }, " end_ms=3.0"),
        line({ path: "/static/tools.js?v=2", rounded: 1 }, " end_ms=0.5"),
      ].join("\n"),
    ),
  );
  assert.equal(serial.requested, 2);
  assert.equal(serial.totals.count, 2);
  assert.equal(serial.totals.end_ms, 1.3);
  assert.equal(serial.before_dcl.end_ms, 0.8);
  assert.equal(serial.log_unpaired, 1);
});

check("a record prints as tables, saying when a build logged its ends coarsely", () => {
  const coarse = parseLog(LOG.replace(/ end_ms=[\d.]+/g, ""));
  const account = windowAccount(coarse, TIMING);
  const text = formatRecord({
    instrument: "server-time/1",
    build: { version: "metab 1" },
    address: "/view/a.md",
    server_args: ["--compress"],
    landings: { cold: { settled: true, load_ms: 100, account } },
    serial: serialAccount([{ path: "/static/app.js?v=1", before_dcl: true }], coarse),
  });
  assert.match(text, /^server-time\/1 metab 1 at \/view\/a\.md \(server --compress\)/);
  assert.match(text, /\nassets +3 +9\.0 +0\.5 +0\.0 +0\.0 +6\.0 +2\.5\n/);
  assert.match(text, /6 of 6 rows logged their end only to the ms/);
  assert.match(text, /serial: 1 assets one at a time: 4\.0 ms/);
});

console.log(`server-time instrument: ${checks} checks passed`);
