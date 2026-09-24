// Browserless session for line anchors in source views.
//
// Loads the production navigation, source-append, source-line-anchors, and plugin SDK
// scripts into one context, attaches a real navigation controller over a fake location
// and history, and renders a source view through the SDK's renderSourceView into a
// small fake document. Then it takes the paths a reader takes: open a partly loaded
// file at #L60, Load more, click a line number, shift-click a range, edit the fragment,
// anchor columns, change the zoom, anchor past the end, clear the fragment, and reach an
// anchor through Load more's full re-render. Then the keyboard moves and extends the
// anchor on the focused gutter, a view mounted when its tab is first shown scrolls to the
// anchor while a staged one waits, and a Markdown file with front matter renders
// through the Markdown plugin's own Source renderer as two code blocks under one gutter.
// Each step prints the address, the gutter and its spoken value, the highlighted lines,
// the measured line pitch, the notice and the status line, and any scroll.
//
// A fake layout gives each rendered line a rounded height that differs from the
// computed `1lh`, as a browser's layout does. The highlight is placed by the pitch the
// production code measures from the gutter, so a regression to `lh` arithmetic shows
// here as the wrong pitch.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
// A 13px font at line-height 1.5 computes to 19.5px, but line boxes are laid out at
// 1/64 px; zoom changes the rounding again.
const LINE_HEIGHT_PX = 19.5;
let renderedLinePx = 19.53125;
const resizeObservers = [];

// ── A small fake document: just the element surface the production code uses ──

const scrollLog = [];

class FakeText {
  constructor(value) {
    this.nodeType = 3;
    this.nodeValue = value;
    this.parentNode = null;
  }
  get textContent() {
    return this.nodeValue;
  }
}

function detach(node) {
  const parent = node.parentNode;
  if (parent) {
    parent.childNodes.splice(parent.childNodes.indexOf(node), 1);
    node.parentNode = null;
  }
}

function matchesCompound(element, compound) {
  const [tag, ...classes] = compound.split(".");
  if (tag && element.tagName !== tag.toUpperCase()) {
    return false;
  }
  return classes.every((name) => element.classList.contains(name));
}

