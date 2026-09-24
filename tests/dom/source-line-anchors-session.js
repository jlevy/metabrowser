// Browserless session for line anchors in source views.
//
// Loads the production navigation, source-append, source-line-anchors, and plugin SDK
// scripts into one context, attaches a real navigation controller over a fake location
// and history, and renders a source view through the SDK's renderSourceView into a
// small fake document. Then it takes the paths a reader takes: open a partly loaded
// file at #L60, Load more, click a line number, shift-click a range, edit the fragment,
// anchor columns, change the zoom, anchor past the end, clear the fragment, and reach an
// anchor through Load more's full re-render. Each step prints the address, the gutter,
// the highlighted lines, the measured line pitch, the notice, and any scroll.
//
// A fake layout gives each rendered line a rounded height that differs from the
// computed `1lh`, as a browser's layout does. The highlight is placed by the pitch the
// production code measures from the gutter, so a regression to `lh` arithmetic shows
// here as the wrong pitch.

const fs = require("node:fs");
const path = require("node:path");
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
    return { height: this.isConnected ? lines * renderedLinePx : 0 };
  }
  scrollIntoView(options) {
    const pre = this.closest("pre.metabrowser-source-lines");
    scrollLog.push({ line: Number(pre?.styleValues.get("--mb-line-first")), ...options });
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
// copy wrap, and the pre with its gutter and code. It reads only that markup's shape.
class FakeSourceHost extends FakeElement {
  set innerHTML(markup) {
    for (const node of [...this.childNodes]) {
      detach(node);
    }
    const source =
      /<pre class="([^"]+)"><span class="source-line-numbers" aria-hidden="true">([^<]*)<\/span><code class="([^"]+)">([^<]*)<\/code><\/pre>/.exec(
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
    const pre = wrap.appendChild(new FakeElement("pre", source[1]));
    const gutter = pre.appendChild(new FakeElement("span", "source-line-numbers"));
    if (source[2]) {
      gutter.appendChild(new FakeText(source[2]));
    }
    const code = pre.appendChild(new FakeElement("code", source[3]));
    code.appendChild(new FakeText(unescapeHtml(source[4])));
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
const controller = route.createController({
  // What app.js's applyNavigationTarget does for a file: open it when the path
  // changes, then deliver the target's fragment to whatever the pane shows.
  apply(target, context) {
    if (context.pathChanged) {
      host?.remove();
      host = new FakeSourceHost("div", "content-body");
      pane.appendChild(host);
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
  return {
    step,
    address: `${location.pathname}${location.search}${location.hash}`,
    gutter: numbers ? `1–${numbers.split("\n").length}` : "",
    highlighted: pre.classList.contains("has-line-anchor")
      ? `${pre.styleValues.get("--mb-line-first")}–${pre.styleValues.get("--mb-line-last")}`
      : null,
    scrollTarget: gutter.querySelector(".source-line-anchor-target") ? "present" : null,
    linePitch: pre.styleValues.get("--mb-line-pitch") ?? null,
    notice: notice ? { role: notice.getAttribute("role"), text: notice.textContent } : null,
    scrolls: scrollLog.splice(0),
  };
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

  const crlf = new FakeSourceHost("div", "content-body");
  pane.appendChild(crlf);
  sandbox.metabrowser.renderSourceView(crlf, { path: "crlf.txt", content: "one\r\ntwo\rthree\n" });
  const crlfPre = crlf.querySelector("pre.metabrowser-source-lines");
  const crlfLines = {
    gutter: crlfPre.querySelector(".source-line-numbers").firstChild.nodeValue,
    code: crlfPre.querySelector("code").textContent,
  };

  process.stdout.write(
    `${JSON.stringify({ grammar, lineCounts, describe, clicks, lineAt, steps, crlfLines, historyWrites }, null, 2)}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
