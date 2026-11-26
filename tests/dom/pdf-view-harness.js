// The page the PDF sessions run the production SDK, compositor, and PDF view in: a vm
// context with a small element tree that records what the view builds, the shell's
// scripts loaded whole in the order the shell loads them, the plugin's module loaded as
// the SDK imports it, and a mount that goes through the compositor's lifecycle as a file
// view does.
//
// The plugin's index.js is an ES module (it exports `mountPdfCard`), which a vm context
// evaluates only as a `vm.SourceTextModule`, behind `--experimental-vm-modules`. A
// session started without the flag is run again with it, so `node <session>` and the
// goldens that spell it stay the same.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

if (typeof vm.SourceTextModule !== "function") {
  const { spawnSync } = require("node:child_process");
  const again = spawnSync(
    process.execPath,
    [
      "--experimental-vm-modules",
      "--disable-warning=ExperimentalWarning",
      ...process.execArgv,
      ...process.argv.slice(1),
    ],
    { stdio: "inherit" },
  );
  process.exit(again.status ?? 1);
}

const repoRoot = path.resolve(__dirname, "../..");

/** The macOS app's descriptor, as its user script defines it (apps/macos OpenFileRequests). */
const APP_HOST = Object.freeze({ actions: Object.freeze(["open-file"]) });

/** The kind and view the server answers for a PDF, as `/api/file` names them. */
const PDF_VIEW = Object.freeze({
  id: "preview",
  label: "PDF",
  default: true,
  container_class: "content-body metabrowser-pdf-host",
  render_runtime: "client",
});

