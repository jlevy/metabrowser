// Browserless session: the SDK's view helpers are there wherever a plugin's code runs.
//
// plugin-sdk-views.js -- renderSourceView and the other helpers that build a view's
// markup, with the line gutter they draw -- is an on-demand bundle, not a startup
// script. The shell fetches it beside the view compositor. A plugin loaded where no
// compositor ran, as the commit page loads the diff plugin and the pull-request page
// loads its own, must still find every helper: while its module evaluates, in a view's
// render, and in a handler.
//
// This loads the production asset loader and plugin SDK into one context and loads a
// third-party plugin through `ensureKindAssets`, with no compositor. The document is a
// double in which every element appended to <head> is a request the session answers
// when it chooses, so the steps show what is requested together, what waits for what,
// and what the page is left with when the bundle cannot be fetched.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const fixtureUrl = pathToFileURL(path.join(__dirname, "fixtures/view-helper-plugin.mjs")).href;

// The plugin's module is imported by Node's own loader, which is what `import()` in a
// vm script needs without a flag. Node calls that experimental on every use; the
// warning carries a process id, so it is kept out of the transcript.
const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("USE_MAIN_CONTEXT_DEFAULT_LOADER")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

const HELPERS = [
  "decorateExternalLink",
  "refChipHtml",
  "refChip",
  "mountRefCopies",
  "ageBucket",
  "ageLabelHtml",
  "highlightSyntax",
  "isLargeTextPreview",
  "langForExtension",
  "langForPath",
  "partialNoticeHtml",
  "renderSourceView",
  "renderTextLoadMoreFooter",
  "renderTextTruncationWarning",
  "wrapWithCopy",
];

