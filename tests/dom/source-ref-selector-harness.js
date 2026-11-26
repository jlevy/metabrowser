// What the browserless sessions of the ref selector share: the production module loaded
// whole, the recording of a real mirror's answers, the injected page (timers and paint, and
// requests that wait for a step to answer them), and how a model is printed.
//
// tests/dom/source-ref-selector-session.js is the selector's conversation, and
// tests/dom/source-ref-selector-pulls-session.js the pull requests a branch heads.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/source-ref-selector-responses.json"), "utf8"),
);
function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function loadProductionModule() {
  const context = {
    window: {},
    AbortController,
    console,
    JSON,
    Object,
    Promise,
    URLSearchParams,
  };
  context.window.window = context.window;
  vm.createContext(context);
  // formatters.js names each commit as every line does, as the shell's startup scripts
  // load it first.
  for (const name of ["formatters.js", "source-ref-selector.js"]) {
    const file = path.join(staticDir, name);
    vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  }
  return context.window.MetabrowserSourceRefSelector;
}

const selectorRuntime = loadProductionModule();
assert(selectorRuntime, "the production module did not install its runtime");

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/**
 * Injected browser facilities for one page: requests wait for the step to answer them.
 *
 * @param {{view: string | null, tab?: string}} page The page's pathname, and the main tab
 *   in front, Files unless it says otherwise.
 */
function createPage(page) {
  const log = [];
  const waiting = [];
  const timers = new Map();
  let nextTimer = 1;
  const navigated = [];
  let model = null;
  let renders = 0;

  const deps = {
    request(method, route, body, signal) {
      const line =
        body === undefined ? `${method} ${route}` : `${method} ${route} ${JSON.stringify(body)}`;
      log.push(line);
      return new Promise((resolve, reject) => {
        const request = { route, resolve, reject };
        waiting.push(request);
        // As fetch does: an aborted request settles at once with an AbortError.
        signal?.addEventListener("abort", () => {
          const at = waiting.indexOf(request);
          if (at >= 0) {
            waiting.splice(at, 1);
            log.push(`aborted ${line}`);
            reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
          }
        });
      });
    },
    schedule(callback, delayMs) {
      const handle = nextTimer;
      nextTimer += 1;
      timers.set(handle, { callback, delayMs });
      return handle;
    },
    cancel(handle) {
      timers.delete(handle);
    },
    render(next) {
      model = next;
      renders += 1;
    },
    // A landing that is a history entry's state, the Commits tab's, prints the state.
    navigate(href, state) {
      navigated.push(state === undefined ? href : `${href} ${JSON.stringify(state)}`);
    },
    currentView: () => page.view,
    tab: () => page.tab ?? "files",
  };

  return {
    deps,
    /** Answer the oldest waiting request (or the one at *index*) with a recorded answer. */
    async answer(recording, index = 0) {
      assert(waiting.length > index, "no request is waiting for an answer");
      const [request] = waiting.splice(index, 1);
      request.resolve({ status: recording.status, etag: null, body: recording.body });
      await settle();
    },
    /**
     * Fail the oldest waiting request as `fetch` does when the server is gone: a server
     * that answers has no failure to record for it.
     */
    async fail(index = 0) {
      assert(waiting.length > index, "no request is waiting to fail");
      const [request] = waiting.splice(index, 1);
      request.reject(new TypeError("Failed to fetch"));
      await settle();
    },
    async fireTimer(delayMs = selectorRuntime.FILTER_DELAY_MS) {
      const pending = [...timers.entries()].filter(([, timer]) => timer.delayMs === delayMs);
      assert(pending.length === 1, `expected one ${delayMs} ms timer, found ${pending.length}`);
      const [handle, timer] = pending[0];
      timers.delete(handle);
      timer.callback();
      await settle();
    },
    /** How many times the selector has drawn: the paint a step's answer cost. */
    renders: () => renders,
    observe(step) {
      const delays = [...timers.values()].map((timer) => timer.delayMs);
      const observed = {
        step,
        requests: log.splice(0),
        filterPending: delays.includes(selectorRuntime.FILTER_DELAY_MS),
        paint: paintOf(model),
      };
      // The wait before an open list asks again for the pull requests the server is filling.
      if (delays.includes(selectorRuntime.PULLS_POLL_MS)) {
        observed.pullsPending = true;
      }
      if (navigated.length > 0) {
        observed.navigated = navigated.splice(0);
      }
      return observed;
    },
  };
}

