// Browserless session: how often a page asks the server for the root's tallies.
//
// Every root aggregate upsert, every tree load, and the recency menu ask for a fresh
// summary, and each answer costs the server a pass over the whole index. A live tree
// upserts its root on every write, so a page that sent one request per ask held a pile
// of identical multi-second requests, and in WebKit, which sends them in parallel, they
// took every connection the Commits tab needed (explorations/tree-summary-storm/README.md).
//
// The block of app.js that answers an ask, from the comment that introduces the
// summary refresh to the tree cache after it, is extracted verbatim and run against
// the real navigation.js, so this session drives exactly what the shell runs. Only the
// browser is a double: the clock and its timers, `fetch` and the server behind it, and
// the document's summary row, Files panel, and visibility. The session asks through
// `scheduleRootSummaryRefresh`, the shell's one entry point, and shows the page again
// through `resumeRootSummaryRefresh` where the shell has one.
//
// Each scenario lists what the page sent and when the server answered, and what it
// holds after: how many asks it made, how many requests it sent, and the most it ever
// had in flight at once.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");

/** The summary refresh, from its introducing comment to the tree cache that follows. */
function refreshBlock() {
  const start = appSource.indexOf("// The walker's root upsert carries gitignore-blind totals");
  const end = appSource.indexOf("// Last /api/tree payload plus the chrome rendered above it.");
  if (start < 0 || end < start) {
    throw new Error("app.js summary refresh block is not extractable");
  }
  return appSource.slice(start, end);
}

// The shell state a summary answer is painted into. None of it decides when to ask.
const COLLABORATORS = `
const RECENT_RECLUSTER_DEBOUNCE_MS = 100;
var _lastTreeRender = { chromeHtml: '<div class="tree-summary">pending</div>' };
var _lastTreeSummaryHtml = "";
var filterOpenMenu = null;
function updateFilterTallies() {
  return false;
}
function renderNavFilterBar() {}
function patchOpenRecencyTallyCounts() {}
function treeSummaryHtml(summary) {
  return '<div class="tree-summary tree-summary-split">' + summary.files + "</div>";
}
`;

/**
 * One page: a clock, its timers, a server that answers each request after `serverMs`,
 * and a document with a summary row on a Files panel.
 *
 * @param {{serverMs: number, failures?: number}} server
 */
function createPage(server) {
  let now = 0;
  let nextTimer = 1;
  /** @type {{id: number, at: number, callback: () => void}[]} */
  let timers = [];
  let inFlight = 0;
  let maxInFlight = 0;
  let requests = 0;
  let asks = 0;
  let failuresLeft = server.failures ?? 0;
  /** @type {string[]} */
  const did = [];
  const files = { style: { display: "" } };
  const row = {
    set outerHTML(html) {
      did.push(`t=${now} painted ${html.replace(/<[^>]*>/g, "")} files`);
    },
  };
  const document = {
    visibilityState: "visible",
    querySelector(selector) {
      return selector === ".tree-summary" ? row : null;
    },
    getElementById(id) {
      return id === "tab-files" ? files : null;
    },
  };

  /** @param {() => void} callback @param {number} ms */
  function setTimeout(callback, ms) {
    const id = nextTimer++;
    timers.push({ id, at: now + Math.max(0, ms || 0), callback });
    return id;
  }
  /** @param {number} id */
  function clearTimeout(id) {
    timers = timers.filter((timer) => timer.id !== id);
  }

  function fetch(url) {
    requests += 1;
    inFlight += 1;
    maxInFlight = Math.max(maxInFlight, inFlight);
    const number = requests;
    did.push(`t=${now} sent #${number} ${url} (${inFlight} in flight)`);
    return new Promise((resolve) => {
      setTimeout(() => {
        inFlight -= 1;
        if (failuresLeft > 0) {
          failuresLeft -= 1;
          did.push(`t=${now} #${number} failed: 503`);
          resolve({ ok: false, status: 503, json: async () => ({}) });
          return;
        }
        did.push(`t=${now} #${number} answered`);
        resolve({ ok: true, status: 200, json: async () => ({ summary: { files: number } }) });
      }, server.serverMs);
    });
  }

  const context = vm.createContext({
    window: {},
    document,
    performance: { now: () => now },
    setTimeout,
    clearTimeout,
    fetch,
    console,
    Promise,
    Math,
    Number,
    Object,
    Error,
    TypeError,
  });
  context.window = context;
  const navigation = path.join(staticDir, "navigation.js");
  vm.runInContext(fs.readFileSync(navigation, "utf8"), context, { filename: navigation });
  vm.runInContext(COLLABORATORS, context, { filename: "root-summary-collaborators.js" });
  vm.runInContext(refreshBlock(), context, { filename: "app-root-summary-refresh.js" });

  /** Let every settled promise run its continuations. */
  async function drain() {
    for (let turn = 0; turn < 20; turn++) {
      await new Promise((resolve) => setImmediate(resolve));
    }
  }

  /** Run the clock forward `ms`, firing each timer at its own time. */
  async function advance(ms) {
    const until = now + ms;
    await drain();
    for (;;) {
      const due = timers.filter((timer) => timer.at <= until).sort((a, b) => a.at - b.at)[0];
      if (!due) {
        break;
      }
      timers = timers.filter((timer) => timer !== due);
      now = due.at;
      due.callback();
      await drain();
    }
    now = until;
  }

  return {
    did,
    files,
    document,
    async ask() {
      asks += 1;
      context.scheduleRootSummaryRefresh();
      await drain();
    },
    async resume() {
      // The shell's resume hook: visibilitychange, and the Files panel's onShow.
      context.resumeRootSummaryRefresh?.();
      await drain();
    },
    advance,
    /** Ask every `everyMs` for `forMs`, as a live tree's root upserts do. */
    async askEvery(everyMs, forMs) {
      for (let elapsed = 0; elapsed < forMs; elapsed += everyMs) {
        await this.ask();
        await advance(everyMs);
      }
    },
    after() {
      return { asks, requests, maxInFlight, inFlight };
    },
  };
}

