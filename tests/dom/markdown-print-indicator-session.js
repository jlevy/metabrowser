// Browserless session: a rendered document's print button (print-indicator.js), on the
// mounts that ask for it.
//
// The production Markdown plugin registers its Document view (index.js), the production
// README panel mounts the production Markdown mount (rendered.js) on a folder's Overview,
// and both place a render through the production placement modules, trusted
// (place-rendered.js) and inert (inert-render.js). The DOM is a small one of this file's
// own, enough for those modules: elements with children, classes, attributes, listeners,
// and the few selectors they use. The SDK's owner mark is the production SDK's
// (sdk-sandbox.js); the inert render's sanitizer is a stand-in, since what it keeps is
// tests/dom/inert-html-session.js's subject and not this one's.
//
// It shows which mounts carry the button, where it goes, what it says, that a click
// prints once and a document's own copy of its markup prints nothing, that a failed render
// has none, and that disposing removes it with its listener. A click prints once the
// document is ready (print-ready.js): an image not yet loaded is made eager and waited
// for, a click meanwhile prints nothing more, and a heading before an image is given its
// size. And a print resolves the page light while a rendered document is mounted, and
// restores the theme after it. Where it lands on the page,
// that nothing moves when it arrives, and the table of contents toggle beside it are
// layout, measured in headless Chrome by tests/dom/document-print-chrome.mjs.
//
// Prints the transcript as JSON, with `failures`; exits 1 on any failure.

const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createSdkSandbox, linkCardRegistration } = require("./sdk-sandbox.js");

const repoRoot = path.resolve(__dirname, "../..");
const pluginRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins");
const moduleUrl = (relative) => pathToFileURL(path.join(pluginRoot, relative)).href;

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

const failures = [];
function check(name, condition, detail = undefined) {
  if (!condition) {
    failures.push(detail === undefined ? name : `${name}: ${JSON.stringify(detail)}`);
  }
}

class Listeners {
  constructor() {
    this.byType = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.byType.get(type) || new Set();
    listeners.add(listener);
    this.byType.set(type, listeners);
  }

  removeEventListener(type, listener) {
    this.byType.get(type)?.delete(listener);
  }

  dispatchEvent(event) {
    for (const listener of [...(this.byType.get(event.type) || [])]) {
      listener(event);
    }
    return true;
  }

  listenerCount() {
    return [...this.byType.values()].reduce((total, listeners) => total + listeners.size, 0);
  }
}

