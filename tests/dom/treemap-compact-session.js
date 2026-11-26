// Run the production compact treemap (treemap-compact.js, over treemap-map.js and
// treemap-layout.js) through its states. Its box follows the section breakdown's answers:
// kept with a skeleton while the index scans, without asking for the deep tree; left out
// when the breakdown's request failed, the index stopped at its cap, or the folder holds no
// files in the population shown; and drawn once the index has settled and the map's own
// rollup answers, inside an outer box for the folder itself. It follows the section's legend
// hover, measure, Show ignored, and the tab's activation; a cell opens the Treemap view at its
// folder, and the outer box at the folder itself, by pointer or by the focus proxy's keys; a
// layout under a still pointer points at the cell under it now; a failed rollup keeps the
// box and recovers on Retry. Disposal releases every listener, the watch, the observer, and
// the hover, and puts away only the map's own tooltip.
//
// The DOM is a stand-in for the calls the map makes: elements it creates and appends, and
// a viewport with a measured box and a 1 px border. The map paints on a canvas, which has
// no context here, so the session reads what the map drew through `inspectTreemap`, the
// layout, paint list, labels, focus, pointer, and marks, and the elements it keeps in the
// DOM: the label layer, the focus proxy, and the hover anchor. Pointer events go to the
// viewport at a cell's coordinates, as the browser sends them.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

const folder = (name) =>
  pathToFileURL(path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/folder", name));

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.listeners = new Map();
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.hidden = false;
    this.className = "";
    const names = () => this.className.split(" ").filter(Boolean);
    this.classList = {
      add: (name) => {
        if (!names().includes(name)) {
          this.className = [...names(), name].join(" ");
        }
      },
      remove: (name) =>
        (this.className = names()
          .filter((each) => each !== name)
          .join(" ")),
      contains: (name) => names().includes(name),
    };
    this._html = "";
    this.clientWidth = 0;
    this.clientHeight = 0;
    this.clientLeft = 0;
    this.clientTop = 0;
  }
  /** Markup replaces the children; the session reads placeholders back as text. */
  set innerHTML(html) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this._html = String(html);
  }
  get innerHTML() {
    return this._html;
  }
  appendChild(node) {
    node.remove();
    node.parentNode = this;
    this.children.push(node);
    return node;
  }
  insertBefore(node, reference) {
    node.remove();
    const at = this.children.indexOf(reference);
    node.parentNode = this;
    this.children.splice(at === -1 ? this.children.length : at, 0, node);
    return node;
  }
  append(...nodes) {
    for (const node of nodes) {
      this.appendChild(node);
    }
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }
  contains(node) {
    for (let each = node; each; each = each.parentNode) {
      if (each === this) {
        return true;
      }
    }
    return false;
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  getAttribute(name) {
    return name in this.attributes ? this.attributes[name] : null;
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }
  removeEventListener(type, listener) {
    if (this.listeners.get(type) === listener) {
      this.listeners.delete(type);
    }
  }
  /** What the browser dispatches on this element; returns the event, to read defaultPrevented. */
  dispatch(type, init = {}) {
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
    this.listeners.get(type)?.(event);
    return event;
  }
  /** The border box: the client box and a border of clientLeft and clientTop on each side. */
  getBoundingClientRect() {
    return {
      width: this.clientWidth + 2 * this.clientLeft,
      height: this.clientHeight + 2 * this.clientTop,
      top: 0,
      left: 0,
    };
  }
  closest() {
    return null;
  }
  /** The first descendant carrying `className`. */
  find(className) {
    for (const child of this.children) {
      if (child.className.split(" ").includes(className)) {
        return child;
      }
      const deeper = child.find(className);
      if (deeper) {
        return deeper;
      }
    }
    return null;
  }
}

const EXTENSION_FAMILIES = { ".py": "python", ".md": "markdown" };

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

function file(name, filePath, size, ext, gitignored = false) {
  return { name, path: filePath, type: "file", size, ext, gitignored, mtime: 1 };
}

function dir(name, dirPath, children, gitignored = false) {
  const sum = (pick) => children.reduce((total, c) => total + pick(c), 0);
  const files = sum((c) => (c.type === "dir" ? c.total_files : 1));
  const size = sum((c) => (c.type === "dir" ? c.total_size : c.size));
  const unignoredFiles = sum((c) => (c.type === "dir" ? c.unignored_files : c.gitignored ? 0 : 1));
  const unignoredSize = sum((c) =>
    c.type === "dir" ? c.unignored_size : c.gitignored ? 0 : c.size,
  );
  const counts = {};
  for (const c of children) {
    const ext = c.type === "dir" ? c.dominant_ext : c.ext;
    counts[ext] = (counts[ext] || 0) + (c.type === "dir" ? c.total_files : 1);
  }
  const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
  return {
    name,
    path: dirPath,
    type: "dir",
    state: "complete",
    total_files: files,
    total_size: size,
    unignored_files: unignoredFiles,
    unignored_size: unignoredSize,
    gitignored,
    dominant_ext: dominant,
    mtime: 1,
    children,
  };
}

