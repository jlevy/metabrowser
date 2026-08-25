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
    this.style = {};
    this._text = "";
    this._html = "";
    this._hovered = false;
    this.scrollCalls = [];
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
    this.children = [];
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
  GIT_HISTORY_MAX_ROWS: 3,
  GIT_HOVER_DEBOUNCE_MS: 0,
  GIT_DETAIL_CACHE_SIZE: 3,
};

const openedPaths = [];
sandbox.dispatchEvent = () => {};
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
let previewClaim = 0;
const removedPanels = [];
let registeredPanel = null;
sandbox.MetabrowserShell = {
  claimPreview: () => {
    previewClaim += 1;
    return previewClaim;
  },
  isPreviewClaimCurrent: (claim) => claim === previewClaim,
  beginPreviewNavigation: (claim) => {
    if (claim !== previewClaim) {
      return false;
    }
    const preview = document.getElementById("preview-pane");
    if (!preview?.firstElementChild || preview.firstElementChild.classList.contains("loading")) {
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
    const preview = new FakeElement("div", document);
    preview.innerHTML = html;
    if (html.includes("git-commit-diff")) {
      const diffHost = new FakeElement("div", document);
      diffHost.className = "git-commit-diff";
      preview.appendChild(diffHost);
    }
    return preview;
  },
  renderPreviewNode: (node, claim) => {
    if (claim !== undefined && claim !== previewClaim) {
      return null;
    }
    previewHtml = node.innerHTML;
    return node;
  },
  activateNavPanel: () => {},
};

// A fresh directory shell has configured plugin descriptors but has not
// evaluated the diff plugin yet. The view appears only after its kind
// assets load, matching the on-demand browser lifecycle.
let diffAssetsLoaded = false;
const ensuredKinds = [];
const renderedDiffRevisions = [];
const renderedDiffContexts = [];
const canceledDiffRevisions = [];
const disposedDiffRevisions = [];
const comparisonFetches = [];
const shownTooltips = [];
let tooltipHideCount = 0;
let comparisonResponder = async (revision) => ({ comparison_id: revision });
sandbox.metabrowser = {
  icons: { copy: '<svg data-icon="copy"></svg>' },
  tooltip: {
    show: (html, anchor) => shownTooltips.push({ html, anchor }),
    hide: () => {
      tooltipHideCount += 1;
    },
  },
  ensureKindAssets: async (kind) => {
    ensuredKinds.push(kind);
    diffAssetsLoaded = true;
  },
  getRegisteredView: (kind, view) => {
    if (!diffAssetsLoaded || kind !== "diff" || view !== "diff") {
      return null;
    }
    return {
      render: async (_host, context) => {
        renderedDiffRevisions.push(context.revision);
        renderedDiffContexts.push(context);
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
    measure: (_label, fn) => fn(),
    measureAsync: (_label, fn) => fn(),
  },
};

// Stubbed network. Each entry is url-prefix -> payload.
const responses = new Map();
let fetchCount = 0;
sandbox.fetch = async (url) => {
  fetchCount += 1;
  for (const [prefix, payload] of responses) {
    if (url.startsWith(prefix)) {
      const value = typeof payload === "function" ? await payload(url) : payload;
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
for (const file of ["formatters.js", "git-graph.js", "git-panel.js"]) {
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
      ]),
      body: "the long body must stay out of a bounded tooltip",
      stats: { files_changed: 3, additions: 10, deletions: 4 },
      files: [],
      files_truncated: false,
    };
    const html = internals.renderCommitTooltip(detail);
    assertContains("tooltip: compact summary root", html, "git-commit-summary-compact");
    assertContains("tooltip: escaped subject", html, "the &lt;subject&gt;");
    assertContains("tooltip: author", html, "Author");
    assertContains("tooltip: short revision", html, SHA_A.slice(0, 7));
    assertContains("tooltip: copy identity glyph", html, 'data-icon="copy"');
    assertContains("tooltip: file count", html, "3 changed files");
    assertContains("tooltip: additions", html, "+10");
    assertContains("tooltip: deletions", html, "−4");
    assertNotContains("tooltip: omits long body", html, "long body");
    assertNotContains("tooltip: omits refs", html, "main");
    assertNotContains("tooltip: has no interactive copy button", html, "<button");
    assertNotContains("tooltip: has no copy behavior", html, "data-mb-copy");

    const unknown = internals.renderCommitTooltip({
      ...detail,
      stats: {},
      files_truncated: true,
    });
    assertContains("tooltip: unknown file count stays unknown", unknown, "? changed files");
    assertContains("tooltip: unknown additions stay unknown", unknown, "+?");
    assertContains("tooltip: unknown deletions stay unknown", unknown, "−?");
  }
  internals.setStateForTests({ ...internals.emptyState(), selectedId: SHA_A });
  await internals.renderCommitDetail({
    is_repo: true,
    commit: commit(SHA_A, [SHA_B], "a commit", [
      { id: "refs/heads/main", name: "main", kind: "branch", is_head: true },
    ]),
    body: "explanatory body",
    stats: { files_changed: 2, additions: 5, deletions: 1 },
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
    "detail: revision copy has an accessible name",
    previewHtml,
    'aria-label="Copy revision"',
  );
  assertContains("detail: revision uses the shared copy icon", previewHtml, 'data-icon="copy"');
  assertContains("detail: body", previewHtml, "explanatory body");
  assertContains("detail: ref badge", previewHtml, "main");
  assertContains(
    "detail: summary has one component root",
    previewHtml,
    '<section class="git-commit-summary"',
  );
  assertContains(
    "detail: summary gives change stats their own child",
    previewHtml,
    "git-commit-change-stats",
  );
  assertContains("detail: summary counts files", previewHtml, "2 changed files");
  assertContains("detail: summary counts additions", previewHtml, "+5");
  assertContains("detail: summary counts deletions", previewHtml, "−1");
  const summaryStart = previewHtml.indexOf('<section class="git-commit-summary"');
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
    internals.appendPage(
      [commit(SHA_A, [SHA_B], "tip"), commit(SHA_B, [SHA_C], "middle")],
      "cursor-1",
    );
    const afterFirst = internals.stateForTests();
    assertEqual("paging: first page rows", afterFirst.rows.length, 2);
    assertEqual("paging: cursor stored", afterFirst.cursor, "cursor-1");
    const trailing = afterFirst.trailingSwimlanes.map((lane) => lane.id);
    assertEqual("paging: trailing lane leads to the next commit", trailing, [SHA_C]);

    const secondPageRows = internals.appendPage([commit(SHA_C, [], "root")], null);
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
    assertEqual("paging: a page reports only its own rows", secondPageRows.length, 1);
    assertEqual(
      "paging: a rejected page reports no rows",
      internals.appendPage([commit(SHA_D, [])], null).length,
      0,
    );
  }

  // ── History retention is explicitly bounded ───────────────
  {
    internals.setStateForTests(internals.emptyState());
    internals.appendPage(
      [commit(SHA_A, [SHA_B], "one"), commit(SHA_B, [SHA_C], "two")],
      "cursor-1",
    );
    internals.appendPage([commit(SHA_C, [SHA_D], "three"), commit(SHA_D, [], "four")], "cursor-2");
    const bounded = internals.stateForTests();
    assertEqual("bounded: row cap", bounded.rows.length, 3);
    assertEqual("bounded: commit cap", bounded.commits.length, 3);
    assertEqual("bounded: pagination stops", bounded.cursor, null);
    assertTrue("bounded: truncation is explicit", bounded.capped);

    const container =
      document.getElementById("tab-git") ??
      document.register("tab-git", document.createElement("div"));
    internals.renderPanel();
    assertEqual(
      "bounded: only capped rows mount",
      container.querySelectorAll(".git-graph-row").length,
      3,
    );
    assertContains("bounded: cap is disclosed", container.textContent, "newest 3 commits");
  }

  // ── Panel states ───────────────────────────────────────────
  {
    const container = document.getElementById("tab-git");

    internals.setStateForTests({ ...internals.emptyState(), loading: true });
    internals.renderPanel();
    assertContains("panel: loading state", container.innerHTML, "spinner");

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
    internals.appendPage(
      [
        commit(SHA_A, [SHA_B], "tip commit", [
          { id: "refs/heads/main", name: "main", kind: "branch", is_head: true },
        ]),
        commit(SHA_B, [], "root commit"),
      ],
      null,
    );
    internals.renderPanel();

    const rows = container.querySelectorAll(".git-graph-row");
    assertEqual("rows: one per commit", rows.length, 2);
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
    rows[0]._hovered = true;
    rows[0].dispatch("mouseenter");
    await new Promise((resolve) => setTimeout(resolve, 0));
    assertEqual("tooltip lifecycle: hover shows one anchored summary", shownTooltips.length, 1);
    assertTrue("tooltip lifecycle: row is the anchor", shownTooltips[0].anchor === rows[0]);
    assertContains(
      "tooltip lifecycle: rich summary reaches shared tooltip",
      shownTooltips[0].html,
      "git-commit-summary-compact",
    );

    rows[0].focus();
    const hidesWhileFocused = tooltipHideCount;
    rows[0]._hovered = false;
    rows[0].dispatch("mouseleave");
    assertEqual(
      "tooltip lifecycle: pointer leave keeps a focused tooltip",
      tooltipHideCount,
      hidesWhileFocused,
    );
    rows[1].focus();
    assertTrue(
      "tooltip lifecycle: blur hides an unhovered tooltip",
      tooltipHideCount > hidesBefore,
    );
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
    internals.appendPage(
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
    // Let the final focus-following selection release its single active
    // preparation slot before the next independent preparation case.
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  // ── Preparation overlaps and reuses pointer intent ─────────
  {
    internals.setStateForTests(internals.emptyState());
    responses.clear();
    const container = document.getElementById("tab-git");
    internals.appendPage(
      [commit(SHA_E, [], "prepared first"), commit(SHA_B, [], "prepared second")],
      null,
    );
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
    await new Promise((resolve) => setTimeout(resolve, 0));
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

    const slotBefore = comparisonFetches.length;
    comparisonResponder = async (revision) => ({ comparison_id: revision });
    rows[0].dispatch("mouseenter");
    const firstSignal = comparisonFetches[slotBefore].signal;
    rows[1].dispatch("mouseenter");
    assertTrue("prepare: newer pointer intent aborts the old slot", firstSignal.aborted);
    assertEqual(
      "prepare: one replacement request serves the newer intent",
      comparisonFetches.length,
      slotBefore + 2,
    );
    rows[1].dispatch("mouseleave");
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
  responses.clear();
  registeredPanel = null;
  // /api/git/repo answers is_repo:false, so nothing is registered, but
  // a later init can retry after that transient/negative result.
  responses.set("/api/git/repo", { is_repo: false, reason: "not_a_repo" });
  await panel.init();
  assertEqual("gate: no tab outside a repository", registeredPanel, null);

  responses.set("/api/git/repo", {
    is_repo: true,
    root: "",
    head: { ref: "refs/heads/main", revision: SHA_A, detached: false, unborn: false },
  });
  responses.set("/api/git/refs", { is_repo: true, refs: [] });
  await panel.init();
  assertTrue("gate: init retries and registers", registeredPanel !== null);

  internals.setStateForTests(internals.emptyState());
  responses.delete("/api/git/log");
  registeredPanel.onShow();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertTrue("show: initial history failure is retained", internals.stateForTests().failed);

  responses.set("/api/git/log", {
    is_repo: true,
    commits: [commit(SHA_A, [], "retry succeeded")],
    cursor: null,
    has_more: false,
  });
  registeredPanel.onShow();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assertEqual("show: reopening retries history", internals.stateForTests().rows.length, 1);
  assertTrue("show: successful retry clears failure", !internals.stateForTests().failed);

  // A rejected cursor invalidates append-only lane continuity. Reset to
  // the refresh state rather than retrying the same cursor on every show.
  internals.setStateForTests({
    ...internals.stateForTests(),
    cursor: "bad-cursor",
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

  responses.set("/api/git/log", {
    is_repo: true,
    commits: [commit(SHA_B, [], "cursor recovery succeeded")],
    cursor: null,
    has_more: false,
  });
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
  const primedCache = fetchCount;
  await internals.selectCommit(SHA_B);
  assertEqual("head: the detail cache serves a repeat select", fetchCount, primedCache);

  responses.set("/api/git/repo", {
    is_repo: true,
    root: "",
    head: { ref: "refs/heads/other", revision: SHA_C, detached: false, unborn: false },
  });
  responses.set("/api/git/log", {
    is_repo: true,
    commits: [commit(SHA_C, [], "after checkout"), commit(SHA_B, [], "older")],
    cursor: null,
    has_more: false,
  });
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
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
