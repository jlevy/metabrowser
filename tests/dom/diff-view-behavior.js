// Render checks for the diff view, deliberately lighter than the model
// tests: the data plane is pinned by the corpus and the CLI goldens, so
// this only asserts the projection — line rows, numbering, availability
// states, metadata-only changes, the per-file disclosure bar, and
// disposal.

const fs = require("node:fs");
const path = require("node:path");
const { registerHooks } = require("node:module");
const { pathToFileURL } = require("node:url");

// The Diff summary's tree module fails to load while this is set, as a dropped connection
// would make it (A3 of review A on #448).
let summaryModuleFails = false;
registerHooks({
  load(url, context, nextLoad) {
    if (summaryModuleFails && /\/diff-summary\.js(?:\?|$)/.test(url)) {
      throw new Error("the module did not load");
    }
    return nextLoad(url, context);
  },
});

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

class FakeClassList {
  /** @param {FakeElement} owner */
  constructor(owner) {
    this.owner = owner;
  }

  _set() {
    return new Set(this.owner.className.split(" ").filter(Boolean));
  }

  _write(set) {
    this.owner.className = [...set].join(" ");
  }

  toggle(name, force) {
    const set = this._set();
    const want = force === undefined ? !set.has(name) : force;
    if (want) {
      set.add(name);
    } else {
      set.delete(name);
    }
    this._write(set);
    return want;
  }

  contains(name) {
    return this._set().has(name);
  }
}

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.textContent = "";
    this.innerHTML = "";
    this.title = "";
    this.dataset = {};
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new FakeClassList(this);
  }

  /** Text appended as a string, as `Element.append` takes it, is a text node of its own. */
  append(...nodes) {
    for (const given of nodes) {
      let node = given;
      if (typeof given === "string") {
        node = new FakeElement("#text");
        node.textContent = given;
      }
      node.parentNode = this;
      this.children.push(node);
    }
  }

  replaceChildren(...nodes) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this.textContent = "";
    this.append(...nodes);
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  addEventListener(type, handler) {
    const handlers = this.listeners.get(type) ?? [];
    handlers.push(handler);
    this.listeners.set(type, handlers);
  }

  removeEventListener(type, handler) {
    this.listeners.set(
      type,
      (this.listeners.get(type) ?? []).filter((candidate) => candidate !== handler),
    );
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  dispatch(type) {
    // Bubbles like the real event: handlers up the ancestor chain all
    // see the original target, and any of them can stop it.
    let stopped = false;
    const event = {
      target: this,
      stopPropagation() {
        stopped = true;
      },
    };
    for (let node = this; node && !stopped; node = node.parentNode) {
      for (const handler of node.listeners.get(type) ?? []) {
        handler(event);
      }
    }
  }

  click() {
    this.dispatch("click");
  }

  pointerDown() {
    this.dispatch("pointerdown");
  }

  contains(candidate) {
    for (let node = candidate; node; node = node.parentNode) {
      if (node === this) {
        return true;
      }
    }
    return false;
  }

  closest(selector) {
    for (let node = this; node; node = node.parentNode) {
      if (selector.startsWith("[") && node.attributes.has(selector.slice(1, -1))) {
        return node;
      }
      if (selector.startsWith(".") && node.classList.contains(selector.slice(1))) {
        return node;
      }
    }
    return null;
  }

  *walk() {
    yield this;
    for (const child of this.children) {
      yield* child.walk();
    }
  }

  find(className) {
    return [...this.walk()].filter((node) => node.classList.contains(className));
  }

  text() {
    return [...this.walk()]
      .map((node) => node.textContent)
      .filter(Boolean)
      .join("\n");
  }

  /** The element's text as a document reads it: its leaves' text, in order, joined. */
  reads() {
    return this.children.length === 0
      ? this.textContent
      : this.children.map((child) => child.reads()).join("");
  }
}

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function tokenLines(source, className) {
  return source.split("\n").map((text) => [{ classes: [`hljs-${className}`], text }]);
}

function renderedText(host) {
  return host.children.length === 0
    ? host.textContent
    : host.children.map((child) => child.textContent).join("");
}

function tooLargeAnswer(byName) {
  const answer = JSON.parse(JSON.stringify(byName.get("deferred-manifest-only")));
  answer.manifest.files[0].availability = "too_large";
  answer.patches = {};
  return answer;
}

/**
 * An element with the layout a windowed tree reads: a style, a box, siblings, and focus.
 * The Diff summary's tree is drawn into these, with every row one row tall.
 */
class LaidOutElement extends FakeElement {
  constructor(tag) {
    super(tag);
    this.style = {
      setProperty(name, value) {
        this[name] = value;
      },
    };
    this.offsetHeight = 0;
  }

  /** A class set as an attribute is the element's class, as in a document. */
  setAttribute(name, value) {
    super.setAttribute(name, value);
    if (name === "class") {
      this.className = String(value);
    }
  }

  replaceChildren(...nodes) {
    super.replaceChildren();
    this.append(...nodes);
  }

  get firstElementChild() {
    return this.children[0] ?? null;
  }

  get nextElementSibling() {
    const siblings = this.parentNode?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
  }

  get isConnected() {
    return this.parentNode !== null;
  }

  after(node) {
    node.remove();
    const siblings = this.parentNode.children;
    siblings.splice(siblings.indexOf(this) + 1, 0, node);
    node.parentNode = this.parentNode;
  }

  insertBefore(node, before) {
    node.remove();
    const at = before === null ? this.children.length : this.children.indexOf(before);
    this.children.splice(at, 0, node);
    node.parentNode = this;
  }

  getBoundingClientRect() {
    return this.box ?? { top: 0, bottom: 0, left: 0, right: 0, width: 0, height: 0 };
  }

  focus() {
    global.document.activeElement = this;
  }

  scrollIntoView() {}
}

/** A key on an element's listener, with Command, Control, or Option as *chord* names. */
function press(element, key, chord = null) {
  let prevented = false;
  for (const handler of element.listeners.get("keydown") ?? []) {
    handler({
      key,
      altKey: chord === "altKey",
      ctrlKey: chord === "ctrlKey",
      metaKey: chord === "metaKey",
      preventDefault() {
        prevented = true;
      },
    });
  }
  return prevented;
}

