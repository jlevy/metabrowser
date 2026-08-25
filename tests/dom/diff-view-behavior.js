// Render checks for the diff view, deliberately lighter than the model
// tests: the data plane is pinned by the corpus and the CLI goldens, so
// this only asserts the projection — line rows, numbering, availability
// states, metadata-only changes, the per-file disclosure bar, and
// disposal.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

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

  append(...nodes) {
    for (const node of nodes) {
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

async function main() {
  const documentListeners = new Map();
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
  const { composeTextRuns, mountDiffView, setChangeLoader } = await import(
    pathToFileURL(viewPath).href
  );
  const corpus = JSON.parse(
    fs.readFileSync(
      path.join(repoRoot, "src/metabrowser/data/file-diff-format/file-diff-conformance.json"),
      "utf-8",
    ),
  );
  const byName = new Map(corpus.cases.map((entry) => [entry.name, entry.document]));
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
    "invalid layout preference falls back to unified",
    invalidPreference.find("diff-root")[0].dataset.layout === "unified",
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
  check("change sets keep the summary", many.find("diff-summary").length === 1);
  const hosted = new FakeElement("div");
  mountDiffView(hosted, twoFiles, undefined, { showSummary: false });
  check(
    "revision-hosted change sets leave the aggregate summary to their commit header",
    hosted.find("diff-summary").length === 0,
  );
  check("revision-hosted change sets keep their toolbar", hosted.find("diff-toolbar").length === 1);

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
  check("the visible head stays outside the group", folded.find("diff-line").length === 61);
  check("the group holds exactly the surplus", group.find("diff-line").length === 40);
  const sectionBody = folded.find("diff-file-body")[0];
  control.click();
  check("expanding reveals the group", !group.classList.contains("diff-fold-collapsed"));
  check(
    "expanding does not also collapse the file",
    !sectionBody.classList.contains("diff-file-body-collapsed"),
  );
  control.click();
  check("collapsing hides it again", group.classList.contains("diff-fold-collapsed"));
  check("short runs do not fold", container.find("diff-fold-control").length === 0);

  const switchingFold = new FakeElement("div");
  mountDiffView(switchingFold, longDoc, layoutApi);
  const switchingControl = switchingFold.find("diff-fold-control")[0];
  const splitFoldGroup = switchingFold.find("diff-fold-group")[0];
  check(
    "split fold hides one paired interval across unequal sides",
    splitFoldGroup.find("diff-split-row").length === 40 &&
      splitFoldGroup.find("diff-split-empty").length === 40,
  );
  switchingControl.click();
  layoutChange("diff-layout", "unified", "one");
  layoutChange("diff-layout", "split", "one");
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
  const deferredLayoutChange = layoutChange;
  check("deferred loader receives the mount signal", deferredSignal instanceof AbortSignal);
  deferredLayoutChange("diff-layout", "unified", "one");
  deferredResolve(JSON.parse(JSON.stringify(byName.get("modified-with-heading"))));
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
  disposedFetchHandle.dispose();
  check("dispose aborts deferred fetches", disposedFetchSignal?.aborted === true);
  disposedFetchResolve(JSON.parse(JSON.stringify(byName.get("modified-with-heading"))));
  await nextTask();
  check(
    "late fetch completion cannot mutate detached DOM",
    detachedBody.find("diff-progress").length === 1 && detachedBody.find("diff-line").length === 0,
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
