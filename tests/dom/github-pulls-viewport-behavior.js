// Production mount with deterministic geometry; viewport growth must fill the newly visible area.
const assert = require("node:assert/strict");
const { pathToFileURL } = require("node:url");
const root = require("node:path").resolve(__dirname, "../..");
const { FakeNode, FakeElement } = require(`${root}/tests/dom/pulls-test-dom.js`);
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
  fetch: async (route) => {
    const q = new URL(route, "http://localhost").searchParams,
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
        open() {},
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
  await paint();
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
  await paint();
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
  assert(
    items().length < 160,
    "mounted DOM stays bounded after distant scrolling and protected focus",
  );
  assert.equal(focused.getAttribute("aria-setsize"), "500");
  assert(
    Number(focused.getAttribute("aria-posinset")) > 1,
    "ARIA position remains absolute in the catalog",
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
