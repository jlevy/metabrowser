// Browserless session: the diff's Diff | Excerpt | Full choice, through the production browser code.
//
// builtin_plugins/diff/diff-view.js, diff-markdown.js and diff-structured.js load whole, as
// the plugin loads them, with static/inert-html.js run as a page runs it and the structured
// plugin's tree helpers, and mount a comparison of six files into a small element tree that
// records what they build: a Markdown file, a code file, a YAML file, a deleted file, a file
// left empty, and a binary file. The rendered files' answers are the server's projections,
// recorded in tests/fixtures/diff-markdown-responses.json, with the recorded parse of each
// block, so the page's own sanitizer runs on what the server sends, and in
// tests/fixtures/diff-structured-responses.json; tests/test_diff_markdown_session.py and
// tests/test_diff_structured_session.py fail when the server answers differently.
//
// The shared chip family, the preference store, and the shortcut registry are stand-ins. The
// chip family draws a chooser's options as buttons and hands a chip's click to the handlers
// bound on an element that holds it; the store answers what was stored; the registry records
// an attachment and runs its `activate` as it would for the first live target, and
// tests/dom/plugin-shortcuts-session.js runs the production surface. Geometry is a model, so
// that the place a choice keeps can be read: the pane is 600 px tall, the toolbar and a file bar
// are 30 px, and every drawn row 20 px, so a file's place moves as Diff and Excerpt draw more or
// fewer rows.
//
// Each step prints what the diff shows, what its toolbar holds, its Diff | Excerpt | Full (`*` marks
// the chosen chip), the layout control, where `N` and `L` sit, what was written to the
// preferences, what each file bar's end group holds where that changed, and, for each file
// whose drawing the step changed, what it draws: a code body's hunk headers and rows (the line
// numbers, the marker, the text), a rendered body's blocks and front matter or its tree's rows,
// and what a file with no rows says. A row Excerpt leaves hidden is not printed. A pull
// request's Docs tab mounts the same diff as its page does, with the layout fixed, Full
// its default, and a preference of its own, and its steps print what it opens on and what is
// written, apart from Changes' `diff.show`.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/diff-markdown-responses.json"), "utf8"),
);
const trees = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/diff-structured-responses.json"), "utf8"),
);
const ORIGIN = "http://127.0.0.1:8123";

// The structured plugin's tree helpers are classic scripts that publish on the global object,
// read here as the page reads them from the plugin's exports.
const plugins = path.join(repoRoot, "src/metabrowser/builtin_plugins");
require(path.join(plugins, "../static/structured-preview.js"));
require(path.join(plugins, "../static/structured-tree.js"));
const tree = globalThis.__structuredTree;
const helpers = {
  materializeRows: tree.materializeRows,
  renderRowHtml: tree.renderRowHtml,
  calculateOptimalExpansion: globalThis.__structuredPreview.calculateOptimalExpansion,
  expansion: tree.expansion,
};

