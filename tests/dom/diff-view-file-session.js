// Browserless session: View file on a diff's file bars, driven through the production
// browser code.
//
// Every document here, the block the shell writes into a page, and every answer of
// POST /api/source/pin is one the in-process application gave: while it served
// tests/diff_view_file_fixture.py's mirror, then while a server on another repository,
// and one on a folder, answered a page left open from it. They are recorded in
// tests/fixtures/diff-view-file-responses.json; tests/test_diff_view_file_session.py
// replays that story against real stores and fails when the recording drifts, so this
// session never runs on an envelope a test wrote by hand. The two routes a pull request's
// page names, its comparison's and the one that opens its revision files, are recorded as
// the server's own `snapshot_route` spells them, with a stand-in for the store's token.
//
// builtin_plugins/diff/index.js loads whole, as the shell loads the plugin, with its
// modules: it reads the page's pin, validates the document, and mounts the diff view,
// whose file bars carry the controls diff-view-file.js decides. static/navigation.js
// loads whole too and spells every address. The SDK functions the plugin calls that
// do not decide anything here (the plugin-data transport, syntax highlighting, and
// preferences) are stand-ins, and the page is a small element tree that records what the
// production code builds. The stand-in for the pin route refuses what the server
// refuses: a request whose content type is not JSON. Each step prints the requests the
// page made, the plugin modules that step loaded, the controls of each file bar, where
// the browser or the page went, and what a refusal said. A browser requests each module
// of /plugin-static/diff/ once, as Node loads it here once, so `modules` is what the step
// asked the server for. The served folder's step comes first, before a pin has loaded
// anything, because a module stays loaded for the rest of the session. The steps that
// fail to load the module print what the view said and what it logged; a rejection nothing
// handles would end this process with an error.

const fs = require("node:fs");
const { registerHooks } = require("node:module");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

// The plugin's modules loaded since the last step, static and dynamic alike.
const loadedModules = [];
// While this is set the server does not answer for the module View file needs. The failed
// URL is its own, because a module that has loaded stays loaded, and so stays usable once
// the step is over.
let viewFileModuleUnavailable = false;
const UNAVAILABLE = "?unavailable";
// The route codec a page imports on demand when its shell did not load it: the address a
// browser asks the server for, which here is the file the server serves at it.
const CODEC = "/static/git-path.js";
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === CODEC) {
      loadedModules.push(CODEC);
      return {
        url: pathToFileURL(path.join(__dirname, "../../src/metabrowser/static/git-path.js")).href,
        shortCircuit: true,
      };
    }
    const resolved = nextResolve(specifier, context);
    return viewFileModuleUnavailable && resolved.url.endsWith("/diff-view-file.js")
      ? { ...resolved, url: `${resolved.url}${UNAVAILABLE}` }
      : resolved;
  },
  load(url, context, nextLoad) {
    if (url.endsWith(UNAVAILABLE)) {
      throw new TypeError("Failed to fetch dynamically imported module");
    }
    const name = /\/builtin_plugins\/diff\/([^/]+\.js)$/.exec(url)?.[1];
    if (name) {
      loadedModules.push(name);
    }
    return nextLoad(url, context);
  },
});

const repoRoot = path.resolve(__dirname, "../..");
const sourceRoot = path.join(repoRoot, "src/metabrowser");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/diff-view-file-responses.json"), "utf8"),
);

// A step that waits on a promise the page never settles would end the process with
// nothing printed and status 0. Say so instead.
let finished = false;
process.on("exit", (code) => {
  if (!finished && code === 0) {
    process.stderr.write(
      "View file session: ended before its last step; a promise never settled\n",
    );
    process.exitCode = 1;
  }
});

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/** Let promises and zero-delay timers run: a refusal is said in the task after it. */
async function settle() {
  for (let turn = 0; turn < 3; turn += 1) {
    await new Promise((resolve) => setTimeout(resolve, 2));
    for (let tick = 0; tick < 10; tick += 1) {
      await new Promise((resolve) => setImmediate(resolve));
    }
  }
}

