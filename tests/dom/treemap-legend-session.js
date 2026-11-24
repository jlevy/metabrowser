// Browserless session: the Treemap's file-type legend and the one hover its cells, tally
// bars, and legend share.
//
// The Treemap shows File Overview's legend under its tally bars (docs/design-system.md,
// "Folder Treemap"). A legend entry is a handle on its family's marks: pointing at it marks
// every cell of the family, the files of its types and the solid folders it is the dominant
// type of (a nested folder is neutral), its segment in every tally row, and the entry.
// Pointing at a cell or a segment marks it and its family's entry. There is one tooltip: the bars show an entry's, the counts of
// the family's segment in the tally row the legend's shares are of, anchored on the entry;
// a cell shows its own, anchored on the hover anchor the map puts over the cell under the
// pointer.
//
// The Treemap view, its tally bars, the legend, the hover, the map, the layout, and the
// legend model are the production modules, loaded whole. The document is a stand-in that
// parses the markup the view writes into elements, for the few calls they make on it, and
// `mb.watchRollup` hands the view the rollup each step names: one with the shape
// `/api/rollup` answers, which cli-api.tryscript.md pins. The map paints its cells on a
// canvas, which has no context here, so what it marks and which cell the pointer is on are
// read through `inspectTreemap`; the pointer is moved by mousemove events on the viewport
// at a cell's coordinates, as the browser sends them. Each step prints the legend, what is
// marked as hovered, the cell under the pointer and whether it shimmers, the tooltip's
// words, and what it is anchored on. Exits 1 on a failed invariant.

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

// As the shell's hideTooltipWithin (static/app.js): a hide within any element puts away a
// tooltip whose anchor has left the page, since nothing else would.
function connected(node, within) {
  const rootOf = (each) => {
    let top = each;
    while (top.parentNode) {
      top = top.parentNode;
    }
    return top;
  };
  return !node || rootOf(node) === rootOf(within);
}

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

