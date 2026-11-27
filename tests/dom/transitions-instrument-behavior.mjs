// The transition-navigation instrument's own logic, browserless: request classes and
// cache disposition over recorded DevTools event sequences, frame accounting and region
// movement over recorded frame logs, and compare's refusals and verdicts over fixture
// rows. Imports the exact modules a series runs without starting the application or Chrome.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HERE = import.meta.dirname;
const LOOP = path.resolve(HERE, "../../explorations/performance-loop");
const recorder = await import(path.join(LOOP, "transitions-recorder.mjs"));
const stats = await import(path.join(LOOP, "transitions-stats.mjs"));
const { waitForOriginStore } = await import(path.join(LOOP, "provenance.mjs"));
const {
  accountFrames,
  applyNetworkEvent,
  disposition,
  hoverDwellOf,
  listChanges,
  networkLog,
  presentedAt,
  readsUpTo,
  regionMovement,
  requestClass,
  routeFamily,
} = recorder;
const {
  CompareRefusal,
  chanceApart,
  commitsLandingOf,
  compareRuns,
  landingDrift,
  sampleRow,
  scrubText,
  summarize,
} = stats;

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
// An event may name its session third ("P" the page, "W" a worker); the default is "S".
const replay = (events) => {
  const log = networkLog();
  for (const [method, params, sid = "S"] of events) {
    applyNetworkEvent(log, method, params, sid === "W" ? "worker" : "page", sid);
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
check("a worker's 304 is revalidated though its ExtraInfo arrives on the page's session", () => {
  // As Chrome reports a dedicated worker's request: the request and its response on the
  // worker's session, both ExtraInfo events on the page's, in either order.
  const at = (sid, [method, params]) => [method, params, sid];
  const d = replay([
    at("W", sent("w1", "/plugin-static/markdown/after.js")),
    at("P", [
      "Network.requestWillBeSentExtraInfo",
      { requestId: "w1", headers: { "If-None-Match": "x" } },
    ]),
    at("P", [
      "Network.responseReceivedExtraInfo",
      { requestId: "w1", statusCode: 304, headers: {} },
    ]),
    at("W", received("w1", 200)),
    at("W", finished("w1", 198)),
    at("P", [
      "Network.responseReceivedExtraInfo",
      { requestId: "w2", statusCode: 304, headers: {} },
    ]),
    at("W", sent("w2", "/plugin-static/markdown/before.js")),
    at("W", received("w2", 200)),
    at("W", sent("w3", "/plugin-static/markdown/full.js")),
    at("P", [
      "Network.responseReceivedExtraInfo",
      { requestId: "w3", statusCode: 200, headers: {} },
    ]),
    at("W", received("w3", 200)),
  ]);
  assert.deepEqual(d, {
    "/plugin-static/markdown/after.js": "revalidated",
    "/plugin-static/markdown/before.js": "revalidated",
    "/plugin-static/markdown/full.js": "network",
  });
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

check("blank frames that still show the origin's prompt are reported apart", () => {
  const frames = grid(["E", "E", "U", "U"]);
  const a = accountFrames({
    frames,
    origin: 99,
    windowEnd: frames.at(-1)[0],
    readyAt: frames[2][0],
    readyRead: frames[2][2],
    readyNext: frames[3][0],
    initialCode: "E",
  });
  assert.equal(a.blankFrames, 2);
  assert.equal(a.blankFramesOriginPrompt, 2);
  // Old content that lingers is not blank, and nothing is the origin's prompt.
  const b = accountFrames({
    ...a,
    frames: grid(["U", "", "U"]),
    origin: 99,
    windowEnd: 200,
    readyAt: 100 + 2 * I,
    readyRead: 102 + 2 * I,
    readyNext: null,
    initialCode: "U",
  });
  assert.equal(b.blankFrames, 1);
  assert.equal(b.blankFramesOriginPrompt, 0);
});

const REG = {
  pane: { selector: "#p", track: ["y"] },
  row: { selector: ".sel", track: ["y"], group: "tree", identity: "data-path" },
};
// Revision 6, mb-s0e4: a frame is [begin, state, read, read cost, seen].
check("the input's own frame is in its window though stamped before the input", () => {
  // The input at 100; Chrome stamps the frame that draws it 0.2 ms earlier, and a frame
  // read before the input began 16 ms earlier still.
  const frames = [
    [83.5, "U", 85, 0.1, 0],
    [99.8, "", 101, 0.2, 1],
    [99.8 + I, "U", 101 + I, 0.4, 1],
    [99.8 + 2 * I, "U", 101 + 2 * I, 0.3, 1],
  ];
  const a = accountFrames({
    frames,
    origin: 100,
    windowEnd: frames.at(-1)[0],
    readyAt: frames[2][0],
    readyRead: frames[2][2],
    readyNext: frames[3][0],
    initialCode: "U",
  });
  assert.equal(a.framesToReady, 2);
  assert.equal(a.blankFramesBeforeReady, 1);
  assert.equal(a.framesInWindow, 3);
  // The read's own cost: the longest in the window, and the sum up to the ready frame.
  assert.equal(a.readCostMaxMs, 0.4);
  assert.equal(a.readCostToReadyMs, 0.6);
  // The input's own frame is the ready frame: in the window with the flag, and placed by
  // its begin time alone, as revision 5 placed every frame, outside it.
  const ready = [
    [83.5, "U", 85, 0.1, 0],
    [99.8, "U", 101, 0.2, 1],
    [99.8 + I, "U", 101 + I, 0.2, 1],
  ];
  const args = {
    origin: 100,
    windowEnd: ready.at(-1)[0],
    readyAt: ready[1][0],
    readyRead: ready[1][2],
    readyNext: ready[2][0],
  };
  assert.equal(accountFrames({ ...args, frames: ready }).framesToReady, 1);
  assert.equal(
    accountFrames({ ...args, frames: ready.map((f) => f.slice(0, 3)) }).framesToReady,
    0,
  );
});
check("a frame read before the input is out of its window though stamped after it", () => {
  // Review of #442: the input at 1000; a frame Chrome stamped 0.3 ms after it was read
  // before it, so it shows the origin and is not the transition's.
  const frames = [
    [983.4, "E", 984, 0.1, 0],
    [1000.3, "E", 1001, 0.1, 0],
    [1016.9, "E", 1018, 0.1, 1],
    [1033.6, "U", 1035, 0.1, 1],
    [1050.2, "U", 1051, 0.1, 1],
  ];
  const a = accountFrames({
    frames,
    origin: 1000,
    windowEnd: 1500,
    readyAt: 1033.6,
    readyRead: 1035,
    readyNext: 1050.2,
    initialCode: "E",
  });
  assert.equal(a.framesToReady, 2);
  assert.equal(a.blankFramesBeforeReady, 1);
  assert.equal(a.framesInWindow, 3);
  // A 40 px move its pre-input read logged is where the region stood at the input.
  const m = regionMovement(
    { pane: [0, 0, 10, 10] },
    [
      [1000.3, "pane", [0, 40, 10, 10], 0],
      [1033.6, "pane", [0, 40, 10, 10], 1],
    ],
    1000,
    REG,
  );
  assert.equal(m.groups.page.path, 0);
});
check("each frame is placed in the window on its own, a missed one by what the tick knew", () => {
  // Review A of #442, A4: a frame whose read never came, stamped after the input, then a
  // frame read before the input. The second stays out of the window, though it follows an
  // entry placed in it.
  const frames = [
    [83.4, "E", 84, 0.1, 0],
    [100.3, null, null],
    [116.9, "", 118, 0.1, 0],
    [133.6, "U", 135, 0.1, 1],
    [150.2, "U", 151, 0.1, 1],
  ];
  const args = {
    origin: 100,
    windowEnd: 200,
    readyAt: 133.6,
    readyRead: 135,
    readyNext: 150.2,
    initialCode: "E",
  };
  const a = accountFrames({ ...args, frames });
  assert.equal(a.framesInWindow, 3);
  assert.equal(a.blankFramesBeforeReady, 1);
  assert.ok(!a.frameStates.some(([t]) => t === 16.9), JSON.stringify(a.frameStates));
  // Review C of #442, C8: the tick that logs a missed frame knows the input had not
  // arrived, so it logs the frame read before the input (0), and the window holds the
  // input's own frames alone.
  const b = accountFrames({ ...args, frames: frames.with(1, [100.3, null, null, null, 0, 0]) });
  assert.deepEqual([b.framesInWindow, b.blankFramesBeforeReady, b.framesToReady], [2, 0, 1]);
  const c = accountFrames({
    ...args,
    frames: [
      [83.4, "E", 84, 0.1, 0, 0],
      [99.8, null, null, null, 0, 0],
      [116.5, "U", 117, 0.1, 1, 0],
      [133.2, "U", 134, 0.1, 1, 0],
    ],
    readyAt: 116.5,
    readyRead: 117,
    readyNext: 133.2,
  });
  assert.deepEqual([c.framesInWindow, c.uncreditedFrames], [2, 0]);
  // After a frame whose read saw the input, a missed frame is in the window (1), whatever
  // its stamp.
  const d = accountFrames({
    ...args,
    frames: [
      [99.9, "", 101, 0.1, 1, 0],
      [99.9 + I, null, null, null, 1, 0],
      [99.9 + 2 * I, "U", 101 + 2 * I, 0.1, 1, 0],
    ],
    readyAt: 99.9 + 2 * I,
    readyRead: 101 + 2 * I,
    readyNext: null,
  });
  assert.deepEqual([d.framesInWindow, d.uncreditedFrames, d.blankFramesBeforeReady], [3, 1, 2]);
});
check("the reads up to a milestone include those read after the window", () => {
  // Review B of #442, B4: the window's frames and the ones read while the milestone was
  // awaited, up to the milestone's own frame, a read before the input left out.
  const frames = [
    [90, "E", 91, 9.9, 0, 1],
    [100, "", 101, 0.3, 1, 0],
    [100 + I, "U", 101 + I, 0.5, 1, 0],
    [100 + 2 * I, "U", 101 + 2 * I, 4.6, 1, 1],
    [100 + 3 * I, null, null, null, 1, 0],
    [100 + 4 * I, "U", 101 + 4 * I, 0.4, 1, 1],
    [100 + 5 * I, "U", 101 + 5 * I, 7.7, 1, 1],
  ];
  assert.deepEqual(readsUpTo(frames, 99, 100 + 4 * I), { maxMs: 4.6, toMs: 5.8, truncated: 2 });
  assert.deepEqual(readsUpTo(frames, 99, 50), { maxMs: null, toMs: 0, truncated: 0 });
});
check("a hover-click's dwell starts at the pointer's arrival over its target", () => {
  // Review A of #442, A6: a boundary event elsewhere under the stationary pointer, after
  // arm and before the move, is not the arrival.
  const inputs = [
    ["pointerover", 1000, true, 0],
    ["pointerover", 1210, true, 1],
    ["pointerover", 1230, true, 1],
    ["pointerdown", 1460, true, 0],
  ];
  assert.equal(hoverDwellOf(inputs, 1460), 250);
  assert.equal(hoverDwellOf(inputs.slice(0, 1), 1460), null);
});
check("a --memory-after name no transition measured is named", () => {
  const journeys = [{ transitions: [{ id: "files.a" }, { id: "files.b" }] }, { transitions: [] }];
  assert.deepEqual(stats.unmeasuredMemoryAfter(["files.b", "files.c"], journeys), ["files.c"]);
  assert.deepEqual(stats.unmeasuredMemoryAfter([], journeys), []);
});
check("the origin's prompt lasts while only the pending modifier changes", () => {
  const frames = grid(["E", "Eb", "Eb", "EPb", "U"]);
  const a = accountFrames({
    frames,
    origin: 99,
    windowEnd: frames.at(-1)[0],
    readyAt: frames[4][0],
    readyRead: frames[4][2],
    readyNext: null,
    initialCode: "E",
  });
  assert.equal(a.blankFramesBeforeReady, 4);
  assert.equal(a.blankFramesOriginPrompt, 4);
  // Anything else on screen ends it: here nothing at all.
  const b = accountFrames({
    ...a,
    frames: grid(["Eb", "", "E", "U"]),
    origin: 99,
    windowEnd: 200,
    readyAt: 100 + 3 * I,
    readyRead: 102 + 3 * I,
    readyNext: null,
    initialCode: "E",
  });
  assert.equal(b.blankFramesOriginPrompt, 1);
});

// ---------------------------------------------------------------------- region movement

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
check("a region absent for some frames moves from where it last was", () => {
  // A pull request's tab bar while its header is replaced by a taller one: gone for a
  // frame, back 66 px lower.
  const m = regionMovement(
    { pane: [0, 300, 10, 10] },
    [
      [10, "pane", null],
      [27, "pane", [0, 366, 10, 10]],
    ],
    5,
    REG,
  );
  assert.equal(m.groups.page.net, 66);
  assert.equal(m.groups.page.path, 66);
  assert.equal(m.groups.page.step, 66);
  assert.equal(m.regions.pane.removed, 1);
  assert.equal(m.regions.pane.appeared, 0);
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
check("a box is in the window when its frame's read saw the input", () => {
  // The input at 100. A box its own frame logged, stamped 0.3 ms before the input, moves
  // the region; one a frame logged 0.5 ms before the input, read before it, is where the
  // region stood (revision 5 took everything from 1 ms before the input).
  const m = regionMovement(
    { pane: [0, 100, 10, 10] },
    [
      [99.5, "pane", [0, 110, 10, 10], 0],
      [99.7, "pane", [0, 140, 10, 10], 1],
    ],
    100,
    REG,
  );
  assert.equal(m.groups.page.net, 30);
  assert.equal(m.groups.page.path, 30);
  const early = regionMovement(
    { pane: [0, 100, 10, 10] },
    [[90, "pane", [0, 140, 10, 10], 1]],
    100,
    REG,
  );
  assert.equal(early.groups.page.net, 40);
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
  scenario_revision: stats.SCENARIO_REVISION,
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
const series = (editA = () => {}, editB = () => {}, pairs = 3) => {
  const rows = [];
  for (let k = 1; k <= pairs; k++) {
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
    /head of the server/,
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
check("a zero control under overlapping ranges goes through the pair rule", () => {
  // Review B's fixture: 0 in every control run, non-zero in five candidate runs of six.
  const six = (id, over) =>
    series(
      () => {},
      (r, k) => setT(r, id, over(k)),
      6,
    );
  for (const [key, over] of [
    ["blank_frames", (k) => ({ blankFrames: k === 1 ? 0 : 1 })],
    ["long_task_max_ms", (k) => ({ longTasks: { maxMs: k <= 2 ? 0 : 60 } })],
    ["placeholder_visible_frames", (k) => ({ placeholderVisibleFrames: k === 1 ? 0 : 3 })],
  ]) {
    const res = cmp(six("files.a", over));
    const e = find(res, "files.a", key);
    assert.equal(e.overlap, true, key);
    assert.equal(e.outcome, "explain", `${key}: ${e.verdict}`);
    assert.equal(e.wrongWay, true, key);
    assert.equal(res.exitCode, 1, key);
  }
  // Both medians 0, a long task in two candidate runs: the medians did not move, and the
  // two pairs beyond the tolerance are owed an explanation in the worse direction.
  const tie = find(
    cmp(six("files.a", (k) => ({ longTasks: { maxMs: k <= 2 ? 70 : 0 } }))),
    "files.a",
    "long_task_max_ms",
  );
  assert.equal(tie.direction, "same");
  assert.equal(tie.outcome, "explain");
  assert.equal(tie.wrongWay, true);
  // Separated ranges from a zero control are still a result, on the ranges alone.
  const apart = find(cmp(six("files.a", () => ({ blankFrames: 1 }))), "files.a", "blank_frames");
  assert.equal(apart.outcome, "result");
  assert.match(apart.verdict, /zero control/);
});
check("one pair beyond the tolerance under overlapping ranges is listed with its pair", () => {
  const res = cmp(
    series(
      (r, k) => setT(r, "files.a", { paintedReadyMs: [40, 60, 50][k - 1] }),
      (r, k) => setT(r, "files.a", { paintedReadyMs: [70, 55, 45][k - 1] }),
    ),
  );
  const e = find(res, "files.a", "painted_ready_ms");
  assert.equal(e.overlap, true);
  assert.equal(e.outcome, "pair");
  assert.equal(e.wrongWay, false);
  assert.match(e.verdict, /ranges overlap; one pair of 3 is higher .*s1#1/);
});
check("a declared milestone missing on both sides is a gap", () => {
  const res = cmp(
    series(
      (r) => setT(r, "files.a", { milestones: { prDescriptionFinal: null } }),
      (r) => setT(r, "files.a", { milestones: { prDescriptionFinal: null } }),
    ),
  );
  assert.ok(
    res.gaps.some(
      (g) => g.metric === "pr_description_final_ms" && /present in none/.test(g.reason),
    ),
    JSON.stringify(res.gaps),
  );
  assert.equal(res.exitCode, 1);
});
check("the corpus refs must match across the runs", () => {
  refuses(
    () =>
      cmp(
        series(
          (r) => {
            r.corpus.refs = "1111";
          },
          (r) => {
            r.corpus.refs = "2222";
          },
        ),
      ),
    /corpus refs/,
  );
});
check("a settle time beyond the candidate's window is marked", () => {
  const res = cmp(
    series(
      (r) => setT(r, "files.a", { settledMs: 300, windowMs: 450 }),
      (r) => setT(r, "files.a", { settledMs: 100, windowMs: 250 }),
    ),
  );
  const e = find(res, "files.a", "settled_ms");
  assert.equal(e.windowCut, true);
  assert.match(e.verdict, /after the candidate's shortest window \(250\.0 ms\) closed/);
  // Review C of #442, C2: it cannot be compared, so it is a gap, not a result, and an
  // expectation on it is not met.
  assert.equal(e.outcome, "window");
  assert.equal(e.wrongWay, false);
  assert.ok(res.gaps.some((g) => g.id === "files.a" && g.metric === "settled_ms"));
  const expected = cmp(
    series(
      (r) => setT(r, "files.a", { settledMs: 600, windowMs: 900 }),
      (r) => setT(r, "files.a", { settledMs: 300, windowMs: 350 }),
    ),
    { expect: ["files.a:settled_ms:lower"] },
  );
  assert.equal(expected.expectations[0].pass, false);
  assert.equal(expected.exitCode, 1);
  // A settle time that is shown but not judged is marked and stays an entry.
  const nav = cmp(
    series(
      (r) => setT(r, "files.a", { navSettledMs: 300, windowMs: 450 }),
      (r) => setT(r, "files.a", { navSettledMs: 100, windowMs: 250 }),
    ),
  );
  const ne = find(nav, "files.a", "nav_settled_ms");
  assert.equal(ne.windowCut, true);
  assert.notEqual(ne.outcome, "window");
  assert.ok(!nav.gaps.some((g) => g.metric === "nav_settled_ms"));
});
check("a settle time beyond the control's window is marked too", () => {
  // The mirror of the check above (review C, C3): the candidate is ready later and watched
  // longer, so its higher settle time may be only the longer window.
  const res = cmp(
    series(
      (r) => setT(r, "files.a", { settledMs: 120, windowMs: 250 }),
      (r) => setT(r, "files.a", { settledMs: 650, windowMs: 800 }),
    ),
  );
  const e = find(res, "files.a", "settled_ms");
  assert.equal(e.windowCut, true);
  assert.equal(e.outcome, "window");
  assert.match(
    e.verdict,
    /the candidate settled at 650\.0 ms, after the control's shortest window \(250\.0 ms\) closed/,
  );
});
check("equal medians with a pair beyond each way name both pairs", () => {
  const res = cmp(
    series(
      (r, k) => setT(r, "files.a", { paintedReadyMs: [40, 50, 60][k - 1] }),
      (r, k) => setT(r, "files.a", { paintedReadyMs: [60, 50, 40][k - 1] }),
    ),
  );
  const e = find(res, "files.a", "painted_ready_ms");
  assert.equal(e.direction, "same");
  assert.equal(e.outcome, "pair");
  assert.equal(e.wrongWay, false);
  assert.match(e.verdict, /one pair of 3 is higher and one lower .*higher s1#1; lower s1#3/);
  assert.doesNotMatch(e.verdict, /same beyond/);
  const text = stats.formatComparison(res).join("\n");
  assert.match(text, /1 higher and 1 lower of 3 beyond/);
});
check("pairs beyond the tolerance count in either direction, whatever the medians do", () => {
  // Review C of #442, C1's four fixtures: each has two pairs worse beyond the tolerance,
  // which the runbook says must be explained, and each read "no detected difference" or
  // was not wrong way.
  const values = (as, bs) =>
    series(
      (r, k) => setT(r, "files.a", { paintedReadyMs: as[k - 1] }),
      (r, k) => setT(r, "files.a", { paintedReadyMs: bs[k - 1] }),
      as.length,
    );
  for (const [label, as, bs, pairs] of [
    ["1, the median 1% lower", [10, 10, 100, 100, 100], [20, 20, 99, 99, 99], "s1#1, s1#2"],
    ["2, three pairs", [10, 20, 100], [13, 26, 15], "s1#1, s1#2"],
    [
      "3, equal medians, two each way",
      [10, 10, 100, 200, 200],
      [20, 20, 100, 100, 100],
      "s1#1, s1#2",
    ],
  ]) {
    const res = cmp(values(as, bs));
    const e = find(res, "files.a", "painted_ready_ms");
    assert.equal(e.outcome, "explain", `${label}: ${e.verdict}`);
    assert.equal(e.wrongWay, true, label);
    assert.match(e.verdict, new RegExp(`higher ${pairs}`), label);
    assert.equal(res.exitCode, 1, label);
  }
  // The median's direction is still the medians': fixture 1's is lower.
  assert.equal(
    find(cmp(values([10, 10, 100, 100, 100], [20, 20, 99, 99, 99])), "files.a", "painted_ready_ms")
      .direction,
    "lower",
  );
  // 4: two complete pairs, both 1.5x higher, each side with one run whose partner was
  // refused, under overlapping ranges.
  const rows = [row("a", 1), row("b", 1), row("a", 2), row("b", 2), row("a", 3), row("b", 4)];
  for (const [r, v] of rows.map((r, i) => [r, [100, 150, 100, 150, 300, 90][i]])) {
    setT(r, "files.a", { paintedReadyMs: v });
  }
  const four = cmp(rows);
  const e4 = find(four, "files.a", "painted_ready_ms");
  assert.equal(e4.outcome, "explain", e4.verdict);
  assert.equal(e4.wrongWay, true);
  assert.equal(four.exitCode, 1);
  // One worse pair of two, under overlapping ranges: the tolerance cannot be judged.
  const one = rows.map((r) => structuredClone(r));
  setT(one[3], "files.a", { paintedReadyMs: 100 });
  const e1 = find(cmp(one), "files.a", "painted_ready_ms");
  assert.equal(e1.outcome, "unpaired", e1.verdict);
  // Two pairs beyond in the better direction must be explained too, and are not wrong way.
  const better = find(
    cmp(values([20, 20, 100, 100, 100], [10, 10, 101, 101, 101])),
    "files.a",
    "painted_ready_ms",
  );
  assert.deepEqual([better.outcome, better.wrongWay], ["explain", false]);
});
check("an expectation met in a metric's worse direction does not fail the exit", () => {
  // Review C of #442, C7: a round that predicts a cost it accepts.
  const rows = series(
    (r) => setT(r, "files.a", { requests: { byClass: { data: 2 } } }),
    (r) => setT(r, "files.a", { requests: { byClass: { data: 3 } } }),
  );
  const met = cmp(rows, { expect: ["files.a:requests_data:higher"] });
  assert.equal(met.expectations[0].pass, true);
  assert.equal(met.wrongWay.length, 0);
  assert.deepEqual(
    met.expected.map((e) => `${e.id} ${e.metric}`),
    ["files.a requests_data"],
  );
  assert.equal(met.exitCode, 0);
  const text = stats.formatComparison(met).join("\n");
  assert.match(text, /\[WRONG WAY, EXPECTED\]/);
  assert.match(text, /Exit 0: complete, with no wrong-way result but the 1 an expectation met/);
  // Unexpected, the same movement still fails.
  assert.equal(cmp(rows).exitCode, 1);
});
check("a journey's end reading is compared on its memory alone", () => {
  const withMemory = (heap) => (r, k) => {
    r.journeys[0].memory = {
      jsHeapUsedKb: heap + k,
      domNodes: 5000,
      workerHeapUsedKb: 900,
      listeners: 40,
      documents: 1,
    };
  };
  const res = cmp(series(withMemory(9000), withMemory(15000)));
  const heap = find(res, "files.end", "memory_js_heap_kb");
  // Report-only (review A of #442, A2): apart, and shown, but neither judged nor a
  // wrong-way result, until a round's protocol registers a budget to judge it against.
  assert.equal(heap.outcome, "result");
  assert.equal(heap.judged, false);
  assert.equal(heap.wrongWay, false);
  assert.equal(res.exitCode, 0);
  assert.equal(find(res, "files.end", "painted_ready_ms"), undefined);
  assert.equal(find(res, "files.end", "requests_data"), undefined);
  assert.equal(res.gaps.filter((g) => g.id === "files.end").length, 0, JSON.stringify(res.gaps));
  for (const key of ["memory_dom_nodes", "memory_worker_heap_kb", "memory_listeners"]) {
    assert.equal(find(res, "files.end", key).judged, false, key);
  }
  // A reading that failed in one run is a missing value, not a smaller sample; it is named
  // in a note and does not make the comparison incomplete.
  const failed = cmp(
    series(withMemory(9000), (r, k) => {
      withMemory(9000)(r, k);
      if (k === 2) {
        r.journeys[0].memory = null;
      }
    }),
  );
  assert.equal(failed.gaps.length, 0, JSON.stringify(failed.gaps));
  assert.equal(failed.exitCode, 0);
  assert.ok(
    failed.notes.some((n) =>
      /^MEMORY READINGS MISSING.*files\.end memory_dom_nodes: missing in 0 of 3 a run\(s\) and 1 of 3 b/.test(
        n,
      ),
    ),
    JSON.stringify(failed.notes),
  );
  const text = summarize(series(withMemory(9000), withMemory(15000))).join("\n");
  assert.match(text, /#### Retained memory, after a garbage collection/);
  assert.match(text, /\| `files\.end` \| 9001–9003 \|/);
  assert.doesNotMatch(text.split("#### Retained")[0], /files\.end/);
  // Samples keep the reading, and a transition's own.
  const r = row("a", 1);
  withMemory(9000)(r, 1);
  setT(r, "files.a", { memory: { domNodes: 7 }, readCostMaxMs: 0.4 });
  const s = sampleRow(r);
  assert.equal(s.journeys[0].memory.jsHeapUsedKb, 9001);
  assert.equal(s.journeys[0].transitions[0].memory.domNodes, 7);
  assert.equal(s.journeys[0].transitions[0].readCostMaxMs, 0.4);
});
check("memory read between transitions is not the standard regime", () => {
  const flagged = (r) => {
    r.regime_flags.memory_after = ["files.a"];
  };
  const res = cmp(series(flagged, flagged));
  assert.ok(res.notes.some((n) => /NOT THE STANDARD REGIME: memory read after files\.a/.test(n)));
  refuses(() => cmp(series(() => {}, flagged)), /regime/);
});
check("truncated searches and slow reads are counted and reported", () => {
  const frames = [
    [100, "", 102, 0.3, 1, 0],
    [100 + I, "", 102 + I, 5.2, 1, 1],
    [100 + 2 * I, "U", 102 + 2 * I, 5.6, 1, 1],
  ];
  const a = accountFrames({
    frames,
    origin: 99,
    windowEnd: frames.at(-1)[0],
    readyAt: frames[2][0],
    readyRead: frames[2][2],
    readyNext: null,
  });
  assert.equal(a.searchTruncatedFrames, 2);
  assert.equal(a.readCostMaxMs, 5.6);
  // compare and summarize name a transition whose read passed the ceiling or whose search
  // was cut, on either side.
  const slow = (r) => setT(r, "files.a", { readCostMaxMs: 5.6, searchTruncatedFrames: 2 });
  const res = cmp(series(() => {}, slow));
  assert.equal(stats.READ_COST_CEILING_MS, 4);
  assert.ok(
    res.notes.some((n) =>
      /^INSTRUMENT COST: in condition b.*files\.a \(longest read 5\.6 ms\)/.test(n),
    ),
    res.notes,
  );
  assert.ok(
    res.notes.some((n) =>
      /^SEARCH TRUNCATED: in condition b.*files\.a \(6 frame\(s\) in 3 run/.test(n),
    ),
  );
  assert.ok(!res.notes.some((n) => /in condition a/.test(n) && /INSTRUMENT|TRUNCATED/.test(n)));
  const text = summarize(series(() => {}, slow)).join("\n");
  assert.match(text, /instrument cost over 4 ms in `files\.a` \(longest read 5\.6 ms\)/);
});
check("a transition's metrics are not judged where a search was cut", () => {
  // The candidate's arm check stopped at its bound in every run, and it reads worse: the
  // transition should perhaps have been refused, so every judged metric is a gap with the
  // reason, not a wrong-way result; the other transition is judged as before.
  const cut = (r) =>
    setT(r, "files.a", { searchTruncatedBeforeInput: 1, paintedReadyMs: 90, blankFrames: 3 });
  const res = cmp(series(() => {}, cut));
  for (const key of ["painted_ready_ms", "blank_frames", "requests_data", "settled_ms"]) {
    const e = find(res, "files.a", key);
    assert.equal(e.outcome, "truncated", key);
    assert.equal(e.wrongWay, false, key);
    assert.match(
      e.verdict,
      /^not judged: the content search stopped at its hit-test bound in 0 a and 3 b frame\(s\) before the input/,
    );
    assert.ok(res.gaps.some((g) => g.id === "files.a" && g.metric === key));
  }
  // Shown figures stay shown.
  assert.equal(find(res, "files.a", "next_frame_ms").outcome, "none");
  assert.equal(find(res, "files.b", "painted_ready_ms").outcome, "none");
  assert.equal(res.wrongWay.length, 0);
  assert.equal(res.exitCode, 1);
  // Review A of #442, A1: a search cut up to the ready frame can find readiness late, and
  // the window's end with it, so the settle time, the longest task, and the counts are
  // gaps too, but not a milestone, which has its own count.
  const late = cmp(
    series(
      (r) => setT(r, "files.a", { milestones: { prHeader: 30 } }),
      (r) =>
        setT(r, "files.a", {
          searchTruncatedFrames: 2,
          searchTruncatedToReady: 1,
          settledMs: 400,
          longTasks: { maxMs: 120 },
          milestones: { prHeader: 30 },
        }),
    ),
  );
  for (const key of ["settled_ms", "long_task_max_ms", "painted_ready_ms", "requests_data"]) {
    const e = find(late, "files.a", key);
    assert.equal(e.outcome, "truncated", key);
    assert.match(e.verdict, /0 a and 3 b frame\(s\) up to the ready frame/, key);
  }
  assert.equal(find(late, "files.a", "pr_header_ms").outcome, "none");
  // Cut only after the ready frame: the blank counts are gaps, readiness and the rest are
  // judged.
  const after = cmp(
    series(
      () => {},
      (r) =>
        setT(r, "files.a", {
          searchTruncatedFrames: 1,
          searchTruncatedToReady: 0,
          longTasks: { maxMs: 120 },
        }),
    ),
  );
  for (const key of ["blank_frames", "blank_frames_after_ready", "blank_ms"]) {
    const e = find(after, "files.a", key);
    assert.equal(e.outcome, "truncated", key);
    assert.match(e.verdict, /0 a and 3 b frame\(s\) after the ready frame/, key);
  }
  assert.equal(find(after, "files.a", "painted_ready_ms").outcome, "none");
  assert.equal(find(after, "files.a", "long_task_max_ms").outcome, "result");
  assert.equal(find(after, "files.a", "long_task_max_ms").wrongWay, true);
  // A search cut while a milestone was awaited (review B of #442, B4): that milestone is a
  // gap, the transition's other metrics are judged, and the read is named.
  const milestone = cmp(
    series(
      (r) =>
        setT(r, "files.a", {
          milestones: { sourceHighlighted: 600 },
          milestoneReads: { sourceHighlighted: { maxMs: 1.1, toMs: 9, truncated: 0 } },
        }),
      (r) =>
        setT(r, "files.a", {
          milestones: { sourceHighlighted: 900 },
          milestoneReads: { sourceHighlighted: { maxMs: 6.3, toMs: 40, truncated: 2 } },
          searchTruncatedAfterWindow: 2,
        }),
    ),
  );
  const m = find(milestone, "files.a", "source_highlighted_ms");
  assert.equal(m.outcome, "truncated");
  assert.match(m.verdict, /0 a and 6 b frame\(s\) up to this milestone/);
  assert.equal(find(milestone, "files.a", "painted_ready_ms").outcome, "none");
  assert.ok(
    milestone.notes.some((n) =>
      /^INSTRUMENT COST: in condition b.*files\.a \(longest read 6\.3 ms before a milestone\)/.test(
        n,
      ),
    ),
    milestone.notes,
  );
  assert.ok(
    milestone.notes.some((n) => /^SEARCH TRUNCATED: in condition b.*files\.a \(6 frame/.test(n)),
  );
  // The frames before the input are counted apart from the window's.
  const a = accountFrames({
    frames: [
      [90, "", 91, 4.1, 0, 1],
      [100, "U", 101, 0.3, 1, 0],
    ],
    origin: 95,
    windowEnd: 100,
    readyAt: 100,
    readyRead: 101,
    readyNext: null,
  });
  assert.deepEqual([a.searchTruncatedBeforeInput, a.searchTruncatedFrames], [1, 0]);
});
check("revision 5 rows compare with each other, noting what revision 6 changed", () => {
  const five = (r) => {
    r.scenario_revision = 5;
  };
  const res = cmp(series(five, five));
  assert.equal(stats.SCENARIO_REVISION, 6);
  assert.ok(
    res.notes.some((n) => /revision 5, compared with each other.*input's own frame/.test(n)),
  );
  refuses(() => cmp(series(() => {}, five)), /scenario revision differs across the runs: 6 \/ 5/);
});
check("an older revision compares with itself, with a note, and not with this one", () => {
  const old = cmp(
    series(
      (r) => {
        r.scenario_revision = 3;
      },
      (r) => {
        r.scenario_revision = 3;
      },
    ),
  );
  assert.ok(old.notes.some((n) => /revision 3, compared with each other.*worker/.test(n)));
  refuses(
    () =>
      cmp(
        series(
          () => {},
          (r) => {
            r.scenario_revision = 3;
          },
        ),
      ),
    /scenario revision/,
  );
});
// Main's 19a36c5b made a switch to Commits land on the newest commit (revision 5).
const landed = (...landings) => [
  {
    name: "maintabs",
    transitions: [
      transition("files.a"),
      ...landings.map((landing, i) => transition(`main.to_commits.${i}`, { landing })),
    ],
  },
];
check("the Commits landing a run saw", () => {
  assert.equal(commitsLandingOf(landed()), null);
  assert.equal(commitsLandingOf(landed("newest", "newest")), "newest");
  // A switch back to Commits before 19a36c5b showed the commit read before.
  assert.equal(commitsLandingOf(landed("empty", "restored")), "empty");
  assert.equal(commitsLandingOf(landed("empty", "newest")), "mixed");
  assert.equal(commitsLandingOf(landed("other 2222")), "mixed");
  // A transition that was never ready saw no landing.
  assert.equal(commitsLandingOf(landed("newest", null)), "newest");
});
check("runs that saw different Commits landings are compared only when asked", () => {
  const before = (r) => {
    r.commits_landing = "empty";
  };
  const after = (r) => {
    r.commits_landing = "newest";
  };
  refuses(() => cmp(series(before, after)), /Commits landing differs/);
  refuses(() => cmp(series(() => {}, after)), /Commits landing differs/);
  const allowed = cmp(series(before, after), { mixedLanding: true });
  assert.ok(
    allowed.notes.some((n) => /^MIXED COMMITS LANDINGS/.test(n)),
    allowed.notes,
  );
  const same = cmp(series(after, after));
  assert.ok(
    same.notes.some((n) => /landed on the newest commit/.test(n)),
    same.notes,
  );
  assert.equal(
    cmp(series()).notes.some((n) => /Commits/.test(n)),
    false,
    "runs with no Commits switch have no landing note",
  );
});
check("samples keep each Commits landing", () => {
  const r = row("a", 1, { commits_landing: "newest", journeys: landed("newest") });
  const s = sampleRow(r);
  assert.equal(s.commits_landing, "newest");
  assert.equal(s.journeys[0].transitions[1].landing, "newest");
  assert.equal(commitsLandingOf(s.journeys), "newest");
});
// Review A of #417: two `mixed` runs can still differ in which switch landed where.
check("runs whose switches to Commits landed differently are refused per transition", () => {
  const mixedA = (r) => {
    r.commits_landing = "mixed";
    r.journeys = landed("empty", "newest");
  };
  const mixedB = (r) => {
    r.commits_landing = "mixed";
    r.journeys = landed("newest", "empty");
  };
  assert.deepEqual(landingDrift(series(mixedA, mixedB)), [
    "main.to_commits.0: empty / newest",
    "main.to_commits.1: newest / empty",
  ]);
  refuses(
    () => cmp(series(mixedA, mixedB)),
    /per transition, main\.to_commits\.0: empty \/ newest/,
  );
  const allowed = cmp(series(mixedA, mixedB), { mixedLanding: true });
  assert.ok(
    allowed.notes.some((n) => /per transition main\.to_commits\.0/.test(n)),
    allowed.notes,
  );
  assert.deepEqual(landingDrift(series(mixedA, mixedA)), []);
});
check("summarize names each condition's Commits landing and any drift", () => {
  const rows = series(
    (r, k) => {
      r.commits_landing = "newest";
      r.journeys = landed(k === 1 ? "empty" : "newest");
    },
    (r) => {
      r.commits_landing = "newest";
      r.journeys = landed("newest");
    },
  );
  const text = summarize(rows).join("\n");
  assert.match(text, /switches to Commits landed newest\./);
  assert.match(text, /landing drift in `main\.to_commits\.0`: empty \/ newest/);
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

check("compare exits 0, 1, 2, and 3 from the command line", () => {
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
    // Review C of #442, C9: a defect is not a refusal.
    const broken = series();
    broken[0].journeys[0].transitions.push(null);
    const crashed = run(write("broken.jsonl", broken), "--control", "a", "--candidate", "b");
    assert.equal(crashed.status, 3, crashed.stderr);
    assert.match(crashed.stderr, /compare failed: TypeError/);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

// ------------------------------------------------------------------- process cleanup
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

{
  const originalFetch = globalThis.fetch;
  const fetchAt = "2026-11-26T21:00:00Z";
  const absent = { refreshable: false, refreshing: false, last_fetch_at: null, stale: false };
  const warming = { refreshable: true, refreshing: true, last_fetch_at: fetchAt, stale: false };
  const warm = { ...warming, refreshing: false };
  const statuses = [absent, warming, warm];
  const urls = [];
  try {
    globalThis.fetch = async (url) => {
      urls.push(url);
      return { ok: true, json: async () => statuses.shift() ?? absent };
    };
    const result = await waitForOriginStore(B, 5000);
    const refused = await waitForOriginStore(B, 10);
    check("origin warm-up observes state and refuses without a fresh completed fetch", () => {
      assert.equal(result.ready, true);
      assert.equal(result.last_fetch_at, fetchAt);
      assert.equal(refused.ready, false);
      assert.equal(refused.last_fetch_at, null);
      assert.ok(urls.length >= 4);
      assert.ok(urls.every((url) => url === `${B}/api/source/status`));
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
}

console.log(`transitions instrument: ${checks} checks passed`);
