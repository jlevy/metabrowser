const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

async function loadCoordinator() {
  const resolverSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-resolver.js"),
    "utf8",
  );
  const resolverUrl = `data:text/javascript;base64,${Buffer.from(resolverSource).toString("base64")}`;
  const linksSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/links.js"),
    "utf8",
  );
  const linksUrl = `data:text/javascript;base64,${Buffer.from(linksSource).toString("base64")}`;
  const adaptersSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/project-adapters.js"),
    "utf8",
  );
  const adaptersUrl = `data:text/javascript;base64,${Buffer.from(adaptersSource).toString("base64")}`;
  const source = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/reconciliation-coordinator.js"),
      "utf8",
    )
    .replace('"./links.js"', JSON.stringify(linksUrl))
    .replace('"./project-adapters.js"', JSON.stringify(adaptersUrl))
    .replace('"./wiki-resolver.js"', JSON.stringify(resolverUrl));
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}

function scheduler() {
  let sequence = 0;
  const frames = new Map();
  const retained = new Map();
  return {
    cancel: (handle) => frames.delete(handle),
    frames,
    retained,
    runNext() {
      const next = frames.entries().next().value;
      if (!next) {
        throw new Error("expected a scheduled reconciliation callback");
      }
      frames.delete(next[0]);
      next[1](0);
    },
    runToIdle(limit = 1000) {
      let count = 0;
      while (frames.size > 0) {
        this.runNext();
        count += 1;
        if (count > limit) {
          throw new Error("reconciliation did not settle");
        }
      }
    },
    schedule(callback) {
      sequence += 1;
      frames.set(sequence, callback);
      retained.set(sequence, callback);
      return sequence;
    },
  };
}

function catalog(initialSnapshot) {
  let snapshot = initialSnapshot;
  let listener = null;
  let subscriptions = 0;
  let unsubscriptions = 0;
  return {
    api: {
      snapshot: () => snapshot,
      subscribe(next) {
        listener = next;
        subscriptions += 1;
        return () => {
          if (listener === next) {
            listener = null;
          }
          unsubscriptions += 1;
        };
      },
    },
    notify() {
      listener?.();
    },
    replace(next) {
      snapshot = next;
    },
    stats() {
      return { listener, subscriptions, unsubscriptions };
    },
  };
}

function file(pathname) {
  return Object.freeze({
    basename: pathname.slice(pathname.lastIndexOf("/") + 1),
    path: pathname,
  });
}

function countedSnapshot(count, extras = []) {
  let reads = 0;
  const paths = Array.from(
    { length: count },
    (_, index) => `generated/${String(index).padStart(6, "0")}.md`,
  );
  paths.push(...extras);
  paths.sort();
  const files = paths.map((pathname) =>
    Object.freeze(
      Object.defineProperties(
        {},
        {
          basename: { value: pathname.slice(pathname.lastIndexOf("/") + 1) },
          path: {
            get() {
              reads += 1;
              return pathname;
            },
          },
        },
      ),
    ),
  );
  return {
    reads: () => reads,
    snapshot: Object.freeze({ complete: true, files: Object.freeze(files), revision: 1 }),
  };
}