/** @param {string} name @param {ReturnType<typeof createPage>} page @param {() => Promise<void>} run */
async function step(name, page, run) {
  page.did.length = 0;
  await run();
  return { step: name, did: [...page.did], after: page.after() };
}

async function main() {
  const transcript = [];

  {
    // Writes every 100 ms after the walk, each upserting the root; a pass costs 3.2 s.
    const page = createPage({ serverMs: 3200 });
    transcript.push({
      scenario: "a live tree upserts its root every 100 ms and each answer takes 3.2 s",
      steps: [
        await step("the root is upserted every 100 ms for 30 s", page, () =>
          page.askEvery(100, 30000),
        ),
        await step("the writes stop", page, () => page.advance(20000)),
      ],
    });
  }

  {
    // A server so slow that twice its answer is past the failure backoff's 30 s cap.
    const page = createPage({ serverMs: 20000 });
    transcript.push({
      scenario: "a live tree whose every answer takes 20 s",
      steps: [
        await step("the root is upserted every 100 ms for 70 s", page, () =>
          page.askEvery(100, 70000),
        ),
      ],
    });
  }

  {
    const page = createPage({ serverMs: 300 });
    transcript.push({
      scenario: "an isolated change on a quiet tree",
      steps: [
        await step("one write", page, async () => {
          await page.ask();
          await page.advance(5000);
        }),
        await step("another write, long after", page, async () => {
          await page.advance(15000);
          await page.ask();
          await page.advance(5000);
        }),
      ],
    });
  }

  {
    const page = createPage({ serverMs: 300, failures: 2 });
    transcript.push({
      scenario: "the server fails the first two requests",
      steps: [
        await step("one write, and no other ask", page, async () => {
          await page.ask();
          await page.advance(30000);
        }),
      ],
    });
  }

  {
    const page = createPage({ serverMs: 300 });
    transcript.push({
      scenario: "a page that is hidden while its tree changes",
      steps: [
        await step("hidden, the root is upserted every 100 ms for 10 s", page, async () => {
          page.document.visibilityState = "hidden";
          await page.askEvery(100, 10000);
        }),
        await step("the page is shown", page, async () => {
          page.document.visibilityState = "visible";
          await page.resume();
          await page.advance(5000);
        }),
      ],
    });
  }

  {
    const page = createPage({ serverMs: 300 });
    transcript.push({
      scenario: "a Files panel behind the Commits tab while its tree changes",
      steps: [
        await step(
          "Commits in front, the root is upserted every 100 ms for 10 s",
          page,
          async () => {
            page.files.style.display = "none";
            await page.askEvery(100, 10000);
          },
        ),
        await step("Files comes to the front", page, async () => {
          page.files.style.display = "";
          await page.resume();
          await page.advance(5000);
        }),
      ],
    });
  }

  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
