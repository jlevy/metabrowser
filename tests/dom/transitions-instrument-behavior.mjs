// The transition-navigation instrument's own logic, browserless: request classes and
// cache disposition over recorded DevTools event sequences, frame accounting and region
// movement over recorded frame logs, and compare's refusals and verdicts over fixture
// rows. Imports the exact modules a series runs; no server, Chrome, or clock is used.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HERE = import.meta.dirname;
const LOOP = path.resolve(HERE, "../../explorations/performance-loop");
const recorder = await import(path.join(LOOP, "transitions-recorder.mjs"));
const stats = await import(path.join(LOOP, "transitions-stats.mjs"));
const {
  accountFrames,
  applyNetworkEvent,
  disposition,
  listChanges,
  networkLog,
  presentedAt,
  regionMovement,
  requestClass,
  routeFamily,
} = recorder;
const { CompareRefusal, chanceApart, compareRuns, sampleRow, scrubText } = stats;

let checks = 0;
const check = (name, fn) => {
  try {
    fn();
  } catch (error) {
    throw new Error(`${name}: ${error.message}`, { cause: error });
  }
  checks += 1;
};

// ------------------------------------------------------------ requests and disposition

const B = "http://127.0.0.1:8890";
check("request classes", () => {
  assert.equal(requestClass(`${B}/api/plugin/github/pulls?state=all&limit=8`), "background");
  assert.equal(
    requestClass(`${B}/api/plugin/github/pulls?state=all&limit=8&after=120`),
    "background",
  );
  // The visible list's own window reads are the reader's data, not the walk.
  assert.equal(
    requestClass(`${B}/api/plugin/github/pulls?state=closed&limit=100&after=250`),
    "data",
  );
  assert.equal(requestClass(`${B}/api/plugin/github/pulls?state=open&limit=8`), "data");
  assert.equal(requestClass(`${B}/api/plugin/github/pulls-refresh`), "background");
  assert.equal(requestClass(`${B}/api/plugin/github/pull-cores-prepare`), "background");
  assert.equal(requestClass(`${B}/api/kpress/render`), "kpress");
  assert.equal(requestClass(`${B}/kpress-static/css/document.css`), "kpress");
  assert.equal(requestClass(`${B}/api/events`), "stream");
  assert.equal(requestClass(`${B}/api/file?path=README.md`), "data");
  assert.equal(requestClass(`${B}/plugin-static/github/index.js`), "plugin");
  assert.equal(requestClass(`${B}/static/app.js`), "static");
  assert.equal(requestClass(`${B}/view/README.md`, "Document"), "document");
  assert.equal(requestClass("data:image/png;base64,AAAA"), "inline");
  assert.equal(routeFamily(`${B}/plugin-static/x.js`), "plugin_static");
  assert.equal(routeFamily(`${B}/kpress-static/x.css`), "kpress_static");
});

/** Replay a recorded event sequence and return each request's disposition by URL. */
const replay = (events) => {
  const log = networkLog();
  for (const [method, params] of events) {
    applyNetworkEvent(log, method, params, "page", "S");
  }
  return Object.fromEntries(log.net.map((e) => [e.url.replace(B, ""), disposition(e)]));
};
const sent = (id, url, extra = {}) => [
  "Network.requestWillBeSent",
  {
    requestId: id,
    request: { url: `${B}${url}`, method: "GET" },
    type: "Fetch",
    wallTime: 1,
    ...extra,
  },
];
const received = (id, status, response = {}) => [
  "Network.responseReceived",
  { requestId: id, response: { status, ...response } },
];
const finished = (id, bytes = 100) => [
  "Network.loadingFinished",
  { requestId: id, encodedDataLength: bytes },
];