let finished = false;
process.on("exit", (code) => {
  if (!finished && code === 0) {
    process.stderr.write("Current session: ended before its last step\n");
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

/** The pane the diff scrolls in: 600 px tall, at the top of the viewport. */
const PANE_PX = 600;
const BAR_PX = 30;
const ROW_PX = 20;
/** What draws as one row of the model. */
const ROWS = [
  "diff-line",
  "diff-split-row",
  "diff-hunk-header",
  "diff-markdown-block",
  "diff-availability",
  "srow",
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
    this.open = false;
    this.text = "";
    this.markup = "";
  }

  // The id is the attribute, as in a document.
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
    return this.parentElement !== null;
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

  get firstElementChild() {
    return this.children[0];
  }

  get previousElementSibling() {
    const siblings = this.parentElement?.children ?? [];
    return siblings[siblings.indexOf(this) - 1] ?? null;
  }

  get nextElementSibling() {
    const siblings = this.parentElement?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
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

  // Only a tree's rows are written as markup this way.
  insertAdjacentHTML(position, html) {
    const rows = parseRows(html);
    if (position === "beforebegin") {
      this.before(...rows);
    } else {
      assert(position === "beforeend" && this.classList.contains("tree-viewport"), position);
      this.append(...rows);
    }
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

  /** What one selector this session's code asks for matches. */
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
    if (selector === "button[data-chip-value]") {
      return this.tagName === "BUTTON" && this.dataset.chipValue !== undefined;
    }
    if (selector === "a[href], img[src]") {
      return (
        (this.tagName === "A" && this.getAttribute("href") !== null) ||
        (this.tagName === "IMG" && this.getAttribute("src") !== null)
      );
    }
    if (selector === 'a[href^="/view/"]') {
      return this.tagName === "A" && (this.getAttribute("href") ?? "").startsWith("/view/");
    }
    if (selector === "a[href]") {
      return this.tagName === "A" && this.getAttribute("href") !== null;
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

  // An icon's markup is kept as a string; a chooser, as the stand-in chip family below hands
  // it, is drawn as its chips.
  set innerHTML(value) {
    this.childNodes = [];
    if (typeof value !== "object" && this.classList.contains("tree-viewport")) {
      this.append(...parseRows(value));
      return;
    }
    if (typeof value !== "object") {
      this.markup = String(value);
      return;
    }
    for (const option of value.options) {
      const chip = element("button");
      chip.dataset.chipValue = option.value;
      chip.setAttribute("data-chip-value", option.value);
      chip.chipKey = value.key;
      if (option.tip !== undefined) {
        chip.dataset.tipText = option.tip;
      }
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
  // A fold's bar is a row; a chunk of rendered blocks not drawn yet keeps the height the
  // views estimate for it.
  if (node.classList.contains("fold-expander")) {
    return ROW_PX;
  }
  if (node.classList.contains("diff-markdown-spacer")) {
    return Number.parseFloat(node.style?.height ?? "0") || 0;
  }
  return node.children.reduce((sum, child) => sum + heightOf(child), 0);
}

const element = (tag) => new PageElement(tag);
const text = (value) => {
  const node = new PageElement("#text");
  node.text = value;
  return node;
};

const ENTITIES = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'" };
const unescapeHtml = (value) =>
  value.replace(/&(?:amp|lt|gt|quot|#39);/g, (each) => ENTITIES[each]);

// One row of renderRowHtml: a div with its class, path and indent, holding spans only.
const ROW =
  /<div class="([^"]*)" data-path="([^"]*)" style="([^"]*)">((?:(?!<\/?div)[\s\S])*)<\/div>/g;

/** A tree's markup as the elements a page parses it into: rows, and nothing else. */
function parseRows(html) {
  const built = [];
  let consumed = 0;
  for (const match of html.matchAll(ROW)) {
    assert(match.index === consumed, `a tree's markup holds only rows: ${html.slice(consumed)}`);
    consumed = match.index + match[0].length;
    const row = element("div");
    row.className = match[1];
    row.setAttribute("data-path", unescapeHtml(match[2]));
    row.setAttribute("style", match[3]);
    row.inner = match[4];
    built.push(row);
  }
  assert(consumed === html.length, `a tree's markup holds only rows: ${html.slice(consumed)}`);
  return built;
}

// The template a page parses a block into, built from the recorded parse of that block.
function parsed(nodes) {
  return nodes.map((node) => {
    if (typeof node === "string") {
      const built = text(node);
      built.nodeValue = node;
      return built;
    }
    const built = element(node.tag);
    for (const [name, value] of node.attrs) {
      built.setAttribute(name, value);
    }
    built.append(...parsed(node.children));
    return built;
  });
}

function template() {
  const made = element("template");
  Object.defineProperty(made, "innerHTML", {
    set(html) {
      assert(html in recorded.trees, `no recorded parse for ${html}`);
      const content = element("#fragment");
      content.append(...parsed(recorded.trees[html]));
      made.content = content;
    },
  });
  return made;
}

const page = {
  activeElement: null,
  addEventListener() {},
  removeEventListener() {},
  createElement: (tag) => (tag === "template" ? template() : element(tag)),
  createTextNode: (value) => text(String(value)),
  createDocumentFragment: () => element("#fragment"),
  implementation: {
    createHTMLDocument: () => ({
      createElement: (tag) => element(tag),
      createTextNode: (value) => text(String(value)),
    }),
  },
};
globalThis.document = page;

/** The scroller the diff sits in, as a pull request's pane is: `data-kpress-viewport`. */
const pane = element("div");
pane.setAttribute("data-kpress-viewport", "");
pane.clientHeight = PANE_PX;
pane.scrollTop = 0;

/** The Markdown views ask for a block of the file once it is near the screen. */
const observers = [];
globalThis.IntersectionObserver = class {
  constructor(notify) {
    this.notify = notify;
    this.observed = new Set();
    observers.push(this);
  }

  observe(target) {
    this.observed.add(target);
  }

  unobserve(target) {
    this.observed.delete(target);
  }

  disconnect() {
    this.observed.clear();
  }
};

/** Every observed element comes into view, as a pane tall enough for them all shows them. */
function reveal() {
  for (const observer of observers) {
    observer.notify(
      [...observer.observed].map((target) => ({ target, isIntersecting: true })),
      observer,
    );
  }
}

// Timers, not immediates: a report of the file at the pane's top waits on a timer where a
// page has no frames, and immediates can all run before it fires.
async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

// ── The comparison ──────────────────────────────────────────────────────────

const side = (filePath, size) => ({
  content: { kind: "empty" },
  entry_type: "file",
  mode: "100644",
  path: filePath,
  ...(size === undefined ? {} : { size }),
});
const hunk = (oldStart, oldCount, newStart, newCount, lines, heading) => ({
  ...(heading === undefined ? {} : { heading }),
  lines: lines.map(([op, value]) => ({ op, text: value })),
  new_count: newCount,
  new_start: newStart,
  old_count: oldCount,
  old_start: oldStart,
});
const C = "context";

/** Five files: Markdown, code, deleted, emptied, and binary, which has no text diff. */
const comparison = {
  manifest: {
    cursor: null,
    files: [
      {
        additions: 3,
        availability: "ready",
        binary: false,
        deletions: 3,
        id: "f1",
        kind: "modified",
        new: side("docs/guide.md"),
        old: side("docs/guide.md"),
      },
      {
        additions: 2,
        availability: "ready",
        binary: false,
        deletions: 1,
        id: "f2",
        kind: "modified",
        new: side("a.py"),
        old: side("a.py"),
      },
      {
        additions: 2,
        availability: "ready",
        binary: false,
        deletions: 4,
        id: "f6",
        kind: "modified",
        new: side("config/app.yaml"),
        old: side("config/app.yaml"),
      },
      {
        additions: 0,
        availability: "ready",
        binary: false,
        deletions: 2,
        id: "f3",
        kind: "deleted",
        old: side("old.txt", 14),
      },
      {
        additions: 0,
        availability: "ready",
        binary: false,
        deletions: 2,
        id: "f4",
        kind: "modified",
        new: side("notes.txt", 0),
        old: side("notes.txt", 12),
      },
      {
        additions: null,
        availability: "binary",
        binary: true,
        deletions: null,
        id: "f5",
        kind: "added",
        new: {
          content: { kind: "git_object", oid: "a".repeat(40) },
          entry_type: "file",
          mode: "100644",
          path: "logo.png",
          size: 2048,
        },
      },
    ],
    totals: { additions: 7, deletions: 12, exact: true, files: 6 },
    truncated: false,
  },
  patches: {
    f1: {
      file_id: "f1",
      hunks: [
        hunk(1, 4, 1, 4, [
          [C, "---"],
          ["del", "owner: docs"],
          ["add", "owner: platform"],
          [C, "title: Guide"],
          [C, "---"],
        ]),
        hunk(6, 4, 6, 4, [
          [C, "# Guide"],
          [C, ""],
          ["del", "Read the setup notes first."],
          ["add", "Read the [first setup notes](setup.md) first."],
          [C, ""],
        ]),
        hunk(30, 3, 30, 3, [
          [C, "![diagram](diagram.png)"],
          [C, ""],
          ["del", "The ~~old~~ closing line."],
          ["add", "The <ins>new</ins> closing line."],
        ]),
      ],
      truncated: false,
    },
    f2: {
      file_id: "f2",
      hunks: [
        hunk(
          3,
          3,
          3,
          4,
          [
            [C, "def f():"],
            ["del", "    return 1"],
            ["add", "    x = 2"],
            ["add", "    return x"],
            [C, ""],
          ],
          "def f():",
        ),
      ],
      truncated: false,
    },
    f6: {
      file_id: "f6",
      hunks: [
        hunk(1, 11, 1, 9, [
          [C, "name: demo"],
          ["del", "version: 3"],
          ["add", "version: 4"],
          [C, "services:"],
          [C, "  web:"],
          [C, "    image: nginx"],
          [C, "    ports:"],
          [C, "      - 80"],
          ["add", "      - 443"],
          ["del", "  db:"],
          ["del", "    image: postgres"],
          ["del", "    port: 5432"],
          [C, "flags: [fast, safe]"],
        ]),
      ],
      truncated: false,
    },
    f3: {
      file_id: "f3",
      hunks: [
        hunk(1, 2, 0, 0, [
          ["del", "first"],
          ["del", "second"],
        ]),
      ],
      truncated: false,
    },
    f4: {
      file_id: "f4",
      hunks: [
        hunk(1, 2, 0, 0, [
          ["del", "a note"],
          ["del", "another"],
        ]),
      ],
      truncated: false,
    },
  },
  resolved: {
    base_policy: "direct",
    comparison_id: "session:current",
    kind: "content",
    left: { kind: "patch" },
    options: { context: 3, rename_detection: true, rename_similarity: 50 },
    right: { kind: "patch" },
    source: { name: "session" },
  },
  schema: "file-diff-v1",
  schema_version: 1,
};
const PATHS = comparison.manifest.files.map((file) => (file.new ?? file.old).path);

// ── What a step prints ──────────────────────────────────────────────────────

/** A drawn code row: its line numbers, its marker, and its text. */
function codeRow(row) {
  const numbers = row.children
    .filter((node) => node.classList.contains("diff-line-number"))
    .map((node) => node.textContent || "-");
  const marker = row.find("diff-line-marker")[0]?.textContent ?? "";
  const body = row.find("diff-line-text")[0]?.textContent ?? "";
  return `${numbers.join(" ")} |${marker}${body}`;
}

/** A file's code body: each hunk's header and rows, Split as a count of its rows. */
function codeBody(body) {
  const shown = [];
  for (const node of body.walk()) {
    if (node.hidden || [...ancestors(node, body)].some((each) => each.hidden)) {
      continue;
    }
    if (node.classList.contains("diff-hunk-header")) {
      shown.push(node.textContent);
    } else if (node.classList.contains("diff-line")) {
      shown.push(codeRow(node));
    } else if (node.classList.contains("diff-availability")) {
      shown.push(`says: ${node.textContent}`);
    }
  }
  const split = body.find("diff-split-row").length;
  return split > 0 ? [...shown, `${split} Split rows`] : shown;
}

function* ancestors(node, within) {
  for (let at = node.parentElement; at !== null && at !== within; at = at.parentElement) {
    yield at;
  }
}

/** A rendered body: its blocks and its front matter, without what is hidden. */
function renderedBody(article) {
  const shown = [];
  for (const node of article.children) {
    if (node.hidden) {
      continue;
    }
    if (node.classList.contains("fold-expander")) {
      const open = node.getAttribute("aria-expanded") === "true";
      shown.push(`[${node.textContent}${open ? ", open" : ""}]`);
    } else if (node.classList.contains("diff-fold-group")) {
      shown.push(...renderedBody(node).map((line) => `  ${line}`));
    } else if (
      node.classList.contains("diff-markdown-change") ||
      node.classList.contains("diff-markdown-run")
    ) {
      // A change and its runs draw its bands (changeRuns in diff-markdown.js); its rows are
      // the blocks.
      shown.push(...renderedBody(node));
    } else if (node.classList.contains("diff-markdown-spacer")) {
      shown.push(`[blocks ${node.dataset.span} not drawn yet]`);
    } else if (node.classList.contains("diff-markdown-frontmatter")) {
      const list = node.querySelector("dl");
      const parts = list.children.filter((part) => !part.hidden);
      for (let index = 0; index < parts.length; index += 2) {
        const [term, value] = parts.slice(index, index + 2);
        const change = term.className.replace("diff-frontmatter-", "") || "context";
        const key = term.childNodes.filter((part) => part.className !== "sr-only")[0];
        shown.push(`front matter ${change}: ${key.textContent} = ${value.textContent}`);
      }
    } else {
      const kind = node.className.replace("diff-markdown-block diff-markdown-", "").split(" ")[0];
      const prose = node.children.filter((part) => part.className !== "sr-only");
      const images = prose.flatMap((part) => part.querySelectorAll("img")).map(() => "[image]");
      const words = prose
        .map((part) => part.textContent)
        .join("")
        .trim();
      shown.push(`${kind}: ${[words, ...images].filter(Boolean).join(" ")}`);
    }
  }
  return shown;
}

/** A tree row's text as a reader sees it: its key and value, without its screen-reader label. */
function visible(inner) {
  return unescapeHtml(
    inner
      .replace(/<span class="sr-only">[^<]*<\/span>/g, "")
      .replace(/<span class="srow-chevron[^"]*"[^>]*>[^<]*<\/span>/g, "")
      .replace(/<[^>]+>/g, ""),
  ).trim();
}

/** A YAML or JSON tree's drawn rows: each one's level, change, and text. */
function treeBody(container) {
  return container.find("srow").map((row) => {
    const indent = Number.parseFloat(/padding-left:([\d.]+)em/.exec(row.getAttribute("style"))[1]);
    const level = indent / (tree.expansion.indentChars * 0.5);
    const names = row.classList.names;
    const change = names.find((name) => name.startsWith("srow-change-"))?.slice(12) ?? "context";
    return `${"  ".repeat(level)}${change}: ${visible(row.inner)}`;
  });
}

/** Whether *node* is drawn: neither it nor anything that holds it is hidden. */
function drawnNode(node) {
  for (let at = node; at !== null; at = at.parentElement) {
    if (at.hidden) {
      return false;
    }
  }
  return true;
}

/** The drawn rows under *root*, in order: a Split row before the sides it holds. */
function drawnRowsOf(root) {
  return [...root.walk()].filter(
    (node) => ROWS.some((name) => node.classList.contains(name)) && drawnNode(node),
  );
}

/** A drawn row as it reads: a code row's text, each side's in Split, or a block's words. */
function rowReads(row) {
  const sides = row.find("diff-line-text").map((node) => node.textContent);
  return sides.length > 0 ? sides.join(" / ") : row.textContent.replace(/\s+/g, " ").trim();
}

/**
 * The first drawn row under *root* that reads *needle*, or holds it: a hunk header holds its
 * heading, which a line reads too.
 */
function rowReading(root, needle) {
  const rows = drawnRowsOf(root);
  const row =
    rows.find((each) => rowReads(each) === needle) ??
    rows.find((each) => rowReads(each).includes(needle));
  assert(row !== undefined, `no drawn row reads ${needle}`);
  return row;
}

/** A chooser's chips, `*` on the chosen one. */
function chips(control) {
  return control.children
    .map((chip) => `${chip.getAttribute("aria-checked") === "true" ? "*" : ""}${chip.textContent}`)
    .join(" | ");
}

// The production `markJoins`, which `main` loads with the module.
let markJoins = null;

// Each row's joins (`markJoins` in diff-markdown.js) are the ones the rows shown around it
// make in what the article shows now, Diff or Excerpt: marking it again whole, and each
// open fold, changes none of them.
function joinsAreFresh(article) {
  const all = [];
  const collect = (node) => {
    for (const child of node.children) {
      if (child.hidden) {
        continue;
      }
      if (child.classList.contains("diff-markdown-block")) {
        assert(child.dataset.join !== undefined, "a row shown is marked (markJoins)");
        all.push(child);
      } else {
        collect(child);
      }
    }
  };
  collect(article);
  const marks = () => all.map((row) => row.dataset.join);
  const before = JSON.stringify(marks());
  markJoins(article.children);
  for (const group of article.children) {
    if (group.classList.contains("diff-fold-group")) {
      markJoins(group.children);
    }
  }
  assert(JSON.stringify(marks()) === before, "a row's joins are stale");
}

/** What a file draws, as the reader sees it. */
function drawing(section) {
  const rendered = section.find("diff-markdown")[0];
  const structured = section.find("diff-structured")[0];
  const body = section.find("diff-file-body")[0];
  if (rendered !== undefined && !rendered.hidden) {
    joinsAreFresh(rendered);
    return { rendered: renderedBody(rendered) };
  }
  if (structured !== undefined && !structured.hidden) {
    return { rendered: treeBody(structured) };
  }
  return body.hidden ? { nothing: "while its rendered view loads" } : { source: codeBody(body) };
}

// ── The story ───────────────────────────────────────────────────────────────

async function main() {
  const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
  const realm = { window: {}, URL };
  vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), realm, { filename: inertPath });
  globalThis.window = {
    location: { origin: ORIGIN },
    MetabrowserInertHtml: realm.window.MetabrowserInertHtml,
  };
  const view = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view.js")).href
  );
  const markdownViews = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-markdown.js")).href
  );
  markJoins = markdownViews.markJoins;

  /** The mount options a pull request's Docs tab passes (github/pull-page.js). */
  const DOCS = {
    unfold: true,
    layout: "unified",
    show: "full",
    showPreference: "github.docs.show",
  };

  /**
   * A diff mounted in the pane under *stored* preferences, a plain object or a store shared
   * with another mount, and the host's *options*: none for Changes, a commit page and a patch.
   */
  function mount(stored, options = {}) {
    const prefs = stored instanceof Map ? stored : new Map(Object.entries(stored));
    const writes = [];
    const binds = [];
    const attachments = [];
    const api = {
      // A file's lines are said by the shell's brief change line, as the SDK hands it.
      ...require("./changed-files-tree-fixture.js").shellPainters(),
      highlightSyntax: async () => null,
      isLargeTextPreview: () => true,
      langForPath: () => "",
      ensureAsset: async () => {},
      // The structured plugin's exports, as `mb.plugins.load` hands them to the diff.
      plugins: { load: async () => helpers },
      prefs: {
        get: (key, fallback) => (prefs.has(key) ? prefs.get(key) : fallback),
        set(key, value) {
          prefs.set(key, value);
          writes.push(`${key}=${value}`);
          return true;
        },
      },
      // The chip family: the chooser's spec is its markup, which the page draws as chips.
      filterControls: {
        groupHtml: (spec) => spec,
        bind(root, handlers) {
          const record = { root, handlers, bound: true };
          binds.push(record);
          return () => {
            record.bound = false;
          };
        },
      },
      shortcuts: {
        attach(target, options) {
          const record = { detached: false, target, options, retargets: 0 };
          attachments.push(record);
          return {
            retarget(next) {
              record.target = next;
              record.retargets += 1;
            },
            detach() {
              record.detached = true;
            },
          };
        },
      },
    };
    const host = element("div");
    pane.replaceChildren(host);
    pane.scrollTop = 0;
    const document_ = { ...structuredClone(comparison), __revision: "fixture-head" };
    const handle = view.mountDiffView(host, document_, api, {
      showSummary: false,
      markdownViews,
      // As the route answers each view the page asks for: Docs asks for Full where the
      // document is short enough (`prefer-full`), and gets it for this one.
      renderMarkdown: async (fileId, _signal, ask) =>
        structuredClone(
          fileId === "f6"
            ? trees["config/app.yaml"]
            : recorded.answers.f1[`view=${ask?.view ?? "concise"}`],
        ),
      markdownTargets: markdownViews.markdownTargets(recorded.image_route, () => true),
      markdownHoldMs: 0,
      ...options,
    });
    const root = host.find("diff-root")[0];
    const toolbar = root.find("diff-toolbar")[0];
    const sections = () => root.children.filter((node) => node.classList.contains("diff-file"));
    const sectionOf = (filePath) => sections()[PATHS.indexOf(filePath)];
    const key = (id) => attachments.find((record) => record.options.id === id);
    /** Where a key's badge sits: the chip, and the file whose bar holds it, or the toolbar. */
    const keyAt = (id) => {
      const record = key(id);
      if (record === undefined) {
        return "not attached";
      }
      if (record.detached) {
        return "detached";
      }
      const section = record.target.closest(".diff-file");
      const where = section === null ? "the toolbar" : PATHS[sections().indexOf(section)];
      return `${record.options.key.toUpperCase()} on ${where}'s ${record.target.textContent}`;
    };
    /**
     * What the toolbar holds, in order, and what each of its choosers reads: the choosers'
     * end group as the list of what it holds.
     */
    const toolbarNow = () => {
      assert(toolbar !== undefined, "no toolbar");
      return toolbar.children.map(describe);
    };
    const describe = (child) => {
      if (child.classList.contains("diff-toolbar-end")) {
        return child.children.map(describe);
      }
      if (child.classList.contains("diff-show-control")) {
        return `Comparison view: ${chips(child)}`;
      }
      if (child.classList.contains("diff-layout-control")) {
        return `Split | Unified: ${child.children
          .map((chip) => {
            const disabled = chip.getAttribute("aria-disabled") === "true";
            const chosen = chip.getAttribute("aria-checked") === "true" ? "*" : "";
            return `${chosen}${chip.textContent}${disabled ? " (unavailable)" : ""}`;
          })
          .join(" | ")}`;
      }
      return child.className;
    };
    /** What each file bar's end group holds: Rendered | Source, or nothing. */
    const barEnds = () =>
      Object.fromEntries(
        sections().map((section, index) => {
          const end = section.find("diff-file-end")[0];
          const held = end.children
            .filter((child) => !child.hidden && !child.classList.contains("diff-markdown-progress"))
            .map((child) =>
              child.classList.contains("diff-markdown-control") ? chips(child) : child.className,
            );
          return [PATHS[index], held.length === 0 ? "nothing" : held.join(", ")];
        }),
      );
    const drawn = new Map();
    let endsSaid = null;
    return {
      handle,
      root,
      writes,
      binds,
      /** The pane scrolled so *filePath*'s bar is *top* px below the pane's top. */
      scrollTo(filePath, top) {
        pane.scrollTop += sectionOf(filePath).getBoundingClientRect().top - top;
        pane.dispatch("scroll");
      },
      topOf: (filePath) => sectionOf(filePath).getBoundingClientRect().top,
      /** The pane scrolled so the first drawn row that reads *needle* is *top* px down it. */
      scrollRowTo(needle, top) {
        pane.scrollTop += rowReading(root, needle).getBoundingClientRect().top - top;
        pane.dispatch("scroll");
      },
      /** How far down the pane the first drawn row that reads *needle* is. */
      rowTop: (needle) => rowReading(root, needle).getBoundingClientRect().top,
      /** The first drawn row whose box ends below the pane's top: how it reads, and its top. */
      rowAtTop() {
        const row = drawnRowsOf(root).find((each) => each.getBoundingClientRect().bottom > 0);
        assert(row !== undefined, "no row at the pane's top");
        return { reads: rowReads(row), top: row.getBoundingClientRect().top };
      },
      /** Focus on the chip *value* of the toolbar's chooser *group*. */
      focus(group, value) {
        toolbar.find(group)[0].querySelector(`[data-chip-value="${value}"]`).focus();
      },
      /** Where focus is: a toolbar chooser's drawn chip, or what is not one. */
      focused() {
        const active = page.activeElement;
        const control = toolbar
          .find("diff-toolbar-end")[0]
          .children.find((each) => each.children.includes(active));
        if (control === undefined) {
          return active === null ? "nothing" : "a chip no longer drawn";
        }
        const name = control.classList.contains("diff-layout-control")
          ? "Split | Unified"
          : "Comparison view";
        return `${name}'s ${active.textContent}`;
      },
      /**
       * A chip's click, as the chip family hands it to each handler bound around it: in the
       * toolbar's chooser *group*, or, with a *filePath*, in that file's bar.
       */
      async click(group, value, filePath = null) {
        const holder =
          filePath === null ? toolbar.find(group)[0] : sectionOf(filePath).find(group)[0];
        const chip = holder.querySelector(`[data-chip-value="${value}"]`);
        for (const record of binds) {
          if (record.bound && record.root.contains(chip)) {
            record.handlers.onChange(chip.chipKey, value, "one");
          }
        }
        await settle();
      },
      /** A key, as the registry runs it: its attachment's own activation. */
      async press(id) {
        key(id).options.activate();
        await settle();
      },
      keys: () => [keyAt("diff.show"), keyAt("diff.layout")],
      /** What a step shows, without the files' drawings. */
      brief(name, extra = {}) {
        assert(
          sections().every((section) => section.find("diff-show-control").length === 0),
          "a file bar holds a Diff | Excerpt | Full",
        );
        return {
          step: name,
          ...extra,
          shows: root.dataset.show,
          toolbar: toolbarNow(),
          keys: [keyAt("diff.show"), keyAt("diff.layout")],
          written: [...writes],
        };
      },
      line(name, extra = {}) {
        const files = {};
        for (const filePath of PATHS) {
          const now = drawing(sectionOf(filePath));
          const textOf = JSON.stringify(now);
          if (drawn.get(filePath) !== textOf) {
            drawn.set(filePath, textOf);
            files[filePath] = now;
          }
        }
        const ends = barEnds();
        const endsText = JSON.stringify(ends);
        const said = endsSaid === endsText ? {} : { "bar ends": ends };
        endsSaid = endsText;
        return { ...this.brief(name, extra), ...said, files };
      },
    };
  }

  const steps = [];

  // Changes, a commit's page or a patch, opened by a reader who never chose: Diff, as before
  // the presentation chooser. It sits before Split | Unified, and supported file bars
  // hold Rendered | Source.
  const diff = mount({ "diff.layout": "unified" });
  steps.push(diff.line("a reader who never chose opens Diff, today's view"));
  reveal();
  await settle();
  steps.push(
    diff.line("the rendered files arrive, their removed blocks, keys and entries among the rest"),
  );
  const attachedShow = diff.binds.length;

  // The toolbar is at the pane's top, above the first file; choosing there keeps that file
  // where it is.
  const first = diff.topOf("docs/guide.md");
  await diff.click("diff-show-control", "current");
  assert(
    diff.topOf("docs/guide.md") === first,
    `the first file moved to ${diff.topOf("docs/guide.md")} px`,
  );
  steps.push(
    diff.line(
      "Excerpt, chosen in the toolbar: every file shows its new version around the changes, stored as diff.show",
      {
        place: `the first file's bar ${first} px down before, ${diff.topOf("docs/guide.md")} px after`,
      },
    ),
  );

  await diff.click("diff-markdown-control", "source", "docs/guide.md");
  steps.push(
    diff.line("the Markdown file's Source in Excerpt: the new file's lines around the changes"),
  );
  await diff.click("diff-markdown-control", "rendered", "docs/guide.md");
  steps.push(diff.line("Rendered again keeps the comparison's Excerpt mode"));

  // Layout is Diff's: in Excerpt its chips say why, and neither they nor L change anything.
  await diff.click("diff-layout-control", "split");
  steps.push(diff.line("Split clicked in Excerpt: nothing changes, and nothing is written"));
  await diff.press("diff.layout");
  steps.push(diff.line("nor does L"));

  // N is the other chip of the toolbar's chooser, wherever the pane is. The reader is in
  // a.py, its bar 100 px down the pane under the end of the Markdown file, and the toolbar
  // is out of view; the block of the Markdown file at the pane's top keeps its place, while
  // Diff draws the removed blocks above it.
  diff.scrollTo("a.py", 100);
  await settle();
  const atTop = diff.rowAtTop();
  const bar = diff.topOf("docs/guide.md");
  steps.push(
    diff.line("a.py's bar 100 px down: N stays on the toolbar's chooser", {
      "pane's top": `${atTop.reads}, at ${atTop.top} px`,
    }),
  );
  await diff.press("diff.show");
  const kept = diff.rowTop(atTop.reads);
  assert(kept === atTop.top, `N moved the block at the pane's top to ${kept} px`);
  steps.push(
    diff.line("N: Diff again, stored, and the block at the pane's top keeps its place", {
      place: `${atTop.reads} is ${atTop.top} px from the pane's top before, ${kept} px after; the Markdown file's bar ${bar} px before, ${diff.topOf("docs/guide.md")} px after`,
    }),
  );
  diff.scrollTo("logo.png", 0);
  await settle();
  steps.push(diff.brief("logo.png at the pane's top: N has not moved"));

  // In a code file the row at the pane's top is a line. A removed line, which Excerpt leaves
  // out, gives its place to the next line Excerpt draws, which stays where it was. Diff again
  // keeps the line now at the pane's top, the one above it, and draws the removed line below.
  diff.scrollRowTo("    return 1", 0);
  await settle();
  const removed = diff.rowAtTop();
  const next = diff.rowTop("    x = 2");
  steps.push(
    diff.brief("a.py's removed line at the pane's top, in Diff", {
      "pane's top": `${removed.reads.trim()}, at ${removed.top} px`,
      "next line": `x = 2, at ${next} px`,
    }),
  );
  await diff.click("diff-show-control", "current");
  const nextInCurrent = diff.rowTop("    x = 2");
  assert(nextInCurrent === next, `Current moved the next line to ${nextInCurrent} px`);
  steps.push(
    diff.line("Excerpt: the next line it draws keeps its place", {
      place: `x = 2 is ${next} px from the pane's top before, ${nextInCurrent} px after`,
    }),
  );
  const currentTop = diff.rowAtTop();
  await diff.click("diff-show-control", "diff");
  const topInDiff = diff.rowTop(currentTop.reads);
  assert(topInDiff === currentTop.top, `Diff moved the line at the pane's top to ${topInDiff} px`);
  steps.push(
    diff.line("Diff again: the line at the pane's top keeps its place, the removed one below it", {
      place: `${currentTop.reads.trim()} is ${currentTop.top} px from the pane's top before, ${topInDiff} px after; the removed line at ${diff.rowTop("    return 1")} px`,
    }),
  );

  // Layout returns with Diff, and Excerpt is one column whatever the layout.
  pane.scrollTop = 0;
  pane.dispatch("scroll");
  await settle();
  await diff.click("diff-layout-control", "split");
  steps.push(diff.line("Split chosen in Diff"));
  // Focus on the layout chooser, N redraws it for Excerpt; focus stays on its chosen chip.
  diff.focus("diff-layout-control", "split");
  await diff.press("diff.show");
  assert(
    diff.focused() === "Split | Unified's Split",
    `focus left the layout chooser: ${diff.focused()}`,
  );
  steps.push(
    diff.line("Excerpt from Split, by N with focus on Split: one column, the layout kept", {
      focus: diff.focused(),
    }),
  );
  await diff.click("diff-show-control", "diff");
  steps.push(diff.line("Diff: Split again"));

  diff.handle.dispose();
  assert(
    diff.binds.slice(0, attachedShow).every((record) => !record.bound),
    "dispose left a chooser bound",
  );
  steps.push({
    step: "disposed: every chooser's listener is unbound, and N and L are detached",
    keys: diff.keys(),
    bound: diff.binds.filter((record) => record.bound).length,
  });

  // A pull request's Docs tab: the layout fixed, so its toolbar holds only the presentation
  // chooser, with Full as its default.
  const docs = mount({ "diff.layout": "split" }, DOCS);
  reveal();
  await settle();
  steps.push(docs.line("Docs, never chosen there: Full, its default, with no layout control"));
  docs.handle.dispose();

  // Each surface keeps its own choice. One reader's store, across Changes and Docs:
  const store = new Map();
  const changes1 = mount(store);
  await changes1.click("diff-show-control", "current");
  steps.push(changes1.brief("Changes: Excerpt chosen, stored as diff.show"));
  changes1.handle.dispose();
  const docs1 = mount(store, DOCS);
  steps.push(docs1.brief("Docs opens on its own default, Full, which Changes did not set"));
  await docs1.click("diff-show-control", "diff");
  steps.push(docs1.brief("Docs: Diff chosen, stored as github.docs.show"));
  docs1.handle.dispose();
  const changes2 = mount(store);
  steps.push(changes2.brief("Changes again: Excerpt, its own choice, which Docs did not move"));
  changes2.handle.dispose();
  const docs2 = mount(store, DOCS);
  steps.push(docs2.brief("Docs again: Diff, its own choice"));
  docs2.handle.dispose();
  steps.push({ step: "what the store holds", stored: Object.fromEntries(store) });

  // A stored value that is not a choice reads as the surface's default, and is not rewritten.
  const odd = mount({ "diff.show": "both" });
  steps.push(odd.brief("Changes, a stored value that is not a choice: Diff, its default"));
  odd.handle.dispose();
  const oddDocs = mount({ "github.docs.show": "both" }, DOCS);
  steps.push(oddDocs.brief("Docs, a stored value that is not a choice: Full, its default"));
  oddDocs.handle.dispose();

  const codeLines = [
    "# Before the first hunk",
    "",
    "def f():",
    "    x = 2",
    "    return x",
    "",
    "# After the last hunk",
  ];
  const requests = [];
  view.setGapLoader(async (_revision, path, ask) => {
    assert(ask.whole === true, "Full reads one bounded complete side");
    requests.push(path);
    return {
      comparison_id: comparison.resolved.comparison_id,
      path,
      start: 1,
      lines: codeLines,
      line_count: codeLines.length,
      ends_with_newline: true,
    };
  });
  const full = mount({ "diff.layout": "split" });
  reveal();
  await settle();
  await full.click("diff-show-control", "full");
  reveal();
  await settle();
  assert(requests.includes("a.py"), "Full asked for the source at the comparison");
  assert(
    full.rowTop("# Before the first hunk") < full.rowTop("# After the last hunk"),
    "Full draws lines outside the patch",
  );
  steps.push(full.line("Full source includes lines before and after the hunks"));
  await full.click("diff-show-control", "current");
  assert(
    !drawnRowsOf(full.root).some((row) => rowReads(row).includes("Before the first hunk")),
    "Excerpt returns to the lines in the patch",
  );
  full.handle.dispose();

  console.log(JSON.stringify({ steps }, null, 2));
  finished = true;
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
