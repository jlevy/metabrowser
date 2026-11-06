// Production mount with deterministic geometry; viewport growth must fill the newly visible area.
const assert = require("node:assert/strict");
const { pathToFileURL } = require("node:url");
const root = require("node:path").resolve(__dirname, "../..");
const { FakeNode, FakeElement } = require(`${root}/tests/dom/pulls-test-dom.js`);
const details = require("../fixtures/github-pull-page-responses.json");
const source = "https://github.com/octo/demo";
const observedAt = "2026-11-03T00:00:00Z";
const absent = { ...details.absent.body, number: 500, source };
const prepared = {
  ...absent,
  core_preview: {
    source,
    number: 500,
    reader: "gh:reader",
    observed_at: observedAt,
    revision: "a".repeat(64),
    comparison_state: "not_started",
    pull: {
      ...details.current.body.record.pull,
      number: 500,
      body: "Prepared visible description",
    },
  },
};
const controls = [],
  detailReads = [],
  opened = [];
let readyCore = false,
  holdAdmission = false,
  refuseAdmission = null,
  finishAdmission;
const answer = (body, status = 200) => ({
  status,
  headers: { get: () => null },
  json: async () => body,
});
const settle = async () => {
  for (let i = 0; i < 20; i++) {
    await new Promise(setImmediate);
  }
};
const perfEntries = [];
const perf = {
  measure(label, work) {
    const value = work();
    perfEntries.push(label);
    return value;
  },
  async measureAsync(label, work) {
    const value = await work();
    perfEntries.push(label);
    return value;
  },
};
let viewHeight = 100;
const body = new FakeElement("body"),
  scroll = new FakeElement("div"),
  container = new FakeElement("div");
body.append(scroll);
scroll.append(container);
scroll.scrollTop = 0;
// Both the list and its expanded trees subscribe to the same native scroll event.
const listen = scroll.addEventListener.bind(scroll);
scroll.addEventListener = (type, listener) => {
  const previous = scroll.listeners.get(type);
  listen(
    type,
    previous === undefined
      ? listener
      : (...args) => {
          previous(...args);
          listener(...args);
        },
  );
};
function height(node) {
  if (node.classList?.contains("github-pulls-spacer")) {
    return Number.parseFloat(node.style.height) || 0;
  }
  if (node.classList?.contains("github-pulls-item")) {
    return 41.5;
  }
  if (node.classList?.contains("github-pulls-list")) {
    return node.childNodes.reduce((n, c) => n + height(c), 0);
  }
  return 0;
}
FakeElement.prototype.getBoundingClientRect = function () {
  if (this.classList.contains("github-pulls-row")) {
    const { top, left, right, width } = this.parentNode.getBoundingClientRect();
    return { top, bottom: top + 41.5, height: 41.5, left, right, width };
  }
  let h = height(this),
    top = 0;
  if (this === scroll) {
    h = viewHeight;
  } else if (this.classList.contains("github-pulls-list")) {
    top = -scroll.scrollTop;
  } else if (this.parentNode?.classList?.contains("github-pulls-list")) {
    top = -scroll.scrollTop;
    for (const sibling of this.parentNode.childNodes) {
      if (sibling === this) {
        break;
      }
      top += height(sibling);
    }
  }
  return { top, bottom: top + h, height: h, left: 0, right: 800, width: 800 };
};
const frames = new Map(),
  timers = new Map(),
  observers = [];
