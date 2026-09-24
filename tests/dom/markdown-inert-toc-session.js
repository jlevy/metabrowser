// Browserless session: the table of contents of an untrusted document.
//
// Under the untrusted profile KPress's toc.js cannot run, so the server sends KPress's
// entries, anchored to the `user-content-` headings, and the page draws and runs its own
// table of contents (builtin_plugins/markdown/inert-toc.js). This session runs the
// production placeRendered (inert-render.js) on the inert render recorded by
// tests/test_inert_toc.py in tests/fixtures/inert-toc-render.json -- Python's HTML parse
// of the server's inert HTML, rebuilt by the production static/inert-html.js -- then
// wires the table of contents in a scrolling viewport: the entry for the section at the
// reading line is active, the narrow toggle opens and closes the drawer, an entry click
// closes it, and disposal removes every listener. Paint, the real scroll, and the
// stylesheet's layout are the QA runbook's.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/inert-toc-render.json"), "utf8"),
);
const inertPath = path.join(repoRoot, "src/metabrowser/static/inert-html.js");
const sandbox = { window: {}, URL };
vm.runInNewContext(fs.readFileSync(inertPath, "utf8"), sandbox, { filename: inertPath });
const inert = sandbox.window.MetabrowserInertHtml;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

// A small element tree: enough of the DOM for the modules under test, with selectors
// limited to compounds of a tag, classes, and attributes, optionally after `:scope >`.
class Listeners {
  constructor() {
    this.listeners = new Map();
  }
  addEventListener(type, listener) {
    const set = this.listeners.get(type) ?? new Set();
    set.add(listener);
    this.listeners.set(type, set);
  }
  removeEventListener(type, listener) {
    this.listeners.get(type)?.delete(listener);
  }
  dispatch(type) {
    for (const listener of [...(this.listeners.get(type) ?? [])]) {
      listener({ type, target: this });
    }
  }
  count() {
    return [...this.listeners.values()].reduce((total, set) => total + set.size, 0);
  }
}

class Text {
  constructor(value, ownerDocument) {
    this.nodeType = 3;
    this.nodeValue = value;
    this.ownerDocument = ownerDocument;
    this.parentElement = null;
  }
  get textContent() {
    return this.nodeValue;
  }
}

class Element extends Listeners {
  constructor(tag, ownerDocument) {
    super();
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.ownerDocument = ownerDocument;
    this.attributes = new Map();
    this.childNodes = [];
    this.parentElement = null;
    this.scrollTop = 0;
    const element = this;
    this.classList = {
      add: (...names) => element.setClasses([...element.classes(), ...names]),
      contains: (name) => element.classes().includes(name),
      toggle(name, force) {
        const on = force ?? !element.classes().includes(name);
        element.setClasses(element.classes().filter((each) => each !== name));
        if (on) {
          element.setClasses([...element.classes(), name]);
        }
        return on;
      },
    };
  }
  classes() {
    return (this.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
  }
  setClasses(names) {
    this.setAttribute("class", [...new Set(names)].join(" "));
  }
  get className() {
    return this.getAttribute("class") ?? "";
  }
  set className(value) {
    this.setAttribute("class", value);
  }
  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  append(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
      this.childNodes.push(node);
    }
  }
  replaceChildren(...nodes) {
    this.childNodes = [];
    this.append(...nodes);
  }
  descendants() {
    return this.childNodes
      .filter((node) => node.nodeType === 1)
      .flatMap((node) => [node, ...node.descendants()]);
  }
  matches(selector) {
    return selector.split(",").some((one) => matchesCompound(this, one.trim()));
  }
  closest(selector) {
    for (let element = this; element; element = element.parentElement) {
      if (element.matches(selector)) {
        return element;
      }
    }
    return null;
  }
  querySelectorAll(selector) {
    const child = /^:scope\s*>\s*/.exec(selector);
    const pool = child ? this.childNodes.filter((node) => node.nodeType === 1) : this.descendants();
    const rest = child ? selector.slice(child[0].length) : selector;
    return pool.filter((element) => element.matches(rest));
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

function matchesCompound(element, selector) {
  const parts = selector.match(/^[a-z0-9]+|\.[\w-]+|\[[^\]]+\]/gi) ?? [];
  assert(parts.join("") === selector, `the session cannot match selector ${selector}`);
  return parts.every((part) => {
    if (part.startsWith(".")) {
      return element.classes().includes(part.slice(1));
    }
    if (part.startsWith("[")) {
      const [, name, value] = /^\[([\w-]+)(?:="((?:[^"\\]|\\.)*)")?\]$/.exec(part) ?? [];
      assert(name, `the session cannot match attribute ${part}`);
      const actual = element.getAttribute(name);
      return value === undefined ? actual !== null : actual === value.replace(/\\(.)/g, "$1");
    }
    return element.tagName.toLowerCase() === part.toLowerCase();
  });
}

const pageDocument = {
  createElement: (tag) => new Element(tag, pageDocument),
  createTextNode: (value) => new Text(String(value), pageDocument),
};

