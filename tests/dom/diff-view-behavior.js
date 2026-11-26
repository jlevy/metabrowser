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

  add(...names) {
    const set = this._set();
    for (const name of names) {
      set.add(name);
    }
    this._write(set);
  }

  remove(...names) {
    const set = this._set();
    for (const name of names) {
      set.delete(name);
    }
    this._write(set);
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

  get previousElementSibling() {
    const siblings = this.parentNode?.children ?? [];
    return siblings[siblings.indexOf(this) - 1] ?? null;
  }

  get nextElementSibling() {
    const siblings = this.parentNode?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
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

  /** The first descendant of one class, `.name`, as a page answers it, or null. */
  querySelector(selector) {
    return this.find(selector.slice(1)).find((node) => node !== this) ?? null;
  }

  /** Descendants of one class; markup set as `innerHTML` is not parsed, so it has none. */
  querySelectorAll(selector) {
    return selector.startsWith(".")
      ? this.find(selector.slice(1)).filter((node) => node !== this)
      : [];
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

/**
 * What a toolbar holds, in order: each part's class, and the choosers' end group as the list of
 * what it holds.
 */
function toolbarHolds(toolbar) {
  return (
    toolbar?.children.map((child) =>
      child.classList.contains("diff-toolbar-end")
        ? child.children.map((part) => part.className)
        : child.className,
    ) ?? null
  );
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
      said.includes("2 files changed") &&
        said.includes("1 A, 1 M") &&
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
        header.find("diff-summary-files")[0]?.children[1]?.reads() === " files changed" &&
        header.find("diff-stat-add")[0]?.reads() === "+1,201",
      JSON.stringify(numbers),
    );
    // Each status is a status count, its number and its rows' letter one span that is the
    // shell's status primitive, which inks it by its status, and its bold status count,
    // which draws number and letter alike bold (mb-8iwn); the dots between the groups and
    // the comma between the statuses are the shell's muted punctuation, the dots hidden
    // from a screen reader (mb-vb51). The header is painted by the shell's painters, the
    // SDK's `countPartsNodes` for its file count and `changeLineNodes` for the brief change
    // line after it, the one component for "1 A, 1 M · +1,201 −1" (mb-9ekj), and each dot
    // is one item of its line with the group before it, so a wrap breaks after a dot.
    const letters = header
      .find("file-change-status")
      .map(
        (count) =>
          `${count.className}: ${count.reads()} ${count.getAttribute("data-file-status")}` +
          ` (${count.find("summary-number").map((number) => number.reads())})`,
      );
    /** A part of the header: its class, a mark with its aria-hidden, or a group's parts. */
    const item = (child) =>
      child.classList.contains("summary-punctuation")
        ? `${child.reads()} ${child.getAttribute("aria-hidden")}`
        : ["diff-summary-group", "change-line", "change-line-group", "change-line-stats"].includes(
              child.className,
            )
          ? { [child.className]: child.children.map(item) }
          : child.className;
    const groups = header.children
      .filter(
        (child) => typeof child === "object" && !child.classList.contains("diff-summary-chevron"),
      )
      .map(item);
    const commas = header
      .find("change-line-statuses")[0]
      ?.find("summary-punctuation")
      .map((mark) => `${mark.reads()} ${mark.getAttribute("aria-hidden")}`);
    check(
      "the header's statuses are status counts in their statuses' ink, its marks muted punctuation",
      JSON.stringify(letters) ===
        JSON.stringify([
          "summary-status-count file-change-status: 1 A added (1)",
          "summary-status-count file-change-status: 1 M modified (1)",
        ]) &&
        JSON.stringify(groups) ===
          JSON.stringify([
            { "diff-summary-group": ["diff-summary-files", "· true"] },
            {
              "change-line": [
                { "change-line-group": ["change-line-statuses", "· true"] },
                { "change-line-stats": ["diff-stat-add", "diff-stat-del"] },
              ],
            },
          ]) &&
        JSON.stringify(commas) === JSON.stringify([", null"]) &&
        header.find("visually-hidden").length === 0,
      JSON.stringify({ letters, groups, commas }),
    );
    check(
      "the header names it all for a screen reader, in words",
      header.getAttribute("aria-label") ===
        "2 files changed: 1 added, 1 modified; 1,201 lines added, 1 deleted",
      header.getAttribute("aria-label") ?? "",
    );
    check(
      "the summary starts collapsed",
      header.getAttribute("aria-expanded") === "false" && header.classList.contains("collapsed"),
    );
    // Its chevron comes after its words, as on every toggle that expands a diff summary,
    // where a folder's toggle and a stack's lead with theirs (docs/design-system.md, "Diff
    // Summary").
    const lastPart = header.children.filter((child) => typeof child === "object").at(-1);
    check(
      "the header is a disclosure toggle with the registry's chevron box, after its words",
      header.classList.contains("disclosure-toggle") &&
        header.find("diff-summary-chevron").length === 1 &&
        lastPart?.classList.contains("diff-summary-chevron") === true &&
        lastPart.classList.contains("summary-toggle-chevron") &&
        header.classList.contains("summary-toggle"),
      lastPart?.className ?? "",
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
      "a folder row carries its rolled-up counts, a zero total left out (mb-ox6a)",
      folder?.text().includes("+1,200") && !folder.text().includes("−0"),
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
        rows[0].getAttribute("aria-label") === "a.py, modified, 2 lines added, 2 deleted",
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
      changeLineNodes: require("./changed-files-tree-fixture.js").shellPainters().changeLineNodes,
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

// Another tab switched the server's pin. A mounted diff hears it from its View file opener,
// and its rendered Markdown keeps no link to a file of the head, whose `/view/` address
// would now open the same path at the other pin (A2 of review A on #511). The production
// opener (diff-view-file.js), Markdown views (diff-markdown.js), and inert sanitizer
// (static/inert-html.js) load whole, mounted by the production view; the projection is the
// server's, recorded with Python's parse of each block for the Markdown session
// (tests/fixtures/diff-markdown-responses.json), and is drawn for the corpus's added
// Markdown file. Which addresses a page keeps is the plugin's rule, pinned by that session;
// here the page shows the head, so the link is drawn, until the pin changes.
async function headLinkChecks(mountDiffView, byName) {
  const vm = require("node:vm");
  const recording = JSON.parse(
    fs.readFileSync(path.join(repoRoot, "tests/fixtures/diff-markdown-responses.json"), "utf8"),
  );
  const ORIGIN = "http://127.0.0.1:8123";
  // The DOM the Markdown views and the sanitizer read, beside what the view uses.
  class MarkupElement extends FakeElement {
    get childNodes() {
      return this.children;
    }
    get nodeType() {
      return this.tagName === "#TEXT" ? 3 : 1;
    }
    get nodeValue() {
      return this.tagName === "#TEXT" ? this.textContent : null;
    }
    get parentElement() {
      return this.parentNode;
    }
    append(...nodes) {
      for (const node of nodes) {
        if (node instanceof FakeElement && node.tagName === "#FRAGMENT") {
          this.append(...node.children.splice(0));
        } else if (typeof node === "string") {
          super.append(markupText(node));
        } else {
          super.append(node);
        }
      }
    }
    replaceChildren(...nodes) {
      for (const child of this.children) {
        child.parentNode = null;
      }
      this.children = [];
      this.append(...nodes);
    }
    after(...nodes) {
      this.#insert(1, nodes);
    }
    before(...nodes) {
      this.#insert(0, nodes);
    }
    prepend(...nodes) {
      for (const node of nodes) {
        node.parentNode = this;
      }
      this.children.unshift(...nodes);
    }
    #insert(offset, nodes) {
      const siblings = this.parentNode.children;
      const at = siblings.indexOf(this) + offset;
      for (const node of nodes) {
        node.parentNode = this.parentNode;
      }
      siblings.splice(at, 0, ...nodes);
    }
    querySelectorAll(selector) {
      const wanted =
        {
          "button[data-chip-value]": (node) =>
            node.tagName === "BUTTON" && node.dataset.chipValue !== undefined,
          "a[href], img[src]": (node) =>
            (node.tagName === "A" && node.getAttribute("href") !== null) ||
            (node.tagName === "IMG" && node.getAttribute("src") !== null),
          'a[href^="/view/"]': (node) =>
            node.tagName === "A" && (node.getAttribute("href") ?? "").startsWith("/view/"),
        }[selector] ?? ((node) => node.tagName === selector.toUpperCase());
      return [...this.walk()].filter((node) => node !== this && wanted(node));
    }
  }
  // A rendered file's Source is drawn only while it shows and once it is reached: on a pull
  // request's Docs, a 17,177-line document's Source, drawn at load behind its rendered view,
  // was 72,000 nodes and 4 s of main-thread work (mb-qzgs). Here a 2,000-line Markdown file
  // drawn as Docs draws it, every fold open.
  async function heldSourceChecks() {
    const book = structuredClone(byName.get("added-text-file"));
    const lines = Array.from({ length: 2000 }, (_, index) => ({
      op: "add",
      text: `Line ${index}.`,
    }));
    book.manifest.files[0].additions = lines.length;
    book.patches.f1.hunks = [
      { lines, new_count: lines.length, new_start: 1, old_count: 0, old_start: 0 },
    ];
    const turns = async (count = 40) => {
      for (let turn = 0; turn < count; turn += 1) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    };
    /**
     * Mount the book, with *answer* for its rendered view, and report each observer's
     * sections as *near* or not: the diff's own hydration lookahead (240 px) apart from the
     * rendered views'.
     */
    const mount = async ({ answer, holdMs, near, embedded = false }) => {
      const first = observers.length;
      const host = new MarkupElement("div");
      const handle = mountDiffView(
        host,
        book,
        {
          filterControls: { groupHtml: () => "", bind: () => () => {} },
          ensureAsset: async () => {},
        },
        {
          markdownViews,
          renderMarkdown: answer,
          markdownTargets: markdownViews.markdownTargets(recording.image_route, () => true),
          markdownHoldMs: holdMs,
          unfold: true,
          ...(embedded ? { embedded } : {}),
        },
      );
      const hydration = observers
        .slice(first)
        .find((observer) => observer.options.rootMargin === "0px 0px 240px 0px");
      const report = (observer, isIntersecting) =>
        observer.callback(
          [...observer.targets].map((target) => ({ target, isIntersecting })),
          observer,
        );
      for (const observer of observers.slice(first)) {
        report(observer, observer === hydration ? near.hydration : near.rendered);
      }
      await turns();
      const [body] = host.find("diff-file-body");
      return {
        handle,
        body,
        rows: () => host.find("diff-line").length,
        nodes: () => [...host.walk()].length,
        reach: async () => {
          report(hydration, true);
          await turns();
        },
      };
    };
    const pending = () => new Promise(() => {});

    // Far from the screen, its rendered view not asked for yet: Source shows, and keeps its
    // place, but is not drawn until it is reached.
    const far = await mount({
      answer: pending,
      holdMs: 0,
      near: { hydration: false, rendered: false },
    });
    check(
      "a far rendered file shows Source and draws none of its rows before they are reached",
      far.body.hidden !== true && far.rows() === 0 && far.nodes() < 100,
      JSON.stringify({ hidden: far.body.hidden, rows: far.rows(), nodes: far.nodes() }),
    );
    await far.reach();
    check(
      "a far rendered file's Source is drawn once it is reached",
      far.rows() > 1000,
      String(far.rows()),
    );
    far.handle.dispose();

    // On the first screen, waiting for its rendered view: Source is hidden while it waits,
    // so none of it is drawn, though it is reached.
    const waiting = await mount({
      answer: pending,
      holdMs: 60_000,
      near: { hydration: true, rendered: true },
    });
    check(
      "a rendered file waiting for its rendered view draws none of its hidden Source",
      waiting.body.hidden === true && waiting.rows() === 0 && waiting.nodes() < 100,
      JSON.stringify({ hidden: waiting.body.hidden, rows: waiting.rows(), nodes: waiting.nodes() }),
    );
    waiting.handle.dispose();

    // Its rendered view answered: Source stays undrawn.
    const answered = await mount({
      answer: async () => structuredClone(recording.answers.f1["view=prefer-full"]),
      holdMs: 60_000,
      near: { hydration: true, rendered: true },
    });
    check(
      "a rendered file whose rendered view is shown never draws its Source",
      answered.body.hidden === true && answered.rows() === 0,
      JSON.stringify({ hidden: answered.body.hidden, rows: answered.rows() }),
    );
    answered.handle.dispose();

    // Past the loading delay with no answer, a first-screen file still waits, its Source
    // undrawn: shown then, it was replaced when the answer came, and the files below moved.
    const late = await mount({
      answer: pending,
      holdMs: 0,
      near: { hydration: true, rendered: true },
    });
    check(
      "a first-screen file past its loading delay still waits and draws none of its Source",
      late.body.hidden === true && late.rows() === 0,
      JSON.stringify({ hidden: late.body.hidden, rows: late.rows() }),
    );
    late.handle.dispose();

    // A file drawn alone in a host of its own, as a guided review's document is, has
    // nothing after it in its diff to keep out of sight: past its host's hold with no
    // answer it shows Source, and the answer that comes late replaces nothing, so the
    // host's page does not move.
    let lateAnswer = () => {};
    const alone = await mount({
      answer: () =>
        new Promise((resolve) => {
          lateAnswer = () => resolve(structuredClone(recording.answers.f1["view=prefer-full"]));
        }),
      holdMs: 0,
      near: { hydration: true, rendered: true },
      embedded: true,
    });
    const atHold = { hidden: alone.body.hidden, rows: alone.rows() };
    lateAnswer();
    await turns();
    check(
      "a file drawn alone shows Source at its host's hold, and a late answer replaces nothing",
      atHold.hidden !== true && atHold.rows > 1000 && alone.body.hidden !== true,
      JSON.stringify({ atHold, after: alone.body.hidden }),
    );
    alone.handle.dispose();

    // The server refuses its rendered view: it shows Source, drawn there.
    const refused = await mount({
      answer: async () => ({ status: "refused" }),
      holdMs: 60_000,
      near: { hydration: true, rendered: true },
    });
    check(
      "a first-screen file whose rendered view is refused shows Source and draws it",
      refused.body.hidden !== true && refused.rows() > 1000,
      JSON.stringify({ hidden: refused.body.hidden, rows: refused.rows() }),
    );
    refused.handle.dispose();
  }

  const markupText = (value) => {
    const node = new MarkupElement("#text");
    node.textContent = String(value);
    return node;
  };
  const parsed = (nodes) =>
    nodes.map((node) => {
      if (typeof node === "string") {
        return markupText(node);
      }
      const built = new MarkupElement(node.tag);
      for (const [name, value] of node.attrs) {
        built.setAttribute(name, value);
      }
      built.append(...parsed(node.children));
      return built;
    });
  const template = () => {
    const made = new MarkupElement("template");
    Object.defineProperty(made, "innerHTML", {
      set(html) {
        if (!(html in recording.trees)) {
          throw new Error(`no recorded parse for ${html}`);
        }
        const content = new MarkupElement("#fragment");
        content.append(...parsed(recording.trees[html]));
        made.content = content;
      },
    });
    return made;
  };
  const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
  const realm = { window: {}, URL };
  vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), realm, { filename: inertPath });
  const markdownViews = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-markdown.js")).href
  );

  const saved = {
    document: global.document,
    window: global.window,
    IntersectionObserver: global.IntersectionObserver,
  };
  const observers = [];
  global.IntersectionObserver = class IntersectionObserver {
    constructor(callback, options = {}) {
      this.callback = callback;
      this.options = options;
      this.targets = new Set();
      observers.push(this);
    }
    observe(target) {
      this.targets.add(target);
    }
    unobserve(target) {
      this.targets.delete(target);
    }
    disconnect() {
      this.targets.clear();
    }
  };
  global.document = {
    ...saved.document,
    activeElement: null,
    createElement: (tag) => (tag === "template" ? template() : new MarkupElement(tag)),
    createTextNode: markupText,
    createDocumentFragment: () => new MarkupElement("#fragment"),
    implementation: {
      createHTMLDocument: () => ({
        createElement: (tag) => new MarkupElement(tag),
        createTextNode: markupText,
      }),
    },
  };
  global.window = {
    location: { origin: ORIGIN },
    MetabrowserInertHtml: realm.window.MetabrowserInertHtml,
  };
  try {
    // A stack's rendered changes omit View file controls. The view still watches
    // the pin for links in Markdown, including after the first projection is drawn.
    let pinChanged = null;
    let headOpen = true;
    const fallback =
      "https://github.com/octo/demo/blob/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/docs/setup.md";
    const requested = [];
    const container = new MarkupElement("div");
    const handle = mountDiffView(
      container,
      byName.get("added-text-file"),
      {
        filterControls: { groupHtml: () => "", bind: () => () => {} },
        ensureAsset: async () => {},
      },
      {
        onPinChanged(listener) {
          pinChanged = listener;
          return () => {
            pinChanged = null;
          };
        },
        markdownViews,
        renderMarkdown: async (fileId) => {
          requested.push(fileId);
          return structuredClone(recording.answers.f1["view=concise"]);
        },
        markdownTargets: markdownViews.markdownTargets(
          recording.image_route,
          () => headOpen,
          (href, links) => links?.viewFileUrl(null, "b".repeat(40), href) ?? null,
        ),
        markdownHoldMs: 0,
      },
    );
    for (const observer of observers) {
      observer.callback(
        [...observer.targets].map((target) => ({ target, isIntersecting: true })),
        observer,
      );
    }
    for (let turn = 0; turn < 20; turn += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    // The bar the production view builds for a rendered file: the name's group, the
    // disclosure, its copy control, and its stats, then the group at the bar's end, the chooser
    // behind its progress mark. This document offers no View file control, which would
    // sit between the two groups (tests/dom/diff-view-file-session.js).
    const [fileBar] = container.find("diff-file-bar");
    const groups = fileBar.children.map((group) =>
      group.children.map((child) => String(child.className).split(" ").at(-1)),
    );
    check(
      "a rendered file's bar puts copy beside the name and the chooser at its end",
      JSON.stringify(fileBar.children.map((group) => group.className)) ===
        JSON.stringify(["diff-file-lead", "diff-file-end"]) &&
        JSON.stringify(groups) ===
          JSON.stringify([
            ["expanded", "diff-file-copy", "diff-file-facts"],
            ["diff-markdown-progress", "diff-markdown-control"],
          ]),
      JSON.stringify(groups),
    );
    const drawn = () =>
      container.querySelectorAll("a").filter((link) => link.closest(".diff-markdown") !== null);
    const toHead = drawn().filter((link) => (link.getAttribute("href") ?? "").startsWith("/view/"));
    check(
      "a page at the head draws rendered Markdown's link to a file of the head",
      requested.length === 1 && toHead.length === 1,
      JSON.stringify({ requested, hrefs: drawn().map((link) => link.getAttribute("href")) }),
    );
    check("the page heard no pin change yet", typeof pinChanged === "function");
    // The first file already rendered when the optional resolver became available.
    global.window.MetabrowserRepositoryLinks = { viewFileUrl: () => fallback };
    headOpen = false;
    pinChanged?.();
    check(
      "a stale diff with a late resolver updates links without View file controls",
      toHead.length === 1 &&
        toHead.every((link) => link.getAttribute("href") === fallback && drawn().includes(link)),
      JSON.stringify(drawn().map((link) => link.getAttribute("href"))),
    );
    handle.dispose();
    check("disposal lets the page's pin-change news go", pinChanged === null);

    // A Markdown file whose changes did not load has the chooser too: Source is chosen,
    // Full and Concise are unavailable for the reason the file's body gives, and no
    // projection is asked for it (mb-rm40).
    const unread = structuredClone(byName.get("added-text-file"));
    unread.manifest.files[0].availability = "too_large";
    unread.patches = {};
    const choosers = [];
    const asked = requested.length;
    const unreadContainer = new MarkupElement("div");
    const unreadHandle = mountDiffView(
      unreadContainer,
      unread,
      {
        filterControls: {
          groupHtml(spec) {
            if (String(spec.label).endsWith(" diff format")) {
              choosers.push(spec);
            }
            return "";
          },
          bind: () => () => {},
        },
        ensureAsset: async () => {},
      },
      {
        markdownViews,
        renderMarkdown: async (fileId) => {
          requested.push(fileId);
          return null;
        },
        markdownTargets: markdownViews.markdownTargets(recording.image_route, () => true),
        markdownHoldMs: 0,
      },
    );
    for (const observer of observers) {
      observer.callback(
        [...observer.targets].map((target) => ({ target, isIntersecting: true })),
        observer,
      );
    }
    for (let turn = 0; turn < 20; turn += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    const chooser = choosers.at(-1);
    const said = unreadContainer
      .querySelectorAll("div")
      .filter((node) => node.className === "diff-availability")
      .map((node) => node.textContent);
    check(
      "a Markdown file whose changes did not load keeps its chooser, its views unavailable for the reason its body gives",
      chooser?.value === "source" &&
        JSON.stringify(chooser.options.map((option) => option.value)) ===
          JSON.stringify(["rendered", "source"]) &&
        chooser.options[0].tip === "This change is too large to show inline." &&
        chooser.options[1].tip === undefined &&
        said.includes("This change is too large to show inline.") &&
        requested.length === asked,
      JSON.stringify({ choosers, said, requested }),
    );
    unreadHandle.dispose();

    await heldSourceChecks();
  } finally {
    global.document = saved.document;
    global.window = saved.window;
    global.IntersectionObserver = saved.IntersectionObserver;
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
    anchorRow,
    composeTextRuns,
    currentAbsence,
    fileDisclosure,
    hunkGaps,
    mountDiffSummary,
    mountDiffView: mountDiffViewImpl,
    mountFilePatch,
    patchRowCounts,
    projectCurrentHunk,
    reservedRows,
    setChangeLoader,
  } = await import(pathToFileURL(viewPath).href);
  // A count summary and a brief change line are painted by the shell's painters, as the
  // SDK's `countPartsNodes`, `changeLine`, and `changeLineNodes` hand them the page's
  // document (formatters.js).
  const painters = require("./changed-files-tree-fixture.js").shellPainters();
  const defaultTestApi = {
    highlightSyntax: async () => null,
    isLargeTextPreview: () => true,
    langForPath: () => "",
    prefs: { get: () => "unified" },
    ...painters,
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

  // Current's rows, by the rules that draw and reserve them: the new file's lines alone,
  // a hunk with none of them left out, and a file with no new version said in a sentence.
  const opsHunk = (...ops) => ({ lines: ops.map((op) => ({ op })) });
  check(
    "Current draws a hunk's context and added lines, in order, and no removed one",
    JSON.stringify(
      projectCurrentHunk({
        lines: ["context", "del", "add", "context"].map((op, at) => ({ op, at })),
      }).map((line) => line.at),
    ) === "[0,2,3]",
  );
  check(
    "a held patch counts in Current the rows Current draws",
    JSON.stringify(
      patchRowCounts(
        { hunks: [opsHunk("context", "del", "del", "add", "context"), opsHunk("del")] },
        "current",
      ),
    ) === JSON.stringify({ lines: 3, headers: 1, folds: 0, notices: 0 }),
  );
  check(
    "a long removal folds in Diff and draws nothing in Current",
    patchRowCounts({ hunks: [opsHunk("context", ...Array(50).fill("del"))] }, "current").folds ===
      0 &&
      patchRowCounts({ hunks: [opsHunk("context", ...Array(50).fill("del"))] }, "unified").folds ===
        1,
  );
  check(
    "a deferred file reserves its added lines and context in Current",
    reservedRows({ additions: 10, deletions: 5 }, "current") === 17 &&
      reservedRows({ additions: 10, deletions: 5 }, "unified") === 22,
  );
  check(
    "a deleted file and an emptied one say why Current shows no lines",
    currentAbsence({ kind: "deleted" }, []) ===
      "This file was deleted, so it has no current version." &&
      currentAbsence({ kind: "modified" }, [{ newStart: 0, newCount: 0 }]) ===
        "This file is empty now." &&
      currentAbsence({ kind: "modified" }, [{ newStart: 4, newCount: 0 }]) === null,
  );
  // A held patch of a file with no current version is counted as the one sentence Current
  // draws for it, as its drawing is, and not as its hunks.
  const emptiedPatch = {
    hunks: [{ ...opsHunk("del", "del"), new_start: 0, new_count: 0 }],
  };
  check(
    "a held deleted or emptied file counts in Current as the sentence that says why",
    JSON.stringify(patchRowCounts(emptiedPatch, "current", { kind: "deleted" })) ===
      JSON.stringify({ lines: 0, headers: 0, folds: 0, notices: 1 }) &&
      JSON.stringify(patchRowCounts(emptiedPatch, "current", { kind: "modified" })) ===
        JSON.stringify({ lines: 0, headers: 0, folds: 0, notices: 1 }) &&
      JSON.stringify(patchRowCounts(emptiedPatch, "unified", { kind: "modified" })) ===
        JSON.stringify({ lines: 2, headers: 1, folds: 0, notices: 0 }),
    JSON.stringify([
      patchRowCounts(emptiedPatch, "current", { kind: "deleted" }),
      patchRowCounts(emptiedPatch, "current", { kind: "modified" }),
      patchRowCounts(emptiedPatch, "unified", { kind: "modified" }),
    ]),
  );

  // The unchanged lines a file's hunks leave out (`hunkGaps`): above each hunk, by the new
  // side's numbers, with what an old number adds, and below the last, which is open until an
  // answer says where the file ends. A hunk's line records need only their op here.
  const span = (oldStart, oldCount, newStart, newCount, ...ops) => ({
    oldStart,
    oldCount,
    newStart,
    newCount,
    lines: ops.map((op) => ({ op, noNewline: false })),
  });
  const twoHunks = [
    span(2, 7, 2, 7, ...Array(3).fill("context"), "del", "add", ...Array(3).fill("context")),
    span(27, 7, 27, 8, ...Array(3).fill("context"), "add", ...Array(4).fill("context")),
  ];
  check(
    "a file's gaps lie before, between, and after its hunks, at the new side's numbers",
    JSON.stringify(hunkGaps(twoHunks, 3)) ===
      JSON.stringify([
        { start: 1, end: 2, offset: 0 },
        { start: 9, end: 27, offset: 0 },
        { start: 35, end: null, offset: -1 },
      ]),
    JSON.stringify(hunkGaps(twoHunks, 3)),
  );
  check(
    "an answer that says where the file ends closes the last gap there, or leaves none",
    JSON.stringify(hunkGaps(twoHunks, 3, 40).at(-1)) ===
      JSON.stringify({ start: 35, end: 41, offset: -1 }) &&
      hunkGaps(twoHunks, 3, 34).at(-1) === null,
  );
  check(
    "a hunk at the file's first line has no gap above it",
    hunkGaps([span(1, 4, 1, 4, "del", "add", "context", "context", "context")], 3)[0] === null,
  );
  check(
    "a last hunk ending in fewer context lines than Git writes ends the file",
    hunkGaps([span(10, 4, 10, 4, ...Array(3).fill("context"), "add")], 3).at(-1) === null &&
      hunkGaps([span(10, 3, 10, 4, ...Array(3).fill("context"), "add", "context")], 3).at(-1) ===
        null,
  );
  const endsUnended = span(
    10,
    6,
    10,
    7,
    ...Array(3).fill("context"),
    "add",
    ...Array(3).fill("context"),
  );
  endsUnended.lines.at(-1).noNewline = true;
  check(
    "a last line with no newline after it ends the file, so no gap follows it",
    hunkGaps([endsUnended], 3).at(-1) === null,
  );
  check(
    "a side with no lines in a hunk starts after the line it names",
    JSON.stringify(hunkGaps([span(3, 0, 4, 2, "add", "add")], 0)[0]) ===
      JSON.stringify({ start: 1, end: 4, offset: 0 }),
    JSON.stringify(hunkGaps([span(3, 0, 4, 2, "add", "add")], 0)),
  );
  check(
    "gaps whose old and new spans disagree are left out, and no hunks have no gaps",
    hunkGaps([span(5, 1, 9, 1, "context")], 3)[0] === null && hunkGaps([], 3).length === 0,
  );
  // A held patch, where its diff reads gaps, counts each gap's bar in place of its hunk's
  // header, and the bar below its last hunk.
  const gapPatch = {
    hunks: [
      {
        ...opsHunk(...Array(3).fill("context"), "add", ...Array(3).fill("context")),
        old_start: 1,
        old_count: 6,
        new_start: 1,
        new_count: 7,
      },
      {
        ...opsHunk(...Array(3).fill("context"), "add", ...Array(3).fill("context")),
        old_start: 20,
        old_count: 6,
        new_start: 21,
        new_count: 7,
      },
    ],
  };
  const textChange = { new: { entry_type: "file" } };
  check(
    "a held patch whose diff reads gaps counts their bars as folds in place of headers",
    JSON.stringify(patchRowCounts(gapPatch, "unified", textChange, 3)) ===
      JSON.stringify({ lines: 14, headers: 1, folds: 2, notices: 0 }) &&
      JSON.stringify(patchRowCounts(gapPatch, "unified", textChange)) ===
        JSON.stringify({ lines: 14, headers: 2, folds: 0, notices: 0 }) &&
      JSON.stringify(patchRowCounts(gapPatch, "unified", { binary: true, ...textChange }, 3)) ===
        JSON.stringify({ lines: 14, headers: 2, folds: 0, notices: 0 }),
    JSON.stringify(patchRowCounts(gapPatch, "unified", textChange, 3)),
  );
  // The row a Diff | Current choice keeps: rows 20 px tall from 5 px, in a pane from 100 to
  // 700 px, so row 4 (85 to 105 px) is at its top.
  const rowsOf = (count, kept = () => true) => {
    const asked = [];
    const rowAt = (index) => {
      asked.push(index);
      return { top: 5 + index * 20, bottom: 25 + index * 20, kept: kept(index) };
    };
    return { count, rowAt, asked };
  };
  const keep = ({ count, rowAt }) => anchorRow(count, rowAt, 100, 700);
  check(
    "the row at the pane's top keeps its offset, a part of it above the top",
    JSON.stringify(keep(rowsOf(50))) === JSON.stringify({ index: 4, offset: -15 }),
    JSON.stringify(keep(rowsOf(50))),
  );
  check(
    "a row the choice leaves out gives its place to the next row it draws, on the screen",
    JSON.stringify(keep(rowsOf(50, (index) => index !== 4 && index !== 5))) ===
      JSON.stringify({ index: 6, offset: 25 }),
    JSON.stringify(keep(rowsOf(50, (index) => index !== 4 && index !== 5))),
  );
  check(
    "where it leaves out the rest of the screen, the last row above goes just above the top",
    JSON.stringify(keep(rowsOf(50, (index) => index < 4 || index > 40))) ===
      JSON.stringify({ index: 3, offset: -20 }),
    JSON.stringify(keep(rowsOf(50, (index) => index < 4 || index > 40))),
  );
  check(
    "with none above, the first row below goes to the top",
    JSON.stringify(keep(rowsOf(50, (index) => index === 45))) ===
      JSON.stringify({ index: 45, offset: 0 }),
    JSON.stringify(keep(rowsOf(50, (index) => index === 45))),
  );
  check(
    "a file with no row the choice draws, or no row at all, keeps its own top",
    keep(rowsOf(50, () => false)) === null && keep(rowsOf(0)) === null,
  );
  const long = rowsOf(100000);
  const longKept = keep(long);
  check(
    "a long file's row at the top is found by bisection, measuring few rows",
    JSON.stringify(longKept) === JSON.stringify({ index: 4, offset: -15 }) &&
      new Set(long.asked).size <= 20,
    JSON.stringify({ longKept, measured: new Set(long.asked).size }),
  );

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
  // No preference store at all, under the host's other fields: the shell's painters, which
  // say each file bar's lines, as every page has them.
  mountDiffViewImpl(defaultLayout, byName.get("modified-with-heading"), {
    ...defaultTestApi,
    prefs: undefined,
  });
  check(
    "missing layout preference defaults to split",
    defaultLayout.find("diff-root")[0].dataset.layout === "split",
  );

  let layoutChange = null;
  let layoutSyntaxCalls = 0;
  const preferenceWrites = [];
  const layoutSpecs = [];
  let unbound = 0;
  // The toolbar's Diff | Current chooser is bound apart from the layout control.
  let showBinds = 0;
  let showUnbound = 0;
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
        if (spec.key === "diff-layout") {
          layoutSpecs.push(spec);
        }
        return `<span role="radiogroup" data-select="${spec.select}" data-layout="${spec.layout}">${spec.options.map((option) => option.label).join("/")}</span>`;
      },
      bind: (root, handlers) => {
        if (!root.classList.contains("diff-layout-control")) {
          showBinds += 1;
          return () => {
            showUnbound += 1;
          };
        }
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
  check("layout override leaves the default preference alone", preferenceWrites.length === 0);
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
  // Diff | Current is in the diff's toolbar, beside the layout control: one choice for the
  // diff, which draws the new file's lines in one column whatever the layout, while the
  // layout control keeps its place, says why it is unavailable, and changes nothing.
  let showChange = null;
  let currentLayoutChange = null;
  const showSpecs = [];
  const currentApi = {
    ...layoutApi,
    filterControls: {
      groupHtml: (spec) => {
        showSpecs.push(spec);
        return "";
      },
      bind: (root, handlers) => {
        if (root.classList.contains("diff-layout-control")) {
          currentLayoutChange = handlers.onChange;
        } else {
          showChange = handlers.onChange;
        }
        return () => {};
      },
    },
  };
  const currentHost = new FakeElement("div");
  const currentHandle = mountDiffView(currentHost, byName.get("modified-with-heading"), currentApi);
  const codeBar = currentHost.find("diff-file-bar")[0];
  const showSpec = showSpecs.find((spec) => spec.key === "diff-show");
  const currentToolbar = currentHost.find("diff-toolbar")[0];
  check(
    "the toolbar ends with one group, Diff | Current, then Split | Unified",
    JSON.stringify(toolbarHolds(currentToolbar)) ===
      JSON.stringify([["diff-show-control", "diff-layout-control"]]),
    JSON.stringify(toolbarHolds(currentToolbar)),
  );
  check(
    "a code file's bar holds no chooser and does not wrap",
    codeBar.find("diff-file-end")[0].children.length === 0 &&
      currentHost.find("diff-show-control").length === 1 &&
      !codeBar.classList.contains("diff-file-bar-markdown"),
  );
  check(
    "the chooser is one joined, exclusive group named for what it chooses",
    showSpec?.label === "Comparison view" &&
      showSpec.layout === "joined" &&
      showSpec.select === "one" &&
      showSpec.value === "diff" &&
      JSON.stringify(showSpec.options.map((option) => [option.label, option.tip])) ===
        JSON.stringify([
          ["Diff", "Show additions and removals with surrounding context."],
          ["Excerpt", "Show the new version around the changes."],
        ]),
    JSON.stringify(showSpec),
  );
  const writesBefore = preferenceWrites.length;
  showChange(showSpec.key, "current", "one");
  await Promise.resolve();
  const currentRoot = currentHost.find("diff-root")[0];
  const currentLines = currentHost.find("diff-line");
  check(
    "Current draws the new file's lines in one column, in place of Split",
    currentRoot.dataset.show === "current" &&
      currentHost.find("diff-split-row").length === 0 &&
      currentHost.find("diff-hunk-current").length === 1 &&
      JSON.stringify(currentLines.map((row) => row.find("diff-line-marker")[0].textContent)) ===
        JSON.stringify([" ", "+", " "]) &&
      currentLines.every((row) => row.find("diff-line-number").length === 1),
    `${currentHost.find("diff-split-row").length} split rows, ${currentLines.length} lines`,
  );
  check(
    "its hunk header names the new side's range alone",
    currentHost.find("diff-hunk-header")[0].textContent.startsWith("@@ +3,"),
    currentHost.find("diff-hunk-header")[0].textContent,
  );
  const layoutInCurrent = showSpecs.filter((spec) => spec.key === "diff-layout").at(-1);
  check(
    "the layout control keeps the stored layout and says why neither chip can be chosen",
    layoutInCurrent.value === "split" &&
      layoutInCurrent.options.every(
        (option) => option.tip === "Switch to Diff to change the layout.",
      ),
    JSON.stringify(layoutInCurrent),
  );
  check(
    "the choice is stored as diff.show, which every surface but Docs shares",
    JSON.stringify(preferenceWrites.slice(writesBefore)) ===
      JSON.stringify([{ key: "diff.show", value: "excerpt" }]),
    JSON.stringify(preferenceWrites.slice(writesBefore)),
  );
  const writesInCurrent = preferenceWrites.length;
  currentLayoutChange("diff-layout", "unified", "one");
  check(
    "choosing a layout in Current changes nothing and stores nothing",
    currentRoot.dataset.layout === "split" &&
      currentHost.find("diff-hunk-current").length === 1 &&
      preferenceWrites.length === writesInCurrent,
  );
  showChange(showSpec.key, "diff", "one");
  await Promise.resolve();
  check(
    "Diff draws the stored layout again",
    currentRoot.dataset.show === "diff" &&
      currentHost.find("diff-split-row").length === 3 &&
      showSpecs.filter((spec) => spec.key === "diff-layout").at(-1).options[1].tip === undefined,
  );
  currentHandle.dispose();
  const deletedCurrent = new FakeElement("div");
  let deletedShow = null;
  const deletedHandle = mountDiffView(deletedCurrent, byName.get("deleted-file"), {
    ...currentApi,
    filterControls: {
      groupHtml: (spec) => {
        if (spec.key === "diff-show") {
          deletedShow = spec.key;
        }
        return "";
      },
      bind: (root, handlers) => {
        if (!root.classList.contains("diff-layout-control")) {
          showChange = handlers.onChange;
        }
        return () => {};
      },
    },
  });
  showChange(deletedShow, "current", "one");
  await Promise.resolve();
  check(
    "a deleted file says in Current that it has no current version",
    deletedCurrent.text().includes("This file was deleted, so it has no current version.") &&
      deletedCurrent.find("diff-line").length === 0,
  );
  deletedHandle.dispose();

  // A host that fixes the layout and opens on Current, as a pull request's Docs tab does:
  // its toolbar holds Diff | Current alone, it opens in Current with nothing stored, and it
  // reads and writes its own preference, never `diff.show`, so a choice on Changes does not
  // move it, nor its own Changes. A stored value that is not a choice reads as its default.
  const docsReads = [];
  const docsWrites = [];
  const docsStored = new Map([["diff.show", "diff"]]);
  let docsChange = null;
  const docsSpecs = [];
  const docsApi = {
    ...layoutApi,
    prefs: {
      get: (key, fallback) => {
        docsReads.push(key);
        return docsStored.has(key) ? docsStored.get(key) : fallback;
      },
      set: (key, value) => {
        docsWrites.push({ key, value });
        docsStored.set(key, value);
        return true;
      },
    },
    filterControls: {
      groupHtml: (spec) => {
        docsSpecs.push(spec);
        return "";
      },
      bind: (root, handlers) => {
        if (root.classList.contains("diff-show-control")) {
          docsChange = handlers.onChange;
        }
        return () => {};
      },
    },
  };
  const docsOptions = { layout: "unified", show: "current", showPreference: "github.docs.show" };
  const docsHost = new FakeElement("div");
  const docsHandle = mountDiffView(
    docsHost,
    byName.get("modified-with-heading"),
    docsApi,
    docsOptions,
  );
  const docsToolbar = docsHost.find("diff-toolbar")[0];
  check(
    "a fixed layout's toolbar is drawn for Diff | Current alone",
    JSON.stringify(toolbarHolds(docsToolbar)) === JSON.stringify([["diff-show-control"]]) &&
      docsSpecs.every((spec) => spec.key === "diff-show"),
    JSON.stringify(toolbarHolds(docsToolbar)),
  );
  check(
    "a surface that opens on Current does so with nothing stored, reading its own preference",
    docsHost.find("diff-root")[0].dataset.show === "current" &&
      docsHost.find("diff-hunk-current").length === 1 &&
      docsSpecs.at(-1).value === "current" &&
      JSON.stringify(docsReads) === JSON.stringify(["github.docs.show"]),
    JSON.stringify({ reads: docsReads, value: docsSpecs.at(-1)?.value }),
  );
  docsChange("diff-show", "diff", "one");
  check(
    "its choice is stored as its own preference, and diff.show is untouched",
    JSON.stringify(docsWrites) === JSON.stringify([{ key: "github.docs.show", value: "diff" }]) &&
      docsStored.get("diff.show") === "diff" &&
      docsHost.find("diff-root")[0].dataset.show === "diff",
    JSON.stringify(docsWrites),
  );
  docsHandle.dispose();
  docsStored.set("github.docs.show", "both");
  const oddDocs = new FakeElement("div");
  const oddDocsHandle = mountDiffView(
    oddDocs,
    byName.get("modified-with-heading"),
    docsApi,
    docsOptions,
  );
  check(
    "a stored value that is not a choice reads as the surface's own default",
    oddDocs.find("diff-root")[0].dataset.show === "current",
  );
  oddDocsHandle.dispose();
  docsStored.set("diff.show", "current");
  const changesHost = new FakeElement("div");
  const changesHandle = mountDiffView(changesHost, byName.get("modified-with-heading"), docsApi);
  check(
    "a surface with no default of its own opens on what diff.show holds",
    changesHost.find("diff-root")[0].dataset.show === "current" && docsReads.at(-1) === "diff.show",
    JSON.stringify(docsReads),
  );
  changesHandle.dispose();

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
    "the Diff | Current binding is one per diff and disposes with it",
    showBinds > 0 && showUnbound === 1,
    `${showBinds} bound, ${showUnbound} unbound`,
  );
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
      bind: (root, handlers) => {
        if (root.classList.contains("diff-layout-control")) {
          boundedLayoutChange = handlers.onChange;
        }
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
  // The bar is two groups: what names the file, the disclosure with the copy control
  // right after it and then the change's stats, and the controls at its end, here none.
  const bar = container.find("diff-file-bar")[0];
  const [lead, end] = bar.children;
  check(
    "the bar leads with the name's group and ends with its controls' group",
    bar.children.length === 2 &&
      lead.classList.contains("diff-file-lead") &&
      end.classList.contains("diff-file-end"),
    JSON.stringify(bar.children.map((child) => child.className)),
  );
  const facts = lead.children[2];
  check(
    "copy control sits right after the disclosure, beside the name, before its stats",
    lead.children.length === 3 &&
      lead.children[0] === toggle &&
      lead.children[1] === copy &&
      facts.classList.contains("diff-file-facts"),
    JSON.stringify(lead.children.map((child) => child.className)),
  );
  check("a bar with nowhere to go ends with no control", end.children.length === 0);
  check(
    "the name ends the disclosure, and the stats follow the copy control",
    toggle.children.length === 3 &&
      toggle.children[2].classList.contains("diff-file-path") &&
      facts.children[0]?.classList.contains("diff-file-stats") === true,
    JSON.stringify(toggle.children.map((child) => child.className)),
  );
  check(
    "the stats describe the disclosure they left",
    typeof facts.getAttribute("id") === "string" &&
      toggle.getAttribute("aria-describedby") === facts.getAttribute("id"),
  );
  // The bar's lines are the shell's brief change line of its totals alone (mb-ox6a).
  const stats = container.find("diff-file-stats")[0];
  const pair = stats.find("change-line-stats")[0];
  check(
    "stat pair renders add then del, as the shell's brief change line",
    stats.children.length === 1 &&
      stats.children[0].classList.contains("change-line") &&
      pair?.children[0]?.classList.contains("diff-stat-add") === true &&
      pair.children[1]?.classList.contains("diff-stat-del") === true,
  );

  // The whole bar is one activation surface: bar clicks toggle, the
  // button's own (bubbled) click toggles, the copy control does not.
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
  stats.click();
  check(
    "a click on the stats toggles, as anywhere else on the bar",
    body.classList.contains("diff-file-body-collapsed") &&
      toggle.getAttribute("aria-expanded") === "false",
  );
  toggle.click();
  // What Changes' bar and trigger are made of, which a card another page draws around a
  // file must match (below, at `fileDisclosure`).
  const classesOf = (node) => String(node.className).split(" ").filter(Boolean).sort().join(" ");
  const changesDisclosure = {
    bar: classesOf(bar),
    toggle: classesOf(toggle),
    chevron: classesOf(toggle.children[0]),
    type: toggle.getAttribute("type"),
    tag: toggle.tagName,
  };

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
  // tree. Without the tree, the totals stand as a line, the header without its statuses, in
  // the shell's number format, with no toggle: only the statuses and the tree of files are
  // lost (A3 of review A on #448), and the muted dot still sets the totals apart (mb-vb51).
  const plain = many.find("diff-summary")[0];
  check(
    "a change set without the shared tree keeps its totals line",
    plain?.reads().includes("2 files changed") &&
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
  const plainMarks = plain
    ?.find("summary-punctuation")
    .map((mark) => `${mark.reads()} ${mark.getAttribute("aria-hidden")}`);
  check(
    "the totals line sets its totals apart with the Diff summary's muted, hidden dot",
    JSON.stringify(plainMarks) === JSON.stringify(["· true"]),
    JSON.stringify(plainMarks),
  );
  // A line has no name that says it in words, as the toggle's does, so a screen reader is
  // told a comma in its dot's place, and the dot is one item with the file count before it.
  const plainGroup = plain?.find("diff-summary-group")[0];
  check(
    "the totals line says a comma in its hidden dot's place",
    JSON.stringify(
      plainGroup?.children.map((part) => `${part.className}: ${part.reads()}`) ?? null,
    ) ===
      JSON.stringify([
        "diff-summary-files: 2 files changed",
        "summary-punctuation: ·",
        "visually-hidden: , ",
      ]) && plain.children[0] === plainGroup,
    JSON.stringify(plainGroup?.children.map((part) => part.className) ?? null),
  );
  const hosted = new FakeElement("div");
  mountDiffView(hosted, twoFiles, undefined, { showSummary: false, changedFiles: sharedTree });
  check(
    "revision-hosted change sets leave the aggregate summary to their commit header",
    hosted.find("diff-summary").length === 0,
  );
  check("revision-hosted change sets keep their toolbar", hosted.find("diff-toolbar").length === 1);
  // A layout the host fixes has no layout control, and leaves the toolbar what else it holds:
  // a change set's totals and Diff | Current, here; Diff | Current alone, as on a pull
  // request's Docs tab. A toolbar with nothing in it, where the chip family is not loaded,
  // is not drawn, and the files follow at once.
  const fixedApi = { filterControls: { groupHtml: () => "", bind: () => () => {} } };
  const fixedTotals = new FakeElement("div");
  mountDiffView(fixedTotals, twoFiles, fixedApi, { layout: "unified" });
  check(
    "a fixed layout keeps the toolbar for the totals, without the layout control",
    fixedTotals.find("diff-toolbar").length === 1 &&
      fixedTotals.find("diff-summary").length === 1 &&
      fixedTotals.find("diff-layout-control").length === 0 &&
      fixedTotals.find("diff-show-control").length === 1 &&
      fixedTotals.find("diff-root")[0]?.dataset.layout === "unified",
  );
  const fixedBare = new FakeElement("div");
  mountDiffView(fixedBare, twoFiles, fixedApi, { showSummary: false, layout: "unified" });
  const fixedToolbar = fixedBare.find("diff-toolbar")[0];
  check(
    "a fixed layout with nothing else for the toolbar draws it for Diff | Current alone",
    JSON.stringify(toolbarHolds(fixedToolbar)) === JSON.stringify([["diff-show-control"]]),
    JSON.stringify(toolbarHolds(fixedToolbar)),
  );
  const fixedBare2 = new FakeElement("div");
  mountDiffView(
    fixedBare2,
    twoFiles,
    { filterControls: undefined },
    {
      showSummary: false,
      layout: "unified",
    },
  );
  const fixedRoot = fixedBare2.find("diff-root")[0];
  check(
    "a fixed layout with nothing at all for the toolbar draws none",
    fixedBare2.find("diff-toolbar").length === 0 &&
      fixedBare2.find("diff-layout-control").length === 0 &&
      fixedRoot?.children[0]?.classList.contains("diff-hydration-failure") === true &&
      fixedRoot.children[1]?.classList.contains("diff-file") === true,
    JSON.stringify(fixedRoot?.children.map((child) => child.className) ?? null),
  );
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
    { formatInteger: (count) => String(count), ...painters },
    { changedFiles: sharedTree, openFile() {} },
  );
  const drawn = slot.children[0];
  check(
    "a page draws a Diff summary on its own from the document, its file count on the size line",
    slot.children.length === 1 &&
      drawn.classList.contains("diff-summary-toggle") &&
      drawn.reads().includes("2 M") &&
      !drawn.reads().includes("files changed"),
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
    !cutHeader?.reads().includes("files changed") &&
      cutHeader?.reads().includes("+15") &&
      cutHeader.reads().includes("−3") &&
      cutHeader.reads().includes("(2 listed)") &&
      cutHeader.find("change-line-statuses").length === 0,
    cutHeader?.reads() ?? "",
  );
  // The note's figure is a count's number: bold, and muted with the note (B4 of review B on
  // #478).
  const listedNumbers = (place) =>
    JSON.stringify(
      place
        ?.find("diff-summary-note")
        .map((note) => note.find("summary-number").map((number) => number.reads())),
    );
  check(
    "and its listed figure is a bold number in its note",
    listedNumbers(cutHeader) === JSON.stringify([["2"]]),
    listedNumbers(cutHeader),
  );
  check(
    "and names them for a screen reader",
    cutHeader?.getAttribute("aria-label") === "15 lines added, 3 deleted; 2 listed",
    cutHeader?.getAttribute("aria-label") ?? "",
  );
  const cutPlain = new FakeElement("div");
  mountDiffView(new FakeElement("div"), cutShort, undefined, {
    summaryHost: cutPlain,
    summaryTotals: whole,
  });
  check(
    "a list cut short says them without the shared tree too",
    !cutPlain.reads().includes("files changed") &&
      cutPlain.reads().includes("+15") &&
      cutPlain.reads().includes("(2 listed)"),
    cutPlain.reads(),
  );
  check(
    "and its listed figure is a bold number in its note there too",
    listedNumbers(cutPlain) === JSON.stringify([["2"]]),
    listedNumbers(cutPlain),
  );
  const wholePlace = new FakeElement("div");
  mountDiffView(new FakeElement("div"), twoFiles, undefined, {
    changedFiles: sharedTree,
    summaryHost: wholePlace,
    summaryTotals: whole,
  });
  check(
    "a whole list says its own totals",
    wholePlace.reads().includes("2 M") && !wholePlace.reads().includes("listed"),
    wholePlace.reads(),
  );
  await diffSummaryChecks(mountDiffView, twoFiles);
  await repeatedPathChecks(mountDiffView, twoFiles);
  await windowedSummaryChecks(repoRoot);
  await headLinkChecks(mountDiffView, byName);
  // A host that cuts the header's breakdown short, as a pull request's header does to keep
  // its one line, gives the header its whole words as a tooltip while it is cut, and none
  // while it is whole (A7 of review A on #470). It runs after the checks of a tree that did
  // not load, since a hover loads the tree's module.
  const tipSlot = new FakeElement("div");
  const tipped = mountDiffSummary(tipSlot, twoFiles, painters, {
    changedFiles: sharedTree,
    openFile() {},
  });
  const tipHeader = tipSlot.children[0];
  const tipBreakdown = tipHeader.find("change-line-statuses")[0];
  tipHeader.dispatch("pointerenter");
  check("a whole breakdown has no tooltip", tipHeader.dataset.tipText === undefined);
  tipBreakdown.scrollWidth = 180;
  tipBreakdown.clientWidth = 60;
  tipHeader.dispatch("pointerenter");
  check(
    "a breakdown cut short gives its header's whole words",
    tipHeader.dataset.tipText === "2 M \u00b7 +1 \u22121",
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

  // Unfolded, as a pull request's Docs tab draws, a long run is drawn open; one the reader
  // closes stays closed when a layout change draws the file again.
  const unfolded = new FakeElement("div");
  mountDiffView(unfolded, longDoc, layoutApi, { unfold: true });
  await nextTask();
  check(
    "an unfolded diff draws its long run open",
    unfolded.find("diff-fold-control")[0].getAttribute("aria-expanded") === "true",
  );
  unfolded.find("diff-fold-control")[0].click();
  await nextTask();
  layoutChange("diff-layout", "unified", "one");
  layoutChange("diff-layout", "split", "one");
  await nextTask();
  check(
    "a fold the reader closed stays closed when the file is drawn again",
    unfolded.find("diff-fold-control")[0].getAttribute("aria-expanded") === "false",
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

  // mountFilePatch, the export Guided Review draws a step's files with, is Changes' body of
  // one file: its rows and fold bars at once, changed-run pairs and syntax after first
  // paint, and a disposal that stops what is still to come (B6 of review B on #677).
  const filePatch = (() => {
    const lines = [
      { op: "context", text: "keep" },
      { op: "del", text: "value = 1" },
      { op: "add", text: "value = 2" },
      { op: "context", text: "sep" },
      ...Array.from({ length: 60 }, (_, index) => ({ op: "add", text: `line ${index}` })),
    ];
    const hunk = { old_start: 1, old_count: 3, new_start: 1, new_count: 63, heading: null, lines };
    return { file_id: "f1", hunks: [hunk], truncated: false };
  })();
  const fileChange = byName.get("modified-with-heading").manifest.files[0];
  let patchLexes = 0;
  const patchApi = {
    ...defaultTestApi,
    highlightSyntax: async (source) => {
      patchLexes += 1;
      return source.split("\n").map((line) => [{ classes: ["hljs-string"], text: line }]);
    },
    isLargeTextPreview: () => false,
    langForPath: () => "python",
  };
  const intraline = (body) => body.find("diff-intraline-change").length;
  const tokens = (body) => body.find("hljs-string").length;
  const patchBody = new FakeElement("div");
  const patchHandle = mountFilePatch(patchBody, fileChange, filePatch, patchApi);
  check(
    "a file patch draws its rows at once, its long run behind a fold bar",
    patchBody.find("diff-line").length === 24 &&
      patchBody.find("diff-fold-control").length === 1 &&
      patchBody.find("diff-fold-control")[0].text().includes("40 more changed lines"),
    `${patchBody.find("diff-line").length} rows`,
  );
  check(
    "a file patch's first paint is plain text",
    intraline(patchBody) === 0 && tokens(patchBody) === 0 && patchLexes === 0,
  );
  const patchFold = patchBody.find("diff-fold-control")[0];
  const patchGroup = patchBody.find("diff-fold-group")[0];
  patchFold.click();
  await nextTask();
  check(
    "a file patch's fold bar expands its run",
    !patchGroup.classList.contains("diff-fold-collapsed") &&
      patchGroup.find("diff-line").length === 40,
  );
  for (let turn = 0; turn < 4; turn += 1) {
    await nextSyntaxUnit();
  }
  check(
    "a file patch pairs its changed run and highlights its rows after first paint",
    intraline(patchBody) > 0 && tokens(patchBody) > 0 && patchLexes > 0,
    `${intraline(patchBody)} intraline, ${tokens(patchBody)} tokens, ${patchLexes} lexes`,
  );
  // A page that draws its own card for a file, as Guided Review does, takes the card's bar
  // from the diff view's builder (`fileDisclosure`, which `guidePatchDrawer` hands over), and
  // it is Changes' own: the same bar, trigger, and chevron, which fold whatever the page
  // hands them, here a box holding a note and the patch.
  {
    const card = new FakeElement("section");
    const folded = new FakeElement("div");
    folded.append(new FakeElement("p"), patchBody);
    const disclosure = fileDisclosure(card, folded);
    const viewLink = new FakeElement("a");
    viewLink.className = "diff-file-view";
    disclosure.bar.append(disclosure.toggle, viewLink);
    card.append(disclosure.bar, folded);
    check(
      "a page's own card takes the bar, trigger, and chevron Changes draws",
      JSON.stringify({
        bar: classesOf(disclosure.bar),
        toggle: classesOf(disclosure.toggle),
        chevron: classesOf(disclosure.toggle.children[0]),
        type: disclosure.toggle.getAttribute("type"),
        tag: disclosure.toggle.tagName,
      }) === JSON.stringify(changesDisclosure),
    );
    const cardFolds = () => ({
      said: disclosure.toggle.getAttribute("aria-expanded"),
      body: folded.classList.contains("diff-file-body-collapsed"),
      card: card.classList.contains("diff-file-collapsed"),
      turned: disclosure.toggle.classList.contains("collapsed"),
      open: disclosure.toggle.classList.contains("expanded"),
    });
    const shut = { said: "false", body: true, card: true, turned: true, open: false };
    const opened = { said: "true", body: false, card: false, turned: false, open: true };
    check(
      "a page's own card starts open, its trigger naming what it folds",
      JSON.stringify(cardFolds()) === JSON.stringify(opened) &&
        disclosure.toggle.getAttribute("aria-controls") === folded.getAttribute("id") &&
        card.getAttribute("aria-labelledby") === disclosure.toggle.getAttribute("id"),
    );
    const patchRows = patchBody.find("diff-line").length;
    disclosure.bar.click();
    check(
      "a press on the card's bar folds it, and keeps what the patch drew",
      JSON.stringify(cardFolds()) === JSON.stringify(shut) &&
        patchBody.find("diff-line").length === patchRows &&
        !patchBody.classList.contains("diff-file-body-collapsed"),
      JSON.stringify(cardFolds()),
    );
    viewLink.click();
    check(
      "a press on the card's link to the file is the link's, not the bar's",
      JSON.stringify(cardFolds()) === JSON.stringify(shut),
    );
    disclosure.toggle.click();
    check(
      "the trigger, which a key presses, opens it again",
      JSON.stringify(cardFolds()) === JSON.stringify(opened),
    );
    const otherCard = fileDisclosure(new FakeElement("section"), new FakeElement("div"));
    check(
      "each card's ids are its own",
      otherCard.toggle.getAttribute("id") !== disclosure.toggle.getAttribute("id") &&
        otherCard.toggle.getAttribute("aria-controls") !== folded.getAttribute("id"),
    );
  }
  patchHandle.dispose();
  // Disposed before its enhancement runs, a file patch stays as first painted, and a fold
  // still materializing stops.
  const lexedBefore = patchLexes;
  const earlyBody = new FakeElement("div");
  const earlyHandle = mountFilePatch(earlyBody, fileChange, filePatch, patchApi);
  const earlyGroup = earlyBody.find("diff-fold-group")[0];
  earlyBody.find("diff-fold-control")[0].click();
  earlyHandle.dispose();
  for (let turn = 0; turn < 4; turn += 1) {
    await nextSyntaxUnit();
  }
  check(
    "a file patch disposed before its enhancement writes nothing later",
    intraline(earlyBody) === 0 &&
      tokens(earlyBody) === 0 &&
      patchLexes === lexedBefore &&
      earlyGroup.find("diff-line").length === 0,
    `${intraline(earlyBody)} intraline, ${tokens(earlyBody)} tokens, ${earlyGroup.find("diff-line").length} folded rows`,
  );

  // Disposed while its syntax is on its way, a file patch keeps the rows it has.
  const heldLexes = [];
  const heldApi = {
    ...patchApi,
    highlightSyntax: (source) =>
      new Promise((resolve) => {
        heldLexes.push(() =>
          resolve(source.split("\n").map((line) => [{ classes: ["hljs-string"], text: line }])),
        );
      }),
  };
  const lateBody = new FakeElement("div");
  const lateHandle = mountFilePatch(lateBody, fileChange, filePatch, heldApi);
  for (let turn = 0; turn < 4; turn += 1) {
    await nextSyntaxUnit();
  }
  const pairedBefore = intraline(lateBody);
  const heldAtDisposal = heldLexes.length;
  lateHandle.dispose();
  // Each side's lexer call follows the one before it, so each is answered as it comes.
  for (let turn = 0; turn < 4; turn += 1) {
    for (const release of heldLexes.splice(0)) {
      release();
    }
    await nextSyntaxUnit();
  }
  check(
    "a file patch disposed while its syntax is on its way paints none of it",
    pairedBefore > 0 && heldAtDisposal > 0 && tokens(lateBody) === 0,
    `${pairedBefore} intraline, ${heldAtDisposal} lexes held, ${tokens(lateBody)} tokens`,
  );

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