check("a 304 the browser answered to its own cache is revalidated", () => {
  // As Chrome reports it: the raw exchange is a 304 in responseReceivedExtraInfo, and
  // responseReceived reports the cached 200 it served the page.
  const d = replay([
    sent("1", "/static/revalidate.js"),
    [
      "Network.requestWillBeSentExtraInfo",
      { requestId: "1", headers: { "If-None-Match": '"v1"' } },
    ],
    ["Network.responseReceivedExtraInfo", { requestId: "1", statusCode: 304, headers: {} }],
    received("1", 200),
    finished("1", 180),
  ]);
  assert.equal(d["/static/revalidate.js"], "revalidated");
});
check("ExtraInfo arriving before its request still counts", () => {
  const d = replay([
    ["Network.requestWillBeSentExtraInfo", { requestId: "2", headers: { "if-none-match": "x" } }],
    ["Network.responseReceivedExtraInfo", { requestId: "2", statusCode: 304, headers: {} }],
    sent("2", "/static/early.js"),
    received("2", 200),
    finished("2"),
  ]);
  assert.equal(d["/static/early.js"], "revalidated");
});
check("cache, network, page conditional, failure, pending, redirect", () => {
  const d = replay([
    sent("m", "/static/memory.js"),
    ["Network.requestServedFromCache", { requestId: "m" }],
    received("m", 200),
    sent("k", "/static/disk.js"),
    received("k", 200, { fromDiskCache: true }),
    sent("n", "/api/file?path=a"),
    ["Network.responseReceivedExtraInfo", { requestId: "n", statusCode: 200, headers: {} }],
    received("n", 200),
    sent("c", "/api/data"),
    ["Network.responseReceivedExtraInfo", { requestId: "c", statusCode: 304, headers: {} }],
    received("c", 304),
    sent("f", "/api/fail"),
    ["Network.loadingFailed", { requestId: "f", errorText: "net::ERR_FAILED" }],
    sent("p", "/api/pending"),
    sent("r", "/api/old"),
    sent("r", "/api/new", { redirectResponse: { status: 302 } }),
    received("r", 200),
  ]);
  assert.deepEqual(d, {
    "/static/memory.js": "cache",
    "/static/disk.js": "cache",
    "/api/file?path=a": "network",
    "/api/data": "revalidated",
    "/api/fail": "failed",
    "/api/pending": "pending",
    "/api/old": "network",
    "/api/new": "network",
  });
});

check("reads after the page's own refresh are settlement reads, not duplicates", () => {
  const read = (n) => ({ method: "GET", url: `${B}/api/plugin/github/pull?number=${n}` });
  const refresh = (body) => ({
    method: "POST",
    url: `${B}/api/plugin/github/pull-refresh`,
    postText: body === undefined ? null : JSON.stringify(body),
  });
  const pattern = ["^/api/plugin/github/pull\\?number=353(&|$)"];
  // A cold click: the page's first read and one more, then a refresh and three polls.
  const r = recorder.subjectReads(
    [
      read(353),
      read(353),
      refresh({ number: 353, wait_core: true }),
      read(353),
      read(351),
      read(353),
      read(353),
    ],
    pattern,
    353,
  );
  assert.deepEqual(r, { total: 5, duplicates: 1, settlement: 3 });
  // A refresh for another pull request settles nothing for this one.
  assert.deepEqual(
    recorder.subjectReads([read(353), refresh({ number: 351 }), read(353)], pattern, 353),
    {
      total: 2,
      duplicates: 1,
      settlement: 0,
    },
  );
  // An unreadable refresh body is the subject's own page asking.
  assert.equal(recorder.subjectReads([refresh(), read(353)], pattern, 353).settlement, 1);
  // Without a pull request subject nothing is settlement.
  assert.deepEqual(
    recorder.subjectReads([read(353), refresh({ number: 353 }), read(353)], pattern),
    {
      total: 2,
      duplicates: 1,
      settlement: 0,
    },
  );
});

// --------------------------------------------------------------------- frame accounting

const I = 1000 / 60;
const grid = (codes, start = 100) => codes.map((c, i) => [start + i * I, c, start + i * I + 2]);

