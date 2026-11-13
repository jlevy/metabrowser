// Which of a Markdown document's images load eagerly when its file is entered again
// (docs/design-system.md, "A Repaint Keeps Its Images").
//
// The production link enhancer, imported from its file with every module it imports,
// resolves each image's address, as every mount of the rendered view has it do, on images
// that arrive as KPress writes them: lazy, with the address the author wrote. The engine's
// loads are events this session fires, so it decides which images the page holds, and
// filesystem changes are calls to `forgetChangedImages`, as the plugin's
// `onInventoryChange` subscription makes them.
//
// An image whose served address has loaded in this page is made eager before that address
// is set, its authored address removed first; any other stays lazy. The record keeps
// `MAX_HELD_IMAGES` images and forgets the least recently loaded past that. A change
// forgets the held images at or beneath its deepest reported paths, and a reconnect
// forgets them all.
//
// This checks attributes, their order, listeners, and the record, not loading or paint,
// which are the engine's; the design-system section has the WebKit and Chrome
// measurements.
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const enhancerUrl = pathToFileURL(
  path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/link-enhancer.js"),
).href;

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

async function run() {
  const { enhanceRenderedLinks, forgetChangedImages, MAX_HELD_IMAGES } = await import(enhancerUrl);
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
  function enter(sources, documentPath = "docs/readme.md") {
    current = { path: documentPath };
    const images = sources.map(image);
    const container = new FakeContainer(images);
    const handle = enhanceRenderedLinks(container, documentPath, mb, options);
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
  const steps = [];

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

  // A reconnect forgets every image; then the record fills to its bound, least recently
  // loaded first.
  forgetChangedImages(null);
  steps.push({ step: "after a reconnect", loading: observe(["images/shown.png"]) });
  const gallery = Array.from({ length: MAX_HELD_IMAGES }, (_, index) => `gallery/${index}.png`);
  loadAll(gallery);
  const last = gallery.at(-1);
  steps.push({
    step: `${MAX_HELD_IMAGES} images loaded: the bound`,
    loading: observe([gallery[0], last]),
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

  // Filesystem changes, as the shell reports them: each changed entry with its ancestors.
  forgetChangedImages(null);
  const HELD = ["images/shown.png", "images/far.png", "deep/x/y/pic.png", "deep/z.png"];
  loadAll(HELD);
  forgetChangedImages(["docs/readme.md", "docs", ""]);
  steps.push({ step: "the Markdown changes", loading: observe(HELD) });
  forgetChangedImages(["docs/images/shown.png", "docs/images", "docs", ""]);
  steps.push({ step: "images/shown.png is replaced", loading: observe(HELD) });
  // Too deep for the shell to watch: reported by its deepest watched ancestor.
  forgetChangedImages(["docs/deep/x", "docs/deep", "docs", ""]);
  steps.push({ step: "a change somewhere under deep/x", loading: observe(HELD) });
  forgetChangedImages(null);
  steps.push({ step: "a reconnect", loading: observe(HELD) });

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
