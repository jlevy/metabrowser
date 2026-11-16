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
  assetBytes,
  busyMs,
  checkRecord,
  deliveryOf,
  formatRecord,
  inFlight,
  landingAssets,
  logPathOf,
  pairRows,
  parseCpuTime,
  parseLog,
  parsePhases,
  parseRequestLine,
  parseServerTiming,
  pathFamily,
  procStatTicks,
  serialAccount,
  splitAtArrival,
  sumByFamily,
  sumRows,
  wholeLinesLength,
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
  `${PREFIX}metabrowser request t=${fields.t ?? "1794727962.321"} -> 1794727962.324 (${fields.rounded} ms) ` +
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
    busy_ms: 0,
    latency_ms: 6.5,
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
  assert.equal(account.totals.latency_ms, 24);
  // Every line arrived at once, so the server was busy as long as the longest answer.
  assert.equal(account.totals.busy_ms, 9);
  assert.equal(account.assets.busy_ms, 4);
  assert.equal(account.foreground.count, 5);
  assert.equal(account.foreground.latency_ms, 19);
  assert.equal(account.assets.count, 3);
  assert.equal(account.assets.latency_ms, 9);
  assert.deepEqual(account.assets.phases, { encode: 6, read: 0.5 });
  assert.equal(account.assets_before_dcl.count, 1);
  assert.equal(account.assets_before_dcl.latency_ms, 4);
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
  assert.equal(serial.totals.latency_ms, 1.3);
  assert.equal(serial.before_dcl.latency_ms, 0.8);
  assert.equal(serial.log_unpaired, 1);
});

check("a record prints as tables, saying when a build logged its ends coarsely", () => {
  const coarse = parseLog(LOG.replace(/ end_ms=[\d.]+/g, ""));
  const account = windowAccount(coarse, TIMING);
  const text = formatRecord({
    instrument: "server-time/2",
    build: { version: "metab 1" },
    address: "/view/a.md",
    server_args: ["--exit-on-eof"],
    landings: { cold: { settled: true, load_ms: 100, account } },
    serial: serialAccount([{ path: "/static/app.js?v=1", before_dcl: true }], coarse),
  });
  assert.match(
    text,
    /^server-time\/2 metab 1 at \/view\/a\.md \(server --exit-on-eof\), cold server/,
  );
  assert.match(text, /\nassets +3 +4\.0 +9\.0 +0\.5 +0\.0 +0\.0 +6\.0 +2\.5\n/);
  assert.match(text, /6 of 6 rows logged their end only to the ms/);
  assert.match(text, /serial, warm \(.*\): 1 assets, 4\.0 ms busy/);
  assert.match(
    formatRecord({ instrument: "x", warmup: 1, address: "/" }),
    /warm server: 1 unrecorded/,
  );
});

check("a record of another revision is refused by name, not read", () => {
  const current = { instrument: "server-time/3" };
  assert.equal(checkRecord(current), current);
  // Revision 2 has the same tables and lacks only what revision 3 added.
  const previous = { instrument: "server-time/2" };
  assert.equal(checkRecord(previous), previous);
  assert.throws(
    () => checkRecord({ instrument: "server-time/1" }, "old.json"),
    /old\.json is a server-time\/1 record, which sums latency and has no busy time/,
  );
  assert.throws(() => checkRecord({}, "x.json"), /x\.json is not a server-time\/3 record/);
});

check("a window reads whole lines only, and the next one starts where they end", () => {
  assert.equal(wholeLinesLength(Buffer.from("a\nb\nc")), 4);
  assert.equal(wholeLinesLength(Buffer.from("a\n")), 2);
  assert.equal(wholeLinesLength(Buffer.from("cut short")), 0);
  assert.equal(wholeLinesLength(Buffer.alloc(0)), 0);
  // A line cut three characters short still parses, as a wrong end: why it is never read.
  const whole = line({ path: "/static/a.js", rounded: 12 }, " end_ms=12.4");
  assert.equal(parseRequestLine(whole.slice(0, -3)).end_ms, 1);
  const text = `${whole}\n${whole.slice(0, -3)}`;
  const kept = Buffer.from(text).subarray(0, wholeLinesLength(Buffer.from(text)));
  assert.deepEqual(
    parseLog(kept.toString("utf8")).map((row) => row.end_ms),
    [12.4],
  );
});

check("rows that arrived before a window are left out of it and counted", () => {
  const rows = parseLog(
    [
      line({ path: "/api/plugin/github/pulls", rounded: 400, t: "99.500" }, " end_ms=400.0"),
      line({ path: "/static/a.js", rounded: 2, t: "100.000" }, " end_ms=2.0"),
      line({ path: "/static/b.js", rounded: 2, t: "100.010" }, " end_ms=2.0"),
    ].join("\n"),
  );
  const { inside, before } = splitAtArrival(rows, 100);
  assert.deepEqual(
    inside.map((row) => row.path),
    ["/static/a.js", "/static/b.js"],
  );
  assert.deepEqual(
    before.map((row) => row.path),
    ["/api/plugin/github/pulls"],
  );
  // The open request's span would have reached 0.4 s back before the window.
  assert.equal(sumRows(inside).busy_ms, 4);
  assert.equal(sumRows(rows).busy_ms, 404);
  assert.equal(splitAtArrival(rows, Number.NaN).inside.length, 3);
});

