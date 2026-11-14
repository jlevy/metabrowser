// Changed-files prefetch in the Pulls panel: the rows a reader is likely to expand, those in
// view and the one the pointer or focus rests on, have their lists read behind the reader, so a
// first expansion draws from the cache. The exact production panel and file-tree controllers
// run on a virtual clock, as tests/dom/github-pr-prefetch-behavior.js runs the panel's metadata
// preparation, against a stand-in server: its prefetch lane reads one list at a time, a
// GitHub list takes LIST_MS, a reader's own list starts at once, and the budget's floor is a
// switch. The rows are the recorded Pulls answer's; the lists are the recorded route's shape.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = path.resolve(__dirname, "../..");
const panelAnswer = require("../fixtures/github-pulls-panel-responses.json").open_current.body;
const filesAnswers = require("../fixtures/github-pull-files-responses.json");

const PREFETCH = "/api/plugin/github/pulls-prefetch";
const FILES = "/api/plugin/github/pull-files";
const FILES_REFRESH = "/api/plugin/github/pull-files-refresh";
const CORES = "/api/plugin/github/pull-cores-prepare";
// What one GitHub list of one page takes: 1.2 to 1.6 s a page was measured on a real pull
// request (pull-files-tree.js, FILES_POLL_MS), and 2 to 5 s a list (LATE_ROWS_MS).
const LIST_MS = 1500;
// What GitHub takes for a batch of the rows' metadata, when the cache lacks it.
const CORE_MS = 2000;

const rows = panelAnswer.rows.map((row) => JSON.parse(row));

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** A GitHub list of *number*'s changed files, as the route answers a cached one. */
function listOf(number) {
  const base = filesAnswers["same second before"];
  const paths = [`src/part-${number}.txt`, "docs/guide.md"];
  return {
    ...base,
    number,
    generation: String(number).padStart(32, "0"),
    fetched: paths.length,
    limit: 3000,
    rows: paths.map((file) => ({
      path: file,
      previous_path: null,
      status: "modified",
      additions: 1,
      deletions: 0,
      display: file,
      previous_display: null,
    })),
  };
}

