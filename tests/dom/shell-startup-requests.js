// What the shell's startup scripts ask for before DOMContentLoaded has been handled.
//
//   node --experimental-vm-modules tests/dom/shell-startup-requests.js \
//     <shell.html> <pathname> [<landing>]
//
// devtools/check_startup_scripts.py counts the <script src> tags of the shell the
// server renders. A script can also ask for another one: through the asset loader, by
// appending a <script> or a preload <link>, or with import(). The performance gate
// counts such a request when it starts before DOMContentLoaded ends, and a reader of
// the HTML cannot see it. This runs the shell's own scripts, the production files and
// the inline blocks of the HTML it is given, in document order, then dispatches
// DOMContentLoaded and lets every promise chain that needs no response run. It prints
// what was asked for as JSON:
//
//   scripts       the script files it ran, as URL paths
//   requested     scripts asked for by a script, with how
//   fetches       the data requests the page started
//   alerts        text the page put in an element as an alert
//   errors        a script that threw, or one this cannot run
//   afterLanding  with <landing>: what history landing on that pathname asks for
//
// No response is delivered: a fetch stays pending, a requested script never loads, and
// no timer or idle callback fires, since a response, a timer and an idle period all
// come after DOMContentLoaded on a page whose scripts are the last thing in its body.
// So this sees what is asked for directly, not what a response would lead to, which is
// why the check refuses any such request instead of adding its size to the total.
//
// The document is a double: an element exists for each id in the HTML and for each
// createElement, answers the calls the startup code makes, and finds nothing through a
// selector. A call the double lacks throws, and the error says to add it here.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const [htmlPath, pathname, landing] = process.argv.slice(2);
if (!htmlPath || !pathname) {
  process.stderr.write("usage: shell-startup-requests.js <shell.html> <pathname> [<landing>]\n");
  process.exit(2);
}
const staticDir = path.resolve(__dirname, "../../src/metabrowser/static");
const html = fs.readFileSync(htmlPath, "utf8");

/** @type {Array<{how: string, url: string}>} */
const requested = [];
/** @type {string[]} */
const fetches = [];
/** @type {string[]} */
const errors = [];
const elements = [];

function urlPath(url) {
  return new URL(String(url), "http://shell.test").pathname;
}

function failure(where, error) {
  const text = error instanceof Error ? `${error.name}: ${error.message}` : String(error);
  errors.push(`${where}: ${text}`);
}

function makeStyle() {
  const style = { getPropertyValue: () => "", removeProperty() {}, setProperty() {} };
  return new Proxy(style, {
    get: (target, key) => (key in target ? target[key] : ""),
    set: () => true,
  });
}

function makeClassList() {
  const names = new Set();
  return {
    add(...added) {
      for (const name of added) {
        names.add(name);
      }
    },
    contains: (name) => names.has(name),
    remove(...removed) {
      for (const name of removed) {
        names.delete(name);
      }
    },
    toggle(name, force) {
      const on = force ?? !names.has(name);
      if (on) {
        names.add(name);
      } else {
        names.delete(name);
      }
      return on;
    },
  };
}

/** An element appended to the document: a script or a preload is a request. */
function appended(node) {
  if (!node || typeof node !== "object") {
    return node;
  }
  const rel = String(node.rel || node.getAttribute?.("rel") || "");
  if (node.tagName === "SCRIPT" && (node.src || node.getAttribute("src"))) {
    requested.push({ how: "script", url: urlPath(node.src || node.getAttribute("src")) });
  } else if (node.tagName === "LINK" && /preload/.test(rel)) {
    const as = String(node.as || node.getAttribute("as") || "");
    if (rel === "modulepreload" || as === "script") {
      requested.push({
        how: `link rel=${rel}`,
        url: urlPath(node.href || node.getAttribute("href")),
      });
    }
  }
  return node;
}

const ZERO_RECT = { bottom: 0, height: 0, left: 0, right: 0, top: 0, width: 0, x: 0, y: 0 };

