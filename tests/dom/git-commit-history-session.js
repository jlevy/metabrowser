// Browserless session: Back and Forward across a page's file and commit entries.
//
// A commit owns the URL while it is shown, and a file opened in-page over it pushes an
// entry. Back onto the commit's entry changed the URL and left the file showing, because
// the navigation controller holds no target for a /commit/ address and leaves the pane to
// the Git panel, which only restored a commit when the page loaded (mb-y1p5). A short
// commit ID in an address, separately, said only that the commit could not be loaded.
//
// navigation.js, git-panel.js, and the modules it reads are production and load whole, and
// the preview pane's ownership is navigation.js's own lifecycle. The shell's
// applyNavigationTarget is lifted verbatim from app.js, which cannot load without a
// document. What it calls to open a file claims the pane and names the file, which is all
// this session asks of a file. `history` and `location` are this file's, and the routes
// answer what the transcripts in cli-api-git.tryscript.md pin.
//
// Each step prints the address, what the pane shows and who owns it, which nav panel is
// active, and the commit requests it made. Exits 1 on a failed invariant.
//
// `options` is what the server does next, and a step may change it: `behind` the entries
// behind the first address, `gateHeldDuringInit` a repository gate that answers only at
// `catchUp`, `notARepository` and `gateFailures` what it answers, and `commitRequestsFail`
// a commit route the network cannot reach.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");

const COMMIT_A = "a".repeat(40);
const COMMIT_B = "b".repeat(40);
const ABSENT = "0".repeat(40);
const SHORT = "aaaaaaa";

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

class StandIn {
  constructor(tag = "div") {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.connectedRoot = false;
    this.className = "";
    this.dataset = {};
    this.style = {};
    this.attributes = {};
    this.textContent = "";
    this.markup = "";
  }
  get innerHTML() {
    return this.markup;
  }
  set innerHTML(value) {
    this.replaceChildren();
    this.markup = String(value);
  }
  get isConnected() {
    return this.connectedRoot || Boolean(this.parentNode?.isConnected);
  }
  append(...children) {
    for (const child of children) {
      this.appendChild(child);
    }
  }
  appendChild(child) {
    child.remove();
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  replaceChildren(...children) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    this.markup = "";
    this.append(...children);
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  addEventListener() {}
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((node) => node !== this);
      this.parentNode = null;
    }
  }
  /** What the commit's stage needs: a stable child host with real connection ownership. */
  querySelector(selector) {
    if (selector !== ".git-commit-diff" || !this.markup.includes("git-commit-diff")) {
      return null;
    }
    let host = this.children.find((child) => child.className === "git-commit-diff");
    if (!host) {
      host = new StandIn();
      host.className = "git-commit-diff";
      this.appendChild(host);
    }
    return host;
  }
  querySelectorAll() {
    return [];
  }
}

