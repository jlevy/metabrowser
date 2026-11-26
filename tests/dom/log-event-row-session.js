// Browserless session: a JSONL log's event rows are controls a keyboard can reach.
//
// Each row's header opens the event's raw payload. It responded only to a pointer, and
// 0.12's move from inline handlers to one delegated listener also took away the clickable
// node the accessibility tree had shown (mb-lf3v). A header now has a button role, a tab
// stop, an expanded state, and Enter and Space, and a click does what it did.
//
// The SDK and both JSONL plugins load whole, so the unknown-JSONL view runs the agent-log
// renderer the way a browser does. `toggleEvent` is lifted verbatim from app.js, which
// cannot load without a document. The rows are stand-ins built from the markup the
// renderer wrote, so the attributes under test are the ones production emitted.
//
// Each step prints the row's state after an event is dispatched on it, and whether the
// event's default was prevented. Exits 1 on a failed invariant.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sourceRoot = path.join(repoRoot, "src/metabrowser");
const appSource = fs.readFileSync(path.join(sourceRoot, "static/app.js"), "utf8");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

class RowElement {
  constructor(attributes = {}, parentElement = null) {
    this.attributes = { ...attributes };
    this.parentElement = parentElement;
    this.dataset = {};
    this.style = {};
    this.innerHTML = "";
    this.classNames = new Set((attributes.class || "").split(" ").filter(Boolean));
    this.classList = {
      add: (name) => this.classNames.add(name),
      contains: (name) => this.classNames.has(name),
      toggle: (name) => {
        if (!this.classNames.delete(name)) {
          this.classNames.add(name);
        }
      },
    };
  }
  getAttribute(name) {
    return this.attributes[name] ?? null;
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  /** A class, or nothing: the filter bar's listener also asks after its own attributes. */
  closest(selector) {
    for (let node = this; selector.startsWith(".") && node; node = node.parentElement) {
      if (node.classNames?.has(selector.slice(1))) {
        return node;
      }
    }
    return null;
  }
  querySelector(selector) {
    return selector === ".log-event-raw" ? this.raw : null;
  }
  /** Where an opened payload's tree is drawn. */
  appendChild(child) {
    this.children = [...(this.children ?? []), child];
    child.parentElement = this;
    return child;
  }
  remove() {
    const parent = this.parentElement;
    if (parent) {
      parent.children = (parent.children ?? []).filter((child) => child !== this);
      this.parentElement = null;
    }
  }
  addEventListener() {}
}

/** The page's preview pane: the listeners on it, and the markup written into it. */
function createPane(document) {
  const listeners = { click: new Set(), keydown: new Set() };
  return {
    innerHTML: "",
    listeners,
    ownerDocument: document,
    parentElement: null,
    addEventListener(type, listener) {
      listeners[type] = listeners[type] ?? new Set();
      listeners[type].add(listener);
    },
    removeEventListener: (type, listener) => listeners[type]?.delete(listener),
    contains(node) {
      for (let current = node; current; current = current.parentElement) {
        if (current === this) {
          return true;
        }
      }
      return false;
    },
    querySelector: () => null,
    querySelectorAll: () => [],
  };
}

/** The rows the renderer wrote, as stand-ins carrying exactly the attributes in its markup. */
function rowsIn(pane) {
  const rows = [];
  const markup = /<div class="log-event" data-idx="(\d+)"[^>]*><div ([^>]*)>/g;
  for (const match of pane.innerHTML.matchAll(markup)) {
    const attributes = {};
    for (const attribute of match[2].matchAll(/([\w-]+)="([^"]*)"/g)) {
      attributes[attribute[1]] = attribute[2];
    }
    const row = new RowElement({ class: "log-event" }, pane);
    const header = new RowElement(attributes, row);
    row.header = header;
    row.raw = new RowElement({ class: "log-event-raw", "data-raw-idx": match[1] }, row);
    row.summary = new RowElement({ class: "log-event-summary" }, header);
    rows.push(row);
  }
  return rows;
}

const document = {
  addEventListener() {},
  body: { append() {} },
  createElement: (tagName) => new RowElement({ tag: tagName }),
  documentElement: {},
  head: { append() {} },
  querySelector: () => null,
  querySelectorAll: () => [],
  removeEventListener() {},
};
const sandbox = {
  console,
  document,
  fetch: async () => ({ json: async () => ({}), ok: true }),
  Map,
  Promise,
  scheduleHighlightCode() {},
  Set,
  URL,
  clearTimeout,
  setTimeout,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const relative of [
  "static/request-error.js",
  "static/formatters.js",
  "static/inventory-scope.js",
  "static/resource-context.js",
  "static/view-state.js",
  "static/navigation.js",
  "static/plugin-sdk.js",
  "static/filter-controls.js",
  "static/menus.js",
  "static/icons.js",
]) {
  const filename = path.join(sourceRoot, relative);
  vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
}
// The agents plugin's index.js and its agent-log renderers are ES modules, which this realm
// evaluates; they reach the page only through `window`, which is the sandbox's. The
// renderers register their views over index.js's stubs, and their exports are what the
// plugin's `loadLogRenderers` answers the shell's live tail.
globalThis.window = sandbox;
require(path.join(sourceRoot, "builtin_plugins/agents/index.js"));
const agentLog = require(path.join(sourceRoot, "builtin_plugins/agents/agent-log.js"));
{
  const filename = path.join(sourceRoot, "builtin_plugins/unknown_jsonl/index.js");
  vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
}
const toggleEvent = appSource.match(/\nfunction toggleEvent\(header\) \{[\s\S]*?\n\}/);
assert(toggleEvent, "toggleEvent was not found in app.js");
vm.runInContext(toggleEvent[0], sandbox, { filename: "app.js (lifted)" });

