// Behavior contract for static/catalog-feed.js: connect-then-fetch
// ordering, delta buffering and replay, sentinel/resync refetch, and
// retry without data loss. Run under Node with a stubbed fetch — the
// module owns no EventSource and no DOM.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const sourcePath = path.join(repoRoot, "src/metabrowser/static/catalog-feed.js");
const source = fs.readFileSync(sourcePath, "utf-8");
vm.runInContext(source, sandbox, { filename: sourcePath });

const failures = [];
// Every distinct scenario this session verified, in first-run order. The
// golden pins the list, so removing a scenario changes the transcript.
const verified = [];

function check(label, condition, detail = "") {
  if (!verified.includes(label)) {
    verified.push(label);
  }
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

/** A recording catalog double for the feed target. */
function makeCatalog() {
  const calls = [];
  return {
    calls,
    beginBulkSnapshot(files, complete, authoritative) {
      let done = false;
      const buffered = [];
      return {
        cancel() {
          done = true;
        },
        enqueueCatalogChange(payload) {
          buffered.push(payload);
        },
        step() {
          if (!done) {
            calls.push({ kind: "bulk", files, complete, authoritative, buffered: [...buffered] });
            done = true;
          }
          return { candidateVisits: 0, cancelled: false, done: true, workItems: files.length };
        },
      };
    },
    beginCatalogChange() {
      return null;
    },
    beginEventChange() {
      return null;
    },
    applyCatalogChange(payload) {
      calls.push({ kind: "change", payload });
      return { candidateVisits: 0, changed: true, workItems: 1 };
    },
    applyEventChange(ops) {
      calls.push({ kind: "event-change", ops });
      return { candidateVisits: 0, changed: true, workItems: ops.length };
    },
    markComplete() {
      calls.push({ kind: "markComplete" });
    },
    markIncomplete() {
      calls.push({ kind: "markIncomplete" });
    },
  };
}

/** A controllable fetch double: each call returns a pending promise. */
function makeFetch() {
  const pending = [];
  const impl = () => {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => {
      resolve = res;
      reject = rej;
    });
    pending.push({ resolve, reject });
    return promise;
  };
  return { impl, pending };
}

function jsonResponse(payload, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(JSON.stringify(payload)),
  };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