/** Tasks pass, so a dynamic import and what waits on it settle. */
async function settled() {
  for (let at = 0; at < 20; at += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

/**
 * The Diff summary as a multi-file diff mounts it: its header in the toolbar, collapsed, and
 * no tree until the header is first opened (diff-summary.js); then the tree's paint, drawn a
 * window at a time, with the keys the tree takes and the chords it leaves alone.
 */
async function diffSummaryChecks(mountDiffView, twoFiles) {
  const sharedTree = require("./changed-files-tree-fixture.js").changedFilesTree();
  const formatInteger = (count) => count.toLocaleString("en-US");
  const createElement = global.document.createElement;
  const computed = global.getComputedStyle;
  const view = global.window;
  global.document.createElement = (tag) => new LaidOutElement(tag);
  global.getComputedStyle = () => ({ getPropertyValue: () => "24px" });
  const element = global.Element;
  global.Element = FakeElement;
  global.window = {
    requestAnimationFrame: () => 1,
    cancelAnimationFrame() {},
    addEventListener() {},
  };
  try {
    const host = new LaidOutElement("div");
    const kinds = {
      ...twoFiles,
      manifest: {
        ...twoFiles.manifest,
        files: [
          twoFiles.manifest.files[0],
          {
            ...twoFiles.manifest.files[0],
            id: "f2",
            kind: "added",
            old: null,
            new: { ...twoFiles.manifest.files[0].new, path: "src/deep/ad\u202Eded.py" },
            additions: 1200,
            deletions: 0,
          },
        ],
        totals: { files: 2, additions: 1201, deletions: 1, exact: true },
      },
    };
    // A pull request's Changes hands the diff its way to a file's own address.
    const opened = [];
    const handle = mountDiffView(
      host,
      kinds,
      { formatInteger },
      { changedFiles: sharedTree, openFile: (path) => opened.push(path) },
    );
    const header = host.find("diff-summary-toggle")[0];
    check("a change set's header is the Diff summary's toggle", header !== undefined);
    if (header === undefined) {
      return;
    }
    const said = header.reads();
    check(
      "the header says what the change set holds, in the shell's number format",
      said.includes("2 changed files") &&
        said.includes("(1 added, 1 modified)") &&
        said.includes("+1,201") &&
        said.includes("−1"),
      said,
    );
    // Its counts are the shell's bold numbers and its words are not (docs/design-system.md,
    // "Count Summaries Bold Their Numbers"); the line totals are the bold change stats.
    const numbers = header.find("summary-number").map((number) => number.reads());
    check(
      "the header's counts, and only its counts, are bold numbers",
      JSON.stringify(numbers) === JSON.stringify(["2", "1", "1"]) &&
        header.find("diff-summary-files")[0]?.children[1]?.reads() === " changed files" &&
        header.find("diff-stat-add")[0]?.reads() === "+1,201",
      JSON.stringify(numbers),
    );
    check(
      "the header names it all for a screen reader",
      header.getAttribute("aria-label") ===
        "2 changed files: 1 added, 1 modified; 1,201 lines added, 1 deleted",
      header.getAttribute("aria-label") ?? "",
    );
    check(
      "the summary starts collapsed",
      header.getAttribute("aria-expanded") === "false" && header.classList.contains("collapsed"),
    );
    check(
      "the header is a disclosure toggle with the registry's chevron box",
      header.classList.contains("disclosure-toggle") &&
        header.find("diff-summary-chevron").length === 1,
    );
    check(
      "nothing of the tree is mounted until it is opened",
      host.find("diff-summary-body").length === 0 && header.getAttribute("aria-controls") === null,
    );
    // A press whose module does not load leaves the header marked, saying a press tries
    // again; the next press loads it, and the mark goes.
    summaryModuleFails = true;
    const errors = [];
    const logged = console.error;
    console.error = (...args) => errors.push(args[0]);
    try {
      header.click();
      await settled();
    } finally {
      console.error = logged;
      summaryModuleFails = false;
    }
    check(
      "a header whose tree did not load says a press tries again",
      header.getAttribute("aria-disabled") === "true" &&
        header.dataset.tipText === "The list of files did not load. Press to try again." &&
        host.find("diff-summary-body").length === 0 &&
        errors[0] === "metabrowser diff: the Diff summary's tree did not load",
    );
    header.click();
    await settled();
    check(
      "a press that loads the tree clears the mark",
      header.getAttribute("aria-disabled") === null && header.dataset.tipText === undefined,
    );
    const body = host.find("diff-summary-body")[0];
    check("opening mounts the tree after the toolbar", body !== undefined);
    if (body === undefined) {
      return;
    }
    const root = host.children[0];
    check(
      "the tree follows the toolbar, above the files",
      root.children.indexOf(body) === root.children.indexOf(host.find("diff-toolbar")[0]) + 1,
    );
    check(
      "the header says it is open, and what it controls",
      header.getAttribute("aria-expanded") === "true" &&
        header.getAttribute("aria-controls") === body.getAttribute("id") &&
        !body.classList.contains("diff-summary-body-collapsed"),
    );
    const rows = () => body.find("diff-summary-row");
    const names = rows().map((row) => row.dataset.id);
    check(
      "the tree draws its folders first, open, then its files",
      JSON.stringify(names) === JSON.stringify(["src/deep/", "src/deep/ad\u202Eded.py", "a.py"]),
      JSON.stringify(names),
    );
    const folder = rows().find((row) => row.dataset.id === "src/deep/");
    check(
      "a folder row carries its rolled-up counts",
      folder?.text().includes("+1,200") && folder.text().includes("−0"),
      folder?.text() ?? "",
    );
    const list = body.children[0];
    check(
      "one row takes Tab",
      rows().filter((row) => row.getAttribute("tabindex") === "0").length === 1,
    );
    check("a chord is the browser's", !press(list, "ArrowDown", "metaKey"));
    check("an arrow is the tree's", press(list, "ArrowDown"));
    check(
      "the arrow moved the row that takes Tab, and focus with it",
      global.document.activeElement?.dataset.id === "src/deep/ad\u202Eded.py",
    );
    check(
      "a file the tree names is one the diff holds",
      handle.scrollToFile("src/deep/ad\u202Eded.py").kind === "jumped",
    );
    // A path is its author's text: a right-to-left override shows as U+FFFD, in the row and
    // its tooltip, and the path itself is what the row's identity and its address carry.
    const evil = rows().find((row) => row.dataset.id === "src/deep/ad\u202Eded.py");
    check(
      "a path's bidi control shows as U+FFFD",
      evil?.text().includes("ad\uFFFDded.py") &&
        !evil.text().includes("\u202E") &&
        evil.dataset.tipText === "src/deep/ad\uFFFDded.py",
      JSON.stringify(evil?.text() ?? ""),
    );
    const bar = host
      .find("diff-file-bar")
      .find(
        (each) =>
          each.find("diff-file-copy")[0]?.getAttribute("data-mb-copy-text") ===
          "src/deep/ad\u202Eded.py",
      );
    const barPath = bar?.find("diff-file-path")[0];
    check(
      "a file bar shows the path as its row does, and copies it as it is",
      barPath?.textContent === "src/deep/ad\uFFFDded.py" &&
        barPath.dataset.tipText === "src/deep/ad\uFFFDded.py" &&
        bar.find("diff-file-stats")[0]?.text().includes("+1,200"),
      JSON.stringify(barPath?.textContent ?? null),
    );
    check("Enter on a file is the tree's", press(list, "Enter"));
    check(
      "a file the summary opens goes to the host's address for it",
      JSON.stringify(opened) === JSON.stringify(["src/deep/ad\u202Eded.py"]),
      JSON.stringify(opened),
    );
    check("a key the tree does not take is left alone", !press(list, "Escape"));
    header.click();
    await settled();
    check(
      "closing keeps what the tree drew, out of sight",
      header.getAttribute("aria-expanded") === "false" &&
        body.classList.contains("diff-summary-body-collapsed") &&
        rows().length > 0,
    );
    handle.dispose();
    check("disposing the diff removes its tree", body.parentNode === null);
  } finally {
    global.document.createElement = createElement;
    global.getComputedStyle = computed;
    global.window = view;
    global.Element = element;
  }
}

/**
 * A path a manifest lists twice, as a patch of a file that became a symlink does, is one row
 * whose counts are both changes', and a press on it goes to the first of its sections (A1 of
 * review A on #448). `twoFiles` lists `a.py` twice.
 */
async function repeatedPathChecks(mountDiffView, twoFiles) {
  const sharedTree = require("./changed-files-tree-fixture.js").changedFilesTree();
  const createElement = global.document.createElement;
  const computed = global.getComputedStyle;
  const view = global.window;
  const element = global.Element;
  global.document.createElement = (tag) => new LaidOutElement(tag);
  global.getComputedStyle = () => ({ getPropertyValue: () => "24px" });
  global.window = {
    requestAnimationFrame: () => 1,
    cancelAnimationFrame() {},
    addEventListener() {},
  };
  global.Element = FakeElement;
  try {
    const host = new LaidOutElement("div");
    const handle = mountDiffView(
      host,
      twoFiles,
      { formatInteger: (count) => count.toLocaleString("en-US") },
      { changedFiles: sharedTree },
    );
    const bars = host.find("diff-file-bar");
    const bodies = host.find("diff-file-body");
    for (const bar of bars) {
      bar.click();
    }
    check(
      "both sections of a repeated path start this check collapsed",
      bodies.length === 2 &&
        bodies.every((body) => body.classList.contains("diff-file-body-collapsed")),
    );
    host.find("diff-summary-toggle")[0].click();
    await settled();
    const rows = host.find("diff-summary-row");
    check(
      "a path listed twice is one row, with both changes' counts",
      rows.length === 1 &&
        rows[0].dataset.id === "a.py" &&
        rows[0].getAttribute("aria-label") === "a.py, modified, 2 added, 2 deleted",
      rows.map((row) => row.getAttribute("aria-label")).join(" | "),
    );
    rows[0].click();
    check(
      "a press on it goes to its first section",
      !bodies[0].classList.contains("diff-file-body-collapsed") &&
        bodies[1].classList.contains("diff-file-body-collapsed"),
    );
    handle.dispose();
  } finally {
    global.document.createElement = createElement;
    global.getComputedStyle = computed;
    global.window = view;
    global.Element = element;
  }
}

/**
 * A long change set's tree draws the rows in the window's view of it and a window past it,
 * and moves that window as the page scrolls, as the Pulls tab's tree does: the tree has no
 * scroll of its own (mb-hi4l). A scroll of a box that does not hold the tree draws nothing,
 * and disposal removes the listeners on the document and the window.
 */
async function windowedSummaryChecks(repoRoot) {
  const sharedTree = require("./changed-files-tree-fixture.js").changedFilesTree();
  const createElement = global.document.createElement;
  const computed = global.getComputedStyle;
  const view = global.window;
  global.document.createElement = (tag) => new LaidOutElement(tag);
  global.getComputedStyle = () => ({ getPropertyValue: () => "24px" });
  const element = global.Element;
  global.Element = FakeElement;
  const node = global.Node;
  global.Node = FakeElement;
  let frame = null;
  // Every listener the tree adds outside itself, with the signal that removes it.
  const signals = [];
  global.window = {
    requestAnimationFrame(callback) {
      frame = callback;
      return 1;
    },
    cancelAnimationFrame() {},
    addEventListener(type, _handler, options) {
      signals.push({ on: `window ${type}`, signal: options?.signal });
    },
    innerHeight: 480,
  };
  // The page's scrolls, which the tree hears on the document in their capture phase.
  const scrolls = [];
  const listen = global.document.addEventListener;
  global.document.addEventListener = (type, handler, options) => {
    signals.push({ on: `document ${type}`, signal: options?.signal });
    if (type === "scroll") {
      scrolls.push({ handler, capture: options?.capture === true });
    }
  };
  try {
    const { mountSummaryTree, SUMMARY_ROWS_OVERSCAN } = await import(
      `${pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-summary.js")).href}?windowed`
    );
    const files = Array.from({ length: 1200 }, (_, at) => ({
      path: `pkg/file-${String(at).padStart(4, "0")}.py`,
      previous_path: null,
      status: "modified",
      additions: 1,
      deletions: 1,
      display: `pkg/file-${String(at).padStart(4, "0")}.py`,
      previous_display: null,
    }));
    const jumps = [];
    const tree = mountSummaryTree({
      tree: sharedTree,
      files,
      id: "summary",
      formatCount: (count) => String(count),
      chevron: () => null,
      jump: (path) => jumps.push(path),
    });
    tree.setOpen(true);
    const drawn = () => tree.body.find("diff-summary-row").length;
    const visible = 480 / 24;
    check(
      "a long tree draws the window's view of it and the overscan, not every row",
      drawn() === visible + SUMMARY_ROWS_OVERSCAN && tree.model.rows().length === 1201,
      String(drawn()),
    );
    check(
      "the tree has no scroll of its own and hears the page's",
      (tree.body.listeners.get("scroll") ?? []).length === 0 &&
        scrolls.length === 1 &&
        scrolls[0].capture,
      JSON.stringify(scrolls.map((each) => each.capture)),
    );
    const list = tree.body.children[0];
    list.box = { top: -12000, bottom: -12000 + 1201 * 24 };
    // A box beside the tree, a Split diff's code or the navigation pane, scrolls: the
    // window's view of the tree cannot have moved, so no frame is asked for.
    frame = null;
    for (const { handler } of scrolls) {
      handler({ target: new FakeElement("div") });
    }
    check("a scroll of a box that does not hold the tree draws nothing", frame === null);
    for (const { handler } of scrolls) {
      handler({ target: global.document });
    }
    frame?.();
    const ids = tree.body.find("diff-summary-row").map((row) => row.dataset.id);
    check(
      "a scroll moves the window",
      !ids.includes("pkg/file-0001.py") && ids.includes("pkg/file-0499.py"),
      `${ids[0]}…${ids.at(-1)}`,
    );
    const target = tree.body
      .find("diff-summary-row")
      .find((row) => row.dataset.id === "pkg/file-0500.py");
    target?.click();
    check("a press on a file jumps the diff to it", jumps.at(-1) === "pkg/file-0500.py");
    tree.dispose();
    check("a disposed tree leaves the document", tree.body.parentNode === null);
    check(
      "disposal removes its listeners on the document and the window",
      signals.length === 2 && signals.every(({ signal }) => signal?.aborted === true),
      JSON.stringify(signals.map(({ on, signal }) => [on, signal?.aborted ?? null])),
    );
  } finally {
    global.Node = node;
    global.document.addEventListener = listen;
    global.document.createElement = createElement;
    global.getComputedStyle = computed;
    global.window = view;
    global.Element = element;
  }
}

async function main() {
  const documentListeners = new Map();
  let hydrationObserver = null;
  global.IntersectionObserver = class IntersectionObserver {
    constructor(callback) {
      this.callback = callback;
      this.observed = new Set();
      hydrationObserver = this;
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

    intersect(target) {
      if (this.observed.has(target)) {
        this.callback([{ isIntersecting: true, target }], this);
      }
    }
  };
  global.document = {
    createElement: (tag) => new FakeElement(tag),
    addEventListener(type, handler) {
      const handlers = documentListeners.get(type) ?? [];
      handlers.push(handler);
      documentListeners.set(type, handlers);
    },
    removeEventListener(type, handler) {
      documentListeners.set(
        type,
        (documentListeners.get(type) ?? []).filter((candidate) => candidate !== handler),
      );
    },
  };
  const dispatchDocument = (type) => {
    for (const handler of documentListeners.get(type) ?? []) {
      handler({ target: null });
    }
  };
  const viewPath = path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view.js");
  const {
    composeTextRuns,
    mountDiffSummary,
    mountDiffView: mountDiffViewImpl,
    setChangeLoader,
  } = await import(pathToFileURL(viewPath).href);
  const defaultTestApi = {
    highlightSyntax: async () => null,
    isLargeTextPreview: () => true,
    langForPath: () => "",
    prefs: { get: () => "unified" },
  };
  const mountDiffView = (container, document, api = {}, options) =>
    mountDiffViewImpl(container, document, { ...defaultTestApi, ...api }, options);
  const corpus = JSON.parse(
    fs.readFileSync(
      path.join(repoRoot, "src/metabrowser/data/file-diff-format/file-diff-conformance.json"),
      "utf-8",
    ),
  );
  const byName = new Map(corpus.cases.map((entry) => [entry.name, entry.document]));
  const sharedTree = require("./changed-files-tree-fixture.js").changedFilesTree();
  const nextTask = () => new Promise((resolve) => setTimeout(resolve, 0));
  const nextSyntaxUnit = async () => {
    await Promise.resolve();
    await nextTask();
  };

  const composed = composeTextRuns(
    "const oldName = true;",
    [
      { classes: ["hljs-keyword"], text: "const" },
      { classes: [], text: " oldName = " },
      { classes: ["hljs-literal"], text: "true" },
      { classes: [], text: ";" },
    ],
    [{ start: 6, end: 13 }],
  );
  check(
    "syntax and intraline boundaries compose without text loss",
    composed.map((run) => run.text).join("") === "const oldName = true;" &&
      composed.some(
        (run) =>
          run.text === "oldName" &&
          run.classes.includes("diff-intraline-change") &&
          run.classes.length === 1,
      ) &&
      composed.some((run) => run.text === "true" && run.classes.includes("hljs-literal")),
    JSON.stringify(composed),
  );

  // A modified file renders numbered rows with the right ops.
  const container = new FakeElement("div");
  const handle = mountDiffView(container, byName.get("modified-with-heading"));
  const lines = container.find("diff-line");
  check("four line rows render", lines.length === 4, String(lines.length));
  const markers = lines.map((row) => row.find("diff-line-marker")[0].textContent);
  check("ops project to markers", JSON.stringify(markers) === JSON.stringify([" ", "-", "+", " "]));
  const firstNumbers = lines[0].find("diff-line-number").map((cell) => cell.textContent);
  check("context rows carry both numbers", JSON.stringify(firstNumbers) === '["3","3"]');
  check("hunk heading renders", container.text().includes("def f():"));

  // Unified syntax is progressive: complete plain text mounts before
  // the asynchronous helper can settle, then only the existing text
  // hosts receive scanner-produced spans. The unified projection uses
  // old-side tokens for deletions and new-side tokens everywhere else.
  let syntaxCalls = 0;
  const syntaxOptionKeys = [];
  const syntaxMeasures = [];
  const syntaxApi = {
    highlightSyntax: async (source, _language, options) => {
      syntaxCalls += 1;
      syntaxOptionKeys.push(Object.keys(options ?? {}).sort());
      const side = syntaxCalls % 2 === 1 ? "old" : "new";
      return source.split("\n").map((text) => [{ classes: [`hljs-${side}`], text }]);
    },
    isLargeTextPreview: () => false,
    langForPath: () => "python",
    perf: {
      measure: (label, work, metadata) => {
        const result = work();
        syntaxMeasures.push({ label, metadata: { ...metadata } });
        return result;
      },
      measureAsync: async (label, work, metadata) => {
        const result = await work();
        syntaxMeasures.push({ label, metadata: { ...metadata } });
        return result;
      },
    },
  };
  const highlighted = new FakeElement("div");
  const highlightedHandle = mountDiffView(
    highlighted,
    byName.get("modified-with-heading"),
    syntaxApi,
  );
  const plainHosts = highlighted.find("diff-line-text");
  check("plain text renders synchronously", plainHosts[1].textContent === "    return 1");
  check(
    "plain render has no token spans",
    plainHosts.every((host) => host.children.length === 0),
  );
  check(
    "diff token hosts escape the global enhancer",
    plainHosts.every((host) => host.tagName === "SPAN" && host.classList.contains("hljs")),
  );
  await nextSyntaxUnit();
  const highlightedLines = highlighted.find("diff-line");
  const contextHost = highlightedLines[0].find("diff-line-text")[0];
  const deletionHost = highlightedLines[1].find("diff-line-text")[0];
  const additionHost = highlightedLines[2].find("diff-line-text")[0];
  check(
    "unified context uses new-side tokens",
    contextHost.children[0].classList.contains("hljs-new"),
  );
  check(
    "unified deletion uses old-side tokens",
    deletionHost.children[0].classList.contains("hljs-old"),
  );
  check(
    "unified addition uses new-side tokens",
    additionHost.children[0].classList.contains("hljs-new"),
  );
  check(
    "unified similar replacements use refined row classes",
    highlightedLines[1].classList.contains("diff-line-refined") &&
      highlightedLines[2].classList.contains("diff-line-refined"),
  );
  check(
    "syntax and changed-range classes coexist",
    deletionHost.children.some(
      (span) =>
        span.classList.contains("hljs-old") && span.classList.contains("diff-intraline-change"),
    ) &&
      additionHost.children.some(
        (span) =>
          span.classList.contains("hljs-new") && span.classList.contains("diff-intraline-change"),
      ),
  );
  check(
    "enhancement preserves visible text",
    deletionHost.children.map((span) => span.textContent).join("") === "    return 1",
  );
  check("one old and one new lexer call serve the hunk", syntaxCalls === 2, String(syntaxCalls));
  check(
    "internal byte metadata does not widen the public SDK options",
    syntaxOptionKeys.every((keys) => JSON.stringify(keys) === '["signal"]'),
  );
  const lexerMeasures = syntaxMeasures.filter(({ label }) => label === "diffSyntax:lexer");
  const fileMeasure = syntaxMeasures.find(({ label }) => label === "diffSyntax:file");
  const mountLabels = new Set(syntaxMeasures.map(({ label }) => label));
  check(
    "mount phases separate model, projection, and attachment cost",
    [
      "diffMount:model",
      "diffMount:fileProjection",
      "diffMount:projection",
      "diffMount:attach",
    ].every((label) => mountLabels.has(label)),
    JSON.stringify([...mountLabels]),
  );
  check("each lexer call has a measured span", lexerMeasures.length === 2);
  check(
    "lexer measurements record language and UTF-8 input",
    lexerMeasures.every(
      ({ metadata }) => metadata.language === "python" && Number(metadata.input_bytes) > 0,
    ),
  );
  check(
    "file measurement records bounded input and calls",
    fileMeasure?.metadata.lexer_calls === 2 &&
      fileMeasure.metadata.hunk_count === 1 &&
      Number(fileMeasure.metadata.input_bytes) > 0,
  );
  highlightedHandle.dispose();

  const unsafeDoc = JSON.parse(JSON.stringify(byName.get("modified-with-heading")));
  unsafeDoc.patches.f1.hunks[0].lines[2].text = "<script>alert(1)</script>";
  const unsafe = new FakeElement("div");
  mountDiffView(unsafe, unsafeDoc, {
    ...syntaxApi,
    highlightSyntax: async (source) =>
      source.split("\n").map((text) => [{ classes: ["hljs-keyword"], text }]),
  });
  await nextSyntaxUnit();
  const unsafeHost = unsafe.find("diff-line-add")[0].find("diff-line-text")[0];
  check("token text is assigned without HTML parsing", unsafeHost.innerHTML === "");
  check(
    "hostile-looking token text remains literal",
    unsafeHost.children[0].textContent === "<script>alert(1)</script>",
  );

  const failed = new FakeElement("div");
  mountDiffView(failed, byName.get("modified-with-heading"), {
    ...syntaxApi,
    highlightSyntax: async () => null,
  });
  await nextSyntaxUnit();
  const failedHosts = failed.find("diff-line-text");
  const expectedFailedText = byName
    .get("modified-with-heading")
    .patches.f1.hunks[0].lines.map((line) => line.text);
  check(
    "failed syntax leaves exact text and independent intraline refinement",
    JSON.stringify(
      failedHosts.map((host) =>
        host.children.length === 0
          ? host.textContent
          : host.children.map((span) => span.textContent).join(""),
      ),
    ) === JSON.stringify(expectedFailedText) && failed.find("diff-intraline-change").length > 0,
  );

  // Split is a second projection of the same records. The host control
  // primitives own radiogroup markup and keyboard behavior; this view
  // supplies the exclusive joined-group contract and reprojects on the
  // reported value without fetching or lexing again.
  const defaultLayout = new FakeElement("div");
  mountDiffViewImpl(defaultLayout, byName.get("modified-with-heading"));
  check(
    "missing layout preference defaults to split",
    defaultLayout.find("diff-root")[0].dataset.layout === "split",
  );

  let layoutChange = null;
  let layoutSyntaxCalls = 0;
  const preferenceWrites = [];
  const layoutSpecs = [];
  let unbound = 0;
  const layoutApi = {
    highlightSyntax: async (source) => {
      layoutSyntaxCalls += 1;
      const side = layoutSyntaxCalls % 2 === 1 ? "old" : "new";
      return source.split("\n").map((text) => [{ classes: [`hljs-${side}`], text }]);
    },
    isLargeTextPreview: () => false,
    langForPath: () => "python",
    prefs: {
      get: () => "split",
      set: (key, value) => {
        preferenceWrites.push({ key, value });
        return true;
      },
    },
    filterControls: {
      groupHtml: (spec) => {
        layoutSpecs.push(spec);
        return `<span role="radiogroup" data-select="${spec.select}" data-layout="${spec.layout}">${spec.options.map((option) => option.label).join("/")}</span>`;
      },
      bind: (_root, handlers) => {
        layoutChange = handlers.onChange;
        return () => {
          unbound += 1;
        };
      },
    },
  };
  const split = new FakeElement("div");
  const splitHandle = mountDiffView(split, byName.get("modified-with-heading"), layoutApi);
  const splitRoot = split.find("diff-root")[0];
  check("valid split preference restores immediately", splitRoot.dataset.layout === "split");
  check(
    "one split row is projected per context or paired run row",
    split.find("diff-split-row").length === 3,
  );
  const splitContext = split.find("diff-split-context")[0];
  check(
    "split context duplicates both source sides",
    splitContext.find("diff-split-side").length === 2,
  );
  const splitChange = split.find("diff-split-change")[0];
  check(
    "equal replacements pair deletion and addition",
    splitChange.find("diff-split-empty").length === 0,
  );
  check(
    "layout control uses the exclusive joined primitive",
    layoutSpecs[0].select === "one" &&
      layoutSpecs[0].layout === "joined" &&
      layoutSpecs[0].value === "split",
  );
  check(
    "layout control orders Split before Unified",
    JSON.stringify(layoutSpecs[0].options.map((option) => option.value)) ===
      JSON.stringify(["split", "unified"]),
  );
  check(
    "layout control is always present",
    split.find("diff-layout-control")[0].innerHTML.includes('role="radiogroup"'),
  );
  await nextSyntaxUnit();
  const splitContextSides = split.find("diff-split-context")[0].find("diff-split-side");
  check(
    "split context keeps each side's tokens",
    splitContextSides[0].find("diff-line-text")[0].children[0].classList.contains("hljs-old") &&
      splitContextSides[1].find("diff-line-text")[0].children[0].classList.contains("hljs-new"),
  );
  const callsBeforeSwitch = layoutSyntaxCalls;
  const splitLayoutChange = layoutChange;
  layoutChange("diff-layout", "unified", "one");
  check("layout switch reprojects immediately", split.find("diff-split-row").length === 0);
  check("unified switch restores four source rows", split.find("diff-line").length === 4);
  check(
    "layout preference persists",
    preferenceWrites.at(-1).key === "diff.layout" && preferenceWrites.at(-1).value === "unified",
  );
  layoutChange("diff-layout", "split", "one");
  layoutChange("diff-layout", "unified", "one");
  check("repeated switches never re-run the lexer", layoutSyntaxCalls === callsBeforeSwitch);
  const splitBar = split.find("diff-file-bar")[0];
  const splitBody = split.find("diff-file-body")[0];
  splitBar.click();
  splitLayoutChange("diff-layout", "split", "one");
  check(
    "collapsed file state survives reprojection",
    splitBody.classList.contains("diff-file-body-collapsed"),
  );
  const splitOldText = split.find("diff-split-old")[0].find("diff-line-text")[0];
  const splitNewText = split.find("diff-split-new")[0].find("diff-line-text")[0];
  splitOldText.pointerDown();
  check("old-side pointer down gates selection", splitRoot.dataset.selectionSide === "old");
  split.find("diff-hunk-header")[0].pointerDown();
  check("full-width hunk header clears the side gate", !splitRoot.dataset.selectionSide);
  splitNewText.pointerDown();
  check("new-side pointer down gates selection", splitRoot.dataset.selectionSide === "new");
  dispatchDocument("pointerup");
  check("pointer up releases the side gate", !splitRoot.dataset.selectionSide);
  splitOldText.pointerDown();
  dispatchDocument("pointercancel");
  check("pointer cancellation releases the side gate", !splitRoot.dataset.selectionSide);

  const unequalDoc = JSON.parse(JSON.stringify(byName.get("modified-with-heading")));
  unequalDoc.patches.f1.hunks[0].lines = [
    { op: "del", text: "old one" },
    { op: "del", text: "old two", no_newline: true },
    { op: "add", text: "new one" },
  ];
  unequalDoc.patches.f1.hunks[0].old_count = 2;
  unequalDoc.patches.f1.hunks[0].new_count = 1;
  const unequal = new FakeElement("div");
  mountDiffView(unequal, unequalDoc, layoutApi);
  const unequalRows = unequal.find("diff-split-change");
  check("unequal replacements use the longer side's row count", unequalRows.length === 2);
  const empty = unequalRows[1].find("diff-split-empty")[0];
  check(
    "padding invents no accessible content or number",
    empty.getAttribute("aria-hidden") === "true" &&
      empty.children.length === 0 &&
      empty.text() === "",
  );
  check(
    "no-newline marker stays on its source side",
    unequalRows[1].find("diff-split-old")[0].find("diff-line-no-newline").length === 1,
  );

  const shiftedDoc = JSON.parse(JSON.stringify(byName.get("modified-with-heading")));
  shiftedDoc.patches.f1.hunks[0].lines = [
    { op: "del", text: "alpha = one;" },
    { op: "del", text: "beta = two;" },
    { op: "del", text: "gamma = three;" },
    { op: "add", text: "inserted = zero;" },
    { op: "add", text: "alpha = 1;" },
    { op: "add", text: "beta = 2;" },
    { op: "add", text: "gamma = 3;" },
  ];
  shiftedDoc.patches.f1.hunks[0].old_count = 3;
  shiftedDoc.patches.f1.hunks[0].new_count = 4;
  const shifted = new FakeElement("div");
  mountDiffView(shifted, shiftedDoc, layoutApi);
  check(
    "split first paint retains positional fallback",
    shifted.find("diff-split-row")[0].find("diff-split-empty").length === 0,
  );
  await nextSyntaxUnit();
  const shiftedRows = shifted.find("diff-split-row");
  const shiftedText = (rowIndex, side) =>
    renderedText(shiftedRows[rowIndex].find(`diff-split-${side}`)[0].find("diff-line-text")[0]);
  check(
    "refinement reprojects only the file with monotonic shifted alignment",
    shiftedRows[0].find("diff-split-old")[0].classList.contains("diff-split-empty") &&
      shiftedText(0, "new") === "inserted = zero;" &&
      shiftedText(1, "old") === "alpha = one;" &&
      shiftedText(1, "new") === "alpha = 1;",
    JSON.stringify(
      shiftedRows.map((row) =>
        row
          .find("diff-split-side")
          .map((side) => ({ className: side.className, text: side.text() })),
      ),
    ),
  );

  const invalidPreference = new FakeElement("div");
  mountDiffView(invalidPreference, byName.get("modified-with-heading"), {
    ...layoutApi,
    prefs: { ...layoutApi.prefs, get: () => "future-layout" },
  });
  check(
    "invalid layout preference falls back to split",
    invalidPreference.find("diff-root")[0].dataset.layout === "split",
  );
  const persistedUnified = new FakeElement("div");
  mountDiffView(persistedUnified, byName.get("modified-with-heading"), {
    ...layoutApi,
    prefs: { ...layoutApi.prefs, get: () => "unified" },
  });
  check(
    "persisted unified preference remains authoritative",
    persistedUnified.find("diff-root")[0].dataset.layout === "unified",
  );
  const pureAdd = new FakeElement("div");
  mountDiffView(pureAdd, byName.get("added-text-file"), layoutApi);
  const pureAddRows = pureAdd.find("diff-split-change");
  check(
    "pure additions leave only old-side padding",
    pureAddRows.length > 0 &&
      pureAddRows.every((row) =>
        row.find("diff-split-old")[0].classList.contains("diff-split-empty"),
      ),
  );
  const pureDelete = new FakeElement("div");
  mountDiffView(pureDelete, byName.get("deleted-file"), layoutApi);
  const pureDeleteRows = pureDelete.find("diff-split-change");
  check(
    "pure deletions leave only new-side padding",
    pureDeleteRows.length > 0 &&
      pureDeleteRows.every((row) =>
        row.find("diff-split-new")[0].classList.contains("diff-split-empty"),
      ),
  );
  const pointerUpListeners = documentListeners.get("pointerup")?.length ?? 0;
  splitHandle.dispose();
  check("layout control binding disposes with the view", unbound === 1, String(unbound));
  check(
    "selection gate listeners dispose with the view",
    (documentListeners.get("pointerup")?.length ?? 0) === pointerUpListeners - 1,
  );

  // The server can return 1,000 ready files. Large layout changes project one
  // measured batch synchronously, then yield without allowing a stale switch
  // to overwrite a newer choice.
  const boundedDoc = JSON.parse(JSON.stringify(byName.get("modified-with-heading")));
  const boundedSeedChange = boundedDoc.manifest.files[0];
  const boundedSeedPatch = boundedDoc.patches.f1;
  boundedDoc.manifest.files = [];
  boundedDoc.patches = {};
  for (let index = 0; index < 101; index += 1) {
    const id = `bound-${index}`;
    boundedDoc.manifest.files.push({ ...boundedSeedChange, id });
    boundedDoc.patches[id] = { ...boundedSeedPatch, file_id: id };
  }
  boundedDoc.manifest.totals.files = 101;
  let boundedLayoutChange;
  const bounded = new FakeElement("div");
  const boundedHandle = mountDiffView(bounded, boundedDoc, {
    ...layoutApi,
    filterControls: {
      ...layoutApi.filterControls,
      bind: (_root, handlers) => {
        boundedLayoutChange = handlers.onChange;
        return () => {};
      },
    },
    prefs: { ...layoutApi.prefs, get: () => "unified" },
  });
  boundedLayoutChange("diff-layout", "split", "one");
  const boundedRoot = bounded.find("diff-root")[0];
  check(
    "large switch updates its control state immediately",
    boundedRoot.dataset.layout === "split",
  );
  check("large switch marks a pending projection", boundedRoot.dataset.layoutPending === "true");
  check(
    "large switch yields after its measured synchronous batch",
    bounded.find("diff-split-row").length === 300 && bounded.find("diff-line").length === 4,
  );
  boundedLayoutChange("diff-layout", "unified", "one");
  await nextTask();
  check(
    "a newer large switch wins every remaining batch",
    bounded.find("diff-split-row").length === 0,
  );
  check(
    "large projection clears its pending marker",
    boundedRoot.dataset.layoutPending === undefined,
  );
  boundedHandle.dispose();

  // The per-file bar: the nav tree's own chevron mechanism (leading
  // glyph, expanded/collapsed classes) plus a copy control, with the
  // stat pair beside the filename.
  const toggle = container.find("diff-file-toggle")[0];
  check(
    "chevron leads, from the shared registry mechanism",
    toggle.children[0].classList.contains("diff-file-chevron"),
  );
  check("trigger starts in the expanded class", toggle.classList.contains("expanded"));
  check("sections start expanded", toggle.getAttribute("aria-expanded") === "true");
  const body = container.find("diff-file-body")[0];
  check(
    "trigger controls the body",
    toggle.getAttribute("aria-controls") === body.getAttribute("id"),
  );
  const copy = container.find("diff-file-copy")[0];
  check("copy control rides the shared delegation", copy.getAttribute("data-mb-copy") === "text");
  check(
    "copy control carries an explicit path payload",
    copy.getAttribute("data-mb-copy-text") === "a.py",
  );
  check("copy control is an icon button", copy.classList.contains("icon-btn"));
  check(
    "stats sit beside the filename",
    toggle.children[2].classList.contains("diff-file-path") &&
      toggle.children[3].classList.contains("diff-file-stats"),
  );
  const stats = container.find("diff-file-stats")[0];
  check(
    "stat pair renders add then del",
    stats.children[0].classList.contains("diff-stat-add") &&
      stats.children[1].classList.contains("diff-stat-del"),
  );

  // The whole bar is one activation surface: bar clicks toggle, the
  // button's own (bubbled) click toggles, the copy control does not.
  const bar = container.find("diff-file-bar")[0];
  bar.click();
  check("bar click collapses the body", body.classList.contains("diff-file-body-collapsed"));
  check("collapse flips aria-expanded", toggle.getAttribute("aria-expanded") === "false");
  check(
    "collapse flips the rotation class the tree uses",
    toggle.classList.contains("collapsed") && !toggle.classList.contains("expanded"),
  );
  check(
    "collapse marks the section, so its bar drops the doubled border",
    bar.parentNode.classList.contains("diff-file-collapsed"),
  );
  check("collapse keeps rows mounted", container.find("diff-line").length === 4);
  toggle.click();
  check("trigger click restores the body", !body.classList.contains("diff-file-body-collapsed"));
  copy.click();
  check(
    "copy click does not toggle",
    !body.classList.contains("diff-file-body-collapsed") &&
      toggle.getAttribute("aria-expanded") === "true",
  );

  // Disposal removes everything the mount added.
  handle.dispose();
  check("dispose removes the root", container.children.length === 0);

  // Every availability state renders one labeled explanation, never an
  // empty section.
  const binary = new FakeElement("div");
  mountDiffView(binary, byName.get("binary-added-elided"));
  check("binary state renders its copy", binary.text().includes("Binary file; no textual diff."));
  // Deferred is progress, not prose: with no revision to load from, the
  // section states unavailability; the progress box and its fetch are
  // covered where a revision exists (the shell's comparison path).
  const deferred = new FakeElement("div");
  mountDiffView(deferred, byName.get("deferred-manifest-only"));
  check(
    "deferred state never renders loading prose",
    !deferred.text().includes("not been loaded yet") && !deferred.text().includes("Loading"),
  );
  check("deferred without a source states unavailability", deferred.text().includes("unavailable"));

  // A metadata-only change (chmod) says so instead of showing nothing.
  const chmod = new FakeElement("div");
  mountDiffView(chmod, byName.get("mode-change-only"));
  check("mode change renders the note", chmod.text().includes("No content changes."));
  check("mode transition is visible", chmod.text().includes("100644→100755"));

  // A single-file document (a container child) skips the summary: its
  // bar already carries the name and stats.
  const single = new FakeElement("div");
  mountDiffView(single, byName.get("modified-with-heading"));
  check("one-file documents omit the summary line", single.find("diff-summary").length === 0);
  check("one-file documents still render their bar", single.find("diff-file-bar").length === 1);
  const many = new FakeElement("div");
  const manyDoc = byName.get("modified-with-heading");
  const twoFiles = {
    ...manyDoc,
    manifest: {
      ...manyDoc.manifest,
      files: [manyDoc.manifest.files[0], { ...manyDoc.manifest.files[0], id: "f2" }],
      totals: { ...manyDoc.manifest.totals, files: 2 },
    },
  };
  mountDiffView(many, twoFiles);
  // A change set's totals are its Diff summary's header, drawn on the shared changed-files
  // tree. Without the tree, the totals stand as the line main drew, in the shell's number
  // format, with no toggle: only the tree of files is lost (A3 of review A on #448).
  const plain = many.find("diff-summary")[0];
  check(
    "a change set without the shared tree keeps its totals line",
    plain?.reads().includes("2 changed files") &&
      plain.reads().includes("+1") &&
      plain.reads().includes("\u22121") &&
      plain.find("diff-summary-toggle").length === 0 &&
      !plain.classList.contains("diff-summary-toggle"),
    plain?.reads() ?? "",
  );
  check(
    "the totals line's file count is a bold number, as the Diff summary's is",
    JSON.stringify(plain?.find("summary-number").map((number) => number.reads())) ===
      JSON.stringify(["2"]),
  );
  const hosted = new FakeElement("div");
  mountDiffView(hosted, twoFiles, undefined, { showSummary: false, changedFiles: sharedTree });
  check(
    "revision-hosted change sets leave the aggregate summary to their commit header",
    hosted.find("diff-summary").length === 0,
  );
  check("revision-hosted change sets keep their toolbar", hosted.find("diff-toolbar").length === 1);
  const singleSummarized = new FakeElement("div");
  mountDiffView(singleSummarized, byName.get("modified-with-heading"), undefined, {
    changedFiles: sharedTree,
  });
  check(
    "one-file documents have no Diff summary",
    singleSummarized.find("diff-summary").length === 0,
  );
  // A page that keeps the Diff summary at its own top (mb-pb35): a commit's page hands the
  // diff the place (`summaryHost`), where the summary is drawn, for one file too, and the
  // toolbar holds no summary; a pull request's page draws it on its own
  // (`mountDiffSummary`) from the document it read, and its diff draws none.
  const placed = new FakeElement("div");
  const place = new FakeElement("div");
  mountDiffView(placed, twoFiles, undefined, { changedFiles: sharedTree, summaryHost: place });
  check(
    "a page's place holds the Diff summary its diff draws",
    place.find("diff-summary-toggle").length === 1 && placed.find("diff-summary").length === 0,
  );
  const placedOne = new FakeElement("div");
  const placeOne = new FakeElement("div");
  mountDiffView(placedOne, byName.get("modified-with-heading"), undefined, {
    changedFiles: sharedTree,
    summaryHost: placeOne,
  });
  check(
    "a page's place holds one file's Diff summary too",
    placeOne.find("diff-summary-toggle").length === 1 &&
      placedOne.find("diff-summary").length === 0,
  );
  const slot = new FakeElement("div");
  const standalone = mountDiffSummary(
    slot,
    twoFiles,
    { formatInteger: (count) => String(count) },
    { changedFiles: sharedTree, openFile() {} },
  );
  const drawn = slot.children[0];
  check(
    "a page draws a Diff summary on its own from the document",
    slot.children.length === 1 &&
      drawn.classList.contains("diff-summary-toggle") &&
      drawn.reads().includes("2 changed files"),
    drawn?.reads() ?? "",
  );
  standalone.dispose();
  // A list cut short at its bound, on a page that knows the whole change set's totals, as a
  // commit's page does from the commit's own stats: the header says those, with no breakdown
  // of the listed files alone, and how many files are listed (A3 of review A on #470). A list
  // that is whole says its own totals, whatever the page gives.
  const whole = { files: 5, additions: 15, deletions: 3, exact: true };
  const cutShort = {
    ...twoFiles,
    manifest: { ...twoFiles.manifest, truncated: true, cursor: "manifest-cap" },
  };
  const cutPlace = new FakeElement("div");
  mountDiffView(new FakeElement("div"), cutShort, undefined, {
    changedFiles: sharedTree,
    summaryHost: cutPlace,
    summaryTotals: whole,
  });
  const cutHeader = cutPlace.find("diff-summary-toggle")[0];
  check(
    "a list cut short says the page's whole totals and how many it lists",
    cutHeader?.text().includes("5 changed files") &&
      cutHeader.text().includes("+15") &&
      cutHeader.text().includes("−3") &&
      cutHeader.text().includes("(2 listed)") &&
      cutHeader.find("diff-summary-breakdown").length === 0,
    cutHeader?.text() ?? "",
  );
  check(
    "and names them for a screen reader",
    cutHeader?.getAttribute("aria-label") ===
      "5 changed files; 15 lines added, 3 deleted; 2 listed",
    cutHeader?.getAttribute("aria-label") ?? "",
  );
  const cutPlain = new FakeElement("div");
  mountDiffView(new FakeElement("div"), cutShort, undefined, {
    summaryHost: cutPlain,
    summaryTotals: whole,
  });
  check(
    "a list cut short says them without the shared tree too",
    cutPlain.text().includes("5 changed files") && cutPlain.text().includes("(2 listed)"),
    cutPlain.text(),
  );
  const wholePlace = new FakeElement("div");
  mountDiffView(new FakeElement("div"), twoFiles, undefined, {
    changedFiles: sharedTree,
    summaryHost: wholePlace,
    summaryTotals: whole,
  });
  check(
    "a whole list says its own totals",
    wholePlace.text().includes("2 changed files") && !wholePlace.text().includes("listed"),
    wholePlace.text(),
  );
  await diffSummaryChecks(mountDiffView, twoFiles);
  await repeatedPathChecks(mountDiffView, twoFiles);
  await windowedSummaryChecks(repoRoot);
  // A host that cuts the header's breakdown short, as a pull request's header does to keep
  // its one line, gives the header its whole words as a tooltip while it is cut, and none
  // while it is whole (A7 of review A on #470). It runs after the checks of a tree that did
  // not load, since a hover loads the tree's module.
  const tipSlot = new FakeElement("div");
  const tipped = mountDiffSummary(tipSlot, twoFiles, undefined, {
    changedFiles: sharedTree,
    openFile() {},
  });
  const tipHeader = tipSlot.children[0];
  const tipBreakdown = tipHeader.find("diff-summary-breakdown")[0];
  tipHeader.dispatch("pointerenter");
  check("a whole breakdown has no tooltip", tipHeader.dataset.tipText === undefined);
  tipBreakdown.scrollWidth = 180;
  tipBreakdown.clientWidth = 60;
  tipHeader.dispatch("pointerenter");
  check(
    "a breakdown cut short gives its header's whole words",
    tipHeader.dataset.tipText === "2 changed files (2 modified)  +1 \u22121",
    tipHeader.dataset.tipText ?? "",
  );
  tipBreakdown.scrollWidth = 60;
  tipHeader.dispatch("pointerenter");
  check("a breakdown whole again has none", tipHeader.dataset.tipText === undefined);
  tipped.dispose();

  // A long contiguous run folds behind an expander; ordinary runs do not.
  const longDoc = JSON.parse(JSON.stringify(byName.get("modified-with-heading")));
  const longHunk = longDoc.patches.f1.hunks[0];
  const addedLines = [];
  for (let i = 0; i < 60; i += 1) {
    addedLines.push({ op: "add", text: `line ${i}` });
  }
  longHunk.lines = [{ op: "context", text: "keep" }, ...addedLines];
  longHunk.old_count = 1;
  longHunk.new_count = 61;
  const folded = new FakeElement("div");
  mountDiffView(folded, longDoc);
  const control = folded.find("diff-fold-control")[0];
  check("a long run renders one expander", folded.find("diff-fold-control").length === 1);
  check("the expander states the hidden count", control.text().includes("40 more changed lines"));
  const group = folded.find("diff-fold-group")[0];
  check("hidden lines start collapsed", group.classList.contains("diff-fold-collapsed"));
  check("the visible head stays outside the group", folded.find("diff-line").length === 21);
  check("collapsed surplus rows are not materialized", group.find("diff-line").length === 0);
  const sectionBody = folded.find("diff-file-body")[0];
  control.click();
  check("expanding reveals the group", !group.classList.contains("diff-fold-collapsed"));
  check("expansion feedback precedes row construction", group.find("diff-line").length === 0);
  check(
    "expanding does not also collapse the file",
    !sectionBody.classList.contains("diff-file-body-collapsed"),
  );
  await nextTask();
  check("expansion materializes the surplus cooperatively", group.find("diff-line").length === 40);
  control.click();
  check("collapsing hides it again", group.classList.contains("diff-fold-collapsed"));
  check("collapsing releases surplus row DOM", group.find("diff-line").length === 0);
  check("short runs do not fold", container.find("diff-fold-control").length === 0);

  const hugeDoc = JSON.parse(JSON.stringify(longDoc));
  const hugeHunk = hugeDoc.patches.f1.hunks[0];
  hugeHunk.lines = Array.from({ length: 2_020 }, (_, index) => ({
    op: "add",
    text: `large line ${index}`,
  }));
  hugeHunk.old_count = 0;
  hugeHunk.new_count = hugeHunk.lines.length;
  const hugeFold = new FakeElement("div");
  const hugeHandle = mountDiffView(hugeFold, hugeDoc);
  const hugeControl = hugeFold.find("diff-fold-control")[0];
  const hugeGroup = hugeFold.find("diff-fold-group")[0];
  check(
    "large collapsed runs mount only their visible prefix",
    hugeFold.find("diff-line").length === 20,
  );
  hugeControl.click();
  await nextTask();
  check(
    "large expansion yields after one bounded row batch",
    hugeGroup.find("diff-line").length === 100,
    String(hugeGroup.find("diff-line").length),
  );
  hugeHandle.cancelPending();
  await nextTask();
  check(
    "navigation cancellation stops later fold batches",
    hugeGroup.find("diff-line").length === 100,
    String(hugeGroup.find("diff-line").length),
  );
  hugeControl.click();
  await nextTask();
  check("collapsed expansion cancels later batches", hugeGroup.find("diff-line").length === 0);
  hugeHandle.dispose();

  const switchingFold = new FakeElement("div");
  mountDiffView(switchingFold, longDoc, layoutApi);
  const switchingControl = switchingFold.find("diff-fold-control")[0];
  const splitFoldGroup = switchingFold.find("diff-fold-group")[0];
  check(
    "collapsed split surplus starts unmaterialized",
    splitFoldGroup.find("diff-split-row").length === 0,
  );
  switchingControl.click();
  await nextTask();
  check(
    "split fold hides one paired interval across unequal sides",
    splitFoldGroup.find("diff-split-row").length === 40 &&
      splitFoldGroup.find("diff-split-empty").length === 40,
  );
  layoutChange("diff-layout", "unified", "one");
  layoutChange("diff-layout", "split", "one");
  await nextTask();
  const restoredControl = switchingFold.find("diff-fold-control")[0];
  check(
    "expanded fold state survives reprojection",
    restoredControl.getAttribute("aria-expanded") === "true",
  );
  check(
    "restored split fold stays visible",
    !switchingFold.find("diff-fold-group")[0].classList.contains("diff-fold-collapsed"),
  );

  // Deferred data and syntax share one mount lifetime. Layout changes
  // only alter the projection; pending work is neither restarted nor
  // allowed to mutate state after disposal.
  const deferredDoc = JSON.parse(JSON.stringify(byName.get("deferred-manifest-only")));
  deferredDoc.__revision = "revision-1";
  const manyDeferredDoc = JSON.parse(JSON.stringify(deferredDoc));
  manyDeferredDoc.manifest.files = [0, 1, 2].map((index) => {
    const change = JSON.parse(JSON.stringify(deferredDoc.manifest.files[0]));
    change.id = `f${index + 1}`;
    change.old.path = `old-${index}.txt`;
    change.new.path = `new-${index}.txt`;
    return change;
  });
  manyDeferredDoc.manifest.totals.files = 3;
  let viewportLoads = 0;
  setChangeLoader(() => {
    viewportLoads += 1;
    return new Promise(() => {});
  });
  const manyDeferred = new FakeElement("div");
  const manyDeferredHandle = mountDiffView(manyDeferred, manyDeferredDoc, layoutApi);
  const deferredBodies = manyDeferred.find("diff-file-body");
  check("mounting many deferred files starts no requests", viewportLoads === 0);
  check("all deferred bodies wait for visibility", hydrationObserver.observed.size === 3);
  for (const body of deferredBodies) {
    hydrationObserver.intersect(body.parentNode);
  }
  check("visible deferred work asks for one file at a time", viewportLoads === 1);
  manyDeferredHandle.cancelPending();
  check("cancellation drops every queued observation", hydrationObserver.observed.size === 0);
  manyDeferredHandle.dispose();

  let deferredResolve;
  let deferredSignal;
  let deferredLoads = 0;
  setChangeLoader((_revision, _path, options) => {
    deferredLoads += 1;
    deferredSignal = options?.signal;
    return new Promise((resolve) => {
      deferredResolve = resolve;
    });
  });
  const hydrated = new FakeElement("div");
  mountDiffView(hydrated, deferredDoc, layoutApi);
  const deferredBody = hydrated.find("diff-file-body")[0];
  check("offscreen deferred files do not start requests", deferredLoads === 0);
  hydrationObserver.intersect(deferredBody.parentNode);
  const deferredLayoutChange = layoutChange;
  check("deferred loader receives the mount signal", deferredSignal instanceof AbortSignal);
  deferredLayoutChange("diff-layout", "unified", "one");
  deferredResolve(JSON.parse(JSON.stringify(byName.get("modified-with-heading"))));
  await nextTask();
  // An answer renders in a frame of its own.
  await nextTask();
  check("deferred file hydrates exactly once", deferredLoads === 1, String(deferredLoads));
  check("pending hydration uses the latest layout", hydrated.find("diff-line").length === 4);

  let disposedFetchResolve;
  let disposedFetchSignal;
  setChangeLoader((_revision, _path, options) => {
    disposedFetchSignal = options?.signal;
    return new Promise((resolve) => {
      disposedFetchResolve = resolve;
    });
  });
  const disposedFetch = new FakeElement("div");
  const disposedFetchHandle = mountDiffView(disposedFetch, deferredDoc, layoutApi);
  const detachedBody = disposedFetch.find("diff-file-body")[0];
  check("replacement test starts with deferred work idle", disposedFetchSignal === undefined);
  hydrationObserver.intersect(detachedBody.parentNode);
  disposedFetchHandle.cancelPending();
  check("pending-work cancellation aborts deferred fetches", disposedFetchSignal?.aborted === true);
  check("pending-work cancellation retains the rendered root", disposedFetch.children.length === 1);
  disposedFetchResolve(JSON.parse(JSON.stringify(byName.get("modified-with-heading"))));
  await nextTask();
  check(
    "late fetch completion cannot mutate retained stale DOM",
    detachedBody.find("diff-line").length === 0,
  );
  disposedFetchHandle.dispose();
  check(
    "disposal removes the retained root after cancellation",
    disposedFetch.children.length === 0,
  );

  let tokenResolve;
  let tokenSignal;
  let tokenSource = "";
  let tokenCalls = 0;
  const pendingTokenApi = {
    highlightSyntax: (source, _language, options) => {
      tokenCalls += 1;
      tokenSource = source;
      tokenSignal = options?.signal;
      if (tokenCalls > 1) {
        return Promise.resolve(null);
      }
      return new Promise((resolve) => {
        tokenResolve = resolve;
      });
    },
    isLargeTextPreview: () => false,
    langForPath: () => "python",
  };
  const disposedSyntax = new FakeElement("div");
  const disposedSyntaxHandle = mountDiffView(
    disposedSyntax,
    byName.get("modified-with-heading"),
    pendingTokenApi,
  );
  const detachedHosts = disposedSyntax.find("diff-line-text");
  await nextSyntaxUnit();
  check("syntax work starts after plain paint", tokenCalls === 1, String(tokenCalls));
  const detachedChildCounts = detachedHosts.map((host) => host.children.length);
  disposedSyntaxHandle.dispose();
  check("dispose aborts syntax waits", tokenSignal?.aborted === true);
  tokenResolve(tokenLines(tokenSource, "late"));
  await nextTask();
  check(
    "late syntax completion cannot mutate detached hosts",
    detachedHosts.every((host, index) => host.children.length === detachedChildCounts[index]),
  );

  const queuedDoc = JSON.parse(JSON.stringify(byName.get("modified-with-heading")));
  const secondChange = JSON.parse(JSON.stringify(queuedDoc.manifest.files[0]));
  secondChange.id = "f2";
  secondChange.old.path = "b.py";
  secondChange.new.path = "b.py";
  queuedDoc.manifest.files.push(secondChange);
  queuedDoc.manifest.totals.files = 2;
  const secondPatch = JSON.parse(JSON.stringify(queuedDoc.patches.f1));
  secondPatch.file_id = "f2";
  secondPatch.hunks[0].lines[0].text = "second file";
  queuedDoc.patches.f2 = secondPatch;
  const queueCalls = [];
  const queueApi = {
    highlightSyntax: async (source) => {
      queueCalls.push(source);
      if (queueCalls.length === 1) {
        throw new Error("first file failed");
      }
      return tokenLines(source, "queue");
    },
    isLargeTextPreview: () => false,
    langForPath: () => "python",
  };
  const queued = new FakeElement("div");
  mountDiffView(queued, queuedDoc, queueApi);
  check("many-file enhancement yields after plain paint", queueCalls.length === 0);
  await nextSyntaxUnit();
  check("only the first file runs in the first task", queueCalls.length === 1);
  await nextSyntaxUnit();
  check(
    "one failed file does not block the next queued file",
    queueCalls.length === 3 && queueCalls[1].includes("second file"),
    JSON.stringify(queueCalls),
  );

  // What the source left out is said above the files, and the files are still there.
  const warned = JSON.parse(JSON.stringify(byName.get("modified-with-heading")));
  warned.resolved.warnings = ["1 section(s) could not be modeled and are left out: gone.txt"];
  const warnedHost = new FakeElement("div");
  mountDiffView(warnedHost, warned);
  const warnings = warnedHost.find("diff-warning");
  check(
    "a warning is shown",
    warnings.length === 1 && warnings[0].textContent.includes("gone.txt"),
  );
  check("the files stay beside a warning", warnedHost.find("diff-file").length === 1);
  const unwarned = new FakeElement("div");
  mountDiffView(unwarned, byName.get("modified-with-heading"));
  check("no warning, no notice", unwarned.find("diff-warning").length === 0);

  // Routine hydration is quiet, including when a file has a documented size limit.
  const partialDoc = JSON.parse(JSON.stringify(byName.get("deferred-manifest-only")));
  partialDoc.__revision = "revision-1";
  partialDoc.manifest.files.push({
    ...JSON.parse(JSON.stringify(partialDoc.manifest.files[0])),
    id: "f2",
    new: { ...partialDoc.manifest.files[0].new, path: "second.py" },
  });
  partialDoc.manifest.totals.files = 2;
  const partialHost = new FakeElement("div");
  let answer;
  setChangeLoader(
    () =>
      new Promise((resolve) => {
        answer = resolve;
      }),
  );
  mountDiffView(partialHost, partialDoc);
  const failureNote = partialHost.find("diff-hydration-failure")[0];
  check("a partial view stays quiet", failureNote.hidden === true);
  const partialBodies = partialHost.find("diff-file-body");
  hydrationObserver.intersect(partialBodies[0].parentNode);
  await nextTask();
  answer(JSON.parse(JSON.stringify(byName.get("modified-with-heading"))));
  await nextTask();
  await nextTask();
  check("a successful file adds no notice", failureNote.hidden === true);
  hydrationObserver.intersect(partialBodies[1].parentNode);
  await nextTask();
  answer(tooLargeAnswer(byName));
  await nextTask();
  await nextTask();
  check("a file past its limit needs only its inline reason", failureNote.hidden === true);
  check(
    "a file too large to hydrate says so, as a reason",
    partialBodies[1].text().includes("too large to show inline"),
    partialBodies[1].text(),
  );

  // A deleted empty file has no hunks and is not an unavailable one.
  const deletedEmpty = new FakeElement("div");
  mountDiffView(deletedEmpty, byName.get("deleted-empty-file"));
  check("a deleted empty file says so", deletedEmpty.text().includes("No content changes."));

  // The no-newline marker is visible, not silently dropped.
  const noNewline = new FakeElement("div");
  mountDiffView(noNewline, byName.get("no-newline-marker"));
  check("no-newline marker renders", noNewline.find("diff-line-no-newline").length === 2);

  if (failures.length > 0) {
    for (const failure of failures) {
      console.error(failure);
    }
    process.exit(1);
  }
  console.log("diff view OK");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