const mb = sandbox.metabrowser;
mb.ensureKindAssets = async () => {};
// The declared providers: the agents plugin, whose agent-log renderers generic JSONL draws
// with (its `loadLogRenderers` answers them, without the stylesheet a page loads), and the
// structured plugin, whose tree an opened payload is. The session records each tree it
// is asked to draw rather than drawing it, and answers the structured load as
// `structuredLoad` says, so a step can hold the load open or fail it.
const treeCalls = [];
const structured = {
  renderInlineTree(container, data) {
    treeCalls.push({ container, data });
  },
};
let structuredLoad = () => Promise.resolve(structured);
let structuredLoads = 0;
mb.plugins = {
  load(name) {
    if (name === "agents") {
      return Promise.resolve({ loadLogRenderers: () => Promise.resolve(agentLog) });
    }
    assert(name === "structured", `plugins.load asked for ${name}`);
    structuredLoads += 1;
    return structuredLoad();
  },
};

/** A load the step settles itself. */
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

const LOG = {
  raw: {
    events: [
      { kind: "text", raw: { first: true }, summary: "[text] first" },
      { kind: "tool_call", raw: { second: true }, summary: "[tool] second" },
    ],
    summary: {},
  },
};

function read(row, event) {
  return {
    expanded: row.classList.contains("expanded"),
    ariaExpanded: row.header.getAttribute("aria-expanded"),
    rawMounted: row.raw.dataset.mounted === "1",
    defaultPrevented: event.defaultPrevented,
  };
}

