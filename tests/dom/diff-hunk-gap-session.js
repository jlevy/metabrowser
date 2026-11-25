// Browserless session: the unchanged lines between a code diff's hunks, through the production
// browser code (mb-zz81).
//
// builtin_plugins/diff/diff-view.js and diff-fold.js load whole, as the plugin loads them,
// and mount a comparison of three files into a small element tree that records what they
// build: `src/app.py`, 120 lines, whose commit adds a line at 10 and changes line 80, so its
// hunks leave lines 1 to 6, 14 to 76, and 84 to the end out; `notes.txt`, whose lines the
// comparison declines, as it does a file a textconv driver converts; a binary file;
// `wide.json`, whose lines are long enough that the route's byte bound cuts every answer to
// 4 of them; `tail.py`, whose last change ends three lines from its end, so the bar below it
// holds nothing; `end.txt`, whose last line has no newline; and `moved.py`, whose answers
// name another comparison, as a ref that moved since the diff was drawn gives. The gap loader
// stands in for the comparison route's `view=lines`
// (tests/golden/cli-api-diff-lines.tryscript.md pins what it answers), answering from the new
// side's text, from a start or up to an end, failing once with a 503 where a step says so,
// and declining `notes.txt` with a 409. `DIFF_GAP_LINES` is 25 here, so a long gap opens in
// steps.
//
// Geometry is a model, so the place a gap keeps can be read: the pane is 600 px tall, a file
// bar and the toolbar are 30 px, and a row, a hunk's separator, and a fold's bar are 20 px.
// The chip family and the preference store are stand-ins, as in diff-current-session.js.
//
// Each step prints what changed: a file's body, each fold's bar (`>` closed, `v` open, with
// what it says and the hunk's separator beside it), a separator that does not open, and its
// rows, a run of unchanged rows read for a gap as one line (its numbers, both sides', and its
// first and last text); the asks the step made; and, where a step is about the reader's
// place, the row at the pane's top before and after it.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");

let finished = false;
process.on("exit", (code) => {
  if (!finished && code === 0) {
    process.stderr.write("hunk gap session: ended before its last step\n");
    process.exitCode = 1;
  }
});

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// ── The page: elements that record what the production code builds ─────────

class ClassList {
  constructor(owner) {
    this.owner = owner;
  }

  get names() {
    return this.owner.className.split(" ").filter(Boolean);
  }

  add(...names) {
    this.owner.className = [...new Set([...this.names, ...names])].join(" ");
  }

  remove(name) {
    this.owner.className = this.names.filter((each) => each !== name).join(" ");
  }

  toggle(name, force) {
    const on = force ?? !this.names.includes(name);
    if (on) {
      this.add(name);
    } else {
      this.remove(name);
    }
    return on;
  }

  contains(name) {
    return this.names.includes(name);
  }
}

const PANE_PX = 600;
const BAR_PX = 30;
const ROW_PX = 20;
/** What draws as one row of the model. */
const ROWS = [
  "diff-line",
  "diff-split-row",
  "diff-hunk-header",
  "diff-availability",
  "fold-expander",
];

class PageElement {
  constructor(tag) {
    this.nodeType = tag === "#text" ? 3 : 1;
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.classList = new ClassList(this);
    this.childNodes = [];
    this.parentElement = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.dataset = {};
    this.style = {
      setProperty(name, value) {
        this[name] = value;
      },
      removeProperty(name) {
        delete this[name];
      },
    };
    this.hidden = false;
    this.text = "";
    this.markup = "";
  }

  get id() {
    return this.getAttribute("id") ?? "";
  }

  set id(value) {
    this.setAttribute("id", value);
  }

  get children() {
    return this.childNodes.filter((node) => node.nodeType === 1);
  }

  get parentNode() {
    return this.parentElement;
  }

  get isConnected() {
    for (let node = this; node; node = node.parentElement) {
      if (node === pane) {
        return true;
      }
    }
    return false;
  }

  get textContent() {
    return this.nodeType === 3
      ? this.text
      : this.childNodes.map((node) => node.textContent).join("");
  }

