// Browserless session: a changed YAML or JSON file's Rendered view in a pull request's
// Changes, through the production code: builtin_plugins/diff/diff-structured.js, the
// views of diff-markdown.js (`createMarkdownViews`), and the structured plugin's own
// preview.js and tree.js. It covers which rows a merged tree has, which open first, what
// a click opens, closes or pages in, how a row is marked, and the page around the tree:
// the chooser, a refusal falling back to Source, a missing tree renderer, and disposal.
//
// The trees in the transcript are the server's, recorded in
// tests/fixtures/diff-structured-responses.json by tests/test_diff_structured_session.py;
// the focused checks below build their own. The page is a small element tree that records
// what the production code builds. The only markup it reads is a tree's rows, which it
// parses back into one element per row and refuses anything else, so a check that rows
// are replaced and not rebuilt compares the elements themselves. Prints the transcript
// tests/golden/cli-ui-diff-structured.tryscript.md pins.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = process.argv[2] ?? path.resolve(__dirname, "../..");
const plugins = path.join(root, "src/metabrowser/builtin_plugins");
const recording = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/diff-structured-responses.json"), "utf8"),
);

// The tree helpers are classic scripts that publish on the global object, read here as
// the page reads them from the structured plugin's exports (`mb.plugins.load`).
require(path.join(plugins, "structured/preview.js"));
require(path.join(plugins, "structured/tree.js"));
const tree = globalThis.__structuredTree;
const preview = globalThis.__structuredPreview;
const helpers = {
  materializeRows: tree.materializeRows,
  renderRowHtml: tree.renderRowHtml,
  calculateOptimalExpansion: preview.calculateOptimalExpansion,
  expansion: tree.expansion,
};

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
    assert.equal(match.index, consumed, `a tree's markup holds only rows: ${html.slice(consumed)}`);
    consumed = match.index + match[0].length;
    const row = element("div");
    row.className = match[1];
    row.setAttribute("data-path", unescapeHtml(match[2]));
    row.setAttribute("style", match[3]);
    row.inner = match[4];
    built.push(row);
  }
  assert.equal(consumed, html.length, `a tree's markup holds only rows: ${html.slice(consumed)}`);
  return built;
}

const page = { activeElement: null };

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
    this.hidden = false;
    this.open = false;
    this.disabled = false;
    this.text = "";
    this.id = "";
    this.inner = "";
  }

  get children() {
    return this.childNodes.filter((node) => node.nodeType === 1);
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
      const node = new PageElement("#text");
      node.text = String(value);
      this.append(node);
    }
  }

  get nextElementSibling() {
    const siblings = this.parentElement?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
  }

  append(...nodes) {
    for (const node of nodes) {
      node.remove();
      node.parentElement = this;
      this.childNodes.push(node);
    }
  }

  replaceChildren(...nodes) {
    for (const node of this.childNodes) {
      node.parentElement = null;
    }
    this.childNodes = [];
    this.append(...nodes);
  }

  #insert(offset, nodes) {
    const parent = this.parentElement;
    for (const node of nodes) {
      node.remove();
      node.parentElement = parent;
    }
    parent.childNodes.splice(parent.childNodes.indexOf(this) + offset, 0, ...nodes);
  }

  after(...nodes) {
    this.#insert(1, nodes);
  }

  before(...nodes) {
    this.#insert(0, nodes);
  }

  prepend(...nodes) {
    for (const node of nodes) {
      node.remove();
      node.parentElement = this;
    }
    this.childNodes.unshift(...nodes);
  }

  remove() {
    const parent = this.parentElement;
    if (parent !== null) {
      parent.childNodes.splice(parent.childNodes.indexOf(this), 1);
      this.parentElement = null;
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

  addEventListener(name, listener) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), listener]);
  }

  removeEventListener(name, listener) {
    this.listeners.set(
      name,
      (this.listeners.get(name) ?? []).filter((each) => each !== listener),
    );
  }

  contains(node) {
    for (let at = node; at; at = at.parentElement) {
      if (at === this) {
        return true;
      }
    }
    return false;
  }

  closest(selector) {
    for (let at = this; at; at = at.parentElement) {
      const wanted = selector.startsWith(".")
        ? at.classList.contains(selector.slice(1))
        : selector === "a[href]" && at.tagName === "A" && at.getAttribute("href") !== null;
      if (wanted) {
        return at;
      }
    }
    return null;
  }

  focus() {
    page.activeElement = this;
  }

  // Markup is written in two places only: the chip family's chooser, as the shared
  // stand-in below spells it, and a tree's rows.
  set innerHTML(spec) {
    if (typeof spec === "object") {
      this.replaceChildren(
        ...spec.options.map((option) => {
          const chip = element("button");
          chip.dataset.chipValue = option.value;
          chip.textContent = option.label;
          chip.setAttribute("aria-checked", String(spec.value === option.value));
          return chip;
        }),
      );
      this.label = spec.label;
      return;
    }
    assert.ok(this.classList.contains("tree-viewport"), `markup written into ${this.tagName}`);
    this.replaceChildren(...parseRows(spec));
  }

  insertAdjacentHTML(position, html) {
    const rows = parseRows(html);
    if (position === "beforebegin") {
      this.before(...rows);
    } else {
      assert.equal(position, "beforeend");
      assert.ok(this.classList.contains("tree-viewport"), "rows go into a tree's viewport");
      this.append(...rows);
    }
  }

  querySelectorAll(selector) {
    assert.equal(selector, "button[data-chip-value]");
    return this.children.filter((child) => child.dataset.chipValue !== undefined);
  }
}