const TREE = dir("src", "src", [
  dir("lib", "src/lib", [
    file("app.py", "src/lib/app.py", 6000, ".py"),
    file("util.py", "src/lib/util.py", 3000, ".py"),
    file("cli.py", "src/lib/cli.py", 2000, ".py"),
  ]),
  dir("docs", "src/docs", [
    file("guide.md", "src/docs/guide.md", 3000, ".md"),
    file("notes.md", "src/docs/notes.md", 1500, ".md"),
  ]),
  file("README.md", "src/README.md", 2500, ".md"),
  file("cache.md", "src/cache.md", 9000, ".md", true),
]);
// One large file and smaller ones, halving: the larger have room for their names, the
// smaller for their icons alone, and the smallest for neither.
const DWINDLING = dir("src", "src", [
  file("main.py", "src/main.py", 64000, ".py"),
  ...Array.from({ length: 10 }, (_, n) =>
    file(`part${n}.md`, `src/part${n}.md`, Math.round(16000 / 2 ** n), ".md"),
  ),
]);
// Files of one size in a mixed order, with one larger: the larger leads, and the rest,
// tied, group by the family that colors them (JSON, Markdown, Python), the one with no
// extension last, then by name whatever its case.
const TIED = dir("src", "src", [
  file("zeta.py", "src/zeta.py", 1000, ".py"),
  file("Makefile", "src/Makefile", 1000, ""),
  file("beta.md", "src/beta.md", 1000, ".md"),
  file("big.py", "src/big.py", 4000, ".py"),
  file("Alpha.py", "src/Alpha.py", 1000, ".py"),
  file("alpha.md", "src/alpha.md", 1000, ".md"),
  file("data.json", "src/data.json", 1000, ".json"),
]);
const ONLY_IGNORED = dir("src", "src", [file("cache.md", "src/cache.md", 9000, ".md", true)]);
const EMPTY = dir("src", "src", []);

/** What the section's breakdown is told: its tally rollup has the folder's node, no tree. */
const breakdownAnswer = (indexStatus, tree, nodeState = "complete") => ({
  index_status: indexStatus,
  node: { ...tree, children: null, state: nodeState },
});

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

/** The box a layer element is placed in, from its inline style, as the map writes it. */
function styleBox(element) {
  const match =
    /left:([\d.]+)px;top:([\d.]+)px;width:([\d.]+)px;height:([\d.]+)px/.exec(
      element.getAttribute("style") ?? "",
    ) ?? [];
  return match.slice(1, 5).map(Number);
}

/** The box the map places a cell's layer elements in: its rectangle, one pixel short. */
function cellBox(cell) {
  return [cell.x, cell.y, Math.max(0, cell.w - 1), Math.max(0, cell.h - 1)].map((value) =>
    Number(value.toFixed(1)),
  );
}