function dispatch(pane, type, target, keys = {}) {
  const event = {
    ...keys,
    defaultPrevented: false,
    target,
    type,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
  for (const listener of pane.listeners[type]) {
    listener(event);
  }
  return event;
}

(async () => {
  const transcript = {};

  for (const [kind, view] of [
    ["agent-log", mb.getRegisteredView("agent-log", "log")],
    ["unknown-jsonl", mb.getRegisteredView("unknown-jsonl", "log")],
  ]) {
    const pane = createPane(document);
    await view.render(pane, LOG);
    const rows = rowsIn(pane);
    assert(rows.length === 2, `${kind}: found ${rows.length} rows`);
    const [row, other] = rows;
    const steps = {};
    steps.markup = rows.map(({ header }) => ({ ...header.attributes }));
    assert(
      rows.every(
        ({ header }) =>
          header.getAttribute("role") === "button" && header.getAttribute("tabindex") === "0",
      ),
      `${kind}: a row is not a control with a tab stop`,
    );

    const enter = dispatch(pane, "keydown", row.header, { key: "Enter" });
    steps["Enter opens the row"] = read(row, enter);
    assert(steps["Enter opens the row"].expanded, `${kind}: Enter did not open the row`);
    assert(steps["Enter opens the row"].rawMounted, `${kind}: Enter did not mount the payload`);
    assert(enter.defaultPrevented, `${kind}: Enter was left to the browser`);

    const space = dispatch(pane, "keydown", row.header, { key: " " });
    steps["Space closes it"] = read(row, space);
    assert(!steps["Space closes it"].expanded, `${kind}: Space did not close the row`);
    assert(space.defaultPrevented, `${kind}: Space would scroll the pane`);

    // Keys that are not a button's, and the ones a button does not act on, change nothing
    // and stay the browser's.
    for (const [name, keys] of Object.entries({
      Tab: { key: "Tab" },
      "a letter": { key: "a" },
      "Ctrl+Enter": { ctrlKey: true, key: "Enter" },
      "Shift+Space": { key: " ", shiftKey: true },
      "a held Enter": { key: "Enter", repeat: true },
    })) {
      const event = dispatch(pane, "keydown", row.header, keys);
      assert(!row.classList.contains("expanded"), `${kind}: ${name} opened the row`);
      assert(!event.defaultPrevented, `${kind}: ${name} was taken from the browser`);
    }

    // A pointer's click anywhere on the header works as before, and keeps the state true.
    const click = dispatch(pane, "click", row.summary);
    steps["a click on the summary opens the row"] = read(row, click);
    assert(row.classList.contains("expanded"), `${kind}: a click did not open the row`);
    assert(!other.classList.contains("expanded"), `${kind}: a click opened another row`);
    const keyAfterClick = dispatch(pane, "keydown", row.header, { key: "Enter" });
    steps["Enter after a click closes it"] = read(row, keyAfterClick);
    assert(!row.classList.contains("expanded"), `${kind}: Enter did not follow the click`);

    // Keys inside the open payload belong to what is there, not to the row around it.
    dispatch(pane, "keydown", other.header, { key: "Enter" });
    const inPayload = new RowElement({ class: "structured-node" }, other.raw);
    const payloadKey = dispatch(pane, "keydown", inPayload, { key: " " });
    steps["a key inside the open payload leaves the row"] = read(other, payloadKey);
    assert(other.classList.contains("expanded"), `${kind}: a key in the payload closed the row`);
    assert(!payloadKey.defaultPrevented, `${kind}: a key in the payload was taken`);

    // A row the live tail appends is the same control.
    assert(
      agentLog
        .renderLogEvent(pane, LOG.raw.events[0], 2)
        .includes('role="button" tabindex="0" aria-expanded="false"'),
      `${kind}: an appended row is not a control`,
    );

    view.dispose(pane);
    assert(pane.listeners.keydown.size === 0, `${kind}: disposal left a key listener`);
    assert(pane.listeners.click.size === 0, `${kind}: disposal left a click listener`);
    transcript[kind] = steps;
  }

  // An opened payload (agents/agent-log.js mountLogEventRaw): an object is the structured
  // tree, drawn once the load settles; a failed load leaves the flat JSON block and no
  // empty wrapper; a string is the flat block at once; and closing and reopening a row
  // while the load is in flight draws it once.
  {
    const view = mb.getRegisteredView("agent-log", "log");
    const payloads = {
      raw: {
        events: [
          { kind: "text", raw: { tree: 1 }, summary: "[text] a tree" },
          { kind: "text", raw: { tree: 2 }, summary: "[text] a failed load" },
          { kind: "text", raw: "a string payload", summary: "[text] a string" },
          { kind: "text", raw: { tree: 4 }, summary: "[text] toggled while loading" },
        ],
        summary: {},
      },
    };
    const pane = createPane(document);
    await view.render(pane, payloads);
    const [object, failed, string, toggled] = rowsIn(pane);
    const mountRaw = sandbox.metabrowserAgentLog.mountLogEventRaw;
    const steps = {};
    const flatBlock = (row) =>
      (row.raw.innerHTML.match(/<pre><code class="language-json">/g) ?? []).length;

    let load = deferred();
    structuredLoad = () => load.promise;
    treeCalls.length = 0;
    mountRaw(object.raw);
    const beforeSettle = treeCalls.length;
    load.resolve(structured);
    await settle();
    steps["an object payload is drawn as the tree once the load settles"] = {
      treesBeforeTheLoadSettled: beforeSettle,
      trees: treeCalls.length,
      drawnInTheWrapper: treeCalls[0]?.container === object.raw.children?.[0],
      payload: treeCalls[0]?.data,
      flatBlocks: flatBlock(object),
    };
    assert(beforeSettle === 0 && treeCalls.length === 1, "an object payload was not drawn once");
    assert(treeCalls[0].container === object.raw.children[0], "the tree is not in its wrapper");
    assert(treeCalls[0].data === payloads.raw.events[0].raw, "the tree is not the payload");

    load = deferred();
    treeCalls.length = 0;
    const warn = console.warn;
    console.warn = () => {};
    mountRaw(failed.raw);
    load.reject(new Error("the structured plugin did not load"));
    await settle();
    console.warn = warn;
    steps["a failed load leaves the flat block and no wrapper"] = {
      trees: treeCalls.length,
      wrappers: failed.raw.children?.length ?? 0,
      flatBlocks: flatBlock(failed),
    };
    assert(treeCalls.length === 0, "a failed load drew a tree");
    assert((failed.raw.children?.length ?? 0) === 0, "a failed load left its empty wrapper");
    assert(flatBlock(failed) === 1, "a failed load did not leave one flat block");

    const loadsBefore = structuredLoads;
    mountRaw(string.raw);
    steps["a string payload is the flat block at once"] = {
      structuredLoads: structuredLoads - loadsBefore,
      flatBlocks: flatBlock(string),
    };
    assert(structuredLoads === loadsBefore, "a string payload loaded the structured plugin");
    assert(flatBlock(string) === 1, "a string payload was not mounted at once");

    load = deferred();
    treeCalls.length = 0;
    dispatch(pane, "click", toggled.summary);
    dispatch(pane, "click", toggled.summary);
    dispatch(pane, "click", toggled.summary);
    load.resolve(structured);
    await settle();
    steps["closing and reopening while the load is in flight draws once"] = {
      expanded: toggled.classList.contains("expanded"),
      trees: treeCalls.length,
      wrappers: toggled.raw.children?.length ?? 0,
    };
    assert(toggled.classList.contains("expanded"), "the row did not end open");
    assert(treeCalls.length === 1, `the toggled row drew ${treeCalls.length} trees`);
    assert(toggled.raw.children.length === 1, "the toggled row mounted twice");

    view.dispose(pane);
    transcript["opened payloads"] = steps;
  }

  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
