// Which of a Markdown document's images load eagerly when its file is entered again
// (docs/design-system.md, "A Repaint Keeps Its Images").
//
// The production placement (place-rendered.js) and link enhancer (link-enhancer.js) run
// together, as a mount runs them, on renders shaped as the server sends them: HTML whose
// images KPress wrote lazy at the address the author wrote, and `raw_versions`, the
// version of each served file the document embeds. Only the browser is a double: the DOM,
// a template that parses the render's images, and the engine's loads, which are events
// this session fires, so it decides which images the page holds.
//
// The page holds a loaded image only at an address that names its bytes: a served file's
// address with the version the render gave it, any served address on a pinned revision,
// and an address on another origin. A held served image is made eager before its address
// is set, its authored address removed first; a held outside image is made eager in the
// template, before the page adopts it; a scheme-relative address is outside when its host
// is another. A replaced file has a new version, so its address is new and it loads
// lazily there; an unversioned served address, and an absolute or scheme-relative one on
// the page's own origin, are never held. The record keeps `MAX_HELD_IMAGES` images
// and forgets the least recently loaded past that.
//
// This checks attributes, their order, listeners, and the record, not loading or paint,
// which are the engine's; the design-system section has the WebKit and Chrome
// measurements.
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const markdownDir = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");
const moduleUrl = (name) => pathToFileURL(path.join(markdownDir, name)).href;

// The page's origin: an image addressed there is the page's own, not outside it.
const ORIGIN = "http://127.0.0.1:8000";
globalThis.location = { href: `${ORIGIN}/view/docs/readme.md`, origin: ORIGIN };

class ElementShim {}
global.Element = ElementShim;

class FakeElement extends ElementShim {
  constructor(tagName, attributes = {}) {
    super();
    this.tagName = tagName.toUpperCase();
    this.parentElement = null;
    this.attributes = new Map(Object.entries(attributes));
    /** Attribute changes after the element was parsed, and its placement, in order. */
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

const RESOURCE_SELECTOR =
  "a[href],img[src],audio[src],video[src],source[src],object[data],[data-mb-wiki-target]";

/** Parsed elements, queried as a template's content or a placed root is. */
class FakeParent extends FakeElement {
  constructor(tagName) {
    super(tagName);
    this.elements = [];
  }

  querySelector() {
    return null;
  }

  querySelectorAll(selector) {
    if (selector === RESOURCE_SELECTOR || selector === "img[src]") {
      return this.elements.filter((element) => element.hasAttribute("src"));
    }
    return [];
  }
}

/** A template: its HTML is parsed into images that load nothing until placed. */
class FakeTemplate extends FakeParent {
  constructor() {
    super("template");
    this.content = new FakeParent("#document-fragment");
  }

  set innerHTML(html) {
    this.content.elements = [...html.matchAll(/<img loading="lazy" src="([^"]*)">/g)].map(
      (match) => new FakeElement("img", { loading: "lazy", src: match[1] }),
    );
  }
}

/** A rendered document's root: what was placed in it, and the listeners put on it. */
class FakeContainer extends FakeParent {
  constructor() {
    super("div");
    this.listeners = new Map();
    this.ownerDocument = { createElement: () => new FakeTemplate() };
  }

