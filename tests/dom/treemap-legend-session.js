// Browserless session: the Treemap's file-type legend and the one hover its cells, tally
// bars, and legend share.
//
// The Treemap shows File Overview's legend under its tally bars (docs/design-system.md,
// "Folder Treemap"). A legend entry is a handle on its family's marks: pointing at it marks
// every cell of the family, the files of its types and the folders it is the dominant type
// of, its segment in every tally row, and the entry. Pointing at a cell or a segment marks
// it and its family's entry. There is one tooltip: the bars show an entry's, the counts of
// the family's segment in the tally row the legend's shares are of, anchored on the entry;
// a cell shows its own.
//
// The Treemap view, its tally bars, the legend, the hover, the layout, and the legend
// model are the production modules, loaded whole. The document is a stand-in that parses
// the markup the view writes into elements, for the few calls they make on it, and
// `mb.watchRollup` hands the view the rollup each step names: one with the shape
// `/api/rollup` answers, which cli-api.tryscript.md pins. Each step prints the legend,
// what is marked as hovered, the tooltip's words, and what it is anchored on. Exits 1 on a
// failed invariant.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

// The folder plugin's modules have no package.json saying they are modules, which the
// browser never asks about. Node's warning names the process and the checkout, so it is
// kept out of the transcript.
const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const ENTITIES = { "&amp;": "&", "&quot;": '"', "&lt;": "<", "&gt;": ">", "&#39;": "'" };
const decode = (text) => text.replace(/&(amp|quot|lt|gt|#39);/g, (entity) => ENTITIES[entity]);

/** One simple selector: `.class`, `[attr]`, `[attr="value"]`, or a tag. */
function matches(element, selector) {
  if (selector.startsWith(".")) {
    return element.classList.contains(selector.slice(1));
  }
  const attribute = /^\[([\w-]+)(?:="([^"]*)")?\]$/.exec(selector);
  if (attribute) {
    const value = element.getAttribute(attribute[1]);
    return attribute[2] === undefined ? value !== null : value === attribute[2];
  }
  return element.tagName === selector.toUpperCase();
}

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.dataset = {};
    this.style = {
      setProperty: (name, value) => {
        this.style[name] = value;
      },
      removeProperty: (name) => {
        delete this.style[name];
      },
    };
    this.listeners = {};
    this.hidden = false;
    this.ownText = "";
    this.classList = {
      add: (...names) => {
        this.className = [...new Set([...this.className.split(" "), ...names])]
          .filter(Boolean)
          .join(" ");
      },
      remove: (...names) => {
        this.className = this.className
          .split(" ")
          .filter((name) => !names.includes(name))
          .join(" ");
      },
      toggle: (name, on) => (on ? this.classList.add(name) : this.classList.remove(name)),
      contains: (name) => this.className.split(" ").includes(name),
    };
  }
  get className() {
    return this.attributes.class ?? "";
  }
  set className(value) {
    this.attributes.class = String(value);
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name.startsWith("data-")) {
      const key = name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      this.dataset[key] = String(value);
    }
    if (name === "hidden") {
      this.hidden = true;
    }
  }
  getAttribute(name) {
    if (name.startsWith("data-")) {
      const key = name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
      return this.dataset[key] ?? null;
    }
    return name in this.attributes ? this.attributes[name] : null;
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
  append(...children) {
    for (const child of children) {
      child.remove();
      child.parentNode = this;
      this.children.push(child);
    }
  }
  replaceChildren(...children) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this.ownText = "";
    this.append(...children);
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }
  addEventListener(type, listener) {
    this.listeners[type] = [...(this.listeners[type] ?? []), listener];
  }
  removeEventListener(type, listener) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((each) => each !== listener);
  }
  /**
   * What the browser would dispatch for *type* with this element as its target: to this
   * element alone for mouseenter and mouseleave, and up through its ancestors for
   * mouseover and mouseout, which bubble to the map's one delegated pair.
   */
  emit(type, event = {}) {
    const bubbles = type === "mouseover" || type === "mouseout";
    for (let node = this; node; node = bubbles ? node.parentNode : null) {
      for (const listener of [...(node.listeners[type] ?? [])]) {
        listener({ type, target: this, ...event });
      }
    }
  }
  descendants() {
    return this.children.flatMap((child) => [child, ...child.descendants()]);
  }
  querySelector(selector) {
    return this.descendants().find((element) => matches(element, selector)) ?? null;
  }
  querySelectorAll(selector) {
    return this.descendants().filter((element) => matches(element, selector));
  }
  closest(selector) {
    for (let node = this; node; node = node.parentNode) {
      if (node instanceof FakeElement && matches(node, selector)) {
        return node;
      }
    }
    return null;
  }
  contains(other) {
    return other === this || this.descendants().includes(other);
  }
  /** In the document: each parent up to its body still holds the element. */
  get isConnected() {
    let node = this;
    while (node.parentNode?.children.includes(node)) {
      node = node.parentNode;
    }
    return node === document.body;
  }
  focus() {}
  /** The map's viewport is 800 by 600 under the page's chrome; nothing else is measured. */
  getBoundingClientRect() {
    return this.classList.contains("tm-viewport")
      ? { top: 120, left: 0, width: 800, height: 600 }
      : { top: 0, left: 0, width: 0, height: 0 };
  }
  /** Parse markup the view writes: well-formed tags, quoted attributes, and text. */
  set innerHTML(html) {
    this.replaceChildren();
    const stack = [this];
    for (const [, closing, tag, attrs, text] of String(html).matchAll(
      /<(\/?)([a-z0-9]+)([^>]*)>|([^<]+)/gi,
    )) {
      const parent = stack.at(-1);
      if (text !== undefined) {
        parent.ownText += decode(text);
      } else if (closing) {
        stack.pop();
      } else {
        const element = new FakeElement(tag);
        for (const [, name, value] of attrs.matchAll(/([\w:-]+)(?:="([^"]*)")?/g)) {
          element.setAttribute(name, value === undefined ? "" : decode(value));
        }
        parent.append(element);
        stack.push(element);
      }
    }
  }
  set textContent(value) {
    this.replaceChildren();
    this.ownText = String(value);
  }
  /** What a sighted reader sees: nothing hidden and nothing for screen readers only. */
  get textContent() {
    return [
      this.ownText,
      ...this.children
        .filter((child) => !child.hidden && !child.classList.contains("sr-only"))
        .map((child) => child.textContent),
    ]
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
  }
}

