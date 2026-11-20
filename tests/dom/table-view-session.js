// Browserless session: the table view, driven through a scripted page.
//
// The table plugin (src/metabrowser/builtin_plugins/table/) draws one table of a tabular
// source from the table routes. The server sorts, filters, searches, pages, and counts
// (table_source.py and the delimited source); the page owns what the address says the
// view shows, which rows it draws, the focus, the open record, and the columns that fit
// (table-model.js), and draws what the routes answer (table-view.js).
//
// This loads both production modules whole and drives `mountTable` through a page of
// stand-ins: the SDK's `fetchPluginData`, `navigation`, and `tooltip`; a window whose
// timers and animation frames the session runs; a history Back walks; and a DOM of just
// enough nodes to read the view back (pulls-test-dom.js). The answers are the server's,
// recorded in tests/fixtures/table-view-responses.json and
// tests/fixtures/table-view-long-responses.json by tests/test_table_view_session.py, which
// fails when they drift; a request the recordings do not hold fails the session. A
// generation, which names a file's identity and time, is recorded as `G`.
//
// Each step prints what the page shows after it, and the requests it made. Exits 1 on a
// failed invariant.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { FakeElement } = require("./pulls-test-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const plugin = path.join(repoRoot, "src/metabrowser/builtin_plugins/table");
const answers = {};
for (const name of ["table-view-responses.json", "table-view-long-responses.json"]) {
  Object.assign(
    answers,
    JSON.parse(fs.readFileSync(path.join(repoRoot, "tests/fixtures", name), "utf8")).answers,
  );
}

// ── A DOM of just enough nodes ─────────────────────────────────

/** The pulls DOM's element, with every listener of a type, a box, and form values. */
class Element extends FakeElement {
  constructor(tag) {
    super(tag);
    this.handlers = new Map();
    this.scrollTop = 0;
    this.clientHeight = 0;
    this.clientWidth = 0;
    this.value = "";
    this.checked = false;
    this.selected = false;
  }
  addEventListener(type, listener) {
    const list = this.handlers.get(type) ?? [];
    list.push(listener);
    this.handlers.set(type, list);
  }
  removeEventListener(type, listener) {
    const list = this.handlers.get(type) ?? [];
    this.handlers.set(
      type,
      list.filter((item) => item !== listener),
    );
  }
  getBoundingClientRect() {
    return { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 };
  }
  get options() {
    return this.childNodes.filter((node) => node.localName === "option");
  }
}

const documentStandIn = {
  createElement: (tag) => new Element(tag),
  body: new Element("body"),
  activeElement: null,
};
globalThis.document = documentStandIn;

/** Every element under *node*, in document order. */
function* walk(node) {
  for (const child of node.childNodes ?? []) {
    if (child instanceof Element) {
      yield child;
      yield* walk(child);
    }
  }
}

function find(node, test) {
  for (const element of walk(node)) {
    if (test(element)) {
      return element;
    }
  }
  return null;
}

function findAll(node, test) {
  return [...walk(node)].filter(test);
}

const hasClass = (name) => (element) => element.classes.has(name);

/** Dispatch *type* at *target*, bubbling to every ancestor's listeners. */
function dispatch(target, type, init = {}) {
  let prevented = false;
  const event = {
    type,
    target,
    button: 0,
    shiftKey: false,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    ...init,
    preventDefault() {
      prevented = true;
    },
  };
  for (let node = target; node; node = node.parentNode) {
    for (const listener of node.handlers?.get(type) ?? []) {
      listener(event);
    }
  }
  return { prevented, event };
}

function click(target, init) {
  return dispatch(target, "click", init);
}

function key(target, keyName, init = {}) {
  return dispatch(target, "keydown", { key: keyName, ...init });
}

// ── The page's services ────────────────────────────────────────