  set textContent(value) {
    if (this.nodeType === 3) {
      this.text = String(value);
      return;
    }
    this.childNodes = [];
    if (value) {
      this.append(text(String(value)));
    }
  }

  append(...nodes) {
    for (const given of nodes) {
      const node = typeof given === "string" ? text(given) : given;
      if (node.tagName === "#FRAGMENT") {
        this.append(...node.childNodes.splice(0));
        continue;
      }
      node.remove?.();
      node.parentElement = this;
      this.childNodes.push(node);
    }
  }

  prepend(...nodes) {
    for (const node of nodes) {
      node.remove?.();
      node.parentElement = this;
    }
    this.childNodes.unshift(...nodes);
  }

  replaceChildren(...nodes) {
    for (const child of this.childNodes) {
      child.parentElement = null;
    }
    this.childNodes = [];
    this.append(...nodes);
  }

  remove() {
    if (this.parentElement !== null) {
      const siblings = this.parentElement.childNodes;
      siblings.splice(siblings.indexOf(this), 1);
      this.parentElement = null;
    }
  }

  #insert(offset, nodes) {
    const parent = this.parentElement;
    for (const node of nodes) {
      node.remove?.();
    }
    const at = parent.childNodes.indexOf(this) + offset;
    for (const node of nodes) {
      node.parentElement = parent;
    }
    parent.childNodes.splice(at, 0, ...nodes);
  }

  after(...nodes) {
    this.#insert(1, nodes);
  }

  before(...nodes) {
    this.#insert(0, nodes);
  }

  replaceWith(node) {
    this.before(node);
    this.remove();
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  addEventListener(type, listener, options) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
    options?.signal?.addEventListener("abort", () => this.removeEventListener(type, listener));
  }

  removeEventListener(type, listener) {
    this.listeners.set(
      type,
      (this.listeners.get(type) ?? []).filter((candidate) => candidate !== listener),
    );
  }

  /** A click, as a press of the bar or Enter on it sends: it bubbles to the file's bar. */
  click() {
    let stopped = false;
    const event = {
      type: "click",
      target: this,
      stopPropagation() {
        stopped = true;
      },
    };
    for (let node = this; node && !stopped; node = node.parentElement) {
      for (const listener of node.listeners.get("click") ?? []) {
        listener(event);
      }
    }
  }

  dispatch(type) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ type, target: this });
    }
  }

  contains(node) {
    for (let at = node; at; at = at.parentElement) {
      if (at === this) {
        return true;
      }
    }
    return false;
  }

  focus() {
    page.activeElement = this;
  }

  matches(selector) {
    if (selector.startsWith(".")) {
      return this.classList.contains(selector.slice(1));
    }
    const valued = /^\[([\w-]+)="([^"]*)"\]$/.exec(selector);
    if (valued) {
      return this.getAttribute(valued[1]) === valued[2];
    }
    const named = /^\[([\w-]+)\]$/.exec(selector);
    if (named) {
      return this.attributes.has(named[1]);
    }
    return /^[a-z]+$/.test(selector) && this.tagName === selector.toUpperCase();
  }

  closest(selector) {
    for (let node = this; node; node = node.parentElement) {
      if (node.nodeType === 1 && node.matches(selector)) {
        return node;
      }
    }
    return null;
  }

  *walk() {
    for (const child of this.children) {
      yield child;
      yield* child.walk();
    }
  }

  querySelectorAll(selector) {
    return [...this.walk()].filter((node) => node.matches(selector));
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }

  find(className) {
    return this.querySelectorAll(`.${className}`);
  }

  get innerHTML() {
    return this.markup;
  }

  // An icon's markup is kept as a string; a chooser, as the stand-in chip family hands it,
  // is drawn as its chips.
  set innerHTML(value) {
    this.childNodes = [];
    if (typeof value !== "object") {
      this.markup = String(value);
      return;
    }
    for (const option of value.options) {
      const chip = element("button");
      chip.dataset.chipValue = option.value;
      chip.setAttribute("data-chip-value", option.value);
      chip.chipKey = value.key;
      chip.textContent = option.label;
      chip.setAttribute("aria-checked", String(value.value === option.value));
      this.append(chip);
    }
  }

  /** The model's box: a bar and each row its fixed height, inside the pane's scroll. */
  getBoundingClientRect() {
    if (this === pane) {
      return { top: 0, bottom: PANE_PX, left: 0, right: 0, height: PANE_PX, width: 0 };
    }
    let offset = 0;
    let node = this;
    for (; node.parentElement !== null && node !== pane; node = node.parentElement) {
      for (const sibling of node.parentElement.children) {
        if (sibling === node) {
          break;
        }
        offset += heightOf(sibling);
      }
    }
    const top = node === pane ? offset - pane.scrollTop : 0;
    const height = heightOf(this);
    return { top, bottom: top + height, left: 0, right: 0, height, width: 0 };
  }
}