function rig({ coldCores = false, belowFloor = false, holdPrefetch = false } = {}) {
  let now = 0;
  let serial = 0;
  /** @type {Map<number, {fn: () => void, at: number}>} */
  const timers = new Map();
  const schedule = (fn, delay) => {
    serial += 1;
    timers.set(serial, { fn, at: now + delay });
    return serial;
  };
  const server = {
    belowFloor,
    holdPrefetch,
    /** Numbers whose list is cached. */
    lists: new Set(),
    /** Lists GitHub is reading now, by number, and for whom. */
    jobs: new Map(),
    /** Every list GitHub was asked for: when, which, and for whom. */
    gh: [],
    lane: { queue: [], running: null },
    coresCached: new Set(coldCores ? [] : rows.map((row) => row.number)),
    coreJobs: new Map(),
    /** Every request, with when it was made. */
    requests: [],
    /** Prefetch POSTs left unanswered while `holdPrefetch` is set. */
    held: [],
  };

  /** Start GitHub's read of *number*'s list; *done* runs when it is cached. */
  function startList(number, by, done = () => {}) {
    server.gh.push({ at: now, number, by });
    server.jobs.set(number, by);
    schedule(() => {
      server.jobs.delete(number);
      server.lists.add(number);
      done();
    }, LIST_MS);
  }

  /** The lane: one list at a time, each read again before it runs, stopping at the floor. */
  function runLane() {
    const lane = server.lane;
    while (lane.running === null && lane.queue.length > 0) {
      if (server.belowFloor) {
        lane.queue = [];
        return;
      }
      const number = lane.queue.shift();
      if (server.lists.has(number) || server.jobs.has(number)) {
        continue;
      }
      lane.running = number;
      startList(number, "prefetch", () => {
        lane.running = null;
        runLane();
      });
    }
  }

  function filesEnvelope(number) {
    if (server.lists.has(number)) {
      return listOf(number);
    }
    const absent = filesAnswers.absent;
    return server.jobs.has(number)
      ? { ...filesAnswers.pending, number, rows: [] }
      : { ...absent, number, rows: [] };
  }

  async function request(method, route, options = {}) {
    server.requests.push({ at: now, method, route, body: options.body ?? null });
    const url = new URL(route, "http://localhost");
    if (url.pathname === PREFETCH && method === "POST") {
      if (server.belowFloor) {
        return {
          status: 200,
          etag: null,
          body: { prefetch: "deferred", queued: 0, reason: "below_floor" },
        };
      }
      const answer = () => {
        server.lane.queue = [...options.body.files];
        const started = server.lane.running === null ? "started" : "joined";
        runLane();
        return { status: 202, etag: null, body: { prefetch: started, queued: 1 } };
      };
      if (server.holdPrefetch) {
        return new Promise((resolve) => server.held.push(() => resolve(answer())));
      }
      return answer();
    }
    if (url.pathname === PREFETCH) {
      const lane = server.lane;
      return {
        status: 200,
        etag: null,
        body: {
          running: lane.running === null ? null : { kind: "files", number: lane.running },
          queued: lane.queue.map((number) => ({ kind: "files", number })),
          governor: { admits: !server.belowFloor },
          files: { per_hour: 100, hour_used: 0 },
        },
      };
    }
    if (url.pathname === CORES) {
      const numbers = options.body.numbers;
      if (numbers.length === 0) {
        return { status: 200, etag: null, body: { preparation: "released" } };
      }
      const missing = numbers.filter((number) => !server.coresCached.has(number));
      if (missing.length === 0) {
        return {
          status: 200,
          etag: null,
          body: { preparation: "ready", ready_numbers: numbers, skipped_numbers: [] },
        };
      }
      const key = missing.join(",");
      if (!server.coreJobs.has(key)) {
        server.coreJobs.set(key, now);
        schedule(() => {
          for (const number of missing) {
            server.coresCached.add(number);
          }
          server.coreJobs.delete(key);
        }, CORE_MS);
      }
      return { status: 202, etag: null, body: { preparation: "joined" } };
    }
    if (url.pathname === FILES && method === "GET") {
      const envelope = filesEnvelope(Number(url.searchParams.get("number")));
      const offset = Number(url.searchParams.get("offset") ?? 0);
      return {
        status: 200,
        etag: null,
        body: { ...envelope, offset, rows: envelope.rows.slice(offset) },
      };
    }
    if (url.pathname === FILES_REFRESH) {
      const number = options.body.number;
      if (server.lists.has(number)) {
        return {
          status: 200,
          etag: null,
          body: { refresh: "not_due", files: { ...listOf(number), limit: 0, rows: [] } },
        };
      }
      const joined = server.jobs.has(number);
      if (!joined) {
        startList(number, "reader");
      }
      return {
        status: 202,
        etag: null,
        body: { refresh: joined ? "joined" : "started", files: filesEnvelope(number) },
      };
    }
    if (url.pathname.endsWith("/pull")) {
      return { status: 404, etag: null, body: null };
    }
    if (method === "POST") {
      return { status: 200, etag: null, body: { pulls: { ...panelAnswer, rows } } };
    }
    return { status: 200, etag: null, body: { ...panelAnswer, rows } };
  }

  const opened = [];
  return {
    server,
    now: () => now,
    timers,
    deps: {
      request,
      schedule,
      cancel: (id) => timers.delete(id),
      now: () => now,
      isVisible: () => true,
      isOnline: () => true,
      formatTime: (at) => at,
      render() {},
      markCurrent() {},
      markAnchor() {},
      reveal() {},
      open(route) {
        opened.push(route.number);
      },
      filterChanged() {},
    },
    /** The reader's tree of *number*'s files, with when its rows were first drawn. */
    tree(module, number) {
      const tree = { drawnAt: null, model: null };
      tree.controller = module.createFileTreeController(
        {
          request,
          schedule,
          cancel: (id) => timers.delete(id),
          now: () => now,
          isVisible: () => true,
          formatTime: (at) => at,
          render(model) {
            tree.model = model;
            if (
              tree.drawnAt === null &&
              model.expanded &&
              !model.opening &&
              model.rows.length > 0
            ) {
              tree.drawnAt = now;
            }
          },
          markAnchor() {},
          markCurrent() {},
          markMuted() {},
          page: () => null,
          open() {},
          leave() {},
          lastInput: () => null,
          held() {},
        },
        { number, autoExpandFiles: 3000 },
      );
      return tree;
    },
    /** Run every timer due within *ms*, in order, then stand at the end of it. */
    async advance(ms) {
      const end = now + ms;
      for (;;) {
        await settle();
        const due = [...timers.entries()]
          .filter(([, timer]) => timer.at <= end)
          .sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
        if (due === undefined) {
          break;
        }
        timers.delete(due[0]);
        now = Math.max(now, due[1].at);
        due[1].fn();
      }
      now = end;
      await settle();
    },
    /** Where the requests made so far end, for `asks` to start from. */
    mark: () => server.requests.length,
    /** The prefetch asks made since *mark*, with their time and the files they name. */
    asks(mark = 0) {
      return server.requests
        .slice(mark)
        .filter((entry) => entry.route === PREFETCH && entry.method === "POST")
        .map((entry) => ({ at: entry.at, files: entry.body.files }));
    },
    async release() {
      for (const answer of server.held.splice(0)) {
        answer();
      }
      await settle();
    },
  };
}