const windowListeners = new Map();
global.window = globalThis;
global.addEventListener = (type, listener) => windowListeners.set(type, listener);
global.removeEventListener = (type) => windowListeners.delete(type);
global.innerHeight = 1000;
global.document = { createElement: (tag) => new FakeElement(tag) };
document.body = new FakeElement("body");
const originalWarn = console.warn;
console.warn = () => {};

const FILE_TYPES = {
  schemaVersion: 1,
  revision: 1,
  fingerprint: "session",
  groups: [
    { id: "code", label: "Code" },
    { id: "docs", label: "Documentation" },
    { id: "data", label: "Data" },
    { id: "other", label: "Other" },
  ],
  displayGroups: [
    { id: "docs", label: "Documentation" },
    { id: "code", label: "Code" },
    { id: "data", label: "Data" },
    { id: "other", label: "Other" },
  ],
  families: [
    { id: "python", label: "Python", groupId: "code", extensions: [".py"] },
    { id: "markdown", label: "Markdown", groupId: "docs", extensions: [".md"] },
    { id: "json", label: "JSON", groupId: "data", extensions: [".json"] },
  ],
  distributionKeyForExtension(extension) {
    const family = this.families.find((each) => each.extensions.includes(extension));
    return family ? `family:${family.id}` : extension;
  },
};

const tally = (allFiles, allBytes, files, bytes) => ({
  all: { files: allFiles, bytes: allBytes },
  unignored: { files, bytes },
});
const ZERO = tally(0, 0, 0, 0);
const file = (name, size, ext, gitignored = false) => ({
  type: "file",
  name,
  path: gitignored ? `docs/build/${name}` : `docs/${name}`,
  size,
  ext,
  gitignored,
  mtime: 1700000000,
});

/**
 * A folder of three families with the shape /api/rollup answers: two Markdown files, a
 * Python file and an ignored build folder holding another, and a JSON file. The legend is
 * the route's for this breakdown: every family above the share floor, by value and then
 * family ID.
 */