function makeElement(tag, id = "") {
  const attributes = new Map();
  const element = {
    tagName: String(tag).toUpperCase(),
    nodeType: 1,
    id,
    children: [],
    childNodes: [],
    classList: makeClassList(),
    dataset: {},
    style: makeStyle(),
    hidden: false,
    innerHTML: "",
    textContent: "",
    value: "",
    isConnected: true,
    clientHeight: 0,
    clientWidth: 0,
    offsetHeight: 0,
    offsetParent: null,
    offsetWidth: 0,
    scrollHeight: 0,
    scrollLeft: 0,
    scrollTop: 0,
    firstChild: null,
    firstElementChild: null,
    lastElementChild: null,
    nextElementSibling: null,
    parentElement: null,
    parentNode: null,
    previousElementSibling: null,
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent: () => true,
    getAttribute: (name) => (attributes.has(name) ? attributes.get(name) : null),
    hasAttribute: (name) => attributes.has(name),
    removeAttribute: (name) => attributes.delete(name),
    setAttribute: (name, value) => attributes.set(name, String(value)),
    toggleAttribute() {},
    after() {},
    append: (...nodes) => nodes.forEach(appended),
    appendChild: appended,
    before() {},
    insertAdjacentElement: (_where, node) => appended(node),
    insertAdjacentHTML() {},
    insertBefore: appended,
    prepend: (...nodes) => nodes.forEach(appended),
    remove() {},
    removeChild() {},
    replaceChildren: (...nodes) => nodes.forEach(appended),
    replaceWith() {},
    closest: () => null,
    contains: () => false,
    matches: () => false,
    querySelector: () => null,
    querySelectorAll: () => [],
    getBoundingClientRect: () => ZERO_RECT,
    getClientRects: () => [],
    blur() {},
    click() {},
    cloneNode: () => makeElement(tag),
    focus() {},
    scrollIntoView() {},
    scrollTo() {},
  };
  elements.push(element);
  return element;
}

