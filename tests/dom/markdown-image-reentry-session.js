// Which of a Markdown document's images load eagerly when its file is entered again
// (docs/design-system.md, "A Repaint Keeps Its Images").
//
// The production pieces run together, as the page runs them:
// - the shell's inventory stream handlers and its file store, extracted from app.js
//   verbatim, which turn each `fs.snapshot` and `fs.change` frame into the
//   `metabrowser:inventory-change` event;
// - the plugin SDK, whose `onInventoryChange` hears that event;
// - the Markdown plugin's index.js, which subscribes `forgetHeldImages` to it; and
// - the link enhancer, imported from its file, which resolves each image's address on
//   images that arrive as KPress writes them: lazy, with the address the author wrote.
// Only the browser is a double: the event stream, the DOM, and the engine's loads, which
// are events this session fires, so it decides which images the page holds. The frames
// are shaped as the server sends them on the shell's `root-depth-2` stream.
//
// An image whose served address has loaded in this page since the last filesystem
// change is made eager before that address is set, its authored address removed first;
// any other stays lazy. Any change, a reconnect even with the same snapshot, forgets
// every held image, and a load assigned before a change is not remembered after it. An
// image under a hidden name is never held: the watcher reports no change there. The
// record keeps `MAX_HELD_IMAGES` images and forgets the least recently loaded past that.
//
// This checks attributes, their order, listeners, and the record, not loading or paint,
// which are the engine's; the design-system section has the WebKit and Chrome
// measurements.
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const vm = require("node:vm");
const { createSdkSandbox } = require("./sdk-sandbox.js");

const repoRoot = path.resolve(__dirname, "../..");
const markdownDir = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");
const moduleUrl = (name) => pathToFileURL(path.join(markdownDir, name)).href;
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf8");

/** One app.js declaration, bounded by its closing line at column zero. */
function appDeclaration(pattern, label) {
  const match = appSource.match(pattern);
  if (!match) {
    throw new Error(`app.js ${label} is not extractable`);
  }
  return match[0];
}

const SHELL_VARIABLES = [
  "fileStore",
  "fileStoreSubscribers",
  "inventoryEventSource",
  "lastInventorySnapshot",
  "catalogFeedCanStart",
];
const SHELL_FUNCTIONS = [
  "_createInventoryEventSource",
  "fileStoreApplySnapshot",
  "fileStoreApplySnapshotInner",
  "fileStoreApplyChange",
  "fileStoreApplyChangeInner",
  "notifyFileStoreSubscribers",
  "announceUnchangedSnapshot",
];
const shellSource = [
  appDeclaration(/^const activeFiles = new Map\(\);[^\n]*$/m, "active files"),
  appDeclaration(/^const fileCache = new Map\(\);$/m, "file cache"),
  ...SHELL_VARIABLES.map((name) =>
    appDeclaration(new RegExp(`^var ${name} = [^\\n]*;`, "m"), `variable ${name}`),
  ),
  ...SHELL_FUNCTIONS.map((name) =>
    appDeclaration(
      new RegExp(`^function ${name}\\([^)]*\\) \\{[\\s\\S]*?^\\}`, "m"),
      `function ${name}`,
    ),
  ),
].join("\n\n");

// The shell services a frame is handed to besides the file store; none of them decides
// whether a consumer hears the change.
const COLLABORATORS = `
var _perf = { measure: (_label, fn) => fn() };
var pageConnections = { suspended: () => false, defer() {} };
var quickFileCatalogFeed = null;
var knownFileCatalog = null;
var filterState = null;
var inventoryChangeHighlightingActive = false;
var recentEverLoaded = false;
var currentRecentWindow = null;
var recentContinuity = { dirtyActiveRequest() {} };
var fileNeedsRevalidate = new Set();
var subtreeCache = new Map();
var subtreeRequests = new Map();
var recentFilterRefetch = { pending: () => false };
var treeFilterModel = { observeRecentSentinel() {} };
function filterHasConstraints() { return false; }
function recentRepairDescriptor() { return null; }
function filesPanelUsesRecentSource() { return false; }
function recentViewOwnsCurrentCursor() { return false; }
function _scheduleRecentRecompute() {}
function _scheduleInventoryReconnect() {}
function retryFailedExpandedSubtrees() {}
function invalidateSubtreeCaches() {}
function invalidateFilePreviews() {}
function applyCellPatch() {}
function _mirrorActiveFromFsEntry() {}
function _removeDeferredTreePageEntries() {}
function _removeRenderedRows() {}
function _removeRenderedRowsImmediately() {}
function loadTree() {}
`;