// ── The page: elements that record what the production code builds ─────────

class PageElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.className = "";
    this.textContent = "";
    this.innerHTML = "";
    this.hidden = false;
    this.dataset = {};
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = new Map();
    const owner = this;
    this.classList = {
      contains: (name) => owner.className.split(" ").includes(name),
      toggle(name, force) {
        const names = new Set(owner.className.split(" ").filter(Boolean));
        const want = force === undefined ? !names.has(name) : force;
        if (want) {
          names.add(name);
        } else {
          names.delete(name);
        }
        owner.className = [...names].join(" ");
        return want;
      },
    };
  }

  append(...nodes) {
    for (const node of nodes) {
      node.parentNode = this;
      this.children.push(node);
    }
  }

  replaceChildren(...nodes) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this.textContent = "";
    this.append(...nodes);
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
      this.parentNode = null;
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name.startsWith("data-")) {
      const key = name.slice(5).replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
      this.dataset[key] = String(value);
    }
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  addEventListener(type, handler) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), handler]);
  }

  removeEventListener(type, handler) {
    this.listeners.set(
      type,
      (this.listeners.get(type) ?? []).filter((candidate) => candidate !== handler),
    );
  }

  contains(candidate) {
    for (let node = candidate; node; node = node.parentNode) {
      if (node === this) {
        return true;
      }
    }
    return false;
  }

  closest(selector) {
    for (let node = this; node; node = node.parentNode) {
      if (selector.startsWith("[") && node.attributes.has(selector.slice(1, -1))) {
        return node;
      }
      if (selector.startsWith(".") && node.classList.contains(selector.slice(1))) {
        return node;
      }
    }
    return null;
  }

  *walk() {
    yield this;
    for (const child of this.children) {
      yield* child.walk();
    }
  }

  find(className) {
    return [...this.walk()].filter((node) => node.classList.contains(className));
  }

  /**
   * A click, bubbling as the real event does. Returns whether a handler prevented the
   * browser's own action, which for a link is following its address.
   */
  click() {
    let stopped = false;
    const event = {
      target: this,
      defaultPrevented: false,
      preventDefault() {
        event.defaultPrevented = true;
      },
      stopPropagation() {
        stopped = true;
      },
    };
    for (let node = this; node && !stopped; node = node.parentNode) {
      for (const handler of node.listeners.get("click") ?? []) {
        handler(event);
      }
    }
    return event.defaultPrevented;
  }
}

// ── Production modules, loaded whole ────────────────────────────────────────