const element = (tag) => new PageElement(tag);
page.createElement = element;
globalThis.document = page;

// The views' observer of files near the viewport; the other, of chunks of rendered
// Markdown not drawn yet, looks above as well as below, and no tree file has one.
let observer;
globalThis.IntersectionObserver = class {
  constructor(notify, options) {
    if (options.rootMargin.startsWith("0px ")) {
      observer = this;
    }
    this.notify = notify;
    this.options = options;
    this.observed = [];
  }

  observe(target) {
    this.observed.push(target);
  }

  disconnect() {
    this.observed = [];
  }
};

/** A click on *target*, heard by it and each element it is in, as an event bubbles. */
function click(target) {
  const event = { type: "click", target };
  for (let at = target; at; at = at.parentElement) {
    for (const listener of at.listeners.get("click") ?? []) {
      listener(event);
    }
  }
}

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

// ── What a step prints ──────────────────────────────────────────────────────

/** A row's text as a reader sees it: its key and value, without its screen-reader label. */
function visible(inner) {
  return unescapeHtml(
    inner
      .replace(/<span class="sr-only">[^<]*<\/span>/g, "")
      .replace(/<span class="srow-chevron[^"]*"[^>]*>[^<]*<\/span>/g, "")
      .replace(/<[^>]+>/g, ""),
  ).trim();
}

/** A drawn row: its level, change, state and text. */
function line(row) {
  const indent = Number.parseFloat(/padding-left:([\d.]+)em/.exec(row.getAttribute("style"))[1]);
  const level = indent / (tree.expansion.indentChars * 0.5);
  const names = row.classList.names;
  const change = names.find((name) => name.startsWith("srow-change-"))?.slice(12) ?? "context";
  const state = names.includes("srow-more")
    ? "more"
    : names.includes("srow-container")
      ? names.includes("srow-expanded")
        ? "open"
        : "closed"
      : names.includes("srow-empty")
        ? "empty"
        : "leaf";
  return `${"  ".repeat(level)}${change} ${state} ${visible(row.inner)}`;
}

/** What a mounted tree draws: its note, if it has one, and its rows. */
function drawn(container) {
  const lines = [];
  for (const node of container.children) {
    if (node.tagName === "P") {
      lines.push(`note: ${node.textContent}`);
    } else {
      assert.ok(node.classList.contains("tree-viewport"), `a tree holds ${node.tagName}`);
      lines.push(...node.children.map(line));
    }
  }
  return lines;
}

function rowsOf(container) {
  return container.children.find((node) => node.classList.contains("tree-viewport")).children;
}

/** The first drawn row whose text starts with *text*. */
function rowNamed(container, text) {
  const found = rowsOf(container).find((row) => visible(row.inner).startsWith(text));
  assert.ok(found, `no row reads ${text}`);
  return found;
}

// ── The story ───────────────────────────────────────────────────────────────