const timers = [];
let clock = 0;
const windowListeners = new Map();
const pageWindow = {
  addEventListener(type, listener) {
    windowListeners.set(type, [...(windowListeners.get(type) ?? []), listener]);
  },
  removeEventListener(type, listener) {
    windowListeners.set(
      type,
      (windowListeners.get(type) ?? []).filter((item) => item !== listener),
    );
  },
  setTimeout(callback, ms) {
    const timer = { at: clock + ms, callback };
    timers.push(timer);
    return timer;
  },
  clearTimeout(timer) {
    const index = timers.indexOf(timer);
    if (index >= 0) {
      timers.splice(index, 1);
    }
  },
  requestAnimationFrame(callback) {
    return pageWindow.setTimeout(callback, 16);
  },
  cancelAnimationFrame(timer) {
    pageWindow.clearTimeout(timer);
  },
  getSelection: () => ({ isCollapsed: true, toString: () => "" }),
};

function emit(type) {
  for (const listener of windowListeners.get(type) ?? []) {
    listener({ type });
  }
}

/** Let *ms* pass: run the timers and frames due, in order. */
function tick(ms) {
  clock += ms;
  for (;;) {
    timers.sort((a, b) => a.at - b.at);
    const due = timers[0];
    if (!due || due.at > clock) {
      return;
    }
    timers.shift();
    due.callback();
  }
}

/** The address's history: the shell's navigation as a plugin sees it. */
const entries = [];
let position = -1;
const history = {
  state: null,
  back() {
    position -= 1;
    history.state = entries[position].state;
    emit("popstate");
  },
  replaceState(state) {
    history.state = state;
    entries[position].state = state;
  },
};

const requests = [];
const unrecorded = [];
let hold = null;
const tooltips = [];

function keyOf(route, params) {
  const sorted = Object.entries(params).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  return `${route}?${new URLSearchParams(sorted)}`;
}