// One compound selector: a tag, classes, and bare or valued attributes.
function parseCompound(text) {
  const match = /^([a-z][a-z0-9-]*)?((?:\.[\w-]+)*)((?:\[[\w-]+(?:="[^"]*")?\])*)$/i.exec(text);
  if (!match) {
    throw new Error(`the session's DOM has no selector ${text}`);
  }
  return {
    attributes: [...match[3].matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)].map((part) => [
      part[1],
      part[2],
    ]),
    classes: match[2].split(".").filter(Boolean),
    tag: match[1]?.toUpperCase() ?? null,
  };
}

function matchesCompound(element, compound) {
  return (
    (compound.tag === null || element.tagName === compound.tag) &&
    compound.classes.every((name) => element.classList.contains(name)) &&
    compound.attributes.every(([name, value]) =>
      value === undefined ? element.hasAttribute(name) : element.getAttribute(name) === value,
    )
  );
}

// A selector of compounds joined by `>` or descendant spaces, optionally from `:scope`,
// matched right to left against *element*, with *scope* the element queried.
function matchesChain(element, steps, scope) {
  let current = element;
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const step = steps[index];
    if (index === steps.length - 1) {
      if (!matchesCompound(current, step.compound)) {
        return false;
      }
    } else if (step.compound === ":scope") {
      return step.next === ">" ? current.parentElement === scope : scope.contains(current);
    } else if (step.next === ">") {
      current = current.parentElement;
      if (!current || !matchesCompound(current, step.compound)) {
        return false;
      }
    } else {
      do {
        current = current.parentElement;
      } while (current && !matchesCompound(current, step.compound));
      if (!current) {
        return false;
      }
    }
  }
  return true;
}

function parseSelector(selector) {
  return selector.split(",").map((part) => {
    const tokens = part
      .trim()
      .split(/\s*(>)\s*|\s+/)
      .filter(Boolean);
    const steps = [];
    for (let index = 0; index < tokens.length; index += 1) {
      if (tokens[index] === ">") {
        continue;
      }
      steps.push({
        compound: tokens[index] === ":scope" ? ":scope" : parseCompound(tokens[index]),
        next: tokens[index + 1] === ">" ? ">" : " ",
      });
    }
    return steps;
  });
}

class ClassList {
  constructor(element) {
    this.element = element;
  }

  get names() {
    return this.element.className.split(/\s+/).filter(Boolean);
  }

  add(...names) {
    this.element.className = [...new Set([...this.names, ...names])].join(" ");
  }

  remove(...names) {
    this.element.className = this.names.filter((name) => !names.includes(name)).join(" ");
  }

  contains(name) {
    return this.names.includes(name);
  }

  toggle(name, force) {
    const on = force === undefined ? !this.contains(name) : Boolean(force);
    if (on) {
      this.add(name);
    } else {
      this.remove(name);
    }
    return on;
  }
}

class Element extends Listeners {
  constructor(ownerDocument, tagName, attributes = {}) {
    super();
    this.ownerDocument = ownerDocument;
    this.nodeType = 1;
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map();
    this.children = [];
    this.parentElement = null;
    this.className = "";
    this.classList = new ClassList(this);
    this.dataset = {};
    this.markup = "";
    this.textContent = "";
    // An image's load, which the session completes by hand; other elements have none.
    this.complete = true;
    this.naturalWidth = 0;
    this.naturalHeight = 0;
    const properties = new Map();
    this.style = {
      getPropertyValue: (name) => properties.get(name) ?? "",
      removeProperty: (name) => properties.delete(name),
      setProperty: (name, value) => properties.set(name, String(value)),
    };
    for (const [name, value] of Object.entries(attributes)) {
      this.setAttribute(name, value);
    }
  }

  get firstElementChild() {
    return this.children[0] ?? null;
  }

  get lastElementChild() {
    return this.children.at(-1) ?? null;
  }

  get nextElementSibling() {
    const siblings = this.parentElement?.children ?? [];
    return siblings[siblings.indexOf(this) + 1] ?? null;
  }

  matches(selector) {
    return parseSelector(selector).some((steps) => matchesChain(this, steps, null));
  }

  get childElementCount() {
    return this.children.length;
  }

  get type() {
    return this.getAttribute("type") ?? "";
  }

  set type(value) {
    this.setAttribute("type", value);
  }

  // The markup this file's DOM keeps as text: an icon, or a loading placeholder, which
  // replaces the children as the browser's would.
  get innerHTML() {
    return this.markup;
  }

  set innerHTML(value) {
    this.replaceChildren();
    this.markup = String(value);
  }

  getAttribute(name) {
    if (name === "class") {
      return this.className || null;
    }
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return name === "class" ? Boolean(this.className) : this.attributes.has(name);
  }

  setAttribute(name, value) {
    if (name === "class") {
      this.className = String(value);
      return;
    }
    this.attributes.set(name, String(value));
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  append(...nodes) {
    for (const node of nodes) {
      if (node instanceof Fragment) {
        this.append(...node.children);
        continue;
      }
      node.remove();
      node.parentElement = this;
      this.children.push(node);
    }
  }

  prepend(...nodes) {
    const rest = this.children;
    this.children = [];
    this.append(...nodes);
    this.children.push(...rest);
  }

  replaceChildren(...nodes) {
    for (const child of [...this.children]) {
      child.remove();
    }
    this.markup = "";
    this.append(...nodes);
  }

  remove() {
    const parent = this.parentElement;
    if (parent) {
      parent.children = parent.children.filter((child) => child !== this);
      this.parentElement = null;
    }
  }

  contains(candidate) {
    for (let node = candidate; node; node = node.parentElement) {
      if (node === this) {
        return true;
      }
    }
    return false;
  }

  closest(selector) {
    const chains = parseSelector(selector);
    for (let node = this; node; node = node.parentElement) {
      if (chains.some((steps) => matchesChain(node, steps, null))) {
        return node;
      }
    }
    return null;
  }

  descendants() {
    return this.children.flatMap((child) => [child, ...child.descendants()]);
  }

  querySelectorAll(selector) {
    const chains = parseSelector(selector);
    return this.descendants().filter((node) =>
      chains.some((steps) => matchesChain(node, steps, this)),
    );
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }

  click() {
    this.dispatchEvent({ type: "click", target: this, preventDefault() {} });
  }
}

// A template's or a sanitizer's parsed content: children, and no element of its own.
class Fragment extends Element {
  constructor(ownerDocument) {
    super(ownerDocument, "#fragment");
  }
}

class Document extends Listeners {
  constructor() {
    super();
    this.implementation = { createHTMLDocument: () => new Document() };
    this.documentElement = new Element(this, "html");
  }

  createElement(tagName) {
    const element = new Element(this, tagName);
    if (element.tagName === "TEMPLATE") {
      // A render's HTML, parsed: the session's renders are built from their specs below.
      Object.defineProperty(element, "innerHTML", {
        set: (html) => {
          element.content = build(this, html);
        },
      });
    }
    return element;
  }
}

/**
 * A KPress render's HTML for this DOM: `html` names a spec below, and the spec builds the
 * elements KPress emits for it.
 */
const RENDERS = {
  // A trusted render: KPress's article, its layout, and the card holding the prose, with
  // a heading first and an Obsidian transclusion whose own card is nested in the document.
  "kpress:readme": (doc) => [
    el(doc, "article", { class: "kpress kpress-doc", "data-kpress-card": "on" }, [
      el(doc, "div", { class: "kpress-doc-layout kpress-content-with-toc" }, [
        el(doc, "nav", { class: "kpress-toc", "data-kpress-toc": "" }),
        el(doc, "div", { class: "kpress-prose kpress-long-text" }, [
          el(doc, "h1", { id: "sample-project" }),
          el(doc, "p"),
          // A screenshot under its heading, below the fold: KPress writes it lazy.
          el(doc, "h2", { id: "screenshot" }),
          el(doc, "figure", { class: "kpress-figure" }, [unloadedImage(doc)]),
          el(doc, "div", { class: "metabrowser-wiki-transclusion" }, [
            el(doc, "article", { class: "kpress kpress-doc", "data-kpress-card": "on" }, [
              el(doc, "div", { class: "kpress-doc-layout" }, [
                el(doc, "div", { class: "kpress-prose kpress-long-text" }, [el(doc, "p")]),
              ]),
            ]),
          ]),
          // The document's own copy of the button's markup, which a trusted folder's
          // Markdown keeps: it is not the page's button and prints nothing.
          el(doc, "button", { class: "icon-btn metabrowser-print-indicator", type: "button" }),
        ]),
      ]),
    ]),
  ],
  // A document whose first block is a paragraph.
  "kpress:note": (doc) => [
    el(doc, "article", { class: "kpress kpress-doc", "data-kpress-card": "on" }, [
      el(doc, "div", { class: "kpress-doc-layout" }, [
        el(doc, "div", { class: "kpress-prose kpress-long-text" }, [el(doc, "p")]),
      ]),
    ]),
  ],
  // What the inert render's sanitizer keeps: the prose's nodes, which inert-render.js
  // puts in an article and card of its own.
  "inert:readme": (doc) => [el(doc, "h1", { id: "user-content-sample-project" }), el(doc, "p")],
};

/** A lazy image that has not loaded, as KPress writes one the reader has not scrolled to. */
function unloadedImage(doc) {
  const image = el(doc, "img", { src: "/raw?path=shot.png", loading: "lazy" });
  image.complete = false;
  return image;
}

/** Load *image*, 1600 by 1000, as the browser does once it fetches it. */
function loadImage(image) {
  Object.assign(image, { complete: true, naturalWidth: 1600, naturalHeight: 1000 });
  image.dispatchEvent({ type: "load", target: image });
}

function el(doc, tagName, attributes = {}, children = []) {
  const element = new Element(doc, tagName, attributes);
  element.append(...children);
  return element;
}

function build(doc, html) {
  const spec = RENDERS[html];
  if (!spec) {
    throw new Error(`no render spec ${html}`);
  }
  const fragment = new Fragment(doc);
  fragment.append(...spec(doc));
  return fragment;
}

async function flush() {
  for (let turn = 0; turn < 8; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

(async () => {
  const doc = new Document();
  const prints = [];
  const windowTarget = new Listeners();
  Object.assign(windowTarget, {
    cancelAnimationFrame: () => {},
    print: () => prints.push("window.print"),
    requestAnimationFrame: () => 0,
  });
  globalThis.document = doc;
  globalThis.window = windowTarget;
  globalThis.requestAnimationFrame = windowTarget.requestAnimationFrame;
  globalThis.cancelAnimationFrame = windowTarget.cancelAnimationFrame;

  // The production SDK's owner mark, from a page of its own.
  const sdk = createSdkSandbox();
  const PRINTER = '<svg data-icon="printer"></svg>';
  const renders = new Map();
  const registered = new Map();
  // The Markdown plugin's exports, which the README panel loads as a dependent does.
  let markdown = null;
  const mb = {
    decorateExternalLink: sdk.metabrowser.decorateExternalLink,
    ...linkCardRegistration(),
    async ensureAsset(name) {
      check("the inert render loads only its sanitizer", name === "inert-html", name);
    },
    plugins: {
      async load(name) {
        check("the README panel loads only the Markdown plugin", name === "markdown", name);
        return markdown;
      },
    },
    errors: { isAbortError: (error) => error?.name === "AbortError" },
    escapeHtml: (value) => String(value),
    async fetchKpressRender(ctx) {
      const render = renders.get(ctx.path);
      if (render instanceof Error) {
        throw render;
      }
      return render;
    },
    fileCatalog: { snapshot: () => ({ complete: true, files: [] }), subscribe: () => () => {} },
    icons: { print: PRINTER },
    kpressInitToc: () => () => {},
    navigation: {
      current: () => ({ path: "" }),
      href: (target) => `/view/${target.path}`,
      open: async () => {},
    },
    ownDelegate: sdk.metabrowser.ownDelegate,
    registerView(kind, view, spec) {
      registered.set(`${kind}/${view}`, spec);
    },
    repository: null,
  };
  windowTarget.metabrowser = mb;
  // The inert render's sanitizer: the nodes of the render the spec names.
  windowTarget.MetabrowserInertHtml = {
    kpressProse(nodes, scratch) {
      const prose = scratch.createElement("div");
      prose.className = "kpress-prose";
      prose.append(...nodes);
      return prose;
    },
    sanitizeHtml: (html) => build(doc, html).children,
  };

  markdown = await import(moduleUrl("markdown/index.js"));
  const { createReadmePanel } = await import(moduleUrl("folder/readme-panel.js"));
  const { PRINT_INDICATOR_LABEL } = await import(moduleUrl("markdown/print-indicator.js"));
  // A file's text arrives without its content here, so no mount runs the Markdown Worker.
  const context = (filePath) => ({ kind: "markdown", path: filePath, raw: {} });
  const mounted = async (handle) => {
    await handle.ready;
    await flush();
    return handle;
  };
  const container = () => {
    const host = doc.createElement("div");
    host.className = "content-body metabrowser-kpress-host md-body";
    return host;
  };
  const card = (host) =>
    host.querySelector(":scope > article.kpress > .kpress-doc-layout > .kpress-long-text");
  const pageButtons = (host) =>
    host
      .querySelectorAll(".metabrowser-print-indicator")
      .filter((button) => sdk.MetabrowserPluginHost.isOwnedDelegate(button));
  const describe = (host) => {
    const buttons = pageButtons(host);
    const button = buttons[0];
    const top = card(host);
    return {
      buttons: buttons.length,
      ...(button
        ? {
            ariaLabel: button.getAttribute("aria-label"),
            className: button.className,
            icon: button.innerHTML === PRINTER ? "printer" : button.innerHTML,
            id: button.getAttribute("id"),
            inCard: button.parentElement === top,
            lastInCard: top?.lastElementChild === button,
            ownerMarked: sdk.MetabrowserPluginHost.isOwnedDelegate(button),
            // The tooltip admits it inside the document by identity (app.js tipTextAnchor).
            pageElement: sdk.MetabrowserPluginHost.ownsElement(button),
            tipText: button.getAttribute("data-tip-text"),
            type: button.type,
          }
        : {}),
    };
  };

  // The file's Document view, as the shell mounts it: the registered render, which asks for
  // the button.
  renders.set("README.md", { diagnostics: [], html: "kpress:readme" });
  renders.set("notes/note.md", { diagnostics: [], html: "kpress:note" });
  const fileView = container();
  const fileHandle = await mounted(
    registered.get("markdown/rendered").render(fileView, context("README.md")),
  );
  const file = describe(fileView);
  check("the Document view's card has one page button", file.buttons === 1, file);
  check(
    "it is the card's last child, the top-level card and not a transclusion's",
    file.inCard && file.lastInCard,
    file,
  );
  check(
    "it is named and labelled for print",
    file.ariaLabel === PRINT_INDICATOR_LABEL && file.tipText === PRINT_INDICATOR_LABEL,
    file,
  );
  check(
    "it is owner-marked, the element ownDelegate marked, and has no id a label could name",
    file.ownerMarked && file.pageElement && !file.id,
    file,
  );

  const noteView = container();
  const noteHandle = await mounted(
    registered.get("markdown/rendered").render(noteView, context("notes/note.md")),
  );
  const note = describe(noteView);
  check("a document opening with a paragraph has it too", note.buttons === 1 && note.lastInCard);

  // A click on the button prints once the document is ready; a click on the document's
  // own copy prints nothing, since no document-wide listener reads the class.
  fileView.querySelector(".metabrowser-print-indicator")?.click();
  await flush();
  const documentCopyPrints = prints.length;
  const fileButtonNow = pageButtons(fileView)[0];
  const shot = card(fileView)?.querySelector(":scope > figure > img");
  const heading = card(fileView)?.querySelector(":scope > h2");
  fileButtonNow?.click();
  await flush();
  // The screenshot has not loaded: no print yet, and a second click adds none.
  const waiting = {
    busy: fileButtonNow?.getAttribute("aria-busy") ?? null,
    loading: shot?.getAttribute("loading") ?? null,
    prints: prints.length - documentCopyPrints,
  };
  fileButtonNow?.click();
  await flush();
  if (shot) {
    loadImage(shot);
  }
  await flush();
  const click = {
    documentCopy: documentCopyPrints,
    waiting,
    pageButton: prints.length - documentCopyPrints,
    busyAfter: fileButtonNow?.getAttribute("aria-busy") ?? null,
    headingImage: {
      ratio: heading?.style.getPropertyValue("--print-next-image-ratio") ?? null,
      width: heading?.style.getPropertyValue("--print-next-image-width") ?? null,
    },
    documentListeners: doc.listenerCount(),
  };
  check("the document's copy of the markup prints nothing", click.documentCopy === 0, click);
  check(
    "a click makes an image not yet loaded eager and waits for it",
    waiting.loading === "eager" && waiting.prints === 0 && waiting.busy === "true",
    click,
  );
  check("the page's button prints once, the browser's way", click.pageButton === 1, click);
  check("the button is not busy once it printed", click.busyAfter === null, click);
  check(
    "the heading before the image is given its size for print",
    click.headingImage.width === "1600px" && click.headingImage.ratio === "0.625",
    click,
  );
  check("the button adds no document-wide listener", click.documentListeners === 0, click);

  // A print resolves the page light while a rendered document is mounted, with the theme
  // crossfade off, and restores the theme after it; a light page is left as it is.
  const root = doc.documentElement;
  root.setAttribute("data-theme", "dark");
  root.setAttribute("data-kpress-resolved-theme", "dark");
  root.classList.add("theme-anim");
  const themeOf = () => ({
    anim: root.classList.contains("theme-anim"),
    kpress: root.getAttribute("data-kpress-resolved-theme"),
    theme: root.getAttribute("data-theme"),
  });
  windowTarget.dispatchEvent({ type: "beforeprint" });
  const printingDark = themeOf();
  windowTarget.dispatchEvent({ type: "afterprint" });
  const afterDark = themeOf();
  root.setAttribute("data-theme", "light");
  root.setAttribute("data-kpress-resolved-theme", "light");
  windowTarget.dispatchEvent({ type: "beforeprint" });
  const printingLight = themeOf();
  windowTarget.dispatchEvent({ type: "afterprint" });
  const printListeners = () =>
    ["beforeprint", "afterprint"].reduce(
      (total, type) => total + (windowTarget.byType.get(type)?.size ?? 0),
      0,
    );
  const theme = { printingDark, afterDark, printingLight, printListeners: printListeners() };
  check(
    "a print in the dark theme resolves the page light, crossfade off",
    printingDark.theme === "light" && printingDark.kpress === "light" && !printingDark.anim,
    theme,
  );
  check(
    "after the print the dark theme is back, crossfade on",
    afterDark.theme === "dark" && afterDark.kpress === "dark" && afterDark.anim,
    theme,
  );
  check("a print in the light theme changes nothing", printingLight.theme === "light", theme);
  check(
    "the page holds one pair of print listeners, however many documents",
    theme.printListeners === 2,
    theme,
  );

  // The README on a folder's Overview: the README panel asks for the button.
  const readmeBody = container();
  const readmeHandle = await mounted(
    await createReadmePanel(mb).mount(readmeBody, { path: "", raw: {} }, { path: "README.md" }, {}),
  );
  const readme = describe(readmeBody);
  check("the Overview's README has the file's button", readme.buttons === 1 && readme.lastInCard);

  // A host that does not ask, and one that asks for something else.
  const plainView = container();
  const plainHandle = await mounted(markdown.mountRendered(plainView, context("README.md")));
  const offView = container();
  const offHandle = await mounted(
    markdown.mountRendered(offView, context("README.md"), { printIndicator: false }),
  );
  const hosts = {
    asked: file.buttons,
    notAsked: describe(plainView).buttons,
    off: describe(offView).buttons,
  };
  check("a mount has none unless its host asks", hosts.notAsked === 0 && hosts.off === 0, hosts);

  // An inert render, as a served mirror and an --untrusted folder place it: the page's own
  // article and card, and the same button in it.
  renders.set("mirror/README.md", { diagnostics: [], html: "inert:readme", inert: true });
  const inertView = container();
  const inertHandle = await mounted(
    registered.get("markdown/rendered").render(inertView, context("mirror/README.md")),
  );
  const inert = describe(inertView);
  check(
    "an inert render's card has the same button",
    inert.buttons === 1 &&
      inert.lastInCard &&
      inertView.querySelector(":scope > article.kpress-inert") !== null,
    inert,
  );

  // A render that failed draws an error, which has no card and no button.
  renders.set("broken.md", Object.assign(new Error("KPress render failed"), { payload: {} }));
  const brokenView = container();
  // The failure goes to the console (docs/design-system-messages.md), which this
  // session does not pin.
  const consoleError = console.error;
  console.error = () => {};
  let brokenHandle;
  try {
    brokenHandle = await mounted(
      registered.get("markdown/rendered").render(brokenView, context("broken.md")),
    );
  } finally {
    console.error = consoleError;
  }
  const broken = { buttons: describe(brokenView).buttons, card: card(brokenView) !== null };
  check("a failed render has no button", broken.buttons === 0 && !broken.card, broken);

  // Disposing removes the button and its listener, once.
  const fileButton = pageButtons(fileView)[0];
  fileHandle.dispose();
  fileHandle.dispose();
  const disposed = {
    buttons: describe(fileView).buttons,
    listeners: fileButton?.listenerCount() ?? null,
    removed: fileButton?.parentElement === null,
  };
  check(
    "disposing removes the button and its listener",
    disposed.buttons === 0 && disposed.removed && disposed.listeners === 0,
    disposed,
  );
  // The shell disposes a view before it mounts the next into the same host: one button.
  const remounted = await mounted(
    registered.get("markdown/rendered").render(fileView, context("README.md")),
  );
  const replaced = describe(fileView).buttons;
  check("a view mounted again into its host has one button", replaced === 1, replaced);
  for (const handle of [
    remounted,
    noteHandle,
    readmeHandle,
    plainHandle,
    offHandle,
    inertHandle,
    brokenHandle,
  ]) {
    handle.dispose();
  }
  // With the last document gone, so are the print listeners.
  theme.printListenersAfterAll = printListeners();
  check(
    "the last document's disposal removes the print listeners",
    theme.printListenersAfterAll === 0,
    theme,
  );

  const transcript = {
    broken,
    click,
    disposed,
    file,
    hosts,
    inert: { buttons: inert.buttons, lastInCard: inert.lastInCard },
    note: { buttons: note.buttons, lastInCard: note.lastInCard },
    readme: { buttons: readme.buttons, lastInCard: readme.lastInCard },
    replaced,
    theme,
    failures,
  };
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  process.exit(failures.length ? 1 : 0);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
