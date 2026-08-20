// Behavioral checks for the Git nav panel.
//
// The panel is exercised through a fake DOM and a stubbed `fetch`, so
// these assertions cover the parts that are easy to get wrong and
// invisible in a screenshot: which rows are navigable, what the hover
// card says, whether a truncated file list admits it, and whether a
// stale in-flight request can overwrite a newer selection.

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
  }

  set className(value) {
    this.classNames = new Set(String(value).split(/\s+/).filter(Boolean));
  }
  get className() {
    return Array.from(this.classNames).join(" ");
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
  appendChild(child) {
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
  }
  createElement(tagName) {
    return new FakeElement(tagName, this);
  }
  createElementNS(_ns, tagName) {
    return new FakeSvgElement(tagName, this);
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
};

// Shell bridge stub. The panel only uses these three.
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
    return preview;
  },
  activateNavPanel: () => {},
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
for (const file of ["git_graph.js", "git_panel.js"]) {
  const source = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", file), "utf-8");
  vm.runInContext(source, sandbox, { filename: file });
}

const panel = sandbox.MetabrowserGitPanel;
const internals = panel._internals;

const SHA_A = "a".repeat(40);
const SHA_B = "b".repeat(40);
const SHA_C = "c".repeat(40);
const SHA_D = "d".repeat(40);

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

  // ── Hover card ─────────────────────────────────────────────
  {
    const text = internals.hoverText({
      commit: commit(SHA_A, [], "the subject"),
      body: "the body",
      stats: { files_changed: 3, additions: 10, deletions: 4 },
    });
    assertContains("hover: subject", text, "the subject");
    assertContains("hover: body", text, "the body");
    assertContains("hover: file count", text, "3 file(s) changed");
    assertContains("hover: additions", text, "+10");
    assertContains("hover: deletions", text, "−4");
  }
  internals.renderCommitDetail({
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
  assertContains("detail: subject", previewHtml, "a commit");
  assertContains("detail: short sha", previewHtml, SHA_A.slice(0, 7));
  assertContains("detail: body", previewHtml, "explanatory body");
  assertContains("detail: ref badge", previewHtml, "main");
  // The commit's files are presented by the diff view mounted below, so
  // the panel keeps only what that view cannot show: a host for it, the
  // files outside the served root, and any bound on the comparison.
  assertContains("detail: mounts the diff host", previewHtml, "git-commit-diff");
  assertNotContains("detail: no duplicate file list", previewHtml, "2 files changed");
  assertNotContains("detail: no truncation note", previewHtml, "the diff below is bounded");
  internals.renderCommitDetail({
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
  internals.renderCommitDetail({
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

    internals.appendPage([commit(SHA_C, [], "root")], null);
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
    assertTrue("paging: gutter width is set", afterSecond.gutterWidth > 0);
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
    // Keyboard reachable — the rows are the panel's primary control.
    assertEqual("rows: focusable", rows[0].getAttribute("tabindex"), "0");
    assertEqual("rows: exposed as buttons", rows[0].getAttribute("role"), "button");
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
    rows[0].dispatch("click");
    await new Promise((resolve) => setTimeout(resolve, 0));
    assertContains("selection: renders the clicked commit", previewHtml, "first");
    assertTrue("selection: row is marked", rows[0].classList.contains("selected"));

    // Two selections in flight: the later one must win regardless of
    // which response lands first.
    const before = fetchCount;
    rows[1].dispatch("click");
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

  // ── Changed files navigate through the shell ───────────────
  {
    openedPaths.length = 0;
    // renderCommitDetail wires listeners on the element the shell
    // returns, so drive it through the same path the panel uses.
    let capturedPreview = null;
    sandbox.MetabrowserShell.renderPreviewHtml = (html) => {
      previewHtml = html;
      const preview = new FakeElement("div", document);
      const row = new FakeElement("div", document);
      row.classList.add("git-commit-file");
      row.dataset.path = "one.js";
      preview.appendChild(row);
      capturedPreview = preview;
      return preview;
    };
    internals.renderCommitDetail({
      is_repo: true,
      commit: commit(SHA_A, [], "nav"),
      body: "",
      stats: { files_changed: 1, additions: 1, deletions: 0 },
      files: [{ path: "one.js", status: "modified", additions: 1, deletions: 0 }],
      files_truncated: false,
    });
    capturedPreview.querySelectorAll(".git-commit-file[data-path]")[0].dispatch("click");
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
    assertEqual("age: sub-minute", internals.relativeAge(now - 10), "just now");
    assertEqual("age: minutes", internals.relativeAge(now - 300), "5m ago");
    assertEqual("age: hours", internals.relativeAge(now - 7200), "2h ago");
    assertEqual("age: days", internals.relativeAge(now - 3 * 86400), "3d ago");
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