class FakeElement {
  constructor(tag, className = "") {
    this.nodeType = 1;
    this.tagName = tag.toUpperCase();
    this.className = className;
    this.childNodes = [];
    this.parentNode = null;
    this.connected = false;
    this.attributes = new Map();
    this.styleValues = new Map();
    this.listeners = new Map();
    const element = this;
    this.style = {
      setProperty(name, value) {
        element.styleValues.set(name, value);
      },
      removeProperty(name) {
        element.styleValues.delete(name);
      },
    };
    this.classList = {
      add(...names) {
        for (const name of names) {
          if (!element.classList.contains(name)) {
            element.className = `${element.className} ${name}`.trim();
          }
        }
      },
      remove(...names) {
        element.className = element.className
          .split(/\s+/)
          .filter((name) => name && !names.includes(name))
          .join(" ");
      },
      contains(name) {
        return element.className.split(/\s+/).includes(name);
      },
      toggle(name, force) {
        const on = force === undefined ? !element.classList.contains(name) : force;
        if (on) {
          element.classList.add(name);
        } else {
          element.classList.remove(name);
        }
        return on;
      },
    };
  }
  get ownerDocument() {
    return fakeDocument;
  }
  get firstChild() {
    return this.childNodes[0] ?? null;
  }
  get parentElement() {
    return this.parentNode;
  }
  get isConnected() {
    let node = this;
    while (node.parentNode) {
      node = node.parentNode;
    }
    return node.connected === true;
  }
  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }
  set textContent(value) {
    for (const node of [...this.childNodes]) {
      detach(node);
    }
    this.appendChild(new FakeText(String(value)));
  }
  appendChild(node) {
    detach(node);
    node.parentNode = this;
    this.childNodes.push(node);
    return node;
  }
  prepend(node) {
    detach(node);
    node.parentNode = this;
    this.childNodes.unshift(node);
  }
  before(node) {
    const parent = this.parentNode;
    detach(node);
    node.parentNode = parent;
    parent.childNodes.splice(parent.childNodes.indexOf(this), 0, node);
  }
  remove() {
    detach(this);
  }
  contains(node) {
    for (let current = node; current; current = current.parentNode) {
      if (current === this) {
        return true;
      }
    }
    return false;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  addEventListener(type, listener) {
    const entries = this.listeners.get(type) ?? [];
    entries.push(listener);
    this.listeners.set(type, entries);
  }
  dispatch(type, event) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ ...event, type, target: event.target ?? this, preventDefault() {} });
    }
  }
  matches(selector) {
    if (selector.startsWith("[") && selector.endsWith("]")) {
      return this.attributes.has(selector.slice(1, -1));
    }
    const parts = selector.split(/\s*>\s*/);
    if (!matchesCompound(this, parts[parts.length - 1])) {
      return false;
    }
    return (
      parts.length === 1 ||
      (this.parentNode?.nodeType === 1 && matchesCompound(this.parentNode, parts[0]))
    );
  }
  querySelector(selector) {
    for (const child of this.childNodes) {
      if (child.nodeType !== 1) {
        continue;
      }
      if (child.matches(selector)) {
        return child;
      }
      const found = child.querySelector(selector);
      if (found) {
        return found;
      }
    }
    return null;
  }
  closest(selector) {
    for (let current = this; current && current.nodeType === 1; current = current.parentNode) {
      if (current.matches(selector)) {
        return current;
      }
    }
    return null;
  }
  getClientRects() {
    return this.isConnected ? [{}] : [];
  }
  getBoundingClientRect() {
    // Only the gutter is measured: one text node of rendered line boxes.
    const lines =
      this.firstChild?.nodeType === 3 ? this.firstChild.nodeValue.split("\n").length : 0;
    return { top: 0, height: this.isConnected ? lines * renderedLinePx : 0 };
  }
  scrollIntoView(options) {
    const pre = this.closest("pre.metabrowser-source-lines");
    const line = pre?.styleValues.get("--mb-line-focus") ?? pre?.styleValues.get("--mb-line-first");
    scrollLog.push({ line: Number(line), ...options });
  }
}

function unescapeHtml(text) {
  return text
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&amp;", "&");
}

// A source host builds the element tree the SDK's markup describes: the notices, the
// copy wrap with its copy payload when the text is in several code blocks, and the pre
// with its gutter and code blocks. It reads only that markup's shape.
class FakeSourceHost extends FakeElement {
  set innerHTML(markup) {
    for (const node of [...this.childNodes]) {
      detach(node);
    }
    const source =
      /(<code data-mb-copy-payload class="no-highlight" hidden>[^<]*<\/code>)?<pre class="([^"]+)"><span class="source-line-numbers"([^>]*)>([^<]*)<\/span>((?:<code class="[^"]+">[^<]*<\/code>)+)<\/pre>/.exec(
        markup,
      );
    if (!source) {
      throw new Error(`unexpected source view markup: ${markup.slice(0, 200)}`);
    }
    if (markup.includes("metabrowser-source-truncation-warning")) {
      this.appendChild(
        new FakeElement("div", "notice partial-notice metabrowser-source-truncation-warning"),
      );
    }
    const wrap = this.appendChild(new FakeElement("div", "content-copy-wrap"));
    if (source[1]) {
      const payload = wrap.appendChild(new FakeElement("code", "no-highlight"));
      payload.setAttribute("data-mb-copy-payload", "");
    }
    const pre = wrap.appendChild(new FakeElement("pre", source[2]));
    const gutter = pre.appendChild(new FakeElement("span", "source-line-numbers"));
    for (const [, name, value] of source[3].matchAll(/ ([a-z-]+)="([^"]*)"/g)) {
      gutter.setAttribute(name, value);
    }
    if (source[4]) {
      gutter.appendChild(new FakeText(source[4]));
    }
    for (const [, className, text] of source[5].matchAll(
      /<code class="([^"]+)">([^<]*)<\/code>/g,
    )) {
      const code = pre.appendChild(new FakeElement("code", className));
      code.appendChild(new FakeText(unescapeHtml(text)));
    }
    if (markup.includes("metabrowser-source-more-footer")) {
      this.appendChild(
        new FakeElement("div", "notice partial-notice metabrowser-source-more-footer"),
      );
    }
  }
}