async function main() {
  // A failed rollup is logged; the session reports those lines as data instead.
  const warnings = [];
  console.warn = (message) => warnings.push(String(message));
  const { createDistributionHover } = await import(folder("distribution-hover.js"));
  const { mountCompactTreemap } = await import(folder("treemap-compact.js"));
  // The module the map is, so its inspection reads the mounted map.
  const { inspectTreemap } = await import(folder("treemap-map.js"));

  // One device pixel per CSS pixel, so the paint list is the same on every host.
  global.window = { devicePixelRatio: 1 };
  global.document = { createElement: (tag) => new FakeElement(tag) };
  const observers = [];
  global.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
      this.observed = [];
      this.disconnected = false;
      observers.push(this);
    }
    observe(element) {
      this.observed.push(element);
    }
    disconnect() {
      this.disconnected = true;
    }
  };

  /** One mount: its rollup watch, navigation, tooltip, and controls. */
  function mount({ width = 600 } = {}) {
    const navigation = [];
    const tooltipHides = [];
    const tooltipShows = [];
    // The page's one tooltip: what it shows and its anchor, until a hide puts it away. A
    // hide within an element puts away only a tooltip anchored there.
    const tooltip = { html: null, anchor: null };
    const watch = { options: null, apply: null, disposed: false, refreshes: 0, stale: false };
    let controlsState = { metric: "size", includeIgnored: true };
    const controlListeners = new Set();
    const activeListeners = new Set();
    const mb = {
      escapeHtml: (value) =>
        String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;"),
      fileTypeIcon: (name) => ({
        svg: `<svg class="${name.split(".").pop()}"></svg>`,
        className: "",
      }),
      // As the taxonomy (file-type-taxonomy.js): no extension is the remaining types'
      // key, "", and an extension of no family is its own key.
      fileTypes: {
        distributionKeyForExtension: (ext) =>
          ext === "(none)" ? "" : (EXTENSION_FAMILIES[ext] ?? ext),
      },
      formatFileCount: (count) => `${count} files`,
      formatSize: (bytes) => `${bytes} B`,
      formatTimestamp: () => "then",
      ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
        label: "then",
        className: "age-old",
      })),
      countClass: () => "",
      sizeHtml: (bytes) => `<span class="size">${bytes} B</span>`,
      navigation: { open: (...args) => navigation.push(args) },
      sourceKind: () => "filesystem",
      tooltip: {
        show(html, anchor) {
          tooltipShows.push(anchor);
          tooltip.html = html;
          tooltip.anchor = anchor;
        },
        hide(within) {
          tooltipHides.push(within);
          if (!within || !connected(tooltip.anchor, within) || within.contains(tooltip.anchor)) {
            tooltip.html = null;
            tooltip.anchor = null;
          }
        },
      },
      viewState: {
        isActive: () => true,
        subscribeActive(_element, listener) {
          activeListeners.add(listener);
          return () => activeListeners.delete(listener);
        },
      },
      watchRollup(scope, options, apply) {
        assert.equal(scope, "src");
        assert.equal(watch.options, null, "the map asks for its tree once");
        watch.options = options;
        watch.apply = apply;
        return {
          dispose() {
            watch.disposed = true;
          },
          refresh: async () => {
            watch.refreshes += 1;
          },
          stale: () => watch.stale,
        };
      },
    };
    const controls = {
      get: () => controlsState,
      subscribe(listener) {
        controlListeners.add(listener);
        return () => controlListeners.delete(listener);
      },
    };
    const palette = { classFor: (key) => `c-${key}`, styleFor: () => "", paint() {} };
    const hover = createDistributionHover();
    const container = new FakeElement("div");
    // The box the stylesheet gives the compact map, inside its 1 px border; set before the
    // mount, as the stylesheet sizes it before the first paint.
    const created = document.createElement;
    document.createElement = (tag) => {
      const element = created(tag);
      element.clientWidth = width;
      element.clientHeight = 218;
      element.clientLeft = 1;
      element.clientTop = 1;
      return element;
    };
    const handle = mountCompactTreemap(container, { path: "src" }, mb, palette, controls, {
      hover,
    });
    document.createElement = created;
    const viewport = container.children[0];
    const page = {
      handle,
      container,
      viewport,
      hover,
      watch,
      navigation,
      tooltip,
      tooltipShows,
      tooltipHides,
      controlListeners,
      activeListeners,
      inspect: () => inspectTreemap(viewport),
      setControls(next) {
        controlsState = next;
        for (const listener of [...controlListeners]) {
          listener(next);
        }
      },
      activate() {
        for (const listener of [...activeListeners]) {
          listener(true);
        }
      },
      resize(nextWidth) {
        viewport.clientWidth = nextWidth;
        for (const observer of observers) {
          if (observer.observed.includes(viewport)) {
            observer.callback();
          }
        }
      },
      /** The index of the drawn folder or file cell at `cellPath`. */
      cellAt(cellPath) {
        const index = page
          .inspect()
          .cells.findIndex((cell) => cell.path === cellPath && cell.kind !== "rest");
        assert.ok(index >= 0, `${cellPath} is drawn`);
        return index;
      },
      /** The client coordinates of a point in the viewport's padding box. */
      client({ x, y }) {
        const rect = viewport.getBoundingClientRect();
        return {
          clientX: rect.left + viewport.clientLeft + x,
          clientY: rect.top + viewport.clientTop + y,
        };
      },
      /** Move the pointer onto a point of the cell at `cellPath` that is its own. */
      pointAt(cellPath, at) {
        const index = page.cellAt(cellPath);
        const point = at ?? ownPointOf(page.inspect().cells, index);
        viewport.dispatch("mousemove", page.client(point));
        assert.equal(page.inspect().hovered, index, `the pointer is on ${cellPath}`);
        return point;
      },
      clickAt(cellPath) {
        viewport.dispatch(
          "click",
          page.client(ownPointOf(page.inspect().cells, page.cellAt(cellPath))),
        );
      },
      key(key) {
        return viewport.dispatch("keydown", { key });
      },
    };
    return page;
  }

  /** The label layer's elements, by the path of the cell each labels. */
  const labelled = (page) => {
    const map = page.inspect();
    const layer = page.viewport.find("tm-labels");
    if (!map || !layer) {
      return [];
    }
    // A relayout keeps the labels it can and appends the new ones, so the layer's order is
    // not the layout's; each label is placed by its own box.
    const indexes = layer.children
      .map((element) => {
        const index = Number(element.dataset.tmCell);
        const cell = map.cells[index];
        assert.ok(
          element.className.split(" ").includes(`tm-${cell.kind}`),
          "a label takes its cell's kind",
        );
        assert.deepEqual(styleBox(element), cellBox(cell), `${cell.path}'s label sits on its cell`);
        if (cell.kind === "file") {
          assert.ok(
            element.innerHTML.includes("tm-cell-file-icon"),
            `${cell.path}'s name sits under its icon`,
          );
        }
        return index;
      })
      .sort((a, b) => a - b);
    assert.deepEqual(indexes, map.labels, "the label layer holds the labels the map reports");
    return indexes.map((index) => map.cells[index].path);
  };

  /** The glyph size an icon's markup carries, which the map sized to its cell. */
  const glyphOf = (html) => {
    const match = /--icon-glyph:([0-9.]+)px/.exec(html);
    return match ? Number(match[1]) : null;
  };

  /**
   * The cells too small for a label that show their icon alone, by path and glyph
   * size: each the size the map reports for it (inspectTreemap's glyphs), drawn on the
   * icons canvas at its place (iconRects), a square of that size inside its cell's fill,
   * and no element in the label layer.
   */
  const iconsOnly = (page) => {
    const map = page.inspect();
    const layer = page.viewport.find("tm-labels");
    if (!map || !layer) {
      return [];
    }
    const dpr = map.dpr;
    const entries = map.iconRects.map((rect) => {
      const cell = map.cells[rect.cell];
      const glyph = map.glyphs.find((each) => each.cell === rect.cell);
      assert.ok(glyph?.alone, `${cell.path}'s icon is reported as alone`);
      assert.equal(rect.w, Math.round(glyph.px * dpr), `${cell.path}'s icon is drawn at its size`);
      assert.equal(rect.w, rect.h, "square");
      const left = Math.round(cell.x * dpr);
      const top = Math.round(cell.y * dpr);
      const right = Math.round((cell.x + cell.w) * dpr);
      const bottom = Math.round((cell.y + cell.h) * dpr);
      assert.ok(
        rect.x >= left && rect.y >= top && rect.x + rect.w <= right && rect.y + rect.h <= bottom,
        `${cell.path}'s icon sits inside its cell`,
      );
      assert.ok(!map.labels.includes(rect.cell), `${cell.path} has no label too`);
      return `${cell.path} ${glyph.px}px`;
    });
    assert.deepEqual(
      map.iconRects.map((rect) => rect.cell),
      map.icons.map((icon) => icon.cell),
      "the icons canvas draws the icons the map reports",
    );
    assert.ok(
      !layer.children.some(
        (element) => element.dataset.tmCell && !element.className.includes("tm-label-cell"),
      ),
      "the label layer holds labels alone",
    );
    return entries;
  };

  /** The labelled cells that show their icon before their name, by path and glyph size. */
  const labelIcons = (page) => {
    const map = page.inspect();
    const layer = page.viewport.find("tm-labels");
    if (!map || !layer) {
      return [];
    }
    return layer.children
      .filter((element) => element.className.split(" ").includes("tm-label-cell"))
      .filter((element) => element.innerHTML.includes("tm-cell-file-icon"))
      .map((element) => {
        const index = Number(element.dataset.tmCell);
        const glyph = map.glyphs.find((each) => each.cell === index);
        assert.ok(
          glyph && !glyph.alone,
          `${map.cells[index].path}'s icon is reported over its label`,
        );
        assert.equal(glyphOf(element.innerHTML), glyph.px, "it is drawn at its size");
        return { index, entry: `${map.cells[index].path} ${glyph.px}px` };
      })
      .sort((a, b) => a.index - b.index)
      .map((each) => each.entry);
  };

  /** The focus proxy: the one control, over the focused cell, named for it. */
  const focusProxy = (page) => {
    const map = page.inspect();
    const proxy = page.viewport.find("tm-focus");
    if (!map || !proxy) {
      return null;
    }
    if (map.focused >= 0) {
      assert.equal(Number(proxy.dataset.tmCell), map.focused, "the proxy is on the focused cell");
      assert.deepEqual(styleBox(proxy), cellBox(map.cells[map.focused]), "the proxy covers it");
    }
    return {
      role: proxy.getAttribute("role"),
      tabindex: proxy.getAttribute("tabindex"),
      hidden: proxy.hidden,
      on: map.focused >= 0 ? map.cells[map.focused].path : null,
      label: proxy.getAttribute("aria-label"),
    };
  };

  /** The hover anchor: at most one, over the cell under the pointer, and the tooltip's anchor. */
  const pointer = (page) => {
    const map = page.inspect();
    const anchors = page.viewport.children.filter((element) =>
      element.className.split(" ").includes("tm-hover-anchor"),
    );
    assert.ok(anchors.length <= 1, "one hover anchor at most");
    const anchor = anchors[0] ?? null;
    assert.equal(anchor !== null, (map?.hovered ?? -1) >= 0, "an anchor while a cell is hovered");
    // The two marks canvases cross-fade: a hover that marks other cells draws them on the
    // canvas not shown and shows it, as the other fades out (styles.css, .tm-marks).
    const marksCanvases = page.viewport.children.filter((element) =>
      element.className.split(" ").includes("tm-marks"),
    );
    const shownMarks = marksCanvases.filter((element) =>
      element.className.split(" ").includes("tm-marks-shown"),
    );
    assert.ok(shownMarks.length <= 1, "one marks canvas shown at most");
    const marks = {
      shown: shownMarks.length ? marksCanvases.indexOf(shownMarks[0]) : null,
      ops: (map?.markOps ?? []).map((op) => `${op.op} ${map.cells[op.cell].path}`),
    };
    if (!anchor) {
      return { on: null, anchor: null, marks, cursor: page.viewport.style.cursor || "" };
    }
    const cell = map.cells[map.hovered];
    assert.equal(Number(anchor.dataset.tmCell), map.hovered, "the anchor is the hovered cell's");
    assert.deepEqual(styleBox(anchor), cellBox(cell), "the anchor covers its cell");
    return {
      on: cell.path,
      anchor: anchor.className,
      shimmers: anchor.dataset.hovered === "self",
      tooltip:
        page.tooltip.anchor === anchor
          ? page.tooltip.html
              .replace(/<br>/g, " / ")
              .replace(/<\/div><div/g, " / <div")
              .replace(/<[^>]*>/g, "")
          : null,
      marked: map.marked.map((index) => map.cells[index].path),
      marks,
      cursor: page.viewport.style.cursor,
    };
  };

  const summary = (page) => {
    const map = page.inspect();
    return {
      hidden: page.container.hidden,
      skeleton: page.viewport.innerHTML.includes("tm-loading"),
      unavailable: page.viewport.innerHTML.includes("Treemap unavailable."),
      asked: page.watch.options !== null,
      cells: (map?.cells ?? []).map(
        (cell) => `${cell.kind} ${cell.path} ${cell.w.toFixed(0)}x${cell.h.toFixed(0)}`,
      ),
      labelled: labelled(page),
    };
  };
  const drawn = (page) => (page.inspect()?.cells.length ?? 0) > 0;
  const steps = [];

  // ── a folder whose index settles ──────────────────────────────
  const page = mount();
  steps.push({ step: "mounted, before the breakdown answers", ...summary(page) });

  page.handle.follow(breakdownAnswer("scanning", TREE, "pending"));
  steps.push({ step: "the breakdown says the index is still scanning", ...summary(page) });

  page.handle.follow(breakdownAnswer("done", TREE));
  steps.push({
    step: "the breakdown says the index has finished",
    request: {
      depth: page.watch.options.depth,
      top: page.watch.options.top,
      ext_rank: page.watch.options.ext_rank,
    },
    ...summary(page),
  });

  page.watch.apply({ index_status: "done", node: TREE });
  // Every cell is painted inside the border: the map lays out to the client box, not to the
  // bounding box, which is larger by the border and pushed edge cells under it. What is
  // painted is the paint list, in device pixels, which reaches the client box's edge.
  const arrived = page.inspect();
  const deviceBox = [page.viewport.clientWidth, page.viewport.clientHeight].map((side) =>
    Math.round(side * arrived.dpr),
  );
  const reach = arrived.paint.reduce(
    (most, rect) => [Math.max(most[0], rect.x + rect.w), Math.max(most[1], rect.y + rect.h)],
    [0, 0],
  );
  const insideBorder =
    reach[0] <= deviceBox[0] && reach[1] <= deviceBox[1] && reach[0] >= deviceBox[0] - 1;
  steps.push({
    step: "the map's tree arrives",
    insideBorder,
    layers: page.viewport.children.map(
      (element) => `${element.tagName.toLowerCase()}.${element.className}`,
    ),
    paint: { rects: arrived.paint.length, empty: arrived.empty, dpr: arrived.dpr },
    focus: focusProxy(page),
    ...summary(page),
  });

  const refreshing = mount();
  refreshing.handle.follow(breakdownAnswer("done", TREE));
  refreshing.watch.apply({ index_status: "done", node: TREE });
  const canvas = refreshing.viewport.children[0];
  refreshing.key("ArrowRight");
  const focusedPath = (map) => map.cells[map.focused].path;
  const selected = focusedPath(refreshing.inspect());
  const oldPaths = refreshing.inspect().cells.map((cell) => cell.path);
  await refreshing.handle.refresh();
  refreshing.handle.follow(breakdownAnswer("scanning", TREE, "pending"));
  refreshing.watch.apply({ index_status: "scanning", node: null });
  assert.equal(refreshing.viewport.children[0], canvas, "a pending rollup keeps the old canvas");
  assert.deepEqual(
    refreshing.inspect().cells.map((cell) => cell.path),
    oldPaths,
  );
  const changed = dir("src", "src", [...TREE.children, file("new.py", "src/new.py", 4000, ".py")]);
  refreshing.watch.apply({ index_status: "done", node: changed });
  refreshing.handle.follow(breakdownAnswer("done", changed));
  assert.equal(refreshing.viewport.children[0], canvas, "the completed rollup reuses the canvas");
  assert.ok(refreshing.inspect().cells.some((cell) => cell.path === "src/new.py"));
  assert.equal(focusedPath(refreshing.inspect()), selected, "refresh keeps the chosen cell");
  steps.push({
    step: "refresh keeps the old map until the completed rollup arrives",
    refreshes: refreshing.watch.refreshes,
    previousTreeKeptWhileScanning: true,
    sameCanvasPaintsTheChangedTree: true,
    focusedCellKept: selected,
  });
  refreshing.handle.dispose();

  const entry = { tag: "legend-entry" };
  page.hover.enter({ population: "all", key: "python", anchor: entry, marks: "family" });
  const onEntry = page.inspect();
  steps.push({
    step: "pointing at the Python legend entry",
    marked: onEntry.marked.map((index) => onEntry.cells[index].path),
    markOps: onEntry.markOps.map((op) => `${op.op} ${onEntry.cells[op.cell].path}`),
  });
  page.hover.leave({ population: "all", key: "python", anchor: entry, marks: "family" });
  assert.equal(page.inspect().marked.length, 0, "leaving the entry clears the marks");

  // The pointer over a cell: an anchor of its own carries the tooltip and the shimmer, and
  // the cell's hover marks it. Moving within the cell changes nothing; moving on to another
  // cell gives that one a new anchor; leaving the map takes it all away.
  page.pointAt("src/lib/app.py");
  const appAnchor = page.tooltip.anchor;
  steps.push({ step: "the pointer on the app.py cell", pointer: pointer(page) });
  const appCell = arrived.cells[page.cellAt("src/lib/app.py")];
  page.pointAt("src/lib/app.py", { x: appCell.x + 2, y: appCell.y + 2 });
  assert.equal(page.tooltip.anchor, appAnchor, "moving within a cell keeps its anchor");
  assert.equal(page.tooltipShows.length, 1, "and shows no tooltip again");
  page.pointAt("src/README.md");
  assert.ok(!page.viewport.contains(appAnchor), "the last cell's anchor is gone");
  assert.notEqual(page.tooltip.anchor, appAnchor, "the tooltip has a new anchor");
  steps.push({ step: "the pointer moves on to the README.md cell", pointer: pointer(page) });
  // A folder's own hover lifts its header and frame: its fill is copied and its interior,
  // the separators between its files, cleared, so no edge between them changes.
  page.pointAt("src/lib");
  steps.push({ step: "the pointer on the lib folder's header", pointer: pointer(page) });
  // The same tree again under the still pointer lays the map out again and enters the
  // same cell: its lift stays on the canvas that shows it, with no fade out and in.
  const liftBefore = pointer(page).marks;
  page.watch.apply({ index_status: "done", node: TREE });
  assert.deepEqual(
    pointer(page).marks,
    liftBefore,
    "a relayout keeps an unchanged lift where it is",
  );
  page.viewport.dispatch("mouseleave");
  assert.equal(page.tooltip.anchor, null, "leaving the map puts the tooltip away");
  assert.equal(page.hover.current(), null, "and lets go of the cell's hover");
  steps.push({ step: "the pointer leaves the map", pointer: pointer(page) });

  for (const target of ["src/lib/app.py", "src/docs", "src/README.md"]) {
    page.clickAt(target);
  }
  steps.push({
    step: "clicking two file cells and a folder cell opens the Treemap at their folders",
    navigation: [...page.navigation],
  });

  // The folder's own cell is the outer box around the rest, and opens the Treemap at it.
  const outer = arrived.cells[0];
  assert.equal(outer.path, "src");
  assert.ok(
    outer.x <= 1 && outer.y <= 1 && outer.w >= page.viewport.clientWidth - 2,
    "the box spans the map",
  );
  assert.ok(outer.h >= page.viewport.clientHeight - 2, "the box spans the map's height");
  page.navigation.length = 0;
  page.clickAt("src");
  steps.push({
    step: "clicking the outer box opens the Treemap at the folder",
    outerBox: outer.nested ? "labelled, around the tree" : "solid",
    navigation: [...page.navigation],
  });

  // The keyboard: one focus proxy, which the arrows move over every folder and file cell in
  // layout order, and Enter activates. The compact map has no enclosing folder to go to.
  page.navigation.length = 0;
  const keys = [];
  for (const key of ["ArrowRight", "ArrowRight", "ArrowLeft"]) {
    const before = page.inspect();
    const at = before.focusOrder.indexOf(before.focused);
    const event = page.key(key);
    const after = page.inspect();
    assert.equal(
      after.focused,
      before.focusOrder[at + (key === "ArrowLeft" ? -1 : 1)],
      `${key} moves the focus along the order`,
    );
    keys.push(`${key}${event.defaultPrevented ? "" : " (not taken)"} -> ${focusProxy(page).label}`);
  }
  const enter = page.key("Enter");
  const backspace = page.key("Backspace");
  const focusOrder = page.inspect();
  steps.push({
    step: "the keyboard",
    focusOrder: focusOrder.focusOrder.map((index) => focusOrder.cells[index].path),
    keys,
    enter: { taken: enter.defaultPrevented, navigation: [...page.navigation] },
    backspace: { taken: backspace.defaultPrevented },
  });

  // A canvas raises no mouseover when what is under a still pointer changes, so a layout
  // asks which cell is under the pointer and points at it, with a new anchor.
  const still = page.pointAt("src/cache.md");
  const stillAnchor = page.tooltip.anchor;
  const before = pointer(page);
  page.setControls({ metric: "files", includeIgnored: true });
  const relaid = page.inspect();
  const under = deepestAt(relaid.cells, still.x, still.y);
  assert.equal(relaid.hovered, under, "the layout points at the cell under the pointer");
  assert.notEqual(relaid.cells[under].path, before.on, "a different cell than before");
  assert.ok(!page.viewport.contains(stillAnchor), "the old cell's anchor is gone");
  steps.push({
    step: "the measure switches to Files under a still pointer",
    pointerBefore: before,
    pointerAfter: pointer(page),
    ...summary(page),
  });
  page.viewport.dispatch("mouseleave");

  page.setControls({ metric: "files", includeIgnored: false });
  steps.push({ step: "Show ignored is turned off", ...summary(page) });

  page.watch.stale = true;
  page.activate();
  steps.push({
    step: "the tab is shown again after a change while hidden",
    refreshes: page.watch.refreshes,
  });

  const drawnCells = page.inspect().cells;
  const drawnLayers = [...page.viewport.children];
  const chosenCell = focusedPath(page.inspect());
  await page.handle.refresh();
  page.watch.options.onError(new Error("refresh failed"));
  assert.equal(page.inspect().cells, drawnCells, "a failed refresh keeps the map's layout");
  assert.deepEqual(page.viewport.children, drawnLayers, "and its layers");
  assert.equal(focusedPath(page.inspect()), chosenCell, "a failed refresh keeps the chosen cell");
  const notice = page.container.find("tm-status");
  assert.ok(notice?.classList.contains("notice"), "a failed refresh shows a notice");
  assert.equal(notice.textContent, "Could not refresh the treemap. Showing the previous data.");
  assert.equal(notice.getAttribute("role"), "status", "the notice can be announced");
  assert.equal(notice.dataset.severity, "warning");
  steps.push({
    step: "a refresh fails after a complete answer",
    notice: notice.textContent,
    ...summary(page),
  });

  await page.handle.refresh();
  page.handle.follow(breakdownAnswer("scanning", TREE, "pending"));
  page.watch.apply({ index_status: "scanning", node: null });
  assert.equal(
    notice.classList.contains("notice"),
    true,
    "an intermediate answer keeps the notice",
  );
  assert.equal(page.inspect().cells, drawnCells, "and keeps the previous map");
  page.watch.apply({ index_status: "done", node: changed });
  page.handle.follow(breakdownAnswer("done", changed));
  assert.equal(
    notice.classList.contains("notice"),
    false,
    "a successful terminal answer dismisses the notice",
  );
  assert.equal(notice.textContent, "");
  assert.equal(page.viewport.children[0], drawnLayers[0], "the new map uses the same canvas");
  assert.ok(page.inspect().cells.some((cell) => cell.path === "src/new.py"));
  assert.equal(focusedPath(page.inspect()), chosenCell, "recovery keeps the chosen cell");

  // Disposal with the pointer on a cell: the cell's hover is let go of, and the map's own
  // tooltip, anchored inside the map, is the one put away.
  page.pointAt("src/lib/util.py");
  const before2 = page.tooltipHides.length;
  page.handle.dispose();
  page.handle.dispose();
  steps.push({
    step: "disposed with the pointer on a cell",
    viewportListeners: [...page.viewport.listeners.keys()],
    controlListeners: page.controlListeners.size,
    activeListeners: page.activeListeners.size,
    watchDisposed: page.watch.disposed,
    observerDisconnected: observers[0].disconnected,
    hoverReleased: page.hover.current() === null,
    inspectable: page.inspect() !== null,
    tooltipHides: page.tooltipHides.length - before2,
    hidOwnTooltipOnly: page.tooltipHides.at(-1) === page.container && page.tooltip.anchor === null,
  });

  // ── the breakdown's request fails, and Retry recovers ─────────
  const retried = mount();
  retried.handle.follow(null);
  steps.push({ step: "the breakdown's request fails", ...summary(retried) });
  retried.handle.refresh();
  retried.handle.follow(breakdownAnswer("done", TREE));
  retried.watch.apply({ index_status: "done", node: TREE });
  steps.push({
    step: "Retry: the breakdown answers, and the map follows",
    hidden: retried.container.hidden,
    drawn: drawn(retried),
  });
  retried.handle.dispose();

  // ── the map's own first rollup fails, and Retry recovers ──────
  const failing = mount();
  failing.handle.follow(breakdownAnswer("done", TREE));
  failing.watch.options.onError(new Error("no rollup"));
  steps.push({ step: "the map's first rollup fails", ...summary(failing) });
  failing.handle.refresh();
  failing.watch.apply({ index_status: "done", node: TREE });
  steps.push({
    step: "Retry: the map asks again, and its tree arrives",
    refreshes: failing.watch.refreshes,
    hidden: failing.container.hidden,
    drawn: drawn(failing),
  });
  failing.handle.dispose();

  // ── an index stopped at its cap before finishing this folder ──
  const capped = mount();
  capped.handle.follow(breakdownAnswer("truncated", TREE, "pending"));
  steps.push({ step: "the index stopped at its cap mid-folder", ...summary(capped) });
  capped.handle.dispose();

  // ── an empty folder, and one whose files are all ignored ──────
  const empty = mount();
  empty.handle.follow(breakdownAnswer("done", EMPTY));
  steps.push({ step: "the folder is empty", ...summary(empty) });
  empty.handle.dispose();

  const ignored = mount();
  ignored.setControls({ metric: "size", includeIgnored: false });
  ignored.handle.follow(breakdownAnswer("done", ONLY_IGNORED));
  steps.push({ step: "every file is ignored, and Show ignored is off", ...summary(ignored) });
  ignored.setControls({ metric: "size", includeIgnored: true });
  steps.push({ step: "Show ignored is turned on", ...summary(ignored) });
  ignored.handle.dispose();

  // ── files too small for their names ───────────────────────────
  const dwindling = mount();
  dwindling.setControls({ metric: "size", includeIgnored: false });
  dwindling.handle.follow(breakdownAnswer("done", DWINDLING));
  dwindling.watch.apply({ index_status: "done", node: DWINDLING });
  const shown = summary(dwindling);
  const iconCells = iconsOnly(dwindling);
  const iconPaths = iconCells.map((each) => each.split(" ")[0]);
  steps.push({
    step: "icons shrink with their cells: over a name, alone, and the smallest neither",
    cells: shown.cells,
    labelled: shown.labelled,
    labelIcons: labelIcons(dwindling),
    iconsOnly: iconCells,
    bare: shown.cells
      .map((each) => each.split(" ")[1])
      .filter(
        (each) => each !== "src" && !shown.labelled.includes(each) && !iconPaths.includes(each),
      ),
  });
  dwindling.handle.dispose();

  // ── files of one size, grouped by type ─────────────────────────
  // Value orders the cells, so no size changes; a tie breaks by family, then extension,
  // then name, so one color's cells sit together. The same files sent in reverse lay
  // out alike.
  const tied = mount();
  tied.setControls({ metric: "size", includeIgnored: false });
  tied.handle.follow(breakdownAnswer("done", TIED));
  tied.watch.apply({ index_status: "done", node: TIED });
  const tiedOrder = summary(tied).cells.filter((each) => each.startsWith("file "));
  tied.handle.dispose();
  const reversed = mount();
  reversed.setControls({ metric: "size", includeIgnored: false });
  const TIED_REVERSED = { ...TIED, children: [...TIED.children].reverse() };
  reversed.handle.follow(breakdownAnswer("done", TIED_REVERSED));
  reversed.watch.apply({ index_status: "done", node: TIED_REVERSED });
  assert.deepEqual(
    summary(reversed).cells.filter((each) => each.startsWith("file ")),
    tiedOrder,
    "the rollup's order changes nothing",
  );
  reversed.handle.dispose();
  steps.push({
    step: "files of one size group by family, then by extension and name",
    cells: tiedOrder,
  });

  // ── a box too small to draw in yet ────────────────────────────
  const narrow = mount({ width: 6 });
  narrow.handle.follow(breakdownAnswer("done", TREE));
  narrow.watch.apply({ index_status: "done", node: TREE });
  steps.push({ step: "the box is too narrow to draw in", ...summary(narrow) });
  narrow.resize(600);
  steps.push({
    step: "the pane widens",
    hidden: narrow.container.hidden,
    drawn: drawn(narrow),
  });
  narrow.handle.dispose();

  console.log(JSON.stringify({ steps, warnings }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