// The template the page parses the server's HTML into, from Python's parse of it.
function templateNodes(nodes) {
  return nodes.map((node) =>
    typeof node === "string"
      ? { nodeType: 3, nodeValue: node }
      : {
          nodeType: 1,
          tagName: node.tag.toUpperCase(),
          getAttribute: (name) => node.attrs.find(([key]) => key === name)?.[1] ?? null,
          childNodes: templateNodes(node.children),
        },
  );
}

// The page's own parse is a real browser's; everything after it is production code.
sandbox.window.MetabrowserInertHtml = Object.freeze({
  ...inert,
  sanitizeHtml: (_html, base) =>
    inert.sanitizeNodes(templateNodes(recorded.tree), pageDocument, base),
});
globalThis.window = sandbox.window;

function entries(article) {
  return article.querySelectorAll("a.toc-link").map((link) => ({
    level: link.parentElement.className,
    href: link.getAttribute("href"),
    text: link.textContent,
  }));
}

function state(article, viewport) {
  const toggle = article.querySelector(".kpress-toc-toggle");
  const backdrop = article.querySelector(".kpress-toc-backdrop");
  return {
    scrollTop: viewport.scrollTop,
    active: article.querySelector("a.active")?.getAttribute("href") ?? null,
    activeMarked: article.querySelector("[data-active]")?.getAttribute("href") ?? null,
    expanded: toggle.getAttribute("aria-expanded"),
    drawerOpen: article.querySelector(".kpress-toc").classList.contains("kpress-mobile-visible"),
    backdropVisible: backdrop.classList.contains("kpress-visible"),
    toggleShown: toggle.classList.contains("show-toggle"),
  };
}

async function main() {
  const render = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/inert-render.js"))
      .href
  );
  const mb = { ensureAsset: async () => undefined };

  // The viewport scrolls; each heading sits at a fixed offset in the document.
  const viewport = new Element("main", pageDocument);
  viewport.setAttribute("data-kpress-viewport", "");
  viewport.clientHeight = 800;
  viewport.getBoundingClientRect = () => ({ top: 100, height: 800 });
  const target = new Element("div", pageDocument);
  viewport.append(target);

  await render.placeRendered(
    target,
    { html: "", inert: true, toc: recorded.toc, model: { headings: recorded.headings } },
    mb,
  );
  const article = render.inertArticle(target);
  assert(article, "the inert article is the render's container's child");
  const headings = article.querySelectorAll("h1, h2, h3, h4, h5, h6");
  headings.forEach((heading, index) => {
    heading.getBoundingClientRect = () => ({ top: 100 + index * 1000 - viewport.scrollTop });
  });

  // A render KPress drew no table of contents for gets none, and entries that do not
  // point at an anchor in the document are left out.
  const plain = new Element("div", pageDocument);
  await render.placeRendered(
    plain,
    { html: "", inert: true, toc: false, model: { headings: recorded.headings } },
    mb,
  );
  const forged = new Element("div", pageDocument);
  await render.placeRendered(
    forged,
    {
      html: "",
      inert: true,
      toc: true,
      model: {
        headings: [
          { level: 1, title: "Outside", href: "https://example.com/" },
          { level: 1, title: "Unanchored", href: "#install" },
          { level: 1, title: "Missing", href: "#user-content-missing" },
          { level: 9, title: "Install", href: "#user-content-install" },
        ],
      },
    },
    mb,
  );

  /** @type {Array<() => void>} */
  const frames = [];
  const flush = () => {
    for (const frame of frames.splice(0)) {
      frame();
    }
  };
  const windowTarget = new Listeners();
  windowTarget.innerHeight = 800;
  windowTarget.scrollY = 0;
  const dispose = render.wireInertToc(article, {
    schedule: (callback) => frames.push(callback),
    cancel: () => {},
    windowTarget,
  });
  const transcript = {
    headingIds: headings.map((heading) => heading.getAttribute("id")),
    layout: article.querySelector(".kpress-doc-layout").className,
    entries: entries(article),
    withoutToc: plain.querySelector(".kpress-toc") === null,
    forgedEntries: entries(render.inertArticle(forged)),
    atTop: state(article, viewport),
  };
  for (const entry of transcript.entries) {
    assert(
      article.querySelector(`[id="${entry.href.slice(1)}"]`)?.tagName.startsWith("H"),
      `${entry.href} names a heading`,
    );
  }

  // Scroll so the fourth heading (constructor, 4000px down) crosses the reading line.
  viewport.scrollTop = 3900;
  viewport.dispatch("scroll");
  viewport.dispatch("scroll");
  transcript.scrollFramesQueued = frames.length;
  flush();
  transcript.scrolled = state(article, viewport);

  const toggle = article.querySelector(".kpress-toc-toggle");
  toggle.dispatch("click");
  transcript.toggleOpened = state(article, viewport);
  const troubleshooting = article
    .querySelectorAll("a.toc-link")
    .find((link) => link.getAttribute("href") === "#user-content-troubleshooting");
  troubleshooting.dispatch("click");
  transcript.entryClicked = state(article, viewport);
  toggle.dispatch("click");
  article.querySelector(".kpress-toc-backdrop").dispatch("click");
  transcript.backdropClicked = state(article, viewport);

  dispose();
  const listeners = [viewport, toggle, ...article.descendants()].reduce(
    (total, element) => total + element.count(),
    0,
  );
  transcript.disposed = { listeners };
  console.log(JSON.stringify(transcript, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