async function main() {
  const structured = await import(
    pathToFileURL(path.join(plugins, "diff/diff-structured.js")).href
  );
  const markdown = await import(pathToFileURL(path.join(plugins, "diff/diff-markdown.js")).href);
  const { ROW_BUDGET, PAGE, diffRows, initialExpansion, isStructuredProjection } = structured;
  const { mountStructuredDiff } = structured;

  const steps = [];
  const clock = { now: () => 0, later: () => 0, cancel: () => {} };
  const controls = { groupHtml: (spec) => spec, bind: () => () => {} };

  /**
   * Mount *names* through the page's views, as a pull request's Changes does, with
   * *ensureStructured* for the tree renderer, and draw the first screen.
   */
  async function mount(names, ensureStructured) {
    const requests = [];
    const asked = { structured: 0 };
    const views = markdown.createMarkdownViews({
      controls,
      load: async (fileId) => {
        requests.push(fileId);
        return structuredClone(recording[fileId]);
      },
      ensureInert: async () => undefined,
      ensureStructured: async () => {
        asked.structured += 1;
        return ensureStructured();
      },
      loadStyles: async () => {},
      mutate: (change) => change(),
      ...clock,
    });
    const diff = element("div");
    const files = names.map((name) => {
      const format = markdown.renderedFormat({
        availability: "ready",
        new: { entry_type: "file", path: name },
      });
      const section = element("section");
      const bar = element("div");
      const toggle = element("button");
      const end = element("div");
      bar.append(toggle, end);
      const source = element("div");
      source.id = `diff-file-${name}`;
      section.append(bar, source);
      diff.append(section);
      views.add({ section, bar, end, toggle, source, id: name, format });
      const [, control] = end.childNodes;
      const [, , rendered] = section.childNodes;
      return { name, section, bar, source, control, rendered };
    });
    await settle();
    const before = asked.structured;
    views.observe(diff, null);
    observer.notify(files.map((file) => ({ target: file.section, isIntersecting: true })));
    await settle();
    return { views, files, requests, asked, before };
  }

  /** A file as a step prints it: its chooser, what its body shows, and its rows. */
  function describe(file) {
    const chips = file.control.children.map(
      (chip) => `${chip.getAttribute("aria-checked") === "true" ? "*" : ""}${chip.textContent}`,
    );
    const shows = !file.rendered.hidden ? "rendered" : !file.source.hidden ? "source" : "nothing";
    return {
      chooser: file.control.hidden ? "none" : `${file.control.label}: ${chips.join(" | ")}`,
      shows,
      ...(shows === "rendered" ? { rows: drawn(file.rendered) } : {}),
    };
  }

  const names = Object.keys(recording);
  const page1 = await mount(names, async () => helpers);
  steps.push({
    step: "the first screen: each file asked for in turn, and a tree's renderer once",
    "renderer asked before the first answer": page1.before,
    "renderer asked in all": page1.asked.structured,
    requests: page1.requests,
    files: Object.fromEntries(page1.files.map((file) => [file.name, describe(file)])),
  });
  assert.equal(page1.before, 1, "the tree's renderer is asked for when its file is added");
  assert.equal(page1.asked.structured, 1, "every load awaits the one request for it");

  const config = page1.files.find((file) => file.name === "config/app.yaml");
  const show = (step) => steps.push({ step, rows: drawn(config.rendered) });

  page1.views.show("current");
  const excerpt = drawn(config.rendered);
  assert(excerpt.some((line) => line.includes("db: removed")));
  assert(!excerpt.some((line) => line.includes("postgres") || line.includes("flags")));
  show("Excerpt keeps changed paths and a marker for removed values");
  page1.views.show("full");
  const full = drawn(config.rendered);
  assert(full.some((line) => line.includes("flags")));
  assert(!full.some((line) => line.includes("db:")));
  show("Full includes unchanged values in the new tree");
  page1.views.show("diff");

  // A click replaces only the rows of the container it changes: the rows above it and
  // below its subtree are the same elements.
  const keep = (from) => rowsOf(config.rendered).filter((row) => !from.includes(row));
  let before = rowsOf(config.rendered);
  click(rowNamed(config.rendered, "flags"));
  show("a click on a closed unchanged list opens it, as the file view's tree does");
  const after = rowsOf(config.rendered);
  assert.equal(after.length, before.length + 2);
  assert.equal(
    after.filter((row) => before.includes(row)).length,
    before.length - 1,
    "only the clicked row is drawn again; every other row is the element it was",
  );

  before = rowsOf(config.rendered);
  click(rowNamed(config.rendered, "services"));
  show("a click on an open modified mapping closes it, previewing its new side");
  assert.ok(
    before.indexOf(rowNamed(config.rendered, "flags")) >= 0,
    "the rows below the closed mapping are the elements they were",
  );
  assert.equal(keep(before).length, 1, "the closed row is the one row drawn again");

  click(rowNamed(config.rendered, "services"));
  show("opened again, it keeps open what was open inside it");

  // A refusal and a missing renderer both show Source: a refusal is a file that can only
  // show Source and loses its chooser, and a renderer that failed to load keeps it, so
  // choosing Rendered asks again.
  const warnings = [];
  const warn = console.warn;
  console.warn = (...args) => warnings.push(String(args[0]));
  const page2 = await mount(["config/app.yaml"], async () => undefined);
  console.warn = warn;
  steps.push({
    step: "a tree renderer that failed to load leaves the file in Source, its chooser kept",
    files: Object.fromEntries(page2.files.map((file) => [file.name, describe(file)])),
    warnings,
  });
  page2.views.dispose();

  // Disposal takes the trees' listeners with it: a click on a row does nothing.
  const viewport = config.rendered.children.find((node) =>
    node.classList.contains("tree-viewport"),
  );
  page1.views.dispose();
  const disposedRows = drawn(config.rendered);
  click(rowNamed(config.rendered, "flags"));
  assert.deepEqual(drawn(config.rendered), disposedRows, "a disposed tree does not redraw");
  steps.push({
    step: "disposal removes each tree's click listener",
    listeners: (viewport.listeners.get("click") ?? []).length,
  });

  checks({
    markdown,
    ROW_BUDGET,
    PAGE,
    diffRows,
    initialExpansion,
    isStructuredProjection,
    mountStructuredDiff,
  });
  process.stdout.write(
    `${JSON.stringify({ "row budget": ROW_BUDGET, page: PAGE, steps }, null, 2)}\n`,
  );
}