/** The size the map's viewport measures, which a step narrows and widens again. */
const viewportBox = { width: 800, height: 600 };

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
  appendChild(child) {
    this.append(child);
    return child;
  }
  insertBefore(child, reference) {
    child.remove();
    const at = this.children.indexOf(reference);
    child.parentNode = this;
    this.children.splice(at === -1 ? this.children.length : at, 0, child);
    return child;
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
   * What the browser would dispatch for *type* with this element as its target, to this
   * element's own listeners: the legend's mouseenter and mouseleave, and the map's
   * viewport, which takes every pointer and key event itself. Returns the event, to read
   * whether a listener took it.
   */
  emit(type, init = {}) {
    const event = {
      type,
      target: this,
      altKey: false,
      ctrlKey: false,
      metaKey: false,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...init,
    };
    for (const listener of [...(this.listeners[type] ?? [])]) {
      listener(event);
    }
    return event;
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
  /** The map's viewport, 800 by 600 under the page's chrome; nothing else is measured. */
  getBoundingClientRect() {
    return this.classList.contains("tm-viewport")
      ? { top: 120, left: 0, ...viewportBox }
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
// One device pixel per CSS pixel, so the map's paint list is the same on every host.
global.devicePixelRatio = 1;
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
/** The deepest cell containing (x, y): of the cells containing a point, the last emitted. */
function deepestAt(cells, x, y) {
  for (let i = cells.length - 1; i >= 0; i -= 1) {
    const cell = cells[i];
    if (x >= cell.x && x < cell.x + cell.w && y >= cell.y && y < cell.y + cell.h) {
      return i;
    }
  }
  return -1;
}

/**
 * A point in cell `index`'s own area, outside its children: its center when no child
 * covers it, else the first pixel center, row by row, that none does.
 */
function ownPointOf(cells, index) {
  const cell = cells[index];
  const center = { x: cell.x + cell.w / 2, y: cell.y + cell.h / 2 };
  if (deepestAt(cells, center.x, center.y) === index) {
    return center;
  }
  for (let y = Math.floor(cell.y) + 0.5; y < cell.y + cell.h; y += 1) {
    for (let x = Math.floor(cell.x) + 0.5; x < cell.x + cell.w; x += 1) {
      if (deepestAt(cells, x, y) === index) {
        return { x, y };
      }
    }
  }
  throw new Error(`no point of ${cell.path} is its own`);
}

(async () => {
  const folder = (name) =>
    pathToFileURL(path.join(__dirname, "../../src/metabrowser/builtin_plugins/folder", name)).href;
  const { registerTreemap } = await import(folder("treemap.js"));
  // The module the view's map is, so its inspection reads the mounted map.
  const { inspectTreemap } = await import(folder("treemap-map.js"));

  // The page's one tooltip, as the shell keeps it: what it shows and the element it is
  // anchored on, until a hide puts it away. A hide within an element puts away only a
  // tooltip anchored there (docs/design-system.md, "A Surface Puts Away Only Its Own
  // Tooltip"); a hide with nothing puts away whatever is up.
  const tooltip = { html: null, anchor: null };
  const navigation = [];
  let rollupAnswer = null;
  /** What the view's current watch asks the route for, beyond the tree's shape. */
  let asked = null;
  /** The tree without its gitignored nodes, as the route emits it for ignored=exclude. */
  const withoutIgnored = (node) => ({
    ...node,
    children: Array.isArray(node.children)
      ? node.children.filter((child) => !child.gitignored).map(withoutIgnored)
      : node.children,
  });
  /** The tree in the compact encoding: a folder's files as `[name, size, mtime, ext, gitignored]`. */
  const compacted = (node) => {
    if (!Array.isArray(node.children)) {
      return node;
    }
    const files = node.children.filter((child) => child.type === "file");
    return {
      ...node,
      children: node.children.filter((child) => child.type !== "file").map(compacted),
      files: files.map((file) => [
        file.name,
        file.size,
        file.mtime ?? null,
        file.ext,
        file.gitignored ? 1 : 0,
      ]),
    };
  };
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
    // The age the SDK's formatter gives the fixtures' 2023-11-14 timestamps, fixed so the
    // session reads the same on any day.
    formatAge: () => ({ label: "3y ago", className: "age-old" }),
    navigation: {
      open: async (target, options) => {
        navigation.push(options ? [target.path, options.viewId] : [target.path]);
      },
    },
    registerView(kind, id, view) {
      assert(kind === "folder" && id === "treemap", `registered ${kind} ${id}`);
      render = view.render;
    },
    sizeClass: () => "",
    sizeHtml: (value) => `<span class="size">${value.toLocaleString("en-US")} B</span>`,
    sourceKind: () => "filesystem",
    tooltip: {
      hide(within) {
        if (
          !within ||
          !connected(tooltip.anchor, within) ||
          within === tooltip.anchor ||
          within.contains(tooltip.anchor)
        ) {
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
    // Answers as the route does: without the gitignored nodes when asked to leave them
    // out, and in the compact encoding when asked for it, which the view decodes.
    watchRollup(_scope, options, onUpdate) {
      asked = { nodes: options.nodes, encoding: options.encoding, ignored: options.ignored };
      rollupAnswer = (envelope) => {
        let node = options.ignored === "exclude" ? withoutIgnored(envelope.node) : envelope.node;
        /** @type {Record<string, any>} */
        let answer = { ...envelope, node };
        if (options.encoding === "compact") {
          node = compacted(node);
          answer = { ...envelope, encoding: "compact", node };
        }
        onUpdate(JSON.parse(JSON.stringify(answer)));
      };
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
  const map = () => inspectTreemap(viewport());
  const legendList = () => container.querySelector(".tm-legend");
  const entry = (label) =>
    legendList().children.find(
      (item) => item.querySelector(".file-type-summary-legend-label")?.textContent === label,
    );
  /** The tally row a segment is drawn in, by its heading: Files, Ignored, or Total. */
  const rowOf = (segment) => segment.closest("tr").children[0].textContent;
  const segment = (row, key) =>
    container
      .querySelectorAll("[data-segment-key]")
      .find((each) => each.dataset.segmentKey === key && rowOf(each) === row);

  /** The index of the drawn folder or file cell at `cellPath`. */
  const cellIndex = (cellPath) => {
    const index = map().cells.findIndex((cell) => cell.path === cellPath && cell.kind !== "rest");
    assert(index >= 0, `${cellPath} is drawn`);
    return index;
  };
  /** The client coordinates of a point in the viewport's box, which has no border. */
  const client = ({ x, y }) => {
    const rect = viewport().getBoundingClientRect();
    return { clientX: rect.left + x, clientY: rect.top + y };
  };
  /** Move the pointer onto `at`, or a point of the cell at `cellPath` that is its own. */
  const pointAt = (cellPath, at) => {
    const index = cellIndex(cellPath);
    const point = at ?? ownPointOf(map().cells, index);
    viewport().emit("mousemove", client(point));
    assert(map().hovered === index, `the pointer is on ${cellPath}`);
    return point;
  };
  const leaveMap = () => viewport().emit("mouseleave");
  const clickAt = (cellPath) =>
    viewport().emit("click", client(ownPointOf(map().cells, cellIndex(cellPath))));

  const name = (element) => {
    if (element === null) {
      return null;
    }
    if (element.classList.contains("tm-hover-anchor")) {
      const cells = map()?.cells;
      return cells && viewport().contains(element)
        ? `the anchor over ${cells[Number(element.dataset.tmCell)].path}`
        : "a detached hover anchor";
    }
    if (element.dataset.legendKey !== undefined) {
      return `legend ${element.dataset.legendKey}`;
    }
    if (element.dataset.segmentKey !== undefined) {
      return `${rowOf(element)} ${element.dataset.segmentKey}`;
    }
    return `not a mark: ${element.className}`;
  };
  /**
   * What is on screen of the legend and the hover: the legend's entries and the name a
   * screen reader gives it; what is marked as hovered, the bars' segments and the legend's
   * entries in page order and then the cells the map marks in layout order; the cell under
   * the pointer and whether its anchor shimmers, which a folder's does not; the tooltip's
   * words; and what it is anchored on.
   */
  const read = () => {
    const drawn = map();
    // A disposed map is the host's to take away, with whatever it left in the viewport.
    const anchors = drawn ? viewport().querySelectorAll(".tm-hover-anchor") : [];
    const hovered = drawn?.hovered ?? -1;
    assert(anchors.length <= 1, "one hover anchor at most");
    assert((anchors.length === 1) === hovered >= 0, "an anchor while a cell is under the pointer");
    if (hovered >= 0) {
      assert(Number(anchors[0].dataset.tmCell) === hovered, "the anchor is the hovered cell's");
    }
    return {
      legend: legendList().hidden ? "hidden" : legendList().textContent,
      legendName: legendList().getAttribute("aria-label"),
      marked: [
        ...container
          .querySelectorAll("[data-hovered]")
          .filter((element) => !element.classList.contains("tm-hover-anchor"))
          .map(name),
        ...(drawn?.marked ?? []).map((index) => `cell ${drawn.cells[index].path}`),
      ],
      pointer: hovered >= 0 ? `cell ${drawn.cells[hovered].path}` : null,
      shimmers: hovered >= 0 && anchors[0].dataset.hovered === "self",
      tooltip:
        tooltip.html === null
          ? null
          : tooltip.html
              .replace(/<br>/g, " / ")
              .replace(/<\/div><div/g, " / <div")
              .replace(/<[^>]*>/g, "")
              .trim(),
      anchoredOn: name(tooltip.anchor),
    };
  };
  const nothing = (reading) =>
    reading.marked.length === 0 &&
    reading.pointer === null &&
    reading.tooltip === null &&
    reading.anchoredOn === null;
  const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
  const transcript = {};

  const atRest = read();
  assert(
    atRest.legend === "Markdown 40% Python 40% JSON 20%" && nothing(atRest),
    `at rest: ${JSON.stringify(atRest)}`,
  );
  transcript["the legend under the tally bars, at rest"] = atRest;

  // Each label shows a size only when the whole of it fits,
  // at most 0.62 em a character (VALUE_CHAR_EM) inside the cell's 5 px padding. In a pane
  // too narrow for a size, the label keeps its name and leaves the size out.
  const labelsNow = () =>
    viewport()
      .querySelectorAll(".tm-label-cell")
      .map((element) => {
        const cell = map().cells[Number(element.dataset.tmCell)];
        const sub = element.querySelector(".tm-cell-sub");
        const size = sub ? sub.textContent : null;
        assert(
          size === null || size.length * cell.valuePx * 0.62 <= cell.w - 1 - 10,
          `${cell.path}'s size fits whole: ${size} in ${cell.w}`,
        );
        return `${cell.path} ${Math.round(cell.w)}x${Math.round(cell.h)} ${size ?? "(no size)"}`;
      })
      .sort();
  const wideLabels = labelsNow();
  viewportBox.width = 56;
  windowListeners.get("resize")();
  const narrowLabels = labelsNow();
  assert(
    narrowLabels.some((each) => each.endsWith("(no size)")) &&
      narrowLabels.some((each) => !each.endsWith("(no size)")),
    `a narrow pane leaves out the sizes that do not fit: ${JSON.stringify(narrowLabels)}`,
  );
  // A nested folder narrower than 140 px keeps its size beside its name where the size
  // and the smallest name fit (FOLDER_TITLE_GAP_PX), not by a fixed width.
  viewportBox.width = 120;
  windowListeners.get("resize")();
  const midLabels = labelsNow();
  const midBuild = midLabels.find((each) => each.startsWith("docs/build "));
  assert(
    midBuild !== undefined &&
      /^docs\/build (\d+)x\d+ 1 file$/.test(midBuild) &&
      Number(/ (\d+)x/.exec(midBuild)[1]) < 140,
    `a nested folder under 140 px keeps its size: ${JSON.stringify(midLabels)}`,
  );
  viewportBox.width = 800;
  windowListeners.get("resize")();
  assert(same(labelsNow(), wideLabels), "the pane widened again draws its labels again");
  transcript["each label at 800 px and at 56 px wide"] = {
    wide: wideLabels,
    middle: midLabels,
    narrow: narrowLabels,
  };

  // A legend entry marks every cell of its family: the files of its type, and no nested
  // folder, whose header and frame are neutral since it holds many types (the outer box
  // and docs/build here). It marks the family's segment in each tally row, and itself.
  entry("Python").emit("mouseenter");
  const onEntry = read();
  assert(
    same(onEntry.marked, [
      "Files family:python",
      "Ignored family:python",
      "Total family:python",
      "legend family:python",
      "cell docs/c.py",
      "cell docs/build/d.py",
    ]) &&
      onEntry.pointer === null &&
      onEntry.tooltip === "2 files · 600 B" &&
      onEntry.anchoredOn === "legend family:python",
    `the Python entry: ${JSON.stringify(onEntry)}`,
  );
  entry("Python").emit("mouseleave");
  const leftEntry = read();
  assert(nothing(leftEntry), `left the entry: ${JSON.stringify(leftEntry)}`);

  // A cell marks itself and its family's entry; its tooltip is its own, anchored on the
  // anchor the map puts over it. Moving within the cell, over its label, is not leaving it.
  const cellPoint = pointAt("docs/c.py");
  const cellAnchor = tooltip.anchor;
  const onCell = read();
  assert(
    same(onCell.marked, ["legend family:python", "cell docs/c.py"]) &&
      onCell.pointer === "cell docs/c.py" &&
      onCell.shimmers &&
      onCell.anchoredOn === "the anchor over docs/c.py" &&
      onCell.tooltip === "docs/c.py / 300 B / modified 3y ago",
    `the c.py cell: ${JSON.stringify(onCell)}`,
  );
  const python = map().cells[cellIndex("docs/c.py")];
  assert(map().labels.includes(cellIndex("docs/c.py")), "the c.py cell is labelled");
  pointAt("docs/c.py", { x: python.x + 3, y: python.y + 3 });
  const withinCell = read();
  assert(
    same(withinCell, onCell) && tooltip.anchor === cellAnchor,
    `moving over the cell's label: ${JSON.stringify(withinCell)}`,
  );
  leaveMap();
  const leftCell = read();
  assert(nothing(leftCell), `left the cell: ${JSON.stringify(leftCell)}`);

  // A nested folder is neutral, so it keys to no family's entry and marks only itself. A
  // folder lifts without the shimmer, which would cover its children. Its child under the pointer
  // is the deepest cell there, and takes the hover.
  pointAt("docs/build");
  const onFolder = read();
  assert(
    same(onFolder.marked, ["cell docs/build"]) &&
      !onFolder.shimmers &&
      onFolder.anchoredOn === "the anchor over docs/build",
    `the build folder: ${JSON.stringify(onFolder)}`,
  );
  pointAt("docs/build/d.py");
  const onChild = read();
  assert(
    same(onChild.marked, ["legend family:python", "cell docs/build/d.py"]) &&
      onChild.shimmers &&
      onChild.anchoredOn === "the anchor over docs/build/d.py",
    `the build folder's file: ${JSON.stringify(onChild)}`,
  );
  leaveMap();

  // A click opens the deepest cell under it: a file in the view the file opens in, and a
  // folder in the Treemap.
  clickAt("docs/build/d.py");
  clickAt("docs/build");
  clickAt("docs/e.json");
  const clicked = [...navigation];
  assert(
    same(clicked, [["docs/build/d.py"], ["docs/build", "treemap"], ["docs/e.json"]]),
    `clicks: ${JSON.stringify(clicked)}`,
  );
  navigation.length = 0;

  // The folder's sums arrive whenever a file changes, and redraw the bars alone. A cell
  // and an entry outlive that draw and hear nothing, so the bars enter their hover again.
  const SUMS = {
    total_files: 5,
    total_size: 850,
    unignored_files: 4,
    unignored_size: 550,
    state: "complete",
  };
  pointAt("docs/c.py", cellPoint);
  const barBefore = segment("Total", "family:python");
  sumsListener(SUMS);
  const sumsUnderCell = read();
  leaveMap();
  assert(
    segment("Total", "family:python") !== barBefore && same(sumsUnderCell, onCell),
    `the sums redrew the bars under a cell: ${JSON.stringify(sumsUnderCell)}`,
  );
  entry("Python").emit("mouseenter");
  sumsListener(SUMS);
  const sumsUnderEntry = read();
  entry("Python").emit("mouseleave");
  assert(
    same(sumsUnderEntry, onEntry),
    `the sums redrew the bars under the entry: ${JSON.stringify(sumsUnderEntry)}`,
  );

  // A segment marks itself and its family's entry, and no cell.
  segment("Total", "family:markdown").emit("mouseenter");
  const onSegment = read();
  segment("Total", "family:markdown").emit("mouseleave");
  assert(
    same(onSegment.marked, ["Total family:markdown", "legend family:markdown"]) &&
      onSegment.tooltip === "Documentation / Markdown / 2 files · 200 B" &&
      onSegment.anchoredOn === "Total family:markdown",
    `the Total row's Markdown segment: ${JSON.stringify(onSegment)}`,
  );

  // A layout replaces every cell. The entry outlives it, so its hover is drawn again on
  // the new cells.
  entry("Markdown").emit("mouseenter");
  const cellsBefore = map().cells;
  windowListeners.get("resize")();
  const relaidUnderEntry = read();
  assert(
    map().cells !== cellsBefore &&
      same(relaidUnderEntry.marked, [
        "Files family:markdown",
        "Total family:markdown",
        "legend family:markdown",
        "cell docs/a.md",
        "cell docs/b.md",
      ]),
    `a layout under the Markdown entry: ${JSON.stringify(relaidUnderEntry)}`,
  );
  entry("Markdown").emit("mouseleave");

  // A canvas raises no mouseover when what is under a still pointer changes, so a layout
  // asks which cell is under the pointer and points at it, on a new anchor: the same cell
  // after a layout that moves nothing, and the cell now there after one that does.
  const stillPoint = pointAt("docs/e.json");
  const jsonAnchor = tooltip.anchor;
  windowListeners.get("resize")();
  const relaidUnderCell = read();
  assert(
    same(relaidUnderCell.marked, ["legend family:json", "cell docs/e.json"]) &&
      relaidUnderCell.anchoredOn === "the anchor over docs/e.json" &&
      tooltip.anchor !== jsonAnchor &&
      !viewport().contains(jsonAnchor),
    `a layout under the e.json cell: ${JSON.stringify(relaidUnderCell)}`,
  );
  controls.set({ metric: "size" });
  const remeasured = read();
  const nowUnder = map().cells[deepestAt(map().cells, stillPoint.x, stillPoint.y)];
  assert(
    remeasured.pointer === `cell ${nowUnder.path}` &&
      nowUnder.path !== "docs/e.json" &&
      remeasured.anchoredOn === `the anchor over ${nowUnder.path}` &&
      remeasured.tooltip.startsWith(nowUnder.path),
    `the measure switched under the e.json cell: ${JSON.stringify(remeasured)}`,
  );
  controls.set({ metric: "files" });
  const measuredBack = read();
  assert(
    same(measuredBack, relaidUnderCell),
    `the measure switched back under the pointer: ${JSON.stringify(measuredBack)}`,
  );
  leaveMap();

  // The keyboard: one focus proxy, the map's one control, which the arrows move over every
  // folder and file cell in layout order; Enter opens the cell it is on, and Backspace the
  // enclosing folder's Treemap.
  const proxy = viewport().querySelector(".tm-focus");
  const keyed = map();
  const focusOrder = keyed.focusOrder.map((index) => keyed.cells[index].path);
  const proxyAt = () => ({
    on: map().focused >= 0 ? map().cells[map().focused].path : null,
    label: proxy.getAttribute("aria-label"),
  });
  const keys = [{ key: "(none)", ...proxyAt() }];
  /** @param {string} key */
  const press = (key) => {
    const before = map();
    const event = viewport().emit("keydown", { key });
    const after = map();
    const step = { ArrowRight: 1, ArrowLeft: -1 }[key] ?? 0;
    assert(
      after.focused === before.focusOrder[before.focusOrder.indexOf(before.focused) + step] &&
        event.defaultPrevented,
      `${key} on the focus proxy: ${JSON.stringify(proxyAt())}`,
    );
    keys.push({ key, ...proxyAt() });
  };
  for (const key of ["ArrowRight", "ArrowRight", "ArrowLeft"]) {
    press(key);
  }
  // Then to the folder, wherever the layout put it in the order, so Enter opens a folder.
  const folderAt = focusOrder.indexOf("docs/build");
  while (focusOrder.indexOf(proxyAt().on ?? "") !== folderAt) {
    press(focusOrder.indexOf(proxyAt().on ?? "") < folderAt ? "ArrowRight" : "ArrowLeft");
  }
  press("Enter");
  press("Backspace");
  const keyboard = {
    proxy: {
      role: proxy.getAttribute("role"),
      tabindex: proxy.getAttribute("tabindex"),
      hidden: proxy.hidden,
      controls: viewport().querySelectorAll('[role="button"]').length,
    },
    focusOrder,
    keys,
    navigation: [...navigation],
  };
  assert(
    keyboard.proxy.role === "button" &&
      keyboard.proxy.tabindex === "0" &&
      !keyboard.proxy.hidden &&
      keyboard.proxy.controls === 1 &&
      navigation.length === 2 &&
      same(navigation[0], ["docs/build", "treemap"]) &&
      same(navigation[1], ["", "treemap"]),
    `the keyboard: ${JSON.stringify(keyboard)}`,
  );
  navigation.length = 0;

  // Show ignored turned off under the pointer rebuilds the legend, which lets go of the
  // hover the entry it removes held, and asks again for the tree without its ignored
  // nodes. The new entry's shares are of Files, and the map drops the ignored folder.
  const askedFirst = asked;
  entry("Python").emit("mouseenter");
  controls.set({ includeIgnored: false });
  const toggled = { ...read(), asked };
  assert(
    nothing(toggled) &&
      same(askedFirst, { nodes: "max", encoding: "compact", ignored: "include" }) &&
      same(asked, { nodes: "max", encoding: "compact", ignored: "exclude" }),
    `Show ignored turned off under the entry: ${JSON.stringify({ askedFirst, toggled })}`,
  );
  entry("Python").emit("mouseenter");
  const filesOnly = read();
  assert(
    filesOnly.legend === "Markdown 50% JSON 25% Python 25%" &&
      filesOnly.legendName === "Share of Files (4 files)" &&
      same(filesOnly.marked, [
        "Files family:python",
        "Ignored family:python",
        "Total family:python",
        "legend family:python",
        "cell docs/c.py",
      ]) &&
      filesOnly.tooltip === "1 file · 300 B",
    `the Python entry without ignored files: ${JSON.stringify(filesOnly)}`,
  );

  // The tree without ignored nodes, or a refresh of it, rebuilds the legend under the
  // pointer and puts the hover away, and the browser enters the rebuilt entry.
  rollupAnswer(ROLLUP);
  const refreshed = read();
  assert(
    nothing(refreshed),
    `a refresh under the entry kept its hover: ${JSON.stringify(refreshed)}`,
  );
  entry("Python").emit("mouseenter");
  const reentered = read();
  assert(
    same(reentered.marked, filesOnly.marked),
    `entering the rebuilt entry: ${JSON.stringify(reentered)}`,
  );

  // Disposed with the pointer on a cell: the view lets go of the cell's hover and puts
  // away its own tooltip.
  entry("Python").emit("mouseleave");
  pointAt("docs/e.json");
  const beforeDispose = read();
  assert(beforeDispose.pointer === "cell docs/e.json", "the pointer is on a cell at disposal");
  view.dispose();
  const disposedMap = inspectTreemap(viewport());
  const disposed = {
    ...read(),
    inspectable: disposedMap !== null,
    viewportListeners: Object.values(viewport().listeners).reduce(
      (count, listeners) => count + listeners.length,
      0,
    ),
  };
  assert(
    nothing(disposed) && !disposed.inspectable && disposed.viewportListeners === 0,
    `disposal kept the hover: ${JSON.stringify(disposed)}`,
  );

  Object.assign(transcript, {
    "pointer on the Python entry, Show ignored on": onEntry,
    "left the entry": leftEntry,
    "pointer on the c.py cell": onCell,
    "pointer moved within the c.py cell, over its label": withinCell,
    "left the map": leftCell,
    "pointer on the build folder's frame": onFolder,
    "pointer on the build folder's file": onChild,
    "clicked the d.py cell, the build folder's frame, and the e.json cell": clicked,
    "the folder's sums redrew the bars under the c.py cell": sumsUnderCell,
    "the folder's sums redrew the bars under the Python entry": sumsUnderEntry,
    "pointer on the Total row's Markdown segment": onSegment,
    "the map laid out again under the Markdown entry": relaidUnderEntry,
    "the map laid out again under a still pointer on the e.json cell": relaidUnderCell,
    "the measure switched to Bytes under the still pointer": remeasured,
    "the measure switched back to Files under the still pointer": measuredBack,
    "the keyboard on the focus proxy": keyboard,
    "Show ignored turned off under the Python entry": toggled,
    "pointer on the Python entry, Show ignored off": filesOnly,
    "the rollup refreshed under the pointer": refreshed,
    "the browser entered the rebuilt entry": reentered,
    "the view disposed with the pointer on the e.json cell": disposed,
  });
  console.warn = originalWarn;
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  console.warn = originalWarn;
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
