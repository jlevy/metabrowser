// Browserless session: View file on a diff's file bars, driven through the production
// browser code.
//
// Every document here, the block the shell writes into a page, and every answer of
// POST /api/source/pin is one the in-process application gave: while it served
// tests/diff_view_file_fixture.py's mirror, then while a server on another repository,
// and one on a folder, answered a page left open from it. They are recorded in
// tests/fixtures/diff-view-file-responses.json; tests/test_diff_view_file_session.py
// replays that story against real stores and fails when the recording drifts, so this
// session never runs on an envelope a test wrote by hand.
//
// builtin_plugins/diff/index.js loads whole, as the shell loads the plugin, with its
// modules: it reads the page's pin, validates the document, and mounts the diff view,
// whose file bars carry the controls diff-view-file.js decides. static/navigation.js
// loads whole too and formats every address. The SDK functions the plugin calls that
// do not decide anything here (the plugin-data transport, syntax highlighting, and
// preferences) are stand-ins, and the page is a small element tree that records what the
// production code builds. Each step prints the requests the page made, the controls of
// each file bar, where the browser or the page went, and what a refusal said.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const sourceRoot = path.join(repoRoot, "src/metabrowser");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/diff-view-file-responses.json"), "utf8"),
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
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
    Uint8Array,
    METABROWSER_SOURCE_KIND: "git_revision",
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  const file = path.join(sourceRoot, "static/navigation.js");
  vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
  return sandbox.MetabrowserNavigationRoute;
}

const route = loadNavigation();

// The page's requests, in order, and the pin requests waiting for the step to answer.
const requests = [];
const waiting = [];
const navigated = [];

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
  location: {
    assign(href) {
      navigated.push(href);
    },
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
// The pin route, as the plugin asks it: each request waits for the step to answer.
globalThis.fetch = (url, init) => {
  requests.push(`${init.method} ${url} ${init.body}`);
  return new Promise((resolve, reject) => {
    waiting.push({ body: JSON.parse(init.body), resolve, reject });
  });
};

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
  const href = control.getAttribute("href");
  const kind = control.tagName === "A" ? `link ${href}` : "button";
  const name = control.getAttribute("aria-label");
  const detail = control.getAttribute("data-tip-text");
  assert(name === `${control.textContent}: ${detail}`, "the name is the label and the detail");
  return `[${control.textContent}] ${kind} · ${detail}`;
}

/** Each file bar's controls, and what a refusal says under it. */
function bars(container) {
  const shown = {};
  for (const section of container.find("diff-file")) {
    const bar = section.find("diff-file-bar")[0];
    shown[barLabel(bar)] = bar.find("diff-file-view").map(describeControl);
  }
  return shown;
}

function notices(container) {
  const said = {};
  for (const section of container.find("diff-file")) {
    const notice = section.find("diff-file-notice")[0];
    if (notice && !notice.hidden) {
      said[barLabel(section.find("diff-file-bar")[0])] = notice.textContent;
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

  /** Mount a diff on a page the server rendered for *page*, as a caller of the view does. */
  async function open(page, ctx) {
    mounted?.dispose();
    if (page === null) {
      delete globalThis.window.METABROWSER_SOURCE_PIN;
    } else {
      globalThis.window.METABROWSER_SOURCE_PIN = page;
    }
    container = new PageElement("div");
    mounted = await diffView.render(container, ctx);
    await settle();
  }

  function step(name, extra = {}) {
    steps.push({
      step: name,
      requests: requests.splice(0),
      ...extra,
      ...(navigated.length > 0 ? { navigated: navigated.splice(0) } : {}),
      ...(Object.keys(notices(container)).length > 0 ? { notices: notices(container) } : {}),
    });
  }

  const commitDiff = { revision: ids.second, raw: Promise.resolve(recorded.commit.body) };
  const readme = "M README.md";
  const renamed = "R100 src/old_name.py → src/new_name.py";

  // The Git panel asks for the commit's comparison itself and hands it to the view.
  await open(recorded.page, commitDiff);
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

  const toParent = control(container, renamed, "View at parent");
  toParent.click();
  await settle();
  step("View at parent asks the server to switch", {
    busy: toParent.getAttribute("aria-busy"),
    barStillOpen: expanded(container, renamed),
  });

  control(container, "D gone.txt", "View at parent").click();
  await settle();
  step("a second switch waits for the first");

  await answer(recorded.switch_parent);
  const went = navigated[0];
  step("the page goes where the server says", {
    busy: toParent.getAttribute("aria-busy"),
    opens: pathOf(went),
  });

  // The page that load brings is rendered for the parent; Back returns to the diff on it.
  await open(recorded.page_at_parent, commitDiff);
  step("the same diff from the page on the parent", { bars: bars(container) });

  control(container, renamed, "View file").click();
  await settle();
  await answer(recorded.switch_head);
  step("View file switches to the commit", { opens: pathOf(navigated[0]) });

  await open(recorded.page, { revision: ids.first, raw: Promise.resolve(recorded.root.body) });
  step("a root commit has only its own side", { bars: bars(container) });

  // The pull-request page names the record's two commits and the view asks for them.
  const pull = { left: ids.base, right: ids.second, base_policy: "merge_base" };
  pluginData.set(pluginRoute("diff", "comparison", pull), recorded.pull.body);
  await open(recorded.page, { comparison: pull });
  assert(
    control(container, readme, "View at base")
      .getAttribute("data-tip-text")
      .includes(ids.first.slice(0, 12)),
    "the base side is the merge base, not the base branch's tip",
  );
  step("a pull request's Files changed opens the merge base and the head", {
    bars: bars(container),
  });

  const patch = recorded.views.readme.replace(/[^/]*$/, "g1-Y2hhbmdlcy5wYXRjaA");
  pluginData.set(
    pluginRoute("diff", "document", { path: patch.slice("/view/".length) }),
    recorded.patch.body,
  );
  await open(recorded.page, { path: patch.slice("/view/".length) });
  step("a patch file names no commit", { opens: pathOf(patch), bars: bars(container) });

  // A page left open while its server was restarted on another repository.
  await open(recorded.page, commitDiff);
  requests.splice(0);
  const lacking = control(container, readme, "View at parent");
  lacking.click();
  await settle();
  await answer(recorded.other_pending);
  step("a commit the server's mirror lacks is being fetched");

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

  // A served folder's page carries no pin, so its diffs carry no controls.
  await open(recorded.folder_page, commitDiff);
  step("a served folder's page has no controls", { bars: bars(container) });

  mounted?.dispose();
  process.stdout.write(`${JSON.stringify({ steps }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(1);
});