/** One page: its history, its pane, and a server that answers the Git routes. */
async function createPage(start, options = {}) {
  const log = [];
  let repositoryReads = 0;
  const shown = { pane: "nothing", navPanel: "files" };
  const preview = new StandIn();
  preview.connectedRoot = true;
  let pendingStageCleanup = null;
  const held = new Map();
  const listeners = new Map();
  const entries = [...(options.behind ?? []), start];
  let index = entries.length - 1;
  const location = {};
  const moveTo = (url) => {
    const parsed = new URL(url, "http://127.0.0.1:8471");
    location.pathname = parsed.pathname;
    location.search = parsed.search;
    location.hash = parsed.hash;
  };
  moveTo(start);

  const history = {
    pushState(_state, _title, url) {
      entries.length = index + 1;
      entries.push(String(url));
      index += 1;
      moveTo(url);
    },
    replaceState(_state, _title, url) {
      entries[index] = String(url);
      moveTo(url);
    },
  };

  const commitDetail = (id) => ({
    is_repo: true,
    commit: {
      id,
      short_id: id.slice(0, 7),
      parent_ids: [],
      author: { name: "Author", email: "a@example.invalid" },
      authored_at: 1700000000,
      committed_at: 1700000000,
      subject: `commit ${id.slice(0, 7)}`,
    },
    stats: { files_changed: 0, additions: 0, deletions: 0 },
    files: [],
    files_truncated: false,
  });

  const answer = (body, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });

  async function fetchRoute(url) {
    const route = String(url);
    if (route.startsWith("/api/git/repo")) {
      repositoryReads += 1;
      await held.get(route);
      if (options.gateFailures > 0) {
        options.gateFailures -= 1;
        return answer({ error: "unavailable" }, 503);
      }
      return answer(
        options.notARepository
          ? { is_repo: false }
          : { is_repo: true, head: { revision: COMMIT_B, ref: "refs/heads/main" } },
      );
    }
    if (route.startsWith("/api/git/commit/")) {
      const id = route.slice("/api/git/commit/".length);
      log.push(`GET /api/git/commit/${id}`);
      await held.get(route);
      if (options.commitRequestsFail) {
        throw new TypeError("Failed to fetch");
      }
      if (!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(id)) {
        return answer(
          {
            error: "revision must be a full 40- or 64-character object id",
            code: "revision_not_full",
          },
          400,
        );
      }
      return id === ABSENT
        ? answer({ error: "unknown revision", code: "commit_not_found" }, 404)
        : answer(commitDetail(id));
    }
    if (route.startsWith("/api/git/log")) {
      return answer({
        is_repo: true,
        page: 0,
        commits: [commitDetail(COMMIT_B).commit, commitDetail(COMMIT_A).commit],
        cursor: null,
        has_more: false,
        page_cursor: "history:0",
        previous_cursor: null,
        scope: "all",
        scope_refs: [],
        scope_fingerprint: "session",
        graph_checkpoint: {
          version: 1,
          prior_swimlanes: [],
          color_index: -1,
          head_revision: COMMIT_B,
          scope_fingerprint: "session",
        },
      });
    }
    return route.startsWith("/api/git/refs")
      ? answer({ refs: [] })
      : answer({ is_repo: true, commit_count: 2 });
  }

  const sandbox = {
    AbortController,
    console: { error: console.error, warn() {} },
    CustomEvent: class {},
    Date,
    dispatchEvent: () => true,
    document: {
      addEventListener() {},
      createElement: (tag) => new StandIn(tag),
      createElementNS: (_ns, tag) => new StandIn(tag),
      getElementById: () => null,
      querySelector: () => null,
      querySelectorAll: () => [],
    },
    fetch: fetchRoute,
    history,
    HTMLElement: StandIn,
    location,
    Map,
    Math,
    METABROWSER_SETTINGS: {},
    Number,
    Promise,
    Set,
    URL,
    URLSearchParams,
    addEventListener(type, listener) {
      if (!listeners.has(type)) {
        listeners.set(type, new Set());
      }
      listeners.get(type).add(listener);
    },
    removeEventListener(type, listener) {
      listeners.get(type)?.delete(listener);
    },
    clearTimeout,
    setTimeout,
    metabrowser: {
      delegateOwnerAttribute: () => "",
      ensureAsset: async (name) => {
        assert(name === "sdk-views", "Git waits for the shared view helper bundle");
      },
      ensureKindAssets: async () => {},
      fetchPluginData: async () => ({}),
      getRegisteredView: () => ({
        render: async (host) => {
          assert(host.isConnected, "Git diff renders inside connected preview staging");
          return { cancelPending() {}, dispose() {} };
        },
      }),
      icons: { copy: "" },
      perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
      tooltip: { hide() {}, show() {} },
    },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  for (const file of [
    "formatters.js",
    "navigation.js",
    "git-graph.js",
    "git-history-window.js",
    "git-panel.js",
  ]) {
    const filename = path.join(staticDir, file);
    vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
  }
  const routes = sandbox.MetabrowserNavigationRoute;
  const previewPane = routes.createPreviewPaneLifecycle();
  let panel = null;

  const paint = (claim, text, node = new StandIn()) => {
    if (!previewPane.isCurrent(claim)) {
      return null;
    }
    preview.replaceChildren(node);
    shown.pane = text;
    return preview;
  };

  sandbox.MetabrowserShell = {
    rememberMainTabAddress() {},
    activateNavPanel(id) {
      shown.navPanel = id;
      sandbox.activeNavPanelId = id;
      if (id === "git") {
        panel?.onShow?.();
      }
    },
    beginPreviewNavigation: () => false,
    claimPreview(owner, selection) {
      pendingStageCleanup?.();
      if (owner !== "git") {
        sandbox.MetabrowserGitPanel.cancelPending();
      }
      return previewPane.claim(owner, selection);
    },
    endPreviewNavigation() {},
    isPreviewClaimCurrent: (claim) => previewPane.isCurrent(claim),
    registerNavPanel(next) {
      panel = next;
    },
    removeNavPanel(id) {
      if (shown.navPanel === id) {
        shown.navPanel = "files";
      }
      panel = null;
    },
    renderPreviewHtml: (html, claim) => paint(claim, html.replace(/<[^>]*>/g, "")),
    stagePreviewNode(node, claim) {
      if (!previewPane.isCurrent(claim)) {
        return null;
      }
      pendingStageCleanup?.();
      const stage = new StandIn();
      stage.className = "preview-file-stage";
      stage.setAttribute("aria-hidden", "true");
      stage.inert = true;
      stage.appendChild(node);
      preview.appendChild(stage);
      const cleanup = () => {
        stage.remove();
        if (pendingStageCleanup === cleanup) {
          pendingStageCleanup = null;
        }
      };
      pendingStageCleanup = cleanup;
      return cleanup;
    },
    renderPreviewNode(node, claim) {
      const revision = /data-revision="([^"]*)"/.exec(node.innerHTML)?.[1];
      return paint(
        claim,
        revision
          ? `commit ${revision.slice(0, 7)}`
          : node.children.map((child) => child.textContent).join(": "),
        node,
      );
    },
    sourceFreshness: async () => null,
  };
  // What app.js calls: opening a file claims the pane, then names the file a task later.
  sandbox.__file = {
    async open(filePath) {
      const claim = sandbox.MetabrowserShell.claimPreview("file", {
        folder: false,
        path: filePath,
      });
      await new Promise((resolve) => setImmediate(resolve));
      paint(claim, `file ${filePath}`);
      previewPane.settle(claim, "content");
      return { status: "opened" };
    },
    landing() {
      shown.pane = "landing";
    },
  };
  sandbox.__previewPane = previewPane;

  const applyTarget = appSource.match(
    /\nasync function applyNavigationTarget\(target, context\) \{[\s\S]*?\n\}/,
  );
  assert(applyTarget, "applyNavigationTarget was not found in app.js");
  vm.runInContext(
    `
    var PULL_ROUTE_PREFIX = "/pull/";
    var PULLS_ROUTE = "/pulls";
    function isPullAddress(pathname) { return pathname.startsWith(PULL_ROUTE_PREFIX) || pathname === PULLS_ROUTE; }
    var previewPane = __previewPane;
    var navigationController = null;
    var activeNavPanelId = "files";
    var mainTabIntent = 0;
    var treeKeyboard = null;
    var mainTabs = {
      takeFilesScroll: () => false,
      remember() {},
      fileLanding() {
        if (activeNavPanelId !== "files") {
          MetabrowserShell.claimPreview("none");
          MetabrowserShell.activateNavPanel("files");
        }
      },
    };
    function isGitHistoryLanding() { return false; }
    function beginViewCompositionLoad() { return null; }
    function addressedView() { return null; }
    function showPreviewTab() {}
    function deliverNavigationFragment() {}
    function showNavigationLanding() { __file.landing(); }
    function loadPullPageHost() { throw new Error("no pull-request page in this session"); }
    async function revealInTree() { return true; }
    function selectFile(path) { return __file.open(path); }
    ${applyTarget[0]}
    `,
    sandbox,
    { filename: "app.js (lifted)" },
  );
  const controller = routes.createController({ apply: sandbox.applyNavigationTarget });
  sandbox.navigationController = controller;
  routes.attachController(controller);
  await controller.start();
  let releaseGate = () => {};
  if (options.gateHeldDuringInit) {
    held.set(
      "/api/git/repo",
      new Promise((resolve) => {
        releaseGate = resolve;
      }),
    );
  }
  const initializing = sandbox.MetabrowserGitPanel.init();
  if (!options.gateHeldDuringInit) {
    await initializing;
  }

  const settle = async () => {
    for (let turn = 0; turn < 8; turn += 1) {
      await new Promise((resolve) => setImmediate(resolve));
    }
  };
  await settle();

  const traverse = (delta) => {
    index += delta;
    assert(index >= 0 && index < entries.length, "history has no such entry");
    moveTo(entries[index]);
    for (const listener of [...(listeners.get("popstate") ?? [])]) {
      listener({ type: "popstate" });
    }
  };

  return {
    entries,
    held,
    history,
    repositoryReads: () => repositoryReads,
    listeners,
    log,
    options,
    routes,
    settle,
    shown,
    /** Who holds the pane: every claim on it, even one that repaints the same text, moves this. */
    claim: () => previewPane.snapshot().claim,
    async back() {
      traverse(-1);
      await settle();
    },
    async forward() {
      traverse(1);
      await settle();
    },
    /** The repository gate answers at last, and `init` runs to its end. */
    async catchUp() {
      releaseGate();
      await initializing;
      await settle();
    },
    /** The reader clicking the Git tab, whose `onShow` asks the gate whether HEAD moved. */
    async showGitTab() {
      sandbox.MetabrowserShell.activateNavPanel("git");
      await settle();
    },
    /** `init` again, after a teardown. */
    async restart() {
      await sandbox.MetabrowserGitPanel.init();
      await settle();
    },
    /** An in-page open, the way the shell and plugins reach navigation. */
    async open(filePath) {
      await routes.navigation.open({ path: filePath });
      await settle();
    },
    /** The reader selecting a commit in the Git tab. */
    async selectRow(revision) {
      sandbox.MetabrowserShell.activateNavPanel("git");
      await settle();
      await sandbox.MetabrowserGitPanel._internals.selectCommit(revision);
      await settle();
    },
    read() {
      assert(!pendingStageCleanup, "settled history step releases preview staging");
      assert(
        preview.children.every((node) => node.className !== "preview-file-stage"),
        "settled history step has no hidden stage",
      );
      const requests = log.splice(0);
      return {
        url: `${location.pathname}${location.hash}`,
        pane: shown.pane,
        owner: previewPane.snapshot().owner,
        navPanel: shown.navPanel,
        requests,
      };
    },
  };
}