function createPage() {
  let innerHtmlWrites = 0;

  class FakeElement {
    constructor(tagName, ownerDocument) {
      this.tagName = String(tagName).toUpperCase();
      this.ownerDocument = ownerDocument;
      this.parentNode = null;
      this.children = [];
      this.attributes = new Map();
      this._innerHTML = "";
      this._text = "";
    }

    set innerHTML(value) {
      innerHtmlWrites += 1;
      this._innerHTML = String(value);
      this.replaceChildren();
    }

    get innerHTML() {
      return this._innerHTML;
    }

    set textContent(value) {
      this._text = String(value);
      this.replaceChildren();
    }

    get textContent() {
      return this._text + this.children.map((child) => child.textContent).join("");
    }

    setAttribute(name, value) {
      this.attributes.set(String(name), String(value));
    }

    getAttribute(name) {
      return this.attributes.get(String(name)) ?? null;
    }

    hasAttribute(name) {
      return this.attributes.has(String(name));
    }

    removeAttribute(name) {
      this.attributes.delete(String(name));
    }

    append(...children) {
      for (const child of children) {
        if (child.parentNode) {
          child.remove();
        }
        child.parentNode = this;
        this.children.push(child);
      }
    }

    replaceChildren(...children) {
      for (const child of this.children) {
        child.parentNode = null;
      }
      this.children = [];
      for (const child of children) {
        if (child.parentNode) {
          child.remove();
        }
        child.parentNode = this;
        this.children.push(child);
      }
    }

    remove() {
      if (!this.parentNode) {
        return;
      }
      const parent = this.parentNode;
      parent.children = parent.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }

  const document = {
    addEventListener() {},
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    documentElement: {},
  };
  document.createElement = (tagName) => new FakeElement(tagName, document);
  document.head = document.createElement("head");

  const sandbox = {
    console,
    document,
    encodeURIComponent,
    // A session that serves previews replaces it (`servePreviews`).
    fetch: () => Promise.reject(new Error("fetch is unavailable in the pdf session")),
    location: { origin: "http://127.0.0.1:8411" },
    Map,
    Promise,
    Set,
    TextDecoder,
    Uint8Array,
    URL,
    atob,
    btoa,
    clearInterval,
    clearTimeout,
    setInterval,
    setTimeout,
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);

  function runProduction(relative) {
    const absolute = path.join(repoRoot, relative);
    vm.runInContext(fs.readFileSync(absolute, "utf8"), sandbox, { filename: absolute });
  }

  /** @type {Map<string, vm.SourceTextModule>} */
  const modules = new Map();

  function moduleFor(absolute) {
    let module = modules.get(absolute);
    if (module === undefined) {
      module = new vm.SourceTextModule(fs.readFileSync(absolute, "utf8"), {
        context: sandbox,
        identifier: absolute,
      });
      modules.set(absolute, module);
    }
    return module;
  }

  /** Evaluate a production ES module in the page, once, and return its exports. */
  async function importProduction(relative) {
    const module = moduleFor(path.join(repoRoot, relative));
    if (module.status === "unlinked") {
      await module.link((specifier, referencing) =>
        moduleFor(path.resolve(path.dirname(referencing.identifier), specifier)),
      );
    }
    if (module.status === "linked") {
      await module.evaluate();
    }
    return module.namespace;
  }

  /**
   * Answer the page's requests from *answers*, by address, as the server recorded them:
   * the preview route's JSON. Every other address fails, as it would offline.
   *
   * @param {Record<string, unknown>} answers
   * @param {string[]} [requests] Each address asked, in order.
   */
  function servePreviews(answers, requests = []) {
    sandbox.fetch = (address) => {
      requests.push(String(address));
      if (!Object.hasOwn(answers, address)) {
        return Promise.reject(new Error(`no recorded answer for ${address}`));
      }
      const body = answers[address];
      return Promise.resolve({ ok: true, status: 200, json: async () => body });
    };
    return requests;
  }

  for (const relative of [
    "src/metabrowser/static/request-error.js",
    "src/metabrowser/static/formatters.js",
    "src/metabrowser/static/inventory-scope.js",
    "src/metabrowser/static/contribution-registry.js",
    "src/metabrowser/static/resource-context.js",
    "src/metabrowser/static/view-state.js",
    "src/metabrowser/static/git-path.js",
    "src/metabrowser/static/navigation.js",
    "src/metabrowser/static/plugin-sdk.js",
    "src/metabrowser/static/view-composition.js",
  ]) {
    runProduction(relative);
  }

  /**
   * The globals the shell writes into a page: the trust block of `METABROWSER_SETTINGS`,
   * the source kind, and the host's descriptor, which only the macOS app defines.
   */
  function serve({ capabilities, sourceKind, host }) {
    sandbox.METABROWSER_SETTINGS = capabilities === undefined ? {} : { CAPABILITIES: capabilities };
    if (sourceKind === undefined) {
      delete sandbox.METABROWSER_SOURCE_KIND;
    } else {
      sandbox.METABROWSER_SOURCE_KIND = sourceKind;
    }
    if (host) {
      sandbox.metabrowserHost = host;
    } else {
      delete sandbox.metabrowserHost;
    }
  }

  return {
    document,
    sandbox,
    runProduction,
    importProduction,
    servePreviews,
    serve,
    innerHtmlWrites: () => innerHtmlWrites,
  };
}

/** One element as a golden reads it: its tag, attributes in name order, and text. */
function describe(element) {
  const attributes = {};
  for (const name of Array.from(element.attributes.keys()).sort()) {
    attributes[name] = element.attributes.get(name);
  }
  const text = element.textContent;
  return { tag: element.tagName.toLowerCase(), attributes, ...(text ? { text } : {}) };
}

/**
 * The compositor, ready to mount the PDF view: the view's script loads with its kind's
 * assets, as the shell loads it, and the result says what that took.
 */
async function preparePdfView(page, views = [PDF_VIEW]) {
  const sdk = page.sandbox.metabrowser;
  const compositor = page.sandbox.MetabrowserViewComposition;
  const assetRequests = [];
  let loaded = false;
  const eagerlyRegistered = sdk.getRegisteredView("pdf", "preview") !== null;
  const prepared = await compositor.prepare({
    kind: "pdf",
    views,
    preferredViewId: views.find((view) => view.default)?.id ?? views[0]?.id,
    ensureKindAssets: async (kind) => {
      assetRequests.push(kind);
      if (!loaded) {
        await page.importProduction("src/metabrowser/builtin_plugins/pdf/index.js");
        loaded = true;
      }
    },
    getRegisteredView: sdk.getRegisteredView,
    isCurrent: () => true,
  });
  const renderer = prepared.views[0]?.renderer;
  const lifecycle = compositor.createLifecycle();
  const host = page.document.createElement("main");

  /** Mount the view on *filePath* in a fresh container, replacing the last one. */
  async function mount(filePath) {
    const container = page.document.createElement("section");
    const stage = lifecycle.begin();
    const status = await compositor.mount(
      container,
      renderer,
      { kind: "pdf", path: filePath },
      stage.disposers,
    );
    const committed = stage.commit(() => host.replaceChildren(container));
    return { container, committed, status };
  }

  return { assetRequests, eagerlyRegistered, prepared, renderer, lifecycle, host, mount };
}

module.exports = { APP_HOST, PDF_VIEW, createPage, describe, preparePdfView };