  replaceChildren(fragment) {
    this.elements = fragment.elements;
    fragment.elements = [];
    for (const element of this.elements) {
      element.parentElement = this;
      element.changes.push("placed");
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

  /** The engine finished loading *image*: its load reaches the root in the capture phase. */
  load(image) {
    const entry = this.listeners.get("load");
    if (entry?.capture) {
      entry.listener({ target: image, type: "load" });
    }
  }
}

/** A render as the server sends it: each image as KPress writes it, and the versions. */
function render(sources, versions = {}) {
  return {
    html: sources.map((source) => `<img loading="lazy" src="${source}">`).join("\n"),
    raw_versions: versions,
  };
}

async function run() {
  const { placeRendered, MAX_HELD_IMAGES } = await import(moduleUrl("place-rendered.js"));
  const { enhanceRenderedLinks } = await import(moduleUrl("link-enhancer.js"));
  let sourceKind = "filesystem";
  const mb = {
    decorateExternalLink() {},
    navigation: {
      current: () => ({ path: "docs/readme.md" }),
      href: (target) => `/view/${target.path}`,
      open: async () => {},
    },
    sourceKind: () => sourceKind,
  };
  const eventTarget = { addEventListener() {}, removeEventListener() {} };
  const options = { cancel: () => {}, eventTarget, schedule: () => 0 };

  /** Enter `docs/readme.md`, rendered with *sources* and *versions*, as a mount does. */
  async function enter(sources, versions = {}) {
    const container = new FakeContainer();
    const rendered = render(sources, versions);
    const { enhanced: handle } = await placeRendered(container, rendered, mb, (root) =>
      enhanceRenderedLinks(root, "docs/readme.md", mb, {
        ...options,
        rawVersions: rendered.raw_versions,
      }),
    );
    return { container, handle, images: container.elements };
  }

  /** Each image's loading, address, and the changes made to it, placement included. */
  const facts = (images) =>
    images.map((element) => ({
      loading: element.getAttribute("loading"),
      src: element.getAttribute("src"),
      changes: element.changes,
    }));

  /** Enter a document showing *sources* and report each one's loading; load nothing. */
  async function observe(sources, versions = {}) {
    const entered = await enter(sources, versions);
    entered.handle.dispose();
    return Object.fromEntries(
      sources.map((source, index) => [source, entered.images[index].getAttribute("loading")]),
    );
  }

  /** Enter a document showing *sources*, and the engine loads each, in order. */
  async function loadAll(sources, versions = {}) {
    const entered = await enter(sources, versions);
    for (const element of entered.images) {
      entered.container.load(element);
    }
    entered.handle.dispose();
  }

  /** Each source under docs/, at version *version*. */
  const versioned = (sources, version) =>
    Object.fromEntries(sources.map((source) => [`docs/${source}`, version]));

  const SHOWN = "images/shown.png";
  const FAR = "images/far.png";
  const UNVERSIONED = "images/past-the-bound.png";
  const REMOTE = "https://example.com/remote.png";
  // Scheme-relative: another host's, and the page's own.
  const SCHEMELESS = "//cdn.example.com/badge.svg";
  const OWN_SCHEMELESS = "//127.0.0.1:8000/own.png";
  const README = [SHOWN, FAR, UNVERSIONED, REMOTE, SCHEMELESS, OWN_SCHEMELESS];
  // The render versions each served file it embeds, up to its bound.
  const VERSIONS = versioned([SHOWN, FAR], "a1b2c3d4e5f60718");
  const steps = [];

  // First entry: the page holds nothing, so every image is lazy.
  const first = await enter(README, VERSIONS);
  steps.push({
    step: "first entry",
    listens: { load: first.container.listeners.get("load")?.capture ? "capture" : null },
    images: facts(first.images),
  });
  // The reader sees all but the far image, which never loads.
  for (const index of [0, 2, 3, 4, 5]) {
    first.container.load(first.images[index]);
  }
  first.handle.dispose();
  steps.push({ step: "left", listening: [...first.container.listeners.keys()] });

  // Entering again builds the document again.
  const second = await enter(README, VERSIONS);
  steps.push({ step: "entered again", images: facts(second.images) });
  second.handle.dispose();

  // The image is replaced: the next render gives it a new version, so a new address.
  const REPLACED = versioned([SHOWN], "0f1e2d3c4b5a6978");
  const replaced = await enter([SHOWN], REPLACED);
  steps.push({ step: "the image is replaced", images: facts(replaced.images) });
  replaced.container.load(replaced.images[0]);
  replaced.handle.dispose();
  steps.push({
    step: "its new address loaded, then entered again",
    loading: await observe([SHOWN], REPLACED),
  });

  // An absolute address on the page's own origin is the page's, and may change.
  const OWN = `${ORIGIN}/raw?path=docs%2Fimages%2Fshown.png`;
  await loadAll([OWN]);
  steps.push({
    step: "an absolute address on the page's origin loads",
    loading: await observe([OWN]),
  });

  // On a pinned revision a served file never changes at its address.
  sourceKind = "git_revision";
  const PINNED = ["images/pinned.png"];
  await loadAll(PINNED);
  steps.push({ step: "a pinned revision's image loads", loading: await observe(PINNED) });
  sourceKind = "filesystem";

  // The record fills to its bound, least recently loaded first.
  const gallery = Array.from({ length: MAX_HELD_IMAGES }, (_, index) => `gallery/${index}.png`);
  const galleryVersions = versioned([...gallery, "extra/0.png", "extra/1.png"], "1111222233334444");
  await loadAll(gallery, galleryVersions);
  steps.push({
    step: `${MAX_HELD_IMAGES} images loaded: the bound`,
    loading: await observe([gallery[0], gallery.at(-1)], galleryVersions),
  });
  await loadAll(["extra/0.png"], galleryVersions);
  steps.push({
    step: "one more loads: the least recently loaded is forgotten",
    loading: await observe([gallery[0], gallery[1], "extra/0.png"], galleryVersions),
  });
  // Loading an older image again makes it the most recently loaded.
  await loadAll([gallery[1]], galleryVersions);
  await loadAll(["extra/1.png"], galleryVersions);
  steps.push({
    step: "gallery/1.png loads again, then one more loads",
    loading: await observe([gallery[1], gallery[2], gallery[3], "extra/1.png"], galleryVersions),
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
