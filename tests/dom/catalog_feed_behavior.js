// Behavior contract for static/catalog_feed.js: connect-then-fetch
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

const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/catalog_feed.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "catalog_feed.js" });

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

/** A recording catalog double for the feed's three-method target. */
function makeCatalog() {
  const calls = [];
  return {
    calls,
    applyBulkSnapshot(files, complete, authoritative) {
      calls.push({ kind: "bulk", files, complete, authoritative });
    },
    applyCatalogChange(payload) {
      calls.push({ kind: "change", payload });
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
    json: () => Promise.resolve(payload),
  };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

async function main() {
  // ── Buffering before the bulk payload, replay after ──────────
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
      "buffered changes replay after the bulk, in order",
      catalog.calls.length === 3 &&
        catalog.calls[1].payload.upserts[0].p === "early.txt" &&
        catalog.calls[2].payload.upserts[0].p === "during.txt",
    );

    feed.onCatalogChange({ upserts: [{ p: "live.txt", e: ".txt" }], removes: [] });
    check(
      "post-fetch changes apply directly",
      catalog.calls.length === 4 && catalog.calls[3].payload.upserts[0].p === "live.txt",
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
      "refetch replays changes buffered during it",
      catalog.calls.length === applied + 2 &&
        catalog.calls[catalog.calls.length - 1].payload.upserts[0].p === "gap.txt",
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
    await tick();
    check("completion after a partial reconnect payload refetches", pending.length === 3);
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
      reconnectCalls.includes("markIncomplete") && reconnectCalls.includes("markComplete"),
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
    check("changes during resync refetch buffer and replay", catalog.calls.length === before + 2);
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
      "retry applies bulk then the delta buffered across the failure",
      catalog.calls.length === 2 &&
        catalog.calls[0].kind === "bulk" &&
        catalog.calls[1].payload.upserts[0].p === "kept.txt",
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

main().then(() => {
  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write("OK catalog feed\n");
});