/** static/navigation.js, for the address of a path and the path of an address. */
function loadNavigation() {
  const sandbox = {
    console,
    Object,
    Array,
    String,
    Error,
    TypeError,
    URIError,
    atob,
    btoa,
    TextDecoder,
    TextEncoder,
    Uint8Array,
    METABROWSER_SOURCE_KIND: "git_revision",
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  // A pin's shell loads the GitPath codec ahead of navigation.js.
  for (const name of ["git-path.js", "navigation.js"]) {
    const file = path.join(sourceRoot, "static", name);
    vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
  }
  return sandbox;
}

const navigationRealm = loadNavigation();
const route = navigationRealm.MetabrowserNavigationRoute;
const gitPath = navigationRealm.MetabrowserGitPath;

// The page's requests, in order, and the pin requests waiting for the step to answer.
const requests = [];
const waiting = [];
const navigated = [];
// What the page listens for on its window: `pageshow`, for a restore by the browser.
const windowListeners = new Map();

/** The answers of the plugin's data hooks, by route and query, from the recording. */
const pluginData = new Map();

function pluginRoute(plugin, name, params) {
  return `/api/plugin/${plugin}/${name}?${new URLSearchParams(params)}`;
}

/** @type {{render: (container: PageElement, ctx: object) => Promise<{dispose(): void}>} | null} */
let diffView = null;

globalThis.document = {
  createElement: (tag) => new PageElement(tag),
  addEventListener() {},
  removeEventListener() {},
};
globalThis.window = {
  MetabrowserGitPath: gitPath,
  MetabrowserNavigationRoute: route,
  location: {
    assign(href) {
      navigated.push(href);
    },
  },
  addEventListener(type, handler) {
    windowListeners.set(type, [...(windowListeners.get(type) ?? []), handler]);
  },
  removeEventListener(type, handler) {
    windowListeners.set(
      type,
      (windowListeners.get(type) ?? []).filter((candidate) => candidate !== handler),
    );
  },
  metabrowser: {
    registerView(kind, view, spec) {
      assert(kind === "diff" && view === "diff", "the plugin registers its one view");
      diffView = spec;
    },
    // The plugin-data transport: the recorded answer for exactly this request.
    async fetchPluginData(plugin, name, params) {
      const request = pluginRoute(plugin, name, params);
      requests.push(`GET ${request}`);
      assert(pluginData.has(request), `no recorded answer for ${request}`);
      return structuredClone(pluginData.get(request));
    },
    navigation: { href: route.href },
    highlightSyntax: async () => null,
    isLargeTextPreview: () => true,
    langForPath: () => "",
    ownDelegate: (element) => element,
    prefs: { get: (_name, fallback) => fallback, set: () => true },
  },
};
// The pin route, as the plugin asks it: each request waits for the step to answer. The
// server answers a body that is not declared JSON with 415 before it reads it, so a
// request without that content type never reaches an answer here either.
globalThis.fetch = (url, init) => {
  const type = new Headers(init.headers).get("content-type");
  requests.push(`${init.method} ${url} [content-type: ${type}] ${init.body}`);
  assert(type === "application/json", `the pin route refuses content type ${type} with 415`);
  return new Promise((resolve, reject) => {
    waiting.push({ body: JSON.parse(init.body), resolve, reject });
  });
};

/** A `pageshow`, as the browser fires it when it brings the page back. */
function pageshow(persisted) {
  for (const handler of windowListeners.get("pageshow") ?? []) {
    handler({ persisted });
  }
}

/** Answer the waiting pin request with what a server answered that same request. */
async function answer(recording) {
  assert(waiting.length === 1, `expected one waiting request, found ${waiting.length}`);
  const [request] = waiting.splice(0, 1);
  assert(
    JSON.stringify(request.body) === JSON.stringify(recording.request),
    `the page asked ${JSON.stringify(request.body)}, the recording answers ${JSON.stringify(recording.request)}`,
  );
  request.resolve({ status: recording.status, json: async () => structuredClone(recording.body) });
  await settle();
}

async function failRequest() {
  assert(waiting.length === 1, `expected one waiting request, found ${waiting.length}`);
  const [request] = waiting.splice(0, 1);
  request.reject(new TypeError("fetch failed"));
  await settle();
}

// ── Reading the page ────────────────────────────────────────────────────────

function barLabel(bar) {
  return `${bar.find("diff-file-kind")[0].textContent} ${bar.find("diff-file-path")[0].textContent}`;
}

function describeControl(control) {
  const kind =
    control.tagName === "A"
      ? `link ${control.getAttribute("href")}`
      : `button[type=${control.getAttribute("type")}]`;
  const name = control.getAttribute("aria-label");
  const detail = control.getAttribute("data-tip-text");
  assert(name === `${control.textContent}: ${detail}`, "the name is the label and the detail");
  return `[${control.textContent}] ${kind} · ${detail}`;
}

/** Each file bar's controls. */
function bars(container) {
  const shown = {};
  for (const section of container.find("diff-file")) {
    const bar = section.find("diff-file-bar")[0];
    shown[barLabel(bar)] = bar.find("diff-file-view").map(describeControl);
  }
  return shown;
}

/** What the view announces in place of a diff. */
function failure(container) {
  return container
    .find("diff-availability")
    .filter((notice) => notice.getAttribute("role") === "alert")
    .map((notice) => notice.textContent);
}

/** What a refusal says under a bar, with the role it is announced by. */
function notices(container) {
  const said = {};
  for (const section of container.find("diff-file")) {
    const notice = section.find("diff-file-notice")[0];
    if (notice && !notice.hidden) {
      said[barLabel(section.find("diff-file-bar")[0])] =
        `[role=${notice.getAttribute("role")}] ${notice.textContent}`;
    }
  }
  return said;
}

function control(container, file, label) {
  for (const section of container.find("diff-file")) {
    const bar = section.find("diff-file-bar")[0];
    if (barLabel(bar) !== file) {
      continue;
    }
    const found = bar.find("diff-file-view").filter((candidate) => candidate.textContent === label);
    assert(found.length === 1, `${file} has one ${label} control`);
    return found[0];
  }
  throw new Error(`no file bar ${file}`);
}

function expanded(container, file) {
  for (const section of container.find("diff-file")) {
    const bar = section.find("diff-file-bar")[0];
    if (barLabel(bar) === file) {
      return bar.find("diff-file-toggle")[0].getAttribute("aria-expanded") === "true";
    }
  }
  throw new Error(`no file bar ${file}`);
}

/** The controls that say a switch is on its way. */
function busy(container) {
  return container
    .find("diff-file-view")
    .filter((candidate) => candidate.getAttribute("aria-busy") === "true")
    .map((candidate) => `${barLabel(candidate.parentNode)} [${candidate.textContent}]`);
}

/** The path a `/view/` address names on a pin, by the production decoder. */
function pathOf(href) {
  assert(href.startsWith("/view/"), `${href} is a /view/ address`);
  return route.displayPath(href.slice("/view/".length), "git_revision");
}

// ── The session ─────────────────────────────────────────────────────────────

async function main() {
  await import(pathToFileURL(path.join(sourceRoot, "builtin_plugins/diff/index.js")).href);
  assert(diffView !== null, "the diff plugin registered its view");

  const ids = recorded.commits;
  const steps = [];
  let mounted = null;
  let container = null;

  /** Start a diff on a page the server rendered for *page*, as a caller of the view does. */
  function begin(page, ctx) {
    mounted?.dispose();
    mounted = null;
    if (page === null) {
      delete globalThis.window.METABROWSER_SOURCE_PIN;
    } else {
      globalThis.window.METABROWSER_SOURCE_PIN = page;
    }
    container = new PageElement("div");
    return diffView.render(container, ctx);
  }

  async function open(page, ctx) {
    mounted = await begin(page, ctx);
    await settle();
  }

  /** Run *body* with the view's console.error recorded; returns one line per call. */
  async function logging(body) {
    const logged = [];
    const consoleError = console.error;
    console.error = (message, details, error) => {
      logged.push(`${message} · ${details.hook} · ${error.message}`);
    };
    try {
      await body();
    } finally {
      console.error = consoleError;
    }
    return logged;
  }

  function step(name, extra = {}) {
    const modules = loadedModules.splice(0).sort();
    steps.push({
      step: name,
      requests: requests.splice(0),
      ...(modules.length > 0 ? { modules } : {}),
      ...extra,
      ...(navigated.length > 0 ? { navigated: navigated.splice(0) } : {}),
      ...(Object.keys(notices(container)).length > 0 ? { notices: notices(container) } : {}),
    });
  }

  const commitDiff = { revision: ids.second, raw: Promise.resolve(recorded.commit.body) };
  const readme = "M README.md";
  const renamed = "R100 src/old_name.py → src/new_name.py";

  // A served folder's page carries no pin, so its diffs carry no controls, and it never
  // asks for the module that decides them.
  await open(recorded.folder_page, commitDiff);
  step("a served folder's page has no controls", { bars: bars(container) });

  // The Git panel asks for the commit's comparison itself and hands it to the view. A pin
  // asks for the module as that request is on its way, so neither waits for the other.
  let comparisonArrives = () => {};
  const rendering = begin(recorded.page, {
    revision: ids.second,
    raw: new Promise((resolve) => {
      comparisonArrives = resolve;
    }),
  });
  await settle();
  step("a pin's first diff asks for the module before its comparison answers", {
    bars: bars(container),
  });
  comparisonArrives(recorded.commit.body);
  mounted = await rendering;
  await settle();
  step("a commit's diff on the page that shows that commit", { bars: bars(container) });

  // A link has no handler: the browser follows its address, and the bar does not fold.
  const link = control(container, readme, "View file");
  const prevented = link.click();
  assert(link.getAttribute("href") === recorded.views.readme, "the link is the file's address");
  step("the link is the browser's to follow", {
    prevented,
    follows: link.getAttribute("href"),
    opens: pathOf(link.getAttribute("href")),
    barStillOpen: expanded(container, readme),
  });
  const latin1 = control(container, "M latin1-\ufffd.txt", "View file").getAttribute("href");
  assert(latin1 === recorded.views.latin1, "a name that is not UTF-8 keeps its bytes");

  // The rest of the bar still folds the file.
  container.find("diff-file-path")[0].click();
  step("the rest of the bar still folds the file", { barStillOpen: expanded(container, readme) });

  control(container, renamed, "View at parent").click();
  await settle();
  step("View at parent asks the server to switch", {
    busy: busy(container),
    barStillOpen: expanded(container, renamed),
  });

  control(container, "D gone.txt", "View at parent").click();
  await settle();
  step("a second switch waits for the first", { busy: busy(container) });

  await answer(recorded.switch_parent);
  const went = navigated[0];
  step("the page goes where the server says", { opens: pathOf(went), busy: busy(container) });

  // The page is leaving. Until it has, nothing more is asked of the server.
  control(container, "D gone.txt", "View at parent").click();
  await settle();
  step("a page that is leaving asks nothing more", { busy: busy(container) });

  // Back, with the commit the page shows served again: the browser restores the page as
  // it was left, and its controls work again.
  pageshow(false);
  step("a pageshow that restores nothing changes nothing", { busy: busy(container) });
  pageshow(true);
  control(container, "D gone.txt", "View at parent").click();
  await settle();
  step("a page the browser brings back switches again", { busy: busy(container) });

  // Unmounted while that switch was on its way: its answer takes the page nowhere.
  mounted.dispose();
  mounted = null;
  await answer(recorded.switch_gone);
  step("a diff unmounted before the answer goes nowhere", {
    listeningForPageshow: (windowListeners.get("pageshow") ?? []).length,
  });

  // The page that load brings is rendered for the parent; Back returns to the diff on it.
  await open(recorded.page_at_parent, commitDiff);
  step("the same diff from the page on the parent", { bars: bars(container) });

  control(container, renamed, "View file").click();
  await settle();
  await answer(recorded.switch_head);
  step("View file switches to the commit, and the server is on its branch again", {
    opens: pathOf(navigated[0]),
    served: recorded.switch_head.body.status.ref,
  });

  await open(recorded.page, { revision: ids.first, raw: Promise.resolve(recorded.root.body) });
  step("a root commit has only its own side", { bars: bars(container) });

  // A pull request's page names the route that opens a file at either end of its
  // comparison without changing the pin, and its comparison's own route; the server spells
  // both (tests/test_diff_view_file_session.py records them). The comparison's base is the
  // merge base, as a pull request's record names it.
  const routes = recorded.pull_routes;
  const merged = recorded.pull.body.resolved.left.id;
  const comparisonTarget = new URL(routes.comparison, "http://metabrowser.invalid");
  pluginData.set(
    pluginRoute("github", "pull-comparison", Object.fromEntries(comparisonTarget.searchParams)),
    recorded.pull.body,
  );
  const pullPage = {
    left: merged,
    right: ids.second,
    base_policy: "merge_base",
    route: routes.comparison,
    snapshot_route: routes.snapshot,
  };
  const noSwitch = () =>
    assert(
      !requests.some((request) => request.startsWith("POST")),
      "a pull request's View file never asks the server to switch its pin",
    );

  // On a mirror serving the pull request's head, the head is the commit the page shows.
  // The only page that mounts a two-endpoint comparison is a pull request's, and it always
  // names these routes, so no comparison here switches the pin.
  await open(recorded.page, { comparison: pullPage });
  noSwitch();
  assert(
    control(container, readme, "View at base")
      .getAttribute("data-tip-text")
      .includes(ids.first.slice(0, 12)),
    "the base side is the merge base, not the base branch's tip",
  );
  step("a pull request's Changes at its head opens the base on its revision page", {
    bars: bars(container),
  });
  const atBase = control(container, readme, "View at base");
  step("a revision page is a link the browser follows", {
    prevented: atBase.click(),
    follows: atBase.getAttribute("href"),
  });

  // Beside a checkout the page has no pin and its shell no route codec: both sides open on
  // their revision page, and the codec is asked for once, with the module.
  const codec = globalThis.window.MetabrowserGitPath;
  delete globalThis.window.MetabrowserGitPath;
  await open(null, { comparison: pullPage });
  noSwitch();
  step("beside a checkout both sides open on their revision page", {
    codecLoaded: globalThis.window.MetabrowserGitPath !== undefined,
    bars: bars(container),
  });
  globalThis.window.MetabrowserGitPath = codec;

  // A side whose commit is not that end of the comparison is not served by the route.
  await open(null, { comparison: { ...pullPage, left: ids.base } });
  noSwitch();
  step("a side at another commit than its end of the comparison has no control", {
    bars: bars(container),
  });

  const patch = gitPath.wire("changes.patch");
  pluginData.set(pluginRoute("diff", "document", { path: patch }), recorded.patch.body);
  await open(recorded.page, { path: patch });
  step("a patch file names no commit", {
    opens: pathOf(`/view/${patch}`),
    bars: bars(container),
  });

  // A page left open while its server was restarted on another repository.
  await open(recorded.page, commitDiff);
  requests.splice(0);
  const lacking = control(container, readme, "View at parent");
  lacking.click();
  await settle();
  await answer(recorded.other_pending);
  step("a commit the server's mirror lacks is being fetched", { busy: busy(container) });

  lacking.click();
  await settle();
  await answer(recorded.other_not_found);
  step("asked again after the fetch, the origin does not have it");

  lacking.click();
  await settle();
  await answer(recorded.other_fetch_failed);
  step("a fetch that could not run says so");

  lacking.click();
  await settle();
  await answer(recorded.folder_refused);
  step("a server that now serves a folder refuses");

  lacking.click();
  await settle();
  await failRequest();
  step("a request that fails says so");

  lacking.click();
  await settle();
  step("asking again clears what the last refusal said", { waiting: waiting.length });
  await failRequest();
  requests.splice(0);

  // The server does not answer for the module: a server restarted on another build, or a
  // lost connection. The diff is there to show, but the page cannot decide its controls.
  viewFileModuleUnavailable = true;
  let logged = await logging(() => open(recorded.page, commitDiff));
  step("a page whose module does not load says so, and logs the request", {
    bars: bars(container),
    failure: failure(container),
    logged,
  });

  // A diff that fails first speaks for itself, and the import failing after it is handled.
  const failed = Object.assign(new Error("the comparison failed"), {
    status: 500,
    payload: { message: "This commit's comparison failed." },
  });
  logged = await logging(() =>
    open(recorded.page, { revision: ids.second, raw: Promise.reject(failed) }),
  );
  step("a diff that fails while the module fails too says the diff's failure", {
    bars: bars(container),
    failure: failure(container),
    logged,
  });

  // A served folder asks for nothing, so nothing of the module can fail on one.
  logged = await logging(() => open(recorded.folder_page, commitDiff));
  viewFileModuleUnavailable = false;
  step("a served folder's diff does not depend on the module", {
    bars: bars(container),
    failure: failure(container),
    logged,
  });

  mounted?.dispose();
  finished = true;
  process.stdout.write(`${JSON.stringify({ steps }, null, 2)}\n`);
}

main().catch((error) => {
  finished = true;
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
