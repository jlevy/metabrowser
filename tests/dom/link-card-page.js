// One page for the link card's browserless sessions: the exact shell tooltip, the exact SDK
// that registers a link and loads the card at the first rest, the exact registry and
// providers it loads, and the exact resolver, in one realm, as one page has them.
//
//   const { createPage } = require("./link-card-page.js");
//   const page = createPage({ repository: null, cards: { loadMs: 30 } });
//
// It runs:
//
// - app.js's tooltip and its delegated listeners, lifted verbatim from its section comment
//   through the listener that ends a focus repair: `show`, `hide`, the short-tip listeners on
//   `mouseenter` and `mouseleave`, and the `focusin` listener that puts a tooltip away, with
//   the helpers they call (`esc`, `eventTargetElement`, `isPageElement`), lifted by name as
//   tests/dom/nav-reveal-session.js lifts them;
// - static/plugin-sdk-views.js whole, which registers each link (`metabrowser.previewLink`)
//   and loads the `link-previews` bundle at the first rest on one;
// - static/repository-links.js, whose `enhance` registers each link of a text it reads;
// - the `link-previews` bundle, static/link-previews.js and then
//   static/link-preview-providers.js, as server.py lists it (tests/test_link_previews_js.py
//   holds that), run when the SDK asks for it (`ensureAsset`), *loadMs* later on this file's
//   clock, or refused with *fails*; every read its providers make replays the server's own
//   answer (tests/fixtures/link-preview-providers-responses.json, recorded by
//   tests/test_link_preview_providers_session.py), answered 40 ms later.
//
// The DOM is stand-ins that know their parent, their attributes, their text, the few
// selectors these modules ask, and the events the browser sends: a pointer that leaves one
// element and enters another sends `pointerout`, `mouseleave` for each element it left,
// `pointerover`, and `mouseenter` for each it entered; a press sends `pointerdown`, and focus
// `focusin`, each through the document's capture listeners first. The SDK is the shell's own
// where it registers a link and draws the card (`mb.tooltip` is app.js's tooltip) and
// stand-ins elsewhere.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticRoot = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticRoot, "app.js"), "utf8");
const recorded = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "tests/fixtures/link-preview-providers-responses.json"),
    "utf8",
  ),
);

/** The `link-previews` bundle's scripts, in server.py's order. */
const LINK_PREVIEWS_BUNDLE = ["link-previews.js", "link-preview-providers.js"];

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/** app.js's tooltip, from its section comment through its delegated listeners. */
const TOOLTIP_AND_LISTENERS =
  /\n\/\/ ── Custom tooltip[\s\S]*?\ndocument\.addEventListener\("pointerdown", endTooltipFocusRepair, true\);\n/;
const tooltipSource = appSource.match(TOOLTIP_AND_LISTENERS)?.[0];
assert(tooltipSource, "app.js's tooltip and its listeners were not found");

/** One top-level function of app.js, by name, as tests/dom/nav-reveal-session.js lifts one. */
function appFunction(name) {
  const match = new RegExp(`\\n(async )?function ${name}\\(`).exec(appSource);
  assert(match, `app.js ${name} is not extractable`);
  const start = match.index + 1;
  const end = appSource.indexOf("\n}\n", start);
  return appSource.slice(start, end + 2);
}

// ── The stand-in DOM ───────────────────────────────────────────────

class FakeText {
  constructor(text) {
    this.nodeType = 3;
    this.nodeValue = text;
    this.parentNode = null;
  }
  get textContent() {
    return this.nodeValue;
  }
}

/** Whether *element* matches one compound selector: `tag`, `.class`, `[attr]`, or `*`. */
function matches(element, selector) {
  if (selector === "*") {
    return true;
  }
  const parts = selector.match(/^([a-z]+)?((?:\.[\w-]+)*)((?:\[[\w-]+\])*)$/);
  assert(parts, `the stand-in DOM does not read ${selector}`);
  const [, tag, classes, attributes] = parts;
  if (tag && element.tagName !== tag.toUpperCase()) {
    return false;
  }
  const own = String(element.attributes.get("class") ?? "").split(/\s+/);
  for (const name of classes.split(".").filter(Boolean)) {
    if (!own.includes(name)) {
      return false;
    }
  }
  for (const [, name] of attributes.matchAll(/\[([\w-]+)\]/g)) {
    if (!element.attributes.has(name)) {
      return false;
    }
  }
  return true;
}