async function main() {
  // ── Buffering before the bulk payload, folded at commit ─────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });

    feed.onCatalogChange({ upserts: [{ p: "early.txt", e: ".txt" }], removes: [] });
    check("no apply before start", catalog.calls.length === 0);

    feed.start();
    await tick();
    check("first start begins one fetch", pending.length === 1);

    feed.onCatalogChange({ upserts: [{ p: "during.txt", e: ".txt" }], removes: [] });
    check("changes during fetch stay buffered", catalog.calls.length === 0);

    pending[0].resolve(jsonResponse({ complete: true, files: [{ p: "bulk.txt", e: ".txt" }] }));
    await tick();
    await tick();

    check("bulk applies first", catalog.calls[0]?.kind === "bulk");
    check("bulk carries completeness", catalog.calls[0]?.complete === true);
    check(
      "buffered changes fold into the bulk in order",
      catalog.calls.length === 1 &&
        catalog.calls[0].buffered[0].upserts[0].p === "early.txt" &&
        catalog.calls[0].buffered[1].upserts[0].p === "during.txt",
    );

    feed.onCatalogChange({
      non_file_paths: ["replaced-link"],
      upserts: [{ p: "live.txt", e: ".txt" }],
      removes: [],
    });
    check(
      "small post-fetch changes use the direct point path",
      catalog.calls.length === 2 &&
        catalog.calls[1].payload.upserts[0].p === "live.txt" &&
        catalog.calls[1].payload.non_file_paths[0] === "replaced-link",
    );
    feed.onEventChange([{ op: "remove", path: "old-dir" }]);
    check(
      "fs.change uses the same scheduler-backed delivery seam",
      catalog.calls.length === 3 &&
        catalog.calls[2].kind === "event-change" &&
        catalog.calls[2].ops[0].path === "old-dir",
    );
  }

  // ── Sentinel snapshots: first is not a continuity break ───────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });

    feed.onSentinelSnapshot();
    check("sentinel before first fetch does nothing", pending.length === 0);

    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[0].resolve(jsonResponse({ complete: true, files: [] }));
    await tick();
    await tick();

    feed.onSentinelSnapshot();
    await tick();
    check("sentinel after a completed fetch refetches", pending.length === 2);

    // Changes during the refetch buffer and replay after it.
    feed.onCatalogChange({ upserts: [{ p: "gap.txt", e: ".txt" }], removes: [] });
    const applied = catalog.calls.length;
    pending[1].resolve(jsonResponse({ complete: true, files: [] }));
    await tick();
    await tick();
    check(
      "refetch folds changes buffered during it",
      catalog.calls.length === applied + 1 &&
        catalog.calls.at(-1).buffered[0].upserts[0].p === "gap.txt",
    );
  }

  // ── Reconnect during a fresh scan converges at completion ──────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });

    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[0].resolve(
      jsonResponse({ complete: true, files: [{ p: "deleted-while-away.txt", e: ".txt" }] }),
    );
    await tick();
    await tick();

    // A later open is a reconnect. Its first payload may be only a
    // prefix while the restarted server scans, so it cannot remove a
    // path that disappeared while the stream was down.
    feed.start();
    check(
      "reconnect marks catalog coverage incomplete",
      catalog.calls.some((call) => call.kind === "markIncomplete"),
    );
    await tick();
    check("reconnect open refetches before its sentinel", pending.length === 2);
    feed.onSentinelSnapshot();
    await tick();
    check("reconnect sentinel does not duplicate the open refetch", pending.length === 2);
    pending[1].resolve(jsonResponse({ complete: false, files: [] }));
    await tick();
    await tick();

    feed.onIndexComplete();
    feed.onIndexComplete();
    await tick();
    check("completion after a partial reconnect payload refetches", pending.length === 3);
    check("duplicate completion signals share one authoritative refetch", pending.length === 3);
    check(
      "partial reconnect does not claim completion before an authoritative payload",
      !catalog.calls.some((call) => call.kind === "markComplete"),
    );

    if (pending[2]) {
      pending[2].resolve(jsonResponse({ complete: true, files: [] }));
      await tick();
      await tick();
      const finalBulk = catalog.calls[catalog.calls.length - 1];
      check(
        "completion refetch applies authoritative membership",
        finalBulk?.kind === "bulk" &&
          finalBulk.complete === true &&
          finalBulk.authoritative === true,
      );
    }
  }

  // ── A capped scan still repairs reconnect membership ──────────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });

    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[0].resolve(
      jsonResponse({ complete: true, files: [{ p: "deleted-while-away.txt", e: ".txt" }] }),
    );
    await tick();
    await tick();

    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[1].resolve(jsonResponse({ complete: false, files: [] }));
    await tick();
    await tick();

    feed.onIndexComplete(true);
    await tick();
    check("truncated completion repairs reconnect membership", pending.length === 3);
    check(
      "truncated completion never claims complete root coverage",
      !catalog.calls.some((call) => call.kind === "markComplete"),
    );

    if (pending[2]) {
      pending[2].resolve(jsonResponse({ complete: true, truncated: true, files: [] }));
      await tick();
      await tick();
      const finalBulk = catalog.calls[catalog.calls.length - 1];
      check(
        "truncated completion refetch is authoritative but incomplete",
        finalBulk?.kind === "bulk" &&
          finalBulk.complete === false &&
          finalBulk.authoritative === true,
      );
    }
  }

  // ── Reconnect invalidates the unfinished initial fetch ─────────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });

    feed.start();
    feed.onSentinelSnapshot();
    await tick();

    // The stream reconnects before the original bulk response lands.
    // start() must invalidate that response even though fetchedOnce is
    // still false; waiting for the sentinel would miss this gap.
    feed.start();
    feed.onSentinelSnapshot();
    pending[0].resolve(
      jsonResponse({ complete: true, files: [{ p: "before-reconnect.txt", e: ".txt" }] }),
    );
    await tick();
    await tick();
    check(
      "reconnect discards an unfinished initial response",
      !catalog.calls.some(
        (call) =>
          call.kind === "bulk" && call.files.some((file) => file.p === "before-reconnect.txt"),
      ),
    );
    check("reconnect queues a replacement for the initial fetch", pending.length === 2);

    pending[1].resolve(
      jsonResponse({ complete: true, files: [{ p: "after-reconnect.txt", e: ".txt" }] }),
    );
    await tick();
    await tick();
    check(
      "replacement initial fetch applies",
      catalog.calls.some(
        (call) =>
          call.kind === "bulk" && call.files.some((file) => file.p === "after-reconnect.txt"),
      ),
    );
  }

  // ── Conditional reconnect fetch preserves prior coverage ──────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });

    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[0].resolve(jsonResponse({ complete: true, files: [] }));
    await tick();
    await tick();

    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[1].resolve(jsonResponse({}, 304));
    await tick();
    await tick();
    const reconnectCalls = catalog.calls.slice(1).map((call) => call.kind);
    check(
      "304 reconnect restores known complete coverage",
      reconnectCalls.includes("markIncomplete") &&
        catalog.calls.at(-1)?.kind === "bulk" &&
        catalog.calls.at(-1)?.complete === true,
      reconnectCalls.join(","),
    );
  }

  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });

    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[0].resolve(jsonResponse({ complete: true, truncated: true, files: [] }));
    await tick();
    await tick();

    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[1].resolve(jsonResponse({}, 304));
    await tick();
    await tick();
    check(
      "304 reconnect keeps capped coverage incomplete",
      !catalog.calls.some((call) => call.kind === "markComplete"),
    );
  }

  // ── Resync rebuilds from scratch ──────────────────────────────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });
    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[0].resolve(jsonResponse({ complete: true, files: [] }));
    await tick();
    await tick();

    feed.onResync();
    await tick();
    check("resync refetches", pending.length === 2);
    feed.onCatalogChange({ upserts: [{ p: "afterswap.txt", e: ".txt" }], removes: [] });
    const before = catalog.calls.length;
    pending[1].resolve(jsonResponse({ complete: false, files: [] }));
    await tick();
    await tick();
    check(
      "changes during resync refetch fold into its commit",
      catalog.calls.length === before + 1 &&
        catalog.calls.at(-1).buffered[0].upserts[0].p === "afterswap.txt",
    );
  }

  // ── Retry on failure without losing buffered deltas ───────────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const retries = [];
    const feed = sandbox.MetabrowserCatalogFeed.create({
      catalog,
      fetchImpl: impl,
      scheduleRetry: (callback, delayMs) => {
        retries.push({ callback, delayMs });
        return retries.length;
      },
      cancelRetry: () => {},
    });
    feed.start();
    await tick();
    feed.onCatalogChange({ upserts: [{ p: "kept.txt", e: ".txt" }], removes: [] });
    pending[0].reject(new Error("network down"));
    await tick();
    await tick();
    check("failure schedules a retry", retries.length === 1);
    check("nothing applied on failure", catalog.calls.length === 0);

    retries[0].callback();
    await tick();
    pending[1].resolve(jsonResponse({ complete: true, files: [{ p: "bulk.txt", e: ".txt" }] }));
    await tick();
    await tick();
    check(
      "retry folds the delta buffered across the failure into its bulk",
      catalog.calls.length === 1 &&
        catalog.calls[0].kind === "bulk" &&
        catalog.calls[0].buffered[0].upserts[0].p === "kept.txt",
    );
  }

  // ── Resync invalidates an in-flight fetch (Bugbot R4) ─────────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });
    feed.start();
    await tick();

    // Root swap arrives while the first bulk fetch is still in
    // flight. The old response must be discarded — it describes the
    // previous root — and a fresh fetch must still happen.
    feed.onResync();
    pending[0].resolve(
      jsonResponse({ complete: true, files: [{ p: "stale-root.txt", e: ".txt" }] }),
    );
    await tick();
    await tick();
    check(
      "stale pre-resync response is never applied",
      !catalog.calls.some(
        (call) => call.kind === "bulk" && call.files.some((f) => f.p === "stale-root.txt"),
      ),
    );
    check("resync during a fetch still queues a follow-up fetch", pending.length === 2);

    pending[1].resolve(jsonResponse({ complete: true, files: [{ p: "new-root.txt", e: ".txt" }] }));
    await tick();
    await tick();
    check(
      "follow-up fetch applies the new root's catalog",
      catalog.calls.some(
        (call) => call.kind === "bulk" && call.files.some((f) => f.p === "new-root.txt"),
      ),
    );
  }

  // ── Sentinel during a fetch is not swallowed (Bugbot R5) ──────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });
    feed.start();
    feed.onSentinelSnapshot();
    await tick();
    pending[0].resolve(jsonResponse({ complete: true, files: [] }));
    await tick();
    await tick();

    feed.onSentinelSnapshot();
    await tick();
    check("first sentinel refetches", pending.length === 2);

    // A second reconnect lands while the refetch is still in
    // flight: its response may predate the dropped deltas, so it
    // must be discarded and another fetch queued once it settles.
    feed.onSentinelSnapshot();
    pending[1].resolve(jsonResponse({ complete: true, files: [{ p: "pre-drop.txt", e: ".txt" }] }));
    await tick();
    await tick();
    check(
      "response overtaken by a second sentinel is discarded",
      !catalog.calls.some(
        (call) => call.kind === "bulk" && call.files.some((f) => f.p === "pre-drop.txt"),
      ),
    );
    check("sentinel during a fetch queues a follow-up", pending.length === 3);
    pending[2].resolve(
      jsonResponse({ complete: true, files: [{ p: "post-drop.txt", e: ".txt" }] }),
    );
    await tick();
    await tick();
    check(
      "queued follow-up applies",
      catalog.calls.some(
        (call) => call.kind === "bulk" && call.files.some((f) => f.p === "post-drop.txt"),
      ),
    );
  }

  // ── Completion flag and disposal ──────────────────────────────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });
    feed.onIndexComplete();
    check("index completion marks the catalog", catalog.calls[0]?.kind === "markComplete");

    feed.start();
    await tick();
    feed.dispose();
    pending[0].resolve(jsonResponse({ complete: true, files: [{ p: "x", e: "" }] }));
    await tick();
    await tick();
    check("disposed feed applies nothing", catalog.calls.length === 1);
  }

  // The lightweight progress poll is a second source of terminal catalog
  // repair when the SSE capability event is dropped. Inactive is broader than
  // complete: provider failure is inactive but must not promote a partial
  // catalog. Execute the actual app.js function so this wiring cannot regress
  // behind a source-string assertion.
  {
    const appSource = fs.readFileSync(
      path.join(repoRoot, "src/metabrowser/static/app.js"),
      "utf-8",
    );
    const refreshSource = appSource.match(
      /^async function refreshIndexProgress\(force\) \{[\s\S]*?^\}/m,
    )?.[0];
    check("progress poll function is extractable", typeof refreshSource === "string");

    async function completionCalls(meta) {
      const calls = [];
      const progressSandbox = {
        console,
        indexProgressInFlight: false,
        indexProgressLastRendered: { status: "scanning" },
        fetch: async () => ({ ok: true, status: 200, json: async () => meta }),
        shouldRenderIndexProgress: () => false,
        renderIndexProgress() {},
        indexProgressIsActive: () => false,
        ensureTreeTruncationNote() {},
        quickFileCatalogFeed: {
          onIndexComplete(truncated) {
            calls.push(truncated);
          },
        },
        announceScanCompletion() {},
        refreshTreeIfPendingTallies: async () => {},
        stopIndexProgressPolling() {},
      };
      vm.createContext(progressSandbox);
      vm.runInContext(refreshSource, progressSandbox, { filename: "app.js:refreshIndexProgress" });
      await progressSandbox.refreshIndexProgress(false);
      return calls;
    }

    const failedCalls = await completionCalls({
      status: "failed",
      complete: false,
      truncated: false,
    });
    check("failed progress does not complete the catalog", failedCalls.length === 0);

    const cappedCalls = await completionCalls({
      status: "truncated",
      complete: true,
      truncated: true,
      max_files: 100,
    });
    check(
      "capped progress repairs without claiming complete coverage",
      cappedCalls.length === 1 && cappedCalls[0] === true,
    );
  }

  // A walk that stopped at the max-files cap reports complete AND truncated.
  // Files past the cap were never indexed, so the catalog is not a complete
  // view of the root and must not claim to be (senior review R10).
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });
    feed.start();
    await tick();
    pending[0].resolve(
      jsonResponse({ complete: true, truncated: true, files: [{ p: "capped.txt", e: ".txt" }] }),
    );
    await tick();
    await tick();
    check("truncated bulk applies its files", catalog.calls[0]?.kind === "bulk");
    check(
      "a truncated catalog is not reported complete",
      catalog.calls[0]?.complete === false,
      String(catalog.calls[0]?.complete),
    );
    feed.onIndexComplete(true);
    check(
      "a truncated terminal event does not mark the catalog complete",
      !catalog.calls.some((call) => call.kind === "markComplete"),
    );
  }
}

