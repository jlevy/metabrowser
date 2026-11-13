// Behavioral checks for the Git nav panel.
//
// The panel is exercised through a fake DOM and a stubbed `fetch`, so
// these assertions cover the parts that are easy to get wrong and
// invisible in a screenshot: which rows are navigable, what the hover
// card says, whether a truncated file list admits it, and whether a
// stale in-flight request can overwrite a newer selection, and whether
// the first commit opened in a fresh shell loads the diff plugin before
// asking it to render.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const failures = [];

function assertEqual(label, actual, expected) {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) {
    failures.push(`${label}: expected ${b} got ${a}`);
  }
}

function assertTrue(label, value) {
  if (!value) {
    failures.push(`${label}: expected true`);
  }
}

function assertContains(label, haystack, needle) {
  if (!String(haystack).includes(needle)) {
    failures.push(`${label}: expected to contain ${JSON.stringify(needle)}`);
  }
}

function assertNotContains(label, haystack, needle) {
  if (String(haystack).includes(needle)) {
    failures.push(`${label}: expected NOT to contain ${JSON.stringify(needle)}`);
  }
}

// Counts are accessible labels; status identity and visible letters are separate
// semantics. Attribute order and incidental span whitespace are not the contract.
function assertFileStatus(label, html, status, count) {
  const token = `data-file-status="${status}"`;
  if (count === 0) {
    assertNotContains(label, html, token);
    return;
  }
  const unit = count === 1 ? "file" : "files";
  assertContains(`${label}: accessible count`, html, `aria-label="${count} ${status} ${unit}"`);
  assertContains(`${label}: status identity`, html, token);
  const letter = { modified: "M", added: "A", deleted: "D" }[status];
  const text = String(html)
    .replace(/<[^>]*>/g, "")
    .replace(/\s+/g, " ");
  assertContains(`${label}: visible count and letter`, text, `${count} ${letter}`);
}

// ── Fake DOM ─────────────────────────────────────────────────

class FakeClassList {
  constructor(element) {
    this.element = element;
  }
  add(...names) {
    for (const name of names) {
      this.element.classNames.add(name);
    }
  }
  remove(...names) {
    for (const name of names) {
      this.element.classNames.delete(name);
    }
  }
  contains(name) {
    return this.element.classNames.has(name);
  }
  toggle(name, force) {
    const enabled = force === undefined ? !this.contains(name) : Boolean(force);
    if (enabled) {
      this.add(name);
    } else {
      this.remove(name);
    }
    return enabled;
  }
}

class FakeElement {
  constructor(tagName, document) {
    this.tagName = String(tagName).toUpperCase();
    this.ownerDocument = document;
    this.parentNode = null;
    this.children = [];
    this.attributes = new Map();
    this.listeners = new Map();
    this.classNames = new Set();
    this.classList = new FakeClassList(this);
    this.dataset = {};
    // `style` is a bag with the one CSSOM method the panel uses: custom
    // properties are how the row pitch reaches the skeleton CSS without
    // restating SWIMLANE_HEIGHT there.
    this.style = {
      setProperty(name, value) {
        this[name] = value;
      },
      getPropertyValue(name) {
        return this[name] ?? "";
      },
    };
    this._text = "";
    this._html = "";
    this._hovered = false;
    this.scrollCalls = [];
    // The options of each focus() call, so a test can tell focus that scrolls from focus
    // that does not.
    this.focusCalls = [];
    // Layout the panel actually reads. The Git panel converts between the
    // scroller's coordinate space and the virtualized list's by summing
    // the heights of the chrome above the list, so a fake DOM reporting
    // nothing here cannot exercise that conversion.
    this.offsetHeight = 0;
  }

  set className(value) {
    this.classNames = new Set(String(value).split(/\s+/).filter(Boolean));
  }
  get className() {
    return Array.from(this.classNames).join(" ");
  }
  get parentElement() {
    return this.parentNode;
  }
  get isConnected() {
    return this === this.ownerDocument.root || Boolean(this.parentNode?.isConnected);
  }
  get firstElementChild() {
    return this.children[0] || null;
  }

  set textContent(value) {
    this._text = String(value);
    this.children = [];
  }
  get textContent() {
    if (this._text) {
      return this._text;
    }
    return this.children.map((child) => child.textContent).join("");
  }

  set innerHTML(value) {
    this._html = String(value);
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    if (this._html.startsWith('<div class="loading ')) {
      const loading = new FakeElement("div", this.ownerDocument);
      loading.className = "loading mb-delayed-loading";
      this.appendChild(loading);
    }
    if (this._html.includes("git-commit-diff")) {
      const diffHost = new FakeElement("div", this.ownerDocument);
      diffHost.className = "git-commit-diff";
      this.appendChild(diffHost);
    }
    // The full summary's identity group and its refs, so a test can watch the refs of a
    // summary on screen replaced in place.
    if (this._html.includes('<span class="git-commit-identity">')) {
      const identity = new FakeElement("span", this.ownerDocument);
      identity.className = "git-commit-identity";
      const refs = this._html.match(
        /<span class="git-commit-refs">([\s\S]*?)<\/span><\/span><span class="actor-name git-commit-author">/,
      );
      if (refs) {
        const group = new FakeElement("span", this.ownerDocument);
        group.className = "git-commit-refs";
        group.innerHTML = refs[1];
        identity.appendChild(group);
      }
      this.appendChild(identity);
    }
    for (const match of this._html.matchAll(
      /class="[^"]*git-commit-file[^"]*"[^>]*data-path="([^"]+)"/g,
    )) {
      const row = new FakeElement("button", this.ownerDocument);
      row.className = "git-commit-file";
      row.dataset.path = match[1];
      this.appendChild(row);
    }
  }
  get innerHTML() {
    if (this._html) {
      return this._html;
    }
    return this.children.map((child) => child.outerHTML).join("");
  }

  get outerHTML() {
    const attrs = Array.from(this.attributes.entries())
      .map(([name, value]) => ` ${name}="${value}"`)
      .join("");
    const cls = this.classNames.size ? ` class="${this.className}"` : "";
    return `<${this.tagName.toLowerCase()}${cls}${attrs}>${this.innerHTML}${this._text}</${this.tagName.toLowerCase()}>`;
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  appendChild(child) {
    if (child.isFragment) {
      // A real fragment empties into its new parent.
      for (const node of child.children.splice(0)) {
        node.parentNode = this;
        this.children.push(node);
      }
      return child;
    }
    child.remove();
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  append(...nodes) {
    for (const node of nodes) {
      this.appendChild(node);
    }
  }
  replaceChildren(...nodes) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this._html = "";
    this._text = "";
    this.append(...nodes);
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((c) => c !== this);
      this.parentNode = null;
    }
  }
  addEventListener(type, handler) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type).push(handler);
  }
  removeEventListener(type, handler) {
    const listeners = this.listeners.get(type) ?? [];
    this.listeners.set(
      type,
      listeners.filter((candidate) => candidate !== handler),
    );
  }
  dispatch(type, event = {}) {
    for (const handler of this.listeners.get(type) ?? []) {
      handler(event);
    }
  }
  focus(options) {
    this.focusCalls.push(options ?? null);
    const previous = this.ownerDocument.activeElement;
    if (previous === this) {
      return;
    }
    previous?.dispatch("blur", { target: previous, relatedTarget: this });
    this.ownerDocument.activeElement = this;
    this.dispatch("focus", { target: this, relatedTarget: previous });
    for (let current = this; current; current = current.parentNode) {
      current.dispatch("focusin", { target: this, relatedTarget: previous });
    }
  }
  scrollIntoView(options) {
    this.scrollCalls.push(options);
  }
  matches(selector) {
    if (selector === ":hover") {
      return this._hovered;
    }
    return false;
  }
  descendants() {
    const out = [];
    for (const child of this.children) {
      out.push(child, ...child.descendants());
    }
    return out;
  }
  querySelectorAll(selector) {
    return this.descendants().filter((node) => node.matchesSelector(selector));
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
  matchesSelector(selector) {
    // Only the selector forms the panel actually uses.
    const classMatch = selector.match(/^\.([a-z0-9-]+)/i);
    if (classMatch && !this.classNames.has(classMatch[1])) {
      return false;
    }
    const attrMatch = selector.match(/\[data-([a-z-]+)(?:="([^"]*)")?\]/);
    if (attrMatch) {
      const key = attrMatch[1].replace(/-([a-z])/g, (_m, c) => c.toUpperCase());
      if (this.dataset[key] === undefined) {
        return false;
      }
      if (attrMatch[2] !== undefined && this.dataset[key] !== attrMatch[2]) {
        return false;
      }
    }
    return Boolean(classMatch || attrMatch);
  }
}

class FakeSvgElement extends FakeElement {
  constructor(tagName, document) {
    super(tagName, document);
    this.tagName = tagName;
  }
}

class FakeDocument {
  constructor() {
    this.byId = new Map();
    this.root = new FakeElement("body", this);
    this.activeElement = null;
  }
  createElement(tagName) {
    return new FakeElement(tagName, this);
  }
  createElementNS(_ns, tagName) {
    return new FakeSvgElement(tagName, this);
  }
  createDocumentFragment() {
    // A fragment behaves like a container whose children move to the
    // parent it is appended to, which is the only property the panel
    // relies on (one insertion per page rather than per row).
    const fragment = new FakeElement("#document-fragment", this);
    fragment.isFragment = true;
    return fragment;
  }
  register(id, element) {
    element.dataset.id = id;
    this.byId.set(id, element);
    this.root.appendChild(element);
    return element;
  }
  getElementById(id) {
    return this.byId.get(id) ?? null;
  }
  querySelectorAll(selector) {
    return this.root.querySelectorAll(selector);
  }
  querySelector(selector) {
    return this.root.querySelector(selector);
  }
  addEventListener() {}
  removeEventListener() {}
}

// ── Sandbox ──────────────────────────────────────────────────

const document = new FakeDocument();
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.document = document;
sandbox.console = console;
sandbox.setTimeout = setTimeout;
sandbox.clearTimeout = clearTimeout;
sandbox.AbortController = AbortController;
sandbox.Date = Date;
sandbox.Number = Number;
sandbox.Math = Math;
sandbox.URLSearchParams = URLSearchParams;
sandbox.CustomEvent = class CustomEvent {
  constructor(type, init) {
    this.type = type;
    this.detail = init?.detail;
  }
};
sandbox.HTMLElement = FakeElement;
sandbox.METABROWSER_SETTINGS = {
  GIT_LOG_LIMIT: 2,
  GIT_HISTORY_WINDOW_MAX_ROWS: 3,
  GIT_HISTORY_WINDOW_OVERSCAN_ROWS: 1,
  GIT_HISTORY_PAGE_CACHE_PAGES: 2,
  GIT_HISTORY_SEGMENT_REBASE_PX: 220,
  GIT_HOVER_DEBOUNCE_MS: 5,
  GIT_DETAIL_CACHE_SIZE: 3,
};

const openedPaths = [];
sandbox.dispatchEvent = () => {};
sandbox.addEventListener = () => {};
sandbox.removeEventListener = () => {};
// Navigation goes through the documented namespace. The panel used to dispatch
// `metabrowser:open-path`, which the SDK 0.2 break removed with no shim.
sandbox.MetabrowserNavigationRoute = {
  navigation: {
    open: (target) => {
      openedPaths.push(target.path);
      return Promise.resolve({ status: "opened" });
    },
  },
  // The comparison address space: a selected commit owns the URL.
  commitHref: (revision, file = "") =>
    `/commit/${encodeURIComponent(revision)}${file ? `/${file}` : ""}`,
  parseCommit: () => null,
};
/** @type {string[]} Routes the panel replaced, newest last. */
const replacedRoutes = [];
// Whether the address is the neutral Commits entry, which a switch to Commits pushes. A
// replaced entry is a commit's address, so it is the neutral entry no longer.
let neutralLanding = false;
sandbox.history = {
  replaceState: (_state, _title, url) => {
    replacedRoutes.push(String(url));
    neutralLanding = false;
  },
};

// Shell bridge stub. Pending state is shell-owned so file and Git navigation
// exercise the same claim-scoped lifecycle.
let previewHtml = "";
let previewNode = null;
let previewClaim = 0;
let pendingStageCleanup = null;
const stagedPreviewNodes = [];
document.register("preview-pane", document.createElement("div"));
// The page's freshness controller: null when a folder is served.
let freshnessController = null;
const removedPanels = [];
let registeredPanel = null;
sandbox.MetabrowserShell = {
  rememberMainTabAddress() {},
  isGitHistoryLanding: () => neutralLanding,
  claimPreview: () => {
    pendingStageCleanup?.();
    previewClaim += 1;
    return previewClaim;
  },
  isPreviewClaimCurrent: (claim) => claim === previewClaim,
  beginPreviewNavigation: (claim) => {
    if (claim !== previewClaim) {
      return false;
    }
    const preview = document.getElementById("preview-pane");
    if (
      !preview?.firstElementChild ||
      preview.firstElementChild.classList.contains("preview-empty")
    ) {
      return false;
    }
    preview.classList.add("preview-navigation-pending");
    preview.setAttribute("aria-busy", "true");
    preview.setAttribute("data-preview-pending-claim", String(claim));
    return true;
  },
  endPreviewNavigation: (claim) => {
    const preview = document.getElementById("preview-pane");
    if (preview?.getAttribute("data-preview-pending-claim") !== String(claim)) {
      return;
    }
    preview.classList.remove("preview-navigation-pending");
    preview.removeAttribute("aria-busy");
    preview.removeAttribute("data-preview-pending-claim");
  },
  registerNavPanel: (panel) => {
    registeredPanel = panel;
  },
  removeNavPanel: (id) => removedPanels.push(id),
  renderPreviewHtml: (html, claim) => {
    if (claim !== undefined && claim !== previewClaim) {
      return null;
    }
    previewHtml = html;
    const preview = document.getElementById("preview-pane");
    preview.innerHTML = html;
    return preview;
  },
  stagePreviewNode: (node, claim) => {
    if (claim !== previewClaim) {
      return null;
    }
    pendingStageCleanup?.();
    const stage = document.createElement("div");
    stage.className = "preview-file-stage";
    stage.appendChild(node);
    document.getElementById("preview-pane").appendChild(stage);
    stagedPreviewNodes.push(node);
    const cleanup = () => {
      stage.remove();
      if (pendingStageCleanup === cleanup) {
        pendingStageCleanup = null;
      }
    };
    pendingStageCleanup = cleanup;
    return cleanup;
  },
  renderPreviewNode: (node, claim) => {
    if (claim !== undefined && claim !== previewClaim) {
      return null;
    }
    previewHtml = node.innerHTML;
    previewNode = node;
    document.getElementById("preview-pane").replaceChildren(node);
    return node;
  },
  activateNavPanel: () => {},
  sourceFreshness: async () => freshnessController,
};

// A fresh directory shell has configured plugin descriptors but has not
// evaluated the diff plugin yet. The view appears only after its kind
// assets load, matching the on-demand browser lifecycle.
let diffAssetsLoaded = false;
const ensuredKinds = [];
const renderedDiffRevisions = [];
const renderedDiffContexts = [];
const renderedDiffConnections = [];
const canceledDiffRevisions = [];
const disposedDiffRevisions = [];
const comparisonFetches = [];
const shownTooltips = [];
const measuredLabels = [];
let tooltipHideCount = 0;
let comparisonResponder = async (revision) => ({ comparison_id: revision });
sandbox.metabrowser = {
  ...require("./sdk-ref-fixture.js").refHelpers(document),
  icons: { copy: '<svg data-icon="copy"></svg>' },
  delegateOwnerAttribute: () => ' data-mb-owner="page-owner"',
  tooltip: {
    show: (html, anchor) => shownTooltips.push({ html, anchor }),
    hide: () => {
      tooltipHideCount += 1;
    },
  },
  ensureAsset: async () => {},
  ensureKindAssets: async (kind) => {
    ensuredKinds.push(kind);
    diffAssetsLoaded = true;
  },
  getRegisteredView: (kind, view) => {
    if (!diffAssetsLoaded || kind !== "diff" || view !== "diff") {
      return null;
    }
    return {
      render: async (host, context) => {
        renderedDiffConnections.push(host.isConnected);
        renderedDiffRevisions.push(context.revision);
        renderedDiffContexts.push(context);
        await context.raw;
        return {
          cancelPending: () => canceledDiffRevisions.push(context.revision),
          dispose: () => disposedDiffRevisions.push(context.revision),
        };
      },
    };
  },
  fetchPluginData: async (plugin, route, params, options) => {
    comparisonFetches.push({ plugin, route, params, signal: options?.signal });
    return comparisonResponder(params.revision);
  },
  perf: {
    measure: (label, fn) => {
      measuredLabels.push(label);
      return fn();
    },
    measureAsync: (label, fn) => {
      measuredLabels.push(label);
      return fn();
    },
  },
};

// Stubbed network. Each entry is url-prefix -> payload.
const responses = new Map();
let fetchCount = 0;
const fetchRequests = [];
sandbox.fetch = async (url, options) => {
  fetchCount += 1;
  fetchRequests.push({ url, signal: options?.signal });
  for (const [prefix, payload] of responses) {
    if (url.startsWith(prefix)) {
      const value = typeof payload === "function" ? await payload(url, options) : payload;
      if (value && typeof value === "object" && "httpStatus" in value) {
        return {
          ok: value.httpStatus >= 200 && value.httpStatus < 300,
          status: value.httpStatus,
          json: async () => value.body || {},
        };
      }
      return { ok: true, status: 200, json: async () => value };
    }
  }
  return { ok: false, status: 404, json: async () => ({}) };
};

vm.createContext(sandbox);
// formatters.js first: the panel's ages come from that shared primitive,
// and loading the real module (not a stub) is what proves a commit's age
// is spelled exactly like a file's.
// source-freshness.js is the production module a pin loads on demand; the panel hands
// it a commit the mirror lacks.
for (const file of [
  "formatters.js",
  "git-graph.js",
  "git-history-window.js",
  "source-freshness.js",
  "git-panel.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", file), "utf-8");
  vm.runInContext(source, sandbox, { filename: file });
}

const panel = sandbox.MetabrowserGitPanel;
const internals = panel._internals;

const SHA_A = "a".repeat(40);
const SHA_B = "b".repeat(40);
const SHA_C = "c".repeat(40);
const SHA_D = "d".repeat(40);
const SHA_E = "e".repeat(40);
const SHA_F = "f".repeat(40);
const SHA_G = "1".repeat(40);

function commit(id, parents, subject, refs) {
  return {
    id,
    short_id: id.slice(0, 7),
    parent_ids: parents,
    author: { name: "Author", email: "a@example.invalid" },
    authored_at: Date.now() / 1000 - 3600,
    committed_at: Date.now() / 1000 - 3600,
    subject,
    ...(refs ? { refs } : {}),
  };
}

function historyPage(page, commits, total, headRevision) {
  const nextPage = page + 1;
  const hasMore = nextPage * sandbox.METABROWSER_SETTINGS.GIT_LOG_LIMIT < total;
  return {
    is_repo: true,
    page,
    commits,
    cursor: hasMore ? `history:${nextPage}` : null,
    has_more: hasMore,
    page_cursor: `history:${page}`,
    previous_cursor: page > 0 ? `history:${page - 1}` : null,
    scope: "all",
    scope_refs: [],
    scope_fingerprint: "deep-scope",
    graph_checkpoint: {
      version: 1,
      prior_swimlanes: page > 0 ? [{ id: commits[0].id, color: "var(--git-ref-remote)" }] : [],
      color_index: -1,
      head_revision: headRevision,
      scope_fingerprint: "deep-scope",
    },
  };
}

/**
 * Append a synthetic page while preserving the production checkpoint
 * contract. Tests that call appendPage directly still have to provide the
 * exact boundary state the server would have emitted.
 */
function appendTestPage(commits, cursor) {
  const current = internals.stateForTests();
  const page = current.nextPageNumber;
  let priorSwimlanes = [];
  let colorIndex = -1;
  if (page > 0) {
    const previous = current.pageCache.peek(page - 1);
    if (!previous) {
      throw new Error(`Test page ${page} has no cached predecessor`);
    }
    const result = sandbox.MetabrowserGitGraph.computeSwimlanes(previous.commits, {
      priorSwimlanes: previous.checkpoint.priorSwimlanes,
      colorIndex: previous.checkpoint.colorIndex,
      headRevision: current.headRevision,
      refColors: new Map(),
      rowStart: previous.commits.length,
      rowEnd: previous.commits.length,
    });
    priorSwimlanes = result.trailingSwimlanes;
    colorIndex = result.colorIndex;
  }
  const scopeFingerprint = current.scopeFingerprint || "test-scope";
  internals.appendPage(commits, cursor, {
    is_repo: true,
    page,
    commits,
    cursor,
    has_more: cursor !== null,
    page_cursor: `test:${page}`,
    previous_cursor: page > 0 ? `test:${page - 1}` : null,
    scope: "all",
    scope_refs: [],
    scope_fingerprint: scopeFingerprint,
    graph_checkpoint: {
      version: 1,
      prior_swimlanes: priorSwimlanes,
      color_index: colorIndex,
      head_revision: current.headRevision,
      scope_fingerprint: scopeFingerprint,
    },
  });
}