class FakeElement {
  constructor(tag, name = tag, attributes = {}) {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.name = name;
    this.parentNode = null;
    this.childNodes = [];
    this.listeners = [];
    this.attributes = new Map(Object.entries(attributes));
    this.isDocument = false;
    this.style = {};
    this.innerHTML = "";
    this.classList = {
      contains: (value) =>
        String(this.attributes.get("class") ?? "")
          .split(/\s+/)
          .includes(value),
      add: (value) => {
        const own = new Set(String(this.attributes.get("class") ?? "").split(/\s+/));
        own.add(value);
        this.attributes.set("class", [...own].filter(Boolean).join(" "));
      },
      remove: (value) => {
        const own = String(this.attributes.get("class") ?? "")
          .split(/\s+/)
          .filter((each) => each && each !== value);
        this.attributes.set("class", own.join(" "));
      },
    };
    this.dataset = new Proxy(
      {},
      {
        get: (_target, key) =>
          this.attributes.get(
            `data-${String(key).replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`,
          ),
      },
    );
  }
  append(...nodes) {
    for (const item of nodes) {
      const node = typeof item === "string" ? new FakeText(item) : item;
      node.parentNode = this;
      this.childNodes.push(node);
    }
    return this;
  }
  appendChild(node) {
    this.append(node);
    return node;
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.childNodes = this.parentNode.childNodes.filter((node) => node !== this);
      this.parentNode = null;
    }
  }
  get className() {
    return this.attributes.get("class") ?? "";
  }
  set className(value) {
    this.attributes.set("class", String(value));
  }
  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }
  set textContent(text) {
    this.childNodes = [];
    this.append(String(text));
  }
  get lastElementChild() {
    return this.childNodes.findLast((node) => node.nodeType === 1) ?? null;
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  hasAttribute(name) {
    return this.attributes.has(name);
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  contains(other) {
    for (let at = other; at; at = at.parentNode) {
      if (at === this) {
        return true;
      }
    }
    return false;
  }
  get isConnected() {
    for (let at = this; at; at = at.parentNode) {
      if (at.isDocument) {
        return true;
      }
    }
    return false;
  }
  closest(selector) {
    for (let at = this; at && at.nodeType === 1; at = at.parentNode) {
      if (!at.isDocument && matches(at, selector)) {
        return at;
      }
    }
    return null;
  }
  /** Descendants matching one selector or a comma's list of them, in document order. */
  querySelectorAll(selector) {
    const selectors = selector.split(",").map((each) => each.trim());
    const found = [];
    const walk = (node) => {
      for (const child of node.childNodes) {
        if (child.nodeType === 1) {
          if (selectors.some((each) => matches(child, each))) {
            found.push(child);
          }
          walk(child);
        }
      }
    };
    walk(this);
    return found;
  }
  querySelector(selector) {
    return selector.startsWith(":scope") ? null : (this.querySelectorAll(selector)[0] ?? null);
  }
  addEventListener(type, listener, capture = false) {
    this.listeners.push({ type, listener, capture: capture === true || capture?.capture === true });
  }
  removeEventListener(type, listener) {
    this.listeners = this.listeners.filter(
      (each) => each.type !== type || each.listener !== listener,
    );
  }
  getBoundingClientRect() {
    return { left: 100, top: 100, right: 180, bottom: 120, width: 80, height: 20 };
  }
  get clientWidth() {
    return 0;
  }
  get scrollWidth() {
    return 0;
  }
  get clientHeight() {
    return 0;
  }
  get scrollHeight() {
    return 0;
  }
}

// ── The clock ──────────────────────────────────────────────────────

const settle = () => new Promise((resolve) => setImmediate(resolve));

function createClock() {
  let now = 0;
  let nextId = 1;
  const timers = new Map();
  return {
    get now() {
      return now;
    },
    setTimeout(callback, delay = 0) {
      const id = nextId++;
      timers.set(id, { at: now + Math.max(0, delay), callback });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    /** Run every timer due by *end*, settling promises after each, as the event loop does. */
    async to(end) {
      await settle();
      for (;;) {
        const due = [...timers.entries()]
          .filter(([, timer]) => timer.at <= end)
          .sort((left, right) => left[1].at - right[1].at || left[0] - right[0])[0];
        if (!due) {
          break;
        }
        timers.delete(due[0]);
        now = due[1].at;
        due[1].callback();
        await settle();
      }
      now = Math.max(now, end);
    },
  };
}

// ── A page ─────────────────────────────────────────────────────────

/** The GitHub identity of the page the sessions serve, unless they serve a plain folder. */
const GITHUB_REPOSITORY = Object.freeze({
  host: "github.com",
  owner: "octo",
  name: "demo",
  branch: "main",
  revision: "a".repeat(40),
  served_prefix: "",
});
const READ_MS = 40;

/**
 * What the served folder holds, each a file a link can open (`/api/file` serves every one),
 * and what of it the page's Quick File catalog lists. As the real catalog does, the stand-in
 * lists only a file the walker indexed and the catalog keeps: no symbolic link, since it
 * keeps an entry of type `file` alone, no gitignored file
 * (`_catalog_entry_filter` in inventory_engine/providers/python_inventory.py), and nothing
 * the walker hides, a dot-named file or anything under a dot-named folder (`is_visible` in
 * fs_paths.py). So a complete catalog is not every file a link can open.
 */
const SERVED_FILES = Object.freeze([
  Object.freeze({ path: "README.md" }),
  Object.freeze({ path: "docs/guide.md" }),
  Object.freeze({ path: ".github/CONTRIBUTING.md" }),
  Object.freeze({ path: "build/report.md", gitignored: true }),
  Object.freeze({ path: "alias.md", symlink: true }),
]);

/** Whether the page's Quick File catalog lists *file*, one of the served files. */
function catalogLists(file) {
  return (
    file.symlink !== true &&
    file.gitignored !== true &&
    !file.path.split("/").some((segment) => segment.startsWith("."))
  );
}

/** A card's lines as text: what a reader sees. */
function lines(html) {
  return html
    .split("</div>")
    .filter(Boolean)
    .map((line) =>
      line
        .replace(/<[^>]+>/g, "")
        .replaceAll("&lt;", "<")
        .replaceAll("&gt;", ">")
        .replaceAll("&quot;", '"')
        .replaceAll("&#39;", "'")
        .replaceAll("&amp;", "&"),
    )
    .join(" | ");
}

/**
 * A page: *repository* is its GitHub identity, or null for a plain folder's page; *cards*
 * says how the `link-previews` bundle loads, *loadMs* after the SDK asks, or not at all.
 *
 * @param {{repository?: object | null, cards?: {loadMs?: number, fails?: boolean}}} [options]
 */
function createPage(options = {}) {
  const repository = options.repository === undefined ? GITHUB_REPOSITORY : options.repository;
  const loadMs = options.cards?.loadMs ?? 0;
  const loadFails = options.cards?.fails === true;
  const clock = createClock();
  const log = [];
  const document = new FakeElement("html", "the page");
  document.isDocument = true;
  const body = new FakeElement("body", "the body");
  document.append(body);
  document.body = body;
  document.createElement = (tag) => new FakeElement(tag);

  // The catalog's snapshot of the served files, the tree's folder totals, and the reads a
  // provider makes.
  const listed = SERVED_FILES.filter(catalogLists).map((file) => file.path);
  /** @type {Map<string, {files: number, bytes: number}>} */
  const totals = new Map();
  const failing = new Set();
  let context = null;
  const sdk = {
    repository,
    sourceKind: () => "filesystem",
    navigation: {
      href: (target) => `/view/${target.path}`,
      open: async () => {},
      openRoute: () => true,
    },
    /** The asset loader, for the one bundle these pages ask for: the link card's. */
    ensureAsset(name) {
      log.push({ at: clock.now, load: name });
      assert(name === "link-previews", `the page asked for the ${name} bundle`);
      return new Promise((resolve, reject) =>
        clock.setTimeout(() => {
          if (loadFails) {
            log.push({ at: clock.now, loaded: name, failed: true });
            reject(new TypeError(`Failed to load the ${name} bundle`));
            return;
          }
          for (const script of LINK_PREVIEWS_BUNDLE) {
            const file = path.join(staticRoot, script);
            vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
          }
          log.push({ at: clock.now, loaded: name });
          resolve();
        }, loadMs),
      );
    },
    fetchPluginData(plugin, route, params = {}) {
      const query = new URLSearchParams(
        Object.entries(params).map(([name, value]) => [name, String(value)]),
      ).toString();
      const name = `${route}${query ? `?${query}` : ""}`;
      log.push({ at: clock.now, read: `${plugin}/${name}` });
      return new Promise((resolve, reject) =>
        clock.setTimeout(() => {
          if (failing.delete(name)) {
            reject(new TypeError(`Failed to fetch ${name}`));
            return;
          }
          const answer = recorded[name];
          if (answer === undefined) {
            reject(new Error(`no recorded answer for ${name}`));
            return;
          }
          resolve(answer.body);
        }, READ_MS),
      );
    },
    ensureKindAssets: async () => {},
    prefetchCounterpart() {},
    // Whole, as a served folder's is once its feed is in: a catalog still filling would
    // hide a reading that takes it for every file a link can open.
    fileCatalog: {
      snapshot: () => ({
        complete: true,
        truncated: false,
        files: [...listed].sort().map((file) => ({ path: file })),
        observedCount: listed.length,
        revision: 1,
        sourceSummary: {},
      }),
    },
    directoryTotals: {
      get(folder) {
        const known = totals.get(folder);
        return known === undefined
          ? null
          : {
              path: folder,
              revision: 1,
              state: "complete",
              totalFiles: known.files,
              totalBytes: known.bytes,
              unignoredFiles: known.files,
              unignoredBytes: known.bytes,
            };
      },
    },
    formatAge: () => ({ label: "" }),
    formatFileCount: (count) => `${count} files`,
    formatSize: (bytes) => `${bytes} B`,
    plugins: { load: () => new Promise(() => {}) },
    // What static/plugin-sdk-views.js reads of the SDK as it loads.
    registerView() {},
    delegateOwnerAttribute: "data-mb-delegate-owner",
    ownDelegate: (element) => element,
    escapeHtml: String,
  };

  context = {
    AbortController,
    URL,
    URLSearchParams,
    TextEncoder,
    TextDecoder,
    btoa,
    atob,
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout,
    requestAnimationFrame: (callback) => clock.setTimeout(callback, 16),
    performance: { now: () => clock.now },
    console: { warn: (message) => log.push({ at: clock.now, warned: String(message) }) },
    document,
    Element: FakeElement,
    HTMLElement: FakeElement,
    innerWidth: 1200,
    innerHeight: 800,
    metabrowser: sdk,
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(
    ["esc", "eventTargetElement", "isPageElement"].map(appFunction).join("\n") +
      tooltipSource +
      "\ninitTooltip();",
    context,
    { filename: "app.js (lifted)" },
  );
  // The shell's SDK draws a card on the shell's own tooltip (plugin-sdk.js, `tooltip`).
  sdk.tooltip = {
    show: (html, anchor) => context.MetabrowserTooltip.show(html, anchor),
    hide: (within) => context.MetabrowserTooltip.hide(within),
  };
  for (const name of [
    "formatters.js",
    "git-path.js",
    "repository-links.js",
    "plugin-sdk-views.js",
  ]) {
    const file = path.join(staticRoot, name);
    vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  }
  // Stand-ins for the view helpers' marks, which draw with a DOM these stand-ins lack.
  sdk.fileTypeIcon = () => ({ svg: "", className: "" });
  sdk.decorateExternalLink = (anchor) => anchor;
  const tooltip = body.childNodes.find((node) => node.classList?.contains("custom-tooltip"));
  assert(tooltip, "app.js drew no tooltip");

  /** A KPress host in the page, holding prose named *name*. */
  function prose(name) {
    const host = new FakeElement("div", "the KPress host", { class: "metabrowser-kpress-host" });
    const element = new FakeElement("div", name, { class: "kpress-prose" });
    host.append(element);
    body.append(host);
    return { host, prose: element };
  }

  /**
   * A pull request's text as its page draws one: a KPress host holding the inert prose, each
   * link, `[name, href, inner?]`, as the allowlist leaves it, then made what it opens by the
   * exact resolver, which registers each link for its card.
   */
  function text(...links) {
    const { host, prose: element } = prose("the description");
    const anchors = {};
    for (const [name, href, inner] of links) {
      const anchor = new FakeElement("a", name, {
        href,
        target: "_blank",
        rel: "noopener noreferrer",
      });
      anchor.append(...(inner ?? [`${name}`]));
      element.append(anchor, " ");
      anchors[name] = anchor;
    }
    context.MetabrowserRepositoryLinks.enhance(element, sdk);
    return { host, prose: element, anchors };
  }

  /**
   * A rendered Markdown document's links, each `{name, href, target, title?, newTab?}`,
   * registered through the SDK with what the Markdown enhancer says it opens, as it
   * registers them (builtin_plugins/markdown/link-enhancer.js, `previewLink`): its author's
   * title moves into the card when the SDK answers that the link has one.
   */
  function markdown(name, ...links) {
    const { host, prose: element } = prose(name);
    const anchors = {};
    for (const link of links) {
      const anchor = new FakeElement("a", link.name, {
        href: link.href,
        ...(link.title === undefined ? {} : { title: link.title }),
        ...(link.newTab ? { target: "_blank", rel: "noopener noreferrer" } : {}),
      });
      anchor.append(link.name);
      element.append(anchor, " ");
      anchors[link.name] = anchor;
      const authorTitle = anchor.getAttribute("title");
      const card = sdk.previewLink(element, anchor, link.target, { authorTitle });
      if (card) {
        anchor.removeAttribute("title");
      }
      log.push({ at: clock.now, registered: link.name, card });
    }
    return { host, prose: element, anchors };
  }

  /** Dispatch *type* at *target*: the document's capture listeners, then up from *target*. */
  function dispatch(target, type, init = {}) {
    const event = {
      type,
      target,
      relatedTarget: null,
      pointerType: "mouse",
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...init,
    };
    for (const { type: listened, listener, capture } of document.listeners) {
      if (listened === type && capture) {
        listener(event);
      }
    }
    if (type === "mouseenter" || type === "mouseleave") {
      return;
    }
    for (let at = target; at; at = at.parentNode) {
      for (const { type: listened, listener, capture } of at.listeners) {
        if (listened === type && !(capture && at === document)) {
          listener(event);
        }
      }
    }
  }

  const chain = (node) => {
    const nodes = [];
    for (let at = node; at && !at.isDocument; at = at.parentNode) {
      nodes.push(at);
    }
    return nodes;
  };
  // The pointer, which leaves what it was on before it arrives, in the browser's order.
  let under = body;
  async function point(time, element, pointerType = "mouse") {
    await clock.to(time);
    if (under === element) {
      return;
    }
    const left = chain(under).filter((node) => !node.contains(element));
    const entered = chain(element).filter((node) => !node.contains(under));
    dispatch(under, "pointerout", { relatedTarget: element, pointerType });
    for (const node of left) {
      dispatch(node, "mouseleave", { relatedTarget: element, pointerType });
    }
    dispatch(element, "pointerover", { relatedTarget: under, pointerType });
    for (const node of entered.reverse()) {
      dispatch(node, "mouseenter", { relatedTarget: under, pointerType });
    }
    log.push({
      at: clock.now,
      pointer: element.name,
      ...(pointerType === "mouse" ? {} : { pointerType }),
    });
    under = element;
  }
  /** Focus moves onto *element*, as a Tab or a click on it moves it. */
  async function focus(time, element) {
    await clock.to(time);
    log.push({ at: clock.now, focus: element.name });
    dispatch(element, "focusin");
  }
  /** The reader presses on what the pointer is on. */
  async function press(time) {
    await clock.to(time);
    log.push({ at: clock.now, press: under.name });
    dispatch(under, "pointerdown");
  }
  /**
   * What the reader sees now: the tooltip's lines, and the element whose markup they are,
   * which the tooltip was placed on (`tooltipShown` in app.js). The element the last show
   * named (`tooltipAnchor`) is not it: it is named before its markup is up, so it would name
   * the next link while the last link's card is still the one shown.
   */
  async function look(time) {
    await clock.to(time);
    const up = tooltip.style.display === "block" && tooltip.classList.contains("visible");
    const seen = up ? lines(tooltip.innerHTML) : null;
    log.push({ at: clock.now, sees: seen, ...(up ? { on: context.tooltipShown?.name } : {}) });
    return seen;
  }

  return {
    clock,
    log,
    body,
    sdk,
    prose,
    text,
    markdown,
    point,
    focus,
    press,
    look,
    /** The card's words for where a link opens, once its bundle has loaded. */
    opens: () => context.MetabrowserLinkPreviews.OPENS,
    loaded: () => context.MetabrowserLinkPreviews !== undefined,
    appearDelay: Number(appSource.match(/\nvar TOOLTIP_APPEAR_DELAY = (\d+);/)?.[1]),
    fail: (name) => failing.add(name),
    /** The tree totals *folder*, as its walk finishing there does. */
    total: (folder, known) => {
      totals.set(folder, known);
    },
  };
}

module.exports = {
  FakeElement,
  GITHUB_REPOSITORY,
  LINK_PREVIEWS_BUNDLE,
  SERVED_FILES,
  assert,
  catalogLists,
  createPage,
  lines,
  recorded,
};