/** The shell with its stream, the SDK, and the Markdown plugin, in one page. */
async function createPage() {
  const events = new EventTarget();
  const streams = [];
  class SessionEventSource {
    constructor(url) {
      this.url = String(url);
      this.handlers = new Map();
      streams.push(this);
    }
    addEventListener(type, handler) {
      this.handlers.set(type, handler);
    }
    close() {}
  }
  const sandbox = createSdkSandbox({
    CustomEvent,
    EventSource: SessionEventSource,
    JSON,
    addEventListener: events.addEventListener.bind(events),
    dispatchEvent: events.dispatchEvent.bind(events),
    removeEventListener: events.removeEventListener.bind(events),
  });
  vm.runInContext(COLLABORATORS, sandbox, { filename: "markdown-image-collaborators.js" });
  vm.runInContext(shellSource, sandbox, { filename: "app-inventory-stream.js" });
  vm.runInContext("_createInventoryEventSource()", sandbox);
  // The plugin's own index.js subscribes the enhancer's record to the SDK.
  globalThis.window = { metabrowser: sandbox.metabrowser };
  await import(moduleUrl("index.js"));
  const stream = streams.at(-1);
  return {
    /** The server sends *type* with *data* on the shell's stream. */
    sends(type, data) {
      stream.handlers.get(type)({ data: JSON.stringify(data) });
    },
  };
}

class ElementShim {}
global.Element = ElementShim;

class FakeElement extends ElementShim {
  constructor(tagName, attributes = {}) {
    super();
    this.tagName = tagName.toUpperCase();
    this.parentElement = null;
    this.attributes = new Map(Object.entries(attributes));
    /** Attribute changes after the element was parsed, in order. */
    this.changes = [];
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  removeAttribute(name) {
    this.changes.push(`remove ${name}`);
    this.attributes.delete(name);
  }

  setAttribute(name, value) {
    this.changes.push(`${name}=${value}`);
    this.attributes.set(name, value);
  }
}

/** A rendered document's root: its parsed elements, and the listeners put on it. */
class FakeContainer extends FakeElement {
  constructor(elements) {
    super("div");
    this.elements = elements;
    this.listeners = new Map();
    for (const element of elements) {
      element.parentElement = this;
    }
  }

  addEventListener(name, listener, capture = false) {
    this.listeners.set(name, { listener, capture: capture === true });
  }

  removeEventListener(name, listener, capture = false) {
    const entry = this.listeners.get(name);
    if (entry?.listener === listener && entry.capture === (capture === true)) {
      this.listeners.delete(name);
    }
  }

  querySelector() {
    return null;
  }

  querySelectorAll(selector) {
    if (
      selector ===
      "a[href],img[src],audio[src],video[src],source[src],object[data],[data-mb-wiki-target]"
    ) {
      return this.elements.filter((element) => element.hasAttribute("src"));
    }
    return [];
  }