(async () => {
  const panel = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pulls-panel.js")).href
  );
  const treeModule = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-files-tree.js"))
      .href
  );
  const numbers = rows.map((row) => row.number);
  // A list pane of twenty rows: the rows in view, top first.
  const inView = numbers.slice(0, 20);
  const facts = {};

  // ── A visible row's files are prefetched ─────────────────────
  // The panel shows its first twenty rows. Once they stay put, it names their files, up to
  // the sixteen one ask may name, and the lane reads them one at a time behind the reader.
  const seen = rig();
  const controller = panel.createPullsController(seen.deps, { filter: "open" });
  await controller.start({ shown: true });
  await seen.advance(0);
  const shownAt = seen.now();
  const shownMark = seen.mark();
  controller.prepareVisible(inView);
  await seen.advance(panel.FILES_DWELL_MS - 1);
  facts.asksBeforeDwell = seen.asks(shownMark).length;
  await seen.advance(1);
  const visibleAsk = seen.asks(shownMark)[0];
  assert(visibleAsk !== undefined, "the rows in view have their files asked for");
  facts.visibleAsk = { afterMs: visibleAsk.at - shownAt, files: visibleAsk.files };
  assert.equal(facts.asksBeforeDwell, 0);
  assert.equal(visibleAsk.at - shownAt, panel.FILES_DWELL_MS);
  assert.equal(visibleAsk.files.length, panel.PREFETCH_FILES);
  assert(visibleAsk.files.every((number) => inView.includes(number)));
  // The pointer rests on the eighteenth row, past what the first ask named: it is asked
  // for at once, first, and read next.
  await seen.advance(2 * LIST_MS);
  const rested = inView[17];
  const restedFrom = seen.now();
  const restedMark = seen.mark();
  // The lists started so far, the last of them still being read.
  const startedBefore = seen.server.gh.length;
  controller.peek(rested);
  await seen.advance(0);
  const restedAsk = seen.asks(restedMark)[0];
  facts.restedAsk = { afterMs: restedAsk.at - restedFrom, first: restedAsk.files[0] };
  assert.equal(restedAsk.files[0], rested);
  await seen.advance(20 * LIST_MS);
  facts.listed = seen.server.gh.map((read) => `${read.number} by ${read.by}`);
  assert.deepEqual(
    seen.server.gh.map((read) => read.by),
    seen.server.gh.map(() => "prefetch"),
  );
  assert.equal(
    seen.server.gh[startedBefore].number,
    rested,
    "the rested row is read as soon as the list being read ends",
  );
  assert.equal(seen.server.lane.running, null, "the lane ends with the rows asked for");

  // ── An expansion after prefetch draws with no request ────────
  // The reader expands the sixth row in view: its first read of the list finds it cached, so
  // the tree opens with its rows at the click's own time, asks for no refresh, and GitHub is
  // not read for it. A row out of view, never rested on, is the reader's own first read.
  async function expand(rigged, number) {
    const from = rigged.now();
    const ghBefore = rigged.server.gh.length;
    const tree = rigged.tree(treeModule, number);
    tree.controller.expand();
    controller.activate(number);
    await rigged.advance(0);
    for (let step = 0; step < 20 && tree.drawnAt === null; step += 1) {
      await rigged.advance(250);
    }
    const asked = rigged.server.requests.filter(
      (entry) => entry.at >= from && entry.route.startsWith(FILES),
    );
    const result = {
      drawnAfterMs: tree.drawnAt === null ? null : tree.drawnAt - from,
      rows: tree.model?.rows.length ?? 0,
      refreshAsks: asked.filter((entry) => entry.route === FILES_REFRESH).length,
      githubReads: rigged.server.gh
        .slice(ghBefore)
        .filter((read) => read.number === number)
        .map((read) => read.by),
    };
    tree.controller.dispose();
    return result;
  }
  facts.expandedAfterPrefetch = await expand(seen, inView[5]);
  assert.deepEqual(facts.expandedAfterPrefetch, {
    drawnAfterMs: 0,
    // Two files, each in its folder.
    rows: 4,
    refreshAsks: 0,
    githubReads: [],
  });
  const outOfView = numbers.find(
    (number) => !inView.includes(number) && !seen.server.lists.has(number),
  );
  facts.expandedOutOfView = await expand(seen, outOfView);
  assert.equal(facts.expandedOutOfView.refreshAsks, 1);
  assert.deepEqual(facts.expandedOutOfView.githubReads, ["reader"]);
  assert(facts.expandedOutOfView.drawnAfterMs >= LIST_MS);
  controller.dispose();

  // ── Prefetch stops below the budget floor ───────────────────
  // The account is below the floor: the server refuses the first ask, the scan's, from
  // memory, and the panel asks nothing more for a slow poll, however the rows in view and the
  // pointer move. Once the budget is back and the hold is over, the next row rested on is
  // asked for and read.
  const low = rig({ belowFloor: true });
  const starved = panel.createPullsController(low.deps, { filter: "open" });
  await starved.start({ shown: true });
  await low.advance(0);
  starved.prepareVisible(inView);
  await low.advance(panel.FILES_DWELL_MS);
  for (const number of inView.slice(0, 6)) {
    starved.peek(number);
    await low.advance(1000);
  }
  facts.belowFloor = {
    asks: low.asks().length,
    githubReads: low.server.gh.length,
  };
  assert.deepEqual(facts.belowFloor, { asks: 1, githubReads: 0 });
  low.server.belowFloor = false;
  await low.advance(30_000);
  const back = low.mark();
  starved.peek(inView[9]);
  await low.advance(LIST_MS);
  facts.afterFloor = {
    asks: low.asks(back).length,
    firstRead: low.server.gh[0]?.number ?? null,
  };
  assert.deepEqual(facts.afterFloor, { asks: 1, firstRead: inView[9] });
  starved.dispose();

  // ── Prefetch never delays a reader's request ─────────────────
  // The rows in view lack their metadata, which GitHub reads for the reader while their titles
  // breathe: no list is asked for, or read, until those batches settle.
  const cold = rig({ coldCores: true });
  const waiting = panel.createPullsController(cold.deps, { filter: "open" });
  await waiting.start({ shown: true });
  await cold.advance(0);
  const coldFrom = cold.now();
  const coldMark = cold.mark();
  // The scan's own ask, before the rows came into view, named the anchored row's neighbour.
  const readsBefore = cold.server.gh.length;
  waiting.prepareVisible(inView.slice(0, 16));
  await cold.advance(20_000);
  const settled = cold.server.requests
    .filter((entry) => entry.route === CORES && entry.body.numbers.length > 0)
    .at(-1).at;
  const firstFiles = cold.asks(coldMark)[0];
  facts.behindMetadata = {
    metadataSettledMs: settled - coldFrom,
    filesAskedMs: firstFiles === undefined ? null : firstFiles.at - coldFrom,
    listsBeforeSettled: cold.server.gh.slice(readsBefore).filter((read) => read.at < settled)
      .length,
  };
  assert(firstFiles !== undefined, "the files are asked for once the metadata settles");
  assert(facts.behindMetadata.filesAskedMs >= facts.behindMetadata.metadataSettledMs);
  assert.equal(facts.behindMetadata.listsBeforeSettled, 0);
  waiting.dispose();

  // A held key walks the rows past the moment the rows in view would be asked for: no files
  // ask is sent while it walks, and the landing's, once it stops, names them too. A prefetch the server has not answered holds up none of the reader's reads: a
  // click reads its record and its tree's list at once.
  const walked = rig({ holdPrefetch: true });
  const walker = panel.createPullsController(walked.deps, { filter: "open" });
  await walker.start({ shown: true });
  await walked.advance(0);
  await walked.release();
  walked.server.holdPrefetch = false;
  walker.prepareVisible(inView);
  walker.setCurrent(inView[0]);
  await walked.advance(panel.FILES_DWELL_MS - 100);
  const walkFrom = walked.mark();
  for (let step = 0; step < 8; step += 1) {
    walker.move(1, { repeat: true });
    await walked.advance(50);
  }
  facts.asksDuringWalk = walked.asks(walkFrom).length;
  await walked.advance(panel.WALK_SETTLE_MS + panel.OPEN_WAIT_MS);
  const landing = walked.asks(walkFrom);
  facts.asksOnceStopped = landing.length;
  assert.equal(facts.asksDuringWalk, 0);
  assert.equal(landing.length, 1);
  assert(inView.slice(10, 16).every((number) => landing[0].files.includes(number)));
  walked.server.holdPrefetch = true;
  walker.peek(inView[14]);
  // A press follows the pointer's rest by about 200 ms.
  await walked.advance(200);
  assert.equal(walked.server.held.length, 1, "the rested row's ask is on its way, unanswered");
  const clickAt = walked.now();
  const tree = walked.tree(treeModule, inView[14]);
  tree.controller.expand();
  walker.activate(inView[14]);
  await walked.advance(0);
  facts.readerReadsWhileAskHeld = walked.server.requests
    .filter((entry) => entry.at === clickAt && entry.method === "GET")
    .map((entry) => `${entry.route.split("?")[0].replace("/api/plugin/github/", "")} +0 ms`);
  assert.deepEqual(facts.readerReadsWhileAskHeld, ["pull-files +0 ms", "pull +0 ms"]);
  tree.controller.dispose();
  await walked.release();
  walker.dispose();

  console.log(JSON.stringify(facts, null, 2));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