(async () => {
  const transcript = {};

  // A file, a commit selected over it, a file opened from there, and across them.
  {
    const page = await createPage("/view/README.md");
    const steps = {};
    steps["the page opens on a file"] = page.read();
    await page.selectRow(COMMIT_A);
    steps["selecting a commit replaces the entry"] = page.read();
    assert(page.entries.length === 1, "selecting a commit pushed an entry");
    await page.open("src/a.py");
    steps["opening a file pushes one"] = page.read();
    const beforeGitLanding = page.repositoryReads();
    await page.back();
    assert(
      page.repositoryReads() === beforeGitLanding + 1,
      "an addressed Git activation shares its repo-info read",
    );
    steps["Back shows the commit"] = page.read();
    assert(steps["Back shows the commit"].pane === `commit ${COMMIT_A.slice(0, 7)}`, "Back");
    assert(steps["Back shows the commit"].owner === "git", "Back left the pane with the file");
    await page.forward();
    steps["Forward shows the file"] = page.read();
    assert(steps["Forward shows the file"].pane === "file src/a.py", "Forward");
    assert(steps["Forward shows the file"].owner === "file", "Forward left the pane with Git");
    await page.back();
    steps["Back shows the commit again"] = page.read();
    assert(steps["Back shows the commit again"].pane === `commit ${COMMIT_A.slice(0, 7)}`, "Back");
    await page.selectRow(COMMIT_B);
    steps["another commit replaces the commit's entry"] = page.read();
    await page.forward();
    steps["Forward from it still shows the file"] = page.read();
    assert(steps["Forward from it still shows the file"].pane === "file src/a.py", "Forward");
    await page.back();
    steps["Back lands on the commit now in that entry"] = page.read();
    assert(
      steps["Back lands on the commit now in that entry"].pane === `commit ${COMMIT_B.slice(0, 7)}`,
      "Back landed on the replaced commit",
    );
    transcript["from a file, through commits"] = steps;
  }

  // A page opened on a commit's address, and a file's inner address on it.
  {
    const page = await createPage(`/commit/${COMMIT_A}/src/a.py`);
    const steps = {};
    steps["the page opens on the commit"] = page.read();
    assert(steps["the page opens on the commit"].owner === "git", "the commit did not open");
    await page.open("docs/");
    steps["opening a folder pushes an entry"] = page.read();
    await page.back();
    steps["Back shows the commit, not yet its file"] = page.read();
    assert(
      steps["Back shows the commit, not yet its file"].pane === `commit ${COMMIT_A.slice(0, 7)}`,
      "Back from a folder",
    );
    transcript["from a commit's address"] = steps;
  }

  // A step between entries of the commit shown does not load it again.
  {
    const page = await createPage(`/commit/${COMMIT_A}`);
    page.read();
    page.history.pushState(null, "", `/commit/${COMMIT_A}#diff-1`);
    const claim = page.claim();
    await page.back();
    const fragment = page.read();
    assert(fragment.requests.length === 0, "a fragment step asked for the commit again");
    // The detail is cached, so only the claim tells a step that changes nothing from one that
    // selects the commit again, which renders the diff anew and resets the pane.
    assert(page.claim() === claim, "a fragment step selected the commit again");
    assert(fragment.pane === `commit ${COMMIT_A.slice(0, 7)}`, "a fragment step lost the commit");
    transcript["a fragment on the commit shown"] = fragment;
  }

  // Stepping on before the commit has answered, while the panel catches up and while the
  // commit itself loads: the later entry keeps the pane and nothing paints over it.
  for (const [step, held] of [
    ["while the panel catches up", "/api/git/repo"],
    ["while the commit loads", `/api/git/commit/${COMMIT_A}`],
  ]) {
    const page = await createPage("/view/README.md");
    await page.selectRow(COMMIT_B);
    page.history.replaceState(null, "", `/commit/${COMMIT_A}`);
    await page.open("src/a.py");
    page.read();
    let release = () => {};
    page.held.set(held, new Promise((resolve) => (release = resolve)));
    await page.back();
    await page.forward();
    release();
    await page.settle();
    const after = page.read();
    assert(after.pane === "file src/a.py", `${step}: a stale commit took the pane`);
    assert(after.owner === "file", `${step}: Git kept the pane`);
    transcript[`stepping on ${step}`] = after;
  }

  // Back onto a commit the repository lacks, and a short ID, say which they are.
  {
    const page = await createPage(`/commit/${ABSENT}`);
    const absent = page.read();
    assert(absent.pane.startsWith("Commit not found"), `an absent commit: ${absent.pane}`);
    const short = await createPage(`/commit/${SHORT}`);
    const opened = short.read();
    assert(opened.pane.startsWith("Full commit ID needed"), `a short ID: ${opened.pane}`);
    assert(opened.pane.includes(SHORT), "a short ID's state does not name the address");
    await short.open("src/a.py");
    short.read();
    await short.back();
    const landed = short.read();
    assert(landed.pane === opened.pane, `Back onto a short ID: ${landed.pane}`);
    // Whether an ID is full is a fact about its text, which a request lost on the way to being
    // refused again does not change: the address still cannot work, and the sentence says why.
    short.options.commitRequestsFail = true;
    await short.open("src/a.py");
    short.read();
    await short.back();
    const unreachable = short.read();
    assert(unreachable.pane === opened.pane, `a short ID, unreachable: ${unreachable.pane}`);
    short.options.commitRequestsFail = false;
    // The route's grammar admits capitals and its full-ID rule does not, so an ID of the right
    // length is refused too, and the sentence has to say why.
    const upper = await createPage(`/commit/${COMMIT_A.toUpperCase()}`);
    const uppercase = upper.read();
    assert(uppercase.pane.startsWith("Full commit ID needed"), `capitals: ${uppercase.pane}`);
    assert(uppercase.pane.includes("lowercase"), `capitals, not said: ${uppercase.pane}`);
    transcript["an address the repository cannot answer"] = {
      absent,
      opened,
      landed,
      unreachable,
      uppercase,
    };
  }

  // Stepping before the panel is ready. The panel adds its listener only when the repository
  // gate answers, so what it restores is where the reader is by then, not where the page opened.
  {
    const page = await createPage("/view/src/a.py", {
      behind: [`/commit/${COMMIT_A}`],
      gateHeldDuringInit: true,
    });
    page.read();
    await page.back();
    const waiting = page.read();
    await page.catchUp();
    const ready = page.read();
    assert(ready.pane === `commit ${COMMIT_A.slice(0, 7)}`, `an early Back: ${ready.pane}`);
    assert(ready.owner === "git", "an early Back left the pane with the file");
    assert(ready.navPanel === "git", "an early Back did not show the Git panel");

    const opened = await createPage(`/commit/${COMMIT_A}`, { gateHeldDuringInit: true });
    await opened.open("src/a.py");
    await opened.catchUp();
    const moved = opened.read();
    assert(moved.pane === "file src/a.py", `the address the page opened on: ${moved.pane}`);
    assert(moved.owner === "file", "the address the page opened on took the pane");
    transcript["stepping before the panel is ready"] = { waiting, ready, moved };
  }

  // A landing the panel does not outlive paints nothing: there is no panel behind the commit,
  // and nothing would handle the next one. A gate that fails once tears the panel down as one
  // that says the root stopped being a repository does, which mb-5gs6 tracks.
  for (const [step, gate] of [
    ["the root stopped being a repository", { notARepository: true }],
    ["the repository gate failed once", { gateFailures: 1 }],
  ]) {
    const page = await createPage("/view/README.md");
    await page.selectRow(COMMIT_A);
    await page.open("src/a.py");
    page.read();
    Object.assign(page.options, gate);
    await page.back();
    const after = page.read();
    assert(after.pane === "file src/a.py", `${step}: ${after.pane}`);
    assert(after.owner === "file", `${step}: a commit took the pane with no panel behind it`);
    assert(after.navPanel === "files", `${step}: ${after.navPanel}`);
    assert(page.listeners.get("popstate")?.size === 1, `${step}: the panel still listens`);
    transcript[`a landing when ${step}`] = after;
  }

  // A panel that went away and came back starts over: neither a selection nor a refusal from
  // its previous life answers for the pane now.
  {
    const page = await createPage(`/commit/${COMMIT_A}`);
    page.options.notARepository = true;
    await page.showGitTab();
    page.options.notARepository = false;
    page.read();
    await page.restart();
    const selection = page.read();
    assert(selection.navPanel === "git", "an old selection stood in for the one restored");
    assert(selection.requests.length === 1, "the restart did not load the commit it restored");
    assert(selection.pane === `commit ${COMMIT_A.slice(0, 7)}`, `restart: ${selection.pane}`);

    const short = await createPage(`/commit/${SHORT}`);
    short.options.notARepository = true;
    await short.showGitTab();
    short.options.notARepository = false;
    short.options.commitRequestsFail = true;
    short.read();
    await short.restart();
    const refusal = short.read();
    assert(
      refusal.pane === "Could not load this commit.",
      `an old refusal stood in for this failure: ${refusal.pane}`,
    );
    transcript["a panel that came back starts over"] = { selection, refusal };
  }

  // A folder that is not a repository has no panel, and nothing listens for a landing.
  {
    const page = await createPage("/view/README.md", { notARepository: true });
    await page.open("src/a.py");
    await page.back();
    const shown = page.read();
    assert(shown.pane === "file README.md", `a plain folder's Back: ${shown.pane}`);
    assert(shown.navPanel === "files", "a plain folder's Back moved the nav panel");
    assert(page.listeners.get("popstate")?.size === 1, "a plain folder holds a second listener");
    transcript["a folder that is not a repository"] = shown;
  }

  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