const ROLLUP = {
  path: "docs",
  index_status: "done",
  indexed_files: 5,
  max_files: 500000,
  truncated: false,
  node: {
    type: "dir",
    name: "docs",
    path: "docs",
    total_files: 5,
    unignored_files: 4,
    total_size: 850,
    unignored_size: 550,
    dominant_ext: ".py",
    state: "complete",
    children: [
      file("a.md", 100, ".md"),
      file("b.md", 100, ".md"),
      file("c.py", 300, ".py"),
      file("e.json", 50, ".json"),
      {
        type: "dir",
        name: "build",
        path: "docs/build",
        total_files: 1,
        unignored_files: 0,
        total_size: 300,
        unignored_size: 0,
        dominant_ext: ".py",
        gitignored: true,
        state: "complete",
        children: [file("d.py", 300, ".py", true)],
      },
    ],
  },
  file_type_breakdown: {
    schema: "file-type-breakdown-v1",
    registry: { schema_version: 1, revision: 1, fingerprint: "session" },
    metrics: tally(5, 850, 4, 550),
    groups: [
      {
        id: "docs",
        families: [
          {
            id: "markdown",
            metrics: tally(2, 200, 2, 200),
            extensions: [{ extension: ".md", metrics: tally(2, 200, 2, 200) }],
          },
        ],
      },
      {
        id: "code",
        families: [
          {
            id: "python",
            metrics: tally(2, 600, 1, 300),
            extensions: [{ extension: ".py", metrics: tally(2, 600, 1, 300) }],
          },
        ],
      },
      {
        id: "data",
        families: [
          {
            id: "json",
            metrics: tally(1, 50, 1, 50),
            extensions: [{ extension: ".json", metrics: tally(1, 50, 1, 50) }],
          },
        ],
      },
    ],
    no_extension: { metrics: ZERO, filenames: [], others: null },
    remaining_types: { metrics: ZERO, extensions: [], others: null },
  },
  file_type_legend: {
    schema: "file-type-legend-v1",
    limit: 5,
    minimum_share_percent: 1,
    files: {
      all: {
        total: 5,
        named: [
          { family: "markdown", value: 2 },
          { family: "python", value: 2 },
          { family: "json", value: 1 },
        ],
        other: 0,
      },
      unignored: {
        total: 4,
        named: [
          { family: "markdown", value: 2 },
          { family: "json", value: 1 },
          { family: "python", value: 1 },
        ],
        other: 0,
      },
    },
    bytes: {
      all: {
        total: 850,
        named: [
          { family: "python", value: 600 },
          { family: "markdown", value: 200 },
          { family: "json", value: 50 },
        ],
        other: 0,
      },
      unignored: {
        total: 550,
        named: [
          { family: "python", value: 300 },
          { family: "markdown", value: 200 },
          { family: "json", value: 50 },
        ],
        other: 0,
      },
    },
  },
};

