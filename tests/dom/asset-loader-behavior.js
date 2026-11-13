// Behavioral shim for static/asset-loader.js.
//
// The on-demand tier's whole claim is that a document which never opens a
// consuming view pays nothing, and that a document which opens two of them
// pays once. Neither is visible from a request count in a real page, so the
// script element is faked here and every append is recorded.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2] || path.join(__dirname, "../.."));
const sourcePath = path.join(repoRoot, "src/metabrowser/static/asset-loader.js");
const source = fs.readFileSync(sourcePath, "utf8");

/** Every src appended, in order, across the whole run. */
const appended = [];
/** Every `metabrowser:optional-asset-loaded` src, in order. */
const notified = [];
/** srcs whose onload is withheld until released, to observe in-flight sharing. */
const held = new Map();

class FakeScript {
  constructor() {
    this.src = "";
    this.async = true;
    this.onload = null;
    this.onerror = null;
    this.removed = false;
  }
  remove() {
    this.removed = true;
  }
}

function makeSandbox(
  bundles,
  { hold = [], fail = [], failCounts = {}, installs = {}, installAfter = {} } = {},
) {
  const listeners = [];
  const failuresRemaining = new Map(Object.entries(failCounts));
  const appendCounts = new Map();
  const sandbox = {
    METABROWSER_ASSET_BUNDLES: bundles,
    console,
    CustomEvent: class {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    dispatchEvent(event) {
      if (event.type === "metabrowser:optional-asset-loaded") {
        notified.push(event.detail.src);
      }
      for (const fn of listeners) {
        fn(event);
      }
      return true;
    },
    addEventListener(_type, fn) {
      listeners.push(fn);
    },
    document: {
      createElement: () => new FakeScript(),
      head: {
        appendChild(script) {
          appended.push(script.src);
          const appendCount = Number(appendCounts.get(script.src) || 0) + 1;
          appendCounts.set(script.src, appendCount);
          const settle = () => {
            const failuresLeft = Number(failuresRemaining.get(script.src) || 0);
            if (fail.includes(script.src) || failuresLeft > 0) {
              if (failuresLeft > 0) {
                failuresRemaining.set(script.src, failuresLeft - 1);
              }
              script.onerror();
              return;
            }
            // A real script installs its global before onload fires; the
            // `requires` gate on the next entry reads exactly that.
            if (installs[script.src] && appendCount >= Number(installAfter[script.src] || 1)) {
              sandbox[installs[script.src]] = {};
            }
            script.onload();
          };
          if (hold.includes(script.src)) {
            held.set(script.src, settle);
          } else {
            settle();
          }
          return script;
        },
      },
    },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: sourcePath });
  return sandbox;
}

/** The loader starts its chain on a microtask, so appends land after the
 *  synchronous call returns. Yield to the task queue before observing. */
function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