function heightOf(node) {
  if (node.nodeType !== 1 || node.hidden) {
    return 0;
  }
  if (node.classList.contains("diff-file-bar") || node.classList.contains("diff-toolbar")) {
    return BAR_PX;
  }
  if (ROWS.some((name) => node.classList.contains(name))) {
    return ROW_PX;
  }
  return node.children.reduce((sum, child) => sum + heightOf(child), 0);
}

const element = (tag) => new PageElement(tag);
const text = (value) => {
  const node = new PageElement("#text");
  node.text = value;
  return node;
};

const page = {
  activeElement: null,
  addEventListener() {},
  removeEventListener() {},
  createElement: (tag) => element(tag),
  createTextNode: (value) => text(String(value)),
  createDocumentFragment: () => element("#fragment"),
};
globalThis.document = page;

/** The scroller the diff sits in, as a pull request's pane is: `data-kpress-viewport`. */
const pane = element("div");
pane.setAttribute("data-kpress-viewport", "");
pane.clientHeight = PANE_PX;
pane.scrollTop = 0;

async function settle() {
  for (let turn = 0; turn < 30; turn += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

// ── The comparison ──────────────────────────────────────────────────────────

/** The new side of `src/app.py`: line 10 added, line 80 changed. */
const NEW = Array.from({ length: 120 }, (_, index) => {
  const number = index + 1;
  return number === 10 ? "added line" : number === 80 ? "line 80, changed" : `line ${number}`;
});
// The bytes of a file the stand-in highlights at most: its hunks and the three gaps the session opens
// first, and not the fourth, so the last is drawn plain, as a file past `SYNTAX_HIGHLIGHT_MAX_BYTES` is.
const LEXED_BYTES = 800;
const NOTES = Array.from({ length: 30 }, (_, index) => `note ${index + 1}`);
const side = (filePath, oid) => ({
  content: { kind: "git_object", oid },
  entry_type: "file",
  mode: "100644",
  path: filePath,
});
const context = (from, to, lines) =>
  Array.from({ length: to - from + 1 }, (_, index) => ({
    op: "context",
    text: lines[from + index - 1],
  }));

/** The new side of a file whose line *changed* is all its commit changes. */
const lines = (prefix, length, changed) =>
  Array.from({ length }, (_, index) =>
    index + 1 === changed ? `${prefix}${index + 1}, changed` : `${prefix}${index + 1}`,
  );
const WIDE = lines("row ", 200, 150);
const TAIL = lines("tail ", 10, 7);
const END = lines("end ", 20, 5);
const MOVED = lines("moved ", 30, 15);
/** Each such file's new side, and whether it ends with a newline. */
const SIDES = {
  "src/app.py": { lines: NEW, newline: true },
  "wide.json": { lines: WIDE, newline: true },
  "tail.py": { lines: TAIL, newline: true },
  "end.txt": { lines: END, newline: false },
  "moved.py": { lines: MOVED, newline: true },
};
// The lines one answer for `wide.json` holds, as the route's `MAX_LINES_ANSWER_BYTES` cuts a
// run of long lines: those nearest the line it was asked from.
const WIDE_ANSWER_LINES = 4;
/** A file whose commit changes line *changed* of *after*, and its one hunk. */
function changedOnce(id, filePath, after, changed) {
  const first = changed - 3;
  const last = Math.min(changed + 3, after.length);
  return {
    change: {
      additions: 1,
      availability: "ready",
      binary: false,
      deletions: 1,
      id,
      kind: "modified",
      new: side(filePath, id.repeat(20).slice(0, 40)),
      old: side(filePath, id.repeat(20).slice(0, 40).replace(/./, "0")),
    },
    patch: {
      hunks: [
        {
          heading: "",
          lines: [
            ...context(first, changed - 1, after),
            { op: "del", text: after[changed - 1].replace(", changed", "") },
            { op: "add", text: after[changed - 1] },
            ...context(changed + 1, last, after),
          ],
          new_count: last - first + 1,
          new_start: first,
          old_count: last - first + 1,
          old_start: first,
        },
      ],
      truncated: false,
    },
  };
}
const ONCE = [
  changedOnce("f4", "wide.json", WIDE, 150),
  changedOnce("f5", "tail.py", TAIL, 7),
  changedOnce("f6", "end.txt", END, 5),
  changedOnce("f7", "moved.py", MOVED, 15),
];

const comparison = {
  manifest: {
    cursor: null,
    files: [
      {
        additions: 2,
        availability: "ready",
        binary: false,
        deletions: 1,
        id: "f1",
        kind: "modified",
        new: side("src/app.py", "1".repeat(40)),
        old: side("src/app.py", "2".repeat(40)),
      },
      {
        additions: 1,
        availability: "ready",
        binary: false,
        deletions: 1,
        id: "f2",
        kind: "modified",
        new: side("notes.txt", "3".repeat(40)),
        old: side("notes.txt", "4".repeat(40)),
      },
      {
        additions: null,
        availability: "binary",
        binary: true,
        deletions: null,
        id: "f3",
        kind: "modified",
        new: side("logo.png", "5".repeat(40)),
        old: side("logo.png", "6".repeat(40)),
      },
      ...ONCE.map((once) => once.change),
    ],
    totals: { additions: 7, deletions: 6, exact: true, files: 7 },
    truncated: false,
  },
  patches: {
    f1: {
      hunks: [
        {
          heading: "",
          lines: [...context(7, 9, NEW), { op: "add", text: NEW[9] }, ...context(11, 13, NEW)],
          new_count: 7,
          new_start: 7,
          old_count: 6,
          old_start: 7,
        },
        {
          heading: "def main():",
          lines: [
            ...context(77, 79, NEW),
            { op: "del", text: "line 80" },
            { op: "add", text: NEW[79] },
            ...context(81, 83, NEW),
          ],
          new_count: 7,
          new_start: 77,
          old_count: 7,
          old_start: 76,
        },
      ],
      truncated: false,
    },
    f2: {
      hunks: [
        {
          heading: "",
          lines: [
            ...context(10, 12, NOTES),
            { op: "del", text: "note 13 before" },
            { op: "add", text: NOTES[12] },
            ...context(14, 16, NOTES),
          ],
          new_count: 7,
          new_start: 10,
          old_count: 7,
          old_start: 10,
        },
      ],
      truncated: false,
    },
    ...Object.fromEntries(ONCE.map((once) => [once.change.id, once.patch])),
  },
  resolved: { comparison_id: "git:session", options: { context: 3 } },
  schema: "file-diff-v1",
  schema_version: 1,
};

// ── What a step prints ──────────────────────────────────────────────────────

/** A bar: closed `>` or open `v`, what it says, the separator beside it, and if it waits. */
function bar(node) {
  const open = node.getAttribute("aria-expanded") === "true";
  const label = node.find("diff-fold-label")[0]?.textContent ?? "";
  const detail = node.find("diff-fold-detail")[0]?.textContent ?? "";
  const busy = node.getAttribute("aria-busy") === "true" ? " (loading)" : "";
  return `${open ? "v" : ">"} [${label}]${detail ? ` ${detail}` : ""}${busy}`;
}

/** A code row's numbers, marker, and text, Split's as both sides. */
function row(node) {
  if (node.classList.contains("diff-split-row")) {
    return node.children
      .map((cell) => {
        const number = cell.find("diff-line-number")[0]?.textContent || "-";
        return `${number} ${cell.find("diff-line-text")[0]?.textContent ?? ""}`;
      })
      .join(" || ");
  }
  const numbers = node.children
    .filter((child) => child.classList.contains("diff-line-number"))
    .map((child) => child.textContent || "-");
  const marker = node.find("diff-line-marker")[0]?.textContent ?? "";
  const highlighted = node.find("hljs-string").length > 0 ? " *" : "";
  const open = node.find("diff-line-no-newline").length > 0 ? " (no newline)" : "";
  return `${numbers.join(" ")} |${marker}${node.find("diff-line-text")[0]?.textContent ?? ""}${highlighted}${open}`;
}

/** A gap's run of rows, as one line: how many, the first's and last's numbers and text. */
function run(rows) {
  const first = rows[0];
  const last = rows.at(-1);
  return `${rows.length} rows: ${row(first)} ... ${row(last)}`;
}

/** What a file's body draws, a gap's rows collapsed into their runs. */
function body(section) {
  const shown = [];
  /** @type {object[]} */
  let pending = [];
  const flush = () => {
    if (pending.length > 0) {
      shown.push(pending.length > 2 ? run(pending) : pending.map(row).join("; "));
      pending = [];
    }
  };
  for (const node of section.find("diff-file-body")[0].walk()) {
    if (node.classList.contains("fold-expander")) {
      flush();
      shown.push(bar(node));
    } else if (node.classList.contains("diff-hunk-header")) {
      flush();
      shown.push(`= ${node.textContent}`);
    } else if (node.classList.contains("diff-notice")) {
      flush();
      shown.push(`says: ${node.textContent}`);
    } else if (node.classList.contains("diff-availability")) {
      flush();
      shown.push(`says: ${node.textContent}`);
    } else if (node.classList.contains("diff-line") || node.classList.contains("diff-split-row")) {
      if (node.parentElement.classList.contains("diff-gap-group")) {
        pending.push(node);
      } else {
        flush();
        shown.push(row(node));
      }
    }
  }
  flush();
  return shown;
}

async function main() {
  globalThis.window = { location: { origin: "http://127.0.0.1:8123" } };
  globalThis.METABROWSER_SETTINGS = { DIFF_GAP_LINES: 25 };
  const view = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view.js")).href
  );

  /** Every ask the gap loader is sent, and what fails next. */
  const asks = [];
  let failNext = false;
  view.setGapLoader(async (revision, filePath, ask) => {
    const at = "start" in ask ? `start=${ask.start}` : `end=${ask.end}`;
    asks.push(`${revision} ${filePath} lines ${at} count=${ask.count}`);
    await new Promise((resolve) => setTimeout(resolve, 0));
    if (filePath === "notes.txt") {
      throw Object.assign(new Error("HTTP 409"), {
        status: 409,
        payload: { code: "textconv", message: "These lines cannot be shown." },
      });
    }
    if (failNext) {
      failNext = false;
      throw Object.assign(new Error("HTTP 503"), { status: 503, payload: null });
    }
    // A run from its start, or ending before its end or at the side's last line, as the
    // route cuts one; `wide.json`'s cut short at the end far from where it was asked from.
    const { lines: all, newline } = SIDES[filePath];
    const last = "start" in ask ? ask.start + ask.count : Math.min(ask.end, all.length + 1);
    let start = "start" in ask ? ask.start : Math.max(1, ask.end - ask.count);
    let run = all.slice(start - 1, last - 1);
    if (filePath === "wide.json" && run.length > WIDE_ANSWER_LINES) {
      run = "start" in ask ? run.slice(0, WIDE_ANSWER_LINES) : run.slice(-WIDE_ANSWER_LINES);
      start = "start" in ask ? start : last - WIDE_ANSWER_LINES;
    }
    return {
      comparison_id: filePath === "moved.py" ? "git:moved" : "git:session",
      file_id: "f1",
      path: filePath,
      start,
      lines: run,
      line_count: all.length,
      ends_with_newline: newline,
    };
  });
  const lexed = [];

  /** A diff mounted in the pane: *revision* is what a comparison's page carries beside it. */
  function mount(revision) {
    const binds = [];
    const api = {
      // Each line one run, so a highlighted row is a row whose text has a child span. The
      // file's bound counts the hunks' bytes and every gap's highlighted so far: 1,500 here,
      // so the session reaches it.
      highlightSyntax: async (source, language) => {
        lexed.push(`${language}: ${source.split("\n").length} lines`);
        return source.split("\n").map((line) => [{ text: line, classes: ["hljs-string"] }]);
      },
      isLargeTextPreview: (data) => Number(data.size) > LEXED_BYTES,
      langForPath: (filePath) => (filePath.endsWith(".py") ? "python" : ""),
      ensureAsset: async () => {},
      prefs: {
        get: (key, fallback) => (key === "diff.layout" ? "unified" : fallback),
        set: () => true,
      },
      filterControls: {
        groupHtml: (spec) => spec,
        bind(root, handlers) {
          binds.push({ root, handlers });
          return () => {};
        },
      },
    };
    const host = element("div");
    pane.replaceChildren(host);
    pane.scrollTop = 0;
    const document_ = structuredClone(comparison);
    if (revision !== null) {
      Object.defineProperty(document_, "__revision", { value: revision, enumerable: false });
    }
    const handle = view.mountDiffView(host, document_, api, { showSummary: false });
    const root = host.find("diff-root")[0];
    const sections = () => root.children.filter((node) => node.classList.contains("diff-file"));
    const sectionOf = (filePath) =>
      sections().find((section) => section.textContent.includes(filePath));
    return {
      handle,
      sectionOf,
      /** What *filePath* draws now. */
      body: (filePath) => body(sectionOf(filePath)),
      /** The bar in *filePath* whose label reads *label*. */
      barOf(filePath, label) {
        const found = sectionOf(filePath)
          .find("fold-expander")
          .find((node) => node.find("diff-fold-label")[0]?.textContent === label);
        assert(found !== undefined, `${filePath} has no bar reading ${label}`);
        return found;
      },
      async press(filePath, label) {
        this.barOf(filePath, label).click();
        await settle();
      },
      /** A chooser's chip, as the chip family hands its click to the handlers around it. */
      async choose(group, value) {
        const chip = root.find(group)[0].querySelector(`[data-chip-value="${value}"]`);
        for (const record of binds) {
          if (record.root.contains(chip)) {
            record.handlers.onChange(chip.chipKey, value, "one");
          }
        }
        await settle();
      },
      /** The first row whose box ends below the pane's top: how it reads, and its top. */
      rowAtTop() {
        const rows = root
          .querySelectorAll(".diff-line")
          .concat(root.querySelectorAll(".diff-split-row"))
          .filter((each) => each.getBoundingClientRect().bottom > 0)
          .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
        return rows.length === 0
          ? null
          : `${row(rows[0])} at ${rows[0].getBoundingClientRect().top} px`;
      },
      /** The pane scrolled so the first row that reads *needle* is *top* px down it. */
      scrollRowTo(needle, top) {
        const found = root
          .querySelectorAll(".diff-line")
          .find((each) => each.find("diff-line-text")[0]?.textContent === needle);
        assert(found !== undefined, `no row reads ${needle}`);
        pane.scrollTop += found.getBoundingClientRect().top - top;
        pane.dispatch("scroll");
      },
    };
  }

  // What the view tells the console, its first argument, said with the step that caused it: a
  // load that failed and a refusal are the console's to explain (docs/design-system-messages.md).
  const warned = [];
  console.warn = (message) => warned.push(String(message));
  const steps = [];
  const asked = () => asks.splice(0);
  const step = (name, diff, files, extra = {}) =>
    steps.push({
      step: name,
      ...Object.fromEntries(files.map((filePath) => [filePath, diff.body(filePath)])),
      asks: asked(),
      ...(warned.length > 0 ? { console: warned.splice(0) } : {}),
      ...extra,
    });

  const diff = mount("HEAD");
  await settle();
  lexed.splice(0);
  step("A comparison: each hunk's separator is a fold's bar, and one more below the last", diff, [
    "src/app.py",
    "notes.txt",
    "logo.png",
  ]);

  await diff.press("src/app.py", "6 unchanged lines");
  step("The bar above the first hunk opens to the file's first lines", diff, ["src/app.py"], {
    highlighted: lexed.splice(0),
  });

  // The reader is below the bar between the hunks, which is just above the pane's top, and
  // opens it from the keyboard: the rows it draws push nothing they are looking at.
  diff.scrollRowTo("line 77", 0);
  const before = diff.rowAtTop();
  await diff.press("src/app.py", "63 unchanged lines");
  step(
    "The gap between the hunks opens its 25 lines nearest the hunk below",
    diff,
    ["src/app.py"],
    {
      rowAtTopBefore: before,
      rowAtTopAfter: diff.rowAtTop(),
      highlighted: lexed.splice(0),
    },
  );

  failNext = true;
  await diff.press("src/app.py", "38 unchanged lines");
  step("Its next step's lines do not load: the bar closes and says so", diff, ["src/app.py"]);

  await diff.press("src/app.py", "Could not load 38 unchanged lines. Retry");
  step("A press asks again, and the next 25 lines are drawn above the last", diff, ["src/app.py"], {
    highlighted: lexed.splice(0),
  });

  await diff.press("src/app.py", "Rest of the file");
  step(
    "Below the last hunk: the rest of the file, whose end the answer says",
    diff,
    ["src/app.py"],
    { highlighted: lexed.splice(0) },
  );

  await diff.press("src/app.py", "Hide 50 lines");
  step("Closing a gap closes its steps too", diff, ["src/app.py"]);

  await diff.press("src/app.py", "63 unchanged lines");
  step("Opened again, it shows its first lines from what it read, asking for none", diff, [
    "src/app.py",
  ]);

  await diff.choose("diff-layout-control", "split");
  step("Split draws the open gaps' lines on both sides, at both numbers", diff, ["src/app.py"]);

  await diff.choose("diff-layout-control", "unified");
  await diff.choose("diff-show-control", "current");
  step("Current draws them at their new numbers", diff, ["src/app.py"]);
  await diff.choose("diff-show-control", "diff");

  await diff.press("notes.txt", "9 unchanged lines");
  step("A file whose lines the comparison declines draws plain separators, saying so", diff, [
    "notes.txt",
  ]);

  await diff.press("wide.json", "146 unchanged lines");
  step(
    "An answer its byte bound cuts short opens the lines nearest the hunk, the rest behind a bar",
    diff,
    ["wide.json"],
  );

  await diff.press("wide.json", "142 unchanged lines");
  step("Its next step asks once more, up to the lines it drew", diff, ["wide.json"]);

  await diff.press("wide.json", "Hide 8 lines");
  await diff.press("wide.json", "146 unchanged lines");
  step("Closed and opened again, it opens to the lines it read, asking for none", diff, [
    "wide.json",
  ]);

  await diff.press("wide.json", "Rest of the file");
  step("Below the last hunk too: the lines nearest the hunk, then a bar for the rest", diff, [
    "wide.json",
  ]);

  // The reader reaches the bar below `tail.py`'s hunk from the keyboard.
  diff.barOf("tail.py", "Rest of the file").focus();
  await diff.press("tail.py", "Rest of the file");
  step(
    "A bar below a hunk that ends the file goes, and the keyboard goes on from the file's bar",
    diff,
    ["tail.py"],
    { focused: document.activeElement?.className ?? null },
  );

  await diff.press("end.txt", "Rest of the file");
  step("A file's last line with no newline says so, as the patch's own does", diff, ["end.txt"]);

  await diff.press("moved.py", "11 unchanged lines");
  step("An answer for another comparison, as a moved ref gives, is declined, saying so", diff, [
    "moved.py",
  ]);
  diff.handle.dispose();

  const patch = mount(null);
  await settle();
  step("A patch file names no snapshot, so its separators do not open", patch, ["src/app.py"]);
  patch.handle.dispose();

  console.log(JSON.stringify({ steps }, null, 2));
  finished = true;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