function keyboardEvent(key, options = {}) {
  return {
    key,
    altKey: false,
    ctrlKey: false,
    metaKey: false,
    shiftKey: false,
    isComposing: false,
    defaultPrevented: false,
    repeat: false,
    ...options,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
}

async function run() {
  let commitLoadingSession;
  // ── Ref badges ─────────────────────────────────────────────
  {
    const html = internals.renderRefBadges([
      { id: "refs/heads/main", name: "main", kind: "branch", is_head: true },
      { id: "refs/remotes/upstream/trunk", name: "upstream/trunk", kind: "remote" },
      { id: "refs/tags/v1", name: "v1", kind: "tag" },
    ]);
    assertContains("badges: head branch is marked", html, "git-ref-head");
    assertContains("badges: remote kind class", html, "git-ref-remote");
    assertContains("badges: tag kind class", html, "git-ref-tag");
    assertContains("badges: local copy names the branch", html, 'data-ref-copy="main"');
    assertContains(
      "badges: remote copy preserves its prefix",
      html,
      'data-ref-copy="upstream/trunk"',
    );
    assertContains("badges: tag copy names the tag", html, 'data-ref-copy="v1"');
    assertNotContains(
      "badges: canonical namespace is not a branch name",
      html,
      'data-ref-copy="refs/',
    );
    const longName = `feature/${"long-name-".repeat(30)}←<literal>`;
    const longChip = internals.renderRefBadges([
      { id: `refs/heads/${longName}`, name: longName, kind: "branch" },
    ]);
    assertContains(
      "badges: visual clipping never truncates the payload",
      longChip,
      `data-ref-copy="${longName.replace(/</g, "&lt;").replace(/>/g, "&gt;")}"`,
    );
    assertEqual("badges: none renders nothing", internals.renderRefBadges([]), "");
  }

  // ── Escaping ───────────────────────────────────────────────
  {
    const html = internals.renderRefBadges([
      { id: "x", name: "<img src=x onerror=alert(1)>", kind: "branch" },
    ]);
    // Ref names come from the repository, which is not necessarily
    // trusted input — a branch name is whatever someone pushed.
    assertNotContains("escaping: raw tag in badge", html, "<img");
    assertContains("escaping: entity-encoded", html, "&lt;img");

    const fileHtml = internals.renderFileRow({
      path: '"><script>bad()</script>',
      status: "modified",
      additions: 1,
      deletions: 0,
    });
    assertNotContains("escaping: raw script in file row", fileHtml, "<script>");
  }

  // ── File rows ──────────────────────────────────────────────
  {
    const normal = internals.renderFileRow({
      path: "src/a.js",
      status: "modified",
      additions: 4,
      deletions: 2,
    });
    assertContains("file row: native button", normal, "<button");
    assertContains("file row: explicit button type", normal, 'type="button"');
    assertContains("file row: navigable carries data-path", normal, 'data-path="src/a.js"');
    assertNotContains("file row: no synthetic button role", normal, 'role="button"');
    assertContains("file row: additions", normal, "+4");
    assertContains("file row: deletions", normal, "−2");

    const outside = internals.renderFileRow({
      path: "other/b.js",
      status: "modified",
      additions: 1,
      deletions: 1,
      outside_root: true,
    });
    // Outside the served root: shown, because omitting it would
    // misreport the commit, but not navigable.
    assertContains("file row: outside root is inert", outside, "git-commit-file-inert");
    assertNotContains("file row: outside root has no data-path", outside, "data-path");

    const deleted = internals.renderFileRow({
      path: "gone.js",
      status: "deleted",
      additions: 0,
      deletions: 9,
    });
    // A deleted file has nothing to open at the current revision.
    assertContains("file row: deleted is inert", deleted, "git-commit-file-inert");
    assertNotContains("file row: deleted has no data-path", deleted, "data-path");

    const binary = internals.renderFileRow({
      path: "img.png",
      status: "modified",
      additions: null,
      deletions: null,
      binary: true,
    });
    assertContains("file row: binary label", binary, "binary");
    assertNotContains("file row: binary has no line counts", binary, "+0");

    const renamed = internals.renderFileRow({
      path: "new.js",
      old_path: "old.js",
      status: "renamed",
      additions: 0,
      deletions: 0,
    });
    assertContains("file row: rename shows both paths", renamed, "old.js");
    assertContains("file row: rename arrow", renamed, "→");
  }

  // ── Commit-summary tooltip ─────────────────────────────────
  {
    const detail = {
      commit: commit(SHA_A, [], "the <subject>", [
        { id: "refs/heads/main", name: "main", kind: "branch" },
        { id: "refs/tags/v1", name: "v1", kind: "tag" },
      ]),
      body: "the long body must stay out of a bounded tooltip",
      stats: {
        files_changed: 32,
        files_modified: 28,
        files_added: 4,
        files_deleted: 0,
        additions: 1921,
        deletions: 160,
      },
      files: [],
      files_truncated: false,
    };
    const html = internals.renderCommitTooltip(detail);
    assertContains("tooltip: compact summary root", html, "git-commit-summary-compact");
    assertContains("tooltip: escaped subject", html, "the &lt;subject&gt;");
    assertContains("tooltip: author", html, "Author");
    assertContains("tooltip: short revision", html, SHA_A.slice(0, 7));
    assertContains("tooltip: copy identity glyph", html, 'data-icon="copy"');
    assertContains("tooltip: refs use the history badge", html, "git-ref-local");
    assertContains("tooltip: tags use the history badge", html, "git-ref-tag");
    assertContains("tooltip: refs stay beside the revision", html, "main");
    const identityStart = html.indexOf('<span class="git-commit-identity">');
    const identityEnd = html.indexOf("</span>", html.indexOf("git-commit-refs", identityStart));
    assertTrue(
      "tooltip: identity owns revision and refs",
      identityStart >= 0 &&
        html.indexOf("git-commit-revision", identityStart) < identityEnd &&
        html.indexOf("git-commit-refs", identityStart) < identityEnd,
    );
    assertFileStatus("tooltip: modified files", html, "modified", 28);
    assertFileStatus("tooltip: added files", html, "added", 4);
    assertFileStatus("tooltip: zero deleted files are omitted", html, "deleted", 0);
    assertContains("tooltip: file unit", html, 'git-commit-stat-unit">files');
    assertContains("tooltip: additions", html, "+1921");
    assertContains("tooltip: deletions", html, "−160");
    assertContains("tooltip: line unit", html, 'git-commit-stat-unit">lines');
    const metaStart = html.indexOf('<div class="git-commit-meta">');
    const metaEnd = html.indexOf("</div>", metaStart);
    const statsStart = html.indexOf('<div class="git-commit-change-stats">');
    const fileStatsStart = html.indexOf('<div class="git-commit-file-statuses"', statsStart);
    const lineStatsStart = html.indexOf('<div class="git-commit-line-stats"', statsStart);
    assertTrue(
      "tooltip: change statistics are two rows below identity metadata",
      metaStart >= 0 &&
        metaEnd > metaStart &&
        statsStart > metaEnd &&
        fileStatsStart > statsStart &&
        lineStatsStart > fileStatsStart,
    );
    assertNotContains("tooltip: omits long body", html, "long body");
    assertNotContains("tooltip: has no interactive copy button", html, "<button");
    assertNotContains("tooltip: has no copy behavior", html, "data-mb-copy");

    const unknown = internals.renderCommitTooltip({
      ...detail,
      stats: {},
      files_truncated: true,
    });
    assertFileStatus("tooltip: unknown modified count stays unknown", unknown, "modified", "?");
    assertFileStatus("tooltip: unknown added count stays unknown", unknown, "added", "?");
    assertFileStatus("tooltip: unknown deleted count stays unknown", unknown, "deleted", "?");
    assertContains("tooltip: unknown additions stay unknown", unknown, "+?");
    assertContains("tooltip: unknown deletions stay unknown", unknown, "−?");
  }
  internals.setStateForTests({ ...internals.emptyState(), selectedId: SHA_A });
  await internals.renderCommitDetail({
    is_repo: true,
    commit: commit(SHA_A, [SHA_B], "a commit", [
      { id: "refs/heads/main", name: "main", kind: "branch", is_head: true },
    ]),
    body: "explanatory body\n\nsecond paragraph",
    stats: {
      files_changed: 2,
      files_modified: 1,
      files_added: 1,
      files_deleted: 0,
      additions: 5,
      deletions: 1,
    },
    files: [
      { path: "one.js", status: "modified", additions: 5, deletions: 1 },
      { path: "two.js", status: "added", additions: 0, deletions: 0 },
    ],
    files_truncated: false,
  });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertContains("detail: subject", previewHtml, "a commit");
  assertContains("detail: short sha", previewHtml, SHA_A.slice(0, 7));
  assertContains(
    "detail: revision uses the copyable identifier group",
    previewHtml,
    "git-commit-revision",
  );
  assertContains(
    "detail: revision uses the shared copy delegate",
    previewHtml,
    'data-mb-copy="text"',
  );
  assertContains(
    "detail: revision copies the full sha",
    previewHtml,
    `data-mb-copy-text="${SHA_A}"`,
  );
  assertContains(
    "detail: revision copy carries the page's owner mark",
    previewHtml,
    `data-mb-copy-text="${SHA_A}" data-mb-owner="page-owner"`,
  );
  assertContains(
    "detail: revision copy has an accessible name",
    previewHtml,
    'aria-label="Copy revision"',
  );
  assertContains("detail: revision uses the shared copy icon", previewHtml, 'data-icon="copy"');
  assertContains(
    "detail: body preserves authored newlines",
    previewHtml,
    "explanatory body\n\nsecond paragraph",
  );
  assertContains("detail: ref badge", previewHtml, "main");
  assertContains(
    "detail: summary has one component root",
    previewHtml,
    '<section class="git-commit-summary page-reading-column"',
  );
  assertContains(
    "detail: summary gives change stats their own child",
    previewHtml,
    "git-commit-change-stats",
  );
  assertFileStatus("detail: summary counts modified files", previewHtml, "modified", 1);
  assertFileStatus("detail: summary counts added files", previewHtml, "added", 1);
  assertFileStatus("detail: summary omits zero deleted files", previewHtml, "deleted", 0);
  assertContains("detail: summary counts additions", previewHtml, "+5");
  assertContains("detail: summary counts deletions", previewHtml, "−1");
  assertContains(
    "detail: uses the shared page heading",
    previewHtml,
    '<h1 class="git-commit-subject page-heading"',
  );
  const summaryStart = previewHtml.indexOf(
    '<section class="git-commit-summary page-reading-column"',
  );
  const summaryEnd = previewHtml.indexOf("</section>", summaryStart);
  assertTrue(
    "detail: component owns subject, metadata, refs, and description",
    summaryStart >= 0 &&
      previewHtml.indexOf("git-commit-subject", summaryStart) < summaryEnd &&
      previewHtml.indexOf("git-commit-meta", summaryStart) < summaryEnd &&
      previewHtml.indexOf("git-commit-refs", summaryStart) < summaryEnd &&
      previewHtml.indexOf("git-commit-body", summaryStart) < summaryEnd,
  );
  // The commit's files are presented by the diff view mounted below, so
  // the panel keeps only what that view cannot show: a host for it, the
  // files outside the served root, and any bound on the comparison.
  assertContains("detail: mounts the diff host", previewHtml, "git-commit-diff");
  assertEqual("detail: loads fresh diff assets", ensuredKinds, ["diff"]);
  assertEqual("detail: renders after loading diff assets", renderedDiffRevisions, [SHA_A]);
  assertEqual("detail: diff renders in the connected staging layer", renderedDiffConnections, [
    true,
  ]);
  assertEqual(
    "detail: successful handoff removes its hidden staging wrapper",
    document.querySelectorAll(".preview-file-stage").length,
    0,
  );
  assertEqual("detail: prepared comparison reaches the view", await renderedDiffContexts[0].raw, {
    comparison_id: SHA_A,
  });
  assertNotContains("detail: no truncation note", previewHtml, "the diff below is bounded");
  await internals.renderCommitDetail({
    is_repo: true,
    commit: commit(SHA_A, [], "outside commit"),
    body: "",
    stats: { files_changed: 2, additions: 1, deletions: 1 },
    files: [
      { path: "inside.js", status: "modified", additions: 1, deletions: 0 },
      { path: "../outside.js", status: "modified", additions: 0, deletions: 1, outside_root: true },
    ],
    files_truncated: false,
  });
  // Files the server cannot open are still reported; hiding them would
  // misreport what the commit changed.
  assertContains("detail: names files outside the folder", previewHtml, "outside this folder");
  assertContains("detail: lists the outside file", previewHtml, "outside.js");
  assertNotContains("detail: does not relist inside files", previewHtml, "inside.js");
  await internals.renderCommitDetail({
    is_repo: true,
    commit: commit(SHA_A, [], "big commit"),
    body: "",
    stats: { files_changed: 900, additions: 1, deletions: 1 },
    files: [{ path: "one.js", status: "modified", additions: 1, deletions: 1 }],
    files_truncated: true,
  });
  // A silently bounded diff reads as a complete one, which is the worse
  // failure — so the bound has to be stated, with the real total.
  assertContains("detail: truncation is stated", previewHtml, "the diff below is bounded");
  assertContains("detail: truncation names the total", previewHtml, "900");

  // ── Paging appends and keeps lanes continuous ──────────────
  {
    internals.setStateForTests(internals.emptyState());
    appendTestPage([commit(SHA_A, [SHA_B], "tip"), commit(SHA_B, [SHA_C], "middle")], "cursor-1");
    const afterFirst = internals.stateForTests();
    assertEqual("paging: first page rows", afterFirst.rows.length, 2);
    assertEqual("paging: cursor stored", afterFirst.cursor, "cursor-1");
    appendTestPage([commit(SHA_C, [], "root")], null);
    const afterSecond = internals.stateForTests();
    assertEqual("paging: rows accumulate", afterSecond.rows.length, 3);
    assertEqual("paging: end of history clears the cursor", afterSecond.cursor, null);
    // The third row must have inherited the lane from the previous page,
    // or the graph would restart at column zero mid-scroll.
    assertEqual(
      "paging: continuity across the boundary",
      afterSecond.rows[2].inputSwimlanes.map((lane) => lane.id),
      [SHA_C],
    );
    // Rows are independent: each gutter is exactly its own row's graph,
    // so a later page cannot change how an earlier row lays out. That
    // independence is what lets a page be appended rather than
    // triggering a rebuild of the whole history.
    // Rows are independent — each gutter is exactly its own row's graph
    // — so a later page cannot change how an earlier row lays out. That
    // independence is what lets a page be appended to the rendered list
    // instead of rebuilding the whole history on every "load more".
    assertEqual(
      "paging: a page lays out only its requested range",
      internals.rowsForRange(2, 3).length,
      1,
    );
  }

  // ── History retention is explicitly bounded ───────────────
  {
    internals.setStateForTests(internals.emptyState());
    appendTestPage([commit(SHA_A, [SHA_B], "one"), commit(SHA_B, [SHA_C], "two")], "cursor-1");
    appendTestPage([commit(SHA_C, [SHA_D], "three"), commit(SHA_D, [], "four")], "cursor-2");
    const continuous = internals.stateForTests();
    assertEqual("continuous: every discovered row remains logical", continuous.rowCount, 4);
    assertEqual("continuous: decoded pages stay bounded", continuous.pageCache.size, 2);
    assertEqual("continuous: pagination continues", continuous.cursor, "cursor-2");

    const container =
      document.getElementById("tab-git") ??
      document.register("tab-git", document.createElement("div"));
    internals.renderPanel();
    assertEqual(
      "continuous: mounted rows stay bounded",
      container.querySelectorAll(".git-graph-row").length,
      3,
    );
    assertNotContains(
      "continuous: no product cutoff is disclosed",
      container.textContent,
      "newest",
    );
  }

  // ── Deep history reaches its real end and replays after eviction ──
  {
    const total = 1003;
    const revisions = Array.from({ length: total }, (_value, index) =>
      (index + 1).toString(16).padStart(40, "0"),
    );
    const deepCommits = revisions.map((revision, index) =>
      commit(
        revision,
        index + 1 < total ? [revisions[index + 1]] : [],
        `deep commit ${index}`,
        index === 0
          ? [{ id: "refs/heads/main", name: "main", kind: "branch", is_head: true }]
          : undefined,
      ),
    );
    const deep = internals.emptyState();
    deep.headRevision = revisions[0];
    internals.setStateForTests(deep);
    for (let page = 0; page * 2 < total; page += 1) {
      const commits = deepCommits.slice(page * 2, page * 2 + 2);
      const wire = historyPage(page, commits, total, revisions[0]);
      internals.appendPage(commits, wire.cursor, wire);
    }
    assertEqual("deep: logical history crosses one thousand rows", deep.rowCount, total);
    assertTrue("deep: real end is distinct from an omitted page", deep.endReached);
    assertEqual(
      "deep: final commit is reachable",
      internals.rowsForRange(1002, 1003)[0].row.commit.id,
      revisions[1002],
    );
    assertEqual("deep: decoded cache remains bounded at the real end", deep.pageCache.size, 2);

    const requestStart = fetchRequests.length;
    responses.clear();
    responses.set("/api/git/log", (url) => {
      const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
      const page = cursor ? Number(cursor.split(":")[1]) : 0;
      const commits = deepCommits.slice(page * 2, page * 2 + 2);
      return historyPage(page, commits, total, revisions[0]);
    });
    const panelContainer = document.byId.get("tab-git");
    document.byId.delete("tab-git");
    try {
      assertTrue("deep: evicted first page replays", await internals.ensurePageLoaded(0));
    } finally {
      if (panelContainer) {
        document.byId.set("tab-git", panelContainer);
      }
    }
    assertEqual(
      "deep: a visited page replays in one request, not one per page",
      fetchRequests.length - requestStart,
      1,
    );
    assertEqual(
      "deep: replay restores the first exact commit",
      internals.rowsForRange(0, 1)[0].row.commit.id,
      revisions[0],
    );
    assertEqual("deep: replay still keeps the decoded cache bounded", deep.pageCache.size, 2);
    assertTrue(
      "deep: replay walks page handles rather than offset cursors",
      fetchRequests.slice(requestStart).every((request) => !request.url.includes("skip=")),
    );
  }

  // ── A missing visible page is replayed in place ──────────────
  {
    const container = document.getElementById("tab-git");
    container.clientHeight = 44;
    container.scrollTop = 0;
    const total = 6;
    const revisions = Array.from({ length: total }, (_value, index) =>
      (index + 2000).toString(16).padStart(40, "0"),
    );
    const commits = revisions.map((revision, index) =>
      commit(
        revision,
        index + 1 < total ? [revisions[index + 1]] : [],
        `replay commit ${index}`,
        index === 0
          ? [{ id: "refs/heads/main", name: "main", kind: "branch", is_head: true }]
          : undefined,
      ),
    );
    const replayed = internals.emptyState();
    replayed.headRevision = revisions[0];
    internals.setStateForTests(replayed);
    for (let page = 0; page < 3; page += 1) {
      const pageCommits = commits.slice(page * 2, page * 2 + 2);
      const wire = historyPage(page, pageCommits, total, revisions[0]);
      internals.appendPage(pageCommits, wire.cursor, wire);
    }
    assertTrue("replay window: first page begins evicted", !replayed.pageCache.peek(0));
    responses.clear();
    responses.set("/api/git/log", (url) => {
      const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
      const page = Number(cursor?.split(":")[1] ?? 0);
      const pageCommits = commits.slice(page * 2, page * 2 + 2);
      return historyPage(page, pageCommits, total, revisions[0]);
    });
    internals.renderPanel();
    // A pending page shows the shape of the rows it stands in for, and
    // names itself only to a screen reader. See design-system.md,
    // "Loading States Are Shapes, Not Sentences".
    assertContains(
      "replay window: missing rows show a skeleton",
      container.innerHTML,
      "git-history-skeleton",
    );
    assertNotContains(
      "replay window: missing rows carry no visible loading text",
      container.textContent,
      "Loading history",
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));
    const rows = container.querySelectorAll(".git-graph-row");
    assertEqual("replay window: exact first row returns", rows[0].dataset.revision, revisions[0]);
    assertEqual("replay window: visible range fills after replay", rows.length, 3);
    assertEqual("replay window: decoded cache stays bounded", replayed.pageCache.size, 2);
    container.clientHeight = undefined;
    container.scrollTop = 0;
  }

  // ── Chrome above the list does not shift the resolved window ──
  //
  // The header tally lives above `.git-graph-list` inside the shared
  // scroller, so `scrollTop` carries height the virtualized window knows
  // nothing about. The panel converts between the two coordinate spaces.
  // Without that conversion the `scrollTop` written back on a segment
  // rebase lands short by the tally's height, which is what this pins.
  {
    const container = document.getElementById("tab-git");
    const deepRows = 400;
    const revisions = Array.from({ length: deepRows }, (_value, index) =>
      (index + 9000).toString(16).padStart(40, "0"),
    );
    const commits = revisions.map((revision, index) =>
      commit(revision, index + 1 < deepRows ? [revisions[index + 1]] : [], `origin ${index}`),
    );

    /**
     * Scroll deep enough to force a segment rebase and report the
     * `scrollTop` the panel writes back.
     *
     * @param {number} chrome height of the tally above the list
     * @returns {number}
     */
    const rebasedScrollTop = async (chrome) => {
      container.clientHeight = 44;
      container.scrollTop = 0;
      const fresh = internals.emptyState();
      fresh.pageCache.put({
        page: 0,
        startOrdinal: 0,
        commits,
        checkpoint: {
          version: 1,
          priorSwimlanes: [],
          colorIndex: -1,
          headRevision: revisions[0],
          scopeFingerprint: "scope",
        },
        pageCursor: "page-0",
        nextCursor: null,
        previousCursor: null,
      });
      fresh.rowCount = commits.length;
      fresh.virtualWindow.setRowCount(commits.length);
      fresh.scopeFingerprint = "scope";
      internals.setStateForTests(fresh);
      internals.renderPanel();
      await new Promise((resolve) => setTimeout(resolve, 0));
      const summary = container.querySelector(".git-history-summary");
      summary.offsetHeight = chrome;
      internals.invalidateHistoryOrigin();
      // Past the later overscan edge, so the segment must rebase.
      container.scrollTop = 22 * 300 + chrome;
      internals.renderVirtualRows();
      await new Promise((resolve) => setTimeout(resolve, 0));
      return container.scrollTop;
    };

    const withoutChrome = await rebasedScrollTop(0);
    const withChrome = await rebasedScrollTop(30);
    assertEqual("scroll origin: chrome above the list is measured", internals.historyOrigin(), 30);
    assertTrue(
      "scroll origin: the fixture actually rebased",
      withoutChrome !== 22 * 300 && withoutChrome > 0,
    );
    assertEqual(
      "scroll origin: a rebase writes back through the tally's height",
      withChrome,
      withoutChrome + 30,
    );

    const summary = container.querySelector(".git-history-summary");
    summary.offsetHeight = 0;
    internals.invalidateHistoryOrigin();
    container.clientHeight = undefined;
    container.scrollTop = 0;
  }

  // ── The tally is the Commits tab's toolbar, in the navigation's slot ──
  //
  // With the shell's toolbar slot, the tally fills it, so the slot is never
  // empty and the list starts at the panel's top, where the Files tree starts.
  {
    const container = document.getElementById("tab-git");
    const toolbar = document.register("nav-toolbar-git", document.createElement("div"));
    const shipped = document.createElement("div");
    shipped.className = "git-history-summary";
    toolbar.appendChild(shipped);
    const revisions = [SHA_A, SHA_B];
    const fresh = internals.emptyState();
    fresh.pageCache.put({
      page: 0,
      startOrdinal: 0,
      commits: [commit(SHA_A, [SHA_B], "second"), commit(SHA_B, [], "first")],
      checkpoint: {
        version: 1,
        priorSwimlanes: [],
        colorIndex: -1,
        headRevision: revisions[0],
        scopeFingerprint: "scope",
      },
      pageCursor: "page-0",
      nextCursor: null,
      previousCursor: null,
    });
    fresh.rowCount = 2;
    fresh.virtualWindow.setRowCount(2);
    fresh.scopeFingerprint = "scope";
    fresh.summary = { commitCount: 2, firstCommitAt: null };
    internals.setStateForTests(fresh);
    // A panel showing its first list: the earlier scenarios left one mounted.
    container.replaceChildren();
    internals.renderPanel();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const tally = toolbar.querySelector(".git-history-summary");
    assertTrue("toolbar: the tally fills the slot", tally?.textContent === "2 commits");
    assertTrue(
      "toolbar: the list starts at the panel's top",
      container.querySelector(".git-history-summary") === null &&
        container.children[0]?.className === "git-graph-list",
    );
    assertEqual("toolbar: nothing above the list shifts it", internals.historyOrigin(), 0);
    // History that cannot load settles the toolbar at its height, rather than leaving the
    // pending tally pulsing over a failure.
    const failedState = internals.emptyState();
    failedState.failed = true;
    internals.setStateForTests(failedState);
    container.replaceChildren();
    internals.renderPanel();
    assertTrue(
      "toolbar: a failed history settles the tally",
      toolbar.textContent === "History unavailable" &&
        toolbar.querySelector(".tally-pending") === null &&
        toolbar.querySelector(".git-history-summary") !== null,
    );
    document.byId.delete("nav-toolbar-git");
    toolbar.remove();
    internals.setStateForTests(internals.emptyState());
    internals.renderPanel();
  }

  // ── The panel mounts a logical window, not its decoded working set ──
  {
    const container = document.getElementById("tab-git");
    container.clientHeight = 44;
    container.scrollTop = 0;
    const virtualized = internals.emptyState();
    const commits = [
      commit(SHA_G, [SHA_B], "window one"),
      commit(SHA_B, [SHA_C], "window two"),
      commit(SHA_C, [SHA_D], "window three"),
      commit(SHA_D, [SHA_E], "window four"),
      commit(SHA_E, [], "window five"),
    ];
    virtualized.pageCache.put({
      page: 0,
      startOrdinal: 0,
      commits,
      checkpoint: {
        version: 1,
        priorSwimlanes: [],
        colorIndex: -1,
        headRevision: SHA_G,
        scopeFingerprint: "scope",
      },
      pageCursor: "page-0",
      nextCursor: null,
      previousCursor: null,
    });
    virtualized.rowCount = commits.length;
    virtualized.virtualWindow.setRowCount(commits.length);
    virtualized.selectedId = SHA_E;
    internals.setStateForTests(virtualized);
    internals.renderPanel();

    let rows = container.querySelectorAll(".git-graph-row");
    assertEqual("virtual panel: mounted rows obey the hard bound", rows.length, 3);
    assertEqual("virtual panel: first window starts at ordinal zero", rows[0].dataset.ordinal, "0");
    assertTrue(
      "virtual panel: unmounted selection has no false selected row",
      !rows.some((row) => row.classList.contains("selected")),
    );

    const tooltipCountBeforeUnmount = shownTooltips.length;
    let hoverAbortSignal;
    responses.set(
      `/api/git/commit/${SHA_G}`,
      (_url, options) =>
        new Promise((resolve) => {
          hoverAbortSignal = options?.signal;
          if (hoverAbortSignal?.aborted) {
            resolve({ httpStatus: 499, body: {} });
            return;
          }
          hoverAbortSignal?.addEventListener(
            "abort",
            () => resolve({ httpStatus: 499, body: {} }),
            { once: true },
          );
        }),
    );
    rows[0]._hovered = true;
    rows[0].dispatch("mouseenter");
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertTrue("virtual panel: hover detail has a cancellation signal", hoverAbortSignal);
    rows[0].focus();
    container.scrollTop = 66;
    internals.renderVirtualRows();
    await new Promise((resolve) => setTimeout(resolve, 0));
    rows = container.querySelectorAll(".git-graph-row");
    assertEqual("virtual panel: scrolled window remains bounded", rows.length, 3);
    assertEqual("virtual panel: scrolled window advances ordinals", rows[0].dataset.ordinal, "2");

    rows = container.querySelectorAll(".git-graph-row");
    assertTrue(
      "virtual panel: selection returns when its row remounts",
      rows[2].classList.contains("selected"),
    );
    assertTrue(
      "virtual panel: unmounted focus transfers to the scroller",
      document.activeElement === container,
    );
    assertEqual(
      "virtual panel: unmount cancels pending hover work",
      shownTooltips.length,
      tooltipCountBeforeUnmount,
    );
    assertTrue("virtual panel: unmount aborts in-flight hover detail", hoverAbortSignal.aborted);

    container.scrollTop = 0;
    internals.renderVirtualRows();
    rows = container.querySelectorAll(".git-graph-row");
    assertTrue(
      "virtual panel: logical focus returns when its row remounts",
      document.activeElement === rows[0],
    );
    container.clientHeight = undefined;
    container.scrollTop = 0;
  }

  // ── Panel states ───────────────────────────────────────────
  {
    const container = document.getElementById("tab-git");

    internals.setStateForTests({ ...internals.emptyState(), loading: true });
    internals.renderPanel();
    assertContains(
      "panel: first load draws skeleton rows",
      container.innerHTML,
      "git-history-skeleton",
    );
    assertNotContains(
      "panel: first load carries no visible loading text",
      container.textContent,
      "Loading",
    );
    assertNotContains("panel: first load uses no spinner", container.innerHTML, "spinner");

    internals.setStateForTests({ ...internals.emptyState(), failed: true });
    internals.renderPanel();
    assertContains("panel: failure state", container.innerHTML, "Could not read");

    internals.setStateForTests(internals.emptyState());
    internals.renderPanel();
    // A repository with no commits is not a failure and must not read
    // like one.
    assertContains("panel: empty repository", container.innerHTML, "No commits yet");
    assertNotContains("panel: empty is not an error", container.innerHTML, "Could not");
    assertEqual(
      "panel: empty offers refresh",
      container.querySelectorAll(".git-panel-refresh").length,
      1,
    );
  }

  // ── Rows render with graph, badges, and meta ───────────────
  {
    const container = document.getElementById("tab-git");
    internals.setStateForTests(internals.emptyState());
    appendTestPage(
      [
        commit(SHA_A, [SHA_B], "tip commit", [
          { id: "refs/heads/main", name: "main", kind: "branch", is_head: true },
        ]),
        commit(SHA_B, [], "root commit"),
        commit(SHA_F, [], "tooltip-only commit"),
      ],
      null,
    );
    internals.renderPanel();

    const rows = container.querySelectorAll(".git-graph-row");
    assertEqual("rows: one per commit", rows.length, 3);
    assertEqual("rows: revision on the element", rows[0].dataset.revision, SHA_A);
    assertTrue(
      "rows: gutter holds an svg",
      rows[0].querySelectorAll(".git-graph-gutter").length === 1,
    );
    assertContains("rows: subject rendered", rows[0].innerHTML, "tip commit");
    assertContains("rows: badge rendered", rows[0].innerHTML, "main");
    // A row set is one Tab stop, not one stop per mounted commit.
    assertEqual("rows: first row is the roving anchor", rows[0].getAttribute("tabindex"), "0");
    assertEqual("rows: other rows leave the Tab order", rows[1].getAttribute("tabindex"), "-1");
    assertEqual("rows: exposed as buttons", rows[0].getAttribute("role"), "button");

    responses.set(`/api/git/commit/${SHA_A}`, {
      is_repo: true,
      commit: commit(SHA_A, [SHA_B], "first"),
      body: "verbose tooltip body",
      stats: { files_changed: 2, additions: 7, deletions: 3 },
      files: [],
      files_truncated: false,
    });
    shownTooltips.length = 0;
    const hidesBefore = tooltipHideCount;
    rows[0].focus();
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual("tooltip lifecycle: keyboard focus stays silent", shownTooltips.length, 0);

    rows[0]._hovered = true;
    rows[0].dispatch("mouseenter");
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual("tooltip lifecycle: hover shows one anchored summary", shownTooltips.length, 1);
    assertTrue("tooltip lifecycle: row is the anchor", shownTooltips[0].anchor === rows[0]);
    assertContains(
      "tooltip lifecycle: rich summary reaches shared tooltip",
      shownTooltips[0].html,
      "git-commit-summary-compact",
    );

    const hidesBeforePointerLeave = tooltipHideCount;
    rows[0]._hovered = false;
    rows[0].dispatch("mouseleave");
    assertTrue(
      "tooltip lifecycle: pointer leave dismisses despite keyboard focus",
      tooltipHideCount > hidesBeforePointerLeave,
    );

    let resolveDelayedTooltip;
    responses.set(
      `/api/git/commit/${SHA_F}`,
      () =>
        new Promise((resolve) => {
          resolveDelayedTooltip = resolve;
        }),
    );
    rows[2]._hovered = true;
    rows[2].dispatch("mouseenter");
    await new Promise((resolve) => setTimeout(resolve, 10));
    rows[2].focus();
    const tooltipCountBeforeKeyboardSelection = shownTooltips.length;
    const hidesBeforeKeyboardSelection = tooltipHideCount;
    rows[2].dispatch("keydown", keyboardEvent("Enter"));
    assertTrue(
      "tooltip lifecycle: keyboard selection dismisses immediately",
      tooltipHideCount > hidesBeforeKeyboardSelection,
    );
    resolveDelayedTooltip({
      is_repo: true,
      commit: commit(SHA_F, [], "tooltip-only commit"),
      body: "",
      stats: { files_changed: 1, additions: 1, deletions: 1 },
      files: [],
      files_truncated: false,
    });
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual(
      "tooltip lifecycle: stale pointer detail cannot reopen after keyboard selection",
      shownTooltips.length,
      tooltipCountBeforeKeyboardSelection,
    );
    rows[2]._hovered = false;
    assertTrue("tooltip lifecycle: dismissal remains observable", tooltipHideCount > hidesBefore);
  }

  // ── Selection and stale-response handling ──────────────────
  {
    responses.clear();
    responses.set(`/api/git/commit/${SHA_A}`, {
      is_repo: true,
      commit: commit(SHA_A, [], "first"),
      body: "",
      stats: { files_changed: 1, additions: 1, deletions: 0 },
      files: [{ path: "one.js", status: "modified", additions: 1, deletions: 0 }],
      files_truncated: false,
    });
    responses.set(`/api/git/commit/${SHA_B}`, {
      is_repo: true,
      commit: commit(SHA_B, [], "second"),
      body: "",
      stats: { files_changed: 1, additions: 1, deletions: 0 },
      files: [{ path: "two.js", status: "modified", additions: 1, deletions: 0 }],
      files_truncated: false,
    });

    const container = document.getElementById("tab-git");
    const rows = container.querySelectorAll(".git-graph-row");
    previewHtml = '<div class="git-commit-view">prior commit</div>';
    rows[0].dispatch("click");
    assertContains("selection: retains prior content while preparing", previewHtml, "prior commit");
    await new Promise((resolve) => setTimeout(resolve, 0));
    assertContains("selection: renders the clicked commit", previewHtml, "first");
    assertTrue("selection: row is marked", rows[0].classList.contains("selected"));
    // A commit is a selection like any other, so it owns the URL while
    // shown — replaced, not pushed, so skimming a history list does not
    // bury the reader's entry point.
    assertEqual(
      "selection: writes its own route",
      replacedRoutes[replacedRoutes.length - 1],
      `/commit/${SHA_A}`,
    );

    // Two selections in flight: the later one must win regardless of
    // which response lands first.
    const before = fetchCount;
    const canceledBefore = canceledDiffRevisions.length;
    rows[1].dispatch("click");
    assertEqual(
      "selection: cancels obsolete diff work while retaining its DOM",
      canceledDiffRevisions.slice(canceledBefore),
      [SHA_A],
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    assertContains("selection: switches to the newer commit", previewHtml, "second");
    assertTrue("selection: issued a request", fetchCount > before);

    // Re-selecting a cached commit must not hit the network again.
    const cachedBefore = fetchCount;
    rows[0].dispatch("click");
    await new Promise((resolve) => setTimeout(resolve, 0));
    assertEqual("selection: cache avoids a refetch", fetchCount, cachedBefore);

    // A shell navigation owns the preview after it happens. A late Git
    // response must not replace the newer file/navigation surface.
    let resolveDelayed;
    responses.set(
      `/api/git/commit/${SHA_D}`,
      () =>
        new Promise((resolve) => {
          resolveDelayed = resolve;
        }),
    );
    const delayedSelection = internals.selectCommit(SHA_D);
    await new Promise((resolve) => setTimeout(resolve, 0));
    const fileClaim = sandbox.MetabrowserShell.claimPreview("file");
    sandbox.MetabrowserShell.renderPreviewHtml("<div>file preview wins</div>", fileClaim);
    resolveDelayed({
      is_repo: true,
      commit: commit(SHA_D, [], "delayed commit"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    await delayedSelection;
    assertContains("selection: newer preview owner wins", previewHtml, "file preview wins");
    assertNotContains("selection: delayed commit is discarded", previewHtml, "delayed commit");
  }

  // ── Nav-like row keyboard contract ─────────────────────────
  {
    const container = document.getElementById("tab-git");
    internals.setStateForTests(internals.emptyState());
    appendTestPage(
      [commit(SHA_A, [SHA_B], "keyboard first"), commit(SHA_B, [], "keyboard second")],
      null,
    );
    internals.renderPanel();
    const rows = container.querySelectorAll(".git-graph-row");

    rows[0].focus();
    const down = keyboardEvent("ArrowDown");
    rows[0].dispatch("keydown", down);
    assertTrue("keyboard: handled down prevents page scroll", down.defaultPrevented);
    assertTrue("keyboard: down focuses the next commit", document.activeElement === rows[1]);
    assertEqual(
      "keyboard: down opens the next commit",
      internals.stateForTests().selectedId,
      SHA_B,
    );
    assertEqual(
      "keyboard: input task leaves the prior Tab anchor untouched",
      rows[0].getAttribute("tabindex"),
      "0",
    );
    assertEqual(
      "keyboard: input task does not promote the destination Tab anchor",
      rows[1].getAttribute("tabindex"),
      "-1",
    );
    // Focus and selection move in the input task; the focus-order write waits
    // for the selected view boundary so a retained diff cannot delay feedback.
    await new Promise((resolve) => setTimeout(resolve, 0));
    assertEqual("keyboard: prior row leaves the Tab order", rows[0].getAttribute("tabindex"), "-1");
    assertEqual("keyboard: destination becomes the anchor", rows[1].getAttribute("tabindex"), "0");
    assertEqual("keyboard: destination scrolls into view", rows[1].scrollCalls, [
      { block: "nearest" },
    ]);

    const routeCountAtEdge = replacedRoutes.length;
    const clamped = keyboardEvent("ArrowDown");
    rows[1].dispatch("keydown", clamped);
    assertTrue("keyboard: clamped down still prevents page scroll", clamped.defaultPrevented);
    assertTrue("keyboard: clamped down keeps focus", document.activeElement === rows[1]);
    assertEqual("keyboard: clamped edge does not reopen", replacedRoutes.length, routeCountAtEdge);

    const up = keyboardEvent("ArrowUp", { repeat: true });
    rows[1].dispatch("keydown", up);
    assertTrue("keyboard: repeated up is handled", up.defaultPrevented);
    assertTrue("keyboard: up focuses the prior commit", document.activeElement === rows[0]);
    assertEqual("keyboard: up opens the prior commit", internals.stateForTests().selectedId, SHA_A);

    const modified = keyboardEvent("ArrowDown", { altKey: true });
    rows[0].dispatch("keydown", modified);
    assertTrue("keyboard: modified arrow is ignored", !modified.defaultPrevented);
    assertTrue("keyboard: ignored arrow leaves focus alone", document.activeElement === rows[0]);
    await new Promise((resolve) => setTimeout(resolve, 0));

    // J and K are Down and Up here as in the file tree, under the arrows' guards,
    // and dismiss a pending pointer-owned tooltip before moving, as the arrows do.
    rows[0]._hovered = true;
    rows[0].dispatch("mouseenter");
    const hidesBeforeJ = tooltipHideCount;
    const j = keyboardEvent("j", { repeat: true });
    rows[0].dispatch("keydown", j);
    rows[0]._hovered = false;
    assertTrue("keyboard: j dismisses the hover tooltip", tooltipHideCount > hidesBeforeJ);
    assertTrue("keyboard: repeated j is handled", j.defaultPrevented);
    assertTrue("keyboard: j focuses the next commit", document.activeElement === rows[1]);
    assertEqual("keyboard: j opens the next commit", internals.stateForTests().selectedId, SHA_B);
    await new Promise((resolve) => setTimeout(resolve, 0));

    const k = keyboardEvent("k");
    rows[1].dispatch("keydown", k);
    assertTrue("keyboard: k is handled", k.defaultPrevented);
    assertTrue("keyboard: k focuses the prior commit", document.activeElement === rows[0]);
    assertEqual("keyboard: k opens the prior commit", internals.stateForTests().selectedId, SHA_A);
    await new Promise((resolve) => setTimeout(resolve, 0));

    // Letters match in either case, as the shortcut registry matches them, so
    // Caps Lock does not turn the aliases off.
    const capsLock = keyboardEvent("J");
    rows[0].dispatch("keydown", capsLock);
    assertTrue("keyboard: an unshifted capital J is handled", capsLock.defaultPrevented);
    assertTrue("keyboard: capital J focuses the next commit", document.activeElement === rows[1]);
    assertEqual(
      "keyboard: capital J opens the next commit",
      internals.stateForTests().selectedId,
      SHA_B,
    );
    await new Promise((resolve) => setTimeout(resolve, 0));

    for (const modifier of ["altKey", "ctrlKey", "metaKey"]) {
      for (const key of ["j", "k"]) {
        const chord = keyboardEvent(key, { [modifier]: true });
        rows[1].dispatch("keydown", chord);
        assertTrue(`keyboard: ${modifier} with ${key} is ignored`, !chord.defaultPrevented);
      }
    }
    assertTrue("keyboard: ignored chords leave focus alone", document.activeElement === rows[1]);
    assertEqual(
      "keyboard: ignored chords leave the selection alone",
      internals.stateForTests().selectedId,
      SHA_B,
    );

    // Shift never changes a row key: Shift with K, J, or an arrow moves and
    // opens, as without it.
    for (const [key, from, to, revision] of [
      ["K", 1, 0, SHA_A],
      ["J", 0, 1, SHA_B],
      ["ArrowUp", 1, 0, SHA_A],
      ["ArrowDown", 0, 1, SHA_B],
    ]) {
      const shifted = keyboardEvent(key, { shiftKey: true });
      rows[from].dispatch("keydown", shifted);
      assertTrue(`keyboard: Shift with ${key} is handled`, shifted.defaultPrevented);
      assertTrue(`keyboard: Shift with ${key} moves focus`, document.activeElement === rows[to]);
      assertEqual(
        `keyboard: Shift with ${key} opens the commit`,
        internals.stateForTests().selectedId,
        revision,
      );
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    // With Commits already in front and no landing waiting, the Commits tab's key, `H`, only
    // moves focus, back to the row the reader left. A switch to Commits lands on the newest
    // row instead ("The Commits key lands on the newest row", below).
    document.activeElement = null;
    assertTrue("focusRow: the roving row takes focus", internals.focusCommitRow());
    assertTrue(
      "focusRow: in front, focus lands on the row left",
      document.activeElement === rows[1],
    );
  }

  // ── Preparation overlaps and reuses pointer intent ─────────
  {
    internals.setStateForTests(internals.emptyState());
    responses.clear();
    const container = document.getElementById("tab-git");
    appendTestPage(
      [commit(SHA_E, [], "prepared first"), commit(SHA_B, [], "prepared second")],
      "prepared-next",
    );
    appendTestPage([commit(SHA_C, [], "prepared third")], null);
    internals.renderPanel();
    const rows = container.querySelectorAll(".git-graph-row");
    let resolveDetail;
    let resolveComparison;
    responses.set(
      `/api/git/commit/${SHA_E}`,
      () =>
        new Promise((resolve) => {
          resolveDetail = resolve;
        }),
    );
    comparisonResponder = () =>
      new Promise((resolve) => {
        resolveComparison = resolve;
      });
    const comparisonsBefore = comparisonFetches.length;
    const detailsBefore = fetchCount;
    const previewPane =
      document.getElementById("preview-pane") ??
      document.register("preview-pane", document.createElement("div"));
    const priorCommit = document.createElement("div");
    priorCommit.className = "git-commit-view";
    priorCommit.textContent = "prior staged commit";
    previewPane.replaceChildren(priorCommit);
    rows[0]._hovered = true;
    rows[0].dispatch("mouseenter");
    assertEqual(
      "prepare: entering a row does not start comparison work before stable intent",
      comparisonFetches.length,
      comparisonsBefore,
    );
    assertEqual(
      "prepare: entering a row does not start detail work before stable intent",
      fetchCount,
      detailsBefore,
    );
    rows[0]._hovered = false;
    rows[0].dispatch("mouseleave");
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual(
      "prepare: scrolling past a row starts no comparison work",
      comparisonFetches.length,
      comparisonsBefore,
    );
    assertEqual("prepare: scrolling past a row starts no detail work", fetchCount, detailsBefore);

    rows[0]._hovered = true;
    rows[0].dispatch("mouseenter");
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual(
      "prepare: pointer intent starts one comparison",
      comparisonFetches.length,
      comparisonsBefore + 1,
    );

    const select = internals.selectCommit(SHA_E);
    await Promise.resolve();
    assertEqual(
      "pending: retained preview is aria-busy",
      previewPane.getAttribute("aria-busy"),
      "true",
    );
    assertTrue(
      "pending: retained preview uses the shared pending class",
      previewPane.classList.contains("preview-navigation-pending"),
    );
    assertContains(
      "pending: old commit remains mounted",
      previewPane.textContent,
      "prior staged commit",
    );
    assertEqual(
      "prepare: selection reuses pointer comparison",
      comparisonFetches.length,
      comparisonsBefore + 1,
    );
    assertEqual(
      "prepare: selection joins the pointer detail request",
      fetchCount,
      detailsBefore + 1,
    );
    resolveDetail({
      is_repo: true,
      commit: commit(SHA_E, [], "prepared first"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    resolveComparison({ comparison_id: SHA_E });
    await select;
    assertContains("prepare: selected commit is eventually shown", previewHtml, "prepared first");
    assertEqual(
      "pending: aria-busy clears after the swap",
      previewPane.getAttribute("aria-busy"),
      null,
    );
    assertTrue(
      "pending: class clears after the swap",
      !previewPane.classList.contains("preview-navigation-pending"),
    );

    comparisonResponder = async (revision) => ({ comparison_id: revision });
    const selectedComparisons = comparisonFetches.length;
    const selectedDetails = fetchCount;
    const selectedTooltips = shownTooltips.length;
    rows[0]._hovered = false;
    rows[0].dispatch("mouseleave");
    rows[0]._hovered = true;
    rows[0].dispatch("mouseenter");
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual(
      "prepare: re-entering the current selected row does not refetch its comparison",
      comparisonFetches.length,
      selectedComparisons,
    );
    assertEqual("prepare: selected-row tooltip reuses detail", fetchCount, selectedDetails);
    assertEqual(
      "prepare: selected-row tooltip still opens",
      shownTooltips.length,
      selectedTooltips + 1,
    );

    for (const [revision, subject] of [
      [SHA_B, "prepared second"],
      [SHA_C, "prepared third"],
    ]) {
      responses.set(`/api/git/commit/${revision}`, {
        is_repo: true,
        commit: commit(revision, [], subject),
        body: "",
        stats: { files_changed: 0, additions: 0, deletions: 0 },
        files: [],
        files_truncated: false,
      });
    }
    const slotBefore = comparisonFetches.length;
    rows[0]._hovered = false;
    rows[1]._hovered = true;
    rows[1].dispatch("mouseenter");
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual(
      "prepare: a different row can still prepare after selected-row hover",
      comparisonFetches.length,
      slotBefore + 1,
    );
    const firstSignal = comparisonFetches[slotBefore].signal;
    rows[1]._hovered = false;
    rows[2]._hovered = true;
    rows[2].dispatch("mouseenter");
    assertTrue("prepare: newer pointer intent aborts the old slot", firstSignal.aborted);
    assertEqual(
      "prepare: replacement waits for stable intent",
      comparisonFetches.length,
      slotBefore + 1,
    );
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual(
      "prepare: one replacement request serves the newer intent",
      comparisonFetches.length,
      slotBefore + 2,
    );
    rows[2]._hovered = false;
    rows[2].dispatch("mouseleave");

    // A file claiming the pane leaves selectedId intact, but its claim
    // invalidates the Git selection. Returning must prepare and reopen it.
    sandbox.MetabrowserShell.claimPreview("file");
    const reopenComparisons = comparisonFetches.length;
    const reopenMounts = renderedDiffRevisions.length;
    rows[0]._hovered = true;
    rows[0].dispatch("mouseenter");
    await new Promise((resolve) => setTimeout(resolve, 10));
    assertEqual(
      "prepare: another preview owner permits the same selected revision to prepare",
      comparisonFetches.length,
      reopenComparisons + 1,
    );
    await internals.selectCommit(SHA_E);
    assertEqual(
      "prepare: reopening joins the comparison prepared after another owner",
      comparisonFetches.length,
      reopenComparisons + 1,
    );
    assertEqual(
      "prepare: reopening mounts the selected revision",
      renderedDiffRevisions.length,
      reopenMounts + 1,
    );
    assertContains("prepare: reopening shows the same commit", previewHtml, "prepared first");
    rows[0]._hovered = false;
    rows[0].dispatch("mouseleave");
  }

  // Initial loading must not replace a connected stage or a ready commit while
  // the browser defers paint. Timers and frames advance independently.
  {
    const originalTimeout = sandbox.setTimeout;
    const originalClearTimeout = sandbox.clearTimeout;
    const originalAssets = sandbox.metabrowser.ensureKindAssets;
    const originalFreshness = sandbox.MetabrowserShell.sourceFreshness;
    const timers = new Map();
    const frames = [];
    let clock = 0;
    let nextTimer = 0;
    sandbox.setTimeout = (callback, delay) => {
      const id = ++nextTimer;
      timers.set(id, { callback, at: clock + delay });
      return id;
    };
    sandbox.clearTimeout = (id) => timers.delete(id);
    sandbox.requestAnimationFrame = (callback) => frames.push(callback);
    const advance = (milliseconds) => {
      clock += milliseconds;
      for (const [id, timer] of [...timers]) {
        if (timer.at <= clock && timers.delete(id)) {
          timer.callback();
        }
      }
    };
    const until = async (predicate, label) => {
      for (let turn = 0; turn < 100; turn += 1) {
        if (predicate()) {
          return;
        }
        await Promise.resolve();
      }
      throw new Error(`loading session did not reach ${label}`);
    };
    const pane = document.getElementById("preview-pane");
    const checkpoints = {};
    try {
      for (const boundary of ["paint", "assets"]) {
        const revision = (boundary === "paint" ? "21" : "22").repeat(20);
        responses.set(`/api/git/commit/${revision}`, {
          is_repo: true,
          commit: commit(revision, [], `ready before ${boundary}`),
          body: "",
          stats: { files_changed: 1, additions: 1, deletions: 0 },
          files: [{ path: "ready.js", status: "modified", additions: 1, deletions: 0 }],
          files_truncated: false,
        });
        let releaseAssets;
        const heldAssets = new Promise((resolve) => {
          releaseAssets = resolve;
        });
        sandbox.metabrowser.ensureKindAssets =
          boundary === "assets" ? () => heldAssets : originalAssets;
        pane.replaceChildren();
        const selecting = internals.selectCommit(revision);
        await until(
          () =>
            boundary === "paint"
              ? frames.length > 0
              : pane.querySelector(".git-commit-stage") !== null,
          boundary,
        );
        const stage = pane.querySelector(".git-commit-stage");
        advance(120);
        if (boundary === "paint") {
          const ready = pane.querySelector(".git-commit-stage");
          assertTrue("loading: paused paint retains the promoted commit", ready === stage);
          assertNotContains(
            "loading: paused paint never restores the spinner",
            previewHtml,
            "Loading commit",
          );
          checkpoints[boundary] = {
            readyConnected: stage.isConnected,
            loading: previewHtml.includes("Loading commit"),
          };
        } else {
          assertTrue(
            "loading: delayed spinner preserves the connected mount stage",
            stage.isConnected,
          );
          assertContains(
            "loading: slow initial assets still show the standard spinner",
            previewHtml,
            'class="spinner"',
          );
          checkpoints[boundary] = {
            stageConnected: stage.isConnected,
            spinner: previewHtml.includes('class="spinner"'),
          };
          releaseAssets();
          await until(() => frames.length > 0, "assets released");
        }
        assertEqual(
          "loading: busy state remains until paint",
          pane.getAttribute("aria-busy"),
          "true",
        );
        frames.shift()();
        frames.shift()();
        await selecting;
        assertContains(
          `loading: ${boundary} ends on the selected commit`,
          previewHtml,
          `ready before ${boundary}`,
        );
        assertEqual(
          `loading: ${boundary} mounts the selected diff`,
          renderedDiffRevisions.at(-1),
          revision,
        );
        assertTrue(
          `loading: ${boundary} mounted diff stays connected`,
          renderedDiffConnections.at(-1),
        );
        assertEqual(`loading: ${boundary} leaves no pending timer`, timers.size, 0);
        assertEqual("loading: paint clears busy state", pane.getAttribute("aria-busy"), null);
      }
      // An older paint callback must not finish the newer selection's busy state.
      const older = "23".repeat(20);
      const newer = "24".repeat(20);
      let releaseNewer;
      sandbox.metabrowser.ensureKindAssets = originalAssets;
      for (const revision of [older, newer]) {
        const detail = {
          is_repo: true,
          commit: commit(revision, [], revision === older ? "older ready" : "newer ready"),
          body: "",
          stats: { files_changed: 0, additions: 0, deletions: 0 },
          files: [],
          files_truncated: false,
        };
        responses.set(
          `/api/git/commit/${revision}`,
          revision === older
            ? detail
            : () =>
                new Promise((resolve) => {
                  releaseNewer = () => resolve(detail);
                }),
        );
      }
      const selectingOlder = internals.selectCommit(older);
      await until(() => frames.length > 0, "older paint");
      const selectingNewer = internals.selectCommit(newer);
      await until(() => releaseNewer !== undefined, "newer detail request");
      const newerClaim = pane.getAttribute("data-preview-pending-claim");
      frames.shift()();
      frames.shift()();
      await selectingOlder;
      assertEqual(
        "loading: older paint preserves newer busy state",
        pane.getAttribute("aria-busy"),
        "true",
      );
      assertEqual(
        "loading: older paint preserves newer claim",
        pane.getAttribute("data-preview-pending-claim"),
        newerClaim,
      );
      checkpoints.crossing = {
        newerBusyAfterOlderPaint: pane.getAttribute("aria-busy") === "true",
      };
      releaseNewer();
      await until(() => frames.length > 0, "newer paint");
      frames.shift()();
      frames.shift()();
      await selectingNewer;
      assertContains(
        "loading: crossing selections ends on newer commit",
        previewHtml,
        "newer ready",
      );
      assertEqual(
        "loading: newer paint clears its own busy state",
        pane.getAttribute("aria-busy"),
        null,
      );
      // A missing commit can wait for freshness assets after another selection starts.
      const missing = "27".repeat(20);
      const found = "28".repeat(20);
      let releaseFreshness;
      let releaseFound;
      sandbox.MetabrowserShell.sourceFreshness = () =>
        new Promise((resolve) => {
          releaseFreshness = resolve;
        });
      responses.set(`/api/git/commit/${missing}`, {
        httpStatus: 404,
        body: { error: "unknown revision", code: "commit_not_found" },
      });
      responses.set(
        `/api/git/commit/${found}`,
        () =>
          new Promise((resolve) => {
            releaseFound = resolve;
          }),
      );
      const selectingMissing = internals.selectCommit(missing);
      await until(() => releaseFreshness !== undefined, "missing commit freshness assets");
      const selectingFound = internals.selectCommit(found);
      await until(() => releaseFound !== undefined, "found commit detail");
      const foundClaim = pane.getAttribute("data-preview-pending-claim");
      releaseFreshness(null);
      await selectingMissing;
      assertEqual(
        "loading: missing completion preserves newer busy state",
        pane.getAttribute("aria-busy"),
        "true",
      );
      assertEqual(
        "loading: missing completion preserves newer claim",
        pane.getAttribute("data-preview-pending-claim"),
        foundClaim,
      );
      checkpoints.missing = { newerBusyAfterMissing: pane.getAttribute("aria-busy") === "true" };
      releaseFound({
        is_repo: true,
        commit: commit(found, [], "found after missing"),
        body: "",
        stats: { files_changed: 0, additions: 0, deletions: 0 },
        files: [],
        files_truncated: false,
      });
      await until(() => frames.length > 0, "found commit paint");
      frames.shift()();
      frames.shift()();
      await selectingFound;
      assertContains(
        "loading: missing crossing ends on newer commit",
        previewHtml,
        "found after missing",
      );
      assertEqual(
        "loading: found commit paint clears its busy state",
        pane.getAttribute("aria-busy"),
        null,
      );
      commitLoadingSession = checkpoints;
    } finally {
      sandbox.setTimeout = originalTimeout;
      sandbox.clearTimeout = originalClearTimeout;
      sandbox.metabrowser.ensureKindAssets = originalAssets;
      sandbox.MetabrowserShell.sourceFreshness = originalFreshness;
      delete sandbox.requestAnimationFrame;
    }
  }

  // The renderer must never start on a stage a newer pane owner removed.
  // Resolve each real preparation boundary in turn; selection and comparison
  // remain the production state machine, not a simulated cancellation result.
  {
    const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
    const originalAssets = sandbox.metabrowser.ensureKindAssets;
    const originalComparison = comparisonResponder;
    const originalView = sandbox.metabrowser.getRegisteredView;
    for (const [index, boundary] of ["assets", "comparison", "renderer"].entries()) {
      const revision = `${index + 10}`.repeat(20);
      responses.set(`/api/git/commit/${revision}`, {
        is_repo: true,
        commit: commit(revision, [], `staged ${boundary}`),
        body: "",
        stats: { files_changed: 1, additions: 1, deletions: 0 },
        files: [{ path: "stage.js", status: "modified", additions: 1, deletions: 0 }],
        files_truncated: false,
      });
      let release;
      const held = new Promise((resolve) => {
        release = resolve;
      });
      sandbox.metabrowser.ensureKindAssets =
        boundary === "assets"
          ? async () => {
              await held;
              diffAssetsLoaded = true;
            }
          : originalAssets;
      comparisonResponder =
        boundary === "comparison"
          ? async () => {
              await held;
              return { comparison_id: revision };
            }
          : async () => ({ comparison_id: revision });
      sandbox.metabrowser.getRegisteredView = (kind, view) => {
        const registered = originalView(kind, view);
        if (!registered || boundary !== "renderer") {
          return registered;
        }
        return {
          render: async (host, context) => {
            const handle = await registered.render(host, context);
            await held;
            return handle;
          },
        };
      };
      const pane = document.getElementById("preview-pane");
      const prior = document.createElement("div");
      prior.textContent = `prior useful ${boundary}`;
      pane.replaceChildren(prior);
      const rendersBefore = renderedDiffRevisions.length;
      const disposedBefore = disposedDiffRevisions.length;
      const selecting = internals.selectCommit(revision);
      await tick();
      assertTrue(`stage ${boundary}: prior useful content remains connected`, prior.isConnected);
      assertEqual(
        `stage ${boundary}: exactly one pending connected wrapper`,
        pane.querySelectorAll(".preview-file-stage").length,
        1,
      );
      assertEqual(
        `stage ${boundary}: render waits for selected preparation`,
        renderedDiffRevisions.length,
        rendersBefore + (boundary === "renderer" ? 1 : 0),
      );
      const fileClaim = sandbox.MetabrowserShell.claimPreview("file");
      assertEqual(
        `stage ${boundary}: another owner immediately removes staging`,
        pane.querySelectorAll(".preview-file-stage").length,
        0,
      );
      sandbox.MetabrowserShell.renderPreviewHtml(
        `<div>file wins over ${boundary}</div>`,
        fileClaim,
      );
      release();
      await selecting;
      assertContains(
        `stage ${boundary}: late work preserves file owner`,
        previewHtml,
        `file wins over ${boundary}`,
      );
      assertEqual(
        `stage ${boundary}: stale preparation never starts a renderer`,
        renderedDiffRevisions.length,
        rendersBefore + (boundary === "renderer" ? 1 : 0),
      );
      assertEqual(
        `stage ${boundary}: returned stale handle is disposed`,
        disposedDiffRevisions.length,
        disposedBefore + (boundary === "renderer" ? 1 : 0),
      );
      assertEqual(
        `stage ${boundary}: no staged wrapper leaks`,
        pane.querySelectorAll(".preview-file-stage").length,
        0,
      );
    }
    sandbox.metabrowser.ensureKindAssets = originalAssets;
    comparisonResponder = originalComparison;
    sandbox.metabrowser.getRegisteredView = originalView;
  }

  // Use the actual shell claim boundary and production hydration scheduler:
  // a file or Pulls owner must stop old Git work while retaining its DOM.
  {
    const originalClaim = sandbox.MetabrowserShell.claimPreview;
    const originalFetch = sandbox.metabrowser.fetchPluginData;
    const originalView = sandbox.metabrowser.getRegisteredView;
    const app = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf8");
    const actualClaim = app.match(
      /\nfunction claimPreview\(owner, selection\) \{[\s\S]*?\n\}/,
    )?.[0];
    assertTrue("cross-owner: actual shell claim function found", Boolean(actualClaim));
    sandbox.cancelPendingFilePreviewStage = () => {
      pendingStageCleanup?.();
    };
    sandbox.pullPageHost = null;
    sandbox.retainedPullPageDispose = null;
    sandbox.clearPreviewNavigationState = (pane) => {
      pane.classList.remove("preview-navigation-pending");
      pane.removeAttribute("aria-busy");
      pane.removeAttribute("data-preview-pending-claim");
    };
    sandbox.previewPane = {
      claim: () => {
        previewClaim += 1;
        return previewClaim;
      },
    };
    vm.runInContext(actualClaim, sandbox, { filename: "actual-app-claimPreview.js" });
    sandbox.MetabrowserShell.claimPreview = sandbox.claimPreview;
    const flush = async () => {
      for (let turn = 0; turn < 4; turn += 1) {
        await new Promise((resolve) => setImmediate(resolve));
      }
    };
    const revision = "90".repeat(20);
    const detail = (id) => ({
      is_repo: true,
      commit: commit(id, [], "cross-owner commit"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    responses.set(`/api/git/commit/${revision}`, detail(revision));
    let releaseComparison;
    const comparisonReleases = [];
    let staleSuccesses = 0;
    sandbox.metabrowser.fetchPluginData = (plugin, route, params, options) => {
      comparisonFetches.push({ plugin, route, params, signal: options?.signal });
      return new Promise((resolve, reject) => {
        const signal = options.signal;
        signal.addEventListener(
          "abort",
          () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })),
          { once: true },
        );
        releaseComparison = () => {
          if (!signal.aborted) {
            staleSuccesses += 1;
            resolve({ comparison_id: params.revision });
          }
        };
        comparisonReleases.push(releaseComparison);
      });
    };
    const selecting = internals.selectCommit(revision);
    await flush();
    const pendingSignal = comparisonFetches.at(-1).signal;
    const mountedBefore = renderedDiffRevisions.length;
    const comparisonsBeforeReopen = comparisonFetches.length;
    const releaseOldComparison = releaseComparison;
    sandbox.MetabrowserShell.claimPreview("file", { folder: false, path: "controlled.txt" });
    assertTrue("cross-owner: file claim aborts pending Git comparison", pendingSignal.aborted);
    assertEqual(
      "cross-owner: file claim retains Git selection",
      internals.stateForTests().selectedId,
      revision,
    );
    // Reopen synchronously before the old canceled selection's finally runs.
    // Its cleanup must not clear the new preparation for this same revision.
    const reopening = internals.selectCommit(revision);
    releaseOldComparison();
    await selecting;
    assertEqual("cross-owner: canceled comparison cannot succeed later", staleSuccesses, 0);
    assertEqual(
      "cross-owner: canceled comparison never starts renderer",
      renderedDiffRevisions.length,
      mountedBefore,
    );
    await flush();
    const rejoining = internals.selectCommit(revision);
    await flush();
    assertEqual(
      "cross-owner: old selection cleanup preserves the new same-revision slot",
      comparisonFetches.length,
      comparisonsBeforeReopen + 1,
    );
    for (const release of comparisonReleases) {
      release();
    }
    await Promise.all([reopening, rejoining]);
    sandbox.metabrowser.fetchPluginData = originalFetch;

    const { createHydrationScheduler } = await import(
      require("node:url").pathToFileURL(
        path.join(repoRoot, "src/metabrowser/builtin_plugins/diff/diff-view.js"),
      ).href
    );
    const requests = [],
      frames = [];
    let oldRenders = 0,
      cancelCalls = 0;
    const hydration = createHydrationScheduler({
      now: () => 0,
      load: (id, signal) =>
        new Promise((resolve, reject) => {
          requests.push({ id, signal, resolve });
          signal.addEventListener(
            "abort",
            () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })),
            { once: true },
          );
        }),
      render: () => {
        oldRenders += 1;
        return "painted";
      },
      fail: () => {},
      abandon: () => {},
      frame: (callback) => {
        frames.push(callback);
        return callback;
      },
      cancelFrame: (callback) => {
        const at = frames.indexOf(callback);
        if (at >= 0) {
          frames.splice(at, 1);
        }
      },
      after: () => {
        throw new Error("no jump timer expected");
      },
      cancelAfter: () => {},
    });
    sandbox.metabrowser.getRegisteredView = () => ({
      render: async () => ({
        cancelPending: () => {
          cancelCalls += 1;
          hydration.dispose();
        },
        dispose: () => hydration.dispose(),
      }),
    });
    const mountedRevision = "91".repeat(20);
    responses.set(`/api/git/commit/${mountedRevision}`, detail(mountedRevision));
    await internals.selectCommit(mountedRevision);
    const retained = previewNode;
    const history = internals.stateForTests().pageCache;
    hydration.add("old-active", 0);
    hydration.add("old-queued", 1);
    hydration.setNearby([
      ["old-active", true],
      ["old-queued", true],
    ]);
    assertEqual("cross-owner: one active hydration and one queued", requests.length, 1);
    sandbox.MetabrowserShell.claimPreview("pull-request");
    assertEqual("cross-owner: Pulls claim cancels mounted Git work", cancelCalls, 1);
    assertTrue("cross-owner: active deferred request aborts", requests[0].signal.aborted);
    assertTrue("cross-owner: prior Git DOM stays connected", retained.isConnected);
    requests[0].resolve({});
    await flush();
    for (const frame of frames.splice(0)) {
      frame();
    }
    await flush();
    assertEqual("cross-owner: queued old request never starts", requests.length, 1);
    assertEqual("cross-owner: no old deferred answer renders", oldRenders, 0);
    assertTrue(
      "cross-owner: history pages retained",
      internals.stateForTests().pageCache === history,
    );
    assertEqual(
      "cross-owner: selected revision retained",
      internals.stateForTests().selectedId,
      mountedRevision,
    );
    sandbox.metabrowser.getRegisteredView = originalView;
    const comparisonsBefore = comparisonFetches.length;
    await internals.selectCommit(mountedRevision);
    assertEqual(
      "cross-owner: returning same selected Git revision prepares again",
      comparisonFetches.length,
      comparisonsBefore + 1,
    );
    assertContains(
      "cross-owner: returning Git renders its commit",
      previewHtml,
      "cross-owner commit",
    );
    assertEqual(
      "cross-owner: returning Git has no leaked stages",
      document.querySelectorAll(".preview-file-stage").length,
      0,
    );
    hydration.dispose();
    sandbox.MetabrowserShell.claimPreview = originalClaim;
  }

  // The commit diff another owner takes the pane from ends when that owner's content
  // replaces it, and its `L` with it. The shell's claim and install functions are lifted
  // from app.js; the registry and the plugin shortcut facade are production; the diff
  // stands in for diff-view.js, which attaches `L` on its layout chip and detaches it in
  // `dispose()` (tests/dom/diff-layout-fit-session.js pins that half).
  {
    const shell = sandbox.MetabrowserShell;
    const originals = {
      claimPreview: shell.claimPreview,
      renderPreviewHtml: shell.renderPreviewHtml,
      renderPreviewNode: shell.renderPreviewNode,
      view: sandbox.metabrowser.getRegisteredView,
    };
    const app = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf8");
    const lifted = [
      "claimPreview(owner, selection)",
      "finishRetainedPullPage()",
      "renderPreviewHtml(html, claim)",
      "renderPreviewNode(node, claim)",
    ].map((signature) => {
      const pattern = new RegExp(
        `\\nfunction ${signature.replace(/[()]/g, "\\$&")} \\{[\\s\\S]*?\\n\\}`,
      );
      const source = app.match(pattern)?.[0];
      assertTrue(`relinquished diff: app.js has ${signature}`, Boolean(source));
      return source ?? "";
    });
    sandbox.cancelPendingFilePreviewStage = () => pendingStageCleanup?.();
    sandbox.pullPageHost = null;
    sandbox.retainedPullPageDispose = null;
    sandbox.shellKeymap = null;
    sandbox.clearPreviewNavigationState = (pane) => {
      pane.classList.remove("preview-navigation-pending");
      pane.removeAttribute("aria-busy");
      pane.removeAttribute("data-preview-pending-claim");
    };
    sandbox.previewPane = {
      claim: () => {
        previewClaim += 1;
        return previewClaim;
      },
    };
    sandbox.isPreviewClaimCurrent = (claim) => claim === previewClaim;
    sandbox.disposeActivePluginViews = () => {};
    sandbox.animatePreviewContentArrival = () => {};
    vm.runInContext(lifted.join("\n"), sandbox, { filename: "app.js (lifted)" });
    shell.claimPreview = sandbox.claimPreview;
    shell.renderPreviewHtml = sandbox.renderPreviewHtml;
    shell.renderPreviewNode = sandbox.renderPreviewNode;

    for (const name of ["keyboard-shortcuts.js", "plugin-shortcuts.js"]) {
      const filename = path.join(repoRoot, "src/metabrowser/static", name);
      vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
    }
    const registry = sandbox.MetabrowserKeyboardShortcuts.create({ document });
    const facade = sandbox.MetabrowserPluginShortcuts;
    const detachRegistry = facade.attachShortcutRegistry(registry);
    /** What Help lists of the plugin keys: it lists a command with an attachment, live or not. */
    const helpKeys = () =>
      registry
        .snapshot("help", { includeInactive: true })
        .flatMap((group) => group.commands)
        .filter((command) => command.scope === "plugin")
        .map((command) => `${command.bindings.visible.join("")} ${command.copy.action}`);
    const mounts = [];
    sandbox.metabrowser.getRegisteredView = () => ({
      render: async (host, context) => {
        const root = document.createElement("div");
        const chip = document.createElement("button");
        root.appendChild(chip);
        host.appendChild(root);
        const layoutKey = facade.attachShortcut(chip, {
          activate: () => {},
          copy: {
            action: "Toggle diff layout",
            description: "Switch the diff between Split and Unified.",
            hint: "Layout",
          },
          group: "controls",
          id: "diff.layout",
          key: "l",
          order: 40,
        });
        const mount = { revision: context.revision, chip, canceled: 0, disposed: 0 };
        mounts.push(mount);
        return {
          cancelPending: () => {
            mount.canceled += 1;
          },
          dispose: () => {
            mount.disposed += 1;
            layoutKey.detach();
            root.remove();
          },
        };
      },
    });
    const revision = "92".repeat(20);
    responses.set(`/api/git/commit/${revision}`, {
      is_repo: true,
      commit: commit(revision, [], "relinquished commit"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });

    await internals.selectCommit(revision);
    const [first] = mounts;
    assertEqual("relinquished diff: the commit view mounts one diff", mounts.length, 1);
    assertEqual("relinquished diff: Help lists the diff's L", helpKeys(), ["L Toggle diff layout"]);

    shell.claimPreview("file", { folder: false, path: "after-commit.txt" });
    assertEqual("relinquished diff: a file claim cancels the diff's work", first.canceled, 1);
    assertEqual("relinquished diff: the diff waits for the file's content", first.disposed, 0);
    assertTrue("relinquished diff: the commit view stays on screen", first.chip.isConnected);
    assertEqual("relinquished diff: L stays while the diff is shown", helpKeys(), [
      "L Toggle diff layout",
    ]);
    // A second claim before the first one's content arrives keeps the one handoff.
    const fileClaim = shell.claimPreview("file", { folder: false, path: "later.txt" });
    assertEqual("relinquished diff: a second claim keeps the handoff", first.disposed, 0);

    shell.renderPreviewHtml('<div class="file-view">later.txt</div>', fileClaim);
    assertEqual("relinquished diff: the file's content disposes the diff", first.disposed, 1);
    assertEqual("relinquished diff: Help no longer lists L", helpKeys(), []);
    assertEqual(
      "relinquished diff: the chip keeps no aria-keyshortcuts",
      first.chip.getAttribute("aria-keyshortcuts"),
      null,
    );

    await internals.selectCommit(revision);
    const second = mounts[1];
    assertEqual("relinquished diff: showing the commit again mounts a diff", mounts.length, 2);
    assertEqual("relinquished diff: the earlier diff is disposed once", first.disposed, 1);
    assertEqual("relinquished diff: the new diff stays mounted", second?.disposed, 0);
    assertEqual("relinquished diff: Help lists L again", helpKeys(), ["L Toggle diff layout"]);
    assertEqual(
      "relinquished diff: L is on the new diff's chip",
      second?.chip.getAttribute("aria-keyshortcuts"),
      "L",
    );

    // The commit view's own replacement still disposes the diff it replaces.
    const replacement = "93".repeat(20);
    responses.set(`/api/git/commit/${replacement}`, {
      is_repo: true,
      commit: commit(replacement, [], "replacing commit"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    await internals.selectCommit(replacement);
    assertEqual("relinquished diff: the next commit disposes the shown diff", second?.disposed, 1);
    assertEqual("relinquished diff: one L for the shown commit", helpKeys(), [
      "L Toggle diff layout",
    ]);

    detachRegistry();
    registry.dispose();
    Object.assign(shell, {
      claimPreview: originals.claimPreview,
      renderPreviewHtml: originals.renderPreviewHtml,
      renderPreviewNode: originals.renderPreviewNode,
    });
    sandbox.metabrowser.getRegisteredView = originals.view;
    sandbox.retainedPullPageDispose = null;
  }

  // ── Changed files navigate through the shell ───────────────
  {
    openedPaths.length = 0;
    const preview = new FakeElement("div", document);
    const row = new FakeElement("button", document);
    row.classList.add("git-commit-file");
    row.dataset.path = "one.js";
    preview.appendChild(row);
    internals.wireCommitFileNavigation(preview);
    row.dispatch("click");
    assertEqual("navigation: opens through the shell event", openedPaths, ["one.js"]);
  }
  internals.teardown();
  responses.clear();
  registeredPanel = null;
  // /api/git/repo answers is_repo:false, so nothing is registered, but
  // a later init can retry after that transient/negative result.
  const viewAssets = [];
  const assetWaits = [];
  sandbox.metabrowser.ensureAsset = (name) => {
    viewAssets.push(name);
    return new Promise((resolve, reject) => assetWaits.push({ resolve, reject }));
  };
  responses.set("/api/git/repo", { is_repo: false, reason: "not_a_repo" });
  await panel.init();
  assertEqual("gate: a plain folder never asks for view helpers", viewAssets, []);
  assertEqual("gate: no tab outside a repository", registeredPanel, null);

  responses.set("/api/git/repo", {
    is_repo: true,
    root: "",
    head: { ref: "refs/heads/main", revision: SHA_A, detached: false, unborn: false },
  });
  responses.set("/api/git/refs", { is_repo: true, refs: [] });
  await panel.init();
  assertTrue(
    "gate: a repository registers its real Git tab before helper loading",
    registeredPanel !== null,
  );
  assertTrue(
    "gate: the Commits tab hands its key's focus to the history",
    registeredPanel.focusRow === internals.focusCommitRow,
  );
  assertEqual("gate: an unopened Git tab does not load the view helpers", viewAssets, []);
  registeredPanel.onShow();
  await new Promise(setImmediate);
  assertEqual("gate: opening Git requests the one helper bundle", viewAssets, ["sdk-views"]);
  assertTrue(
    "gate: pending helper shows history loading",
    document.getElementById("tab-git").querySelector(".git-history-skeleton") !== null,
  );
  assetWaits.shift().reject(new Error("view helpers unavailable"));
  await new Promise(setImmediate);
  assertTrue("gate: failed helpers retain the real Git tab", registeredPanel !== null);
  assertContains(
    "gate: helper failure has an actionable explanation",
    document.getElementById("tab-git").textContent,
    "Could not load Git view controls. Refresh to try again.",
  );
  const retry = document.getElementById("tab-git").querySelector(".git-panel-refresh");
  assertTrue("gate: helper failure exposes a real retry button", retry !== null);
  retry.dispatch("click");
  await new Promise(setImmediate);
  assertEqual("gate: retry asks the same required bundle", viewAssets, ["sdk-views", "sdk-views"]);
  responses.set("/api/git/log", historyPage(0, [commit(SHA_A, [], "recovered history")], 1, SHA_A));
  assetWaits.shift().resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertEqual("gate: visible retry restores real history", internals.stateForTests().rowCount, 1);
  assertNotContains(
    "gate: successful retry clears the helper failure",
    document.getElementById("tab-git").textContent,
    "Could not load Git view controls",
  );
  internals.teardown();
  await panel.init();
  registeredPanel.onShow();
  await new Promise(setImmediate);
  internals.teardown();
  await panel.init();
  const replacementPanel = registeredPanel;
  registeredPanel.onShow();
  await new Promise(setImmediate);
  assetWaits.shift().reject(new Error("abandoned helpers failed late"));
  await new Promise(setImmediate);
  assertTrue(
    "gate: abandoned failure cannot remove the replacement tab",
    registeredPanel === replacementPanel,
  );
  assertTrue(
    "gate: abandoned failure cannot replace newer loading state",
    document.getElementById("tab-git").querySelector(".git-history-skeleton") !== null,
  );
  assetWaits.shift().resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertEqual(
    "gate: replacement completion restores history",
    internals.stateForTests().rowCount,
    1,
  );
  assertEqual("gate: helper retries preserve the one bundle identity", viewAssets, [
    "sdk-views",
    "sdk-views",
    "sdk-views",
    "sdk-views",
  ]);
  internals.teardown();
  await panel.init();
  registeredPanel.onShow();
  await new Promise(setImmediate);
  internals.teardown();
  await panel.init();
  const latestPanel = registeredPanel;
  registeredPanel.onShow();
  await new Promise(setImmediate);
  const beforeAbandonedSuccess = fetchCount;
  assetWaits.shift().resolve();
  await new Promise(setImmediate);
  assertTrue(
    "gate: abandoned success keeps the latest registration",
    registeredPanel === latestPanel,
  );
  assertEqual(
    "gate: abandoned success cannot start a history read",
    fetchCount,
    beforeAbandonedSuccess,
  );
  assertTrue(
    "gate: abandoned success cannot settle newer loading state",
    document.getElementById("tab-git").querySelector(".git-history-skeleton") !== null,
  );
  assetWaits.shift().resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertEqual(
    "gate: latest helper owner alone restores history",
    internals.stateForTests().rowCount,
    1,
  );
  internals.teardown();
  const previousLocation = sandbox.location;
  const previousParseCommit = sandbox.MetabrowserNavigationRoute.parseCommit;
  sandbox.location = { pathname: `/commit/${SHA_A}` };
  sandbox.MetabrowserNavigationRoute.parseCommit = (pathname) =>
    pathname === `/commit/${SHA_A}` ? { revision: SHA_A } : null;
  responses.set(`/api/git/commit/${SHA_A}`, {
    is_repo: true,
    commit: commit(SHA_A, [], "recovered landing"),
    body: "",
    stats: { files_changed: 0, additions: 0, deletions: 0 },
    files: [],
    files_truncated: false,
  });
  const renderedBeforeLanding = renderedDiffRevisions.length;
  const landingInit = panel.init();
  await new Promise(setImmediate);
  assetWaits.shift().reject(new Error("landing helpers unavailable"));
  await landingInit;
  assertEqual(
    "gate: failed landing does not invoke unavailable view helpers",
    renderedDiffRevisions.length,
    renderedBeforeLanding,
  );
  document.getElementById("tab-git").querySelector(".git-panel-refresh").dispatch("click");
  await new Promise(setImmediate);
  assetWaits.shift().resolve();
  for (
    let turn = 0;
    turn < 50 && renderedDiffRevisions.length === renderedBeforeLanding;
    turn += 1
  ) {
    await new Promise(setImmediate);
  }
  assertEqual(
    "gate: retry restores the addressed commit",
    renderedDiffRevisions.length,
    renderedBeforeLanding + 1,
  );
  assertEqual(
    "gate: recovered landing retains its route",
    sandbox.location.pathname,
    `/commit/${SHA_A}`,
  );
  assertEqual(
    "gate: recovered landing selects its exact commit",
    internals.stateForTests().selectedId,
    SHA_A,
  );
  sandbox.location = previousLocation;
  sandbox.MetabrowserNavigationRoute.parseCommit = previousParseCommit;
  sandbox.metabrowser.ensureAsset = async () => {};

  internals.setStateForTests(internals.emptyState());
  responses.delete("/api/git/log");
  registeredPanel.onShow();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertTrue("show: initial history failure is retained", internals.stateForTests().failed);

  const malformedInitialPage = historyPage(0, [commit(SHA_A, [], "missing checkpoint")], 1, SHA_A);
  delete malformedInitialPage.graph_checkpoint;
  responses.set("/api/git/log", malformedInitialPage);
  registeredPanel.onShow();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertTrue(
    "show: malformed initial history remains a visible failure",
    internals.stateForTests().failed,
  );
  assertContains(
    "show: malformed initial history offers recovery",
    document.getElementById("tab-git").textContent,
    "Could not read",
  );

  responses.set("/api/git/log", historyPage(0, [commit(SHA_A, [], "retry succeeded")], 1, SHA_A));
  registeredPanel.onShow();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertEqual("show: reopening retries history", internals.stateForTests().rows.length, 1);
  assertTrue("show: successful retry clears failure", !internals.stateForTests().failed);

  // A rejected cursor invalidates append-only lane continuity. Reset to
  // the refresh state rather than retrying the same cursor on every show.
  internals.setStateForTests({
    ...internals.stateForTests(),
    cursor: "bad-cursor",
    endReached: false,
    failed: true,
  });
  responses.set("/api/git/log", { httpStatus: 400 });
  registeredPanel.onShow();
  await new Promise((resolve) => setTimeout(resolve, 0));
  const rejectedCursor = internals.stateForTests();
  assertEqual("cursor: rejected cursor clears rows", rejectedCursor.rows.length, 0);
  assertEqual("cursor: rejected cursor is discarded", rejectedCursor.cursor, null);
  assertTrue("cursor: rejected cursor offers recovery", rejectedCursor.failed);
  assertEqual(
    "cursor: rejected cursor renders refresh",
    document.getElementById("tab-git").querySelectorAll(".git-panel-refresh").length,
    1,
  );

  responses.set(
    "/api/git/log",
    historyPage(0, [commit(SHA_B, [], "cursor recovery succeeded")], 1, SHA_A),
  );
  registeredPanel.onShow();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertEqual("cursor: reopening restarts at page one", internals.stateForTests().rows.length, 1);
  assertTrue("cursor: successful restart clears failure", !internals.stateForTests().failed);

  // ── Reopening after a checkout ─────────────────────────────
  //
  // HEAD is an input to lane layout, baked into each row when the page
  // was laid out, so a checkout made while another tab was showing can
  // only be recomputed, never repainted. Re-reading repository identity
  // on activation is what catches it.
  responses.set(`/api/git/commit/${SHA_B}`, {
    is_repo: true,
    commit: commit(SHA_B, [], "cursor recovery succeeded"),
    body: "",
    stats: { files_changed: 0, additions: 0, deletions: 0 },
    files: [],
    files_truncated: false,
  });
  await internals.selectCommit(SHA_B);
  assertTrue(
    "performance: selection records immediate feedback separately",
    measuredLabels.includes("gitRevision:selectionFeedback"),
  );
  assertTrue(
    "performance: selection retains the painted-ready total",
    measuredLabels.includes("gitRevision:selectToReady"),
  );
  const primedCache = fetchCount;
  await internals.selectCommit(SHA_B);
  assertEqual("head: the detail cache serves a repeat select", fetchCount, primedCache);

  responses.set("/api/git/repo", {
    is_repo: true,
    root: "",
    head: { ref: "refs/heads/other", revision: SHA_C, detached: false, unborn: false },
  });
  responses.set(
    "/api/git/log",
    historyPage(0, [commit(SHA_C, [], "after checkout"), commit(SHA_B, [], "older")], 2, SHA_C),
  );
  registeredPanel.onShow();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertEqual("head: a moved HEAD recomputes the graph", internals.stateForTests().rows.length, 2);
  assertEqual("head: state adopts the new revision", internals.stateForTests().headRevision, SHA_C);

  // A commit's object id is immutable but its payload is not: refs move
  // as branches and tags do, so a detail cached before the refresh must
  // not survive it.
  const afterRefresh = fetchCount;
  await internals.selectCommit(SHA_B);
  assertTrue("head: a refresh clears the detail cache", fetchCount > afterRefresh);

  // ── Switching to Commits lands on the newest commit ────────
  //
  // The neutral Commits entry selects the top row once history is here, an older selection
  // notwithstanding. The newest row is selected and is the list's Tab stop, focus stays on
  // the tab the switch left it on, a scrolled list comes back to its top, and a return
  // with history loaded asks only whether HEAD moved, never for history again.
  {
    responses.set(`/api/git/commit/${SHA_C}`, {
      is_repo: true,
      commit: commit(SHA_C, [], "after checkout"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    const container = document.getElementById("tab-git");
    const tab = document.createElement("button");
    tab.focus();
    container.scrollTop = 500;
    const requestsBefore = fetchRequests.length;
    neutralLanding = true;
    await panel.restoreCommitLanding();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const asked = fetchRequests.slice(requestsBefore).map((request) => request.url);
    assertEqual("newest: the top row is selected", internals.stateForTests().selectedId, SHA_C);
    assertEqual(
      "newest: its address replaces the entry",
      replacedRoutes.at(-1),
      `/commit/${SHA_C}`,
    );
    const newestRow = container.querySelector('.git-graph-row[data-ordinal="0"]');
    assertTrue("newest: the row is marked", newestRow?.classList.contains("selected") === true);
    assertEqual("newest: the row is the Tab stop", newestRow?.getAttribute("tabindex"), "0");
    assertTrue("newest: focus stays on the tab", document.activeElement === tab);
    assertEqual("newest: the list is back at its top", container.scrollTop, 0);
    assertEqual("newest: history is not asked for again", asked, [
      "/api/git/repo",
      `/api/git/commit/${SHA_C}`,
    ]);
    // An address that names a commit wins: the entry is not the neutral one.
    await internals.selectCommit(SHA_B);
    const landedBefore = replacedRoutes.length;
    await panel.restoreCommitLanding();
    await new Promise((resolve) => setTimeout(resolve, 0));
    assertEqual(
      "newest: a non-neutral address selects nothing",
      replacedRoutes.length,
      landedBefore,
    );
    assertEqual("newest: the older commit stays", internals.stateForTests().selectedId, SHA_B);
  }

  // ── The Commits key lands on the newest row ──────────────
  //
  // The key switches to Commits and then asks the panel for its row (main-tabs.js), before
  // the landing has selected anything. That row is the newest, not the older one the reader
  // left: focused without scrolling the list and made its Tab stop, so `↓` opens the next
  // commit. A newest row the list has not mounted takes focus when the landing reveals it,
  // unless the reader has moved focus by then, and a refresh that replaces the focused row
  // gives focus back to the new one. A click on the tab leaves focus on the tab, and a
  // landing that lost the pane or the address steers nothing.
  {
    const container = document.getElementById("tab-git");
    const tab = document.register("commits-tab", document.createElement("button"));
    tab.className = "tab-btn";
    tab.dataset.tab = "git";
    const filesRow = document.register("files-row", document.createElement("div"));
    const filter = document.register("files-filter", document.createElement("input"));
    const rowAt = (ordinal) => container.querySelector(`.git-graph-row[data-ordinal="${ordinal}"]`);
    const settle = async () => {
      for (let tick = 0; tick < 50; tick += 1) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
    };
    const detail = (revision) => ({
      is_repo: true,
      commit: commit(revision, [], "key detail"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    // What the key does from another tab (main-tabs.js bindShortcuts and openMainTab): it
    // gives up the pane, pushes the neutral entry, and asks the panel to land; the landing
    // shows the panel (activateNavPanel, below). Then it asks the panel for its row, or
    // focuses the tab while the panel has none.
    const pressCommitsDigit = () => {
      sandbox.MetabrowserShell.claimPreview("none");
      neutralLanding = true;
      const landing = panel.restoreCommitLanding();
      const took = registeredPanel.focusRow();
      if (!took) {
        tab.focus();
      }
      return { landing, took };
    };
    // A click on the tab: the button takes focus, and the switch is the key's, without the
    // request for a row.
    const clickCommitsTab = () => {
      tab.focus();
      sandbox.MetabrowserShell.claimPreview("none");
      neutralLanding = true;
      return panel.restoreCommitLanding();
    };
    // The key with Commits in front: openMainTab only shows the panel again, with no
    // landing of its own, and then asks for the row.
    const pressDigitWithCommitsShown = () => {
      registeredPanel.onShow();
      const took = registeredPanel.focusRow();
      if (!took) {
        tab.focus();
      }
      return took;
    };
    // Showing the panel from another tab puts its list at the top, and its onShow checks
    // history, which renders the rows at that top unless a page is on its way.
    const shellActivate = sandbox.MetabrowserShell.activateNavPanel;
    sandbox.MetabrowserShell.activateNavPanel = (id) => {
      if (id === "git") {
        container.scrollTop = 0;
        registeredPanel.onShow();
      }
    };
    // A held answer for the repository read that each landing and onShow make first.
    const holdRepo = (answer) => {
      let release = () => {};
      const held = new Promise((resolve) => (release = resolve));
      responses.set("/api/git/repo", async () => {
        await held;
        return answer;
      });
      return () => {
        release();
        responses.set("/api/git/repo", answer);
      };
    };
    const repoAt = (revision, ref = "refs/heads/main") => ({
      is_repo: true,
      root: "",
      head: { ref, revision, detached: false, unborn: false },
    });

    // Mounted: the reader left the older commit at ordinal 1 for Files.
    {
      filesRow.focus();
      const { landing, took } = pressCommitsDigit();
      const newest = rowAt(0);
      assertTrue(
        "H: the newest row takes focus at once",
        took && document.activeElement === newest,
      );
      assertEqual("H: focus does not scroll the list", newest?.focusCalls.at(-1), {
        preventScroll: true,
      });
      assertEqual("H: the newest row is the Tab stop", newest?.getAttribute("tabindex"), "0");
      assertEqual("H: the row left is not", rowAt(1)?.getAttribute("tabindex"), "-1");
      await landing;
      await settle();
      assertEqual("H: the newest is selected", internals.stateForTests().selectedId, SHA_C);
      assertTrue("H: focus stays on the newest row", document.activeElement === rowAt(0));
      assertEqual("H: it stays the Tab stop", rowAt(0)?.getAttribute("tabindex"), "0");
      assertEqual("H: the list stays at its top", container.scrollTop, 0);
      const down = keyboardEvent("ArrowDown");
      document.activeElement.dispatch("keydown", down);
      assertTrue("H: ↓ is handled", down.defaultPrevented);
      assertEqual("H: ↓ opens the next commit", internals.stateForTests().selectedId, SHA_B);
      assertTrue("H: ↓ focuses its row", document.activeElement === rowAt(1));
      await settle();
    }
    filesRow.focus();
    await clickCommitsTab();
    await settle();
    assertEqual("click: the newest is selected", internals.stateForTests().selectedId, SHA_C);
    assertEqual("click: the newest row is the Tab stop", rowAt(0)?.getAttribute("tabindex"), "0");
    assertTrue("click: focus stays on the tab", document.activeElement === tab);

    // HEAD moved while Commits was hidden. The landing's refresh replaces the rows, the
    // focused newest among them, and a browser then drops focus to the body; the landing
    // gives it to the new newest row.
    {
      filesRow.focus();
      responses.set(`/api/git/commit/${SHA_D}`, detail(SHA_D));
      responses.set("/api/git/repo", {
        is_repo: true,
        root: "",
        head: { ref: "refs/heads/other", revision: SHA_D, detached: false, unborn: false },
      });
      let releasePage = () => {};
      const pageHeld = new Promise((resolve) => (releasePage = resolve));
      let pageAsked = false;
      responses.set("/api/git/log", async () => {
        pageAsked = true;
        await pageHeld;
        return historyPage(
          0,
          [commit(SHA_D, [SHA_C], "moved head"), commit(SHA_C, [], "after checkout")],
          2,
          SHA_D,
        );
      });
      const { landing, took } = pressCommitsDigit();
      assertTrue(
        "H, refresh: the newest row takes focus",
        took && document.activeElement === rowAt(0),
      );
      for (let tick = 0; tick < 50 && !pageAsked; tick += 1) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
      assertTrue("H, refresh: the refresh asks for history", pageAsked);
      assertEqual("H, refresh: the refresh replaced the rows", rowAt(0), null);
      // What a browser does when the focused element leaves the document.
      document.activeElement = null;
      releasePage();
      await landing;
      await settle();
      assertEqual(
        "H, refresh: the new newest is selected",
        internals.stateForTests().selectedId,
        SHA_D,
      );
      assertTrue(
        "H, refresh: focus returns to the newest row",
        document.activeElement === rowAt(0),
      );
      assertEqual("H, refresh: without scrolling", rowAt(0)?.focusCalls.at(-1), {
        preventScroll: true,
      });
    }

    // The reader clicks text in the preview while the landing reads HEAD, which moved back:
    // focus goes nowhere before the refresh replaces the rows, and the landing leaves it
    // there. Only a row the refresh removed hands focus back.
    {
      filesRow.focus();
      responses.set(
        "/api/git/log",
        historyPage(
          0,
          [commit(SHA_C, [SHA_B], "checked out again"), commit(SHA_B, [], "older")],
          2,
          SHA_C,
        ),
      );
      const releaseRepo = holdRepo(repoAt(SHA_C));
      const { landing, took } = pressCommitsDigit();
      assertTrue(
        "H, text click: the newest row takes focus",
        took && document.activeElement === rowAt(0),
      );
      // A click on text no one can focus: the browser reports the body.
      document.activeElement = null;
      releaseRepo();
      await landing;
      await settle();
      assertEqual(
        "H, text click: the newest is selected",
        internals.stateForTests().selectedId,
        SHA_C,
      );
      assertTrue("H, text click: focus stays nowhere", document.activeElement === null);
    }

    // The reader scrolls the key's row away while the landing reads HEAD, which moved
    // again: focus parks on the scroller, and the refresh that replaces the rows forgets the
    // parking, so no render hands focus back. The landing gives it to the new newest row.
    {
      filesRow.focus();
      responses.set(
        "/api/git/log",
        historyPage(
          0,
          [commit(SHA_D, [SHA_C], "moved again"), commit(SHA_C, [], "before the move")],
          2,
          SHA_D,
        ),
      );
      const releaseRepo = holdRepo(repoAt(SHA_D));
      const { landing, took } = pressCommitsDigit();
      assertTrue(
        "H, parked refresh: the newest row takes focus",
        took && document.activeElement === rowAt(0),
      );
      // Where renderVirtualRows parks focus when the focused row leaves the window.
      container.focus();
      releaseRepo();
      await landing;
      await settle();
      assertEqual(
        "H, parked refresh: the new newest is selected",
        internals.stateForTests().selectedId,
        SHA_D,
      );
      assertTrue(
        "H, parked refresh: focus returns to the newest row",
        document.activeElement === rowAt(0),
      );
    }

    // Not mounted: the reader left a commit far down a history deep enough to evict its first
    // page. The tab holds focus while the landing replays that page, and the reveal hands it
    // to the newest row; the row left never takes it, so the list stays at its top.
    {
      const total = 8;
      const revisions = Array.from({ length: total }, (_value, index) =>
        (index + 8000).toString(16).padStart(40, "0"),
      );
      const walk = revisions.map((revision, index) =>
        commit(revision, index + 1 < total ? [revisions[index + 1]] : [], `key commit ${index}`),
      );
      responses.set("/api/git/repo", {
        is_repo: true,
        root: "",
        head: { ref: "refs/heads/main", revision: revisions[0], detached: false, unborn: false },
      });
      let holdFirstPage = null;
      let firstPageAsked = false;
      responses.set("/api/git/log", async (url) => {
        const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
        const page = Number(cursor?.split(":")[1] ?? 0);
        if (page === 0) {
          firstPageAsked = true;
          await holdFirstPage;
        }
        return historyPage(page, walk.slice(page * 2, page * 2 + 2), total, revisions[0]);
      });
      for (const revision of revisions) {
        responses.set(`/api/git/commit/${revision}`, detail(revision));
      }
      const deep = internals.emptyState();
      deep.headRevision = revisions[0];
      deep.headRef = "refs/heads/main";
      internals.setStateForTests(deep);
      for (let page = 0; page < 4; page += 1) {
        const pageCommits = walk.slice(page * 2, page * 2 + 2);
        const wire = historyPage(page, pageCommits, total, revisions[0]);
        internals.appendPage(pageCommits, wire.cursor, wire);
      }
      container.clientHeight = 44;
      // The reader scrolls down to an older commit, selects it, and leaves for Files.
      const leaveFromFarDown = async () => {
        container.scrollTop = 132;
        internals.renderPanel();
        await settle();
        await internals.selectCommit(revisions[6]);
        filesRow.focus();
      };

      await leaveFromFarDown();
      const left = rowAt(6);
      assertEqual(
        "H, unmounted: the row left is the Tab stop",
        left?.getAttribute("tabindex"),
        "0",
      );
      assertEqual("H, unmounted: the newest row is not mounted", rowAt(0), null);
      const { landing, took } = pressCommitsDigit();
      assertTrue("H, unmounted: no row takes focus yet", !took);
      assertTrue("H, unmounted: the tab holds focus", document.activeElement === tab);
      assertEqual("H, unmounted: the row left is not focused", left?.focusCalls, []);
      await landing;
      await settle();
      const newest = rowAt(0);
      assertEqual(
        "H, unmounted: the newest is selected",
        internals.stateForTests().selectedId,
        revisions[0],
      );
      assertTrue(
        "H, unmounted: the newest row takes focus once revealed",
        newest !== null && document.activeElement === newest,
      );
      assertEqual("H, unmounted: without scrolling", newest?.focusCalls.at(-1), {
        preventScroll: true,
      });
      assertEqual("H, unmounted: the list stays at its top", container.scrollTop, 0);
      assertEqual(
        "H, unmounted: the newest row is the Tab stop",
        newest?.getAttribute("tabindex"),
        "0",
      );
      const down = keyboardEvent("ArrowDown");
      newest?.dispatch("keydown", down);
      assertEqual(
        "H, unmounted: ↓ opens the next commit",
        internals.stateForTests().selectedId,
        revisions[1],
      );
      assertTrue("H, unmounted: ↓ focuses its row", document.activeElement === rowAt(1));
      await settle();

      // The reader moves focus while the landing waits for the first page: it stays there.
      // Scrolling the focused row away parked focus on the scroller first, and that
      // suspension, stale once the reader left for Files, does not take focus back either.
      await leaveFromFarDown();
      let releaseFirstPage = () => {};
      holdFirstPage = new Promise((resolve) => (releaseFirstPage = resolve));
      firstPageAsked = false;
      const moved = pressCommitsDigit();
      assertTrue("H, moved: the tab holds focus", !moved.took && document.activeElement === tab);
      for (let tick = 0; tick < 50 && !firstPageAsked; tick += 1) {
        await new Promise((resolve) => setTimeout(resolve, 0));
      }
      assertTrue("H, moved: the landing waits for the first page", firstPageAsked);
      filter.focus();
      releaseFirstPage();
      await moved.landing;
      await settle();
      assertEqual(
        "H, moved: the newest is still selected",
        internals.stateForTests().selectedId,
        revisions[0],
      );
      assertTrue(
        "H, moved: focus stays where the reader put it",
        document.activeElement === filter,
      );

      // The reader clicks text while the tab holds focus: focus goes nowhere, and the landing
      // leaves it there; nowhere is not the tab.
      await leaveFromFarDown();
      const nowhere = pressCommitsDigit();
      assertTrue(
        "H, text click on the tab: the tab holds focus",
        !nowhere.took && document.activeElement === tab,
      );
      document.activeElement = null;
      await nowhere.landing;
      await settle();
      assertEqual(
        "H, text click on the tab: the newest is selected",
        internals.stateForTests().selectedId,
        revisions[0],
      );
      assertTrue("H, text click on the tab: focus stays nowhere", document.activeElement === null);

      // A click after focus last parked on the scroller: the reader focused a row, scrolled it
      // away, and left for Files. The landing's reveal mounts that row again, and it does not
      // take focus back from the tab.
      container.scrollTop = 0;
      internals.renderPanel();
      await settle();
      rowAt(1)?.focus();
      container.scrollTop = 132;
      internals.renderPanel();
      await settle();
      assertTrue(
        "click, parked: focus parks on the scroller",
        document.activeElement === container && internals.stateForTests().focusSuspended,
      );
      filesRow.focus();
      await clickCommitsTab();
      await settle();
      assertEqual(
        "click, parked: the newest is selected",
        internals.stateForTests().selectedId,
        revisions[0],
      );
      assertTrue("click, parked: the row left is mounted again", rowAt(1) !== null);
      assertTrue("click, parked: focus stays on the tab", document.activeElement === tab);

      // The key with Commits in front while a click's landing waits on HEAD. The reader
      // focused a row since and scrolled it away, so focus parked on the scroller; the
      // key's row is still the newest, and a render that mounts the row left at the top
      // gives it neither focus nor the Tab stop. Page reads wait too, so nothing settles
      // until both answers come.
      filesRow.focus();
      let releaseRepo = holdRepo(repoAt(revisions[0]));
      const pageLog = responses.get("/api/git/log");
      let releasePages = () => {};
      const pagesHeld = new Promise((resolve) => (releasePages = resolve));
      responses.set("/api/git/log", async (url) => {
        await pagesHeld;
        return pageLog(url);
      });
      const waiting = clickCommitsTab();
      rowAt(1)?.focus();
      container.scrollTop = 132;
      internals.renderPanel();
      assertTrue("in front: focus parks on the scroller", document.activeElement === container);
      assertTrue("in front: the newest row is not mounted", rowAt(0) === null);
      const rowTaken = pressDigitWithCommitsShown();
      assertTrue("in front: the tab holds focus", !rowTaken && document.activeElement === tab);
      container.scrollTop = 0;
      internals.renderPanel();
      assertTrue("in front: the row left is mounted again", rowAt(1) !== null);
      assertTrue("in front: it does not take focus", document.activeElement === tab);
      assertEqual(
        "in front: the newest row is the Tab stop",
        rowAt(0)?.getAttribute("tabindex"),
        "0",
      );
      responses.set("/api/git/log", pageLog);
      releasePages();
      releaseRepo();
      await waiting;
      await settle();
      assertEqual(
        "in front: the newest is selected",
        internals.stateForTests().selectedId,
        revisions[0],
      );
      assertTrue("in front: the newest row takes focus", document.activeElement === rowAt(0));

      // A landing that lost the pane steers nothing: a file takes it while the click's landing
      // waits, HEAD answers and the list renders, and the key with Commits in front then
      // hands focus to the row the reader left, as with no landing. That row is still the
      // Tab stop, and the landing selects nothing.
      await internals.selectCommit(revisions[1]);
      await settle();
      filesRow.focus();
      releaseRepo = holdRepo(repoAt(revisions[0]));
      const lost = clickCommitsTab();
      panel.cancelPending();
      sandbox.MetabrowserShell.claimPreview("file");
      neutralLanding = false;
      releaseRepo();
      await lost;
      await settle();
      assertEqual(
        "lost: the landing selects nothing",
        internals.stateForTests().selectedId,
        revisions[1],
      );
      assertEqual(
        "lost: the row left is still the Tab stop",
        rowAt(1)?.getAttribute("tabindex"),
        "0",
      );
      assertTrue("lost: a row takes focus", pressDigitWithCommitsShown());
      assertTrue("lost: it is the row the reader left", document.activeElement === rowAt(1));

      // Back during the key's wait: the address is no longer the neutral entry, and the
      // landing neither selects nor moves focus when HEAD answers.
      await leaveFromFarDown();
      releaseRepo = holdRepo(repoAt(revisions[0]));
      const back = pressCommitsDigit();
      assertTrue("back: the tab holds focus", !back.took && document.activeElement === tab);
      neutralLanding = false;
      await panel.restoreCommitLanding();
      releaseRepo();
      await back.landing;
      await settle();
      assertEqual(
        "back: the landing selects nothing",
        internals.stateForTests().selectedId,
        revisions[6],
      );
      assertTrue("back: focus stays on the tab", document.activeElement === tab);

      // A file takes the pane during the key's wait, and the reader moves to it: the
      // landing ends without selecting or moving focus.
      await leaveFromFarDown();
      releaseRepo = holdRepo(repoAt(revisions[0]));
      const file = pressCommitsDigit();
      panel.cancelPending();
      sandbox.MetabrowserShell.claimPreview("file");
      neutralLanding = false;
      filesRow.focus();
      releaseRepo();
      await file.landing;
      await settle();
      assertEqual(
        "file: the landing selects nothing",
        internals.stateForTests().selectedId,
        revisions[6],
      );
      assertTrue("file: focus stays with the file", document.activeElement === filesRow);
      delete container.clientHeight;
      container.scrollTop = 0;
    }

    // A page on its way when the key switches: onShow's history check waits for it and
    // renders nothing, so the window mounted further down is the last one drawn, though the
    // switch put the list at its top. The landing's reveal redraws it from the newest row,
    // which then takes focus.
    {
      const total = 4;
      const revisions = Array.from({ length: total }, (_value, index) =>
        (index + 9000).toString(16).padStart(40, "0"),
      );
      const walk = revisions.map((revision, index) =>
        commit(revision, index + 1 < total ? [revisions[index + 1]] : [], `in flight ${index}`),
      );
      responses.set("/api/git/repo", repoAt(revisions[0]));
      for (const revision of revisions) {
        responses.set(`/api/git/commit/${revision}`, detail(revision));
      }
      const small = internals.emptyState();
      small.headRevision = revisions[0];
      small.headRef = "refs/heads/main";
      internals.setStateForTests(small);
      for (let page = 0; page < 2; page += 1) {
        const pageCommits = walk.slice(page * 2, page * 2 + 2);
        const wire = historyPage(page, pageCommits, total, revisions[0]);
        internals.appendPage(pageCommits, wire.cursor, wire);
      }
      container.clientHeight = 44;
      let windowFound = false;
      for (const top of [44, 55, 66, 77, 88]) {
        container.scrollTop = top;
        internals.renderPanel();
        await settle();
        if (rowAt(0) === null && rowAt(2) !== null) {
          windowFound = true;
          break;
        }
      }
      assertTrue("in flight: a window without the newest row", windowFound);
      assertEqual(
        "in flight: the window is in the first segment",
        internals.stateForTests().mountedRange?.segmentStart,
        0,
      );
      filesRow.focus();
      const live = { ...internals.stateForTests() };
      delete live.rows;
      delete live.commits;
      live.loading = true;
      internals.setStateForTests(live);
      const inFlight = pressCommitsDigit();
      assertTrue(
        "in flight: the tab holds focus",
        !inFlight.took && document.activeElement === tab,
      );
      await inFlight.landing;
      await settle();
      assertEqual(
        "in flight: the newest is selected",
        internals.stateForTests().selectedId,
        revisions[0],
      );
      assertTrue(
        "in flight: the newest row takes focus",
        rowAt(0) !== null && document.activeElement === rowAt(0),
      );
      live.loading = false;
      internals.renderPanel();
      await settle();
      assertTrue("in flight: it keeps focus", document.activeElement === rowAt(0));

      // A render while a selected commit loads replaces its row. The selection's own anchor
      // write, when the commit is ready, must not land on the replaced row: the live row
      // stays the list's Tab stop.
      filesRow.focus();
      let releaseDetail = () => {};
      const detailHeld = new Promise((resolve) => (releaseDetail = resolve));
      responses.set(`/api/git/commit/${revisions[1]}`, async () => {
        await detailHeld;
        return detail(revisions[1]);
      });
      const selecting = internals.selectCommit(revisions[1]);
      await settle();
      const replacedRow = rowAt(1);
      assertTrue(
        "replaced: the row shows the selection",
        replacedRow?.classList.contains("selected") === true,
      );
      internals.renderPanel();
      assertTrue("replaced: the render replaced the row", rowAt(1) !== replacedRow);
      releaseDetail();
      await selecting;
      await settle();
      assertEqual(
        "replaced: the live row is the Tab stop",
        rowAt(1)?.getAttribute("tabindex"),
        "0",
      );
      assertEqual("replaced: the replaced row is not", replacedRow?.getAttribute("tabindex"), "-1");
      delete container.clientHeight;
      container.scrollTop = 0;
    }

    sandbox.MetabrowserShell.activateNavPanel = shellActivate;
    neutralLanding = false;
    document.activeElement = null;
    for (const [id, element] of [
      ["commits-tab", tab],
      ["files-row", filesRow],
      ["files-filter", filter],
    ]) {
      element.remove();
      document.byId.delete(id);
    }
  }

  // ── A newest landing outlives a session recovery ───────────
  //
  // An older commit deep enough to evict page zero, then a return to Commits after the
  // server's history session expired: the landing's reveal replays page zero, the replay
  // answers 410, and recovery rebuilds the walk. Recovery used to restore the older
  // position after the landing had selected the newest commit, leaving its row offscreen
  // and an older row as the list's Tab stop.
  {
    const total = 12;
    const revisions = Array.from({ length: total }, (_value, index) =>
      (index + 5000).toString(16).padStart(40, "0"),
    );
    const deepCommits = revisions.map((revision, index) =>
      commit(revision, index + 1 < total ? [revisions[index + 1]] : [], `deep commit ${index}`),
    );
    const container = document.getElementById("tab-git");
    const deep = internals.emptyState();
    deep.headRevision = revisions[0];
    deep.headRef = "refs/heads/main";
    internals.setStateForTests(deep);
    for (let page = 0; page < 4; page += 1) {
      appendTestPage(deepCommits.slice(page * 2, page * 2 + 2), `history:${page + 1}`);
    }
    const older = internals.stateForTests();
    assertEqual("recovered landing: page zero was evicted", older.pageCache.peek(0), null);
    older.selectedId = revisions[6];
    older.focusedOrdinal = 6;
    delete older.rows;
    delete older.commits;
    internals.setStateForTests(older);
    container.clientHeight = 44;
    container.scrollTop = 132;
    responses.set("/api/git/repo", {
      is_repo: true,
      root: "",
      head: { ref: "refs/heads/main", revision: revisions[0], detached: false, unborn: false },
    });
    responses.set("/api/git/refs", { is_repo: true, refs: [] });
    responses.set("/api/git/summary", { is_repo: true, commit_count: total });
    let replays = 0;
    responses.set("/api/git/log", (url) => {
      const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
      if (cursor?.startsWith("test:")) {
        replays += 1;
        return { httpStatus: 410 };
      }
      const page = cursor ? Number(cursor.split(":")[1]) : 0;
      return historyPage(page, deepCommits.slice(page * 2, page * 2 + 2), total, revisions[0]);
    });
    for (const revision of revisions.slice(0, 1)) {
      responses.set(`/api/git/commit/${revision}`, {
        is_repo: true,
        commit: commit(revision, [], "newest after recovery"),
        body: "",
        stats: { files_changed: 0, additions: 0, deletions: 0 },
        files: [],
        files_truncated: false,
      });
    }
    neutralLanding = true;
    await panel.restoreCommitLanding();
    for (let tick = 0; tick < 50; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    const landed = internals.stateForTests();
    const anchor = container.querySelector(".git-graph-row[data-roving-anchor]");
    assertEqual("recovered landing: the replay expired once", replays, 1);
    assertEqual("recovered landing: the newest is selected", landed.selectedId, revisions[0]);
    assertEqual("recovered landing: the list is at its top", container.scrollTop, 0);
    assertEqual("recovered landing: the newest row is focused", landed.focusedOrdinal, 0);
    assertEqual("recovered landing: the newest row is the Tab stop", anchor?.dataset.ordinal, "0");
    delete container.clientHeight;
    container.scrollTop = 0;
    neutralLanding = false;
  }

  // ── A recovery the reader left places nothing ──────────────
  //
  // The same expired landing, but the reader switches to Files while recovery's first page
  // is on its way. The scroller is shared, so a recovery that went on to reveal the newest
  // row wrote over the offset Files had put back. Leaving Commits cancels the landing, and
  // recovery now places nothing once Commits is not in front or another owner holds the pane.
  {
    const total = 12;
    const revisions = Array.from({ length: total }, (_value, index) =>
      (index + 7000).toString(16).padStart(40, "0"),
    );
    const deepCommits = revisions.map((revision, index) =>
      commit(revision, index + 1 < total ? [revisions[index + 1]] : [], `left commit ${index}`),
    );
    const container = document.getElementById("tab-git");
    const deep = internals.emptyState();
    deep.headRevision = revisions[0];
    deep.headRef = "refs/heads/main";
    internals.setStateForTests(deep);
    for (let page = 0; page < 4; page += 1) {
      appendTestPage(deepCommits.slice(page * 2, page * 2 + 2), `history:${page + 1}`);
    }
    const older = internals.stateForTests();
    older.selectedId = revisions[6];
    older.focusedOrdinal = 6;
    delete older.rows;
    delete older.commits;
    internals.setStateForTests(older);
    container.clientHeight = 44;
    container.scrollTop = 132;
    responses.set("/api/git/repo", {
      is_repo: true,
      root: "",
      head: { ref: "refs/heads/main", revision: revisions[0], detached: false, unborn: false },
    });
    let releaseFirstPage = () => {};
    const firstPageHeld = new Promise((resolve) => (releaseFirstPage = resolve));
    let firstPageAsked = false;
    responses.set("/api/git/log", async (url) => {
      const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
      if (cursor?.startsWith("test:")) {
        return { httpStatus: 410 };
      }
      const page = cursor ? Number(cursor.split(":")[1]) : 0;
      if (page === 0) {
        firstPageAsked = true;
        await firstPageHeld;
      }
      return historyPage(page, deepCommits.slice(page * 2, page * 2 + 2), total, revisions[0]);
    });
    neutralLanding = true;
    void panel.restoreCommitLanding();
    for (let tick = 0; tick < 50 && !firstPageAsked; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    assertTrue("left recovery: recovery's first page is held", firstPageAsked);
    // The reader switches to Files: the shell gives up the pane, which cancels Git's pending
    // work, hides the Commits panel, and puts back the offset Files had in the shared scroller.
    panel.cancelPending();
    sandbox.MetabrowserShell.claimPreview("none");
    neutralLanding = false;
    container.style.display = "none";
    container.scrollTop = 250;
    previewHtml = '<div class="file-view">Files preview</div>';
    const routesBefore = replacedRoutes.length;
    releaseFirstPage();
    for (let tick = 0; tick < 50; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    assertEqual("left recovery: Files keeps its offset", container.scrollTop, 250);
    assertEqual(
      "left recovery: the Files preview stays",
      previewHtml,
      '<div class="file-view">Files preview</div>',
    );
    assertEqual("left recovery: no commit takes the address", replacedRoutes.length, routesBefore);
    delete container.style.display;
    delete container.clientHeight;
    container.scrollTop = 0;
  }

  // ── Bounded session recovery ───────────────────────────────
  //
  // A reaped session replays its prefix one request per page against a
  // fresh walk, so a deep pre-expiry position must restore to the
  // bounded PAGE_CACHE_PAGES * LOG_LIMIT depth rather than issuing one
  // request per LOG_LIMIT rows of unbounded prefix.
  {
    const total = 40;
    const revisions = Array.from({ length: total }, (_value, index) =>
      (index + 3000).toString(16).padStart(40, "0"),
    );
    const recoveryCommits = revisions.map((revision, index) =>
      commit(
        revision,
        index + 1 < total ? [revisions[index + 1]] : [],
        `recovery commit ${index}`,
        index === 0
          ? [{ id: "refs/heads/main", name: "main", kind: "branch", is_head: true }]
          : undefined,
      ),
    );
    // A row focused by the keyboard tests would otherwise donate its
    // ordinal to the render pass and mask the staged deep position.
    document.activeElement = null;
    responses.set("/api/git/repo", {
      is_repo: true,
      root: "",
      head: { ref: "refs/heads/main", revision: revisions[0], detached: false, unborn: false },
    });
    responses.set("/api/git/refs", { is_repo: true, refs: [] });
    let logCalls = 0;
    responses.set("/api/git/log", (url) => {
      logCalls += 1;
      if (logCalls === 1) {
        return { httpStatus: 410 };
      }
      const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
      const page = cursor ? Number(cursor.split(":")[1]) : 0;
      return historyPage(page, recoveryCommits.slice(page * 2, page * 2 + 2), total, revisions[0]);
    });
    const expired = internals.emptyState();
    expired.headRevision = revisions[0];
    expired.cursor = "history:9";
    expired.nextPageNumber = 9;
    expired.rowCount = 18;
    expired.focusedOrdinal = 17;
    internals.setStateForTests(expired);
    await internals.loadNextPage(false);
    const recovered = internals.stateForTests();
    assertEqual(
      "recovery: replay is bounded by the page cache depth",
      logCalls,
      // The 410 itself, then pages 0 and 1: rows 0..3 cover the capped
      // restore ordinal of PAGE_CACHE_PAGES * LOG_LIMIT - 1 = 3.
      3,
    );
    assertEqual("recovery: restored rows stop at the cap", recovered.rowCount, 4);
    assertEqual("recovery: focus lands on the capped ordinal", recovered.focusedOrdinal, 3);
    assertTrue("recovery: the rebuilt session is not failed", !recovered.failed);
  }

  // A selection the reader makes while recovery rebuilds the walk keeps its place: recovery
  // gives up restoring the expired position, and asks for no pages to reach it.
  {
    const total = 8;
    const revisions = Array.from({ length: total }, (_value, index) =>
      (index + 6000).toString(16).padStart(40, "0"),
    );
    const walk = revisions.map((revision, index) =>
      commit(revision, index + 1 < total ? [revisions[index + 1]] : [], `rebuilt ${index}`),
    );
    const container = document.getElementById("tab-git");
    document.activeElement = null;
    container.clientHeight = 44;
    responses.set("/api/git/repo", {
      is_repo: true,
      root: "",
      head: { ref: "refs/heads/main", revision: revisions[0], detached: false, unborn: false },
    });
    responses.set(`/api/git/commit/${revisions[1]}`, {
      is_repo: true,
      commit: commit(revisions[1], [], "chosen during recovery"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    let logCalls = 0;
    responses.set("/api/git/log", (url) => {
      logCalls += 1;
      if (logCalls === 1) {
        return { httpStatus: 410 };
      }
      const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
      const page = cursor ? Number(cursor.split(":")[1]) : 0;
      if (page === 0) {
        // The reader picks a commit while the rebuilt walk's first page is on its way.
        void internals.selectCommit(revisions[1]);
      }
      return historyPage(page, walk.slice(page * 2, page * 2 + 2), total, revisions[0]);
    });
    const expired = internals.emptyState();
    expired.headRevision = revisions[0];
    expired.cursor = "history:3";
    expired.nextPageNumber = 3;
    expired.rowCount = 6;
    expired.focusedOrdinal = 5;
    internals.setStateForTests(expired);
    await internals.loadNextPage(false);
    for (let tick = 0; tick < 20; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    const kept = internals.stateForTests();
    const anchor = container.querySelector(".git-graph-row[data-roving-anchor]");
    assertEqual("recovery: the reader's selection stands", kept.selectedId, revisions[1]);
    assertEqual("recovery: no page is asked for to restore the old place", logCalls, 2);
    assertEqual("recovery: the reader's row is the Tab stop", anchor?.dataset.ordinal, "1");
    delete container.clientHeight;
    container.scrollTop = 0;
  }

  // ── Recovery takes the rebuilt rows' refs ────────────────
  //
  // A commit's detail carries its refs, which move while its id does not. Expired-session
  // recovery keeps the detail cache so the summary and diff on screen are not redrawn, so a
  // cached detail takes the refs of the rebuilt row: the row, its tooltip, and the summary
  // agree. A cached detail whose row the rebuilt session has not served is fetched again.
  {
    const container = document.getElementById("tab-git");
    const total = 8;
    const revisions = Array.from({ length: total }, (_value, index) =>
      (index + 5000).toString(16).padStart(40, "0"),
    );
    const tagged = revisions[0];
    const deep = revisions[4];
    const ref = (revision, name, kind, extra = {}) => ({
      id: kind === "tag" ? `refs/tags/${name}` : `refs/heads/${name}`,
      name,
      kind,
      revision,
      ...extra,
    });
    let moved = false;
    const refsOf = (revision) => {
      if (revision === tagged) {
        return moved
          ? [
              ref(tagged, "main", "branch", { is_head: true, is_trunk: true }),
              ref(tagged, "moved-tag", "tag"),
            ]
          : [
              ref(tagged, "main", "branch", { is_head: true, is_trunk: true }),
              ref(tagged, "gone-tag", "tag"),
            ];
      }
      if (revision === deep) {
        return [ref(deep, moved ? "deep-now" : "deep-before", "branch")];
      }
      return undefined;
    };
    const commitAt = (index) =>
      commit(
        revisions[index],
        index + 1 < total ? [revisions[index + 1]] : [],
        `ref move commit ${index}`,
        refsOf(revisions[index]),
      );
    document.activeElement = null;
    responses.set("/api/git/repo", {
      is_repo: true,
      root: "",
      head: { ref: "refs/heads/main", revision: tagged, detached: false, unborn: false },
    });
    responses.set("/api/git/refs", { is_repo: true, refs: [] });
    let expire = false;
    responses.set("/api/git/log", (url) => {
      if (expire) {
        expire = false;
        return { httpStatus: 410 };
      }
      const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
      const page = cursor ? Number(cursor.split(":")[1]) : 0;
      return historyPage(page, [commitAt(page * 2), commitAt(page * 2 + 1)], total, tagged);
    });
    for (const revision of [tagged, deep]) {
      responses.set(`/api/git/commit/${revision}`, () => ({
        is_repo: true,
        commit: commit(revision, [], "ref move detail", refsOf(revision)),
        body: "",
        stats: { files_changed: 1, additions: 1, deletions: 0 },
        files: [],
        files_truncated: false,
      }));
    }
    const detailFetches = (revision) =>
      fetchRequests.filter((request) => request.url.startsWith(`/api/git/commit/${revision}`))
        .length;
    const rowHtml = (revision) =>
      container.querySelectorAll(".git-graph-row").find((row) => row.dataset.revision === revision)
        ?.innerHTML ?? "";
    const hoverTooltip = async (revision) => {
      const row = container
        .querySelectorAll(".git-graph-row")
        .find((candidate) => candidate.dataset.revision === revision);
      shownTooltips.length = 0;
      row._hovered = true;
      row.dispatch("mouseenter");
      await new Promise((resolve) => setTimeout(resolve, 10));
      row._hovered = false;
      row.dispatch("mouseleave");
      return shownTooltips.at(-1)?.html ?? "";
    };
    const mountedRefs = () =>
      document.getElementById("preview-pane").querySelector(".git-commit-refs")?.innerHTML ?? "";

    const fresh = internals.emptyState();
    fresh.headRevision = tagged;
    internals.setStateForTests(fresh);
    await internals.loadNextPage(true);
    await internals.loadNextPage(false);
    await internals.loadNextPage(false);
    internals.renderPanel();
    // Both details cached; the tagged commit's summary is the one on screen.
    await internals.selectCommit(deep);
    await internals.selectCommit(tagged);
    assertContains("ref move: the row starts with the old tag", rowHtml(tagged), "gone-tag");
    assertContains("ref move: the summary starts with the old tag", mountedRefs(), "gone-tag");
    const taggedFetches = detailFetches(tagged);
    const deepFetches = detailFetches(deep);
    const diffRenders = renderedDiffRevisions.length;

    // The session expires and the tag moves to another name; the next page answers 410.
    moved = true;
    expire = true;
    await internals.loadNextPage(false);
    internals.renderPanel();
    const tooltip = await hoverTooltip(tagged);
    assertContains("ref move: the rebuilt row shows the moved tag", rowHtml(tagged), "moved-tag");
    assertNotContains("ref move: the rebuilt row drops the old tag", rowHtml(tagged), "gone-tag");
    assertContains("ref move: the tooltip agrees with its row", tooltip, "moved-tag");
    assertNotContains("ref move: the tooltip drops the old tag", tooltip, "gone-tag");
    assertContains(
      "ref move: the summary on screen agrees with its row",
      mountedRefs(),
      "moved-tag",
    );
    assertNotContains("ref move: the summary drops the old tag", mountedRefs(), "gone-tag");
    assertContains("ref move: the summary keeps its other refs", mountedRefs(), "git-ref-head");
    assertEqual(
      "ref move: the rebuilt row's detail is not fetched again",
      detailFetches(tagged),
      taggedFetches,
    );
    assertEqual(
      "ref move: recovery does not redraw the diff",
      renderedDiffRevisions.length,
      diffRenders,
    );

    // The deep commit's row is past the replay depth, so its cached refs are unconfirmed:
    // selecting it asks again, and draws the refs the server has now.
    await internals.selectCommit(deep);
    assertEqual(
      "ref move: an unconfirmed detail is fetched again",
      detailFetches(deep),
      deepFetches + 1,
    );
    assertContains("ref move: the refetched summary has the current refs", previewHtml, "deep-now");
    assertNotContains(
      "ref move: the refetched summary drops the old refs",
      previewHtml,
      "deep-before",
    );
  }

  // ── Refs stay current through every rebuild ───────────────
  //
  // A detail's refs are true for the history session they were read in. Each case below
  // fails without the session stamp on details and the summary on screen: a selected
  // commit recovery does not replay (B1), work that outlives a rebuild (B2), a refetched
  // detail after eviction (B3), and the summary record after its view goes (B4).
  {
    const container = document.getElementById("tab-git");
    const total = 8;
    const revisions = Array.from({ length: total }, (_value, index) =>
      (index + 6000).toString(16).padStart(40, "0"),
    );
    const at = (index) => revisions[index];
    let moved = false;
    let headRef = "refs/heads/main";
    let expire = false;
    // Each commit carries one branch whose name says whether the refs have moved yet.
    const refsOf = (revision) => {
      const name = `b${revisions.indexOf(revision)}-${moved ? "now" : "old"}`;
      return [{ id: `refs/heads/${name}`, name, kind: "branch", revision }];
    };
    const detailFor = (revision) => ({
      is_repo: true,
      commit: commit(revision, [], "session stamp detail", refsOf(revision)),
      body: "",
      stats: { files_changed: 1, additions: 1, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    const serveDetail = (revision) =>
      responses.set(`/api/git/commit/${revision}`, () => detailFor(revision));
    const serveAll = () => {
      responses.set("/api/git/repo", () => ({
        is_repo: true,
        root: "",
        head: { ref: headRef, revision: at(0), detached: false, unborn: false },
      }));
      responses.set("/api/git/refs", { is_repo: true, refs: [] });
      responses.set("/api/git/log", (url) => {
        if (expire) {
          expire = false;
          return { httpStatus: 410 };
        }
        const cursor = new URL(`http://metabrowser.invalid${url}`).searchParams.get("cursor");
        const page = cursor ? Number(cursor.split(":")[1]) : 0;
        const commits = [page * 2, page * 2 + 1].map((index) =>
          commit(
            at(index),
            index + 1 < total ? [at(index + 1)] : [],
            `stamp ${index}`,
            refsOf(at(index)),
          ),
        );
        return historyPage(page, commits, total, at(0));
      });
      for (const revision of revisions) {
        serveDetail(revision);
      }
    };
    const detailFetches = (revision) =>
      fetchRequests.filter((request) => request.url.startsWith(`/api/git/commit/${revision}`))
        .length;
    const mountedRefs = () =>
      document.getElementById("preview-pane").querySelector(".git-commit-refs")?.innerHTML ?? "";
    const tick = () => new Promise((resolve) => setTimeout(resolve, 10));
    // Rows 0..5 loaded and a cursor left for page 3, so the next page request can expire.
    // Recovery replays at most rows 0..3, so row 4 is past its depth.
    const freshSession = async () => {
      moved = false;
      headRef = "refs/heads/main";
      expire = false;
      serveAll();
      document.activeElement = null;
      const fresh = internals.emptyState();
      fresh.headRevision = at(0);
      fresh.headRef = headRef;
      internals.setStateForTests(fresh);
      await internals.loadNextPage(true);
      await internals.loadNextPage(false);
      await internals.loadNextPage(false);
      internals.renderPanel();
    };
    const expireAndRecover = async () => {
      moved = true;
      expire = true;
      await internals.loadNextPage(false);
      internals.renderPanel();
    };
    const rowFor = (revision) =>
      container.querySelectorAll(".git-graph-row").find((row) => row.dataset.revision === revision);

    // B1: the selected commit is past the replay depth, so no rebuilt row confirms its
    // refs; recovery reads them again and replaces only the refs group.
    await freshSession();
    await internals.selectCommit(at(4));
    assertContains("B1 recovery: the summary starts with the old branch", mountedRefs(), "b4-old");
    let diffRenders = renderedDiffRevisions.length;
    let comparisons = comparisonFetches.length;
    await expireAndRecover();
    assertContains(
      "B1 recovery: an unreplayed selection takes its current refs",
      mountedRefs(),
      "b4-now",
    );
    assertNotContains(
      "B1 recovery: an unreplayed selection drops its old refs",
      mountedRefs(),
      "b4-old",
    );
    assertEqual(
      "B1 recovery: the diff is not drawn again",
      renderedDiffRevisions.length,
      diffRenders,
    );
    assertEqual(
      "B1 recovery: the comparison is not fetched again",
      comparisonFetches.length,
      comparisons,
    );

    // B1: a full refresh whose first page does not hold the commit on screen.
    await freshSession();
    await internals.selectCommit(at(4));
    assertContains("B1 refresh: the summary starts with the old branch", mountedRefs(), "b4-old");
    diffRenders = renderedDiffRevisions.length;
    comparisons = comparisonFetches.length;
    moved = true;
    headRef = "refs/heads/other";
    registeredPanel.onShow();
    for (let attempt = 0; attempt < 10 && !mountedRefs().includes("b4-now"); attempt += 1) {
      await tick();
    }
    assertContains(
      "B1 refresh: a summary off the first page takes its current refs",
      mountedRefs(),
      "b4-now",
    );
    assertEqual(
      "B1 refresh: the diff is not drawn again",
      renderedDiffRevisions.length,
      diffRenders,
    );
    assertEqual(
      "B1 refresh: the comparison is not fetched again",
      comparisonFetches.length,
      comparisons,
    );

    // B2: a selection staged with old refs waits for the diff's assets while the history
    // is rebuilt; it installs with the refs the rebuilt session confirmed.
    await freshSession();
    const ensureKindAssets = sandbox.metabrowser.ensureKindAssets;
    let releaseAssets = () => {};
    sandbox.metabrowser.ensureKindAssets = () =>
      new Promise((resolve) => {
        releaseAssets = resolve;
      });
    const staging = internals.selectCommit(at(0));
    await tick();
    await expireAndRecover();
    releaseAssets();
    await staging;
    await tick();
    sandbox.metabrowser.ensureKindAssets = ensureKindAssets;
    assertContains(
      "B2 staged: the installed summary has the current refs",
      mountedRefs(),
      "b0-now",
    );
    assertNotContains(
      "B2 staged: the installed summary drops the old refs",
      mountedRefs(),
      "b0-old",
    );

    // B2: the selected row's detail was evicted, so hovering it reads the detail without a
    // preparation; that read answers after the rebuild with the old refs, and must not put
    // them back in the cache or on the tooltip.
    await freshSession();
    await internals.selectCommit(at(0));
    for (const index of [1, 2, 3]) {
      await internals.fetchCommitDetail(at(index));
    }
    const oldDetail = detailFor(at(0));
    let answerHover = () => {};
    responses.set(
      `/api/git/commit/${at(0)}`,
      () =>
        new Promise((resolve) => {
          answerHover = () => resolve(oldDetail);
        }),
    );
    const hovered = rowFor(at(0));
    shownTooltips.length = 0;
    hovered._hovered = true;
    hovered.dispatch("mouseenter");
    await tick();
    await expireAndRecover();
    serveDetail(at(0));
    answerHover();
    await tick();
    hovered._hovered = false;
    hovered.dispatch("mouseleave");
    const afterHover = await internals.fetchCommitDetail(at(0));
    assertEqual(
      "B2 hover: a read that outlived its session leaves no old refs in the cache",
      afterHover?.commit.refs?.map((ref) => ref.name),
      ["b0-now"],
    );
    assertTrue(
      "B2 hover: the tooltip never shows the old refs",
      !shownTooltips.some((tip) => tip.html.includes("b0-old")),
    );

    // B3: a detail cached before recovery, past its replay depth, is evicted; reading it
    // twice afterward fetches it once. Twice over, for repeated recovery and eviction.
    for (const round of [1, 2]) {
      await freshSession();
      for (const index of [0, 1, 4]) {
        await internals.fetchCommitDetail(at(index));
      }
      await expireAndRecover();
      for (const index of [2, 3, 5]) {
        await internals.fetchCommitDetail(at(index));
      }
      const before = detailFetches(at(4));
      await internals.fetchCommitDetail(at(4));
      await internals.fetchCommitDetail(at(4));
      assertEqual(
        `B3 round ${round}: an evicted, refetched detail is read from the cache the second time`,
        detailFetches(at(4)),
        before + 1,
      );
    }

    // B4: the summary record goes with its view: when another owner takes the preview,
    // when a selection fails, and never when a retired view is disposed after a newer one.
    await freshSession();
    await internals.selectCommit(at(0));
    assertEqual("B4: the summary on screen is recorded", internals.mountedSummaryRevision(), at(0));
    const handoff = panel.cancelPending();
    assertEqual(
      "B4: a relinquished view releases its summary",
      internals.mountedSummaryRevision(),
      null,
    );
    await internals.selectCommit(at(1));
    assertEqual("B4: the next view records its summary", internals.mountedSummaryRevision(), at(1));
    handoff?.();
    assertEqual(
      "B4: disposing the retired view keeps the newer summary",
      internals.mountedSummaryRevision(),
      at(1),
    );
    responses.set(`/api/git/commit/${at(5)}`, {
      httpStatus: 404,
      body: { error: "commit not found", code: "commit_not_found" },
    });
    await internals.selectCommit(at(5));
    assertEqual(
      "B4: a failed selection releases the summary",
      internals.mountedSummaryRevision(),
      null,
    );

    // C1: a read that would confirm the refs of the summary on screen fails. The summary
    // shows no refs rather than the old session's, and the diff is left alone; the next
    // page to arrive tries again. Through recovery, a full refresh, and a staged install.
    const failDetail = (revision) =>
      responses.set(`/api/git/commit/${revision}`, {
        httpStatus: 500,
        body: { error: "boom", code: "internal" },
      });
    await freshSession();
    await internals.selectCommit(at(4));
    diffRenders = renderedDiffRevisions.length;
    comparisons = comparisonFetches.length;
    failDetail(at(4));
    await expireAndRecover();
    assertNotContains("C1 recovery: a failed read shows no old refs", mountedRefs(), "b4-old");
    assertEqual("C1 recovery: the summary shows no refs", mountedRefs(), "");
    assertEqual(
      "C1 recovery: the diff is not drawn again",
      renderedDiffRevisions.length,
      diffRenders,
    );
    assertEqual(
      "C1 recovery: the comparison is not fetched again",
      comparisonFetches.length,
      comparisons,
    );
    serveDetail(at(4));
    await internals.loadNextPage(false);
    await tick();
    assertContains(
      "C1 recovery: the next page to arrive confirms the refs",
      mountedRefs(),
      "b4-now",
    );

    await freshSession();
    await internals.selectCommit(at(4));
    failDetail(at(4));
    moved = true;
    headRef = "refs/heads/other";
    registeredPanel.onShow();
    for (let attempt = 0; attempt < 10 && mountedRefs().includes("b4-old"); attempt += 1) {
      await tick();
    }
    await tick();
    assertNotContains("C1 refresh: a failed read shows no old refs", mountedRefs(), "b4-old");
    serveDetail(at(4));
    registeredPanel.onShow();
    for (let attempt = 0; attempt < 10 && !mountedRefs().includes("b4-now"); attempt += 1) {
      await tick();
    }
    assertContains(
      "C1 refresh: showing the panel again confirms the refs",
      mountedRefs(),
      "b4-now",
    );

    await freshSession();
    sandbox.metabrowser.ensureKindAssets = () =>
      new Promise((resolve) => {
        releaseAssets = resolve;
      });
    const stagingDeep = internals.selectCommit(at(4));
    await tick();
    failDetail(at(4));
    await expireAndRecover();
    releaseAssets();
    await stagingDeep;
    await tick();
    sandbox.metabrowser.ensureKindAssets = ensureKindAssets;
    assertNotContains("C1 staged: a failed read installs no old refs", mountedRefs(), "b4-old");
    serveDetail(at(4));

    // C2: a confirmation still waiting on its read does not keep a summary that was taken
    // off the screen alive.
    const v8 = require("node:v8");
    v8.setFlagsFromString("--expose-gc");
    const collect = vm.runInNewContext("gc");
    await freshSession();
    await internals.selectCommit(at(4));
    let answerDeep = () => {};
    responses.set(
      `/api/git/commit/${at(4)}`,
      () =>
        new Promise((resolve) => {
          answerDeep = () => resolve(detailFor(at(4)));
        }),
    );
    const identityRef = new WeakRef(
      document.getElementById("preview-pane").querySelector(".git-commit-identity"),
    );
    const recovering = expireAndRecover();
    await tick();
    panel.cancelPending();
    sandbox.MetabrowserShell.renderPreviewHtml(
      "<div>elsewhere</div>",
      sandbox.MetabrowserShell.claimPreview("file"),
    );
    stagedPreviewNodes.length = 0;
    previewNode = null;
    await tick();
    collect();
    await tick();
    collect();
    assertTrue(
      "C2: a pending confirmation does not keep a disposed summary alive",
      identityRef.deref() === undefined,
    );
    answerDeep();
    await recovering;
    serveDetail(at(4));

    // D1: Reload history after the refs moved, and the repository request fails, with a
    // 500 and with a rejection. The summary shows none of the old session's refs, its
    // diff stays, and the refresh that succeeds confirms the refs.
    for (const failure of ["500", "rejection"]) {
      await freshSession();
      await internals.selectCommit(at(0));
      assertContains(
        `D1 ${failure}: the summary starts with the old branch`,
        mountedRefs(),
        "b0-old",
      );
      diffRenders = renderedDiffRevisions.length;
      comparisons = comparisonFetches.length;
      // The next page says the history changed, which offers Reload history.
      responses.set("/api/git/log", {
        httpStatus: 409,
        body: { error: "git history changed; refresh required", code: "history_stale" },
      });
      await internals.loadNextPage(false);
      const reload = container
        .querySelector(".git-history-stale")
        ?.querySelector(".git-history-reload");
      assertTrue(`D1 ${failure}: Reload history is offered`, reload);
      moved = true;
      responses.set(
        "/api/git/repo",
        failure === "500"
          ? { httpStatus: 500, body: {} }
          : () => {
              throw new Error("the network went away");
            },
      );
      reload?.dispatch("click");
      for (let attempt = 0; attempt < 20 && !internals.stateForTests().failed; attempt += 1) {
        await tick();
      }
      assertTrue(`D1 ${failure}: the refresh failed`, internals.stateForTests().failed);
      assertEqual(`D1 ${failure}: the summary shows no refs`, mountedRefs(), "");
      assertEqual(
        `D1 ${failure}: the diff is not drawn again`,
        renderedDiffRevisions.length,
        diffRenders,
      );
      assertEqual(
        `D1 ${failure}: the comparison is not fetched again`,
        comparisonFetches.length,
        comparisons,
      );
      serveAll();
      container.querySelector(".git-panel-refresh")?.dispatch("click");
      for (let attempt = 0; attempt < 20 && !mountedRefs().includes("b0-now"); attempt += 1) {
        await tick();
      }
      assertContains(
        `D1 ${failure}: the refresh that succeeds confirms the refs`,
        mountedRefs(),
        "b0-now",
      );
      assertEqual(
        `D1 ${failure}: the diff stays through the retry`,
        renderedDiffRevisions.length,
        diffRenders,
      );
    }

    // C3: the selected row's evicted detail is read on hover without a preparation, and
    // the panel is torn down before it answers. The late answer starts no further read
    // and puts nothing in the cleared cache.
    await freshSession();
    await internals.selectCommit(at(0));
    for (const index of [1, 2, 3]) {
      await internals.fetchCommitDetail(at(index));
    }
    let answerLate = () => {};
    const lateDetail = detailFor(at(0));
    responses.set(
      `/api/git/commit/${at(0)}`,
      () =>
        new Promise((resolve) => {
          answerLate = () => resolve(lateDetail);
        }),
    );
    const lateRow = rowFor(at(0));
    lateRow._hovered = true;
    lateRow.dispatch("mouseenter");
    await tick();
    internals.teardown();
    serveDetail(at(0));
    const beforeLate = detailFetches(at(0));
    answerLate();
    await tick();
    await tick();
    lateRow._hovered = false;
    const afterLate = detailFetches(at(0));
    assertEqual("C3: a hover answered after teardown reads nothing more", afterLate, beforeLate);
    await internals.fetchCommitDetail(at(0));
    assertEqual("C3: the cleared cache stays empty", detailFetches(at(0)), afterLate + 1);
    // Put the panel back for the cases after this one.
    await panel.init();
    registeredPanel.onShow();
    await tick();
  }

  // ── A stale cursor is a typed state with a reload action ───
  //
  // `history_stale` means the refs the walk was fingerprinted by moved, as
  // a mirror refresh or a pin switch in another tab does. The panel keeps
  // the rows it has, says the history changed, stops paging, and reloads
  // only when asked; it neither replays a different walk silently nor
  // reports a failure.
  {
    responses.set("/api/git/repo", {
      is_repo: true,
      root: "",
      head: { ref: "refs/heads/main", revision: SHA_A, detached: false, unborn: false },
    });
    responses.set("/api/git/refs", { is_repo: true, refs: [] });
    let staleCalls = 0;
    responses.set("/api/git/log", () => {
      staleCalls += 1;
      return {
        httpStatus: 409,
        body: { error: "git history changed; refresh required", code: "history_stale" },
      };
    });
    const open = internals.emptyState();
    open.headRevision = SHA_A;
    internals.setStateForTests(open);
    appendTestPage([commit(SHA_A, [SHA_B], "on screen")], "history:1");
    const before = internals.stateForTests();
    assertEqual("stale: one row on screen before the next page", before.rowCount, 1);
    await internals.loadNextPage(false);
    const stale = internals.stateForTests();
    assertEqual("stale: one request, no silent replay", staleCalls, 1);
    assertTrue("stale: the state is typed stale", stale.stale);
    assertTrue("stale: a stale walk is not a failure", !stale.failed);
    assertEqual("stale: rows on screen are kept", stale.rowCount, 1);
    internals.renderVirtualRows();
    assertEqual("stale: scrolling does not page past a stale walk", staleCalls, 1);
    const panelNode = document.getElementById("tab-git");
    const notice = panelNode.querySelector(".git-history-stale");
    assertTrue("stale: the panel says the history changed", notice);
    assertContains(
      "stale: the notice text",
      notice?.textContent ?? "",
      "History changed since this list loaded.",
    );
    const reload = notice?.querySelector(".git-history-reload");
    assertTrue("stale: the notice offers a reload", reload);
    responses.set("/api/git/log", historyPage(0, [commit(SHA_B, [], "reloaded")], 1, SHA_A));
    reload?.dispatch("click");
    for (let tick = 0; tick < 50 && internals.stateForTests().commits.length === 0; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    for (let tick = 0; tick < 50 && internals.stateForTests().loading; tick += 1) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
    const reloaded = internals.stateForTests();
    assertTrue("stale: reload starts a new walk", !reloaded.stale);
    assertEqual("stale: the new walk has its own rows", reloaded.commits[0]?.id, SHA_B);
    // The reloaded walk reached its end; later checks start from an open one.
    internals.setStateForTests(internals.emptyState());
  }

  // ── Teardown restores the shared scroller ──────────────────
  //
  // The focus-suspension path writes tabindex onto the shell-owned
  // scroller. Teardown must remove it: the tree keeps using that node
  // after the Git panel is gone.
  {
    const scroller = document.getElementById("tab-git");
    scroller.setAttribute("tabindex", "-1");
    responses.set("/api/git/log", { is_repo: false, reason: "not_a_repo" });
    const gone = internals.stateForTests();
    gone.cursor = "history:1";
    gone.nextPageNumber = 1;
    internals.setStateForTests(gone);
    await internals.loadNextPage(false);
    assertEqual(
      "teardown: shared scroller focusability is restored",
      scroller.getAttribute("tabindex"),
      null,
    );
  }

  // ── History header tally ───────────────────────────────────
  //
  // The Git tab's counterpart of the file tree's "N files (size)" row:
  // rendered pending with the first page, filled by a later request.
  {
    document.activeElement = null;
    const nowSeconds = Math.floor(Date.now() / 1000);
    responses.set("/api/git/repo", {
      is_repo: true,
      root: "",
      head: { ref: "refs/heads/main", revision: SHA_A, detached: false, unborn: false },
    });
    responses.set("/api/git/refs", { is_repo: true, refs: [] });
    responses.set("/api/git/log", historyPage(0, [commit(SHA_A, [], "tally commit")], 1, SHA_A));
    let summaryRequested = false;
    responses.set("/api/git/summary", () => {
      summaryRequested = true;
      return {
        is_repo: true,
        commit_count: 10345,
        first_commit_at: nowSeconds - 2 * 365 * 24 * 60 * 60,
      };
    });
    internals.setStateForTests(internals.emptyState());
    registeredPanel.onShow();
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));
    assertTrue("tally: the summary loads on its own request", summaryRequested);
    const container = document.getElementById("tab-git");
    assertContains("tally: commit count renders", container.textContent, "10,345 commits");
    assertContains("tally: begun wording renders", container.textContent, "begun");
    const tallyAge = container.querySelector(".git-history-summary-age");
    assertTrue("tally: age value is present", tallyAge !== null);
    assertEqual("tally: age value uses the shared formatter", tallyAge?.textContent, "2y");
    assertContains(
      "tally: age value carries the shared freshness tier",
      tallyAge?.className,
      "age-old",
    );
    responses.delete("/api/git/summary");
  }

  // ── A commit the repository does not have ──────────────────
  {
    responses.clear();
    const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
    const notFound = {
      httpStatus: 404,
      body: { error: "unknown revision", code: "commit_not_found" },
    };
    const SHA_MISSING = "2".repeat(40);
    const SHA_BROKEN = "3".repeat(40);
    const SHA_UNFETCHED = "4".repeat(40);
    const SHA_LEFT = "5".repeat(40);

    // A folder has no mirror to fetch into: the commit is simply not there.
    freshnessController = null;
    responses.set(`/api/git/commit/${SHA_MISSING}`, notFound);
    await internals.selectCommit(SHA_MISSING);
    await tick();
    assertContains("missing commit: a folder names the miss", previewHtml, "Commit not found");
    assertContains(
      "missing commit: a folder says where it looked",
      previewHtml,
      "This commit is not in the repository.",
    );
    assertNotContains("missing commit: not a load failure", previewHtml, "Could not load");
    assertEqual(
      "missing commit: a folder offers no fetch",
      previewNode.querySelector(".git-commit-missing-retry"),
      null,
    );
    assertEqual("missing commit: state on the element", previewNode.dataset.state, "not_found");

    // A request that failed is still a load failure, not a missing commit.
    responses.set(`/api/git/commit/${SHA_BROKEN}`, {
      httpStatus: 500,
      body: { error: "git command failed" },
    });
    await internals.selectCommit(SHA_BROKEN);
    await tick();
    assertContains(
      "failed commit: says it could not load",
      previewHtml,
      "Could not load this commit.",
    );

    // The diff plugin's load is refused when the SDK's view helpers cannot be fetched.
    // The commit's own detail still stands and its diff says it could not load. The
    // refusal arrives before the detail does, and nothing awaits it until then: left
    // unhandled, it would end this session here.
    const SHA_NO_ASSETS = "8".repeat(40);
    responses.set(`/api/git/commit/${SHA_NO_ASSETS}`, async () => {
      await new Promise((resolve) => setTimeout(resolve, 5));
      return {
        is_repo: true,
        commit: commit(SHA_NO_ASSETS, [], "diff assets refused"),
        body: "",
        stats: { files_changed: 1, additions: 1, deletions: 0 },
        files: [{ path: "one.js", status: "modified", additions: 1, deletions: 0 }],
        files_truncated: false,
      };
    });
    const ensureKindAssets = sandbox.metabrowser.ensureKindAssets;
    sandbox.metabrowser.ensureKindAssets = async () => {
      throw new Error("Failed to load asset: /static/plugin-sdk-views.js");
    };
    await internals.selectCommit(SHA_NO_ASSETS);
    await tick();
    sandbox.metabrowser.ensureKindAssets = ensureKindAssets;
    assertContains("refused diff assets: the commit is shown", previewHtml, "diff assets refused");
    assertEqual(
      "refused diff assets: the diff says it could not load",
      previewNode.querySelector(".git-commit-diff")?.textContent,
      "Could not load this commit's diff.",
    );

    // A served mirror: the commit view asks the page's controller for the fetch such a
    // commit waits for, and says how that ended.
    const mirrorStatus = (outcome) => ({
      subject: "git_revision",
      generation: 1,
      pin: SHA_A,
      ref: null,
      ref_name: null,
      refreshable: true,
      latest: null,
      ref_on_origin: null,
      last_fetch_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      last_outcome: { operation: "refresh", outcome, at: new Date().toISOString() },
      refreshing: false,
      stale: false,
      pull_request: null,
      selection_state: null,
      selection_href: null,
    });
    const asked = [];
    let endFetch = null;
    // What the controller answers without waiting: inside the freshness window it asks
    // for nothing. Otherwise it says it is waiting and answers when the fetch ends.
    let insideWindow = false;
    freshnessController = {
      fetchMissing: (options) => {
        asked.push(options.retry === true ? "retry" : "own");
        if (insideWindow) {
          return Promise.resolve({
            status: mirrorStatus("succeeded"),
            error: null,
            fetched: false,
            waited: false,
          });
        }
        options.waiting?.();
        return new Promise((resolve) => {
          endFetch = resolve;
        });
      },
    };
    const fetched = (outcome) => ({
      status: mirrorStatus(outcome),
      error: null,
      fetched: true,
      waited: true,
    });
    const commitRequests = (revision) =>
      fetchRequests.filter((request) => request.url.startsWith(`/api/git/commit/${revision}`))
        .length;

    responses.set(`/api/git/commit/${SHA_UNFETCHED}`, notFound);
    const previewPane = document.getElementById("preview-pane");
    const priorView = document.createElement("div");
    priorView.textContent = "prior view";
    previewPane.replaceChildren(priorView);
    const selecting = internals.selectCommit(SHA_UNFETCHED);
    await Promise.resolve();
    assertEqual(
      "unfetched commit: the pane is busy while the commit is asked for",
      previewPane.getAttribute("aria-busy"),
      "true",
    );
    await selecting;
    await tick();
    assertEqual("unfetched commit: the page's own request is made", asked, ["own"]);
    assertContains("unfetched commit: says it is fetching", previewHtml, "Fetching this commit");
    assertEqual(
      "unfetched commit: pending is a status",
      previewNode.getAttribute("role"),
      "status",
    );
    assertEqual(
      "unfetched commit: the pending state has left the busy state",
      previewPane.getAttribute("aria-busy"),
      null,
    );

    endFetch(fetched("origin_unavailable"));
    await tick();
    await tick();
    assertContains("unfetched commit: names the failed fetch", previewHtml, "Commit not fetched");
    assertContains("unfetched commit: says why", previewHtml, "The origin could not be read.");
    assertEqual(
      "unfetched commit: the failure is an alert",
      previewNode.getAttribute("role"),
      "alert",
    );
    const retry = previewNode.querySelector(".git-commit-missing-retry");
    assertTrue("unfetched commit: offers the fetch again", retry !== null);

    // Retry is the reader's click; this time the fetch brings the commit and it opens.
    retry.dispatch("click");
    await tick();
    assertEqual("unfetched commit: the click asks as a retry", asked, ["own", "retry"]);
    assertContains(
      "unfetched commit: retry says it is fetching",
      previewHtml,
      "Fetching this commit",
    );
    responses.set(`/api/git/commit/${SHA_UNFETCHED}`, {
      is_repo: true,
      commit: commit(SHA_UNFETCHED, [], "commit the fetch brought"),
      body: "",
      stats: { files_changed: 0, additions: 0, deletions: 0 },
      files: [],
      files_truncated: false,
    });
    endFetch(fetched("succeeded"));
    await tick();
    await tick();
    assertContains("unfetched commit: opens once fetched", previewHtml, "commit the fetch brought");

    // Selecting it again reads the commit, not the remembered miss, and asks for nothing.
    await internals.selectCommit(SHA_A);
    await tick();
    await internals.selectCommit(SHA_UNFETCHED);
    await tick();
    assertContains(
      "unfetched commit: stays open on reselect",
      previewHtml,
      "commit the fetch brought",
    );
    assertEqual("unfetched commit: a found commit asks for no fetch", asked.length, 2);

    // A request that fails when the commit is asked for again after the fetch is a load
    // failure. It says nothing about the commit, so the view must not say "not found".
    const SHA_REFUSED = "6".repeat(40);
    responses.set(`/api/git/commit/${SHA_REFUSED}`, notFound);
    await internals.selectCommit(SHA_REFUSED);
    await tick();
    responses.set(`/api/git/commit/${SHA_REFUSED}`, {
      httpStatus: 409,
      body: { error: "the server now serves another revision", code: "pin_changed" },
    });
    endFetch(fetched("succeeded"));
    await tick();
    await tick();
    assertContains(
      "refused commit: a failed re-ask is a load failure",
      previewHtml,
      "Could not load this commit.",
    );
    assertNotContains("refused commit: not called not found", previewHtml, "Commit not found");
    assertEqual("refused commit: state on the element", previewNode.dataset.state, "failed");

    // Inside the freshness window the controller asks for nothing: the view says the
    // commit is not in the mirror as fetched, offers Retry, and does not ask the commit
    // route a second time.
    const SHA_INSIDE = "7".repeat(40);
    insideWindow = true;
    responses.set(`/api/git/commit/${SHA_INSIDE}`, notFound);
    await internals.selectCommit(SHA_INSIDE);
    await tick();
    await tick();
    assertContains("inside the window: names the miss", previewHtml, "Commit not found");
    assertContains("inside the window: says what it knows", previewHtml, "as fetched");
    assertNotContains("inside the window: no fetch is claimed", previewHtml, "did not bring it");
    assertNotContains("inside the window: never said fetching", previewHtml, "Fetching");
    assertEqual("inside the window: the route is asked once", commitRequests(SHA_INSIDE), 1);
    assertTrue(
      "inside the window: offers Retry",
      previewNode.querySelector(".git-commit-missing-retry") !== null,
    );
    insideWindow = false;

    // A reader who goes elsewhere while the fetch runs keeps what they went to.
    responses.set(`/api/git/commit/${SHA_LEFT}`, notFound);
    await internals.selectCommit(SHA_LEFT);
    await tick();
    const fileClaim = sandbox.MetabrowserShell.claimPreview("file");
    sandbox.MetabrowserShell.renderPreviewHtml("<div>the reader moved on</div>", fileClaim);
    endFetch(fetched("succeeded"));
    await tick();
    await tick();
    assertContains("left commit: the newer preview stays", previewHtml, "the reader moved on");
    freshnessController = null;
  }

  // ── Relative age ───────────────────────────────────────────
  {
    const now = Date.now() / 1000;
    // One age vocabulary everywhere: the same abbreviations the file
    // tree uses, produced by the same primitive, so a commit's age and a
    // file's age are never spelled differently.
    assertEqual("age: sub-minute", internals.relativeAge(now - 10), "<1m");
    assertEqual("age: minutes", internals.relativeAge(now - 300), "5m");
    assertEqual("age: hours", internals.relativeAge(now - 7200), "2h");
    assertEqual("age: days", internals.relativeAge(now - 3 * 86400), "3d");
    assertEqual("age: carries its freshness class", internals.ageClass(now - 300), "age-min");
    // A missing or zero timestamp renders nothing rather than "56y ago".
    assertEqual("age: zero renders empty", internals.relativeAge(0), "");
  }

  if (failures.length > 0) {
    console.error(`FAILURES (${failures.length}):`);
    for (const failure of failures) {
      console.error(`  - ${failure}`);
    }
    process.exit(1);
  }
  console.log("OK git panel behavior");
  console.log(`commit loading session ${JSON.stringify(commitLoadingSession)}`);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
