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
  focus() {
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
sandbox.history = {
  replaceState: (_state, _title, url) => {
    replacedRoutes.push(String(url));
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
      prior_swimlanes: page > 0 ? [{ id: commits[0].id, color: "var(--git-ref-local)" }] : [],
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

    for (const modifier of ["altKey", "ctrlKey", "metaKey", "shiftKey"]) {
      for (const letter of ["j", "k"]) {
        const key = modifier === "shiftKey" ? letter.toUpperCase() : letter;
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
    // Let the final focus-following selection release its single active
    // preparation slot before the next independent preparation case.
    await new Promise((resolve) => setTimeout(resolve, 0));
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

    const cachedMissing = "9".repeat(40);
    let askedForFreshness = false;
    freshnessController = {
      fetchMissing() {
        askedForFreshness = true;
        throw new Error("tab restoration must not start source refresh");
      },
    };
    responses.set(`/api/git/commit/${cachedMissing}`, notFound);
    const originalLocation = sandbox.location;
    const originalParse = sandbox.MetabrowserNavigationRoute.parseCommit;
    sandbox.location = { pathname: `/commit/${cachedMissing}` };
    sandbox.MetabrowserNavigationRoute.parseCommit = () => ({ revision: cachedMissing });
    sandbox.history.state = { cachedCommit: true };
    responses.set("/api/git/repo", {
      is_repo: true,
      root: "",
      head: { ref: "refs/heads/main", revision: SHA_A, detached: false, unborn: false },
    });
    await panel.init();
    internals.teardown();
    sandbox.location = originalLocation;
    sandbox.MetabrowserNavigationRoute.parseCommit = originalParse;
    delete sandbox.history.state;
    assertEqual("missing cached selection: no refresh", askedForFreshness, false);
    assertContains(
      "missing cached selection: names the local miss",
      previewHtml,
      "not available in the local repository",
    );

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