check("painted ready is the ready frame's presentation, not the end of later work", () => {
  // The subject shows in the first frame after the input and the page keeps changing the
  // DOM for 36 more frames: readiness ends at the first frame, and the rest is settle time.
  const frames = grid(["U", ...Array(36).fill("U")]);
  const a = accountFrames({
    frames,
    origin: 95,
    windowEnd: frames.at(-1)[0],
    readyAt: frames[0][0],
    readyRead: frames[0][2],
    readyNext: frames[1][0],
  });
  assert.equal(a.paintedReadyMs, Math.round((100 + I - 95) * 10) / 10);
  assert.equal(a.readyMs, 7);
  assert.equal(a.framesToReady, 1);
  assert.equal(a.blankFrames, 0);
  assert.equal(a.uncreditedFrames, 0);
});
check("a stall after the ready frame does not move painted ready", () => {
  const frames = grid(["", "U"]);
  // A 300 ms task ran after the ready frame's rendering, and the next frame came after it:
  // the next frame's begin time, which revision 2 reported, is not when the ready frame
  // reached the screen.
  frames.push([frames[1][0] + 300, "U", frames[1][0] + 302]);
  const loafs = [[frames[1][2] + 1, 300, 250, frames[1][2] + 300]];
  const a = accountFrames({
    frames,
    origin: 95,
    windowEnd: frames.at(-1)[0],
    readyAt: frames[1][0],
    readyRead: frames[1][2],
    readyNext: frames[2][0],
    loafs,
  });
  assert.equal(a.paintedReadyMs, Math.round((100 + 2 * I - 95) * 10) / 10);
  assert.equal(a.blankFramesBeforeReady, 1);
});
check("a long ready frame is presented after its own rendering ends", () => {
  assert.equal(presentedAt(100, 102, [], I), 100 + I);
  // A Long Animation Frame that covers the read ends 400 ms later: presented at the first
  // frame boundary after that, whatever the next rAF timestamp says.
  assert.equal(presentedAt(100, 500, [[99, 410, 360, 495]], I), 100 + I * 25);
  // A LoAF without rendering, or one that ends before the read, does not count.
  assert.equal(presentedAt(100, 102, [[90, 60, 50, 0]], I), 100 + I);
  assert.equal(presentedAt(100, 102, [[20, 60, 50, 70]], I), 100 + I);
});
check("blank and placeholder frames count over the whole window", () => {
  // Content, then a mounted placeholder, then nothing, then content again, after ready.
  const frames = grid(["U", "U", "UP", "", "", "U"]);
  const a = accountFrames({
    frames,
    origin: 99,
    windowEnd: frames.at(-1)[0],
    readyAt: frames[0][0],
    readyRead: frames[0][2],
    readyNext: frames[1][0],
  });
  assert.equal(a.blankFrames, 2);
  assert.equal(a.blankFramesBeforeReady, 0);
  assert.equal(a.blankFramesAfterReady, 2);
  assert.equal(a.placeholderVisibleFrames, 1);
  assert.equal(a.placeholderVisibleFramesAfterReady, 1);
  assert.equal(a.blankMs, Math.round(2 * I * 10) / 10);
});
check("a declared prompt is the destination, not a blank", () => {
  const frames = grid(["U", "E", "E", "E"]);
  const args = {
    frames,
    origin: 99,
    windowEnd: frames.at(-1)[0],
    readyAt: frames[2][0],
    readyRead: frames[2][2],
    readyNext: frames[3][0],
  };
  assert.equal(accountFrames({ ...args, emptyState: true }).blankFrames, 0);
  assert.equal(accountFrames({ ...args, emptyState: false }).blankFrames, 3);
  // Nothing at all is still blank, prompt declared or not.
  assert.equal(
    accountFrames({ ...args, frames: grid(["U", "", "E", "E"]), emptyState: true }).blankFrames,
    1,
  );
});
check("a frame without a read carries the previous state and is uncredited", () => {
  const frames = [
    [100, "U", 102],
    [100 + I, null, null],
    [100 + 2 * I, "", 102 + 2 * I],
  ];
  const a = accountFrames({
    frames,
    origin: 99,
    windowEnd: 140,
    readyAt: 100,
    readyRead: 102,
    readyNext: 100 + I,
  });
  assert.equal(a.uncreditedFrames, 1);
  assert.equal(a.blankFrames, 1);
});

