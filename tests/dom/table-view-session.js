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
// recorded in tests/fixtures/table-view-responses.json,
// tests/fixtures/table-view-long-responses.json,
// tests/fixtures/table-view-bounds-responses.json, and
// tests/fixtures/table-view-records-responses.json by tests/test_table_view_session.py,
// which fails when they drift; a request the recordings do not hold fails the session. A
// generation, which names a file's identity and time, is recorded as `G`. The bounds
// recording's answers are the server's with a bound lowered for one small file, as that
// recorder says.
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
for (const name of [
  "table-view-responses.json",
  "table-view-long-responses.json",
  "table-view-bounds-responses.json",
  "table-view-records-responses.json",
]) {
  Object.assign(
    answers,
    JSON.parse(fs.readFileSync(path.join(repoRoot, "tests/fixtures", name), "utf8")).answers,
  );
}

// The live table's answers at each version of its file (tests/test_table_view_session.py
// `LIVE`), and the version on disk now; a step that changes the file moves it.
const liveVersions = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/table-view-live-responses.json"), "utf8"),
).versions;
let liveVersion = "G1";
// The windowed live table's answers at each version (`LIVE_WINDOW`), and the one on disk.
const windowVersions = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "tests/fixtures/table-view-live-window-responses.json"),
    "utf8",
  ),
).versions;
let windowVersion = "W1";
/** How long each read of the live file takes; a step makes it slow. */
let liveReadMs = 0;

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

// The document's listeners by type, bubbling, and those it captures, which hear an event
// before its target does (a menu's outside press, docs/design-system.md, "Every Menu Closes
// Alike").
const documentListeners = new Map();
const documentCaptures = new Map();
/** @param {boolean | {capture?: boolean} | undefined} options */
const capturing = (options) => (typeof options === "boolean" ? options : Boolean(options?.capture));
const documentStandIn = {
  createElement: (tag) => new Element(tag),
  body: new Element("body"),
  activeElement: null,
  // A step hides and shows the page as a browser's visibilitychange does.
  visibilityState: "visible",
  addEventListener(type, listener, options) {
    const listeners = capturing(options) ? documentCaptures : documentListeners;
    listeners.set(type, [...(listeners.get(type) ?? []), listener]);
  },
  removeEventListener(type, listener, options) {
    const listeners = capturing(options) ? documentCaptures : documentListeners;
    listeners.set(
      type,
      (listeners.get(type) ?? []).filter((item) => item !== listener),
    );
  },
};
/** The page becomes *state*, "hidden" or "visible". */
function visibility(state) {
  documentStandIn.visibilityState = state;
  for (const listener of documentListeners.get("visibilitychange") ?? []) {
    listener({ type: "visibilitychange" });
  }
}
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

/**
 * Dispatch *type* at *target*: the document's capturing listeners, then the target's and
 * every ancestor's, then the document's own, unless one stops it.
 */