  /** The engine finished loading *image*: its load reaches the root in the capture phase. */
  load(image) {
    const entry = this.listeners.get("load");
    if (entry?.capture) {
      entry.listener({ target: image, type: "load" });
    }
  }
}

/** An image as KPress writes it. */
function image(src) {
  return new FakeElement("img", { loading: "lazy", src });
}

/** An inventory entry as the stream sends it. */
function entry(entryPath, type) {
  return { path: entryPath, type, size: 460, mtime_ns: 1_790_000_000_000_000_000 };
}

// The shell's `root-depth-2` snapshot: the root, `docs`, and what is directly in it.
const SNAPSHOT = {
  scope: "root-depth-2",
  complete: true,
  entries: [
    entry("", "dir"),
    entry("docs", "dir"),
    entry("docs/readme.md", "file"),
    entry("docs/images", "dir"),
  ],
};
// Editing docs/readme.md: the file, and each ancestor whose totals it moved.
const MARKDOWN_EDITED = {
  ops: [
    { op: "upsert", entry: entry("docs/readme.md", "file") },
    { op: "upsert", entry: entry("docs", "dir") },
    { op: "upsert", entry: entry("", "dir") },
  ],
};
// Replacing docs/images/shown.png, deeper than the stream watches: its deepest watched
// ancestor, and theirs.
const IMAGE_REPLACED = {
  ops: [
    { op: "upsert", entry: entry("docs/images", "dir") },
    { op: "upsert", entry: entry("docs", "dir") },
    { op: "upsert", entry: entry("", "dir") },
  ],
};

async function run() {
  const page = await createPage();
  const { enhanceRenderedLinks, MAX_HELD_IMAGES } = await import(moduleUrl("link-enhancer.js"));
  let current = { path: "docs/readme.md" };
  const mb = {
    decorateExternalLink() {},
    navigation: {
      current: () => current,
      href: (target) => `/view/${target.path}`,
      open: async () => {},
    },
  };
  const eventTarget = { addEventListener() {}, removeEventListener() {} };
  const options = { cancel: () => {}, eventTarget, schedule: () => 0 };

  /** Enter `docs/readme.md` with images parsed from *sources*, as a mount does. */
  function enter(sources) {
    current = { path: "docs/readme.md" };
    const images = sources.map(image);
    const container = new FakeContainer(images);
    const handle = enhanceRenderedLinks(container, "docs/readme.md", mb, options);
    return { container, handle, images };
  }

  /** Each image's loading, address, and the changes the enhancer made to it. */
  const facts = (images) =>
    images.map((element) => ({
      loading: element.getAttribute("loading"),
      src: element.getAttribute("src"),
      changes: element.changes,
    }));

  /** Enter a document showing *sources* and report each one's loading; load nothing. */
  function observe(sources) {
    const entered = enter(sources);
    entered.handle.dispose();
    return Object.fromEntries(
      sources.map((source, index) => [source, entered.images[index].getAttribute("loading")]),
    );
  }

  /** Enter a document showing *sources*, and the engine loads each, in order. */
  function loadAll(sources) {
    const entered = enter(sources);
    for (const element of entered.images) {
      entered.container.load(element);
    }
    entered.handle.dispose();
  }

  const README = ["images/shown.png", "images/far.png", "https://example.com/remote.png"];
  const SHOWN = ["images/shown.png"];
  const steps = [];

  page.sends("fs.snapshot", SNAPSHOT);

  // First entry: the page holds nothing, so every image is lazy.
  const first = enter(README);
  steps.push({
    step: "first entry",
    listens: { load: first.container.listeners.get("load")?.capture ? "capture" : null },
    images: facts(first.images),
  });
  // The reader sees the first image and the remote one; the far one never loads.
  first.container.load(first.images[0]);
  first.container.load(first.images[2]);
  first.handle.dispose();
  steps.push({ step: "left", listening: [...first.container.listeners.keys()] });

  // Entering again builds the document again.
  const second = enter(README);
  steps.push({ step: "entered again", images: facts(second.images) });
  second.handle.dispose();

  /** What *action* does to the held shown image: its loading before and after. */
  function across(step, action) {
    const before = observe(SHOWN)[SHOWN[0]];
    action();
    steps.push({ step, before, after: observe(SHOWN)[SHOWN[0]] });
  }

  // The stream reconnects and sends the same snapshot: deep files may still have changed.
  across("a reconnect sends the same snapshot", () => page.sends("fs.snapshot", SNAPSHOT));
  loadAll(SHOWN);
  across("the Markdown changes", () => page.sends("fs.change", MARKDOWN_EDITED));
  loadAll(SHOWN);
  across("an image under docs/images is replaced", () => page.sends("fs.change", IMAGE_REPLACED));

  // A load in flight across a change may carry the bytes from before it.
  across("a load assigned before a change finishes after it", () => {
    const inFlight = enter(SHOWN);
    page.sends("fs.change", IMAGE_REPLACED);
    inFlight.container.load(inFlight.images[0]);
    inFlight.handle.dispose();
  });
  across("a load assigned after the change", () => loadAll(SHOWN));

  // The watcher reports nothing under a hidden name, so nothing would forget it.
  const HIDDEN = [".assets/logo.png", "images/.cache/thumb.png"];
  loadAll(HIDDEN);
  steps.push({ step: "images under hidden names load", loading: observe(HIDDEN) });

  // The record fills to its bound, least recently loaded first.
  page.sends("fs.change", MARKDOWN_EDITED);
  const gallery = Array.from({ length: MAX_HELD_IMAGES }, (_, index) => `gallery/${index}.png`);
  loadAll(gallery);
  steps.push({
    step: `${MAX_HELD_IMAGES} images loaded: the bound`,
    loading: observe([gallery[0], gallery.at(-1)]),
  });
  loadAll(["extra/0.png"]);
  steps.push({
    step: "one more loads: the least recently loaded is forgotten",
    loading: observe([gallery[0], gallery[1], "extra/0.png"]),
  });
  // Loading an older image again makes it the most recently loaded.
  loadAll([gallery[1]]);
  loadAll(["extra/1.png"]);
  steps.push({
    step: "gallery/1.png loads again, then one more loads",
    loading: observe([gallery[1], gallery[2], gallery[3], "extra/1.png"]),
  });

  return { bound: MAX_HELD_IMAGES, steps };
}

run().then(
  (result) => {
    console.log(JSON.stringify(result, null, 2));
  },
  (error) => {
    console.error(error);
    process.exit(1);
  },
);
