// Which of a Markdown document's images load eagerly when its file is entered again
// (docs/design-system.md, "A Repaint Keeps Its Images").
//
// The production link enhancer resolves each image's address, as every mount of the
// rendered view has it do, on images that arrive as KPress writes them: lazy, with the
// address the author wrote. The engine's loads are events this session fires, so it
// decides which images the page holds: entering a file again builds its document again,
// and an image whose served address has loaded in this page is made eager before that
// address is set, so it takes the held copy. Its authored address goes first, because an
// eager image asks for its address at once. An image not loaded, and one the enhancer
// did not serve, stays lazy. After as many images as one document admits have loaded
// since, the oldest are forgotten and load lazily again.
//
// This checks attributes, their order, and listeners, not loading or paint, which are the
// engine's; the design-system section has the WebKit and Chrome measurements.
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const pluginDir = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");

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

const dataUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const fileUrl = (name) => pathToFileURL(path.join(pluginDir, name)).href;

async function loadEnhancer() {
  const read = (name) => fs.readFileSync(path.join(pluginDir, name), "utf8");
  const coordinator = dataUrl(
    read("reconciliation-coordinator.js")
      .replace('"./links.js"', JSON.stringify(fileUrl("links.js")))
      .replace('"./project-adapters.js"', JSON.stringify(fileUrl("project-adapters.js")))
      .replace('"./wiki-resolver.js"', JSON.stringify(fileUrl("wiki-resolver.js"))),
  );
  // No wiki targets here, and so no Worker.
  const wiki = dataUrl("export function enhanceWikiLinks(){return {dispose(){}}}");
  const worker = dataUrl("export function acquireMarkdownWorkerClient(){return {dispose(){}}}");
  const enhancer = read("link-enhancer.js")
    .replace('"./dom-traversal.js"', JSON.stringify(fileUrl("dom-traversal.js")))
    .replace('"./github-localizer.js"', JSON.stringify(fileUrl("github-localizer.js")))
    .replace('"./links.js"', JSON.stringify(fileUrl("links.js")))
    .replace('"./markdown-worker-client.js"', JSON.stringify(worker))
    .replace('"./reconciliation-coordinator.js"', JSON.stringify(coordinator))
    .replace('"./wiki-enhancer.js"', JSON.stringify(wiki));
  return import(dataUrl(enhancer));
}

async function run() {
  const { enhanceRenderedLinks } = await loadEnhancer();
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

  /** Enter *documentPath*, its images parsed from *sources*, as a mount does. */
  function enter(documentPath, sources) {
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

  const README = ["images/shown.png", "images/far.png", "https://example.com/remote.png"];
  const steps = [];

  // First entry: the page holds nothing, so every image is lazy.
  const first = enter("docs/readme.md", README);
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
  const second = enter("docs/readme.md", README);
  steps.push({ step: "entered again", images: facts(second.images) });
  // The reader scrolls to the far image.
  second.container.load(second.images[1]);
  second.handle.dispose();

  const third = enter("docs/readme.md", README);
  steps.push({ step: "entered after reaching the far image", images: facts(third.images) });
  third.handle.dispose();

  // Held by its served address, whichever document shows it.
  const other = enter("docs/guide/other.md", ["../images/shown.png"]);
  steps.push({ step: "another document shows the same image", images: facts(other.images) });
  other.handle.dispose();

  // As many images as one document admits load after them.
  const gallerySources = Array.from({ length: 4096 }, (_, index) => `gallery/${index}.png`);
  const gallery = enter("docs/gallery.md", gallerySources);
  for (const element of gallery.images) {
    gallery.container.load(element);
  }
  gallery.handle.dispose();
  const forgotten = enter("docs/readme.md", README);
  steps.push({
    step: "entered after 4,096 other images loaded",
    images: facts(forgotten.images),
  });
  forgotten.handle.dispose();

  return { steps };
}

run().then(
  (result) => {
    console.log(JSON.stringify(result));
  },
  (error) => {
    console.error(error);
    process.exit(1);
  },
);