async function main() {
  const results = {};

  // 1. Declaring a bundle loads nothing. This is the tier's whole point.
  appended.length = 0;
  makeSandbox({ chart: [{ src: "chart.js" }] });
  await flush();
  results.appendedBeforeAnyRequest = appended.length;

  // 2. A bundle loads in order, and a `requires` entry sees the global its
  //    predecessor installed.
  {
    appended.length = 0;
    notified.length = 0;
    const sandbox = makeSandbox(
      {
        chart: [
          { src: "chart.js" },
          { src: "plugin.js", requires: "Chart" },
          { src: "adapter.js", requires: "Chart" },
        ],
      },
      { installs: { "chart.js": "Chart" } },
    );
    await sandbox.MetabrowserAssets.ensureAsset("chart");
    results.orderedLoad = appended.slice();
    results.notifiedPerScript = notified.slice();
    results.loadedFlag = sandbox.MetabrowserAssets.assetLoaded("chart");

    // 3. A second request refetches nothing.
    const before = appended.length;
    await sandbox.MetabrowserAssets.ensureAsset("chart");
    results.appendsOnSecondRequest = appended.length - before;
  }

  // 4. A gated entry whose dependency never appeared is skipped, not failed:
  //    the bundle's core still works without its plugins.
  {
    appended.length = 0;
    const sandbox = makeSandbox({
      chart: [{ src: "chart.js" }, { src: "plugin.js", requires: "Chart" }],
    });
    await sandbox.MetabrowserAssets.ensureAsset("chart");
    results.skippedUngatedDependency = appended.slice();
  }

  // 5. Simultaneous callers share the one in-flight load rather than racing
  //    to append duplicates. Held until all three have asked.
  {
    appended.length = 0;
    held.clear();
    const sandbox = makeSandbox({ chart: [{ src: "chart.js" }] }, { hold: ["chart.js"] });
    const all = Promise.all([
      sandbox.MetabrowserAssets.ensureAsset("chart"),
      sandbox.MetabrowserAssets.ensureAsset("chart"),
      sandbox.MetabrowserAssets.ensureAsset("chart"),
    ]);
    await flush();
    results.appendsWhileThreeCallersWait = appended.length;
    held.get("chart.js")();
    await all;
    results.appendsAfterSharedLoadSettled = appended.length;
  }

  // 6. An unknown bundle rejects, so a consumer can say so rather than
  //    rendering into a surface that will not work.
  {
    const sandbox = makeSandbox({ chart: [{ src: "chart.js" }] });
    try {
      await sandbox.MetabrowserAssets.ensureAsset("absent");
      results.unknownBundle = "resolved";
    } catch (error) {
      results.unknownBundle = error.message;
    }
  }

  // 7. A failed script rejects and does not mark the bundle loaded, so the
  //    next attempt retries instead of reporting a library that is not there.
  {
    appended.length = 0;
    const sandbox = makeSandbox({ chart: [{ src: "chart.js" }] }, { fail: ["chart.js"] });
    try {
      await sandbox.MetabrowserAssets.ensureAsset("chart");
      results.failedScript = "resolved";
    } catch (error) {
      results.failedScript = error.message;
    }
    results.loadedFlagAfterFailure = sandbox.MetabrowserAssets.assetLoaded("chart");
    try {
      await sandbox.MetabrowserAssets.ensureAsset("chart");
    } catch (_error) {
      /* expected */
    }
    results.appendsAfterFailedRetry = appended.length;
  }

  // 8. A late entry can fail after the bundle's core installed global state.
  //    Retrying must resume at the failed entry: re-executing a successful
  //    library module can duplicate process-lifetime event subscriptions.
  //    Simultaneous retry callers still share that one resumed load.
  {
    appended.length = 0;
    notified.length = 0;
    const sandbox = makeSandbox(
      {
        chart: [
          { src: "chart.js" },
          { src: "charts-runtime.js", requires: "Chart" },
          { src: "adapter.js", requires: "Chart" },
        ],
      },
      {
        failCounts: { "adapter.js": 1 },
        installs: { "chart.js": "Chart" },
      },
    );
    try {
      await sandbox.MetabrowserAssets.ensureAsset("chart");
    } catch (_error) {
      /* expected */
    }
    const resumed = Promise.all([
      sandbox.MetabrowserAssets.ensureAsset("chart"),
      sandbox.MetabrowserAssets.ensureAsset("chart"),
    ]);
    await resumed;
    results.partialFailureRetryAppends = appended.slice();
    results.partialFailureNotifications = notified.slice();
    results.partialFailureLoaded = sandbox.MetabrowserAssets.assetLoaded("chart");
  }

  // 9. A load event proves only that the browser fetched and evaluated the
  //    script. When the entry promises a global, success is earned only after
  //    that global exists. A missing core must stop the bundle before gated
  //    dependants, must not latch either the script or bundle, and must retry.
  {
    appended.length = 0;
    notified.length = 0;
    const sandbox = makeSandbox(
      {
        chart: [
          { src: "chart.js", provides: "Chart" },
          { src: "plugin.js", requires: "Chart" },
        ],
      },
      {
        installs: { "chart.js": "Chart" },
        installAfter: { "chart.js": 2 },
      },
    );
    try {
      await sandbox.MetabrowserAssets.ensureAsset("chart");
      results.missingProvidedGlobal = "resolved";
    } catch (error) {
      results.missingProvidedGlobal = error.message;
    }
    results.missingProvidedGlobalFirstAppends = appended.slice();
    results.missingProvidedGlobalFirstNotifications = notified.slice();
    results.missingProvidedGlobalLatched = sandbox.MetabrowserAssets.assetLoaded("chart");

    await sandbox.MetabrowserAssets.ensureAsset("chart");
    results.missingProvidedGlobalRetryAppends = appended.slice();
    results.missingProvidedGlobalRetryNotifications = notified.slice();
    results.missingProvidedGlobalRetryLoaded = sandbox.MetabrowserAssets.assetLoaded("chart");
  }

  // 10. A weak and strong declaration can join the same in-flight src. If the
  // weak load does not establish the strong postcondition, the strong caller
  // rejects and clears the src latch so its first retry performs a real load.
  {
    appended.length = 0;
    held.clear();
    const sandbox = makeSandbox(
      {
        weak: [{ src: "shared.js" }],
        strong: [{ src: "shared.js", provides: "Shared" }],
      },
      {
        hold: ["shared.js"],
        installs: { "shared.js": "Shared" },
        installAfter: { "shared.js": 2 },
      },
    );
    const weak = sandbox.MetabrowserAssets.ensureAsset("weak");
    const strong = sandbox.MetabrowserAssets.ensureAsset("strong").then(
      () => "resolved",
      (error) => error.message,
    );
    await flush();
    held.get("shared.js")();
    await weak;
    results.concurrentStrongFailure = await strong;

    const retry = sandbox.MetabrowserAssets.ensureAsset("strong");
    await flush();
    results.concurrentStrongRetryAppends = appended.slice();
    held.get("shared.js")();
    await retry;
    results.concurrentStrongRetryLoaded = sandbox.MetabrowserAssets.assetLoaded("strong");
  }

  process.stdout.write(`${JSON.stringify(results)}\n`);
}

main().catch((error) => {
  process.stderr.write(String(error?.stack ? error.stack : error));
  process.exit(1);
});