const sdk = {
  escapeHtml: (value) => String(value).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`),
  tooltip: {
    show: (html, anchor) => tooltips.push({ show: html, anchor: anchor.className }),
    hide: (within) => tooltips.push({ hide: within?.className ?? null }),
  },
  navigation: {
    current: () => (position >= 0 ? entries[position].target : null),
    href: (target) => `/view/${target.path}${target.query ? `?${target.query}` : ""}`,
    async open(target, how = {}) {
      const entry = { target: { path: target.path, query: target.query ?? "" }, state: null };
      if (how.replace && position >= 0) {
        entries[position] = { ...entry, state: entries[position].state };
      } else {
        entries.splice(position + 1);
        entries.push(entry);
        position += 1;
        history.state = null;
      }
    },
  },
  async fetchPluginData(pluginName, route, params, options) {
    assert.equal(pluginName, "table");
    const key = keyOf(route, params);
    requests.push(key);
    if (hold) {
      await new Promise((resolve) => hold.push(resolve));
    }
    if (options?.signal?.aborted) {
      const error = new Error("aborted");
      error.name = "AbortError";
      throw error;
    }
    const answer = answers[key];
    if (!answer) {
      unrecorded.push(key);
      throw Object.assign(new Error(`unrecorded ${key}`), { status: 599 });
    }
    if (answer.status !== 200) {
      throw Object.assign(new Error(`fetchPluginData table/${route}: ${answer.status}`), {
        status: answer.status,
        payload: answer.body,
      });
    }
    return JSON.parse(JSON.stringify(answer.body));
  },
};

// ── Reading the page back ──────────────────────────────────────

function text(node) {
  return node ? node.textContent.replace(/\s+/g, " ").trim() : null;
}

function cellText(td) {
  const box = td.firstChild;
  const parts = [text(td)];
  if (box?.classes?.has("data-literal")) {
    parts.push("[mono]");
  }
  if (td.classes.has("data-num")) {
    parts.push("[num]");
  }
  for (const kind of ["null", "absent", "empty"]) {
    if (box?.classes?.has(`table-cell-${kind}`)) {
      parts.push(`[${kind}]`);
    }
  }
  return parts.join(" ");
}

/** What the page shows: the address, the toolbar, the header, and the drawn rows. */
function shown(view, { rows = 6 } = {}) {
  const root = view.container;
  const table = find(root, (node) => node.localName === "table");
  const body = find(table, (node) => node.localName === "tbody");
  const drawn = body.childNodes.filter((tr) => !tr.classes.has("table-spacer"));
  const spacers = body.childNodes
    .filter((tr) => tr.classes.has("table-spacer"))
    .map((tr) => tr.firstChild.attributes.get("style"));
  const heads = findAll(
    table,
    (node) => node.localName === "th" && node.attributes.get("scope") === "col",
  );
  const record = find(root, hasClass("table-record"));
  return {
    address: sdk.navigation.current()?.query ?? "",
    status: text(find(root, hasClass("table-status"))),
    chips: findAll(root, hasClass("table-chip")).map((chip) => text(chip.firstChild)),
    notes: findAll(root, hasClass("table-notice")).map(text),
    empty: text(find(root, hasClass("table-empty"))),
    table: table.hidden
      ? "hidden"
      : {
          role: table.attributes.get("role") ?? "table",
          rowcount: table.attributes.get("aria-rowcount") ?? null,
          lines: table.classes.has("table-lines-2") ? 2 : 1,
          header: heads.map((th) => {
            const sort = th.attributes.get("aria-sort");
            return `${text(th).replace("▾", "").trim()}${sort ? ` (${sort})` : ""}`;
          }),
          drawn: drawn.length,
          first: drawn[0]?.attributes.get("aria-rowindex") ?? drawn[0]?.dataset.index,
          spacers,
          rows: drawn
            .slice(0, rows)
            .map((tr) =>
              tr.childNodes
                .map((cell) => (cell.localName === "th" ? text(cell) : cellText(cell)))
                .join(" | "),
            ),
        },
    record: record.hidden ? null : recordShown(record),
    focus: describeFocus(view),
  };
}

/** The record: its heading, notes, and each field with its type and value. */
function recordShown(record) {
  const list = find(record, (node) => node.localName === "dl");
  const fields = [];
  for (const node of list?.childNodes ?? []) {
    if (node.localName === "dt") {
      fields.push(`${text(node.firstChild ?? node)} (${text(node.childNodes[1])}):`);
    } else if (node.localName === "dd") {
      fields[fields.length - 1] += ` ${node.childNodes.map(text).join(" / ")}`;
    }
  }
  return {
    back: text(find(record, hasClass("table-back"))),
    title: text(find(record, hasClass("table-record-title"))),
    notes: findAll(record, (node) => node.parentNode === record && node.localName === "p").map(
      text,
    ),
    fields,
  };
}

function describeFocus(view) {
  const active = documentStandIn.activeElement;
  if (!active || !view.container.contains(active)) {
    return null;
  }
  const tr = (() => {
    for (let node = active; node; node = node.parentNode) {
      if (node.localName === "tr") {
        return node;
      }
    }
    return null;
  })();
  const tabStops = findAll(
    view.container,
    (node) => node.attributes.get("tabindex") === "0",
  ).length;
  return {
    on: active.localName,
    row: tr?.dataset.index ?? null,
    text: text(active).slice(0, 40),
    tabStops,
  };
}

function takeRequests() {
  return requests.splice(0);
}

async function settle() {
  for (let i = 0; i < 20; i++) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

// ── The session ────────────────────────────────────────────────

const transcript = {};
function step(name, value) {
  transcript[name] = value;
}

let model;
let mountTable;

function mount(file, query = "") {
  entries.splice(0);
  position = -1;
  void sdk.navigation.open({ path: file, query });
  const container = new Element("div");
  documentStandIn.body.append(container);
  const handle = mountTable(
    container,
    { path: file },
    {
      sdk,
      window: pageWindow,
      history,
      document: documentStandIn,
    },
  );
  return { container, handle, scroller: find(container, hasClass("table-scroll")) };
}

function headerButton(view, name, className = "table-sort") {
  return find(view.container, (node) => node.classes.has(className) && node.dataset.field === name);
}

function rowsOf(view) {
  const body = find(view.container, (node) => node.localName === "tbody");
  return body.childNodes.filter((tr) => !tr.classes.has("table-spacer"));
}

async function wholeTable() {
  const view = mount("people.csv");
  await ready(view);
  step("a small table, read and drawn whole", { requests: takeRequests(), ...shown(view) });

  click(
    find(headerButton(view, "score"), (node) => node.localName === "span") ??
      headerButton(view, "score"),
  );
  await settle();
  step("its score header, pressed: ascending", { requests: takeRequests(), ...shown(view) });
  click(headerButton(view, "score"));
  await settle();
  step("pressed again: descending", { requests: takeRequests(), ...shown(view) });
  click(headerButton(view, "score"));
  await settle();
  const fileOrder = shown(view);
  step("and again: the file's order, which asks again", {
    requests: takeRequests(),
    address: fileOrder.address,
    header: fileOrder.table.header,
  });

  const trueValue = find(
    view.container,
    (node) => node.classes.has("table-value-filter") && node.textContent === "true",
  );
  click(trueValue);
  await settle();
  step("a boolean value, pressed: a filter", { requests: takeRequests(), ...shown(view) });
  click(find(view.container, hasClass("table-chip-remove")));
  await settle();
  step("its chip's ×: the filter gone", {
    requests: takeRequests(),
    address: shown(view).address,
    status: shown(view).status,
    chips: shown(view).chips,
  });

  const search = find(view.container, hasClass("table-search"));
  search.value = "COMMA";
  dispatch(search, "input");
  tick(100);
  await settle();
  const early = takeRequests();
  tick(200);
  await settle();
  step("typed in Search: asked once the typing pauses, the entry replaced", {
    "requests before the pause": early,
    requests: takeRequests(),
    entries: entries.length,
    ...shown(view),
  });
  search.value = "";
  dispatch(search, "keydown", { key: "Enter" });
  await settle();
  takeRequests();

  // The keyboard: one Tab stop, rows by j and k, cells by the arrows, Enter opens.
  const first = rowsOf(view)[0];
  first.focus();
  key(first, "j");
  key(documentStandIn.activeElement, "j");
  key(documentStandIn.activeElement, "k");
  const moved = describeFocus(view);
  key(documentStandIn.activeElement, "ArrowRight");
  const onCell = describeFocus(view);
  key(documentStandIn.activeElement, "ArrowLeft");
  key(documentStandIn.activeElement, "ArrowLeft");
  step("the keyboard: j, j, k, then Right to a cell and Left back to the row", {
    "after j, j, k": moved,
    "after Right": onCell,
    "after Left, Left": describeFocus(view),
  });
  const before = entries.length;
  key(documentStandIn.activeElement, "Enter");
  await settle();
  step("Enter on the row: its record, an entry Back returns from", {
    requests: takeRequests(),
    "entries added": entries.length - before,
    ...shown(view),
  });
  click(find(view.container, hasClass("table-back")));
  await settle();
  step("Back to the table: the grid, the keyboard on the row it opened", {
    requests: takeRequests(),
    ...shown(view, { rows: 0 }),
  });

  // The header menu: a filter typed into its form, and a column hidden.
  click(headerButton(view, "age", "table-head-menu"));
  const menu = find(view.container, hasClass("table-menu"));
  const items = findAll(menu, hasClass("menu-item")).map(text);
  const form = find(menu, hasClass("table-filter-form"));
  const ops = find(form, hasClass("table-filter-op"));
  ops.value = "contains";
  find(form, hasClass("table-filter-value")).value = "9";
  dispatch(form, "submit");
  await settle();
  step("the age header's menu, and a filter from its form", {
    "menu items": items,
    operators: ops.options.map((option) => option.attributes.get("value")),
    requests: takeRequests(),
    ...shown(view),
  });
  click(find(view.container, hasClass("table-chip-remove")));
  await settle();
  takeRequests();
  click(headerButton(view, "joined", "table-head-menu"));
  click(
    find(
      find(view.container, hasClass("table-menu")),
      (node) => node.classes.has("menu-item") && node.textContent === "Hide column",
    ),
  );
  await settle();
  step("Hide column: the reader's columns, in the address", {
    requests: takeRequests(),
    ...shown(view, { rows: 2 }),
  });
  click(find(view.container, hasClass("table-columns-button")));
  const columns = find(view.container, hasClass("table-menu"));
  const boxes = findAll(columns, (node) => node.localName === "input");
  const listed = boxes.map((box) => `${box.dataset.field}${box.checked ? " ✓" : ""}`);
  click(find(columns, hasClass("table-columns-reset")));
  await settle();
  step("Columns: each field, checked when shown; Default columns", {
    listed,
    requests: takeRequests(),
    address: shown(view).address,
    header: shown(view).table.header,
  });

  // Back walks the entries the steps pushed, and the view follows the address.
  history.back();
  await settle();
  step("Back: the address before, shown", {
    requests: takeRequests(),
    address: shown(view).address,
    header: shown(view).table.header,
  });

  const listeners = windowListeners.get("popstate").length;
  view.handle.dispose();
  view.handle.dispose();
  step("disposed: the window's listeners released", {
    "popstate listeners before": listeners,
    after: windowListeners.get("popstate").length,
    beforeprint: windowListeners.get("beforeprint").length,
  });
  view.container.remove();
}

async function ready(view) {
  await view.handle.ready;
  await settle();
  return view;
}

async function refusals() {
  const bad = mount("people.csv", "f.score=gt:high");
  await ready(bad);
  step("an address whose filter the route refuses", { requests: takeRequests(), ...shown(bad) });
  bad.handle.dispose();
  bad.container.remove();

  const none = mount("people.csv", "f.name=eq:Zed");
  await ready(none);
  step("a filter no row matches", { requests: takeRequests(), ...shown(none) });
  none.handle.dispose();
  none.container.remove();

  const opened = mount("people.csv", "record=%404");
  await ready(opened);
  step("an address that names a record: the record, then the rows behind it", {
    requests: takeRequests(),
    ...shown(opened),
  });
  key(documentStandIn.activeElement, "Escape");
  await settle();
  const closed = shown(opened, { rows: 0 });
  step("Escape in the record: the table, the address without the record, replaced", {
    requests: takeRequests(),
    address: closed.address,
    entries: entries.length,
    record: closed.record,
    drawn: closed.table.drawn,
  });
  opened.handle.dispose();
  opened.container.remove();

  // A view replaced while its answers are on their way draws nothing from them.
  hold = [];
  const late = mount("people.csv");
  await settle();
  const waiting = hold.splice(0);
  late.handle.dispose();
  hold = null;
  for (const release of waiting) {
    release();
  }
  await settle();
  step("disposed before its answers arrived: nothing drawn", {
    requests: takeRequests(),
    rows: rowsOf(late).length,
    status: shown(late).status,
  });
  late.container.remove();
}

async function windowedTable() {
  const view = mount("long.csv");
  view.scroller.clientHeight = 363;
  view.scroller.clientWidth = 0;
  await ready(view);
  step("a table past the whole-table bound: a grid that draws a window", {
    requests: takeRequests(),
    ...shown(view, { rows: 2 }),
  });
  view.scroller.scrollTop = 150 * 33;
  dispatch(view.scroller, "scroll");
  tick(16);
  await settle();
  tick(16);
  step("scrolled to row 150: the window there, and the next page read ahead", {
    requests: takeRequests(),
    ...shown(view, { rows: 1 }),
  });

  const row = rowsOf(view)[0];
  row.focus();
  key(row, "End");
  await settle();
  const atEnd = shown(view, { rows: 1 });
  step("End: the last row held, scrolled into the window, focused", {
    scrollTop: view.scroller.scrollTop,
    first: atEnd.table.first,
    drawn: atEnd.table.drawn,
    focus: atEnd.focus,
  });
  key(documentStandIn.activeElement, "Home");
  key(documentStandIn.activeElement, "ArrowDown", { shiftKey: true });
  key(documentStandIn.activeElement, "ArrowDown", { shiftKey: true });
  const selected = findAll(
    view.container,
    (node) => node.attributes.get("aria-selected") === "true",
  ).length;
  let copied = null;
  const copy = dispatch(view.container.firstChild, "copy", {
    clipboardData: {
      setData: (type, value) => {
        copied = { type, value };
      },
    },
  });
  step("Home, then Shift-Down twice: three rows selected, which copy as tab-separated values", {
    selected,
    "copy handled": copy.prevented,
    copied,
  });
  const all = key(documentStandIn.activeElement, "a", { ctrlKey: true });
  step("Control-A in a windowed grid selects every row held", {
    handled: all.prevented,
    drawnSelected: findAll(
      view.container,
      (node) => node.attributes.get("aria-selected") === "true",
    ).length,
  });

  emit("beforeprint");
  const printing = rowsOf(view).length;
  emit("afterprint");
  step("print draws every row held, and the window again after", {
    "rows while printing": printing,
    "rows after": rowsOf(view).length,
  });

  click(headerButton(view, "n"));
  await settle();
  click(headerButton(view, "n"));
  await settle();
  step("sorted descending: the grid's first rows, its sort said in the header", {
    requests: takeRequests(),
    ...shown(view, { rows: 2 }),
  });
  view.handle.dispose();
  view.container.remove();
}

function modelInvariants() {
  const state = model.parseState(
    "sort=score&order=desc&f.active=eq%3Atrue&q=x&plain=1&record=%404",
  );
  const roundTrip = model.stateQuery(state);
  const reference = model.presentCell(
    { ref: { table: "users", key: "k.WzFd", label: "Ada" } },
    undefined,
  );
  const stored = model.presentCell(
    { value: "x", stored: "text" },
    { name: "n", type: "integer", numeric: true },
  );
  const fit = model.fitColumns({
    columns: ["a", "b", "c"],
    widths: { a: 10, b: 10, c: 10 },
    chPx: 8,
    fixedPx: 0,
    padPx: 20,
    available: 210,
    chosen: false,
  });
  const chosen = model.fitColumns({
    columns: ["a", "b", "c"],
    widths: { a: 10, b: 10, c: 10 },
    chPx: 8,
    fixedPx: 0,
    padPx: 20,
    available: 210,
    chosen: true,
  });
  assert.equal(model.stateQuery(model.parseState(roundTrip)), roundTrip);
  assert.deepEqual(fit.hidden, ["c"]);
  assert.equal(chosen.pinned, true);
  step("the model: an address round trip, cells a delimited file cannot hold, and column fit", {
    "address in": "sort=score&order=desc&f.active=eq%3Atrue&q=x&plain=1&record=%404",
    "address out": roundTrip,
    reference: { kind: reference.kind, text: reference.text, ref: reference.ref },
    "stored type": { text: stored.text, stored: stored.stored, tip: stored.tip },
    "default columns in 210 px": fit,
    "chosen columns in 210 px": chosen,
    "window at 1,000 px of 31 px rows": model.windowRange({
      scrollTop: 1000,
      viewport: 310,
      rowHeight: 31,
      overscan: 12,
      total: 600,
    }),
  });
}

async function main() {
  model = await import(pathToFileURL(path.join(plugin, "table-model.js")).href);
  ({ mountTable } = await import(pathToFileURL(path.join(plugin, "table-view.js")).href));
  modelInvariants();
  await wholeTable();
  await refusals();
  await windowedTable();
  step("requests asked of the server", { unrecorded });
  assert.deepEqual(unrecorded, [], "every request the page made is recorded");
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