// ---------------------------------------------------------------------- region movement

const REG = {
  pane: { selector: "#p", track: ["y"] },
  row: { selector: ".sel", track: ["y"], group: "tree", identity: "data-path" },
};
check("movement over two frames is net and path, not the largest step", () => {
  const m = regionMovement(
    { pane: [0, 100, 10, 10] },
    [
      [10, "pane", [0, 118, 10, 10]],
      [27, "pane", [0, 137, 10, 10]],
    ],
    5,
    REG,
  );
  assert.equal(m.groups.page.step, 19);
  assert.equal(m.groups.page.net, 37);
  assert.equal(m.groups.page.path, 37);
});
check("a region that goes and comes back has a path and no net", () => {
  const m = regionMovement(
    { pane: [0, 100, 10, 10] },
    [
      [10, "pane", [0, 110, 10, 10]],
      [27, "pane", [0, 100, 10, 10]],
    ],
    5,
    REG,
  );
  assert.equal(m.groups.page.net, 0);
  assert.equal(m.groups.page.path, 20);
});
check("a row re-created with its identity moves; another identity is a replacement", () => {
  const same = regionMovement(
    { row: [0, 50, 10, 10, "docs"] },
    [[10, "row", [0, 87, 10, 10, "docs"]]],
    5,
    REG,
  );
  assert.equal(same.groups.tree.net, 37);
  assert.equal(same.groups.tree.replaced, 0);
  const other = regionMovement(
    { row: [0, 50, 10, 10, "docs"] },
    [[10, "row", [0, 87, 10, 10, "src"]]],
    5,
    REG,
  );
  assert.equal(other.groups.tree.path, 0);
  assert.equal(other.groups.tree.replaced, 1);
});
check("list changes after the first rows", () => {
  const c = listChanges(
    [
      [10, [], -1],
      [20, ["a", "b", "c"], 0],
      [30, ["a", "x", "c"], 0],
    ],
    5,
  );
  assert.equal(c.firstRowsMs, 15);
  assert.equal(c.rowReplacements, 1);
  assert.equal(c.rowsReplacedBelowSelection, 1);
});

// -------------------------------------------------------------------------- compare

const transition = (id, over = {}) => ({
  id,
  subject: id,
  ok: true,
  refusals: [],
  readyMs: 30,
  paintedReadyMs: 47,
  framesToReady: 2,
  blankFrames: 0,
  blankFramesAfterReady: 0,
  blankMs: 0,
  placeholderVisibleFrames: 0,
  placeholderVisibleFramesAfterReady: 0,
  navPlaceholderVisibleFrames: 0,
  uncreditedFrames: 0,
  settledMs: 60,
  navSettledMs: 0,
  nextFrameMs: 47,
  movementPx: 0,
  movementNetPx: 0,
  movementPathPx: 0,
  movementByGroup: {},
  requests: {
    byClass: { data: 1 },
    subjectDuplicates: 0,
    byFamily: {},
    fileEnvelopes: 1,
    postBytes: 0,
  },
  previewTop: { removed: 1 },
  shifts: { count: 0, sumNoInput: 0 },
  longTasks: { maxMs: 0 },
  dom: { end: 1000 },
  inputSpanMs: 0,
  readyAfterLastInputMs: 47,
  ...over,
});
const row = (condition, run, over = {}) => ({
  schema: "transition-navigation/v1",
  scenario_revision: 3,
  exp: "exp-900",
  series: "s1",
  condition,
  run,
  pair: run,
  valid: true,
  refusals: [],
  build: {
    version: `metab ${condition}`,
    commit: condition.repeat(40).slice(0, 40),
    dirty: false,
    content: null,
  },
  harness: { commit: "h", dirty: false },
  corpus: { path: "corpus", commit: "c".repeat(40), dirty: false, trunk: "t".repeat(40) },
  facts: { git_log_head: "g".repeat(40), github: { filter_totals: { open: 1, closed: 2 } } },
  server: { indexed_files: 10 },
  headed: false,
  regime_flags: { headed: false, no_warmup: false, journey_subset: false, keep_going: false },
  warmup: [{ name: "files", ok: true }],
  journeys_requested: ["files"],
  load_start: [5],
  load_end: [6],
  journeys: [
    { name: "files", ok: true, transitions: [transition("files.a"), transition("files.b")] },
  ],
  ...over,
});
/** Three control and three candidate runs, pair by pair; `edit(row, k)` mutates each. */
const series = (editA = () => {}, editB = () => {}) => {
  const rows = [];
  for (let k = 1; k <= 3; k++) {
    const a = row("a", k);
    editA(a, k);
    rows.push(a);
    const b = row("b", k);
    editB(b, k);
    rows.push(b);
  }
  return rows;
};
const setT = (r, id, over) => {
  for (const j of r.journeys) {
    j.transitions = j.transitions.map((t) => (t.id === id ? { ...t, ...over } : t));
  }
};
const cmp = (rows, options = {}) => compareRuns(rows, { control: "a", candidate: "b", ...options });
const find = (res, id, key) => res.entries.find((e) => e.id === id && e.metric === key);
const refuses = (fn, pattern) =>
  assert.throws(fn, (e) => e instanceof CompareRefusal && pattern.test(e.message));