/** Let every promise chain that needs no response run. */
async function turn() {
  for (let round = 0; round < 10; round += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

let pages = 0;

/** A page with the shell's startup scripts that a plugin's loading needs, and no view. */
function createPage() {
  pages += 1;
  /** @type {Array<{element: any, name: string}>} */
  const waiting = [];
  /** @type {string[]} */
  const requested = [];
  const fixtureLog = [];
  const templateLog = [];
  const pluginErrors = [];

  function describe(element) {
    const url = element.src || element.getAttribute("src") || element.getAttribute("href") || "";
    const name = url.startsWith("file:") ? "<the plugin's module>" : url;
    const rel = element.getAttribute("rel");
    return `${element.tagName.toLowerCase()}${rel ? ` rel=${rel}` : ""} ${name}`;
  }

  function createElement(tag) {
    const attributes = new Map();
    const listeners = new Map();
    const classes = new Set();
    return {
      tagName: String(tag).toUpperCase(),
      innerHTML: "",
      classList: { add: (name) => classes.add(name) },
      addEventListener(type, listener) {
        listeners.set(type, [...(listeners.get(type) ?? []), listener]);
      },
      fire(type) {
        this[`on${type}`]?.();
        for (const listener of listeners.get(type) ?? []) {
          listener({ type });
        }
      },
      getAttribute: (name) => (attributes.has(name) ? attributes.get(name) : null),
      querySelector: () => null,
      remove() {},
      setAttribute: (name, value) => attributes.set(name, String(value)),
    };
  }

  function request(element) {
    const name = describe(element);
    requested.push(name);
    // A preload is only a fetch: nothing on the page waits for its answer.
    if (!["modulepreload", "preload"].includes(element.getAttribute("rel"))) {
      waiting.push({ element, name });
    }
  }

  const windowListeners = new Map();
  const sandbox = {
    AbortController,
    CustomEvent: class {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    DOMException,
    Map,
    Promise,
    Set,
    TextEncoder,
    URL,
    clearInterval,
    clearTimeout,
    console: {
      error(...args) {
        pluginErrors.push(args.map((arg) => arg?.message || String(arg)).join(" "));
      },
      warn() {},
    },
    fetch: () => Promise.reject(new Error("no request is part of this session")),
    location: { origin: "http://localhost" },
    METABROWSER_ASSET_BUNDLES: {
      mustache: [{ src: "/static/vendor/mustache.min.js", provides: "Mustache" }],
      "sdk-views": [
        { src: "/static/plugin-sdk-views.js", provides: "MetabrowserSourceLineAnchors" },
      ],
    },
    METABROWSER_SETTINGS: {
      SYNTAX_HIGHLIGHT_MAX_BYTES: 512 * 1024,
      SYNTAX_LANGUAGE_BY_BASENAME: {},
      SYNTAX_LANGUAGE_BY_EXTENSION: { ".py": "python" },
    },
    setInterval,
    setTimeout,
    addEventListener(type, listener) {
      windowListeners.set(type, [...(windowListeners.get(type) ?? []), listener]);
    },
    removeEventListener() {},
    dispatchEvent(event) {
      for (const listener of windowListeners.get(event.type) ?? []) {
        listener(event);
      }
      return true;
    },
    document: {
      addEventListener() {},
      body: { append() {} },
      cookie: "",
      createElement,
      documentElement: { getAttribute: () => null },
      head: { append: request, appendChild: request },
    },
    viewHelperFixtureLog: fixtureLog,
    viewHelperTemplateLog: templateLog,
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  // The plugin's module runs in Node's own realm and reaches the page through `window`.
  globalThis.window = sandbox;

  function load(filename) {
    const filepath = path.join(staticDir, filename);
    vm.runInContext(fs.readFileSync(filepath, "utf8"), sandbox, {
      filename: filepath,
      importModuleDynamically: vm.constants.USE_MAIN_CONTEXT_DEFAULT_LOADER,
    });
  }
  for (const filename of [
    "asset-loader.js",
    "request-error.js",
    "formatters.js",
    "inventory-scope.js",
    "resource-context.js",
    "view-state.js",
    "navigation.js",
    "plugin-sdk.js",
  ]) {
    load(filename);
  }

  return {
    fixtureLog,
    templateLog,
    pluginErrors,
    requested,
    sandbox,
    /** One plugin for *kind*: a stylesheet and the fixture's module. */
    configure(kind) {
      sandbox.MetabrowserPluginHost.configureAssets({
        [kind]: [
          {
            module: `${fixtureUrl}?page=${pages}&kind=${kind}`,
            name: `${kind}-plugin`,
            scripts: [],
            styles: [`/plugin-static/${kind}/styles.css`],
          },
        ],
      });
    },
    /** How many of the documented view helpers the SDK object has. */
    helpers() {
      const present = HELPERS.filter((name) => typeof sandbox.metabrowser[name] === "function");
      return `${present.length} of ${HELPERS.length}`;
    },
    /** Answer what the page is waiting for; a name in *failing* gets an error. */
    answer(failing = [], held = []) {
      for (const { element, name } of waiting.splice(0)) {
        if (held.some((part) => name.includes(part))) {
          waiting.push({ element, name });
          continue;
        }
        if (failing.some((part) => name.includes(part))) {
          element.fire("error");
          continue;
        }
        const url = element.src || element.getAttribute("src") || "";
        if (url.startsWith("/static/")) {
          load(url.slice("/static/".length));
        }
        element.fire("load");
      }
    },
  };
}

/** A promise's fate without waiting for it. */
function fate(promise) {
  const state = { settled: "pending" };
  promise.then(
    () => {
      state.settled = "resolved";
    },
    (error) => {
      state.settled = `rejected: ${error.message}`;
    },
  );
  return state;
}

async function withoutACompositor() {
  // The commit page and the pull-request page load a plugin with no compositor.
  const page = createPage();
  page.configure("fixture-kind");
  const before = page.helpers();
  const loading = fate(page.sandbox.metabrowser.ensureKindAssets("fixture-kind"));
  await turn();
  const requestedTogether = [...page.requested];
  const whileWaiting = { loading: loading.settled, pluginCode: [...page.fixtureLog] };
  page.answer();
  await turn();
  const loaded = { loading: loading.settled, pluginCode: [...page.fixtureLog] };

  const view = page.sandbox.metabrowser.getRegisteredView("fixture-kind", "fixture");
  if (!view) {
    throw new Error(`plugin did not register: ${page.pluginErrors.join("; ")}`);
  }
  const container = page.sandbox.document.createElement("div");
  view.render(container, { kind: "fixture-kind" });
  container.fire("click");

  // A second plugin on the same page: the helpers are there, so nothing asks again.
  const alreadyRequested = page.requested.length;
  page.configure("another-kind");
  const second = fate(page.sandbox.metabrowser.ensureKindAssets("another-kind"));
  await turn();
  const secondRequests = page.requested.slice(alreadyRequested);
  page.answer();
  await turn();

  return {
    helpersBefore: before,
    requestedTogether,
    whileWaiting,
    loaded,
    helpersAfter: page.helpers(),
    pluginCode: page.fixtureLog,
    templateCalls: page.templateLog,
    aSecondPlugin: { requested: secondRequests, loading: second.settled },
  };
}

async function whenTheHelpersCannotBeFetched() {
  // No plugin's code runs without the helpers, the caller is told, and asking again
  // fetches what failed without fetching the rest twice.
  const page = createPage();
  page.configure("fixture-kind");
  const failed = fate(page.sandbox.metabrowser.ensureKindAssets("fixture-kind"));
  await turn();
  page.answer(["plugin-sdk-views.js"]);
  await turn();
  const afterFailure = {
    loading: failed.settled,
    pluginCode: [...page.fixtureLog],
    viewRegistered: !!page.sandbox.metabrowser.getRegisteredView("fixture-kind", "fixture"),
  };
  const alreadyRequested = page.requested.length;
  const retried = fate(page.sandbox.metabrowser.ensureKindAssets("fixture-kind"));
  await turn();
  const retryRequests = page.requested.slice(alreadyRequested);
  page.answer();
  await turn();
  return {
    afterFailure,
    retry: { requested: retryRequests, loading: retried.settled, pluginCode: page.fixtureLog },
  };
}

// Idle prefetch and a direct kind request share one template load. Holding its
// response must hold plugin evaluation, even after the other helpers are ready.
async function whenTemplatesCannotBeFetched() {
  const page = createPage();
  page.configure("fixture-kind");
  const prefetch = fate(page.sandbox.MetabrowserAssets.ensureAsset("mustache"));
  const loading = fate(page.sandbox.metabrowser.ensureKindAssets("fixture-kind"));
  await turn();
  page.answer([], ["mustache.min.js"]);
  await turn();
  const whileHeld = {
    loading: loading.settled,
    helpers: page.helpers(),
    templateRequests: page.requested.filter(
      (name) => name === "script /static/vendor/mustache.min.js",
    ).length,
    pluginCode: [...page.fixtureLog],
  };
  page.answer(["mustache.min.js"]);
  await turn();
  const afterFailure = {
    loading: loading.settled,
    prefetch: prefetch.settled,
    pluginCode: [...page.fixtureLog],
    viewRegistered: !!page.sandbox.metabrowser.getRegisteredView("fixture-kind", "fixture"),
  };
  const alreadyRequested = page.requested.length;
  const retried = fate(page.sandbox.metabrowser.ensureKindAssets("fixture-kind"));
  await turn();
  const retryRequests = page.requested.slice(alreadyRequested);
  page.answer();
  await turn();
  return {
    whileHeld,
    afterFailure,
    retry: {
      requested: retryRequests,
      loading: retried.settled,
      pluginCode: page.fixtureLog,
      templateCalls: page.templateLog,
    },
  };
}

// The exact shell boundary, with only its platform/asset promises controlled. The
// renderer itself must not run until both already-defined on-demand bundles are ready.
async function sourceHeaderReadiness() {
  const app = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");
  const begin = app.indexOf("async function startSourceRefSelector() {");
  const end = app.indexOf("// app.js is the last core script", begin);
  if (begin < 0 || end < 0) {
    throw new Error("source header boundary moved");
  }
  function header(managed) {
    const requested = [],
      jobs = new Map(),
      mounted = [];
    let helpersReady = false;
    const element = {};
    const context = {
      Promise,
      isGitRevisionSource: () => managed,
      document: { getElementById: () => element },
      window: {
        MetabrowserAssets: {
          ensureAsset(name) {
            requested.push(name);
            return new Promise((resolve, reject) =>
              jobs.set(name, {
                resolve() {
                  if (name === "sdk-views") {
                    helpersReady = true;
                  }
                  resolve();
                },
                reject,
              }),
            );
          },
        },
        MetabrowserSourceRefSelector: {
          mount(target) {
            if (!helpersReady || target !== element) {
              throw new Error("header mounted before its helpers");
            }
            mounted.push("source header");
          },
        },
      },
    };
    vm.createContext(context);
    vm.runInContext(app.slice(begin, end), context, { filename: "app.js:startSourceRefSelector" });
    return { requested, jobs, mounted, start: () => fate(context.startSourceRefSelector()) };
  }
  const folder = header(false),
    folderLoad = folder.start();
  await turn();
  const managed = header(true),
    loading = managed.start();
  const requestedTogether = [...managed.requested];
  managed.jobs.get("source-ref-selector").resolve();
  await turn();
  const afterSelector = { loading: loading.settled, mounted: [...managed.mounted] };
  managed.jobs.get("sdk-views").resolve();
  await turn();
  const failed = header(true),
    failure = failed.start();
  failed.jobs.get("sdk-views").reject(new Error("helpers unavailable"));
  await turn();
  const afterFailure = { loading: failure.settled, mounted: [...failed.mounted] };
  const retry = failed.start();
  failed.jobs.get("source-ref-selector").resolve();
  failed.jobs.get("sdk-views").resolve();
  await turn();
  return {
    folder: { requested: folder.requested, loading: folderLoad.settled },
    requestedTogether,
    afterSelector,
    loaded: { loading: loading.settled, mounted: managed.mounted },
    afterFailure,
    retry: { loading: retry.settled, mounted: failed.mounted },
  };
}

async function main() {
  const report = {
    withoutACompositor: await withoutACompositor(),
    whenTheHelpersCannotBeFetched: await whenTheHelpersCannotBeFetched(),
    whenTemplatesCannotBeFetched: await whenTemplatesCannotBeFetched(),
    sourceHeaderReadiness: await sourceHeaderReadiness(),
  };
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error?.stack || error}\n`);
  process.exitCode = 1;
});
