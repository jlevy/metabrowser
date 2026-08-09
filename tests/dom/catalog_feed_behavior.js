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
    applyBulkSnapshot(files, complete) {
      calls.push({ kind: "bulk", files, complete });
    },
    applyCatalogChange(payload) {
      calls.push({ kind: "change", payload });
    },
    markComplete() {
      calls.push({ kind: "markComplete" });
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
    feed.start();
    await tick();
    check("start is once-only", pending.length === 1);

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

  // ── Resync rebuilds from scratch ──────────────────────────────
  {
    const catalog = makeCatalog();
    const { impl, pending } = makeFetch();
    const feed = sandbox.MetabrowserCatalogFeed.create({ catalog, fetchImpl: impl });
    feed.start();
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
}

main().then(() => {
  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write("OK catalog feed\n");
});
