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
  createElement: () => ({ appendChild() {}, addEventListener() {}, setAttribute() {} }),
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
  "static/icons.js",
  "builtin_plugins/agent_log/index.js",
  "builtin_plugins/unknown_jsonl/index.js",
]) {
  const filename = path.join(sourceRoot, relative);
  vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
}
const toggleEvent = appSource.match(/\nfunction toggleEvent\(header\) \{[\s\S]*?\n\}/);
assert(toggleEvent, "toggleEvent was not found in app.js");
vm.runInContext(toggleEvent[0], sandbox, { filename: "app.js (lifted)" });

const mb = sandbox.metabrowser;
mb.ensureKindAssets = async () => {};

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
      mb.builtins.agentLog
        .renderLogEvent(pane, LOG.raw.events[0], 2)
        .includes('role="button" tabindex="0" aria-expanded="false"'),
      `${kind}: an appended row is not a control`,
    );

    view.dispose(pane);
    assert(pane.listeners.keydown.size === 0, `${kind}: disposal left a key listener`);
    assert(pane.listeners.click.size === 0, `${kind}: disposal left a click listener`);
    transcript[kind] = steps;
  }

  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