let serial = 0;
// Match Web Crypto on a trusted-network HTTP page: randomUUID is secure-context only.
Object.defineProperty(globalThis, "crypto", {
  value: {
    getRandomValues: require("node:crypto").webcrypto.getRandomValues.bind(
      require("node:crypto").webcrypto,
    ),
  },
});
Object.assign(globalThis, {
  document: {
    body,
    activeElement: body,
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new FakeElement(tag),
    createDocumentFragment: () => new FakeNode("#fragment"),
    importNode: (node) => new FakeElement(node.localName),
  },
  window: {
    addEventListener() {},
    setTimeout(fn, delay) {
      const id = ++serial;
      timers.set(id, { fn, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
    requestAnimationFrame(fn) {
      const id = ++serial;
      frames.set(id, fn);
      return id;
    },
    cancelAnimationFrame: (id) => frames.delete(id),
  },
  getComputedStyle: () => ({ getPropertyValue: () => "24px" }),
  HTMLElement: FakeElement,
  Element: FakeElement,
  DOMParser: class {
    parseFromString() {
      return { body: { firstElementChild: new FakeElement("svg") } };
    }
  },
  ResizeObserver: class {
    constructor(fn) {
      this.fn = fn;
      this.nodes = new Set();
      observers.push(this);
    }
    observe(node) {
      this.nodes.add(node);
    }
    unobserve(node) {
      this.nodes.delete(node);
    }
    disconnect() {
      this.nodes.clear();
    }
  },
  IntersectionObserver: class {
    observe() {}
    disconnect() {}
  },
  fetch: async (route, options) => {
    const url = new URL(route, "http://localhost");
    if (url.pathname === "/api/plugin/github/pull-cores-prepare") {
      const body = JSON.parse(options.body);
      controls.push(body);
      if (body.numbers.length === 0) {
        return answer({ preparation: "released" });
      }
      if (refuseAdmission !== null) {
        const preparation = refuseAdmission;
        refuseAdmission = null;
        return answer({ preparation });
      }
      if (holdAdmission) {
        holdAdmission = false;
        return new Promise((resolve) => {
          finishAdmission = (preparation = "started") =>
            resolve(answer({ preparation }, preparation === "started" ? 202 : 200));
        });
      }
      return answer({ preparation: "started" }, 202);
    }
    if (url.pathname === "/api/plugin/github/pull") {
      const number = Number(url.searchParams.get("number"));
      detailReads.push(number);
      return answer(readyCore && number === 500 ? prepared : { ...absent, number });
    }
    const q = url.searchParams,
      after = Number(q.get("after")),
      start = after ? 501 - after : 0,
      limit = Number(q.get("limit") ?? 100),
      count = Math.min(limit, 500 - start);
    return {
      status: 200,
      headers: { get: () => null },
      json: async () => ({
        state: "current",
        reason: null,
        source: "https://github.com/octo/demo",
        list: q.get("state") ?? "open",
        fetched_at: "2026-11-03T00:00:00Z",
        count_at: "2026-11-03T00:00:00Z",
        reader: "gh:reader",
        fresh_for_s: 60,
        refreshing: false,
        last_refresh: null,
        fetched: 500,
        total: 500,
        repository_total: 500,
        catalog_fetched: 500,
        generation: "one",
        complete: true,
        truncated: false,
        limit,
        next_after: start + count < 500 ? 501 - start - count : null,
        rows: Array.from({ length: count }, (_, i) => ({
          number: 500 - start - i,
          title: `PR ${500 - start - i}`,
          state: "open",
          draft: false,
          merged_at: null,
          author: "reader",
          updated_at: "2026-11-03T00:00:00Z",
          base_ref: "main",
          head_ref: "branch",
          head_repository: "octo/demo",
        })),
      }),
    };
  },
});
async function paint() {
  for (let round = 0; round < 10 && frames.size; round++) {
    const ready = [...frames.values()];
    frames.clear();
    for (const fn of ready) {
      fn();
    }
    await settle();
  }
}
(async () => {
  const panel = await import(
    pathToFileURL(`${root}/src/metabrowser/builtin_plugins/github/pulls-panel.js`)
  );
  const handle = panel.mountPullsPanel(
    container,
    {
      kind: "pull-request-list",
      pullsNav: {
        filter: "open",
        current: null,
        shown: true,
        refreshAhead: false,
        scrollRoot: scroll,
        file: null,
        open(route) {
          opened.push(route);
        },
        fileHref: () => null,
        pageFor: () => null,
        onPageChange: () => () => {},
        filterChanged() {},
      },
    },
    {
      perf,
      filterControls: { groupHtml: () => "", bind: () => () => {} },
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      formatAge: () => ({ label: "now", className: "" }),
      formatTimestamp: () => "",
    },
  );
  await settle();
  assert(perfEntries.includes("githubPulls:rowsReady"));
  assert.equal(controls.length, 0, "summary DOM commits before a preparation POST");
  async function sample() {
    await paint();
    const due = [...timers].find(([, timer]) => timer.delay === panel.PEEK_MS);
    assert.ok(due, "the quiet post-paint sample owns a timer");
    timers.delete(due[0]);
    due[1].fn();
    await settle();
  }
  await sample();
  assert.deepEqual(controls[0].numbers, [500, 499, 498], "overscan is outside the visible cohort");
  const list = container.childNodes.find((n) => n.classList?.contains("github-pulls-list"));
  const items = () => list.childNodes.filter((n) => n.classList?.contains("github-pulls-item"));
  for (const label of [
    "githubPulls:decode",
    "githubPulls:render",
    "githubPulls:window",
    "githubPulls:rowsReady",
    "githubPulls:catalogReady",
  ]) {
    assert(perfEntries.includes(label), `the existing profiler receives ${label}`);
  }
  const before = items().length;
  viewHeight = 3000;
  let observedRoot = 0;
  for (const observer of observers) {
    if (observer.nodes.has(scroll)) {
      observedRoot++;
      observer.fn([{ target: scroll, borderBoxSize: [{ blockSize: viewHeight }] }]);
    }
  }
  holdAdmission = true;
  await sample();
  const pending = controls.at(-1);
  assert.equal(pending.numbers.length, 8);
  assert.ok(finishAdmission);
  handle.setShown(false);
  assert.equal(controls.at(-1), pending, "release is ordered behind the admission");
  finishAdmission();
  await settle();
  assert.deepEqual(controls.at(-1), { ...pending, numbers: [] }, "hide releases its exact token");
  handle.setShown(true);
  await settle();
  await sample();
  assert.notEqual(controls.at(-1).window.id, pending.window.id);
  const after = items().length;
  const visibleGap = list.childNodes.find(
    (n) =>
      n.classList?.contains("github-pulls-spacer") && n.getBoundingClientRect().top < viewHeight,
  );
  console.log(
    JSON.stringify({
      case: "viewport-height-increase",
      before,
      after,
      observedRoot,
      gapStartsAt: visibleGap?.getBoundingClientRect().top ?? null,
      viewportHeight: viewHeight,
    }),
  );
  assert(
    !visibleGap,
    "resizing the viewport must not leave an unmounted spacer inside the visible area",
  );
  scroll.scrollTop = 10000;
  scroll.listeners.get("scroll")();
  await paint();
  const visible = items().find((item) => item.getBoundingClientRect().bottom > 0);
  const focused = visible.firstElementChild;
  focused.focus();
  scroll.scrollTop = 18000;
  scroll.listeners.get("scroll")();
  await paint();
  assert(list.contains(focused), "focused row remains mounted outside the viewport");
  assert.equal(document.activeElement, focused);
  await sample();
  assert(
    !controls.at(-1).numbers.includes(Number(focused.dataset.number)),
    "protected offscreen focus is outside the cohort",
  );
  assert(
    items().length < 160,
    "mounted DOM stays bounded after distant scrolling and protected focus",
  );
  assert.equal(focused.getAttribute("aria-setsize"), "500");
  assert(
    Number(focused.getAttribute("aria-posinset")) > 1,
    "ARIA position remains absolute in the catalog",
  );
  viewHeight = 100;
  document.activeElement = body;
  scroll.scrollTop = 0;
  scroll.listeners.get("scroll")();
  await paint();
  const row = items()[0].firstElementChild;
  list.listeners.get("focusin")({ target: row });
  await settle();
  assert.deepEqual(detailReads, [500]);
  readyCore = true;
  assert(handle.activateAnchor());
  await settle();
  assert.deepEqual(detailReads, [500, 500], "the absent peek cannot hide a prepared core on click");
  assert.equal(opened[0].reader.initial.body.core_preview.observed_at, observedAt);
  const page = await import(
    pathToFileURL(`${root}/src/metabrowser/builtin_plugins/github/pull-page.js`)
  );
  assert(page.isEnvelope(opened[0].reader.initial.body));
  const model = page.describePull(opened[0].reader.initial.body, {
    number: 500,
    tab: "",
    nowMs: Date.parse(observedAt) + 120_000,
  });
  assert.equal(model.canRefresh, true, "a prepared-only direct visit still offers Fetch");
  assert.equal(model.refreshing, false);
  assert.equal(model.freshness, "Description fetched 2 min ago by reader");
  assert.equal(model.filesUnavailable, "Changes have not been fetched.");

  const existingTimers = new Set(timers.keys());
  const retry = () =>
    [...timers].find(
      ([id, timer]) =>
        !existingTimers.has(id) && timer.delay === (panel.CORE_BUSY_RETRY_MS ?? 1000),
    );
  const sampleAt = async (top) => {
    scroll.scrollTop = top;
    scroll.listeners.get("scroll")();
    await sample();
  };
  const previous = controls.at(-1);
  const beforeBusy = controls.length;
  refuseAdmission = "busy";
  await sample();
  const demand = controls.at(-1);
  assert.equal(controls.length, beforeBusy + 1, "busy scroll replacement keeps the old token");
  assert.notEqual(demand.window.id, previous.window.id);
  const delayed = retry();
  assert.ok(delayed, "a stable busy window gets one delayed retry");
  refuseAdmission = "busy";
  timers.delete(delayed[0]);
  delayed[1].fn();
  await settle();
  assert.equal(controls.length, beforeBusy + 2);
  assert.deepEqual(controls.at(-1), demand, "retry uses the exact original window");
  assert.equal(retry(), undefined, "a second busy answer never retries again");

  refuseAdmission = "not_owner";
  await sampleAt(600);
  assert.equal(retry(), undefined, "a refusal cannot re-arm the competing window");
  refuseAdmission = "busy";
  await sampleAt(1000);
  assert.ok(retry());
  await sampleAt(1300);
  assert.equal(retry(), undefined, "a changed viewport cancels the previous retry");
  const currentOwner = controls.at(-1);

  holdAdmission = true;
  await sampleAt(1700);
  assert(handle.activateAnchor());
  finishAdmission("busy");
  await settle();
  assert.equal(retry(), undefined, "selection also disarms a busy reply still in flight");
  refuseAdmission = "busy";
  await sampleAt(2100);
  assert.ok(retry());
  handle.setShown(false);
  await settle();
  assert.equal(retry(), undefined, "hide cancels the queued retry");
  assert.deepEqual(
    controls.at(-1),
    { ...currentOwner, numbers: [] },
    "hide releases the old token",
  );
  handle.dispose();
  assert.equal(frames.size, 0);
  assert.equal(timers.size, 0);
  assert(
    observers.every((observer) => observer.nodes.size === 0),
    "dispose releases row and viewport observers",
  );
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