check("identical conditions compare clean", () => {
  const res = cmp(series());
  assert.equal(res.exitCode, 0);
  assert.equal(res.gaps.length, 0);
  assert.equal(res.wrongWay.length, 0);
  assert.equal(res.pairs, 3);
});
check("a time from a zero control is a result", () => {
  const res = cmp(
    series(
      () => {},
      (r, k) => setT(r, "files.a", { longTasks: { maxMs: 150 + 50 * k } }),
    ),
  );
  const e = find(res, "files.a", "long_task_max_ms");
  assert.equal(e.outcome, "result");
  assert.match(e.verdict, /zero control/);
  assert.equal(e.wrongWay, true);
  assert.equal(res.exitCode, 1);
});
check("a time beyond the tolerance in every pair is a result", () => {
  const res = cmp(
    series(
      () => {},
      (r, k) => setT(r, "files.a", { paintedReadyMs: 80 + k }),
    ),
  );
  const e = find(res, "files.a", "painted_ready_ms");
  assert.equal(e.outcome, "result");
  assert.equal(e.pairs.up.length, 3);
});
check("ranges apart with one pair beyond the tolerance asks for a rerun", () => {
  const res = cmp(
    series(
      (r, k) => setT(r, "files.a", { paintedReadyMs: [47, 47, 47][k - 1] }),
      (r, k) => setT(r, "files.a", { paintedReadyMs: [50, 51, 70][k - 1] }),
    ),
  );
  const e = find(res, "files.a", "painted_ready_ms");
  assert.equal(e.outcome, "rerun");
  assert.match(e.verdict, /s1#3/);
  assert.equal(res.exitCode, 1);
});
check("ranges apart but every pair within the tolerance is not a result", () => {
  const res = cmp(
    series(
      () => {},
      (r, k) => setT(r, "files.a", { paintedReadyMs: 50 + k }),
    ),
  );
  const e = find(res, "files.a", "painted_ready_ms");
  assert.equal(e.outcome, "within");
  assert.equal(e.wrongWay, false);
  assert.equal(res.exitCode, 0);
});
check("pairs beyond the tolerance under overlapping ranges must be explained", () => {
  const res = cmp(
    series(
      (r, k) => setT(r, "files.a", { paintedReadyMs: [40, 40, 100][k - 1] }),
      (r, k) => setT(r, "files.a", { paintedReadyMs: [60, 60, 50][k - 1] }),
    ),
  );
  assert.equal(find(res, "files.a", "painted_ready_ms").outcome, "explain");
});
check("a lower time is a result but not a wrong way", () => {
  const res = cmp(
    series(
      () => {},
      (r) => setT(r, "files.a", { paintedReadyMs: 20 }),
    ),
  );
  const e = find(res, "files.a", "painted_ready_ms");
  assert.equal(e.outcome, "result");
  assert.equal(e.direction, "lower");
  assert.equal(e.wrongWay, false);
});
check("n is checked per metric, and a missing value is a gap", () => {
  const res = cmp(
    series(
      () => {},
      (r, k) => setT(r, "files.a", { paintedReadyMs: k === 1 ? 900 : null }),
    ),
  );
  assert.equal(find(res, "files.a", "painted_ready_ms"), undefined);
  assert.ok(res.gaps.some((g) => g.metric === "painted_ready_ms" && /n=3 and 1/.test(g.reason)));
  assert.ok(res.gaps.some((g) => /missing in 0 of 3 a run\(s\) and 2 of 3 b/.test(g.reason)));
  assert.equal(res.exitCode, 1);
});
check("a milestone the candidate never reaches is a gap, not silence", () => {
  const res = cmp(
    series(
      (r, k) => setT(r, "files.a", { milestones: { prDescriptionFinal: 300 + k } }),
      (r) => setT(r, "files.a", { milestones: { prDescriptionFinal: null } }),
    ),
  );
  assert.ok(res.gaps.some((g) => g.metric === "pr_description_final_ms"));
  assert.equal(res.exitCode, 1);
});
check("a transition measured on one side only is a gap", () => {
  const res = cmp(
    series(
      () => {},
      (r) => setT(r, "files.a", { id: "files.a2" }),
    ),
  );
  assert.ok(res.gaps.some((g) => g.id === "files.a" && /only in a/.test(g.reason)));
  assert.ok(res.gaps.some((g) => g.id === "files.a2" && /only in b/.test(g.reason)));
});
check("unpaired runs are named, and too few pairs leave the tolerance unjudged", () => {
  const rows = series(
    () => {},
    (r, k) => {
      r.pair = k + 10;
      setT(r, "files.a", { paintedReadyMs: 90 });
    },
  );
  const res = cmp(rows);
  assert.ok(res.notes.some((n) => /0 complete back-to-back pair/.test(n)));
  assert.equal(find(res, "files.a", "painted_ready_ms").outcome, "unpaired");
  assert.ok(res.gaps.some((g) => /not judged/.test(g.reason)));
});
check("refusals: labels, runs, builds, tolerance", () => {
  refuses(() => compareRuns(series(), {}), /name both conditions/);
  refuses(() => cmp(series().filter((r) => !(r.condition === "b" && r.run === 3))), /has 2 valid/);
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r, k) => {
            if (k === 3) {
              r.build.commit = "f".repeat(40);
            }
          },
        ),
      ),
    /pools 2 builds/,
  );
  refuses(() => cmp(series(), { tolerance: 2 }), /never 2x/);
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.build.dirty = true;
          },
        ),
      ),
    /dirty build with no content/,
  );
  const noted = cmp(
    series(
      () => {},
      (r) => {
        r.build.dirty = true;
        r.build.content = "sha256:abc";
      },
    ),
  );
  assert.ok(noted.notes.some((n) => /dirty build, identified by its content sha256:abc/.test(n)));
});
check("refusals: corpus and what the server saw", () => {
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.corpus.dirty = true;
          },
        ),
      ),
    /not clean/,
  );
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.corpus.commit = null;
          },
        ),
      ),
    /no commit identity/,
  );
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.corpus.commit = "e".repeat(40);
          },
        ),
      ),
    /corpus commit/,
  );
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.corpus.trunk = "d".repeat(40);
          },
        ),
      ),
    /corpus trunk/,
  );
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.facts.git_log_head = "d".repeat(40);
          },
        ),
      ),
    /git log/,
  );
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.server.indexed_files = 11;
          },
        ),
      ),
    /indexed file/,
  );
});
check("refusals and notes: regime and journeys", () => {
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.regime_flags.headed = true;
          },
        ),
      ),
    /regime/,
  );
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.regime_flags.no_warmup = true;
          },
        ),
      ),
    /regime/,
  );
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r, k) => {
            if (k > 1) {
              r.journeys_requested = ["landing"];
            }
          },
        ),
      ),
    /journeys requested/,
  );
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.scenario_revision = 2;
          },
        ),
      ),
    /scenario revision/,
  );
  const both = cmp(
    series(
      (r) => {
        r.regime_flags.headed = true;
      },
      (r) => {
        r.regime_flags.headed = true;
      },
    ),
  );
  assert.ok(both.notes.some((n) => /NOT THE STANDARD REGIME: headed/.test(n)));
  assert.ok(both.notes.some((n) => /catalog totals/.test(n)));
});
check("an expectation names its metric and reports the accept rule", () => {
  const rows = series(
    () => {},
    (r) => setT(r, "files.a", { paintedReadyMs: 20 }),
  );
  const met = cmp(rows, { expect: ["files.a:painted_ready_ms:lower"] });
  assert.equal(met.expectations[0].pass, true);
  assert.equal(met.expectations[0].conditions.length, 3);
  assert.equal(met.exitCode, 0);
  const missed = cmp(rows, { expect: ["files.b:painted_ready_ms:lower"] });
  assert.equal(missed.expectations[0].pass, false);
  assert.equal(missed.exitCode, 1);
});
check("an A/A split pairs runs in order and exits on gaps only", () => {
  const rows = [];
  for (let k = 1; k <= 6; k++) {
    const r = row("ctl", k);
    setT(r, "files.a", { paintedReadyMs: k % 2 ? 40 : 60 });
    rows.push(r);
  }
  const res = compareRuns(rows, { aa: "ctl" });
  assert.equal(res.pairs, 3);
  assert.equal(find(res, "files.a", "painted_ready_ms").outcome, "result");
  assert.equal(res.exitCode, 0);
});
check("chance separation", () => {
  assert.equal(chanceApart(3, 3), 0.1);
  assert.equal(chanceApart(5, 5), 2 / 252);
});
check("samples keep the metrics and drop paths", () => {
  // Home directories assembled at run time, so this file itself holds none.
  const mac = ["", "Users", "someone"].join("/");
  const linux = ["", "home", "runner"].join("/");
  const r = row("a", 1, {
    refusals: [["run_error", `Error: boom\n    at ${mac}/wrk/x/transitions.mjs:10:5`]],
    build: {
      version: "v",
      commit: "c",
      dirty: false,
      metab: `${mac}/env/.venv/bin/metab`,
      source: `${mac}/src`,
    },
  });
  const s = sampleRow(r);
  assert.equal(s.build.metab, "metab");
  assert.equal(JSON.stringify(s).includes(mac), false);
  assert.equal(s.journeys[0].transitions[0].paintedReadyMs, 47);
  assert.match(scrubText(`at ${linux}/work/a/b.mjs:1`), /…\/b\.mjs/);
});