check("the server's CPU time is read from ps on macOS and procps, and from /proc", () => {
  assert.equal(parseCpuTime("0:01.23"), 1230);
  assert.equal(parseCpuTime("  12:34.56\n"), 754560);
  assert.equal(parseCpuTime("00:00:01"), 1000);
  assert.equal(parseCpuTime("1-02:03:04"), 93784000);
  assert.equal(parseCpuTime(""), null);
  assert.equal(parseCpuTime("n/a"), null);
  // The command name can hold spaces and a parenthesis; utime and stime are fields 14, 15.
  const stat = "4242 (metab (x) y) S 1 2 3 4 5 6 7 8 9 10 250 50 0 0 20 0 9 0";
  assert.equal(procStatTicks(stat), 300);
  assert.equal(procStatTicks("garbage"), null);
});

check("a window says how many bytes its assets crossed the wire as, and decoded to", () => {
  assert.deepEqual(
    assetBytes([
      { family: "static", transfer_bytes: 900, decoded_bytes: 3000 },
      { family: "plugin_static", transfer_bytes: 400, decoded_bytes: 400 },
      { family: "data", transfer_bytes: 100, decoded_bytes: 100 },
      { family: "static", transfer_bytes: null, decoded_bytes: null },
    ]),
    { count: 2, transfer_bytes: 1300, decoded_bytes: 3400 },
  );
  assert.deepEqual(assetBytes(undefined), { count: 0, transfer_bytes: 0, decoded_bytes: 0 });
});

check("an app's start that was sent gzip is labelled the compressed path", () => {
  const app = ["--exit-on-eof"];
  const sentGzip = { server_args: app, serial: { encodings: { gzip: 78, identity: 3 } } };
  assert.equal(deliveryOf(sentGzip).mismatch, true);
  const plain = {
    server_args: app,
    server_delivery: "off for loopback clients of this machine",
    serial: { encodings: { identity: 81 } },
  };
  assert.equal(deliveryOf(plain).mismatch, false);
  assert.equal(deliveryOf({ serial: sentGzip.serial }).mismatch, false, "the default start");
  const record = (r) => ({
    instrument: "server-time/3",
    address: "/",
    ...r,
    serial: { ...r.serial, ...serialAccount([], []) },
  });
  assert.match(
    formatRecord(record(sentGzip)),
    /\n\nNOT THE APP'S START: delivery: asked uncompressed toward loopback \(the app's start\); serial answers gzip 78, identity 3\. /,
  );
  assert.match(
    formatRecord(record(plain)),
    /\n\ndelivery: asked uncompressed .*; serial answers identity 81; the server said "Compression: off for loopback clients of this machine"\n/,
  );
});

check("a record prints the server's CPU, its memory before and after, and what it left out", () => {
  const account = windowAccount(parseLog(LOG), TIMING);
  const text = formatRecord({
    instrument: "server-time/3",
    address: "/view/a.md",
    warmup: 2,
    warmups: [
      { settled: true, unsettled: [] },
      { settled: false, unsettled: [{ url: "x" }] },
    ],
    landings: { landing: { settled: true, load_ms: 100, cpu_ms: 210, arrived_before: 2, account } },
    serial: { encodings: { gzip: 1 }, cpu_ms: 30, ...serialAccount([], []) },
    server_rss_kb_start: 100 * 1024,
    server_rss_kb: 102.5 * 1024,
  });
  assert.match(
    text,
    /\nlanding: settled yes, load 100 ms, server CPU 210 ms, 2 logged rows from before the window left out\n/,
  );
  assert.match(text, /\n {2}assets sent: 1 with a browser record, 1 KB transferred, 0 KB decoded/);
  assert.match(text, /1 of 2 warm-up landing\(s\) did not settle/);
  assert.match(text, /; server CPU 30 ms/);
  assert.match(
    text,
    /server resident: 100\.0 MB after the inventory, 102\.5 MB at the end \(\+2\.5 MB\)/,
  );
});

check("the server's time is the union of the requests' spans, not their sum", () => {
  const rows = parseLog(
    [
      line({ path: "/static/a.js", rounded: 10, t: "100.000" }, " end_ms=10.0"),
      line({ path: "/static/b.js", rounded: 10, t: "100.005" }, " end_ms=10.0"),
      line({ path: "/static/c.js", rounded: 2, t: "100.030" }, " end_ms=2.0"),
    ].join("\n"),
  );
  const sum = sumRows(rows);
  assert.equal(sum.latency_ms, 22);
  // [0, 10] and [5, 15] are one span of 15 ms; [30, 32] is another of 2.
  assert.equal(sum.busy_ms, 17);
  assert.equal(busyMs([]), 0);
});

check(
  "a request is open until some session says it ended, and timers and streams are not waited for",
  () => {
    const open = {
      id: "7",
      url: `${B}/static/a.js?v=1`,
      cls: "static",
      status: null,
      netStatus: null,
      encoded: null,
      failed: null,
      cache: null,
    };
    assert.equal(inFlight(open, new Set()), true);
    // A worker's script: requested on the page's session, ended on the worker's.
    assert.equal(inFlight(open, new Set(["7"])), false);
    assert.equal(inFlight({ ...open, status: 200 }, new Set()), false);
    assert.equal(inFlight({ ...open, netStatus: 304 }, new Set()), false);
    assert.equal(inFlight({ ...open, encoded: 900 }, new Set()), false);
    assert.equal(inFlight({ ...open, failed: "canceled" }, new Set()), false);
    assert.equal(inFlight({ ...open, cache: "memory" }, new Set()), false);
    assert.equal(inFlight({ ...open, cls: "background" }, new Set()), false);
    assert.equal(inFlight({ ...open, cls: "stream" }, new Set()), false);
    assert.equal(
      inFlight({ ...open, cls: "data", url: `${B}/api/stream?path=a.log` }, new Set()),
      false,
    );
  },
);

console.log(`server-time instrument: ${checks} checks passed`);