// A steady staged change that finishes while a refetch is in flight must not
// discard the journal: changes that arrive after that fetch began have to
// replay over its payload, which predates them. Uses the production catalog.
async function stagedChangeDuringRefetch() {
  const catalogSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/static/known-file-catalog.js"),
    "utf-8",
  );
  vm.runInContext(catalogSource, sandbox, { filename: "known-file-catalog.js" });
  const catalog = sandbox.MetabrowserKnownFileCatalog.create();
  const { impl, pending } = makeFetch();
  const turns = [];
  const feed = sandbox.MetabrowserCatalogFeed.create({
    catalog,
    fetchImpl: impl,
    yieldControl: () => new Promise((resolve) => turns.push(resolve)),
  });
  async function settle() {
    for (let round = 0; round < 10_000; round += 1) {
      await tick();
      const turn = turns.shift();
      if (!turn) {
        await tick();
        if (turns.length === 0) {
          return;
        }
        continue;
      }
      turn();
    }
  }

  // Enough rows that a staged change copies its baseline across task slices.
  const baseline = Array.from({ length: 5_000 }, (_, index) => ({
    e: ".txt",
    p: `a/file-${String(index).padStart(4, "0")}.txt`,
  }));
  feed.start();
  await tick();
  pending[0].resolve(jsonResponse({ complete: false, files: baseline }));
  await settle();
  // A reconnect during the walk requires one terminal, authoritative payload.
  feed.start();
  await tick();
  pending[1].resolve(jsonResponse({ complete: false, files: baseline }));
  await settle();

  const bulk = Array.from({ length: 300 }, (_, index) => ({
    e: ".txt",
    p: `bulk/file-${String(index).padStart(3, "0")}.txt`,
  }));
  feed.onCatalogChange({ removes: [], upserts: bulk });
  await tick();
  check("a large steady change is staged", turns.length === 1, String(turns.length));
  feed.onIndexComplete();
  await tick();
  check("walk completion issues the authoritative refetch", pending.length === 3);
  feed.onCatalogChange({ removes: [], upserts: [{ e: ".txt", p: "new.txt" }] });
  await settle();

  pending[2].resolve(jsonResponse({ complete: true, files: [...baseline, ...bulk] }));
  await settle();
  const paths = catalog.snapshot().files.map((file) => file.path);
  check(
    "a change after the refetch began survives its older authoritative payload",
    paths.includes("new.txt") &&
      paths.length === baseline.length + bulk.length + 1 &&
      catalog.snapshot().complete === true,
    JSON.stringify({
      complete: catalog.snapshot().complete,
      count: paths.length,
      hasNew: paths.includes("new.txt"),
    }),
  );
  feed.dispose();
}

main()
  .then(stagedChangeDuringRefetch)
  .then(() => {
    if (failures.length > 0) {
      process.stderr.write(`${failures.join("\n")}\n`);
      process.exit(1);
    }
    process.stdout.write(`${JSON.stringify({ verified }, null, 2)}\n`);
  });