// ------------------------------------------------------------------- command line exits

check("compare exits 0, 1, and 2 from the command line", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "transitions-"));
  try {
    const write = (name, rows) => {
      const f = path.join(dir, name);
      fs.writeFileSync(f, `${rows.map((r) => JSON.stringify(r)).join("\n")}\n`);
      return f;
    };
    const run = (...args) =>
      spawnSync(process.execPath, [path.join(LOOP, "transitions.mjs"), "compare", ...args], {
        encoding: "utf8",
        timeout: 20000,
      });
    const clean = run(write("clean.jsonl", series()), "--control", "a", "--candidate", "b");
    assert.equal(clean.status, 0, clean.stderr);
    const worse = run(
      write(
        "worse.jsonl",
        series(
          () => {},
          (r) => setT(r, "files.a", { paintedReadyMs: 90 }),
        ),
      ),
      "--control",
      "a",
      "--candidate",
      "b",
    );
    assert.equal(worse.status, 1, worse.stderr);
    assert.match(worse.stdout, /\[WRONG WAY\]/);
    const refused = run(write("refused.jsonl", series()), "--control", "a");
    assert.equal(refused.status, 2);
    assert.match(refused.stderr, /name both conditions/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// ------------------------------------------------------------------- process cleanup

const alive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch (_error) {
    return false;
  }
};

check("a server that fails after its spawn is stopped, and the run refused", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "transitions-run-"));
  try {
    const corpus = path.join(dir, "corpus");
    fs.mkdirSync(corpus);
    fs.writeFileSync(path.join(corpus, "README.md"), "# corpus\n");
    const git = (...args) =>
      spawnSync("git", ["-C", corpus, ...args], { encoding: "utf8", timeout: 20000 });
    git("init", "-q");
    git("add", "README.md");
    git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "c");
    // A stand-in `metab`: it reports a version, then serves a complete inventory and drops
    // every other request, so the start fails after the process exists. Each one records
    // whether an earlier one is still running when it starts.
    const bin = path.join(dir, "env", "bin");
    fs.mkdirSync(bin, { recursive: true });
    const metab = path.join(bin, "metab");
    const pidFile = path.join(dir, "server.pid");
    const overlap = path.join(dir, "overlap");
    fs.writeFileSync(
      metab,
      `#!${process.execPath}
const fs = require("node:fs");
const http = require("node:http");
if (process.argv.includes("--version")) { console.log("metab stand-in 1.0"); process.exit(0); }
if (fs.existsSync(${JSON.stringify(pidFile)})) {
  const before = Number(fs.readFileSync(${JSON.stringify(pidFile)}, "utf8"));
  try { process.kill(before, 0); fs.writeFileSync(${JSON.stringify(overlap)}, String(before)); } catch (_error) {}
}
fs.writeFileSync(${JSON.stringify(pidFile)}, String(process.pid));
const port = Number(process.argv[process.argv.indexOf("--port") + 1]);
http.createServer((req, res) => {
  if (req.url.startsWith("/api/index/progress")) { res.end(JSON.stringify({ complete: true, indexed_files: 1 })); }
  else { req.socket.destroy(); }
}).listen(port, "127.0.0.1");
`,
      { mode: 0o755 },
    );
    const out = path.join(dir, "runs.jsonl");
    const result = spawnSync(
      process.execPath,
      [
        path.join(LOOP, "transitions.mjs"),
        "run",
        "--exp",
        "exp-999",
        "--corpus",
        corpus,
        "--condition",
        `standin=${metab}`,
        "--runs",
        "2",
        "--out",
        out,
      ],
      {
        encoding: "utf8",
        timeout: 40000,
        env: { ...process.env, TRANSITIONS_BENCH: path.join(dir, "bench") },
      },
    );
    assert.equal(result.status, 1, result.stderr);
    const rows = stats.parseRows(fs.readFileSync(out, "utf8"));
    assert.equal(rows.length, 2);
    for (const r of rows) {
      assert.equal(r.valid, false);
      assert.ok(
        r.refusals.some(([g]) => g === "run_error"),
        JSON.stringify(r.refusals),
      );
    }
    assert.equal(fs.existsSync(overlap), false, "run 1's server was still running in run 2");
    const pid = Number(fs.readFileSync(pidFile, "utf8"));
    assert.equal(alive(pid), false, `the stand-in server ${pid} is still running`);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
check("a Chrome that cannot start rejects, and leaves no profile", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "transitions-chrome-"));
  try {
    const profileDir = path.join(dir, "profile");
    const result = spawnSync(
      process.execPath,
      [
        "--input-type=module",
        "-e",
        `const m = await import(${JSON.stringify(path.join(LOOP, "transitions-recorder.mjs"))});
try { await m.launchBrowser({ profileDir: ${JSON.stringify(profileDir)} }); console.log("launched"); }
catch (error) { console.log("rejected: " + error.message); }`,
      ],
      {
        encoding: "utf8",
        timeout: 40000,
        env: { ...process.env, CHROME_BIN: path.join(dir, "no-such-chrome") },
      },
    );
    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /^rejected: Chrome could not start/);
    assert.equal(fs.existsSync(profileDir), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

console.log(`transitions instrument: ${checks} checks passed`);