(async () => {
  const folder = (name) =>
    pathToFileURL(path.join(__dirname, "../../src/metabrowser/builtin_plugins/folder", name)).href;
  const { registerTreemap } = await import(folder("treemap.js"));

  // The page's one tooltip, as the shell keeps it: what it shows and the element it is
  // anchored on, until a hide puts it away. A hide within an element puts away only a
  // tooltip anchored there (docs/design-system.md, "A Surface Puts Away Only Its Own
  // Tooltip"); a hide with nothing puts away whatever is up.
  const tooltip = { html: null, anchor: null };
  let rollupAnswer = null;
  let sumsListener = null;
  let render = null;
  const mb = {
    countClass: () => "",
    // The folder's sums from the directory index, which publishes them whenever a file under
    // the folder changes; a step hands them to the view.
    directoryTotals: {
      subscribe(_path, listener) {
        sumsListener = listener;
        return () => {
          sumsListener = null;
        };
      },
    },
    escapeHtml: (value) =>
      String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;"),
    fileTypeIcon: () => ({ className: "", svg: "" }),
    fileTypes: FILE_TYPES,
    formatFileCount: (value) =>
      `${value.toLocaleString("en-US")} ${value === 1 ? "file" : "files"}`,
    formatSize: (value) => `${value.toLocaleString("en-US")} B`,
    formatTimestamp: () => "2023-11-14",
    navigation: { open: async () => {} },
    registerView(kind, id, view) {
      assert(kind === "folder" && id === "treemap", `registered ${kind} ${id}`);
      render = view.render;
    },
    sizeClass: () => "",
    sourceKind: () => "filesystem",
    tooltip: {
      hide(within) {
        if (!within || within === tooltip.anchor || within.contains(tooltip.anchor)) {
          tooltip.html = null;
          tooltip.anchor = null;
        }
      },
      show(html, anchor) {
        tooltip.html = html;
        tooltip.anchor = anchor;
      },
    },
    viewState: { isActive: () => true, subscribeActive: () => () => {} },
    watchRollup(_scope, _options, onUpdate) {
      rollupAnswer = (envelope) => onUpdate(JSON.parse(JSON.stringify(envelope)));
      return { dispose() {}, refresh: async () => {}, stale: () => false };
    },
  };
  // The shared Files / Bytes and Show ignored state, as rollup-controls.js keeps it.
  let controlsState = { metric: "files", includeIgnored: true };
  const controlListeners = new Set();
  const controls = {
    get: () => controlsState,
    mount: () => () => {},
    set(next) {
      controlsState = { ...controlsState, ...next };
      for (const listener of [...controlListeners]) {
        listener(controlsState);
      }
    },
    subscribe(listener) {
      controlListeners.add(listener);
      return () => controlListeners.delete(listener);
    },
  };
  const palette = {
    classFor: (key) => (key ? "mb-distribution-mark" : "mb-distribution-other"),
    paint() {},
    styleFor: () => "",
  };
  registerTreemap(mb, palette, controls);

  const container = new FakeElement("div");
  document.body.append(container);
  const view = render(container, { path: "docs", raw: { dir: ROLLUP.node } });
  rollupAnswer(ROLLUP);

  const viewport = () => container.querySelector(".tm-viewport");
  const legendList = () => container.querySelector(".tm-legend");
  const entry = (label) =>
    legendList().children.find(
      (item) => item.querySelector(".file-type-summary-legend-label")?.textContent === label,
    );
  const cell = (cellPath) => viewport().querySelector(`[data-tm-path="${cellPath}"]`);
  /** The tally row a segment is drawn in, by its heading: Files, Ignored, or Total. */
  const rowOf = (segment) => segment.closest("tr").children[0].textContent;
  const segment = (row, key) =>
    container
      .querySelectorAll("[data-segment-key]")
      .find((each) => each.dataset.segmentKey === key && rowOf(each) === row);
  const name = (element) => {
    if (element === null) {
      return null;
    }
    if (element.dataset.legendKey !== undefined) {
      return `legend ${element.dataset.legendKey}`;
    }
    if (element.dataset.segmentKey !== undefined) {
      return `${rowOf(element)} ${element.dataset.segmentKey}`;
    }
    if (element.dataset.tmPath !== undefined) {
      // A cell says how it is marked: as one of the family an entry names, or as the cell
      // under the pointer, which alone shimmers.
      return "hovered" in element.dataset
        ? `cell ${element.dataset.tmPath} (${element.dataset.hovered})`
        : `cell ${element.dataset.tmPath}`;
    }
    return `not a mark: ${element.className}`;
  };
  /**
   * What is on screen of the legend and the hover: the legend's entries and the name a
   * screen reader gives it, every element marked as hovered in page order, the tooltip's
   * words, and what it is anchored on.
   */
  const read = () => ({
    legend: legendList().hidden ? "hidden" : legendList().textContent,
    legendName: legendList().getAttribute("aria-label"),
    marked: container.querySelectorAll("[data-hovered]").map(name),
    tooltip:
      tooltip.html === null
        ? null
        : tooltip.html
            .replace(/<br>/g, " / ")
            .replace(/<[^>]*>/g, "")
            .trim(),
    anchoredOn: name(tooltip.anchor),
  });
  const nothing = (reading) =>
    reading.marked.length === 0 && reading.tooltip === null && reading.anchoredOn === null;
  const transcript = {};

  const atRest = read();
  assert(
    atRest.legend === "Markdown 40% Python 40% JSON 20%" && nothing(atRest),
    `at rest: ${JSON.stringify(atRest)}`,
  );
  transcript["the legend under the tally bars, at rest"] = atRest;

  // A legend entry marks every cell of its family, the files of its type and the folder it
  // is the dominant type of, the family's segment in each tally row, and itself.
  entry("Python").emit("mouseenter");
  const onEntry = read();
  assert(
    JSON.stringify(onEntry.marked) ===
      JSON.stringify([
        "Files family:python",
        "Ignored family:python",
        "Total family:python",
        "legend family:python",
        "cell docs/c.py (family)",
        "cell docs/build (family)",
        "cell docs/build/d.py (family)",
      ]) &&
      onEntry.tooltip === "2 files · 600 B" &&
      onEntry.anchoredOn === "legend family:python",
    `the Python entry: ${JSON.stringify(onEntry)}`,
  );
  entry("Python").emit("mouseleave");
  const leftEntry = read();
  assert(nothing(leftEntry), `left the entry: ${JSON.stringify(leftEntry)}`);

  // A cell marks itself and its family's entry; its tooltip is its own. Crossing its own
  // label is not leaving it.
  const python = cell("docs/c.py");
  const label = python.querySelector(".tm-cell-label") ?? python;
  python.emit("mouseover");
  const onCell = read();
  // The pointer moves from the cell onto its label: the cell hears mouseout toward the
  // label, read before the label's mouseover arrives, so a leave there would show.
  python.emit("mouseout", { relatedTarget: label });
  const withinCell = read();
  label.emit("mouseover");
  assert(
    JSON.stringify(onCell.marked) ===
      JSON.stringify(["legend family:python", "cell docs/c.py (self)"]) &&
      onCell.anchoredOn === "cell docs/c.py (self)" &&
      onCell.tooltip.startsWith("docs/c.py / 1 file · 300 B"),
    `the c.py cell: ${JSON.stringify(onCell)}`,
  );
  assert(
    JSON.stringify(withinCell.marked) === JSON.stringify(onCell.marked),
    `crossing the cell's label: ${JSON.stringify(withinCell)}`,
  );
  label.emit("mouseout", { relatedTarget: container });
  const leftCell = read();
  assert(nothing(leftCell), `left the cell: ${JSON.stringify(leftCell)}`);

  // A folder is the color of its dominant type, so it keys to that family's entry.
  cell("docs/build").emit("mouseover");
  const onFolder = read();
  cell("docs/build").emit("mouseout", { relatedTarget: container });
  assert(
    JSON.stringify(onFolder.marked) ===
      JSON.stringify(["legend family:python", "cell docs/build (self)"]),
    `the build folder: ${JSON.stringify(onFolder)}`,
  );

  // The folder's sums arrive whenever a file changes, and redraw the bars alone. A cell
  // and an entry outlive that draw and hear nothing, so the bars enter their hover again.
  const SUMS = {
    total_files: 5,
    total_size: 850,
    unignored_files: 4,
    unignored_size: 550,
    state: "complete",
  };
  cell("docs/c.py").emit("mouseover");
  const barBefore = segment("Total", "family:python");
  sumsListener(SUMS);
  const sumsUnderCell = read();
  cell("docs/c.py").emit("mouseout", { relatedTarget: container });
  assert(
    segment("Total", "family:python") !== barBefore &&
      JSON.stringify(sumsUnderCell.marked) === JSON.stringify(onCell.marked) &&
      sumsUnderCell.anchoredOn === onCell.anchoredOn,
    `the sums redrew the bars under a cell: ${JSON.stringify(sumsUnderCell)}`,
  );
  entry("Python").emit("mouseenter");
  sumsListener(SUMS);
  const sumsUnderEntry = read();
  entry("Python").emit("mouseleave");
  assert(
    JSON.stringify(sumsUnderEntry) === JSON.stringify(onEntry),
    `the sums redrew the bars under the entry: ${JSON.stringify(sumsUnderEntry)}`,
  );

  // A segment marks itself and its family's entry, and no cell.
  segment("Total", "family:markdown").emit("mouseenter");
  const onSegment = read();
  segment("Total", "family:markdown").emit("mouseleave");
  assert(
    JSON.stringify(onSegment.marked) ===
      JSON.stringify(["Total family:markdown", "legend family:markdown"]) &&
      onSegment.tooltip === "Markdown / 2 files · 200 B" &&
      onSegment.anchoredOn === "Total family:markdown",
    `the Total row's Markdown segment: ${JSON.stringify(onSegment)}`,
  );

  // A layout replaces every cell. The entry outlives it, so its hover is drawn again on
  // the new cells; a cell's hover goes with its cell, until the browser enters the new one.
  entry("Markdown").emit("mouseenter");
  const markdownCellBefore = cell("docs/a.md");
  windowListeners.get("resize")();
  const relaidUnderEntry = read();
  assert(
    cell("docs/a.md") !== markdownCellBefore &&
      JSON.stringify(relaidUnderEntry.marked) ===
        JSON.stringify([
          "Files family:markdown",
          "Total family:markdown",
          "legend family:markdown",
          "cell docs/a.md (family)",
          "cell docs/b.md (family)",
        ]),
    `a layout under the Markdown entry: ${JSON.stringify(relaidUnderEntry)}`,
  );
  entry("Markdown").emit("mouseleave");
  cell("docs/e.json").emit("mouseover");
  windowListeners.get("resize")();
  const relaidUnderCell = read();
  assert(
    relaidUnderCell.marked.length === 0,
    `a layout under a cell kept its hover: ${JSON.stringify(relaidUnderCell)}`,
  );
  cell("docs/e.json").emit("mouseover");
  const reenteredCell = read();
  assert(
    JSON.stringify(reenteredCell.marked) ===
      JSON.stringify(["legend family:json", "cell docs/e.json (self)"]),
    `entering the redrawn cell: ${JSON.stringify(reenteredCell)}`,
  );
  cell("docs/e.json").emit("mouseout", { relatedTarget: container });

  // Show ignored turned off under the pointer rebuilds the legend, which lets go of the
  // hover the entry it removes held. The new entry's shares are of Files, and the map
  // drops the ignored folder.
  entry("Python").emit("mouseenter");
  controls.set({ includeIgnored: false });
  const toggled = read();
  assert(nothing(toggled), `Show ignored turned off under the entry: ${JSON.stringify(toggled)}`);
  entry("Python").emit("mouseenter");
  const filesOnly = read();
  assert(
    filesOnly.legend === "Markdown 50% JSON 25% Python 25%" &&
      filesOnly.legendName === "Share of Files (4 files)" &&
      JSON.stringify(filesOnly.marked) ===
        JSON.stringify([
          "Files family:python",
          "Ignored family:python",
          "Total family:python",
          "legend family:python",
          "cell docs/c.py (family)",
        ]) &&
      filesOnly.tooltip === "1 file · 300 B",
    `the Python entry without ignored files: ${JSON.stringify(filesOnly)}`,
  );

  // A refreshed rollup rebuilds the legend under the pointer and puts the hover away, and
  // the browser enters the rebuilt entry.
  rollupAnswer(ROLLUP);
  const refreshed = read();
  assert(
    nothing(refreshed),
    `a refresh under the entry kept its hover: ${JSON.stringify(refreshed)}`,
  );
  entry("Python").emit("mouseenter");
  const reentered = read();
  assert(
    JSON.stringify(reentered.marked) === JSON.stringify(filesOnly.marked),
    `entering the rebuilt entry: ${JSON.stringify(reentered)}`,
  );

  view.dispose();
  const disposed = read();
  assert(nothing(disposed), `disposal kept the hover: ${JSON.stringify(disposed)}`);

  Object.assign(transcript, {
    "pointer on the Python entry, Show ignored on": onEntry,
    "left the entry": leftEntry,
    "pointer on the c.py cell": onCell,
    "pointer across the c.py cell's own label": withinCell,
    "left the cell": leftCell,
    "pointer on the build folder": onFolder,
    "the folder's sums redrew the bars under the c.py cell": sumsUnderCell,
    "the folder's sums redrew the bars under the Python entry": sumsUnderEntry,
    "pointer on the Total row's Markdown segment": onSegment,
    "the map laid out again under the Markdown entry": relaidUnderEntry,
    "the map laid out again under the e.json cell": relaidUnderCell,
    "the browser entered the redrawn e.json cell": reenteredCell,
    "Show ignored turned off under the Python entry": toggled,
    "pointer on the Python entry, Show ignored off": filesOnly,
    "the rollup refreshed under the pointer": refreshed,
    "the browser entered the rebuilt entry": reentered,
    "the view disposed under the pointer": disposed,
  });
  console.warn = originalWarn;
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  console.warn = originalWarn;
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