const idsInHtml = new Set(Array.from(html.matchAll(/\sid="([^"]+)"/g), (match) => match[1]));
const byId = new Map();
const documentListeners = new Map();
const windowListeners = new Map();

function listen(listeners) {
  return (type, listener) => listeners.set(type, [...(listeners.get(type) ?? []), listener]);
}

const document = {
  readyState: "loading",
  activeElement: null,
  cookie: "",
  hidden: false,
  title: "",
  visibilityState: "visible",
  body: makeElement("body"),
  documentElement: makeElement("html"),
  head: makeElement("head"),
  addEventListener: listen(documentListeners),
  removeEventListener() {},
  dispatchEvent: () => true,
  createDocumentFragment: () => makeElement("#document-fragment"),
  createElement: (tag) => makeElement(tag),
  createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
  elementFromPoint: () => null,
  getElementById(id) {
    if (!idsInHtml.has(id)) {
      return null;
    }
    if (!byId.has(id)) {
      byId.set(id, makeElement("div", id));
    }
    return byId.get(id);
  },
  getElementsByClassName: () => [],
  getElementsByTagName: () => [],
  querySelector: () => null,
  querySelectorAll: () => [],
};

function storage() {
  const values = new Map();
  return {
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

class Observer {
  disconnect() {}
  observe() {}
  takeRecords() {
    return [];
  }
  unobserve() {}
}

const sandbox = {
  document,
  console: { debug() {}, error() {}, info() {}, log() {}, warn() {} },
  location: {
    hash: "",
    host: "shell.test",
    href: `http://shell.test${pathname}`,
    origin: "http://shell.test",
    pathname,
    protocol: "http:",
    search: "",
  },
  history: { length: 1, pushState() {}, replaceState() {}, scrollRestoration: "auto", state: null },
  navigator: { clipboard: {}, language: "en", platform: "", userAgent: "" },
  localStorage: storage(),
  sessionStorage: storage(),
  addEventListener: listen(windowListeners),
  removeEventListener() {},
  dispatchEvent: () => true,
  fetch(url) {
    fetches.push(String(url));
    return new Promise(() => {});
  },
  EventSource: class {
    constructor(url) {
      fetches.push(String(url));
      this.readyState = 0;
    }
    addEventListener() {}
    close() {}
  },
  setTimeout: () => 0,
  clearTimeout() {},
  setInterval: () => 0,
  clearInterval() {},
  requestAnimationFrame: () => 0,
  cancelAnimationFrame() {},
  requestIdleCallback: () => 0,
  cancelIdleCallback() {},
  queueMicrotask,
  matchMedia: () => ({
    addEventListener() {},
    addListener() {},
    matches: false,
    removeEventListener() {},
    removeListener() {},
  }),
  getComputedStyle: () => makeStyle(),
  getSelection: () => null,
  IntersectionObserver: Observer,
  MutationObserver: Observer,
  PerformanceObserver: Observer,
  ResizeObserver: Observer,
  CustomEvent: class {
    constructor(type, init) {
      this.type = type;
      this.detail = init?.detail;
    }
  },
  Event: class {
    constructor(type) {
      this.type = type;
    }
  },
  performance: {
    getEntriesByName: () => [],
    getEntriesByType: () => [],
    mark() {},
    measure() {},
    now: () => 0,
    timeOrigin: 0,
  },
  crypto: globalThis.crypto,
  AbortController,
  AbortSignal,
  DOMException,
  Headers,
  Intl,
  Request,
  Response,
  TextDecoder,
  TextEncoder,
  URL,
  URLSearchParams,
  structuredClone,
  devicePixelRatio: 1,
  innerHeight: 900,
  innerWidth: 1280,
  scrollTo() {},
  scrollX: 0,
  scrollY: 0,
  Element: class {},
  HTMLElement: class {},
  Node: class {},
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.self = sandbox;
vm.createContext(sandbox);

function run(code, name) {
  try {
    vm.runInContext(code, sandbox, {
      filename: name,
      // import() of anything is a request too; this page makes none at startup.
      // Node calls this only under --experimental-vm-modules, and stops without it.
      importModuleDynamically(specifier) {
        requested.push({ how: "import()", url: urlPath(specifier) });
        return new Promise(() => {});
      },
    });
  } catch (error) {
    failure(name, error);
  }
}

// Classic scripts run where the parser meets them; deferred ones after it, in order.
const tags = Array.from(html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g), (match) => ({
  attributes: match[1],
  body: match[2],
}));
const immediate = tags.filter((tag) => !/\bdefer\b/.test(tag.attributes));
const deferred = tags.filter((tag) => /\bdefer\b/.test(tag.attributes));
/** @type {string[]} */
const scripts = [];
let inline = 0;
for (const tag of [...immediate, ...deferred]) {
  const source = /\bsrc="([^"]+)"/.exec(tag.attributes)?.[1];
  if (/\btype="module"/.test(tag.attributes)) {
    errors.push(`${source ?? "an inline script"}: a module script, which this cannot run`);
  } else if (!source) {
    inline += 1;
    run(tag.body, `inline script ${inline}`);
  } else if (!urlPath(source).startsWith("/static/")) {
    errors.push(`${source}: not under /static/, so there is no file to run`);
  } else {
    const name = urlPath(source);
    scripts.push(name);
    run(fs.readFileSync(path.join(staticDir, name.slice("/static/".length)), "utf8"), name);
  }
}

/** Let every promise chain that needs no response run. */
async function turns() {
  for (let round = 0; round < 20; round += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

async function main() {
  document.readyState = "interactive";
  const handlers = [
    ...(documentListeners.get("DOMContentLoaded") ?? []),
    ...(windowListeners.get("DOMContentLoaded") ?? []),
  ];
  for (const handler of handlers) {
    try {
      const result = handler({ type: "DOMContentLoaded" });
      result?.catch?.((error) => failure("a DOMContentLoaded handler", error));
    } catch (error) {
      failure("a DOMContentLoaded handler", error);
    }
  }
  await turns();
  const atStartup = requested.length;
  if (landing) {
    // Back or forward onto another address of this page: the URL moved, then popstate.
    sandbox.location.pathname = landing;
    for (const handler of windowListeners.get("popstate") ?? []) {
      try {
        handler({ state: null, type: "popstate" });
      } catch (error) {
        failure("a popstate handler", error);
      }
    }
    await turns();
  }
  const alerts = elements
    .filter((element) => /role="alert"/.test(String(element.innerHTML)))
    .map((element) =>
      String(element.innerHTML)
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim(),
    );
  const report = {
    scripts,
    requested: requested.slice(0, atStartup),
    fetches,
    alerts,
    errors,
    ...(landing ? { afterLanding: requested.slice(atStartup) } : {}),
  };
  process.stdout.write(`${JSON.stringify(report)}\n`);
}

main();
