const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const plugin = path.join(process.argv[2], "src/metabrowser/builtin_plugins/diff");

class ClassList {
  constructor() {
    this.names = new Set();
  }

  add(...names) {
    for (const name of names) {
      this.names.add(name);
    }
  }

  remove(name) {
    this.names.delete(name);
  }

  toggle(name, force) {
    const on = force ?? !this.names.has(name);
    if (on) {
      this.names.add(name);
    } else {
      this.names.delete(name);
    }
    return on;
  }

  contains(name) {
    return this.names.has(name);
  }
}

class Element {
  constructor(tag = "") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.dataset = {};
    this.classList = new ClassList();
    this.hidden = false;
    this.textContent = "";
    this.content = this;
    this.open = false;
  }

  set className(value) {
    this.classList = new ClassList();
    this.classList.add(...value.split(" ").filter(Boolean));
  }

  get className() {
    return [...this.classList.names].join(" ");
  }

  append(...children) {
    for (const child of children) {
      child.parent = this;
      this.children.push(child);
    }
  }

  prepend(child) {
    this.children.unshift(child);
  }

  replaceChildren(...children) {
    this.children = [];
    this.append(...children);
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  get firstElementChild() {
    return this.children[0];
  }

  after(...children) {
    const siblings = this.parent.children;
    siblings.splice(siblings.indexOf(this) + 1, 0, ...children);
    for (const child of children) {
      child.parent = this.parent;
    }
  }

  before(...children) {
    const siblings = this.parent.children;
    siblings.splice(siblings.indexOf(this), 0, ...children);
    for (const child of children) {
      child.parent = this.parent;
    }
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  click() {
    this.focus();
    this.listeners.get("click")();
    return Promise.resolve();
  }

  contains(node) {
    return this === node || this.children.some((child) => child.contains?.(node));
  }

  set innerHTML(spec) {
    if (typeof spec === "string") {
      this.html = spec;
      return;
    }
    // Stand in for parsing the shared chip family's groupHtml output.
    this.children = spec.options.map(({ value }) => {
      const chip = make("button");
      chip.dataset.chipValue = value;
      chip.setAttribute("aria-checked", String(spec.value === value));
      chip.addEventListener("click", () => sharedChange(spec.key, value, spec.select));
      return chip;
    });
  }

  focus() {
    document.activeElement = this;
  }

  querySelectorAll(selector) {
    return selector === "button[data-chip-value]" ? this.children : [];
  }
}

const make = (tag) => new Element(tag);
let sharedChange;
globalThis.document = {
  createElement: make,
  createTextNode: (textContent) => ({ textContent }),
  createDocumentFragment: make,
  implementation: { createHTMLDocument: () => ({ createElement: make }) },
};

let observer;
globalThis.IntersectionObserver = class {
  constructor(notify, options) {
    observer = this;
    this.notify = notify;
    this.options = options;
    this.observed = new Set();
  }

  observe(target) {
    this.observed.add(target);
  }

  disconnect() {
    this.observed.clear();
  }
};

/** Timers the test advances by hand. */
function clock() {
  let time = 0;
  const pending = new Map();
  let next = 1;
  return {
    now: () => time,
    later(callback, ms) {
      const handle = next++;
      pending.set(handle, { at: time + ms, callback });
      return handle;
    },
    cancel(handle) {
      pending.delete(handle);
    },
    advance(ms) {
      time += ms;
      for (const [handle, timer] of [...pending].sort((a, b) => a[1].at - b[1].at)) {
        if (timer.at <= time) {
          pending.delete(handle);
          timer.callback();
        }
      }
    },
    get pending() {
      return pending.size;
    },
  };
}

function texts(node) {
  return node.children.flatMap((child) =>
    child.children ? [child.textContent, ...texts(child)] : [child.textContent],
  );
}

async function main() {
  const {
    appendBlocks,
    createMarkdownViews,
    firstScreenMarkdown,
    snapshotTargets,
    supportsMarkdownChange,
  } = await import(pathToFileURL(path.join(plugin, "diff-markdown.js")));
  const md = { entry_type: "file", path: "docs/readme.MD" };
  assert.equal(supportsMarkdownChange({ availability: "ready", old: null, new: md }), true);
  assert.equal(supportsMarkdownChange({ availability: "deferred", old: md, new: null }), true);
  assert.equal(
    supportsMarkdownChange({ availability: "ready", old: md, new: { ...md, path: "README.txt" } }),
    false,
  );
  assert.equal(
    supportsMarkdownChange({ availability: "ready", new: { ...md, entry_type: "symlink" } }),
    false,
  );

  // Snapshot addresses are the comparison's own route, which the server names, completed
  // with a side, a path and, for an image, its mode.
  const route = `/api/plugin/github/pull-snapshot?${new URLSearchParams({
    number: "346",
    left: "1".repeat(40),
    right: "2".repeat(40),
    store: "3".repeat(16),
  })}`;
  const isSnapshotTarget = snapshotTargets(route);
  const href = `${route}&side=head&path=g1-ZG9jcw%2Fg1-UkVBRE1FLm1k`;
  assert.equal(isSnapshotTarget(href, false), true);
  assert.equal(isSnapshotTarget(`${href}&mode=document`, false), true);
  assert.equal(isSnapshotTarget(`${href}&mode=image`, true), true);
  assert.equal(isSnapshotTarget(`${href}&mode=image`, false), false);
  assert.equal(isSnapshotTarget(`${href}&mode=source`, false), false);
  assert.equal(isSnapshotTarget(`${href}&side=base`, false), false, "a repeated name");
  assert.equal(isSnapshotTarget(`${href}&offset=9`, false), false);
  assert.equal(isSnapshotTarget(`https://example.org${href}`, false), false);
  assert.equal(isSnapshotTarget(href.replace("left=1", "left=0"), false), false);
  assert.equal(isSnapshotTarget("/raw?path=README.md", true), false);
  assert.equal(isSnapshotTarget(href.replace("g1-ZG9jcw", ".."), false), false);
  assert.equal(snapshotTargets(undefined)(href, false), false, "no route opens nothing");

  // The first screen's Markdown files, asked for ahead of Changes.
  const entry = (id, path, availability = "ready") => ({
    id,
    availability,
    old: null,
    new: { entry_type: "file", path },
  });
  assert.deepEqual(
    firstScreenMarkdown([
      entry("1", "a.md"),
      entry("2", "b.py"),
      entry("3", "c.md", "deferred"),
      entry("4", "d.md", "too_large"),
      entry("5", "e.md"),
      entry("6", "f.md"),
      entry("7", "g.md"),
      entry("8", "h.md"),
      entry("9", "i.md"),
    ]),
    ["1", "3", "5", "6"],
  );

  // Long unchanged runs fold, a folded run is built only when it opens, and a context
  // block whose source says more never folds.
  const built = [];
  const build = (html) => {
    built.push(html);
    return make("div");
  };
  const context = (n) => ({ kind: "context", html: `<p id="user-content-x-${n}">${n}</p>` });
  const fragment = make("div");
  const folds = appendBlocks(
    fragment,
    [
      ...[0, 1, 2, 3, 4, 5, 6, 7].map(context),
      { kind: "context", html: "<p>flagged</p>", source_only: true },
      { kind: "added", html: "<p>new</p>", source_only: true },
    ],
    build,
  );
  const details = fragment.children.find((child) => child.tagName === "DETAILS");
  assert.equal(details.children[0].textContent, "4 unchanged blocks");
  assert.equal(details.children.length, 1, "a closed fold holds only its summary");
  assert.deepEqual(
    built,
    [0, 1, 6, 7].map((n) => context(n).html).concat(["<p>flagged</p>", "<p>new</p>"]),
  );
  const flagged = fragment.children.at(-1);
  assert.ok(flagged.classList.contains("diff-markdown-source-only"));
  assert.ok(texts(flagged).includes("Source shows changes not shown here."));
  assert.ok(texts(flagged).includes("Added: "));
  assert.deepEqual(
    [...folds.keys()],
    [2, 3, 4, 5].map((n) => `user-content-x-${n}`),
  );
  folds.get("user-content-x-3")();
  assert.equal(details.open, true);
  assert.equal(details.children.length, 5, "opening a fold builds its blocks once");
  details.listeners.get("toggle")();
  assert.equal(details.children.length, 5);

  const calls = [];
  let assets = 0;
  let mutations = 0;
  const inert = {
    sanitizeNodes: () => [],
    kpressProse: () => make("div"),
  };
  const time = clock();
  const root = make("div");
  const view = createMarkdownViews({
    controls: {
      groupHtml: (spec) => spec,
      bind(container, { onChange }) {
        assert.equal(container, root);
        sharedChange = onChange;
        return () => {
          sharedChange = undefined;
        };
      },
    },
    load(id, signal) {
      return new Promise((resolve, reject) => calls.push({ id, signal, resolve, reject }));
    },
    async ensureInert() {
      assets += 1;
      return inert;
    },
    async loadStyles() {},
    mutate(change) {
      mutations += 1;
      change();
    },
    now: time.now,
    later: time.later,
    cancel: time.cancel,
  });
  function file(id) {
    const section = make("section");
    root.append(section);
    const bar = make("div");
    const source = make("div");
    source.id = id;
    section.append(bar, source);
    bar.append(make("button"));
    const state = view.add({ section, bar, source, id });
    const [, fallback, rendered] = section.children;
    const [, control, progress] = bar.children;
    return {
      section,
      source,
      rendered,
      progress,
      fallback,
      state,
      get renderedChoice() {
        return control.children[0];
      },
      get sourceChoice() {
        return control.children[1];
      },
    };
  }

  const a = file("a");
  const b = file("b");
  const c = file("c");
  const d = file("d");
  assert.equal(a.source.hidden, true, "a file waits for Rendered before showing Source");
  view.observe(root, null);
  assert.equal(observer.options.rootMargin, "0px 0px 100% 0px", "a viewport of lookahead");
  assert.equal(calls.length, 0);
  assert.equal(a.renderedChoice.attributes.get("aria-checked"), "true");
  const arrival = (file) => ({ target: file.section, isIntersecting: true });
  observer.notify([arrival(a), arrival(b), { target: d.section, isIntersecting: false }]);
  assert.equal(c.source.hidden, false, "a file away from the first screen shows Source at once");
  assert.equal(d.source.hidden, false);
  assert.equal(b.source.hidden, true);
  assert.deepEqual(
    calls.map(({ id }) => id),
    ["a"],
  );
  assert.ok(a.progress.classList.contains("mb-delayed-loading"), "progress waits for the delay");
  time.advance(50);
  assert.equal(a.source.hidden, false, "past the loading delay Source shows");
  assert.equal(b.source.hidden, false);
  await a.sourceChoice.click();
  assert.equal(a.progress.classList.contains("mb-delayed-loading"), false);
  assert.equal(a.source.hidden, false);
  assert.equal(document.activeElement, a.sourceChoice);
  assert.equal(
    calls[0].signal.aborted,
    false,
    "the server finishes it anyway, so the answer is kept",
  );
  assert.equal(calls.length, 1, "the next file waits for the first request to settle");
  const ready = {
    version: "markdown-diff-v1",
    status: "ready",
    source_only: true,
    blocks: [
      { kind: "added", side: "new", html: "<p>Edited <ins>word</ins></p>", source_only: false },
    ],
  };
  calls[0].resolve(ready);
  await new Promise(setImmediate);
  assert.deepEqual(
    calls.map(({ id }) => id),
    ["a", "b"],
  );
  assert.equal(a.rendered.hidden, true, "late response cannot override Source");
  assert.equal(a.source.hidden, false);
  assert.equal(assets, 1, "the sanitizer loads for the first admitted projection");

  // A busy server is transient: the file keeps Rendered and asks again after a wait.
  const busy = Object.assign(new Error("busy"), { status: 429 });
  calls[1].reject(busy);
  await new Promise(setImmediate);
  assert.equal(b.renderedChoice.attributes.get("aria-checked"), "true");
  assert.equal(b.fallback.textContent, "");
  assert.equal(calls.length, 2);
  time.advance(99);
  assert.equal(calls.length, 2);
  time.advance(1);
  assert.deepEqual(
    calls.map(({ id }) => id),
    ["a", "b", "b"],
  );
  mutations = 0;
  calls[2].resolve(ready);
  await new Promise(setImmediate);
  assert.equal(b.rendered.hidden, false);
  assert.equal(b.source.hidden, true);
  assert.equal(b.progress.classList.contains("mb-delayed-loading"), false);
  assert.equal(mutations, 1, "a ready file is drawn and its progress cleared in one mutation");

  observer.notify([arrival(c)]);
  b.state.setExpanded(false);
  assert.equal(b.source.hidden, true, "a collapsed file keeps its Rendered view");
  assert.deepEqual(
    calls.map(({ id }) => id),
    ["a", "b", "b", "c"],
  );
  c.renderedChoice.focus();
  calls[3].resolve({ status: "too_large" });
  await new Promise(setImmediate);
  assert.equal(c.sourceChoice.attributes.get("aria-checked"), "true");
  assert.equal(c.renderedChoice.disabled, true);
  assert.equal(document.activeElement, c.sourceChoice);
  assert.equal(c.fallback.hidden, false);

  await a.renderedChoice.click();
  assert.equal(calls.length, 4, "the answer that arrived after Source was chosen is reused");
  assert.equal(a.rendered.hidden, false);
  assert.equal(a.source.hidden, true);
  const [shown] = a.rendered.children;
  assert.equal(shown.children.length, 2, "the notice and the one block");
  assert.equal(shown.children[0].textContent, "Source shows additional changes.");
  assert.equal(assets, 1);
  await a.sourceChoice.click();
  assert.equal(a.source.hidden, false);
  await a.renderedChoice.click();
  assert.equal(a.rendered.hidden, false);
  assert.equal(calls.length, 4, "switching back reuses rendered content");

  observer.notify([arrival(d)]);
  assert.equal(calls.length, 5);
  calls[4].reject(new Error("Server is broken"));
  await new Promise(setImmediate);
  assert.equal(d.sourceChoice.attributes.get("aria-checked"), "true");
  assert.equal(d.renderedChoice.disabled, false, "a transport error allows another attempt");
  assert.match(d.fallback.textContent, /retry/);
  await d.renderedChoice.click();
  assert.equal(calls.length, 6);
  assert.equal(d.fallback.hidden, true);
  view.dispose();
  assert.equal(calls[5].signal.aborted, true, "disposal stops the request in flight");
  assert.equal(observer.observed.size, 0);
  assert.equal(sharedChange, undefined);
  assert.equal(time.pending, 0, "disposal cancels every timer");
  calls[5].resolve(ready);
  await new Promise(setImmediate);
  assert.equal(d.rendered.hidden, true);
  console.log("diff Markdown view OK");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