// When a row's commit was made, as the model holds it. The page shows it as an age, which
// depends on the clock, so the transcript prints the time itself.
function committedOf(seconds) {
  return seconds === null
    ? "(no date)"
    : new Date(seconds * 1000).toISOString().replace(".000Z", "Z");
}

// What the selector would show, one line per row, so a transcript reads as the page does:
// a row's name, its commit's short ID, and when the commit was made. A checkout's selector
// adds what a mirror's has none of: the tabs it offers, its working tree's entry, named
// by the branch or commit HEAD is on and the folder's path, which the Working tree tab
// shows, the checked-out branch's badge, each row's chip, and its offer to reload.
function paintOf(model) {
  if (model === null) {
    return null;
  }
  const checkout = model.workingTree !== null;
  const stale = model.stale === null ? {} : { stale: `${model.stale} [Reload page]` };
  if (model.removed) {
    return { removed: true };
  }
  // The row is its label and the chooser's button, whatever the page shows.
  if (!model.open) {
    return { button: model.button, open: false, ...stale };
  }
  const tree = model.workingTree;
  return {
    button: model.button,
    open: true,
    // What the filter box says, once the server has pull requests for it to find.
    ...(model.pullRequests?.state === "ready" ? { filter: model.filterLabel } : {}),
    ...(model.pullRequests === null ? {} : { pullRequests: pullRequestsOf(model.pullRequests) }),
    ...(checkout
      ? {
          workingTree: `Working tree${tree.branch !== null ? ` on ${tree.branch}` : tree.commit !== null ? ` at ${tree.commit}` : ""}${tree.location === "" ? "" : `: ${tree.location} (kept whole: ${tree.base})`}${tree.current ? " [current]" : ""}`,
          lists: model.kinds,
        }
      : {}),
    kind: model.kind,
    query: model.query,
    loading: model.loading,
    switching: model.switching,
    rows: model.rows.map(
      (row) =>
        `${row.name} ${row.commit} ${committedOf(row.committedAt)}${row.default ? " [default]" : ""}${row.checkedOut ? " [checked out]" : ""}${row.current ? " [current]" : ""}${row.own ? ` [${row.own.text}]` : ""}${checkout ? ` (${row.chip} chip)` : ""}${pullsOf(row)}`,
    ),
    // What a row's tooltip says where the reader's own `origin/<branch>` is not where the
    // origin's branch is. Absent where no row says so.
    ...(model.rows.some((row) => row.own)
      ? {
          own: model.rows.filter((row) => row.own).map((row) => `${row.name}: ${row.own.tip}`),
        }
      : {}),
    note: model.note,
    // What a checkout's list says of the store its origin's refs are read from, with
    // when that store was fetched: the page shows it as an age, so the transcript prints
    // the time itself. Absent where no list reads a store.
    ...(model.origin === null || model.origin === undefined
      ? {}
      : {
          origin: `${model.origin.text}${model.origin.fetchedAt === null ? "" : ` (fetched ${model.origin.fetchedAt})`} [${model.origin.tone}]`,
        }),
    error: model.error,
    ...stale,
  };
}

// A row's pull requests, as the row's second line shows the first and counts the rest:
// "| #21 open feat(ref): choose among branches +1".
function pullsOf(row) {
  if (row.pulls.length === 0) {
    return "";
  }
  const [first] = row.pulls;
  const others = row.pullsTotal - 1;
  return ` | #${first.number} ${first.state} ${first.title}${others > 0 ? ` +${others}` : ""}`;
}

// What the listing says of the server's pull requests, as the list shows it: nothing while
// the server has none cached and nothing fills them, and a wait while it does.
function pullRequestsOf(status) {
  const cached =
    status.state === "ready" ? (status.complete ? "cached" : "partly cached") : "none cached";
  return `${cached}${status.refreshing ? ", filling" : ""}`;
}

function emptyState() {
  return {
    shown: null,
    open: false,
    kind: "branch",
    query: "",
    listing: null,
    loading: false,
    switching: false,
    error: null,
  };
}

module.exports = {
  assert,
  committedOf,
  createPage,
  emptyState,
  paintOf,
  recorded,
  repoRoot,
  selectorRuntime,
  settle,
  staticDir,
};
