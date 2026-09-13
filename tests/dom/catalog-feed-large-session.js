// Production-code contract for a large authoritative Quick File catalog.
// A fake task scheduler makes every main-thread slice observable without a
// browser, while the real catalog and feed modules preserve their ordering.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { installArrayWorkMeter } = require("./array-work-meter.js");

const FILE_COUNT = 300_000;
// A direct steady-state change may copy, merge, or shift the projection a
// small constant number of times. A per-point insertion regression multiplies
// the projection by the batch instead (256 points x 300k rows = ~77M elements).
const DIRECT_CHANGE_LINEAR_PASSES = 4;
const repoRoot = path.resolve(__dirname, "../..");
const measurements = [];
const sandbox = { clearTimeout, setTimeout };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.metabrowser = {
  perf: {
    measure(label, fn, metadata = {}) {
      const workBefore = arrayWork.read();
      const result = fn();
      measurements.push({ array_element_work: arrayWork.read() - workBefore, label, ...metadata });
      return result;
    },
    measureAsync(_label, fn) {
      return fn();
    },
  },
};
vm.createContext(sandbox);
const arrayWork = installArrayWorkMeter(sandbox);

for (const filename of ["known-file-catalog.js", "catalog-feed.js"]) {
  const sourcePath = path.join(repoRoot, "src/metabrowser/static", filename);
  const source = fs.readFileSync(sourcePath, "utf-8");
  vm.runInContext(source, sandbox, { filename: sourcePath });
}

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

/** @param {number} rows @param {number} items */
function directChangeWorkBound(rows, items) {
  return DIRECT_CHANGE_LINEAR_PASSES * (rows + items);
}