(async () => {
  const { createMarkdownEnhancementBudget, createMarkdownReconciliationCoordinator } =
    await loadCoordinator();
  const enhancementBudget = createMarkdownEnhancementBudget(2);
  check(
    "root enhancement admission is aggregate and non-refundable",
    enhancementBudget.claim() &&
      enhancementBudget.claim() &&
      !enhancementBudget.claim() &&
      enhancementBudget.exhausted(),
  );

  const aggregate = countedSnapshot(500_000);
  const aggregateCatalog = catalog(aggregate.snapshot);
  const aggregateScheduler = scheduler();
  const aggregateCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: aggregateCatalog.api },
    aggregateScheduler,
  );
  const aggregateResults = [];
  for (let index = 0; index < 24; index += 1) {
    const scope = aggregateCoordinator.createScope();
    scope.wiki(
      {
        action: "navigate",
        authoredTarget: "SharedMissing",
        sourcePath: `nested/${String(index).padStart(2, "0")}.md`,
      },
      (result) => aggregateResults.push(result),
    );
  }
  check("nested scopes share one scheduled callback", aggregateScheduler.frames.size === 1);
  aggregateScheduler.runNext();
  check(
    "nested scopes share one aggregate path budget",
    aggregate.reads() > 0 && aggregate.reads() <= 16_384,
    String(aggregate.reads()),
  );
  check("fallback does not settle from an index prefix", aggregateResults.length === 0);
  aggregateScheduler.runToIdle();
  check(
    "duplicate nested targets share one catalog index",
    aggregate.reads() < 500_100,
    String(aggregate.reads()),
  );
  check(
    "all duplicate nested targets settle identically",
    aggregateResults.length === 24 &&
      aggregateResults.every(
        (result) => result.status === "missing" && result.reason === "not-found",
      ),
  );
  check(
    "complete snapshot is subscribed and pinned once",
    aggregateCatalog.stats().subscriptions === 1 &&
      aggregateCatalog.stats().unsubscriptions === 1 &&
      aggregateCatalog.stats().listener === null,
  );

  const readsBeforeDistinct = aggregate.reads();
  const distinctResults = [];
  for (let index = 0; index < 100; index += 1) {
    aggregateCoordinator.createScope().wiki(
      {
        action: "navigate",
        authoredTarget: `Distinct-${String(index).padStart(3, "0")}`,
        sourcePath: "nested/late.md",
      },
      (result) => distinctResults.push(result),
    );
  }
  aggregateScheduler.runToIdle();
  check("late distinct targets settle", distinctResults.length === 100);
  check(
    "late distinct targets do not rescan the catalog",
    aggregate.reads() - readsBeforeDistinct < 2500,
    String(aggregate.reads() - readsBeforeDistinct),
  );
  aggregateCoordinator.dispose();

  const longSourcePath = `${"a".repeat(1_000_000)}/current.md`;
  const longSourceCatalog = catalog(
    Object.freeze({
      complete: true,
      files: Object.freeze([Object.freeze({ basename: "current.md", path: longSourcePath })]),
      revision: 1,
    }),
  );
  const longSourceScheduler = scheduler();
  const longSourceCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: longSourceCatalog.api },
    longSourceScheduler,
  );
  const longSourceScope = longSourceCoordinator.createScope(undefined, longSourcePath);
  const longSourceResults = [];
  for (let index = 0; index < 100; index += 1) {
    longSourceScope.wiki(
      { action: "navigate", authoredTarget: "#Heading", sourcePath: longSourcePath },
      (result) => longSourceResults.push(result),
    );
  }
  let longSourceSlices = 0;
  while (longSourceScheduler.frames.size > 0) {
    longSourceScheduler.runNext();
    longSourceSlices += 1;
    if (longSourceSlices > 140) {
      throw new Error("shared long-source preparation exceeded its structural work bound");
    }
  }
  check(
    "one root scope shares cooperative provider-long source preparation",
    longSourceResults.length === 100 &&
      longSourceResults.every(
        (result) => result.status === "internal" && result.path === longSourcePath,
      ) &&
      longSourceSlices < 140,
    `${longSourceResults.length} results / ${longSourceSlices} slices`,
  );
  longSourceCoordinator.dispose();

  const exact = countedSnapshot(300_000, ["docs/Target.md"]);
  const exactCatalog = catalog(exact.snapshot);
  const exactScheduler = scheduler();
  const exactCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: exactCatalog.api },
    exactScheduler,
  );
  const exactResults = [];
  exactCoordinator
    .createScope()
    .wiki(
      { action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" },
      (result) => exactResults.push(result),
    );
  exactScheduler.runToIdle();
  check(
    "exact path avoids fallback-index construction",
    exact.reads() < 64 && exactResults[0]?.path === "docs/Target.md",
    `${exact.reads()} reads`,
  );
  exactCoordinator.dispose();

  const mixedCatalog = catalog(
    Object.freeze({
      complete: true,
      files: Object.freeze([file("docs/Target.md"), file("docs/guide.md"), file("mkdocs.yml")]),
      revision: 1,
    }),
  );
  const mixedScheduler = scheduler();
  const mixedCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: mixedCatalog.api },
    mixedScheduler,
  );
  const mixedResults = [];
  for (let index = 0; index < 20; index += 1) {
    mixedCoordinator
      .createScope()
      .wiki(
        { action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" },
        (result) => mixedResults.push(result),
      );
  }
  for (let index = 0; index < 20; index += 1) {
    mixedCoordinator
      .createScope()
      .published({ authoredTarget: "/guide/", resolvedPath: "guide/" }, (result) =>
        mixedResults.push(result),
      );
  }
  mixedScheduler.runNext();
  check(
    "wiki and published jobs share one 32-element callback budget",
    mixedResults.length === 32 && mixedScheduler.frames.size === 1,
    String(mixedResults.length),
  );
  mixedScheduler.runNext();
  check(
    "mixed reconciliation settles in the next shared slice",
    mixedResults.length === 40 && mixedScheduler.frames.size === 0,
  );
  mixedCoordinator.dispose();

  const disposed = countedSnapshot(300_000);
  const disposedCatalog = catalog(disposed.snapshot);
  const disposedScheduler = scheduler();
  const disposedCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: disposedCatalog.api },
    disposedScheduler,
  );
  let disposedCommits = 0;
  let removedAbortListeners = 0;
  const disposalSignal = {
    aborted: false,
    addEventListener() {},
    removeEventListener() {
      removedAbortListeners += 1;
    },
  };
  disposedCoordinator
    .createScope(disposalSignal)
    .wiki({ action: "navigate", authoredTarget: "Missing", sourcePath: "docs/current.md" }, () => {
      disposedCommits += 1;
    });
  disposedScheduler.runNext();
  const retainedHandle = disposedScheduler.frames.keys().next().value;
  const retainedCallback = disposedScheduler.retained.get(retainedHandle);
  const readsBeforeDispose = disposed.reads();
  disposedCoordinator.dispose();
  check("root disposal cancels its queued callback", disposedScheduler.frames.size === 0);
  retainedCallback(0);
  check(
    "retained callback is inert after root disposal",
    disposed.reads() === readsBeforeDispose && disposedCommits === 0 && removedAbortListeners === 1,
  );

  const incompleteOne = Object.freeze({
    complete: false,
    files: Object.freeze([file("docs/current.md")]),
    revision: 1,
  });
  const incompleteTwo = Object.freeze({
    complete: false,
    files: Object.freeze([file("docs/Later.md"), file("docs/current.md")]),
    revision: 2,
  });
  const revisionCatalog = catalog(incompleteOne);
  const revisionScheduler = scheduler();
  const revisionCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: revisionCatalog.api },
    revisionScheduler,
  );
  const revisionResults = [];
  for (let index = 0; index < 40; index += 1) {
    revisionCoordinator
      .createScope()
      .wiki(
        { action: "navigate", authoredTarget: "Later", sourcePath: "docs/current.md" },
        (result) => revisionResults.push(result.status),
      );
  }
  revisionScheduler.runNext();
  check(
    "incomplete revision applies at most one element slice",
    revisionResults.length === 32 && revisionResults.every((status) => status === "pending"),
  );
  revisionCatalog.replace(incompleteTwo);
  revisionCatalog.notify();
  revisionScheduler.runToIdle();
  check(
    "early-absent targets reconcile when an incomplete revision adds them",
    revisionResults.filter((status) => status === "internal").length === 40,
    JSON.stringify(revisionResults),
  );
  revisionCatalog.replace(
    Object.freeze({
      complete: true,
      files: Object.freeze([file("docs/current.md")]),
      revision: 3,
    }),
  );
  revisionCatalog.notify();
  revisionScheduler.runToIdle();
  check(
    "early-present targets reconcile when the pinned revision removes them",
    revisionResults.filter((status) => status === "missing").length === 40 &&
      revisionCatalog.stats().listener === null,
    JSON.stringify(revisionResults),
  );
  revisionCoordinator.dispose();

  const late = countedSnapshot(300_000);
  const lateCatalog = catalog(late.snapshot);
  const lateScheduler = scheduler();
  const lateCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: lateCatalog.api },
    lateScheduler,
  );
  const lateResults = [];
  lateCoordinator
    .createScope()
    .wiki(
      { action: "navigate", authoredTarget: "FirstMissing", sourcePath: "docs/root.md" },
      (result) => lateResults.push(result),
    );
  lateScheduler.runNext();
  lateCoordinator
    .createScope()
    .wiki(
      { action: "navigate", authoredTarget: "LateMissing", sourcePath: "docs/nested.md" },
      (result) => lateResults.push(result),
    );
  lateScheduler.runToIdle();
  check("asynchronous nested scope uses pinned pass", lateResults.length === 2);
  check(
    "asynchronous nested scope reuses in-flight index",
    late.reads() < 300_100,
    String(late.reads()),
  );
  lateCoordinator.dispose();

  const poisonSnapshot = Object.freeze({
    complete: true,
    files: Object.freeze([file("docs/Target.md")]),
    revision: 1,
  });
  const resolverPoisonCatalog = catalog(poisonSnapshot);
  const resolverPoisonScheduler = scheduler();
  const resolverReports = [];
  const resolverPoisonCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: resolverPoisonCatalog.api },
    { ...resolverPoisonScheduler, reportError: (error) => resolverReports.push(error) },
  );
  let resolverPoisonCommit = 0;
  let resolverGoodCommit = 0;
  const resolverPoisonScope = resolverPoisonCoordinator.createScope();
  resolverPoisonScope.wiki(
    { action: "poison", authoredTarget: "./Target", sourcePath: "docs/current.md" },
    () => {
      resolverPoisonCommit += 1;
    },
  );
  resolverPoisonScope.wiki(
    { action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" },
    () => {
      resolverGoodCommit += 1;
    },
  );
  resolverPoisonScheduler.runToIdle();
  check(
    "resolver poison job is quarantined without stranding the next job",
    resolverReports.length === 1 && resolverPoisonCommit === 0 && resolverGoodCommit === 1,
  );
  resolverPoisonCoordinator.dispose();

  const commitPoisonCatalog = catalog(poisonSnapshot);
  const commitPoisonScheduler = scheduler();
  const commitReports = [];
  const commitPoisonCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: commitPoisonCatalog.api },
    { ...commitPoisonScheduler, reportError: (error) => commitReports.push(error) },
  );
  let commitGood = 0;
  const commitPoisonScope = commitPoisonCoordinator.createScope();
  commitPoisonScope.wiki(
    { action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" },
    () => {
      throw new Error("poison commit");
    },
  );
  commitPoisonScope.wiki(
    { action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" },
    () => {
      commitGood += 1;
    },
  );
  commitPoisonScheduler.runToIdle();
  check(
    "commit poison job is quarantined without stranding the next job",
    commitReports.length === 1 && commitGood === 1,
  );
  commitPoisonCoordinator.dispose();

  let snapshotThrows = true;
  let snapshotListener = null;
  const snapshotFailureScheduler = scheduler();
  const snapshotReports = [];
  let snapshotRecoveryCommit = 0;
  const snapshotFailureCoordinator = createMarkdownReconciliationCoordinator(
    {
      fileCatalog: {
        snapshot() {
          if (snapshotThrows) {
            throw new Error("snapshot unavailable");
          }
          return poisonSnapshot;
        },
        subscribe(listener) {
          snapshotListener = listener;
          return () => {
            snapshotListener = null;
          };
        },
      },
    },
    { ...snapshotFailureScheduler, reportError: (error) => snapshotReports.push(error) },
  );
  snapshotFailureCoordinator
    .createScope()
    .wiki({ action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" }, () => {
      snapshotRecoveryCommit += 1;
    });
  snapshotFailureScheduler.runNext();
  check(
    "snapshot failure reports once and does not spin",
    snapshotReports.length === 1 && snapshotFailureScheduler.frames.size === 0,
  );
  snapshotThrows = false;
  snapshotListener();
  snapshotFailureScheduler.runToIdle();
  check("a later catalog notification retries snapshot publication", snapshotRecoveryCommit === 1);
  snapshotFailureCoordinator.dispose();

  const malformedCatalog = catalog(
    Object.freeze({ complete: false, files: Object.freeze([]), revision: 1 }),
  );
  const malformedScheduler = scheduler();
  const malformedReports = [];
  const malformedResults = [];
  const malformedCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: malformedCatalog.api },
    { ...malformedScheduler, reportError: (error) => malformedReports.push(error) },
  );
  malformedCoordinator
    .createScope()
    .wiki(
      { action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" },
      (result) => malformedResults.push(result.status),
    );
  malformedScheduler.runToIdle();
  malformedCatalog.replace(Object.freeze({ complete: true, files: null, revision: 2 }));
  malformedCatalog.notify();
  malformedScheduler.runNext();
  check(
    "malformed context publication reports once and does not spin",
    malformedReports.length === 1 && malformedScheduler.frames.size === 0,
  );
  malformedCatalog.replace(poisonSnapshot);
  malformedCatalog.notify();
  malformedScheduler.runToIdle();
  check(
    "failed context publication leaves the prior generation recoverable",
    JSON.stringify(malformedResults) === '["pending","internal"]',
    JSON.stringify(malformedResults),
  );
  malformedCoordinator.dispose();

  const publishedRevisionCatalog = catalog(
    Object.freeze({
      complete: false,
      files: Object.freeze([file("docs/guide.md"), file("mkdocs.yml")]),
      revision: 1,
    }),
  );
  const publishedRevisionScheduler = scheduler();
  const publishedRevisionCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: publishedRevisionCatalog.api },
    publishedRevisionScheduler,
  );
  const publishedRevisionResults = [];
  publishedRevisionCoordinator
    .createScope()
    .published({ authoredTarget: "/guide/", resolvedPath: "guide/" }, (result) =>
      publishedRevisionResults.push(result),
    );
  publishedRevisionScheduler.runToIdle();
  publishedRevisionCatalog.replace(
    Object.freeze({
      complete: true,
      files: Object.freeze([
        file("docs/guide.md"),
        file("docs/guide/index.md"),
        file("mkdocs.yml"),
      ]),
      revision: 2,
    }),
  );
  publishedRevisionCatalog.notify();
  publishedRevisionScheduler.runToIdle();
  check(
    "published route waits for complete catalog before committing unique inference",
    publishedRevisionResults[0]?.status === "pending" &&
      publishedRevisionResults[1]?.status === "ambiguous",
    JSON.stringify(publishedRevisionResults),
  );
  publishedRevisionCoordinator.dispose();

  // A walk that stops at the file cap is terminal. Its revision is pinned like a
  // complete one, so fallback and published-route jobs settle once with an
  // explanation instead of staying pending and re-running on every live change.
  const truncatedFiles = Object.freeze([
    file("docs/current.md"),
    file("docs/guide.md"),
    file("mkdocs.yml"),
    file("notes/Later.md"),
  ]);
  const truncatedCatalog = catalog(
    Object.freeze({ complete: false, files: truncatedFiles, revision: 1, truncated: false }),
  );
  const truncatedScheduler = scheduler();
  const truncatedCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: truncatedCatalog.api },
    truncatedScheduler,
  );
  const truncatedResults = [];
  const truncatedScope = truncatedCoordinator.createScope(undefined, "docs/current.md");
  truncatedScope.wiki(
    { action: "navigate", authoredTarget: "Later", sourcePath: "docs/current.md" },
    (result) => truncatedResults.push(`wiki:${result.status}:${result.reason}`),
  );
  truncatedScope.published({ authoredTarget: "/guide/", resolvedPath: "guide/" }, (result) =>
    truncatedResults.push(`published:${result?.status}:${result?.reason}`),
  );
  truncatedScheduler.runToIdle();
  truncatedCatalog.replace(
    Object.freeze({ complete: false, files: truncatedFiles, revision: 2, truncated: true }),
  );
  truncatedCatalog.notify();
  truncatedScheduler.runToIdle();
  check(
    "a truncated revision settles pending fallback and published jobs with an explanation",
    JSON.stringify(truncatedResults) ===
      JSON.stringify([
        "wiki:pending:catalog-incomplete",
        "published:pending:catalog-incomplete",
        "wiki:unsupported:catalog-truncated",
        "published:unsupported:catalog-truncated",
      ]),
    JSON.stringify(truncatedResults),
  );
  // Content mounted after the truncated pin resolves against the same revision.
  truncatedScope.wiki(
    { action: "navigate", authoredTarget: "Later", sourcePath: "docs/current.md" },
    (result) => truncatedResults.push(`nested:${result.status}:${result.reason}`),
  );
  truncatedScope.wiki(
    { action: "navigate", authoredTarget: "docs/guide.md", sourcePath: "docs/current.md" },
    (result) => truncatedResults.push(`exact:${result.status}:${result.path}`),
  );
  truncatedScheduler.runToIdle();
  check(
    "a truncated revision keeps its catalog listener for a later complete walk",
    truncatedCatalog.stats().listener !== null && truncatedCatalog.stats().unsubscriptions === 0,
    JSON.stringify(truncatedCatalog.stats()),
  );
  truncatedCatalog.replace(
    Object.freeze({
      complete: false,
      files: Object.freeze([...truncatedFiles, file("zz/later-change.md")]),
      revision: 3,
      truncated: true,
    }),
  );
  truncatedCatalog.notify();
  truncatedScheduler.runToIdle();
  // A reconnect restarts the walk: the catalog is partial again before it can
  // complete. Settled links must not fall back to pending in between.
  truncatedCatalog.replace(
    Object.freeze({ complete: false, files: truncatedFiles, revision: 4, truncated: false }),
  );
  truncatedCatalog.notify();
  truncatedScheduler.runToIdle();
  check(
    "truncated and partial revisions after a truncated pin re-run no reconciliation jobs",
    JSON.stringify(truncatedResults.slice(4)) ===
      JSON.stringify(["nested:unsupported:catalog-truncated", "exact:internal:docs/guide.md"]),
    JSON.stringify(truncatedResults),
  );
  truncatedCatalog.replace(
    Object.freeze({
      complete: true,
      files: truncatedFiles,
      revision: 5,
      truncated: false,
    }),
  );
  truncatedCatalog.notify();
  truncatedScheduler.runToIdle();
  check(
    "a complete revision re-runs only the jobs a truncated revision could not settle",
    JSON.stringify(truncatedResults.slice(6)) ===
      JSON.stringify([
        "wiki:internal:undefined",
        "published:internal:undefined",
        "nested:internal:undefined",
      ]),
    JSON.stringify(truncatedResults),
  );
  check(
    "the complete revision is pinned and releases the catalog listener",
    truncatedCatalog.stats().listener === null && truncatedCatalog.stats().unsubscriptions === 1,
    JSON.stringify(truncatedCatalog.stats()),
  );
  truncatedCatalog.notify();
  check("the pinned complete revision schedules nothing", truncatedScheduler.frames.size === 0);
  truncatedCoordinator.dispose();

  const admissionCatalog = catalog(poisonSnapshot);
  const admissionScheduler = scheduler();
  const admissionCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: admissionCatalog.api },
    admissionScheduler,
  );
  const admissionResults = [];
  const admissionScope = admissionCoordinator.createScope();
  for (let index = 0; index < 4100; index += 1) {
    admissionScope.wiki(
      { action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" },
      (result) => admissionResults.push(result.status),
    );
  }
  check(
    "root admission overflow degrades immediately without retaining extra jobs",
    admissionResults.length === 4 && admissionResults.every((status) => status === "unsupported"),
  );
  admissionScheduler.runToIdle();
  check(
    "root aggregate job budget is shared across scopes",
    admissionResults.length === 4100 &&
      admissionResults.filter((status) => status === "internal").length === 4096,
    String(admissionResults.length),
  );
  admissionCoordinator.dispose();

  const reentrantScheduler = scheduler();
  const reentrantCoordinator = createMarkdownReconciliationCoordinator(
    {
      fileCatalog: catalog(
        Object.freeze({
          complete: true,
          files: Object.freeze([file("docs/guide.md"), file("mkdocs.yml")]),
          revision: 1,
        }),
      ).api,
    },
    reentrantScheduler,
  );
  const reentrantSourcePath = `${"provider-segment/".repeat(1200)}readme.md`;
  const reentrantScope = reentrantCoordinator.createScope(undefined, reentrantSourcePath);
  const reentrantResults = [];
  for (let index = 0; index < 4096; index += 1) {
    reentrantScope.standard(
      {
        action: "navigate",
        authoredTarget: "/guide/",
        sourcePath: reentrantSourcePath,
        syntax: "html",
      },
      (resolved) => {
        reentrantScope.published(
          { authoredTarget: "/guide/", resolvedPath: resolved.path },
          (adapted) => reentrantResults.push(adapted?.status || "exact"),
        );
      },
    );
  }
  reentrantScheduler.runToIdle();
  check(
    "terminal standard jobs release admission before reentrant published follow-ups",
    reentrantResults.length === 4096 && reentrantResults.every((status) => status === "internal"),
    `${reentrantResults.length} results`,
  );
  reentrantCoordinator.dispose();

  const remountSnapshot = Object.freeze({
    complete: true,
    files: Object.freeze([file("docs/New.md")]),
    revision: 1,
  });
  const remountScheduler = scheduler();
  const remountCatalog = catalog(remountSnapshot);
  const remountCoordinator = createMarkdownReconciliationCoordinator(
    { fileCatalog: remountCatalog.api },
    remountScheduler,
  );
  const remountResults = [];
  remountCoordinator
    .createScope()
    .wiki(
      { action: "navigate", authoredTarget: "/docs/New", sourcePath: "docs/current.md" },
      (result) => remountResults.push(result),
    );
  remountScheduler.runToIdle();
  check(
    "replacement coordinator does not reuse disposed root state",
    remountResults.length === 1 && remountResults[0].path === "docs/New.md",
  );
  remountCoordinator.dispose();

  if (failures.length) {
    console.error(`markdown reconciliation coordinator FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown reconciliation coordinator OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
