const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const plugin = path.join(process.argv[2], "src/metabrowser/builtin_plugins/diff");

class Element {
  constructor(tag = "") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.dataset = {};
    this.classList = { add() {} };
    this.hidden = false;
    this.textContent = "";
    this.content = this;
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

  get firstElementChild() {
    return this.children[0];
  }

  after(child) {
    const siblings = this.parent.children;
    siblings.splice(siblings.indexOf(this) + 1, 0, child);
  }

  before(...children) {
    const siblings = this.parent.children;
    siblings.splice(siblings.indexOf(this), 0, ...children);
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
  constructor(notify) {
    observer = this;
    this.notify = notify;
    this.observed = new Set();
  }

  observe(target) {
    this.observed.add(target);
  }

  disconnect() {
    this.observed.clear();
  }
};

async function main() {
  const { createMarkdownViews, isSnapshotTarget, supportsMarkdownChange } = await import(
    pathToFileURL(path.join(plugin, "diff-markdown.js"))
  );
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

  const query = new URLSearchParams({
    number: "346",
    left: "1".repeat(40),
    right: "2".repeat(40),
    store: "3".repeat(16),
    side: "head",
    path: "g1-ZG9jcw/g1-UkVBRE1FLm1k",
  });
  const href = `/api/plugin/github/pull-snapshot?${query}`;
  assert.equal(isSnapshotTarget(href, false), true);
  assert.equal(isSnapshotTarget(`${href}&mode=image`, true), true);
  assert.equal(isSnapshotTarget(`${href}&mode=image`, false), false);
  assert.equal(isSnapshotTarget(`https://example.org${href}`, false), false);
  assert.equal(isSnapshotTarget("/raw?path=README.md", true), false);
  assert.equal(isSnapshotTarget(href.replace("g1-ZG9jcw", ".."), false), false);

  const calls = [];
  let assets = 0;
  const inert = {
    sanitizeNodes: () => [],
    kpressProse: () => make("div"),
  };
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
      change();
    },
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
    const [, progress, fallback, rendered] = section.children;
    return {
      section,
      source,
      rendered,
      progress,
      fallback,
      state,
      get renderedChoice() {
        return bar.children[1].children[0];
      },
      get sourceChoice() {
        return bar.children[1].children[1];
      },
    };
  }

  const a = file("a");
  const b = file("b");
  const c = file("c");
  view.observe(root, null, 240);
  assert.equal(calls.length, 0);
  assert.equal(a.renderedChoice.attributes.get("aria-checked"), "true");
  const arrival = (file) => ({ target: file.section, isIntersecting: true });
  observer.notify([arrival(a), arrival(b)]);
  assert.deepEqual(
    calls.map(({ id }) => id),
    ["a"],
  );
  assert.equal(a.progress.hidden, false);
  await a.sourceChoice.click();
  assert.equal(a.progress.hidden, true);
  assert.equal(a.source.hidden, false);
  assert.equal(document.activeElement, a.sourceChoice);
  assert.equal(calls[0].signal.aborted, true);
  assert.equal(calls.length, 1, "the next file waits for the first request to settle");
  const ready = {
    version: "markdown-diff-v1",
    status: "ready",
    source_only: true,
    blocks: [{ kind: "added", side: "new", html: "<p>Edited <ins>word</ins></p>" }],
  };
  calls[0].resolve(ready);
  await new Promise(setImmediate);
  assert.deepEqual(
    calls.map(({ id }) => id),
    ["a", "b"],
  );
  assert.equal(a.rendered.hidden, true, "late response cannot override Source");
  assert.equal(assets, 0, "the sanitizer loads only for an admitted projection");

  observer.notify([arrival(c)]);
  b.state.setExpanded(false);
  assert.equal(calls[1].signal.aborted, true);
  assert.equal(b.progress.hidden, true);
  calls[1].resolve(ready);
  await new Promise(setImmediate);
  assert.deepEqual(
    calls.map(({ id }) => id),
    ["a", "b", "c"],
  );
  c.renderedChoice.focus();
  calls[2].resolve({ status: "too_large" });
  await new Promise(setImmediate);
  assert.equal(c.sourceChoice.attributes.get("aria-checked"), "true");
  assert.equal(c.renderedChoice.disabled, true);
  assert.equal(document.activeElement, c.sourceChoice);
  assert.equal(c.fallback.hidden, false);

  await a.renderedChoice.click();
  assert.deepEqual(
    calls.map(({ id }) => id),
    ["a", "b", "c", "a"],
  );
  calls[3].resolve(ready);
  await new Promise(setImmediate);
  assert.equal(a.rendered.hidden, false);
  assert.equal(a.source.hidden, true);
  assert.equal(a.rendered.children.length, 1);
  assert.equal(assets, 1);
  await a.sourceChoice.click();
  assert.equal(a.source.hidden, false);
  await a.renderedChoice.click();
  assert.equal(a.rendered.hidden, false);
  assert.equal(calls.length, 4, "switching back reuses rendered content");
  b.state.setExpanded(true);
  assert.equal(calls.length, 5);
  calls[4].reject(new Error("Server is busy"));
  await new Promise(setImmediate);
  assert.equal(b.sourceChoice.attributes.get("aria-checked"), "true");
  assert.equal(b.renderedChoice.disabled, false, "a transport error allows another attempt");
  assert.match(b.fallback.textContent, /retry/);
  await b.renderedChoice.click();
  assert.equal(calls.length, 6);
  assert.equal(b.fallback.hidden, true);
  view.dispose();
  assert.equal(calls[5].signal.aborted, true);
  assert.equal(observer.observed.size, 0);
  assert.equal(sharedChange, undefined);
  calls[5].resolve(ready);
  await new Promise(setImmediate);
  assert.equal(b.rendered.hidden, true);
  console.log("diff Markdown view OK");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