// ── Focused checks ──────────────────────────────────────────────────────────

function checks({
  markdown,
  ROW_BUDGET,
  PAGE,
  diffRows,
  initialExpansion,
  isStructuredProjection,
  mountStructuredDiff,
}) {
  // As the server answers `name: demo / version: 3 / services: {...}` changed to bump
  // the version, add a port, and drop `db`.
  const projection = {
    version: "structured-diff-v1",
    status: "ready",
    format: "yaml",
    source_only: false,
    root: [
      {
        change: "modified",
        type: "map",
        entries: [
          { key: "name", change: "context", value: "demo" },
          { key: "version", change: "removed", value: 3 },
          { key: "version", change: "added", value: 4 },
          {
            key: "services",
            change: "modified",
            type: "map",
            entries: [
              {
                key: "web",
                change: "modified",
                type: "map",
                entries: [
                  { key: "image", change: "context", value: "nginx" },
                  {
                    key: "ports",
                    change: "modified",
                    type: "list",
                    entries: [
                      { change: "context", value: 80 },
                      { change: "added", value: 443 },
                    ],
                  },
                ],
              },
              { key: "db", change: "removed", value: { image: "postgres", port: 5432 } },
            ],
          },
          { key: "flags", change: "context", value: ["fast", "safe"] },
        ],
      },
    ],
  };

  // What is admitted: a ready tree, with a number's text a string. Not a refusal, which
  // is always this version's, nor a Markdown file's answer.
  assert.ok(isStructuredProjection(projection), "the server's answer is admitted");
  assert.ok(
    !isStructuredProjection({ ...projection, root: [{ change: "modified", type: "map" }] }),
    "a modified entry without entries is not",
  );
  assert.ok(!isStructuredProjection({ ...projection, status: "unsupported" }));
  assert.ok(
    !isStructuredProjection({
      version: "structured-diff-v1",
      status: "too_large",
      root: [],
      source_only: false,
    }),
    "a refusal is not",
  );
  assert.ok(
    !isStructuredProjection({
      version: "markdown-diff-v1",
      status: "ready",
      blocks: [],
      source_only: false,
    }),
    "a Markdown file's answer is not",
  );
  const big = { key: "big", change: "added", value: 1e16, text: "1e+16" };
  assert.ok(isStructuredProjection({ ...projection, root: [big] }));
  assert.ok(
    !isStructuredProjection({ ...projection, root: [{ ...big, text: 1e16 }] }),
    "a number's text is a string",
  );

  // Paths are positions: a removed key and its added successor have their own.
  const open = initialExpansion(projection.root, helpers);
  assert.deepEqual([...open].sort(), ["$", "$/3", "$/3/0", "$/3/0/1", "$/3/1"]);
  const rowLine = (row) =>
    `${"  ".repeat(row.level)}${row.change} ${row.kind} ${row.key ?? (row.isArrayIndex ? "-" : "$")}`;
  const rows = diffRows(projection.root, open, helpers);
  assert.deepEqual(rows.map(rowLine), [
    "modified open $",
    "  context kv name",
    "  removed kv version",
    "  added kv version",
    "  modified open services",
    "    modified open web",
    "      context kv image",
    "      modified open ports",
    "        context item -",
    "        added item -",
    "    removed open db",
    "      removed kv image",
    "      removed kv port",
    "  context open flags",
  ]);
  assert.deepEqual(
    rows.map((row) => row.path),
    [
      "$",
      "$/0",
      "$/1",
      "$/2",
      "$/3",
      "$/3/0",
      "$/3/0/0",
      "$/3/0/1",
      "$/3/0/1/0",
      "$/3/0/1/1",
      "$/3/1",
      "$/3/1/0",
      "$/3/1/1",
      "$/4",
    ],
  );
  assert.equal(rows[4].childCount, 1, "a modified mapping counts the keys its new side holds");
  // Current: the same tree without its removed entries, at the merged tree's paths, so
  // what is open in Diff is open in Current.
  const currentRows = diffRows(projection.root, open, helpers, new Map(), true);
  assert.deepEqual(currentRows.map(rowLine), [
    "modified open $",
    "  context kv name",
    "  added kv version",
    "  modified open services",
    "    modified open web",
    "      context kv image",
    "      modified open ports",
    "        context item -",
    "        added item -",
    "  context open flags",
  ]);
  assert.deepEqual(
    currentRows.map((row) => row.path),
    ["$", "$/0", "$/2", "$/3", "$/3/0", "$/3/0/0", "$/3/0/1", "$/3/0/1/0", "$/3/0/1/1", "$/4"],
  );
  // A page counts what draws: Current draws a full page past a removed entry, and its
  // "more" row counts only the entries Current would draw.
  const paged = [
    {
      change: "modified",
      type: "map",
      entries: [
        { key: "gone", change: "removed", value: 0 },
        ...Array.from({ length: PAGE }, (_, index) => ({
          key: `k${index}`,
          change: "context",
          value: index,
        })),
        { key: "old", change: "removed", value: 1 },
        { key: "new", change: "added", value: 2 },
      ],
    },
  ];
  const pagedMore = (current) => {
    const all = diffRows(paged, new Set(["$"]), helpers, new Map(), current);
    const more = all.at(-1);
    return [all.length, more.kind, more.hidden, more.changed];
  };
  assert.deepEqual(pagedMore(false), [1 + PAGE + 1, "more", 3, 2]);
  assert.deepEqual(pagedMore(true), [1 + PAGE + 1, "more", 1, 1]);
  open.delete("$/3");
  const closed = diffRows(projection.root, open, helpers).find((row) => row.path === "$/3");
  assert.deepEqual(closed.value, { web: { image: "nginx", ports: [80, 443] } });

  // Rows are the tree view's own, marked for the change gutter and for screen readers.
  const removed = tree.renderRowHtml(rows[2], 2);
  assert.match(removed, /class="srow srow-change-removed"/);
  assert.match(
    removed,
    /<span class="sr-only">Removed: <\/span><span class="tok-key">version<\/span>/,
  );
  assert.match(
    tree.renderRowHtml(rows[9], 2),
    /Added: <\/span><span class="tok-punct">- <\/span><span class="tok-number">443/,
  );
  const modified = tree.renderRowHtml(rows[0], 2);
  assert.match(modified, /srow-container disclosure-toggle srow-expanded srow-change-modified/);
  assert.doesNotMatch(modified, /sr-only/, "a modified container is announced by its rows");
  const { change: _ignored, ...plain } = rows[1];
  assert.equal(tree.renderRowHtml(rows[1], 2), tree.renderRowHtml(plain, 2));

  // D7: a mapping that is an item of a modified list reads `- `; inside a whole value an
  // item keeps its index, as the file view draws it.
  const items = [
    {
      change: "modified",
      type: "list",
      entries: [
        { change: "modified", type: "map", entries: [{ key: "a", change: "added", value: 1 }] },
        { change: "added", value: [{ b: 1 }] },
      ],
    },
  ];
  const itemRows = diffRows(items, initialExpansion(items, helpers), helpers);
  assert.deepEqual(
    itemRows.map((row) => visible(tree.renderRowHtml(row, 2))),
    ["[2 items]", "- {1 keys}", "a: 1", "- [1 items]", "0: {1 keys}", "b: 1"],
  );

  // A7: a number's JSON text is drawn in place of the value a double keeps.
  const bigRow = diffRows([big], new Set(), helpers)[0];
  assert.match(tree.renderRowHtml(bigRow, 2), /<span class="tok-number">1e\+16<\/span>/);
  const wide = { change: "added", key: "id", value: 2 ** 64, text: "18446744073709551616" };
  assert.match(
    tree.renderRowHtml(diffRows([wide], new Set(), helpers)[0], 2),
    />18446744073709551616</,
  );

  // B6: keys and values are text. Every row's markup holds the row's own tags and
  // attributes and nothing a key or value wrote.
  const hostile = '<img src=x onerror="alert(1)">';
  const quoted = `"double" and 'single'`;
  const tricky = [
    {
      change: "modified",
      type: "map",
      entries: [
        { key: hostile, change: "removed", value: quoted },
        { key: hostile, change: "added", value: hostile },
        { key: "__proto__", change: "added", value: { [hostile]: { [quoted]: hostile } } },
        { key: quoted, change: "context", value: { __proto__: null, [hostile]: [quoted] } },
      ],
    },
  ];
  const trickyOpen = initialExpansion(tricky, helpers);
  trickyOpen.add("$/3");
  const markup = diffRows(tricky, trickyOpen, helpers).map((row) => tree.renderRowHtml(row, 2));
  const ATTRIBUTES = new Set(["class", "data-path", "style", "aria-hidden"]);
  for (const html of markup) {
    let rest = html;
    for (const tag of html.matchAll(/<(\/?)([a-z]+)([^>]*)>/g)) {
      assert.ok(["div", "span"].includes(tag[2]), `a row writes <${tag[2]}>`);
      const attributes = tag[3].replace(/ ([a-z-]+)="[^"<>]*"/g, (_all, name) => {
        assert.ok(ATTRIBUTES.has(name), `a row writes the attribute ${name}`);
        return "";
      });
      assert.equal(attributes, "", `a row's tag holds ${attributes}`);
      rest = rest.replace(tag[0], "");
    }
    assert.doesNotMatch(rest, /[<>"]/, "a key or value reaches the markup unescaped");
  }
  assert.ok(
    markup.some((html) => visible(html).includes(hostile)),
    "and a reader sees the text as written",
  );
  // Front matter is set as text: the same content through frontmatterRow writes no markup
  // (the page refuses markup outside a tree) and reads back as written.
  const frontmatter = markdown.frontmatterRow({
    change: "modified",
    entries: [
      { key: hostile, change: "removed", text: quoted },
      { key: "__proto__", change: "added", text: hostile },
      { key: quoted, change: "context", text: hostile },
    ],
  });
  const [details] = frontmatter.children;
  const [, list] = details.children;
  assert.deepEqual(
    list.children.filter((node) => !node.hidden).map((node) => node.textContent),
    [`Removed: ${hostile}`, quoted, `Added: __proto__`, hostile, quoted, hostile],
  );

  // B1 and A14: a long key above many rows is written once, and no path grows with it.
  const longKey = "k".repeat(20_000);
  const longValue = Array.from({ length: 1_000 }, (_, index) => index);
  const long = [
    {
      change: "modified",
      type: "map",
      entries: [{ key: longKey, change: "added", value: longValue }],
    },
  ];
  const longHost = element("div");
  mountStructuredDiff(longHost, long, helpers);
  click(rowNamed(longHost, longKey));
  const longRows = rowsOf(longHost);
  assert.equal(longRows.length, 2 + PAGE + 1, "the value draws a page and a more row");
  const written = longRows.map((row) => row.getAttribute("data-path") + row.inner).join("");
  assert.equal(written.split(longKey).length - 1, 1, "the long key is written once");
  assert.ok(
    longRows.every((row) => row.getAttribute("data-path").length <= 10),
    "a path is as long as the tree is deep",
  );

  // A5: a draw is bounded. A whole value's root opens only when the file view would
  // open it; an open container draws a page, and its "more" row the next one.
  const huge = [{ change: "added", value: Array.from({ length: 39_000 }, (_, index) => index) }];
  const hugeHost = element("div");
  mountStructuredDiff(hugeHost, huge, helpers);
  assert.deepEqual(drawn(hugeHost).length, 1, "a root past the file view's threshold stays closed");
  click(rowsOf(hugeHost)[0]);
  assert.equal(rowsOf(hugeHost).length, 1 + PAGE + 1);
  assert.match(drawn(hugeHost).at(-1), new RegExp(`^  added more … ${39_000 - PAGE} more$`));
  const firstPage = rowsOf(hugeHost).slice(0, -1);
  click(rowsOf(hugeHost).at(-1));
  assert.equal(rowsOf(hugeHost).length, 1 + 2 * PAGE + 1, "a more row draws the next page");
  assert.ok(
    firstPage.every((row, index) => rowsOf(hugeHost)[index] === row),
    "and replaces only itself",
  );
  click(rowsOf(hugeHost)[0]);
  assert.equal(rowsOf(hugeHost).length, 1, "closing removes every page");
  click(rowsOf(hugeHost)[0]);
  assert.equal(rowsOf(hugeHost).length, 1 + 2 * PAGE + 1, "and reopening keeps the pages shown");

  // A mounted tree switches to Current and back, keeping what the reader opened: a removed
  // entry's rows go, and come back where they were.
  const switchHost = element("div");
  const switching = mountStructuredDiff(switchHost, projection.root, helpers);
  const diffDrawn = drawn(switchHost);
  switching.setCurrent(true);
  const currentDrawn = drawn(switchHost);
  assert.equal(diffDrawn.length - currentDrawn.length, 4, "a removed key and a removed mapping");
  assert.ok(
    currentDrawn.every((row) => !row.includes("removed")),
    currentDrawn.join("\n"),
  );
  switching.setCurrent(false);
  assert.deepEqual(drawn(switchHost), diffDrawn);
  const openedHost = element("div");
  const opening = mountStructuredDiff(openedHost, projection.root, helpers, { current: true });
  assert.deepEqual(drawn(openedHost), currentDrawn, "a tree can open in Current");
  opening.dispose();
  switching.dispose();

  // Many whole values under one modified mapping: its first page of entries, then the
  // values open in order while the first draw stays within its budget.
  const many = [
    {
      change: "modified",
      type: "map",
      entries: Array.from({ length: 1_998 }, (_, index) => ({
        key: `k${index}`,
        change: index % 2 ? "added" : "context",
        value: Array.from({ length: 19 }, (_unused, item) => item),
      })),
    },
  ];
  const manyHost = element("div");
  mountStructuredDiff(manyHost, many, helpers);
  const manyRows = drawn(manyHost);
  assert.ok(manyRows.length <= ROW_BUDGET, `the first draw is ${manyRows.length} rows`);
  assert.match(
    manyRows.at(-1),
    new RegExp(`^  modified more … ${1_998 - PAGE} more, ${(1_998 - PAGE) / 2} changed$`),
    "a modified mapping's more row counts the changes it holds",
  );
  assert.ok(manyRows.includes("  added open k1: [19 items]"), "the first added value opens");
  assert.ok(
    manyRows.some((row) => row.startsWith(`  added closed k${PAGE - 1}: [0, 1, 2`)),
    "and a value past the budget stays closed",
  );

  // Every recorded first draw is within the budget, and the source-only answer notes it.
  for (const answer of Object.values(recording)) {
    if (isStructuredProjection(answer)) {
      const host = element("div");
      mountStructuredDiff(host, answer.root, helpers, { sourceOnly: answer.source_only });
      assert.ok(rowsOf(host).length <= ROW_BUDGET);
      assert.equal(host.children[0].tagName === "P", answer.source_only);
    }
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