const pane = new FakeElement("main", "preview-pane");
pane.connected = true;

const fakeDocument = {
  activeElement: null,
  addEventListener() {},
  body: { append() {} },
  contains: (node) => pane.contains(node),
  cookie: "",
  createElement: (tag) => new FakeElement(tag),
  createTextNode: (value) => new FakeText(value),
  defaultView: null,
  documentElement: { getAttribute: () => null },
  head: { append() {} },
  querySelector: (selector) => pane.querySelector(selector),
};

// ── The production scripts, in the shell's order ──

const windowListeners = new Map();
class FakeCustomEvent {
  constructor(type, init) {
    this.type = type;
    this.detail = init?.detail;
  }
}
const sandbox = {
  AbortController,
  CustomEvent: FakeCustomEvent,
  DOMException,
  Map,
  Promise,
  Set,
  TextEncoder,
  URL,
  clearInterval,
  clearTimeout,
  console,
  document: fakeDocument,
  fetch: () => Promise.reject(new Error("fetch unavailable in the line-anchor session")),
  // Twenty rendered lines fit in the window, so a page is nineteen.
  innerHeight: 20.5 * renderedLinePx,
  ResizeObserver: class {
    constructor(callback) {
      this.callback = callback;
      this.targets = [];
      resizeObservers.push(this);
    }
    observe(target) {
      this.targets.push(target);
    }
    disconnect() {
      this.targets = [];
    }
  },
  location: { origin: "http://localhost" },
  METABROWSER_SETTINGS: {
    SYNTAX_HIGHLIGHT_MAX_BYTES: 512 * 1024,
    SYNTAX_LANGUAGE_BY_BASENAME: {},
    SYNTAX_LANGUAGE_BY_EXTENSION: {},
  },
  setInterval,
  setTimeout,
  addEventListener(type, listener) {
    const entries = windowListeners.get(type) ?? [];
    entries.push(listener);
    windowListeners.set(type, entries);
  },
  removeEventListener(type, listener) {
    windowListeners.set(
      type,
      (windowListeners.get(type) ?? []).filter((entry) => entry !== listener),
    );
  },
  dispatchEvent(event) {
    for (const listener of windowListeners.get(event.type) ?? []) {
      listener(event);
    }
    return true;
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
fakeDocument.defaultView = sandbox;
vm.createContext(sandbox);

for (const filename of [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "source-line-anchors.js",
  "plugin-sdk.js",
  "source-append.js",
]) {
  const filepath = path.join(repoRoot, "src/metabrowser/static", filename);
  vm.runInContext(fs.readFileSync(filepath, "utf8"), sandbox, { filename: filepath });
}

const anchors = sandbox.MetabrowserSourceLineAnchors;

// ── Decisions without a DOM ──

const grammar = Object.fromEntries(
  ["L10", "L10-L20", "L20-L10", "L10C5-L20C8", "L0", "L1-", "heading", "L1234567890"].map(
    (fragment) => [fragment, anchors.parse(fragment)],
  ),
);
const lineCounts = Object.fromEntries(
  [
    ["empty", ""],
    ["one line, no newline", "a"],
    ["one line, newline", "a\n"],
    ["blank last line", "a\n\n"],
    ["partial last line", "a\nb"],
  ].map(([label, text]) => [label, anchors.countLines(text)]),
);
const partLoaded = { lines: 40, truncated: true };
const wholeFile = { lines: 40, truncated: false };
const describe = {
  "L12 in the loaded part": anchors.describe("L12", partLoaded),
  "L30-L60 across the loaded edge": anchors.describe("L30-L60", partLoaded),
  "L60 not loaded yet": anchors.describe("L60", partLoaded),
  "L50-L55 not loaded yet": anchors.describe("L50-L55", partLoaded),
  "L30-L60 past the end": anchors.describe("L30-L60", wholeFile),
  "L60 past the end": anchors.describe("L60", wholeFile),
  "a heading fragment": anchors.describe("install", wholeFile),
};
const clicks = {
  "click 12": anchors.nextFragment("", 12, false),
  "shift-click 5 from L12": anchors.nextFragment("L12", 5, true),
  "shift-click 20 from L5-L12": anchors.nextFragment("L5-L12", 20, true),
  "shift-click 5 from L5": anchors.nextFragment("L5", 5, true),
  "shift-click 7 without an anchor": anchors.nextFragment("", 7, true),
  "click 7 over L5-L20": anchors.nextFragment("L5-L20", 7, false),
};
const layout = { lines: 100, page: 19, origin: 1 };
const keys = {
  "Down with nothing anchored": anchors.keyStep("", 0, "ArrowDown", false, layout),
  "Down with nothing anchored, line 30 first in view": anchors.keyStep("", 0, "ArrowDown", false, {
    ...layout,
    origin: 30,
  }),
  "Down from L10-L20": anchors.keyStep("L10-L20", 0, "ArrowDown", false, layout),
  "Up from L10-L20 moving its first line": anchors.keyStep("L10-L20", 10, "ArrowUp", false, layout),
  "Shift+Down from L10": anchors.keyStep("L10", 10, "ArrowDown", true, layout),
  "Shift+Up from L10-L11 moving its last line": anchors.keyStep(
    "L10-L11",
    11,
    "ArrowUp",
    true,
    layout,
  ),
  "Shift+Up from L10 across its fixed end": anchors.keyStep("L10", 10, "ArrowUp", true, layout),
  "Shift+Page Down from L90": anchors.keyStep("L90", 90, "PageDown", true, layout),
  "Page Up from L5": anchors.keyStep("L5", 5, "PageUp", false, layout),
  "Home from L50": anchors.keyStep("L50", 50, "Home", false, layout),
  "Shift+End from L50": anchors.keyStep("L50", 50, "End", true, layout),
  "a letter": anchors.keyStep("L50", 50, "j", false, layout),
  "an empty file": anchors.keyStep("", 0, "ArrowDown", false, { ...layout, lines: 0 }),
};
const spoken = {
  "L12 shown": anchors.spoken(anchors.describe("L12", wholeFile)),
  "L30-L60 partial": anchors.spoken(anchors.describe("L30-L60", partLoaded)),
  "L1000-L2000 shown": anchors.spoken(
    anchors.describe("L1000-L2000", { lines: 5000, truncated: false }),
  ),
  "L60 not loaded": anchors.spoken(anchors.describe("L60", partLoaded)),
  "no anchor": anchors.spoken(anchors.describe("", wholeFile)),
};
const preferredView = Object.fromEntries(
  [
    ["README.md#L3-L4", { path: "README.md", fragment: "L3-L4" }],
    ["README.md?plain=1", { path: "README.md", query: "plain=1" }],
    ["README.md?utm_source=chat&plain=1", { path: "README.md", query: "utm_source=chat&plain=1" }],
    ["README.md?plain=10", { path: "README.md", query: "plain=10" }],
    ["README.md#install", { path: "README.md", fragment: "install" }],
    ["README.md", { path: "README.md" }],
  ].map(([label, target]) => [label, anchors.preferredView(target)]),
);
const lineAt = {
  "top of line 1": anchors.lineAt(0, LINE_HEIGHT_PX, 40),
  "middle of line 3": anchors.lineAt(2.5 * LINE_HEIGHT_PX, LINE_HEIGHT_PX, 40),
  "below the last line": anchors.lineAt(90 * LINE_HEIGHT_PX, LINE_HEIGHT_PX, 40),
  "no line height": anchors.lineAt(10, Number.NaN, 40),
};

// ── A reader's session through the real navigation controller ──

const numbered = (first, last) => {
  let text = "";
  for (let line = first; line <= last; line++) {
    text += `line ${line}\n`;
  }
  return text;
};
const firstPart = numbered(1, 40);
const rest = numbered(41, 100);
const totalBytes = Buffer.byteLength(firstPart + rest);
const route = sandbox.MetabrowserNavigationRoute;
const location = { pathname: "/view/src/app.py", search: "", hash: "#L60" };
const historyWrites = [];
function writeHistory(kind, href) {
  const url = new URL(href, "http://localhost");
  location.pathname = url.pathname;
  location.search = url.search;
  location.hash = url.hash;
  historyWrites.push(`${kind} ${href}`);
}
// Line anchors only ever replace the entry; opening another file pushes one.
const history = {
  replaceState(_state, _title, href) {
    writeHistory("replace", href);
  },
  pushState(_state, _title, href) {
    writeHistory("push", href);
  },
};

let host = null;
const fullContent = () => ({
  path: "src/big.py",
  ext: ".py",
  size: totalBytes,
  bytes_read: totalBytes,
  content: firstPart + rest,
  content_bytes: totalBytes,
  content_truncated: false,
});
const markdownText = "---\r\ntitle: Guide\r\n---\r\n# Guide\r\n\r\nText.\r\n";
let markdown = null;
const controller = route.createController({
  // What app.js's applyNavigationTarget does for a file: open it when the path
  // changes, rendering into an inert stage whose view then moves into the pane, and
  // then deliver the target's fragment to whatever the pane shows. A Markdown file
  // opens in its Source view, because every address here anchors lines.
  apply(target, context) {
    if (context.pathChanged) {
      host?.remove();
      const stage = pane.appendChild(new FakeElement("div", "preview-file-stage"));
      stage.setAttribute("inert", "");
      host = stage.appendChild(new FakeSourceHost("div", "content-body"));
      if (target.path.endsWith(".md")) {
        markdown.renderMarkdownSource(
          host,
          { raw: { path: target.path, ext: ".md", content: markdownText } },
          sandbox.metabrowser,
        );
      } else {
        sandbox.metabrowser.renderSourceView(host, {
          path: target.path,
          ext: ".py",
          size: totalBytes,
          bytes_read: Buffer.byteLength(firstPart),
          content: firstPart,
          content_bytes: Buffer.byteLength(firstPart),
          content_truncated: true,
        });
      }
      pane.appendChild(host);
      stage.remove();
    }
    sandbox.dispatchEvent(
      new FakeCustomEvent("metabrowser:navigation-fragment", {
        detail: { target: controller.current() || target },
      }),
    );
    return { status: "opened" };
  },
  eventTarget: sandbox,
  history,
  location,
});
route.attachController(controller);

const settle = () => new Promise((resolve) => setImmediate(resolve));

function snapshot(step) {
  const pre = host.querySelector("pre.metabrowser-source-lines");
  const gutter = pre.querySelector(".source-line-numbers");
  const numbers = gutter.firstChild?.nodeType === 3 ? gutter.firstChild.nodeValue : "";
  const notice = host.querySelector("div.metabrowser-source-anchor-notice");
  const status = host.querySelector("span.metabrowser-source-anchor-status");
  return {
    step,
    address: `${location.pathname}${location.search}${location.hash}`,
    gutter: numbers ? `1–${numbers.split("\n").length}` : "",
    value: `${gutter.getAttribute("aria-valuenow")} of ${gutter.getAttribute("aria-valuemax")}: ${gutter.getAttribute("aria-valuetext")}`,
    status: status.textContent,
    highlighted: pre.classList.contains("has-line-anchor")
      ? `${pre.styleValues.get("--mb-line-first")}–${pre.styleValues.get("--mb-line-last")}`
      : null,
    scrollTarget: gutter.querySelector(".source-line-anchor-target") ? "present" : null,
    linePitch: pre.styleValues.get("--mb-line-pitch") ?? null,
    notice: notice ? { role: notice.getAttribute("role"), text: notice.textContent } : null,
    scrolls: scrollLog.splice(0),
  };
}

function press(key, modifiers = {}) {
  const gutter = host.querySelector(".source-line-numbers");
  let prevented = false;
  for (const listener of gutter.listeners.get("keydown") ?? []) {
    listener({
      key,
      shiftKey: false,
      altKey: false,
      ctrlKey: false,
      metaKey: false,
      ...modifiers,
      preventDefault() {
        prevented = true;
      },
    });
  }
  return prevented;
}

function clickLine(line, shiftKey) {
  const gutter = host.querySelector(".source-line-numbers");
  gutter.dispatch("mousedown", { button: 0, shiftKey });
  gutter.dispatch("click", { button: 0, offsetY: (line - 0.5) * renderedLinePx, shiftKey });
}

async function popTo(hash) {
  location.hash = hash;
  sandbox.dispatchEvent(new FakeCustomEvent("popstate"));
  await settle();
}

async function main() {
  markdown = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/source.js")).href
  );
  const steps = [];
  await controller.start();
  await settle();
  steps.push(snapshot("open #L60 with lines 1–40 loaded"));

  const cached = { content: firstPart, content_truncated: true };
  const appended = sandbox.MetabrowserSourceAppend.appendSourceText(fakeDocument, rest);
  const nextCached = sandbox.MetabrowserSourceAppend.nextCacheValue(cached, {
    content: rest,
    content_truncated: false,
  });
  anchors.refresh(fakeDocument, nextCached);
  steps.push({ ...snapshot("Load more reaches line 60"), appended });

  clickLine(3, false);
  await settle();
  steps.push(snapshot("click line 3"));

  clickLine(9, true);
  await settle();
  steps.push(snapshot("shift-click line 9"));

  clickLine(1, true);
  await settle();
  steps.push(snapshot("shift-click line 1"));

  await popTo("#L20-L10");
  steps.push(snapshot("the reader edits the fragment to a reversed range"));

  await popTo("#L5C3-L7C9");
  steps.push(snapshot("a column anchor"));

  renderedLinePx = 21.484375;
  for (const observer of resizeObservers) {
    if (observer.targets.some((target) => target.isConnected)) {
      observer.callback([]);
    }
  }
  steps.push(snapshot("the zoom changes the rendered line height"));
  clickLine(90, false);
  await settle();
  steps.push(snapshot("click line 90 at the new zoom"));

  await popTo("#L150");
  steps.push(snapshot("a line past the end"));

  sandbox.dispatchEvent(
    new FakeCustomEvent("metabrowser:navigation-fragment", {
      detail: { target: { path: "src/other.py", fragment: "L2" } },
    }),
  );
  steps.push(snapshot("another file's fragment"));

  await popTo("");
  steps.push(snapshot("the fragment is removed"));

  // Load more renders a syntax-highlighted view again rather than appending to it;
  // app.js then refreshes the anchors, which scroll to the anchor it has just reached.
  await controller.open({ path: "src/big.py", fragment: "L70" });
  await settle();
  steps.push(snapshot("open another file at #L70 with lines 1–40 loaded"));
  const reloaded = new FakeSourceHost("div", "content-body");
  host.before(reloaded);
  host.remove();
  host = reloaded;
  sandbox.metabrowser.renderSourceView(host, fullContent());
  steps.push(snapshot("Load more renders the view again"));
  anchors.refresh(fakeDocument, { content_truncated: false });
  steps.push(snapshot("the refresh after that render"));

  // The keyboard: Tab reaches the gutter, and keys move and extend the anchor. The
  // focused gutter's own value is what a screen reader announces, so the status line
  // keeps its last words until the anchor changes some other way.
  const gutter = host.querySelector(".source-line-numbers");
  steps.push({
    ...snapshot("Tab reaches the gutter"),
    role: gutter.getAttribute("role"),
    tabindex: gutter.getAttribute("tabindex"),
    label: gutter.getAttribute("aria-label"),
    orientation: gutter.getAttribute("aria-orientation"),
  });
  fakeDocument.activeElement = gutter;
  for (const [label, key, modifiers] of [
    ["Down", "ArrowDown", {}],
    ["Shift+Down", "ArrowDown", { shiftKey: true }],
    ["Shift+Up", "ArrowUp", { shiftKey: true }],
    ["Shift+Up again", "ArrowUp", { shiftKey: true }],
    ["Shift+Up across the fixed end", "ArrowUp", { shiftKey: true }],
    ["Page Down", "PageDown", {}],
    ["End", "End", {}],
    ["Home", "Home", {}],
    ["Shift+End", "End", { shiftKey: true }],
    ["Ctrl+Down, left to the browser", "ArrowDown", { ctrlKey: true }],
    ["J, not a gutter key", "j", {}],
  ]) {
    const prevented = press(key, modifiers);
    await settle();
    steps.push({ ...snapshot(label), prevented });
  }
  fakeDocument.activeElement = null;
  await popTo("#L5");
  steps.push(snapshot("focus leaves, and the reader edits the fragment"));

  // A view the shell renders into its inert stage waits for the fragment event; a view
  // mounted when its tab is first shown is already in the pane and scrolls at once.
  const stage = pane.appendChild(new FakeElement("div", "preview-file-stage"));
  stage.setAttribute("inert", "");
  const shownHost = host;
  host = stage.appendChild(new FakeSourceHost("div", "content-body"));
  sandbox.metabrowser.renderSourceView(host, fullContent());
  steps.push(snapshot("a view rendered into the inert stage"));
  stage.remove();
  host = pane.appendChild(new FakeSourceHost("div", "content-body"));
  sandbox.metabrowser.renderSourceView(host, fullContent());
  steps.push(snapshot("a Source tab shown for the first time"));
  host.remove();
  host = shownHost;

  // A Markdown file with front matter, through the Markdown plugin's Source renderer:
  // YAML and Markdown blocks under one gutter, each block's band offset by the lines
  // above it, and one copy payload for the whole text.
  await controller.open({ path: "docs/guide.md", fragment: "L4-L5" });
  await settle();
  const markdownPre = host.querySelector("pre.metabrowser-source-lines");
  const markdownParts = markdownPre.childNodes
    .filter((node) => node.tagName === "CODE")
    .map((code) => ({
      className: code.className,
      text: code.textContent,
      lineOffset: code.styleValues.get("--mb-line-offset") ?? null,
    }));
  steps.push({
    ...snapshot("a Markdown file with front matter at #L4-L5"),
    parts: markdownPre.styleValues.get("--mb-source-parts") ?? null,
    markdownParts,
    copyPayload: host.querySelector("code.no-highlight")?.getAttribute("data-mb-copy-payload"),
  });
  host.remove();
  host = pane.appendChild(new FakeSourceHost("div", "content-body"));
  markdown.renderMarkdownSource(
    host,
    { raw: { path: "docs/guide.md", ext: ".md", content: "---\nunclosed: true\n# Guide\n" } },
    sandbox.metabrowser,
  );
  steps.push({
    ...snapshot("a Markdown file whose front matter never closes"),
    markdownParts: host
      .querySelector("pre.metabrowser-source-lines")
      .childNodes.filter((node) => node.tagName === "CODE")
      .map((code) => code.className),
  });

  const crlf = new FakeSourceHost("div", "content-body");
  pane.appendChild(crlf);
  sandbox.metabrowser.renderSourceView(crlf, { path: "crlf.txt", content: "one\r\ntwo\rthree\n" });
  const crlfPre = crlf.querySelector("pre.metabrowser-source-lines");
  const crlfLines = {
    gutter: crlfPre.querySelector(".source-line-numbers").firstChild.nodeValue,
    code: crlfPre.querySelector("code").textContent,
  };

  process.stdout.write(
    `${JSON.stringify({ grammar, lineCounts, describe, clicks, keys, spoken, preferredView, lineAt, steps, crlfLines, historyWrites }, null, 2)}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
