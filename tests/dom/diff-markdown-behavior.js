const assert = require("node:assert/strict");
const fs = require("node:fs");
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
    this.style = {};
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

  prepend(...children) {
    for (const child of children) {
      child.parent = this;
    }
    this.children.unshift(...children);
  }

  replaceChildren(...children) {
    this.children = [];
    this.append(...children);
  }

  // A fragment (`createDocumentFragment`, an element with no tag) puts its children in
  // its place.
  replaceWith(...nodes) {
    const siblings = this.parent.children;
    const placed = nodes.flatMap((node) => (node.tagName === "" ? node.children : [node]));
    for (const node of placed) {
      node.parent = this.parent;
    }
    siblings.splice(siblings.indexOf(this), 1, ...placed);
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  get firstElementChild() {
    return this.children[0];
  }

  get previousElementSibling() {
    const siblings = this.parent?.children ?? [];
    return siblings[siblings.indexOf(this) - 1] ?? null;
  }

  get nextElementSibling() {
    const siblings = this.parent?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
  }

  remove() {
    if (this.parent) {
      this.parent.children.splice(this.parent.children.indexOf(this), 1);
      this.parent = null;
    }
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
    this.listeners.get("click")({ target: this, stopPropagation() {}, preventDefault() {} });
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
    this.children = spec.options.map(({ value, tip }) => {
      const chip = make("button");
      chip.dataset.chipValue = value;
      if (tip !== undefined) {
        chip.dataset.tipText = tip;
      }
      chip.setAttribute("aria-checked", String(spec.value === value));
      chip.addEventListener("click", () => {
        for (const [container, onChange] of bound) {
          if (container.contains(chip)) {
            onChange(spec.key, value, spec.select);
          }
        }
      });
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
// The chip family's `bind`: a bound element's handler hears the chips inside it. The layer
// binds each file's chooser by itself, never the diff around them, whose toolbar holds
// another control's dropdown (mb-yn7w).
/** @type {Map<Element, (key: string, value: string, select: string) => void>} */
const bound = new Map();
function bindChooser(container, { onChange }) {
  assert.equal(container.className, "diff-markdown-control", "a chooser is bound by itself");
  bound.set(container, onChange);
  return () => bound.delete(container);
}
// The page's address, which KPress's stylesheets are resolved against (kpressStylesheets).
const PAGE = "http://127.0.0.1:8000/pull/1/files";
globalThis.document = {
  baseURI: PAGE,
  createElement: make,
  createTextNode: (textContent) => ({ textContent }),
  createDocumentFragment: make,
  implementation: { createHTMLDocument: () => ({ createElement: make }) },
};

// The latest views' observers: of files near the viewport, and of chunks not drawn yet.
let observer;
let chunkObserver;
globalThis.IntersectionObserver = class {
  constructor(notify, options) {
    if (options.rootMargin.startsWith("0px ")) {
      observer = this;
    } else {
      chunkObserver = this;
    }
    this.notify = notify;
    this.options = options;
    this.observed = new Set();
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

// An article's rows in order: a changed row is in its change's run (`changeRuns`).
function blockRows(node) {
  return node.children.flatMap((child) =>
    child.classList.contains("diff-markdown-change") ||
    child.classList.contains("diff-markdown-run")
      ? blockRows(child)
      : [child],
  );
}

async function main() {
  const {
    blockOf,
    blockRow,
    changeRuns,
    chunkUnits,
    createMarkdownViews,
    WAITING_CLASS,
    estimatedHeight,
    foldBlocks,
    projectionModel,
    viewUnits,
    firstScreenRendered,
    kpressStylesheets,
    markdownTargets,
    refusalReason,
    renderedFormat,
    supportsRenderedChange,
  } = await import(pathToFileURL(path.join(plugin, "diff-markdown.js")));
  // Which of a projection's stylesheets the page loads: same-origin KPress CSS, by the
  // address the browser resolves, whatever characters the server's stamp and KPress's
  // PEP 440 version put in its segments. Each one left out is named in a warning.
  {
    const kept = [
      // A release, unstamped and stamped.
      "/kpress-static/v0.3.9/css/document.css",
      "/kpress-static/@a009bfcd7946408c/v0.3.9/css/document.css",
      // An editable or development KPress: a local version segment.
      "/kpress-static/@a009bfcd7946408c/v0.3.10.dev10+5c60a81/css/document.css",
      // The rest of what PEP 440 allows: an epoch, a pre-release, a post-release.
      "/kpress-static/@a009bfcd7946408c/v1!0.4.0rc1.post2/css/document.css",
      // The page's own origin, written out.
      "http://127.0.0.1:8000/kpress-static/v0.3.9/css/print.css",
    ];
    const dropped = [
      "https://elsewhere.example/kpress-static/v0.3.9/css/document.css",
      "//elsewhere.example/kpress-static/v0.3.9/css/document.css",
      "http://127.0.0.1:9000/kpress-static/v0.3.9/css/document.css",
      // Out of KPress's route once the path is normalized.
      "/kpress-static/../static/styles.css",
      "/kpress-static/%2e%2e/static/styles.css",
      "/static/styles.css",
      // Not a stylesheet's address.
      "/kpress-static/v0.3.9/js/toc.js",
      "data:text/css,p{font-family:serif}",
      "",
    ];
    const warned = [];
    const warn = console.warn;
    console.warn = (...args) => warned.push(args);
    const manifest = kpressStylesheets(
      {
        schema_version: "kpress-asset-manifest-v2",
        import_map: { "/kpress-static/js/runtime.js": "/kpress-static/v0.3.9/js/runtime.js" },
        assets: [
          ...[...kept, ...dropped].map((public_url) => ({ loading: "stylesheet", public_url })),
          // A script is not a stylesheet, so it is neither kept nor named.
          { loading: "module", public_url: "/kpress-static/v0.3.9/js/toc.js" },
        ],
      },
      PAGE,
    );
    console.warn = warn;
    assert.deepEqual(
      manifest.assets.map((asset) => asset.public_url),
      kept,
      "same-origin KPress CSS is kept, whatever its version",
    );
    assert.deepEqual(manifest.import_map, {}, "nothing of the manifest runs");
    assert.equal(warned.length, 1, "one warning names every stylesheet left out");
    assert.deepEqual(warned[0][1], dropped);
    console.warn = (...args) => warned.push(args);
    kpressStylesheets(
      {
        schema_version: "kpress-asset-manifest-v2",
        import_map: {},
        assets: kept.map((public_url) => ({ loading: "stylesheet", public_url })),
      },
      PAGE,
    );
    console.warn = warn;
    assert.equal(warned.length, 1, "a manifest of KPress CSS alone warns of nothing");
  }
  // The format a change renders as, from both its sides' names, as the server's route
  // reads them (`_rendered_format` in github/pull_rendered_diff.py): an extension in any
  // case, one format on both sides, files only, and a dotfile's name is no extension.
  const side = (name) => ({ entry_type: "file", path: name });
  // One table for both: tests/test_rendered_formats.py reads it for the server's route.
  const table = JSON.parse(
    fs.readFileSync(path.join(process.argv[2], "tests/fixtures/rendered-formats.json"), "utf8"),
  );
  const formats = table.names;
  for (const [name, format] of formats) {
    assert.equal(
      renderedFormat({ availability: "ready", old: null, new: side(name) }),
      format,
      name,
    );
    assert.equal(
      renderedFormat({ availability: "deferred", old: side(name), new: side(name) }),
      format,
      `${name}, deferred`,
    );
  }
  for (const [old, now, format] of table.renames) {
    assert.equal(
      renderedFormat({ availability: "ready", old: side(old), new: side(now) }),
      format,
      `renamed ${old} to ${now}`,
    );
  }
  for (const entry_type of ["symlink", "submodule", "directory"]) {
    assert.equal(
      renderedFormat({ availability: "ready", old: null, new: { entry_type, path: "a.json" } }),
      null,
      `a ${entry_type}`,
    );
  }
  assert.equal(
    renderedFormat({
      availability: "ready",
      old: side("a.json"),
      new: { entry_type: "symlink", path: "a.json" },
    }),
    null,
    "a file that became a symlink",
  );
  // The format alone decides the chooser, so a file whose changes did not load has one
  // too (mb-rm40); no projection is asked for it.
  for (const availability of ["binary", "too_large", "unavailable", undefined]) {
    const change = { availability, new: side("a.json") };
    assert.equal(renderedFormat(change), "json", `${availability}`);
    assert.equal(supportsRenderedChange(change), false, `${availability}`);
  }
  const md = { entry_type: "file", path: "docs/readme.MD" };
  assert.equal(supportsRenderedChange({ availability: "ready", old: null, new: md }), true);
  assert.equal(supportsRenderedChange({ availability: "deferred", old: md, new: null }), true);
  assert.equal(
    supportsRenderedChange({ availability: "ready", old: md, new: { ...md, path: "README.txt" } }),
    false,
  );
  assert.equal(
    supportsRenderedChange({ availability: "ready", new: { ...md, entry_type: "symlink" } }),
    false,
  );

  // Why the server refused, as the sentence the Rendered chip says: the reason it names,
  // its status where it names none or one this page does not know, and the format's own
  // sentence for a file it could not read as its format.
  const refused = (status, reason) => ({ status, ...(reason === undefined ? {} : { reason }) });
  for (const format of ["markdown", "yaml", "json"]) {
    assert.equal(
      refusalReason(refused("too_large", "memory"), format),
      "Rendering stopped at the memory limit. Reload the page to try again.",
    );
  }
  assert.equal(
    refusalReason(refused("too_large", "nesting"), "markdown"),
    "This file is nested too deeply to show rendered.",
  );
  assert.equal(
    refusalReason(refused("unsupported", "no_changes"), "yaml"),
    "This file's content did not change.",
  );
  assert.equal(
    refusalReason(refused("too_large", "deadline"), "markdown"),
    "Rendering this file took too long, so it was stopped. Reload the page to try again.",
  );
  assert.equal(
    refusalReason(refused("too_large"), "json"),
    "This file is too large to show rendered.",
  );
  assert.equal(
    refusalReason(refused("too_large", "a reason of a later server"), "markdown"),
    "This file is too large to show rendered.",
  );
  assert.equal(
    refusalReason(refused("unsupported"), "markdown"),
    "This file's changes cannot be matched to its rendered Markdown.",
  );
  assert.match(refusalReason(refused("unsupported"), "yaml"), /^Rendered cannot show YAML /);
  assert.match(refusalReason(null, "json"), /^Rendered cannot show JSON /);
  assert.equal(
    refusalReason(refused("unsupported", "toString"), "markdown"),
    "This file's changes cannot be matched to its rendered Markdown.",
    "a reason is looked up among the sentences, not on the table's prototype",
  );

  // An image opens on the comparison's own image route, which the server names, completed
  // with a path; a link to a file of the head is its `/view/` address while the page shows
  // that head, and that file at the head on github.com otherwise.
  const route = `/api/plugin/github/pull-image?${new URLSearchParams({
    number: "346",
    left: "1".repeat(40),
    right: "2".repeat(40),
    store: "3".repeat(16),
  })}`;
  let showsHead = true;
  const onGithub = "https://github.com/octo/demo/blob/head/docs/README.md";
  const isTarget = markdownTargets(
    route,
    () => showsHead,
    (href) => (href.startsWith(link) ? onGithub : null),
  );
  const image = `${route}&path=g1-ZG9jcw%2Fg1-UkVBRE1FLm1k`;
  const link = "/view/g1-ZG9jcw/g1-UkVBRE1FLm1k";
  assert.equal(isTarget(image, true), image);
  assert.equal(isTarget(image, false), null, "an image's address is no link");
  assert.equal(isTarget(`${image}&mode=image`, true), null);
  assert.equal(isTarget(`${image}&path=g1-eA`, true), null, "a repeated name");
  assert.equal(isTarget(`https://example.org${image}`, true), null);
  assert.equal(isTarget(image.replace("left=1", "left=0"), true), null);
  assert.equal(isTarget("/raw?path=README.md", true), null);
  assert.equal(isTarget(image.replace("g1-ZG9jcw", ".."), true), null);
  assert.equal(isTarget(link, false), link);
  assert.equal(isTarget(`${link}#user-content-setup`, false), `${link}#user-content-setup`);
  assert.equal(isTarget(`${link}#a"b`, false), null, "a fragment the server never spells");
  assert.equal(isTarget(`${link}?plain=1`, false), null);
  assert.equal(isTarget(link, true), null, "a link's address is no image");
  assert.equal(isTarget("/view/README.md", false), null, "not a pin's address");
  assert.equal(isTarget("/view/g1-ZG9jcw/../g1-UkVBRE1FLm1k", false), null);
  showsHead = false;
  assert.equal(isTarget(link, false), onGithub, "a page on another commit links the head's file");
  assert.equal(isTarget(image, true), image, "and keeps its images");
  assert.equal(
    markdownTargets(route, () => false)(link, false),
    null,
    "with no file on github.com, a page on another commit keeps no link",
  );
  assert.equal(markdownTargets(undefined, () => true)(image, true), null, "no route, no image");

  // The first screen's Markdown files, asked for ahead of Changes.
  const entry = (id, path, availability = "ready") => ({
    id,
    availability,
    old: null,
    new: { entry_type: "file", path },
  });
  assert.deepEqual(
    firstScreenRendered([
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

  // A block's row: its change's label for a screen reader, then what the block draws. A
  // block whose source says more than its render shows draws nothing more to say so.
  const built = [];
  const build = (html) => {
    built.push(html);
    return make("div");
  };
  const flagged = blockRow({ kind: "added", html: "<p>new</p>", source_only: true }, build);
  assert.equal(flagged.className, "diff-markdown-block diff-markdown-added");
  assert.ok(texts(flagged).includes("Added: "));
  assert.equal(
    flagged.children.length,
    2,
    "a block whose source says more draws its label and its content, and no note",
  );
  const unchanged = blockRow({ kind: "context", html: "<p>same</p>", source_only: false }, build);
  assert.equal(unchanged.children.length, 1, "an unchanged block has no label");
  assert.deepEqual(built, ["<p>new</p>", "<p>same</p>"]);

  // Each run of changed rows is one change, and each run of one kind in it one run, the one
  // box that draws its band: unchanged rows and fold bars stand between changes.
  const kinds = ["context", "added", "added", "removed", "added", "context", "removed"];
  const placed = changeRuns(
    kinds.map((kind, index) => blockRow({ kind, html: `<p>${index}</p>` }, build)),
  );
  const placedShape = (node) =>
    node.classList.contains("diff-markdown-change")
      ? node.children.map((run) => `${run.className.split("-").pop()} x${run.children.length}`)
      : node.className.split("-").pop();
  assert.deepEqual(placed.map(placedShape), [
    "context",
    ["added x2", "removed x1", "added x1"],
    "context",
    ["removed x1"],
  ]);

  // A projection as the page holds it: a Concise answer leaves out a withheld fold's
  // blocks, which the model holds as missing until they are asked for. Full draws every
  // block, and Concise each block outside a fold and each fold, which stands for its blocks.
  const context = (n) => ({ kind: "context", html: `<p id="user-content-x-${n}">${n}</p>` });
  const concise = {
    version: "markdown-diff-v1",
    status: "ready",
    source_only: false,
    view: "concise",
    count: 12,
    folds: [
      { at: 2, count: 4, lines: 7 },
      { at: 8, count: 2, lines: 140, withheld: true, ids: ["user-content-x-9"] },
    ],
    blocks: [0, 1, 2, 3, 4, 5, 6, 7, 10, 11].map(context),
  };
  const read = projectionModel(concise);
  assert.equal(read.view, "concise");
  assert.deepEqual(
    read.model.blocks.map((block) => block?.html.match(/>(\d+)</)[1] ?? null),
    ["0", "1", "2", "3", "4", "5", "6", "7", null, null, "10", "11"],
    "a withheld fold's blocks are missing, the rest in their places",
  );
  const shape = (units) =>
    units.map((unit) =>
      unit.kind === "block" ? unit.index : `fold ${unit.fold.at}+${unit.fold.count}`,
    );
  assert.deepEqual(shape(viewUnits(read.model, "concise")), [
    0,
    1,
    "fold 2+4",
    6,
    7,
    "fold 8+2",
    10,
    11,
  ]);
  assert.deepEqual(shape(viewUnits(read.model, "full")), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]);
  assert.equal(blockOf(read.model, "user-content-x-3"), 3, "a heading's block");
  assert.equal(blockOf(read.model, "user-content-x-9"), 8, "a withheld one's fold");
  assert.equal(blockOf(read.model, "user-content-x-99"), -1);
  // An answer whose blocks do not fill what it says it holds is not drawn.
  for (const broken of [
    { ...concise, count: 13 },
    { ...concise, blocks: concise.blocks.slice(1) },
    { ...concise, view: "whole" },
    {
      ...concise,
      folds: [
        { at: 2, count: 4, lines: 7 },
        { at: 4, count: 2, lines: 3 },
      ],
    },
    { ...concise, folds: [{ at: 11, count: 2, lines: 3 }] },
  ]) {
    assert.equal(projectionModel(broken), null, JSON.stringify(broken.folds));
  }
  // Full's answer holds every block, its folds listed but none withheld.
  const full = projectionModel({
    ...concise,
    view: "full",
    folds: concise.folds.map(({ at, count, lines }) => ({ at, count, lines })),
    blocks: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11].map(context),
  });
  assert.ok(full.model.blocks.every((block) => block !== undefined));
  // A withheld fold's blocks, as `blocks=` answers them, and only for that fold.
  const fold = concise.folds[1];
  const range = {
    version: "markdown-diff-v1",
    status: "ready",
    at: 8,
    blocks: [8, 9].map(context),
  };
  assert.deepEqual(foldBlocks(range, fold), range.blocks);
  assert.equal(foldBlocks({ ...range, at: 7 }, fold), null);
  assert.equal(foldBlocks({ ...range, blocks: [context(8)] }, fold), null);
  // A run within 500 units and 512 KiB is drawn whole; a longer one a chunk at a time, a
  // hundred units or 128 KiB of HTML a chunk.
  const many = Array.from({ length: 650 }, (_, index) => ({ kind: "block", index }));
  assert.deepEqual(
    chunkUnits(many.slice(0, 500), () => 1024).map((chunk) => chunk.length),
    [500],
  );
  assert.deepEqual(
    chunkUnits(many, () => 10).map((chunk) => chunk.length),
    [100, 100, 100, 100, 100, 100, 50],
  );
  assert.deepEqual(
    chunkUnits(many.slice(0, 11), () => 50 * 1024).map((chunk) => chunk.length),
    [3, 3, 3, 2],
  );
  assert.deepEqual(
    chunkUnits([], () => 0),
    [],
  );
  assert.equal(
    estimatedHeight(
      [
        { kind: "block", index: 0 },
        { kind: "fold", fold },
      ],
      () => 100,
    ),
    80,
    "a block's place from its bytes, and a fold's bar",
  );

  const calls = [];
  let assets = 0;
  let mutations = 0;
  /** @type {string[][]} */
  const styled = [];
  const inert = {
    sanitizeNodes: () => [],
    kpressProse: () => make("div"),
  };
  const time = clock();
  const root = make("div");
  const view = createMarkdownViews({
    controls: {
      groupHtml: (spec) => spec,
      bind: bindChooser,
    },
    load(id, signal) {
      return new Promise((resolve, reject) => calls.push({ id, signal, resolve, reject }));
    },
    async ensureInert() {
      assets += 1;
      return inert;
    },
    async loadStyles(manifest) {
      styled.push(manifest.assets.map((asset) => asset.public_url));
    },
    mutate(change) {
      mutations += 1;
      change();
    },
    now: time.now,
    later: time.later,
    cancel: time.cancel,
  });
  // A bar as diff-view.js builds it: the disclosure and a View file control, then the
  // group at its end, empty until the chooser arrives. `lead` puts another control before
  // the disclosure, so a test can tell the disclosure the module was handed from whatever
  // happens to lead the bar.
  function file(id, { lead = false } = {}) {
    const section = make("section");
    root.append(section);
    const bar = make("div");
    const source = make("div");
    source.id = id;
    section.append(bar, source);
    const toggle = make("button");
    const end = make("div");
    const viewFile = make("a");
    bar.append(...(lead ? [make("span"), toggle, viewFile, end] : [toggle, viewFile, end]));
    const state = view.add({ section, bar, end, source, id, format: "markdown" });
    const [, fallback, rendered] = section.children;
    assert.equal(fallback.hidden, true, "a Full fallback notice only shows when needed");
    assert.equal(bar.children.at(-1), end, "the chooser adds nothing to the bar itself");
    const [progress, control] = end.children;
    assert.equal(progress.getAttribute("role"), "status", "the progress mark leads its chooser");
    assert.equal(end.children.at(-1), control, "the chooser is last, at the bar's far end");
    assert.equal(bar.children.at(-2), viewFile, "View file stays where the bar put it");
    return {
      section,
      bar,
      source,
      rendered,
      progress,
      state,
      control,
      toggle,
      // A Markdown file opens in Concise, as Changes opens one.
      get renderedChoice() {
        return control.children.find((chip) => chip.dataset.chipValue === "rendered");
      },
      get sourceChoice() {
        return control.children.find((chip) => chip.dataset.chipValue === "source");
      },
    };
  }

  const a = file("a");
  const b = file("b");
  const c = file("c", { lead: true });
  const d = file("d");
  assert.equal(a.source.hidden, true, "a file waits for Rendered before showing Source");
  assert.ok(
    a.bar.classList.contains("diff-file-bar-markdown"),
    "a chooser lays the bar out for it",
  );
  assert.equal(a.control.hidden, false);
  assert.equal(a.progress.hidden, false);
  view.observe(null);
  assert.equal(observer.options.rootMargin, "0px 0px 100% 0px", "a viewport of lookahead");
  assert.equal(
    chunkObserver.options.rootMargin,
    "100% 0px 100% 0px",
    "a chunk is drawn a viewport before the reader reaches it, from above or below",
  );
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
  assert.equal(a.source.hidden, true, "past the loading delay a file still waits for Rendered");
  assert.equal(b.source.hidden, true);
  // What a waiting file's section says, which keeps everything after it out of sight
  // (styles.css), so its body arriving moves nothing a reader sees; one that waits no more
  // does not say it.
  const awaiting = (file) => file.section.classList.contains(WAITING_CLASS);
  assert.deepEqual([a, b, c, d].map(awaiting), [true, true, false, false]);
  await a.sourceChoice.click();
  assert.equal(awaiting(a), false, "choosing Source ends its wait");
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
    view: "concise",
    count: 1,
    folds: [],
    blocks: [
      { kind: "added", side: "new", html: "<p>Edited <ins>word</ins></p>", source_only: false },
    ],
  };
  // The server names KPress's stylesheets under the package's asset stamp
  // (metabrowser.asset_stamps) and KPress's version; only same-origin KPress CSS is kept.
  // An editable or development KPress's version has a PEP 440 local segment, whose `+`
  // a pattern over the address's characters once refused, dropping document.css, so a
  // rendered document read in sans under the serif reading font (mb-2r08).
  const stamped = "/kpress-static/@0123456789abcdef/v0.3.5/css/document.css";
  const local = "/kpress-static/@a009bfcd7946408c/v0.3.10.dev10+5c60a81/css/document.css";
  const away = "https://elsewhere.example/kpress-static/x.css";
  const styleWarnings = [];
  const warnBefore = console.warn;
  console.warn = (...args) => styleWarnings.push(args);
  calls[0].resolve({
    ...ready,
    assets: {
      schema_version: "kpress-asset-manifest-v2",
      import_map: {},
      assets: [
        { loading: "stylesheet", public_url: stamped },
        { loading: "stylesheet", public_url: local },
        { loading: "stylesheet", public_url: "/kpress-static/v0.3.5/css/print.css" },
        { loading: "stylesheet", public_url: away },
        { loading: "module", public_url: "/kpress-static/@0123456789abcdef/v0.3.5/js/toc.js" },
      ],
    },
  });
  await new Promise(setImmediate);
  console.warn = warnBefore;
  assert.deepEqual(
    styled,
    [[stamped, local, "/kpress-static/v0.3.5/css/print.css"]],
    "a release's and a local version's KPress stylesheets load; another origin's and a script do not",
  );
  assert.deepEqual(
    styleWarnings.map(([message, urls]) => [
      message.startsWith("metabrowser diff: KPress stylesheets"),
      urls,
    ]),
    [[true, [away]]],
    "the stylesheet left out is named in a warning",
  );
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
  assert.equal(b.control.hidden, false, "a busy server keeps the chooser");
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
  calls[3].resolve({ version: "markdown-diff-v1", status: "too_large", blocks: [] });
  await new Promise(setImmediate);
  assert.equal(c.sourceChoice.attributes.get("aria-checked"), "true");
  assert.equal(c.control.hidden, false, "a file that can only show Source keeps its chooser");
  assert.equal(c.progress.hidden, false, "and its progress mark's place");
  assert.ok(c.bar.classList.contains("diff-file-bar-markdown"), "and its bar's layout");
  const why = "This file is too large to show rendered.";
  assert.equal(c.renderedChoice.attributes.get("aria-disabled"), "true");
  assert.equal(c.renderedChoice.disabled, undefined, "it takes the pointer, so it can say why");
  assert.equal(c.renderedChoice.dataset.tipText, why, "as its tooltip");
  assert.equal(
    c.renderedChoice.attributes.get("aria-label"),
    `Rendered, unavailable. ${why}`,
    "and in its accessible name",
  );
  assert.equal(c.sourceChoice.dataset.tipText, undefined);
  assert.equal(c.sourceChoice.attributes.get("aria-disabled"), undefined);
  assert.equal(document.activeElement, c.sourceChoice, "focus follows the format shown");
  assert.equal(c.source.hidden, false, "it shows Source");
  assert.equal(c.rendered.hidden, true);
  assert.equal(c.section.children[1].hidden, true, "there is no Full fallback notice in Diff");
  await c.renderedChoice.click();
  await new Promise(setImmediate);
  assert.equal(calls.length, 4, "choosing an unavailable Rendered asks for nothing");
  assert.equal(c.sourceChoice.attributes.get("aria-checked"), "true", "and changes nothing");
  assert.equal(c.source.hidden, false);

  await a.renderedChoice.click();
  assert.equal(calls.length, 4, "the answer that arrived after Source was chosen is reused");
  assert.equal(a.rendered.hidden, false);
  assert.equal(a.source.hidden, true);
  const [shown] = a.rendered.children;
  assert.equal(blockRows(shown).length, 1, "the one block, with no note about Source above it");
  assert.ok(blockRows(shown)[0].className.startsWith("diff-markdown-block"));
  assert.equal(assets, 1);
  await a.sourceChoice.click();
  assert.equal(a.source.hidden, false);
  await a.renderedChoice.click();
  assert.equal(a.rendered.hidden, false);
  assert.equal(calls.length, 4, "switching back reuses rendered content");

  observer.notify([arrival(d)]);
  assert.equal(calls.length, 5);
  const warned = [];
  const warn = console.warn;
  console.warn = (...args) => warned.push(args);
  calls[4].reject(new Error("Server is broken"));
  await new Promise(setImmediate);
  console.warn = warn;
  assert.equal(warned.length, 1, "a failed render is logged to the console");
  assert.equal(warned[0][1].message, "Server is broken");
  assert.equal(d.sourceChoice.attributes.get("aria-checked"), "true");
  assert.equal(
    d.renderedChoice.attributes.get("aria-disabled"),
    undefined,
    "a transport error allows another attempt",
  );
  assert.equal(d.renderedChoice.dataset.tipText, undefined);
  assert.equal(d.control.hidden, false, "a retryable failure keeps the chooser");
  assert.equal(d.progress.hidden, false);
  assert.ok(d.bar.classList.contains("diff-file-bar-markdown"));
  assert.equal(d.source.hidden, false, "a failed render shows Source");
  assert.equal(d.section.children[1].hidden, true, "and says nothing about it");
  await d.renderedChoice.click();
  assert.equal(calls.length, 6, "choosing Rendered asks again");
  assert.equal(d.source.hidden, false, "Source stays until the answer arrives");
  view.dispose();
  assert.equal(calls[5].signal.aborted, true, "disposal stops the request in flight");
  assert.equal(observer.observed.size, 0);
  assert.equal(chunkObserver.observed.size, 0, "disposal stops watching chunks");
  assert.equal(bound.size, 0, "disposal unbinds every chooser");
  assert.equal(time.pending, 0, "disposal cancels every timer");
  calls[5].resolve(ready);
  await new Promise(setImmediate);
  assert.equal(d.rendered.hidden, true);

  // A file whose changes the page holds no patch of has the chooser too: it shows Source,
  // which says why, from the start, its Rendered is unavailable for the same reason, and
  // no projection is ever asked for it.
  const asked = [];
  const root4 = make("div");
  const view4 = createMarkdownViews({
    controls: { groupHtml: (spec) => spec, bind: () => () => {} },
    load: (id) => new Promise(() => asked.push(id)),
    ensureInert: async () => inert,
    async loadStyles() {},
    mutate: (change) => change(),
    now: time.now,
    later: time.later,
    cancel: time.cancel,
  });
  const section4 = make("section");
  root4.append(section4);
  const bar4 = make("div");
  const source4 = make("div");
  source4.id = "h";
  const toggle4 = make("button");
  const end4 = make("div");
  bar4.append(toggle4, end4);
  section4.append(bar4, source4);
  view4.add({
    section: section4,
    bar: bar4,
    end: end4,
    source: source4,
    id: "h",
    format: "yaml",
    unavailable: "This change is too large to show inline.",
  });
  const [, control4] = end4.children;
  assert.equal(source4.hidden, false, "it shows Source at once, with no wait for Rendered");
  assert.equal(control4.children[1].attributes.get("aria-checked"), "true");
  assert.equal(control4.children[0].attributes.get("aria-disabled"), "true");
  assert.equal(control4.children[0].dataset.tipText, "This change is too large to show inline.");
  let settled4 = false;
  void view4.firstScreen.then(() => {
    settled4 = true;
  });
  view4.observe(null);
  observer.notify([{ target: section4, isIntersecting: true }]);
  await new Promise(setImmediate);
  assert.deepEqual(asked, [], "no projection is asked for it");
  assert.equal(settled4, true, "and the first screen does not wait for it");
  view4.dispose();

  // Current: the new version alone. A changed Markdown file's removed blocks and removed
  // front matter keys are hidden, by the attribute, and its added blocks and keys stay;
  // a deleted file, which has no current version, shows its Source body, which says so, and
  // so does a file left empty, whose Rendered is all removed. Diff draws them all again, from
  // what was drawn.
  const loads5 = [];
  const root5 = make("div");
  const view5 = createMarkdownViews({
    controls: { groupHtml: (spec) => spec, bind: () => () => {} },
    load: (id) => new Promise((resolve) => loads5.push({ id, resolve })),
    ensureInert: async () => inert,
    async loadStyles() {},
    mutate: (change) => change(),
    now: time.now,
    later: time.later,
    cancel: time.cancel,
  });
  const file5 = (id, gone) => {
    const section = make("section");
    root5.append(section);
    const bar = make("div");
    const source = make("div");
    source.id = id;
    section.append(bar, source);
    const end = make("div");
    bar.append(make("button"), end);
    view5.add({ section, bar, end, source, id, format: "markdown", gone });
    // Diff | Current is the diff's, in its toolbar: the end group is the progress mark and
    // Rendered | Source alone, in Current as in Diff.
    const [progress, control] = end.children;
    assert.equal(progress.getAttribute("role"), "status", "the progress mark leads the group");
    assert.ok(control.classList.contains("diff-markdown-control"), "Rendered | Source ends it");
    return { section, source, rendered: section.children[2] };
  };
  const changed5 = file5("m", false);
  const deleted5 = file5("x", true);
  const emptied5 = file5("e", false);
  view5.observe(null);
  observer.notify([changed5, deleted5, emptied5].map(({ section }) => arrival({ section })));
  const changedProjection = {
    version: "markdown-diff-v1",
    status: "ready",
    source_only: false,
    view: "concise",
    count: 3,
    folds: [],
    frontmatter: {
      change: "modified",
      entries: [
        { key: "title", text: "Guide", change: "context" },
        { key: "status", text: "draft", change: "removed" },
        { key: "status", text: "final", change: "added" },
        { key: "draft", text: "true", change: "removed" },
      ],
    },
    blocks: [
      { kind: "context", html: "<p>Kept</p>", source_only: false },
      { kind: "removed", html: "<p>Old <del>word</del></p>", source_only: false },
      { kind: "added", html: "<p>New <ins>word</ins></p>", source_only: false },
    ],
  };
  loads5[0].resolve(changedProjection);
  await new Promise(setImmediate);
  const [drawn5] = changed5.rendered.children;
  const [front, kept, removed5, added5] = blockRows(drawn5);
  const list = front.children[0].children[1];
  const [, , oldTerm, oldValue, newTerm, newValue] = list.children;
  const [removedKey, removalNotice] = list.children.slice(-2);
  assert.equal(removedKey.textContent, "draft");
  assert.equal(removalNotice.hidden, true);
  assert.ok(removed5.className.includes("diff-markdown-removed"));
  assert.equal(removed5.parent.className, "diff-markdown-run diff-markdown-run-removed");
  assert.equal(added5.parent.className, "diff-markdown-run diff-markdown-run-added");
  assert.equal(removed5.parent.parent, added5.parent.parent, "an edit's two runs are one change");
  assert.ok(oldTerm.className.includes("diff-frontmatter-removed"));
  // The removed run is hidden with its row, so it draws no band in Current.
  const hiddenParts = () =>
    [kept, removed5.parent, removed5, added5, oldTerm, oldValue, newTerm, newValue].map(
      (part) => part.hidden,
    );
  assert.deepEqual(hiddenParts(), [false, false, false, false, false, false, false, false]);
  assert.equal(changed5.rendered.hidden, false, "Diff draws the changed file's Rendered");
  loads5[1].resolve({ ...changedProjection, frontmatter: undefined });
  await new Promise(setImmediate);
  assert.equal(deleted5.rendered.hidden, false, "and the deleted file's");
  assert.equal(loads5[2].id, "e");
  loads5[2].resolve({
    version: "markdown-diff-v1",
    status: "ready",
    source_only: false,
    view: "concise",
    count: 2,
    folds: [],
    frontmatter: {
      change: "removed",
      entries: [{ key: "title", text: "Notes", change: "removed" }],
    },
    blocks: [
      { kind: "removed", html: "<p>Old <del>word</del></p>", source_only: false },
      { kind: "removed", html: "<p>Last</p>", source_only: false },
    ],
  });
  await new Promise(setImmediate);
  assert.equal(emptied5.rendered.hidden, false, "and the emptied file's");
  assert.equal(emptied5.source.hidden, true);
  view5.show("current");
  assert.equal(removalNotice.hidden, false, "Excerpt marks a removed frontmatter key");
  assert.equal(removalNotice.textContent, "Removed. See Diff.");
  assert.deepEqual(
    hiddenParts(),
    [false, true, true, false, true, true, false, false],
    "Current hides the removed run and block and the removed key's term and value, and only them",
  );
  assert.equal(changed5.rendered.hidden, false, "it is still the file's Rendered");
  assert.equal(deleted5.rendered.hidden, true, "a deleted file has no current version");
  assert.equal(deleted5.source.hidden, false, "so it shows its Source body, which says so");
  assert.equal(emptied5.rendered.hidden, true, "an emptied file has nothing Current draws");
  assert.equal(emptied5.source.hidden, false, "so it shows its Source body, which says so");
  assert.equal(loads5.length, 3, "nothing is asked again");
  view5.show("diff");
  assert.equal(removalNotice.hidden, true, "Diff draws the actual removed key and value");
  assert.deepEqual(hiddenParts(), [false, false, false, false, false, false, false, false]);
  assert.equal(deleted5.rendered.hidden, false, "Diff shows the deleted file's Rendered again");
  assert.equal(deleted5.source.hidden, true);
  assert.equal(emptied5.rendered.hidden, false, "and the emptied file's");
  assert.equal(emptied5.source.hidden, true);
  view5.dispose();

  // A diff that opens in Current draws a file's Rendered in it from its first draw.
  const loads6 = [];
  const root6 = make("div");
  const view6 = createMarkdownViews({
    controls: { groupHtml: (spec) => spec, bind: () => () => {} },
    load: (id) => new Promise((resolve) => loads6.push({ id, resolve })),
    ensureInert: async () => inert,
    async loadStyles() {},
    mutate: (change) => change(),
    now: time.now,
    later: time.later,
    cancel: time.cancel,
    show: "current",
  });
  const section6 = make("section");
  root6.append(section6);
  const bar6 = make("div");
  const source6 = make("div");
  source6.id = "n";
  section6.append(bar6, source6);
  const end6 = make("div");
  bar6.append(make("button"), end6);
  view6.add({
    section: section6,
    bar: bar6,
    end: end6,
    source: source6,
    id: "n",
    format: "markdown",
  });
  view6.observe(null);
  observer.notify([{ target: section6, isIntersecting: true }]);
  loads6[0].resolve({ ...changedProjection, frontmatter: undefined });
  await new Promise(setImmediate);
  const [, removed6, added6] = blockRows(section6.children[2].children[0]);
  assert.equal(removed6.hidden, true, "its removed block is hidden as it is placed");
  assert.equal(removed6.parent.hidden, true, "and its run");
  assert.equal(added6.hidden, false);
  view6.dispose();

  // A withheld fold's blocks asked for while the server's one slot is busy: the wait before
  // asking again ends when the views are disposed, which leaves no timer and asks nothing
  // more.
  const loads7 = [];
  const time7 = clock();
  const root7 = make("div");
  const view7 = createMarkdownViews({
    controls: { groupHtml: (spec) => spec, bind: () => () => {} },
    load: (id, signal, ask) =>
      new Promise((resolve, reject) => loads7.push({ id, signal, ask, resolve, reject })),
    ensureInert: async () => inert,
    async loadStyles() {},
    mutate: (change) => change(),
    now: time7.now,
    later: time7.later,
    cancel: time7.cancel,
  });
  const section7 = make("section");
  root7.append(section7);
  const bar7 = make("div");
  const source7 = make("div");
  source7.id = "w";
  section7.append(bar7, source7);
  const end7 = make("div");
  bar7.append(make("button"), end7);
  view7.add({
    section: section7,
    bar: bar7,
    end: end7,
    source: source7,
    id: "w",
    format: "markdown",
  });
  view7.observe(null);
  observer.notify([{ target: section7, isIntersecting: true }]);
  loads7[0].resolve(structuredClone(concise));
  await new Promise(setImmediate);
  // Past the loading delay, so no timer but the wait below is left.
  time7.advance(50);
  const [, , rendered7] = section7.children;
  // The article holds the fragment it was drawn from, as this page's elements keep one.
  const withheld7 = rendered7.children
    .flatMap((node) => (node.tagName === "" ? node.children : [node]))
    .find((node) => node.dataset.span === "8-10");
  assert.ok(withheld7 !== undefined, "the withheld fold's bar is drawn");
  await withheld7.click();
  assert.deepEqual(
    loads7.map((each) => each.ask),
    [{ view: "concise" }, { blocks: "8-10" }],
    "opening the withheld fold asks for its blocks",
  );
  loads7[1].reject(Object.assign(new Error("rendered_diff_busy"), { status: 429 }));
  await new Promise(setImmediate);
  assert.equal(time7.pending, 1, "the busy fold waits to ask again");
  view7.dispose();
  assert.equal(time7.pending, 0, "disposal ends the wait");
  time7.advance(10_000);
  await new Promise(setImmediate);
  assert.equal(loads7.length, 2, "and nothing is asked after it");

  // Printing draws every chunk not drawn yet in one hold of the reader's place, so rows
  // above the viewport that turn from estimates into blocks leave the reader where they
  // were.
  const printers = new Set();
  globalThis.window = {
    addEventListener: (type, listener) => type === "beforeprint" && printers.add(listener),
    removeEventListener: (_type, listener) => printers.delete(listener),
  };
  const loads8 = [];
  let holds8 = 0;
  let drawnInHold8 = 0;
  const root8 = make("div");
  const section8 = make("section");
  const spacers8 = () =>
    section8.children[2].children
      .flatMap((node) => (node.tagName === "" ? node.children : [node]))
      .filter((node) => node.className === "diff-markdown-spacer");
  const view8 = createMarkdownViews({
    controls: { groupHtml: (spec) => spec, bind: () => () => {} },
    load: (id) => new Promise((resolve) => loads8.push({ id, resolve })),
    ensureInert: async () => inert,
    async loadStyles() {},
    mutate(change) {
      holds8 += 1;
      const before = spacers8().length;
      change();
      drawnInHold8 += before - spacers8().length;
    },
    now: time.now,
    later: time.later,
    cancel: time.cancel,
  });
  root8.append(section8);
  const bar8 = make("div");
  const source8 = make("div");
  source8.id = "p";
  section8.append(bar8, source8);
  const end8 = make("div");
  bar8.append(make("button"), end8);
  view8.add({
    section: section8,
    bar: bar8,
    end: end8,
    source: source8,
    id: "p",
    format: "markdown",
  });
  view8.observe(null);
  observer.notify([{ target: section8, isIntersecting: true }]);
  loads8[0].resolve({
    version: "markdown-diff-v1",
    status: "ready",
    source_only: false,
    view: "full",
    count: 600,
    folds: [],
    blocks: Array.from({ length: 600 }, (_, index) => context(index)),
  });
  await new Promise(setImmediate);
  const waiting8 = spacers8().length;
  assert.ok(waiting8 > 0, "a long document keeps chunks undrawn");
  assert.equal(printers.size, 1, "the views listen for printing");
  holds8 = 0;
  drawnInHold8 = 0;
  for (const listener of printers) {
    listener();
  }
  assert.equal(spacers8().length, 0, "printing draws every chunk");
  assert.equal(holds8, 1, "in one hold of the reader's place");
  assert.equal(drawnInHold8, waiting8, "every chunk drawn inside it");
  view8.dispose();
  assert.equal(printers.size, 0, "disposal stops listening for printing");
  delete globalThis.window;

  // A sanitizer that loaded nothing, or whose load failed, is loaded again when Rendered
  // is chosen again. Each failure is logged, not shown.
  const warn2 = console.warn;
  let warnings = 0;
  console.warn = () => {
    warnings += 1;
  };
  let attempts = 0;
  const retried = [];
  const root2 = make("div");
  const view2 = createMarkdownViews({
    controls: {
      groupHtml: (spec) => spec,
      bind: bindChooser,
    },
    load: (id) => new Promise((resolve) => retried.push({ id, resolve })),
    async ensureInert() {
      attempts += 1;
      if (attempts === 2) {
        throw new Error("offline");
      }
      return attempts === 1 ? undefined : inert;
    },
    async loadStyles() {},
    mutate: (change) => change(),
    now: time.now,
    later: time.later,
    cancel: time.cancel,
  });
  const section2 = make("section");
  root2.append(section2);
  const bar2 = make("div");
  const source2 = make("div");
  source2.id = "e";
  section2.append(bar2, source2);
  const toggle2 = make("button");
  const end2 = make("div");
  bar2.append(toggle2, end2);
  view2.add({
    section: section2,
    bar: bar2,
    end: end2,
    toggle: toggle2,
    source: source2,
    id: "e",
    format: "markdown",
  });
  const [, control2] = end2.children;
  const [, , rendered2] = section2.children;
  view2.observe(null);
  observer.notify([{ target: section2, isIntersecting: true }]);
  retried[0].resolve(ready);
  await new Promise(setImmediate);
  assert.equal(rendered2.hidden, true);
  assert.equal(source2.hidden, false);
  assert.equal(control2.hidden, false, "an empty sanitizer load keeps the chooser");
  await control2.children[0].click();
  assert.equal(retried.length, 2);
  retried[1].resolve(ready);
  await new Promise(setImmediate);
  assert.equal(attempts, 2, "the empty load was not kept");
  assert.equal(source2.hidden, false);
  assert.equal(control2.hidden, false, "a failed sanitizer load keeps the chooser");
  assert.equal(rendered2.hidden, true);
  await control2.children[0].click();
  assert.equal(retried.length, 3);
  retried[2].resolve(ready);
  await new Promise(setImmediate);
  assert.equal(attempts, 3, "the failed load was not kept");
  assert.equal(rendered2.hidden, false);
  console.warn = warn2;
  assert.equal(warnings, 2, "both sanitizer failures were logged");
  assert.equal(section2.children[1].hidden, true, "and none was shown");
  view2.dispose();

  // The first screen settles once none of its files waits: here when both are Rendered,
  // well inside a page's longer wait; and at the wait's end for one that never answers,
  // whose files go on waiting.
  for (const answered of [true, false]) {
    const loads = [];
    const root3 = make("div");
    const view3 = createMarkdownViews({
      controls: { groupHtml: (spec) => spec, bind: () => () => {} },
      load: (id) => new Promise((resolve) => loads.push({ id, resolve })),
      ensureInert: async () => inert,
      async loadStyles() {},
      mutate: (change) => change(),
      now: time.now,
      later: time.later,
      cancel: time.cancel,
      holdMs: 200,
    });
    const sections = ["f", "g"].map((id) => {
      const section = make("section");
      root3.append(section);
      const bar = make("div");
      const source = make("div");
      source.id = id;
      section.append(bar, source);
      const toggle = make("button");
      const end = make("div");
      bar.append(toggle, end);
      view3.add({ section, bar, end, source, id, format: "markdown" });
      return section;
    });
    let settled = false;
    void view3.firstScreen.then(() => {
      settled = true;
    });
    view3.observe(null);
    observer.notify(sections.map((target) => ({ target, isIntersecting: true })));
    time.advance(50);
    await new Promise(setImmediate);
    assert.equal(settled, false, "the page's longer wait outlasts the app's loading delay");
    if (answered) {
      loads[0].resolve(ready);
      await new Promise(setImmediate);
      assert.equal(settled, false, "one file still waits");
      loads[1].resolve(ready);
      await new Promise(setImmediate);
      assert.equal(settled, true, "both drawn Rendered: the first screen is final");
    } else {
      time.advance(150);
      await new Promise(setImmediate);
      assert.equal(settled, true, "the wait's end settles it");
      assert.deepEqual(
        sections.map((section) => section.children.at(-1).hidden),
        [true, true],
        "with no Source shown that a late answer would replace",
      );
    }
    view3.dispose();
  }
  console.log("diff Markdown view OK");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