function hasPath(files, target) {
  let low = 0;
  let high = files.length;
  while (low < high) {
    const middle = low + Math.floor((high - low) / 2);
    if (files[middle].path < target) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  return files[low]?.path === target;
}

async function collectWeakReference(reference) {
  for (let attempt = 0; attempt < 20; attempt++) {
    await tick();
    global.gc();
    if (reference.deref() === undefined) {
      return true;
    }
  }
  return false;
}

async function main() {
  const files = Array.from({ length: FILE_COUNT }, (_, index) => ({
    e: ".txt",
    p: `bulk/file-${String(index).padStart(6, "0")}.txt`,
  }));
  const catalog = sandbox.MetabrowserKnownFileCatalog.create();
  let initialFetches = 0;

  let notifications = 0;
  const completePublications = [];
  let unsubscribeOnComplete = null;
  unsubscribeOnComplete = catalog.subscribe(() => {
    notifications += 1;
    const publication = catalog.snapshot();
    completePublications.push({
      complete: publication.complete,
      hasBufferedUpsert: hasPath(publication.files, "live/after-bulk.md"),
    });
    if (publication.complete) {
      unsubscribeOnComplete?.();
      unsubscribeOnComplete = null;
    }
  });
  const initialSnapshot = catalog.snapshot();

  const scheduledTurns = [];
  const feed = sandbox.MetabrowserCatalogFeed.create({
    catalog,
    fetchImpl: async () => {
      initialFetches += 1;
      return {
        headers: { get: () => null },
        text: async () => JSON.stringify({ complete: true, files }),
        ok: true,
        status: 200,
      };
    },
    yieldControl: () =>
      new Promise((resolve) => {
        scheduledTurns.push(resolve);
      }),
  });

  feed.start();
  await tick();
  await tick();

  check("large bulk schedules continuation", scheduledTurns.length === 1);
  check(
    "partial bulk does not publish a revision",
    catalog.snapshot() === initialSnapshot && notifications === 0,
    `${catalog.snapshot().revision}/${notifications}`,
  );

  // The ordinary cold shell creates the catalog after its initial tree has
  // painted. Navigation can still finish while the bulk stage is yielding;
  // that observation must join the atomic commit without forcing the already
  // ordered 300k-row feed through a second projection pass.
  catalog.observeNavigation("visited/ignored.log", ".log");

  // This event arrives after the first bulk slice. It must remain buffered
  // until authoritative membership and pruning have both finished.
  feed.onCatalogChange({
    remove_files: ["bulk/file-000001.txt"],
    removes: [],
    upserts: [{ e: ".md", p: "live/after-bulk.md" }],
  });

  let turns = 0;
  while (turns < 1_000) {
    const continuation = scheduledTurns.shift();
    if (continuation) {
      continuation();
      turns += 1;
    }
    await tick();
    if (scheduledTurns.length === 0 && catalog.snapshot().complete) {
      break;
    }
  }

  const bulkMeasurements = measurements.filter(
    (measurement) => measurement.label === "knownFileCatalog:applyBulkSnapshot",
  );
  const sliceLimit = sandbox.MetabrowserCatalogFeed.BULK_APPLY_SLICE_ITEMS;
  check(
    "production publishes a positive slice bound",
    Number.isInteger(sliceLimit) && sliceLimit > 0,
  );
  check("300k application spans many task slices", bulkMeasurements.length > 50);
  check(
    "every production slice respects the work-item bound",
    bulkMeasurements.every(
      (measurement) =>
        Number.isInteger(measurement.work_items) && measurement.work_items <= sliceLimit,
    ),
    `${Math.max(...bulkMeasurements.map((measurement) => measurement.work_items || 0))}`,
  );
  check("large application finished within scheduler guard", turns < 1_000, String(turns));
  check(
    "settled start fetches the catalog exactly once",
    initialFetches === 1,
    String(initialFetches),
  );
  const initialBulkWorkItems = bulkMeasurements.reduce(
    (total, measurement) => total + (measurement.work_items || 0),
    0,
  );
  check(
    "ordered initial feed is adopted without a duplicate projection pass",
    initialBulkWorkItems === FILE_COUNT + 3,
    String(initialBulkWorkItems),
  );

  const finalSnapshot = catalog.snapshot();
  const finalPaths = new Set(finalSnapshot.files.map((file) => file.path));
  check("authoritative finalization marks coverage complete", finalSnapshot.complete === true);
  check("navigation exception survives final pruning", finalPaths.has("visited/ignored.log"));
  check("buffered removal replays after the bulk", !finalPaths.has("bulk/file-000001.txt"));
  check("buffered upsert replays after the bulk", finalPaths.has("live/after-bulk.md"));
  check(
    "bulk and buffered event publish one complete notification",
    notifications === 1,
    String(notifications),
  );
  check(
    "completion subscriber sees buffered membership before it unsubscribes",
    completePublications.length === 1 &&
      completePublications[0].complete === true &&
      completePublications[0].hasBufferedUpsert === true,
    JSON.stringify(completePublications),
  );
  check(
    "final membership count is exact",
    finalSnapshot.observedCount === FILE_COUNT + 1,
    String(finalSnapshot.observedCount),
  );

  // The inventory stream may deliver its full bounded point batch at the
  // lexical head of a 300k projection. Repeated Array.splice calls make that
  // adversarial shape quadratic in shifted suffix length, so exercise the
  // exact production feed seam and bound the array elements it touches to a
  // few linear passes. The headed performance probe owns the real-time 50 ms
  // gate; a wall-clock check here would only measure machine load. Replacing
  // the same 256 points covers the update path; removing ten adjacent head
  // entries covers a small direct subtree range without promoting it to the
  // sliced transaction.
  const directHeadEntries = Array.from({ length: 256 }, (_, index) => ({
    e: ".txt",
    p: `bulk/000-head/${index < 10 ? "group-00" : "group-rest"}/file-${String(index).padStart(3, "0")}.txt`,
  }));
  const directHeadRows = catalog.snapshot().observedCount;
  const directHeadStart = measurements.length;
  feed.onCatalogChange({ removes: [], upserts: directHeadEntries });
  await tick();
  const directHeadMeasurement = measurements
    .slice(directHeadStart)
    .find((measurement) => measurement.label === "knownFileCatalog:applyCatalogChange");
  check(
    "256 lexical-head insertions stay within a few linear projection passes",
    directHeadMeasurement?.work_items === 256 &&
      directHeadMeasurement.array_element_work <= directChangeWorkBound(directHeadRows, 256),
    JSON.stringify(directHeadMeasurement),
  );
  check(
    "direct lexical-head insertion publishes every point",
    catalog.snapshot().observedCount === FILE_COUNT + 257,
    String(catalog.snapshot().observedCount),
  );

  const directReplacementRows = catalog.snapshot().observedCount;
  const directReplacementStart = measurements.length;
  feed.onCatalogChange({
    removes: [],
    upserts: directHeadEntries.map((entry) => ({ ...entry, e: ".md" })),
  });
  await tick();
  const directReplacementMeasurement = measurements
    .slice(directReplacementStart)
    .find((measurement) => measurement.label === "knownFileCatalog:applyCatalogChange");
  check(
    "256 lexical-head replacements stay within a few linear projection passes",
    directReplacementMeasurement?.work_items === 256 &&
      directReplacementMeasurement.array_element_work <=
        directChangeWorkBound(directReplacementRows, 256),
    JSON.stringify(directReplacementMeasurement),
  );
  check(
    "direct lexical-head replacements update the immutable projection",
    catalog.snapshot().files.find((file) => file.path === directHeadEntries[0].p)
      ?.logicalExtension === ".md",
  );

  const smallRemovalRows = catalog.snapshot().observedCount;
  const smallRemovalStart = measurements.length;
  feed.onEventChange([{ op: "remove", path: "bulk/000-head/group-00" }]);
  await tick();
  const smallRemovalMeasurement = measurements
    .slice(smallRemovalStart)
    .find((measurement) => measurement.label === "knownFileCatalog:applyEventChange");
  check(
    "small lexical-head subtree removal stays within a few linear projection passes",
    smallRemovalMeasurement?.candidate_visits === 10 &&
      smallRemovalMeasurement.work_items === 20 &&
      smallRemovalMeasurement.array_element_work <= directChangeWorkBound(smallRemovalRows, 20),
    JSON.stringify(smallRemovalMeasurement),
  );
  check(
    "small lexical-head subtree removal publishes exact membership",
    catalog.snapshot().observedCount === FILE_COUNT + 247,
    String(catalog.snapshot().observedCount),
  );

  // A staged monotonic tail is allowed to use the full production slice: its
  // proof excludes replacements and non-tail entries before any projection
  // mutation, so 4096 appends remain O(k). Drive the baseline separately to
  // meter that exact mutation slice rather than conflating it with catalog copy.
  const tailEntries = Array.from({ length: sliceLimit }, (_, index) => ({
    e: ".txt",
    p: `zzzz-tail/file-${String(index).padStart(4, "0")}.txt`,
  }));
  const baselineCount = catalog.snapshot().observedCount;
  const tailApplication = catalog.beginCatalogChange({ upserts: tailEntries }, sliceLimit);
  check("4096 tail points select a staged application", tailApplication !== null);
  let remainingBaseline = baselineCount;
  while (remainingBaseline > 0) {
    const copyStep = tailApplication?.step(Math.min(sliceLimit, remainingBaseline));
    check(
      "tail fixture copies the exact immutable baseline before mutation",
      copyStep?.done === false && copyStep.workItems === Math.min(sliceLimit, remainingBaseline),
      JSON.stringify(copyStep),
    );
    remainingBaseline -= copyStep?.workItems || 0;
  }
  const tailWorkBefore = arrayWork.read();
  const tailStep = tailApplication?.step(sliceLimit);
  const tailArrayWork = arrayWork.read() - tailWorkBefore;
  // O(k) means independent of the 300k baseline: a constant number of touches
  // per appended point, never a copy or shift of the projection.
  check(
    "4096 sorted new-tail points touch only the appended slice",
    tailStep?.done === false &&
      tailStep.workItems === sliceLimit &&
      tailArrayWork <= 4 * sliceLimit,
    `${tailArrayWork}/${JSON.stringify(tailStep)}`,
  );
  const tailCommit = tailApplication?.step(sliceLimit);
  check(
    "the staged tail commits after the bounded mutation slice",
    tailCommit?.done === true && tailCommit.workItems === 0,
    JSON.stringify(tailCommit),
  );
  check(
    "the staged tail publishes exact membership once",
    catalog.snapshot().observedCount === FILE_COUNT + 247 + sliceLimit,
    String(catalog.snapshot().observedCount),
  );

  const eventTailOps = Array.from({ length: 256 }, (_, index) => ({
    entry: {
      logical_ext: ".txt",
      path: `zzzzz-event-tail/file-${String(index).padStart(3, "0")}.txt`,
      type: "file",
    },
    op: "upsert",
  }));
  const eventTailRows = catalog.snapshot().observedCount;
  const eventTailStart = measurements.length;
  feed.onEventChange(eventTailOps);
  await tick();
  const eventTailMeasurement = measurements
    .slice(eventTailStart)
    .find((measurement) => measurement.label === "knownFileCatalog:applyEventChange");
  check(
    "256 sorted new event-entry tails stay within a few linear projection passes",
    eventTailMeasurement?.work_items === 256 &&
      eventTailMeasurement.array_element_work <= directChangeWorkBound(eventTailRows, 256),
    JSON.stringify(eventTailMeasurement),
  );
  check(
    "the event-entry tail publishes exact membership",
    catalog.snapshot().observedCount === FILE_COUNT + 503 + sliceLimit,
    String(catalog.snapshot().observedCount),
  );

  // The exact direct/sliced boundary is part of the production scheduling
  // contract. A normal 256-entry inventory batch avoids a 300k baseline copy;
  // the next entry moves the same shape onto the cooperative transaction.
  const directBoundary = catalog.beginCatalogChange(
    {
      upserts: Array.from({ length: 256 }, (_, index) => ({
        e: ".txt",
        p: `threshold/direct-${String(index).padStart(3, "0")}.txt`,
      })),
    },
    sliceLimit,
  );
  check("256 point changes stay on the measured direct path", directBoundary === null);
  const slicedBoundary = catalog.beginCatalogChange(
    {
      upserts: Array.from({ length: 257 }, (_, index) => ({
        e: ".txt",
        p: `threshold/sliced-${String(index).padStart(3, "0")}.txt`,
      })),
    },
    sliceLimit,
  );
  check("257 point changes use the cooperative transaction", slicedBoundary !== null);
  slicedBoundary?.cancel();

  // Scattered removals are the worst case for interval deletion: one splice
  // per interval would shift the 300k suffix thousands of times inside one
  // slice. The staged transaction compacts in a single charged forward pass.
  const scatteredPaths = Array.from(
    { length: 2_999 },
    (_, index) => `bulk/file-${String((index + 1) * 100).padStart(6, "0")}.txt`,
  );
  const scatteredRows = catalog.snapshot().observedCount;
  const scatteredApplication = catalog.beginCatalogChange(
    { removes: scatteredPaths, upserts: [] },
    sliceLimit,
  );
  check("scattered removals use the cooperative transaction", scatteredApplication !== null);
  let scatteredSteps = 0;
  let scatteredMaxArrayWork = 0;
  let scatteredStep;
  do {
    const workBefore = arrayWork.read();
    scatteredStep = scatteredApplication?.step(sliceLimit);
    scatteredMaxArrayWork = Math.max(scatteredMaxArrayWork, arrayWork.read() - workBefore);
    scatteredSteps += 1;
  } while (scatteredStep && !scatteredStep.done && scatteredSteps < 1_000);
  check(
    "every scattered-removal slice touches a bounded number of array elements",
    scatteredMaxArrayWork <= 4 * sliceLimit,
    String(scatteredMaxArrayWork),
  );
  check(
    "scattered removal spreads compaction across task slices",
    scatteredStep?.done === true && scatteredSteps > 50,
    `${scatteredSteps}/${JSON.stringify(scatteredStep)}`,
  );
  const scatteredSnapshot = catalog.snapshot();
  check(
    "scattered removal publishes exact membership",
    scatteredSnapshot.observedCount === scatteredRows - scatteredPaths.length &&
      !hasPath(scatteredSnapshot.files, scatteredPaths[0]) &&
      !hasPath(scatteredSnapshot.files, scatteredPaths.at(-1)) &&
      hasPath(scatteredSnapshot.files, "bulk/file-000101.txt"),
    String(scatteredSnapshot.observedCount),
  );

  // A live subtree removal can cover the complete catalog. It uses the same
  // production scheduler and staged publication path as initial delivery, so
  // even this worst-case delta stays bounded and invisible between slices.
  let removalNotifications = 0;
  const unsubscribeRemoval = catalog.subscribe(() => {
    removalNotifications += 1;
  });
  const removalMeasurementStart = measurements.length;
  feed.onEventChange([
    { op: "remove", path: "bulk" },
    { op: "remove", path: "zzzz-tail" },
    { op: "remove", path: "zzzzz-event-tail" },
  ]);
  await tick();
  const beforeRemoval = catalog.snapshot();
  check(
    "large subtree removal remains invisible after its first slice",
    beforeRemoval.observedCount === scatteredSnapshot.observedCount && removalNotifications === 0,
    `${beforeRemoval.observedCount}/${removalNotifications}`,
  );
  let removalTurns = 0;
  while (removalTurns < 1_000) {
    const continuation = scheduledTurns.shift();
    if (continuation) {
      continuation();
      removalTurns += 1;
    }
    await tick();
    if (scheduledTurns.length === 0 && catalog.snapshot().observedCount === 2) {
      break;
    }
  }
  const removalMeasurements = measurements
    .slice(removalMeasurementStart)
    .filter((measurement) => measurement.label === "knownFileCatalog:applyEventChange");
  check("large subtree removal spans scheduled slices", removalMeasurements.length > 100);
  check(
    "every live-delta slice respects the production bound",
    removalMeasurements.every(
      (measurement) =>
        Number.isInteger(measurement.work_items) && measurement.work_items <= sliceLimit,
    ),
    `${Math.max(...removalMeasurements.map((measurement) => measurement.work_items || 0))}`,
  );
  check(
    "live-delta metadata counts affected candidate visits",
    removalMeasurements.reduce(
      (total, measurement) => total + (measurement.candidate_visits || 0),
      0,
    ) >= FILE_COUNT,
  );
  check(
    "large subtree removal publishes once after complete application",
    removalNotifications === 1 && catalog.snapshot().observedCount === 2,
    `${removalNotifications}/${catalog.snapshot().observedCount}`,
  );
  unsubscribeRemoval();

  const attributedDeliveryLabels = [
    "apiCatalog:parse",
    "knownFileCatalog:applyBulkSnapshot",
    "knownFileCatalog:applyCatalogChange",
    "knownFileCatalog:applyEventChange",
  ];
  check(
    "every exercised catalog delivery callback retains production attribution",
    attributedDeliveryLabels.every((label) =>
      measurements.some((measurement) => measurement.label === label),
    ),
    measurements.map((measurement) => measurement.label).join(","),
  );

  feed.dispose();

  // A reconnect can invalidate a response between slices. The partial work
  // must never claim completion, and the queued authoritative replacement
  // must retire every path from the canceled payload.
  const cancellationCatalog = sandbox.MetabrowserKnownFileCatalog.create();
  const cancellationTurns = [];
  let fetchIndex = 0;
  const firstFiles = Array.from({ length: sliceLimit + 10 }, (_, index) => ({
    e: ".txt",
    p: `canceled/file-${index}.txt`,
  }));
  const replacementFeed = sandbox.MetabrowserCatalogFeed.create({
    catalog: cancellationCatalog,
    fetchImpl: async () => {
      const payload =
        fetchIndex === 0
          ? { complete: true, files: firstFiles }
          : { complete: true, files: [{ e: ".txt", p: "replacement.txt" }] };
      fetchIndex += 1;
      return {
        headers: { get: () => null },
        text: async () => JSON.stringify(payload),
        ok: true,
        status: 200,
      };
    },
    yieldControl: () =>
      new Promise((resolve) => {
        cancellationTurns.push(resolve);
      }),
  });

  replacementFeed.start();
  await tick();
  await tick();
  check("cancel fixture reaches a scheduled boundary", cancellationTurns.length === 1);
  replacementFeed.start();
  check(
    "superseded application never promotes completeness",
    cancellationCatalog.snapshot().complete === false,
  );
  cancellationTurns.shift()?.();
  await tick();
  await tick();

  let cancellationGuard = 0;
  while (cancellationGuard < 20) {
    cancellationTurns.shift()?.();
    cancellationGuard += 1;
    await tick();
    if (cancellationTurns.length === 0 && cancellationCatalog.snapshot().complete) {
      break;
    }
  }
  check(
    "replacement fetch follows the canceled application",
    fetchIndex === 2 && cancellationCatalog.snapshot().complete,
    `${fetchIndex}/${cancellationCatalog.snapshot().complete}`,
  );
  check(
    "replacement authoritative membership retires canceled partial work",
    JSON.stringify(cancellationCatalog.snapshot().files.map((file) => file.path)) ===
      JSON.stringify(["replacement.txt"]),
    cancellationCatalog
      .snapshot()
      .files.map((file) => file.path)
      .slice(0, 3)
      .join(","),
  );
  replacementFeed.dispose();

  // A reconnect rotates the pending-delta generation. An upsert from the old
  // stream is ambiguous and must not replay over the new authoritative empty
  // payload; an upsert observed after the new open and its paired sentinel is
  // ordered within the new generation and must survive.
  const reconnectCatalog = sandbox.MetabrowserKnownFileCatalog.create();
  const reconnectFetches = [];
  const reconnectFeed = sandbox.MetabrowserCatalogFeed.create({
    catalog: reconnectCatalog,
    fetchImpl: () =>
      new Promise((resolve) => {
        reconnectFetches.push(resolve);
      }),
    yieldControl: () => Promise.resolve(),
  });
  reconnectFeed.start();
  reconnectFeed.onSentinelSnapshot();
  await tick();
  reconnectFeed.onCatalogChange({
    removes: [],
    upserts: [{ e: ".txt", p: "deleted-before-reconnect.txt" }],
  });
  reconnectFeed.start();
  reconnectFeed.onSentinelSnapshot();
  reconnectFeed.onCatalogChange({
    removes: [],
    upserts: [{ e: ".txt", p: "created-after-reconnect.txt" }],
  });
  reconnectFetches[0]?.({
    headers: { get: () => null },
    text: async () => JSON.stringify({ complete: true, files: [] }),
    ok: true,
    status: 200,
  });
  await tick();
  await tick();
  check("reconnect schedules a replacement fetch", reconnectFetches.length === 2);
  reconnectFetches[1]?.({
    headers: { get: () => null },
    text: async () => JSON.stringify({ complete: true, files: [] }),
    ok: true,
    status: 200,
  });
  await tick();
  await tick();
  const reconnectPaths = reconnectCatalog.snapshot().files.map((file) => file.path);
  check(
    "reconnect discards old-stream buffered deltas",
    !reconnectPaths.includes("deleted-before-reconnect.txt"),
    reconnectPaths.join(","),
  );
  check(
    "paired reconnect sentinel preserves new-stream buffered deltas",
    reconnectPaths.includes("created-after-reconnect.txt"),
    reconnectPaths.join(","),
  );
  reconnectFeed.dispose();

  // An unexpected sentinel is itself a continuity boundary even when no
  // matching open callback arrived. It rotates pre-sentinel work while
  // retaining deltas observed after that sentinel for the replacement bulk.
  const sentinelCatalog = sandbox.MetabrowserKnownFileCatalog.create();
  const sentinelFetches = [];
  const sentinelFeed = sandbox.MetabrowserCatalogFeed.create({
    catalog: sentinelCatalog,
    fetchImpl: () =>
      new Promise((resolve) => {
        sentinelFetches.push(resolve);
      }),
    yieldControl: () => Promise.resolve(),
  });
  sentinelFeed.start();
  sentinelFeed.onSentinelSnapshot();
  await tick();
  sentinelFeed.onCatalogChange({
    removes: [],
    upserts: [{ e: ".txt", p: "before-unpaired-sentinel.txt" }],
  });
  sentinelFeed.onSentinelSnapshot();
  sentinelFeed.onCatalogChange({
    removes: [],
    upserts: [{ e: ".txt", p: "after-unpaired-sentinel.txt" }],
  });
  sentinelFetches[0]?.({
    headers: { get: () => null },
    text: async () => JSON.stringify({ complete: true, files: [] }),
    ok: true,
    status: 200,
  });
  await tick();
  await tick();
  check("unpaired sentinel schedules a replacement fetch", sentinelFetches.length === 2);
  sentinelFetches[1]?.({
    headers: { get: () => null },
    text: async () => JSON.stringify({ complete: true, files: [] }),
    ok: true,
    status: 200,
  });
  await tick();
  await tick();
  const sentinelPaths = sentinelCatalog.snapshot().files.map((file) => file.path);
  check(
    "unpaired sentinel discards pre-boundary buffered deltas",
    !sentinelPaths.includes("before-unpaired-sentinel.txt"),
    sentinelPaths.join(","),
  );
  check(
    "unpaired sentinel preserves later buffered deltas",
    sentinelPaths.includes("after-unpaired-sentinel.txt"),
    sentinelPaths.join(","),
  );
  sentinelFeed.dispose();

  // `bumpRevision` must release its internal snapshot reference immediately.
  // External holders still own any snapshot they keep, but once this sole
  // caller drops it a later mutation must make it collectible without another
  // `snapshot()` read.
  const memoCatalog = sandbox.MetabrowserKnownFileCatalog.create();
  memoCatalog.observeNavigation("old.txt", ".txt");
  const oldSnapshotReference = (() => {
    const oldSnapshot = memoCatalog.snapshot();
    return new WeakRef(oldSnapshot);
  })();
  memoCatalog.observeNavigation("new.txt", ".txt");
  if (typeof global.gc === "function") {
    check(
      "revision bump releases the stale memoized snapshot",
      await collectWeakReference(oldSnapshotReference),
    );
  }

  return Object.freeze({
    attributedDeliveryLabels,
    catalogRows: FILE_COUNT,
    initialBulkWorkItems,
    initialFetches,
    sliceItemLimit: sandbox.MetabrowserCatalogFeed.BULK_APPLY_SLICE_ITEMS,
  });
}

main().then((summary) => {
  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
});