function dispatch(target, type, init = {}) {
  let prevented = false;
  let stopped = false;
  const event = {
    type,
    target,
    button: 0,
    shiftKey: false,
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    ...init,
    get defaultPrevented() {
      return prevented;
    },
    preventDefault() {
      prevented = true;
    },
    stopPropagation() {
      stopped = true;
    },
  };
  for (const listener of [...(documentCaptures.get(type) ?? [])]) {
    listener(event);
  }
  for (let node = target; node && !stopped; node = node.parentNode) {
    for (const listener of node.handlers?.get(type) ?? []) {
      listener(event);
    }
  }
  for (const listener of stopped ? [] : [...(documentListeners.get(type) ?? [])]) {
    listener(event);
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
  // The session's clock, which a live read's cost advances.
  performance: { now: () => clock },
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

/**
 * The address's history: the shell's navigation as a plugin sees it, and the browser's
 * address. `writes` counts the view's own history writes (its place). A push the browser
 * drops, as Chrome drops every history call past 200 in 10 seconds, is `dropPushes`: the
 * shell's target moves (`shellTarget`), and the browser's entries and address do not.
 */
const entries = [];
let position = -1;
let writes = 0;
let dropPushes = 0;
let shellTarget = null;
const history = {
  state: null,
  back() {
    position -= 1;
    shellTarget = null;
    history.state = entries[position].state;
    emit("popstate");
  },
  replaceState(state) {
    writes += 1;
    history.state = state;
    entries[position].state = state;
  },
};
const location = {
  get search() {
    const query = entries[position]?.target.query ?? "";
    return query ? `?${query}` : "";
  },
};

const requests = [];
const unrecorded = [];
let hold = null;
const tooltips = [];

/** A request as the recordings key it: its parameters by name, a list's values in order. */
function keyOf(route, params) {
  const sorted = Object.entries(params).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  const query = new URLSearchParams();
  for (const [name, value] of sorted) {
    for (const item of Array.isArray(value) ? value : [value]) {
      query.append(name, String(item));
    }
  }
  return `${route}?${query}`;
}

const sdk = {
  // The shell's menu closing, production filter-controls.js in the SDK's sandbox.
  menus: require("./sdk-sandbox.js").createSdkSandbox().metabrowser.menus,
  escapeHtml: (value) => String(value).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`),
  tooltip: {
    show: (html, anchor) => tooltips.push({ show: html, anchor: anchor.className }),
    hide: (within) => tooltips.push({ hide: within?.className ?? null }),
  },
  navigation: {
    current: () => shellTarget ?? (position >= 0 ? entries[position].target : null),
    href: (target) => `/view/${target.path}${target.query ? `?${target.query}` : ""}`,
    async open(target, how = {}) {
      const entry = { target: { path: target.path, query: target.query ?? "" }, state: null };
      shellTarget = null;
      if (!how.replace && dropPushes > 0) {
        dropPushes -= 1;
        shellTarget = entry.target;
        return;
      }
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
    if (params.path === "live.csv") {
      // What a read of the live file costs the server, in the session's clock.
      clock += liveReadMs;
    }
    const answer =
      params.path === "live.csv"
        ? liveVersions[liveVersion][key]
        : params.path === "live-window.csv"
          ? windowVersions[windowVersion].answers[key]
          : answers[key];
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
let LIVE_COALESCE;
let placeSaveMs;

function mount(file, query = "", context = {}) {
  entries.splice(0);
  position = -1;
  void sdk.navigation.open({ path: file, query });
  const container = new Element("div");
  documentStandIn.body.append(container);
  const handle = mountTable(
    container,
    { path: file, ...context },
    {
      sdk,
      window: pageWindow,
      history,
      location,
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

  // The header is in the grid's one Tab stop: Up from the first row, across its controls
  // with Right, and Down to the first row's cell in the column left.
  key(documentStandIn.activeElement, "k");
  key(documentStandIn.activeElement, "k");
  const onHeader = describeFocus(view);
  key(documentStandIn.activeElement, "ArrowRight");
  const onMenu = describeFocus(view);
  key(documentStandIn.activeElement, "ArrowRight");
  const onNext = describeFocus(view);
  key(documentStandIn.activeElement, "ArrowDown");
  step("the header: k from the first row, Right across its controls, Down to the row", {
    "after k, k": onHeader,
    "after Right": onMenu,
    "after Right again": onNext,
    "after Down": describeFocus(view),
    "header controls out of the Tab order": findAll(
      view.container,
      (node) => node.localName === "button" && node.attributes.get("tabindex") === "-1",
    ).length,
  });
  key(documentStandIn.activeElement, "ArrowLeft");
  key(documentStandIn.activeElement, "ArrowLeft");

  // A header's menu is a dialog: the focus arriving outside it closes it, and Escape
  // returns the focus to its button.
  click(headerButton(view, "name", "table-head-menu"));
  const dialog = find(view.container, hasClass("table-menu"));
  const searchBox = find(view.container, hasClass("table-search"));
  searchBox.focus();
  dispatch(searchBox, "focusin");
  const closedOnLeave = find(view.container, hasClass("table-menu")) === null;
  click(headerButton(view, "name", "table-head-menu"));
  key(documentStandIn.activeElement, "Escape");
  step("a header's menu: closed when the focus leaves it, and by Escape, to its button", {
    role: dialog.attributes.get("role"),
    label: dialog.attributes.get("aria-label"),
    "closed when the focus left": closedOnLeave,
    "open after Escape": find(view.container, hasClass("table-menu")) !== null,
    focus: describeFocus(view),
  });

  // The header menu: a filter typed into its form, and a column hidden.
  click(headerButton(view, "age", "table-head-menu"));
  const menu = find(view.container, hasClass("table-menu"));
  const items = findAll(menu, hasClass("menu-item")).map(text);
  const menuRole = menu.attributes.get("role");
  const form = find(menu, hasClass("table-filter-form"));
  const ops = find(form, hasClass("table-filter-op"));
  ops.value = "contains";
  find(form, hasClass("table-filter-value")).value = "9";
  dispatch(form, "submit");
  await settle();
  step("the age header's menu, and a filter from its form", {
    role: menuRole,
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

  let watchState;
  sdk.watchFile = (_file, options) => {
    watchState = options.onState;
    return () => {};
  };
  const none = mount("people.csv", "f.name=eq:Zed");
  await ready(none);
  step("a filter no row matches", { requests: takeRequests(), ...shown(none) });
  watchState("live", null);
  const empty = find(none.container, hasClass("table-empty"));
  assert.ok(empty, "watch confirmation preserves the empty state");
  assert.match(text(empty), /^No rows match\./);
  const clear = find(empty, hasClass("table-clear"));
  assert.ok(clear);
  hold = [];
  click(clear);
  await settle();
  assert.equal(hold.length, 1, "the unfiltered query is pending");
  assert.deepEqual(takeRequests(), ["rows?limit=200&path=people.csv"]);
  watchState("live", null);
  assert.equal(shown(none).empty, null, "the old empty answer does not describe the new query");
  const [release] = hold;
  hold = null;
  release();
  await settle();
  assert.equal(rowsOf(none).length, 5);
  none.handle.dispose();
  none.container.remove();
  delete sdk.watchFile;

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
  view.scroller.scrollTop = 150 * 32;
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
  const before = describeFocus(view);
  const chords = ["j", "a", "ArrowDown", "End", "Enter", "Escape"].flatMap((name) =>
    [{ metaKey: true }, { ctrlKey: true }, { altKey: true }].map(
      (held) => key(documentStandIn.activeElement, name, held).prevented,
    ),
  );
  step("a key held with Command, Control, or Option is the browser's: none moves or is taken", {
    taken: chords.filter(Boolean).length,
    "focus kept": JSON.stringify(describeFocus(view)) === JSON.stringify(before),
  });
  key(documentStandIn.activeElement, "Home");
  const all = key(documentStandIn.activeElement, "End", { shiftKey: true });
  await settle();
  step("Home, then Shift-End: every row held selected, the window at the last", {
    handled: all.prevented,
    drawnSelected: findAll(
      view.container,
      (node) => node.attributes.get("aria-selected") === "true",
    ).length,
    focus: describeFocus(view),
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

// ── The live table ─────────────────────────────────────────────
//
// metabrowser.watchFile is the page's: here, a stand-in that records the watch and lets a
// step say the file changed, as a `file.changed` on the page's event stream would.

const fileWatches = [];
function watchFile(file, options) {
  const watch = { file, options, disposed: false };
  fileWatches.push(watch);
  requests.push(`watch ${file} at ${options.generation}`);
  void Promise.resolve().then(() => options.onState?.("live", null));
  return () => {
    watch.disposed = true;
    requests.push(`unwatch ${file}`);
  };
}

/** The file moves to *version*, and its watch says so *times* times. */
function fileChanges(version, times = 1) {
  liveVersion = version;
  for (let n = 0; n < times; n++) {
    for (const watch of fileWatches.filter((item) => !item.disposed)) {
      watch.options.onChange({ path: watch.file, generation: version });
    }
  }
}

function pill(view) {
  const found = find(view.container, hasClass("table-live-pill"));
  return found.hidden ? null : text(found);
}

function flashing(view) {
  return rowsOf(view)
    .filter((tr) => tr.classes.has("table-row-flash"))
    .map((tr) => text(tr.firstChild));
}

function liveShown(view, extra = {}) {
  const page = shown(view, { rows: 10 });
  const offer = find(view.container, hasClass("table-offer"));
  return {
    requests: takeRequests(),
    pill: pill(view),
    offer: offer.hidden ? null : text(offer),
    flashing: flashing(view),
    announced: text(find(view.container, (node) => node.attributes.get("aria-live") === "polite")),
    status: page.status,
    notes: page.notes,
    address: page.address,
    rows: page.table === "hidden" ? "hidden" : page.table.rows,
    focus: page.focus,
    ...extra,
  };
}

async function liveTable() {
  sdk.watchFile = watchFile;
  liveVersion = "G1";
  const view = mount("live.csv");
  await ready(view);
  step("live: a table read, its file watched with the generation it read", liveShown(view));

  // A filter half typed in the qty header's menu, not sent, the focus in its field.
  click(headerButton(view, "qty", "table-head-menu"));
  const typed = find(find(view.container, hasClass("table-menu")), hasClass("table-filter-value"));
  typed.focus();
  typed.value = "4";
  fileChanges("G2", 3);
  tick(100);
  await settle();
  const early = takeRequests();
  tick(LIVE_COALESCE);
  await settle();
  const menu = find(view.container, hasClass("table-menu"));
  step("live: three changes in a burst, one read again: a cell changed, a row arrived below", {
    "requests before the window ends": early,
    ...liveShown(view),
    "menu open, its unsent filter kept": menu
      ? find(menu, hasClass("table-filter-value")).value
      : null,
  });
  key(find(menu, hasClass("table-filter-value")), "Escape");
  tick(1000);
  const first = rowsOf(view)[0];
  first.focus();
  key(first, "j");
  key(documentStandIn.activeElement, "Enter");
  await settle();
  takeRequests();
  fileChanges("G3");
  tick(LIVE_COALESCE);
  await settle();
  const record = shown(view).record;
  step("live: the open record, named by position, read again: another row is there now", {
    requests: takeRequests(),
    record,
    notices: findAll(find(view.container, hasClass("table-record")), hasClass("table-notice")).map(
      text,
    ),
  });
  click(find(view.container, hasClass("table-back")));
  await settle();
  takeRequests();
  step("live: back to the table, which was read again behind the record", liveShown(view));

  click(headerButton(view, "qty"));
  await settle();
  click(headerButton(view, "qty"));
  await settle();
  takeRequests();
  view.scroller.scrollTop = 2 * 33;
  const top = rowsOf(view)[0];
  top.focus();
  for (let n = 0; n < 3; n++) {
    key(documentStandIn.activeElement, "j");
  }
  click(find(view.container, hasClass("table-live-pill")));
  fileChanges("G4", 2);
  tick(LIVE_COALESCE);
  await settle();
  step(
    "live: sorted, scrolled two rows down, a row focused, and paused: changes counted, not read",
    {
      scrollTop: view.scroller.scrollTop,
      ...liveShown(view),
    },
  );
  click(find(view.container, hasClass("table-live-pill")));
  tick(LIVE_COALESCE);
  await settle();
  step(
    "live: resumed: the row that sorts above the reader's place offered, the one below drawn, the focus kept",
    { scrollTop: view.scroller.scrollTop, ...liveShown(view) },
  );
  click(find(view.container, hasClass("table-offer")));
  await settle();
  step("live: the offer taken: the new row drawn, the view at it, and the keyboard on it", {
    scrollTop: view.scroller.scrollTop,
    ...liveShown(view),
  });

  // Every write to the live region, so a step can say what was announced and how often.
  const announcements = [];
  const region = find(view.container, (node) => node.attributes.get("aria-live") === "polite");
  let owner = Object.getPrototypeOf(region);
  while (owner && !Object.getOwnPropertyDescriptor(owner, "textContent")) {
    owner = Object.getPrototypeOf(owner);
  }
  const regionText = Object.getOwnPropertyDescriptor(owner, "textContent");
  Object.defineProperty(region, "textContent", {
    get: () => regionText.get.call(region),
    set: (value) => {
      announcements.push(value);
      regionText.set.call(region, value);
    },
  });

  // Two rows selected, and a row element marked, so a step can tell it was not drawn again.
  key(documentStandIn.activeElement, "ArrowDown", { shiftKey: true });
  rowsOf(view)[0].kept = true;
  fileChanges("G5");
  tick(LIVE_COALESCE);
  await settle();
  step("live: the file touched, its rows as they were: nothing drawn again, the selection kept", {
    requests: takeRequests(),
    flashing: flashing(view),
    focus: shown(view).focus,
    selected: rowsOf(view)
      .filter((tr) => tr.attributes.get("aria-selected") === "true")
      .map((tr) => text(tr.firstChild)),
    "first row element kept": Boolean(rowsOf(view)[0].kept),
  });

  liveReadMs = 400;
  fileChanges("G6");
  tick(LIVE_COALESCE);
  await settle();
  liveReadMs = 0;
  step("live: a cell changed under the selection, read slowly: the selection stays on its rows", {
    requests: takeRequests(),
    flashing: flashing(view),
    focus: shown(view).focus,
    selected: rowsOf(view)
      .filter((tr) => tr.attributes.get("aria-selected") === "true")
      .map((tr) => text(tr.firstChild)),
  });

  fileChanges("G7");
  tick(LIVE_COALESCE);
  await settle();
  const early7 = takeRequests();
  tick(2 * 400 - LIVE_COALESCE);
  await settle();
  step("live: after a read that took 400 ms, the next waits twice that, not the window", {
    "requests once the window ends": early7,
    "requests at twice the last read": takeRequests(),
  });

  visibility("hidden");
  fileChanges("G8");
  tick(10 * LIVE_COALESCE);
  await settle();
  const whileHidden = takeRequests();
  visibility("visible");
  tick(LIVE_COALESCE);
  await settle();
  step("live: a change while the page is hidden: nothing read until it is shown, then once", {
    "requests while hidden": whileHidden,
    requests: takeRequests(),
    flashing: flashing(view),
  });

  for (const watch of fileWatches.filter((item) => !item.disposed)) {
    watch.options.onState("refused", "too_many_watches");
  }
  const refusedNotes = shown(view).notes;
  for (const watch of fileWatches.filter((item) => !item.disposed)) {
    watch.options.onState("live", null);
  }
  step("live: a watch refused says the table is not following its file, until it is live again", {
    "notes while refused": refusedNotes,
    "notes once live": shown(view).notes,
    pill: pill(view),
  });

  // The focused row's record, open with the keyboard on its own Live control.
  key(documentStandIn.activeElement, "Enter");
  await settle();
  takeRequests();
  const recordPill = find(
    find(view.container, hasClass("table-record")),
    hasClass("table-live-pill"),
  );
  recordPill.focus();
  const recordBody = find(view.container, hasClass("table-record-fields"));
  fileChanges("G9");
  tick(LIVE_COALESCE);
  await settle();
  step("live: a record read again unchanged: not drawn again, the keyboard on its Live control", {
    requests: takeRequests(),
    "record pane drawn again": find(view.container, hasClass("table-record-fields")) !== recordBody,
    focus: documentStandIn.activeElement === recordPill ? "the record's Live control" : "elsewhere",
    "record pill": recordPill.hidden ? null : text(recordPill),
  });
  click(recordPill);
  fileChanges("G10");
  tick(LIVE_COALESCE);
  await settle();
  step("live: the record's Live control pressed: paused there, a change held back", {
    requests: takeRequests(),
    "record pill": text(recordPill),
  });
  click(recordPill);
  tick(LIVE_COALESCE);
  await settle();
  click(find(view.container, hasClass("table-back")));
  await settle();
  takeRequests();

  fileChanges("G11");
  tick(LIVE_COALESCE);
  await settle();
  step("live: the sorted column removed: dropped from the address, with a notice", liveShown(view));

  announcements.splice(0);
  fileChanges("G12");
  tick(LIVE_COALESCE);
  await settle();
  fileChanges("G13");
  tick(LIVE_COALESCE);
  await settle();
  step("live: the file removed: the rows last read kept, and said to be", {
    ...liveShown(view),
    "announced, each time": [...announcements],
  });

  view.handle.dispose();
  step("live: disposed: the watch released", { requests: takeRequests() });
  view.container.remove();
  delete sdk.watchFile;
}

/** The windowed table's first row drawn, and each drawn whose value is not its position. */
function windowShown(view) {
  const drawn = rowsOf(view).map((tr) => tr.childNodes.map((cell) => text(cell)));
  return {
    first: drawn[0]?.join(" | ") ?? null,
    "rows changed": drawn.filter(([at, value]) => at !== value).map((cells) => cells.join(" | ")),
  };
}

async function liveWindowTable() {
  sdk.watchFile = watchFile;
  windowVersion = "W1";
  const view = mount("live-window.csv");
  await ready(view);
  const scrollTo = async (row) => {
    view.scroller.scrollTop = row * 33;
    dispatch(view.scroller, "scroll");
    tick(16);
    await settle();
    tick(16);
    await settle();
  };
  await scrollTo(40);
  step("live window: sixty rows read in pages of ten, scrolled to row 40", {
    requests: takeRequests().length,
    ...windowShown(view),
  });
  windowVersion = "W2";
  for (const watch of fileWatches.filter((item) => !item.disposed)) {
    watch.options.onChange({ path: watch.file, generation: "W2" });
  }
  tick(LIVE_COALESCE);
  await settle();
  step(
    "live window: rows 5 and 45 changed: read again from the start as far as the reader reached",
    {
      requests: takeRequests(),
      ...windowShown(view),
    },
  );
  await scrollTo(0);
  const scrolledUp = { requests: takeRequests(), ...windowShown(view) };
  tick(LIVE_COALESCE);
  await settle();
  step("live window: back at the top: row 5 as read with the rest, nothing stale to read again", {
    "requests as the window arrives": scrolledUp.requests,
    "rows changed as it arrives": scrolledUp["rows changed"],
    requests: takeRequests(),
    ...windowShown(view),
  });
  view.handle.dispose();
  takeRequests();
  view.container.remove();
  delete sdk.watchFile;
}

function liveInvariants() {
  const row = (key, value) => ({ key, cells: { v: value } });
  const before = [row("a", 1), row("b", 2), row("c", 3), row("d", 4)];
  // A row before the reader's place arrives offered; one after it, drawn; a changed one flashes.
  const merged = model.liveMerge({
    before,
    after: [row("n", 0), row("a", 1), row("b", 2), row("c", 30), row("m", 9), row("d", 4)],
    anchor: 2,
  });
  assert.deepEqual(
    merged.rows.map((item) => item.key),
    ["a", "b", "c", "m", "d"],
  );
  assert.deepEqual([merged.changed, merged.arrived, merged.offered], [["c"], ["m"], 1]);
  // At the top nothing is above the reader: every new row is drawn.
  assert.equal(
    model.liveMerge({ before, after: [row("n", 0), ...before], anchor: null }).offered,
    0,
  );
  // The anchor row gone: the next row still there places "above".
  const gone = model.liveMerge({
    before,
    after: [row("n", 0), row("a", 1), row("d", 4)],
    anchor: 1,
  });
  assert.deepEqual([gone.offered, gone.removed], [1, 2]);
  // Accepted, the offered rows are drawn.
  assert.equal(
    model.liveMerge({ before, after: [row("n", 0), ...before], anchor: 2, accept: true })
      .arrived[0],
    "n",
  );
  assert.equal(model.livePillText(false, 4), "Live");
  assert.equal(model.livePillText(true, 0), "Paused");
  assert.equal(model.livePillText(true, 1), "Paused · 1 change");
  // A busy source's refusal keeps the rows and says why, as every other refusal does.
  assert.match(model.liveFailure("busy"), /file is busy/);
  assert.match(model.liveFailure(null), /rows last read/);
}

async function placeAndHistory() {
  // The place is written once a pause after the keys stop, never a key press each, so a
  // held key cannot use up the browser's history writes and make it drop the record's
  // push (Chrome ignores history calls past 200 in 10 seconds, WebKit throws past 100 in
  // 30); tests/test_table_view_chrome.py presses on past Chrome's bound.
  const view = mount("long.csv");
  view.scroller.clientHeight = 363;
  await ready(view);
  takeRequests();
  rowsOf(view)[0].focus();
  writes = 0;
  for (let press = 0; press < 150; press++) {
    key(documentStandIn.activeElement, "j");
  }
  await settle();
  const during = writes;
  tick(placeSaveMs - 1);
  const before = writes;
  tick(1);
  step("150 presses of j: no history write while the keys come, one a pause after", {
    "writes while pressing": during,
    "writes just before the pause ends": before,
    "writes after it": writes,
    requests: takeRequests(),
    focus: describeFocus(view),
  });
  const added = entries.length;
  key(documentStandIn.activeElement, "Enter");
  await settle();
  const opened = shown(view, { rows: 0 });
  step("Enter after them: the record's entry pushed, its address the record's", {
    "entries added": entries.length - added,
    "browser's address": location.search,
    title: opened.record?.title,
    requests: takeRequests(),
  });
  const at = position;
  click(find(view.container, hasClass("table-back")));
  await settle();
  const back = shown(view, { rows: 0 });
  step("its Back link: Back, to the grid at the place the keys left", {
    "went back": position === at - 1,
    "browser's address": location.search,
    record: back.record,
    scrollTop: view.scroller.scrollTop,
    focus: back.focus,
  });

  // A push the browser dropped anyway: the record is drawn, and its Back link replaces the
  // table's address rather than going Back, which would leave the table.
  dropPushes = 1;
  key(documentStandIn.activeElement, "Enter");
  await settle();
  const dropped = shown(view, { rows: 0 });
  step("a push the browser dropped: the record drawn, the browser's address unchanged", {
    "shell's address": sdk.navigation.current()?.query,
    "browser's address": location.search,
    title: dropped.record?.title,
    requests: takeRequests(),
  });
  const before2 = { position, entries: entries.length };
  click(find(view.container, hasClass("table-back")));
  await settle();
  const replaced = shown(view, { rows: 0 });
  step("its Back link: the table's address replaces the entry, and Back is not taken", {
    "went back": position !== before2.position,
    "entries added": entries.length - before2.entries,
    "browser's address": location.search,
    record: replaced.record,
    focus: replaced.focus,
  });

  // A new answer to the same question keeps the reader's place by key.
  view.scroller.scrollTop = 100 * 32 + 5;
  dispatch(view.scroller, "scroll");
  tick(16);
  key(documentStandIn.activeElement, "ArrowDown", { shiftKey: true });
  const kept = {
    scrollTop: view.scroller.scrollTop,
    focus: describeFocus(view),
    selected: findAll(view.container, (node) => node.attributes.get("aria-selected") === "true")
      .length,
  };
  await view.handle.refresh();
  await settle();
  step("refresh: the question asked again, its answer drawn with the place kept by key", {
    requests: takeRequests(),
    before: kept,
    after: {
      scrollTop: view.scroller.scrollTop,
      focus: describeFocus(view),
      selected: findAll(view.container, (node) => node.attributes.get("aria-selected") === "true")
        .length,
    },
  });
  view.handle.dispose();
  view.container.remove();
}

function modelInvariants() {
  const state = model.parseState(
    "sort=score&order=desc&f.active=eq%3Atrue&q=x&cols=name&cols=a%2C+b&plain=1&record=%404",
  );
  const roundTrip = model.stateQuery(state);
  assert.deepEqual(state.cols, ["name", "a, b"]);
  assert.deepEqual(model.rowsParams(state, { limit: 5 }).cols, ["name", "a, b"]);
  // A cursor names its sort, so a new sort or order is a new question, read from its start.
  const resorted = model.withSort(state, "score", "asc");
  assert.equal(model.sameRows(state, resorted), false);
  assert.equal(model.rowsParams(resorted, { limit: 5 }).after, undefined);
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
  // A question's later pages: the last one says whether it is complete and why, and a
  // page from a table that changed under the cursor ends it as `cursor_expired`.
  const firstPage = {
    rows: [{ key: "@1", cells: {} }],
    columns: ["a"],
    next_after: "c1",
    complete: true,
    truncated: false,
    reason: null,
    count: 3,
    count_complete: true,
    generation: "g1",
  };
  const joined = model.joinPage(
    { ...firstPage, rows: [...firstPage.rows] },
    {
      ...firstPage,
      rows: [{ key: "@2", cells: {} }],
      next_after: null,
      complete: false,
      reason: "budget",
      examined: 9,
    },
  );
  assert.deepEqual(
    [joined.rows.length, joined.next_after, joined.complete, joined.reason, joined.examined],
    [2, null, false, "budget", 9],
  );
  const expired = model.joinPage(
    { ...firstPage, rows: [...firstPage.rows] },
    { ...firstPage, rows: [{ key: "@2", cells: {} }], generation: "g2" },
  );
  assert.deepEqual(
    [expired.rows.length, expired.next_after, expired.complete, expired.reason],
    [1, null, false, "cursor_expired"],
  );
  // The header is part of the grid's roving focus: k from the first row onto the focused
  // column's first control, Right across controls, Down to that column's cell.
  const head = { rows: 5, cols: 3, pageRows: 4, heads: 5, headStarts: [0, 2, 4] };
  assert.deepEqual(model.keyStep({ row: 0, col: 1 }, { key: "k" }, head).focus, {
    row: -1,
    col: 2,
  });
  assert.deepEqual(
    model.keyStep({ row: 0, col: -1 }, { key: "ArrowUp", shiftKey: true }, head).action,
    "extend",
  );
  assert.deepEqual(model.keyStep({ row: -1, col: 3 }, { key: "ArrowDown" }, head).focus, {
    row: 0,
    col: 1,
  });
  assert.deepEqual(model.keyStep({ row: -1, col: 4 }, { key: "ArrowRight" }, head).focus, {
    row: -1,
    col: 4,
  });
  assert.equal(model.keyStep({ row: -1, col: 0 }, { key: "Enter" }, head).action, "none");
  assert.equal(model.keyStep({ row: 1, col: -1 }, { key: "k" }, head).focus.row, 0);
  assert.deepEqual(fit.hidden, ["c"]);
  assert.equal(chosen.pinned, true);
  step("the model: an address round trip, cells a delimited file cannot hold, and column fit", {
    "address in":
      "sort=score&order=desc&f.active=eq%3Atrue&q=x&cols=name&cols=a%2C+b&plain=1&record=%404",
    "address out": roundTrip,
    "a column whose name holds a comma": state.cols,
    reference: { kind: reference.kind, text: reference.text, ref: reference.ref },
    "stored type": { text: stored.text, stored: stored.stored, tip: stored.tip },
    "default columns in 210 px": fit,
    "chosen columns in 210 px": chosen,
    "a later page: the question's end, and a changed table's": {
      joined: { rows: joined.rows.length, complete: joined.complete, reason: joined.reason },
      expired: { rows: expired.rows.length, complete: expired.complete, reason: expired.reason },
    },
    "no rows match, said of a scan the budget stopped": [
      model.noMatchText({ ...firstPage, reason: null }),
      model.noMatchText({ ...firstPage, reason: "budget", examined: 4096 }),
    ],
    "window at 1,000 px of 31 px rows": model.windowRange({
      scrollTop: 1000,
      viewport: 310,
      rowHeight: 31,
      overscan: 12,
      total: 600,
    }),
  });
}

async function bounds() {
  // A page bounded in cells carries fewer rows than asked; its `limit` says how many, and
  // the view reads on from `next_after` until it holds the table.
  const paged = mount("paged.csv");
  await ready(paged);
  const whole = shown(paged, { rows: 8 });
  assert.equal(whole.table.drawn, 8);
  // Drawn whole: every row, no spacers, and no row count for rows not drawn.
  assert.deepEqual(whole.table.spacers, []);
  assert.equal(whole.table.rowcount, null);
  step("pages shorter than asked: read on from each cursor, the table drawn whole", {
    requests: takeRequests(),
    ...whole,
  });
  click(headerButton(paged, "n", "table-head-menu"));
  click(
    find(
      find(paged.container, hasClass("table-menu")),
      (node) => node.classes.has("menu-item") && node.textContent === "Hide column",
    ),
  );
  await settle();
  step("a column hidden: the others, one field a parameter, a comma in a name kept", {
    requests: takeRequests(),
    ...shown(paged, { rows: 1 }),
  });
  paged.handle.dispose();
  paged.container.remove();

  // A search the time budget stopped: the matches among the rows it read, in order, and
  // its cursor continues among them.
  const searched = mount("numbers.csv", "q=match");
  searched.scroller.clientHeight = 363;
  await ready(searched);
  step("a search the time budget stopped: the matches it found, said as such", {
    requests: takeRequests(),
    ...shown(searched, { rows: 2 }),
  });
  searched.scroller.scrollTop = 150 * 32;
  dispatch(searched.scroller, "scroll");
  tick(16);
  await settle();
  tick(16);
  const more = shown(searched, { rows: 0 });
  step("scrolled: the next page continues among the rows it read, and ends", {
    requests: takeRequests(),
    status: more.status,
    notes: more.notes,
    rowcount: more.table.rowcount,
  });
  searched.handle.dispose();
  searched.container.remove();

  // A sort the budget could not finish answers no rows: the view says so, not "no rows",
  // and offers the file's order back.
  const sorted = mount("numbers.csv", "sort=n");
  await ready(sorted);
  const refused = shown(sorted);
  assert.equal(refused.empty, null);
  step("a sort the time budget refused: said by its field, the file's order offered", {
    requests: takeRequests(),
    ...refused,
  });
  click(find(sorted.container, hasClass("table-unsort")));
  await settle();
  step("the file's order, chosen: the rows again", {
    requests: takeRequests(),
    ...shown(sorted, { rows: 2 }),
  });
  sorted.handle.dispose();
  sorted.container.remove();

  for (const [file, what] of [
    ["cut.csv", "a file whose rows have more cells than the table reads"],
    ["tall.csv", "a file with more rows than the table reads"],
  ]) {
    const view = mount(file);
    await ready(view);
    step(what, { requests: takeRequests(), ...shown(view, { rows: 1 }) });
    view.handle.dispose();
    view.container.remove();
  }
}

// The structured kind's Table view: a JSON list of mappings, whose record draws each nested
// value with the renderer its view hands the table (structured/index.js passes the
// structured plugin's inline tree; this stand-in writes the value it was given), and a
// JSON list one of whose items is not a mapping: the server offers the Table tab on a
// file that starts as a list of records, and this one is not.
async function recordLists() {
  const drawnTrees = [];
  let released = 0;
  const renderJson = (host, value) => {
    const tree = new Element("div");
    tree.textContent = `tree ${JSON.stringify(value)}`;
    host.append(tree);
    drawnTrees.push(value);
    return {
      dispose() {
        released += 1;
      },
    };
  };
  const view = mount("records.json", "", { renderJson });
  await ready(view);
  step("a JSON list of mappings: a table of its records", {
    requests: takeRequests(),
    ...shown(view),
  });
  const ada = rowsOf(view)[0];
  ada.focus();
  key(ada, "Enter");
  await settle();
  const opened = shown(view, { rows: 0 });
  step("a record: each nested value drawn as a tree, an absent field said", {
    requests: takeRequests(),
    record: opened.record,
    trees: drawnTrees.length,
  });
  assert.equal(drawnTrees.length, 2, "one tree for each nested value of the record");
  key(documentStandIn.activeElement, "Escape");
  await settle();
  step("Back to the table: the trees released", {
    requests: takeRequests(),
    released,
  });
  assert.equal(released, drawnTrees.length, "every tree a record drew is released with it");
  click(headerButton(view, "age"));
  await settle();
  step("a field of values of several types, sorted: numbers, then text", {
    requests: takeRequests(),
    ...shown(view),
  });
  view.handle.dispose();
  view.container.remove();

  const mixed = mount("mixed.json", "", { renderJson });
  await ready(mixed);
  const said = shown(mixed);
  step("a JSON list with an item that is not a mapping: said in place of the table", {
    requests: takeRequests(),
    toolbar: find(mixed.container, hasClass("table-toolbar")).hidden ? "hidden" : "shown",
    notes: said.notes,
    table: said.table,
    links: findAll(mixed.container, hasClass("table-reset")).length,
  });
  mixed.handle.dispose();
  mixed.container.remove();
}

async function relationshipFilter() {
  const file = "market.db/orders";
  const ref = "people:k.WzFd";
  const via = JSON.stringify([["buyer"], ["id"]]);
  const scoped = new URLSearchParams({ ref, via }).toString();
  for (const malformed of [{ ref, via: "" }, { via }]) {
    const state = model.parseState(new URLSearchParams(malformed).toString());
    assert.equal(model.rowsParams(state, { limit: 200 }).via, malformed.via);
    assert.equal(new URLSearchParams(model.stateQuery(state)).get("via"), malformed.via);
  }
  const respond = (route, params, body) => {
    answers[keyOf(route, params)] = { status: 200, body };
  };
  respond(
    "schema",
    { path: file },
    {
      table: "orders",
      fields: [
        { name: "buyer", title: "Buyer", type: "text", description: "The person who bought it." },
      ],
    },
  );
  respond(
    "card",
    { path: "market.db/people", key: "k.WzFd" },
    {
      label: "Ada Lovelace",
      cells: {},
    },
  );
  const page = { columns: ["buyer"], rows: [], count: 0, count_complete: true, complete: true };
  respond("rows", { path: file, ref, via, limit: 200 }, page);
  respond("rows", { path: file, limit: 200 }, page);

  const schema = [];
  hold = schema;
  const view = mount(file, scoped);
  await settle();
  assert.equal(find(view.container, hasClass("table-open-ref")), null);
  const first = takeRequests();
  assert.deepEqual(first, ["schema?path=market.db%2Forders"]);
  step("during schema loading", { requests: first, hasRelatedLink: false });
  hold = null;
  for (const release of schema) {
    release();
  }
  await ready(view);
  const link = find(view.container, hasClass("table-open-ref"));
  const remove = find(view.container, hasClass("table-chip-remove"));
  assert.equal(text(link), "Ada Lovelace");
  assert.equal(link.dataset.path, "market.db/people");
  const columns = find(view.container, hasClass("table-columns-button"));
  click(columns);
  const menu = find(view.container, hasClass("table-menu"));
  const choice = find(menu, (element) => element.localName === "input");
  const description = choice.attributes.get("aria-description");
  assert.equal(description, "The person who bought it.");
  click(columns);
  step("after the schema resolves", {
    requests: takeRequests(),
    label: text(link.parentNode),
    target: link.dataset.path,
    description,
  });
  click(remove);
  await settle();
  assert.equal(sdk.navigation.current().query, "");
  step("removing the chip clears the scope", { requests: takeRequests(), query: "" });
  view.handle.dispose();
  view.container.remove();
  assert.deepEqual(unrecorded, []);
}

async function main() {
  model = await import(pathToFileURL(path.join(plugin, "table-model.js")).href);
  const view = await import(pathToFileURL(path.join(plugin, "table-view.js")).href);
  ({ mountTable, LIVE_COALESCE_MS: LIVE_COALESCE } = view);
  placeSaveMs = view.PLACE_SAVE_MS;
  if (process.argv[2] === "relationships") {
    await relationshipFilter();
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
    return;
  }
  modelInvariants();
  liveInvariants();
  await wholeTable();
  await refusals();
  await windowedTable();
  await placeAndHistory();
  await bounds();
  await recordLists();
  await liveTable();
  await liveWindowTable();
  step("requests asked of the server", { unrecorded });
  assert.deepEqual(unrecorded, [], "every request the page made is recorded");
  // Every scenario runs either way; the transcript prints the live table's steps as a
  // command of their own (`live`), and the rest without an argument.
  const live = process.argv[2] === "live";
  const printed = Object.fromEntries(
    Object.entries(transcript).filter(([name]) => name.startsWith("live") === live),
  );
  process.stdout.write(`${JSON.stringify(printed, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
