// Browserless session: the Shift key reveal and the shell's keymap, on the production code.
//
// The shortcut registry, the reveal (static/key-reveal.js), the shell keymap
// (static/shell-keymap.js), Help and its strip with the real overlay layer, the file
// tree's keys, Quick Search, the main tabs (static/main-tabs.js), and the Pulls tab's keys
// (static/pulls-nav.js) load whole, with injected time, pointer, and visibility. What
// app.js would do is played here: it renders each file's header and view tab bar from
// the server's answer, stages it in an inert layer, and commits it, calling the keymap
// where app.js does; and it stands in for the activation paths (selectPreviewTab,
// openFilterMenu, the selector's handle, copyFromControl, the Up navigation), recording
// what each was asked. A stand-in commit view lends its Copy revision through the bridge
// git-panel.js uses, and a stand-in pull request page offers hasStack() and moveStack().
//
// The server's side is tests/fixtures/key-reveal-responses.json: the `/api/file`,
// `/api/git/repo`, and `/api/source/status` answers of the in-process application, which
// tests/test_key_reveal_session.py records and holds the shell keys printed here to.
//
// Each step records the reveal's state, the live keymap as key, command, and target, the
// badges mounted, the strip's surface and items, and Help's groups.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { FakeDocument, FakeElement, element, keyEvent } = require("./key-reveal-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const recording = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/key-reveal-responses.json"), "utf8"),
);

// In load order, as the shell's startup scripts and its `shell-tools` bundle run them.
const MODULES = [
  "navigation.js",
  "pull-route.js",
  "main-tabs.js",
  "keyboard-shortcuts.js",
  "overlay-layer.js",
  "keyboard-help.js",
  "key-reveal.js",
  "shell-keymap.js",
  "tree-keyboard-navigation.js",
  "search-palette.js",
  "pulls-nav.js",
];
const SOURCES = new Map(
  MODULES.map((name) => [name, fs.readFileSync(path.join(staticDir, name), "utf8")]),
);
const TAB_LABELS = { files: "Files", git: "Commits", pulls: "Pulls" };
const HOLD_MS = 200;
const REVISION = "0123456789abcdef0123456789abcdef01234567";

/** Let every promise chain that needs no further input run. */
async function settle() {
  for (let turn = 0; turn < 10; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** Injected time: timers fire only when a step says that much time passed. */
function createClock() {
  let now = 0;
  const timers = new Set();
  return {
    schedule(callback, delayMs) {
      const timer = { at: now + delayMs, callback };
      timers.add(timer);
      return timer;
    },
    cancel(timer) {
      timers.delete(timer);
    },
    advance(ms) {
      now += ms;
      for (const timer of [...timers].sort((left, right) => left.at - right.at)) {
        if (timer.at <= now && timers.has(timer)) {
          timers.delete(timer);
          timer.callback();
        }
      }
    },
  };
}

/** A control's label as a reader sees it, without a badge mounted inside it. */
function labelOf(node) {
  return node.childNodes
    .filter((child) => !(child instanceof FakeElement && child.classList.contains("kbd-badge")))
    .map((child) => child.textContent)
    .join("")
    .trim();
}

function describe(target) {
  if (!target) {
    return null;
  }
  if (target.classList.contains("tab-btn")) {
    return `${labelOf(target)} tab`;
  }
  if (target.classList.contains("folder-crumb")) {
    return `${labelOf(target)} crumb`;
  }
  return target.getAttribute("aria-label") || labelOf(target);
}

/**
 * One page of the shell: its DOM, the production modules in a fresh global, and the
 * stand-ins for what app.js does around them.
 */
function createPage({ tabs = ["files"], repository = false, pin = null, address = "/view/" }) {
  const document = new FakeDocument();
  const clock = createClock();
  const did = [];
  const location = { hash: "", pathname: address, search: "" };
  const history = {
    state: null,
    pushState(state, _title, href) {
      this.state = state;
      const url = new URL(href, "http://metabrowser.test");
      location.pathname = url.pathname;
      location.search = url.search;
      did.push(`address ${href}`);
    },
    replaceState(state) {
      this.state = state;
    },
  };
  const windowListeners = [];
  const browserWindow = {
    addEventListener: (type, listener) => windowListeners.push({ type, listener }),
    removeEventListener(type, listener) {
      const at = windowListeners.findIndex(
        (entry) => entry.type === type && entry.listener === listener,
      );
      if (at >= 0) {
        windowListeners.splice(at, 1);
      }
    },
    fire(type) {
      for (const entry of windowListeners.filter((candidate) => candidate.type === type)) {
        entry.listener({ type });
      }
    },
  };
  let kbdCreated = 0;
  const createElement = document.createElement.bind(document);
  document.createElement = (tagName) => {
    if (tagName === "kbd") {
      kbdCreated += 1;
    }
    return createElement(tagName);
  };

  const context = {
    AbortController,
    Array,
    Element: FakeElement,
    Error,
    HTMLElement: FakeElement,
    JSON,
    Map,
    Math,
    Number,
    Object,
    Promise,
    Set,
    String,
    Symbol,
    TypeError,
    URL,
    URLSearchParams,
    addEventListener: browserWindow.addEventListener,
    clearTimeout: (timer) => clock.cancel(timer),
    console: { error() {}, warn() {}, log() {} },
    document,
    history,
    location,
    metabrowser: {
      decorateExternalLink() {},
      ensureAsset: () => new Promise(() => {}),
    },
    queueMicrotask,
    removeEventListener: browserWindow.removeEventListener,
    setTimeout: (callback, delayMs) => clock.schedule(callback, delayMs),
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  for (const name of MODULES) {
    vm.runInContext(SOURCES.get(name), context, { filename: path.join(staticDir, name) });
  }

  // ── The shell's DOM ───────────────────────────────────────────
  const navBar = element(document, "div", { class: "nav-tab-bar", role: "tablist" });
  for (const tab of tabs) {
    navBar.append(
      element(
        document,
        "button",
        {
          "aria-selected": tab === "files" ? "true" : "false",
          class: tab === "files" ? "tab-btn active" : "tab-btn",
          "data-tab": tab,
          role: "tab",
          type: "button",
        },
        TAB_LABELS[tab],
      ),
    );
  }
  const filterBar = element(document, "div", { id: "nav-filter-bar" });
  const filesPanel = element(document, "div", { id: "tab-files", "data-tab-content": "files" });
  const rows = ["README.md", "data.json", "docs"].map((name, index) =>
    element(
      document,
      "div",
      {
        class: `tree-item tree-${name === "docs" ? "folder" : "file"}`,
        "data-path": name,
        "data-tree-id": `${name === "docs" ? "folder" : "file"}:${name}`,
        "data-tree-kind": name === "docs" ? "folder" : "file",
        role: "treeitem",
        tabindex: index === 0 ? "0" : "-1",
      },
      name,
    ),
  );
  filesPanel.append(element(document, "div", { role: "tree" }, ...rows));
  const treeContent = element(document, "div", { id: "tree-content" }, filesPanel);
  if (tabs.includes("pulls")) {
    treeContent.append(element(document, "div", { id: "tab-pulls", "data-tab-content": "pulls" }));
    treeContent.querySelector("#tab-pulls").style.display = "none";
  }
  const hints = element(document, "div", { class: "nav-shortcut-hints", id: "nav-shortcut-hints" });
  const navPane = element(
    document,
    "nav",
    { class: "tree-pane" },
    navBar,
    filterBar,
    treeContent,
    hints,
  );
  const selectorHost = element(document, "div", { id: "source-ref-selector" });
  const preview = element(document, "main", { id: "preview-pane" });
  const app = element(document, "div", { class: "app" }, navPane, selectorHost, preview);
  document.body.append(app);

  // ── What app.js does around the modules ───────────────────────
  /** @type {any} */
  let shortcuts = null;
  let help = null;
  let tree = null;
  let keymap = null;
  let reveal = null;
  let palette = null;
  let selector = null;
  let headerCopyBridge = null;
  const stack = { inStack: false };

  const committedBar = () =>
    preview.children.find((child) => child.classList.contains("tab-bar")) ?? null;

  /** app.js committedHeaderControls, on this page's markup. */
  function headerControls() {
    const header = preview.children.find((child) => child.classList.contains("file-header"));
    let parent = null;
    let copy = null;
    if (header?.classList.contains("folder-header")) {
      parent = header.querySelector(".folder-up[data-nav-dir]:not([disabled])");
    } else if (header) {
      parent = header.querySelectorAll(".folder-breadcrumb [data-nav-dir]").at(-1) ?? null;
      copy = header.querySelector(".file-header-copy");
    }
    if (!copy && headerCopyBridge && preview.contains(headerCopyBridge)) {
      copy = headerCopyBridge;
    }
    return { copy, parent };
  }

  const shell = Object.freeze({
    copyFromControl(control) {
      did.push(`copied ${control.getAttribute("data-mb-copy-text")}`);
      return true;
    },
    filterTrigger: (key) => filterBar.querySelector(`[data-chip-menu-toggle="${key}"]`),
    headerControls,
    openFilterMenu(key) {
      did.push(`opened the ${key} menu`);
      return true;
    },
    openFolder(dir) {
      did.push(`opened the folder "${dir}"`);
    },
    selectPreviewTab(bar, tabId) {
      for (const button of bar.querySelectorAll(".tab-btn")) {
        const on = button.dataset.tab === tabId;
        button.classList.toggle("active", on);
        button.setAttribute("aria-selected", on ? "true" : "false");
      }
      did.push(`selected the ${tabId} tab`);
      return true;
    },
    sourceSelector: () => selector,
    viewTabBar: committedBar,
  });

  /** The end of every install of main-pane content: app.js finishRetainedPullPage. */
  function installed() {
    keymap?.syncViewTabs(committedBar());
    keymap?.syncHeader();
  }

  /** renderFolderHeader and the file header, as app.js renders them. */
  function header(data) {
    const segments = data.path ? data.path.split("/") : [];
    const crumbs = [
      element(document, "button", { class: "folder-crumb", "data-nav-dir": "" }, "/"),
    ];
    segments.forEach((segment, index) => {
      const walked = segments.slice(0, index + 1).join("/");
      const last = index === segments.length - 1;
      crumbs.push(
        element(
          document,
          "button",
          {
            class: "folder-crumb",
            [last && data.kind !== "folder" ? "data-nav-file" : "data-nav-dir"]: walked,
          },
          segment,
        ),
      );
    });
    const breadcrumb = element(
      document,
      "span",
      { class: "file-header-path folder-breadcrumb" },
      ...crumbs,
    );
    if (data.kind === "folder") {
      const parent = segments.length > 0 ? segments.slice(0, -1).join("/") : null;
      const up = element(document, "button", {
        "aria-label": parent === null ? "No parent folder" : "Open parent folder",
        class: "btn parent-nav-btn folder-up",
        "data-nav-dir": parent ?? false,
        disabled: parent === null,
      });
      return element(
        document,
        "div",
        { class: "file-header folder-header", "data-kbd-badge-anchor": true },
        up,
        breadcrumb,
      );
    }
    breadcrumb.append(
      element(document, "button", {
        "aria-label": "Copy path",
        class: "icon-btn icon-btn-reveal file-header-copy",
        "data-mb-copy": "text",
        "data-mb-copy-text": data.path,
      }),
    );
    return element(
      document,
      "div",
      { class: "file-header", "data-kbd-badge-anchor": true },
      breadcrumb,
    );
  }

  /**
   * renderFile: build the header and view tab bar in the inert stage, then commit them,
   * calling commitViewTabs inside the commit as app.js does, never while staging.
   */
  function stage(answer) {
    const data = answer.body;
    const views = data.views;
    const initial = views.find((view) => view.default) ?? views[0];
    const staging = element(document, "div", {
      "aria-hidden": "true",
      class: "preview-file-stage",
      inert: true,
    });
    staging.append(header(data));
    if (views.length > 1) {
      const bar = element(document, "div", { class: "tab-bar", role: "tablist" });
      for (const view of views) {
        bar.append(
          element(
            document,
            "button",
            {
              "aria-selected": view === initial ? "true" : "false",
              class: view === initial ? "tab-btn active" : "tab-btn",
              "data-tab": view.id,
              "data-view-key": view.key ?? false,
              role: "tab",
              type: "button",
            },
            view.label,
          ),
        );
      }
      staging.append(bar);
    }
    preview.append(staging);
    return {
      commit() {
        const previousBar = committedBar();
        preview.replaceChildren(...staging.childNodes);
        keymap?.commitViewTabs(previousBar, committedBar());
        installed();
      },
      cancel() {
        staging.remove();
      },
    };
  }

  function open(answer) {
    stage(answer).commit();
  }

  /** renderPreviewNode with a pull request's page, which has no view tab bar of the shell's. */
  function openPullPage(number) {
    preview.replaceChildren(element(document, "article", { class: "pull-page" }, `#${number}`));
    installed();
  }

  /** The Git panel's commit view, which lends its Copy revision through the bridge. */
  let releaseCopy = null;
  function openCommit() {
    const copy = element(document, "button", {
      "aria-label": "Copy revision",
      class: "icon-btn icon-btn-reveal git-commit-revision-copy",
      "data-mb-copy": "text",
      "data-mb-copy-text": REVISION,
    });
    const view = element(
      document,
      "div",
      { class: "git-commit-view" },
      element(document, "div", { class: "git-commit-header", "data-kbd-badge-anchor": true }, copy),
    );
    preview.replaceChildren(view);
    installed();
    releaseCopy?.();
    // MetabrowserShell.attachHeaderCopy in app.js.
    headerCopyBridge = copy;
    keymap?.syncHeader();
    releaseCopy = () => {
      if (headerCopyBridge === copy) {
        headerCopyBridge = null;
        keymap?.syncHeader();
      }
    };
  }

  /** renderNavFilterBar: a pin has no modified-within filter. */
  function renderFilters() {
    const menu = (key, label, summary) =>
      element(
        document,
        "span",
        { class: "chip-menu", "data-chip-menu": key },
        element(
          document,
          "button",
          { "aria-label": label, class: "chip chip-menu-trigger", "data-chip-menu-toggle": key },
          summary,
        ),
      );
    filterBar.replaceChildren(
      ...(pin ? [] : [menu("recency", "Modified within", "Any age")]),
      menu("types", "File type", "Any type"),
    );
    keymap?.syncFilters();
  }

  /** startSourceRefSelector: a mirror's pin mounts the selector and keeps its handle. */
  function mountSelector() {
    if (!pin) {
      return;
    }
    const button = element(
      document,
      "button",
      { class: "source-ref-selector-toggle" },
      `Branch: ${pin.ref_name}`,
    );
    selectorHost.replaceChildren(button);
    selector = Object.freeze({
      activate() {
        did.push("opened the branch list and focused its filter");
      },
      button,
    });
    keymap?.syncSource();
  }

  const mainTabs = context.MetabrowserMainTabs.create({
    cancelPreview() {},
    flushPull() {},
    focusFilesRow: () => tree?.focusCurrent() ?? false,
    isGitHistoryLanding: () => false,
    isPullAddress: (pathname) => pathname.startsWith("/pull"),
    restore: () => Promise.resolve(),
    scrollShadow() {},
  });

  /** The Git panel registers Commits once discovery finds a repository. */
  function discoverGit() {
    if (!repository) {
      return;
    }
    mainTabs.register({
      focusRow() {
        const row = document.querySelector("#tab-git .git-graph-row[data-roving-anchor]");
        row?.focus();
        return row !== null;
      },
      id: "git",
      label: "Commits",
      onFirstShow: null,
      onShow() {
        const panel = document.getElementById("tab-git");
        if (panel.children.length > 0) {
          return;
        }
        // The Commits rows handle J, K, and the arrows in their own listener.
        const commits = ["a1", "b2"].map((id, index) => {
          const row = element(
            document,
            "div",
            { class: "git-graph-row", "data-revision": id, tabindex: index === 0 ? "0" : "-1" },
            id,
          );
          if (index === 0) {
            row.dataset.rovingAnchor = "";
          }
          row.addEventListener("keydown", (event) => {
            if (
              event.key.toLowerCase() === "j" &&
              !event.ctrlKey &&
              !event.metaKey &&
              !event.altKey
            ) {
              event.preventDefault();
              did.push(`the commit row moved down from ${id}`);
            }
          });
          return row;
        });
        panel.append(element(document, "div", { class: "git-graph-list" }, ...commits));
      },
    });
  }

  // The Pulls tab's host, with a stand-in list and a stand-in pull request page.
  let pulls = null;
  if (tabs.includes("pulls")) {
    pulls = context.MetabrowserPullsNav.createPullsNav({
      activate: (panelId) => mainTabs.activate(panelId),
      activeTab: () => mainTabs.active(),
      cancelPrefetch() {},
      container: () => document.getElementById("tab-pulls"),
      loadView: async () => ({
        render(container) {
          container.replaceChildren(
            element(
              document,
              "a",
              { class: "github-pulls-row", href: "/pull/7", tabindex: "0" },
              "#7",
            ),
          );
          return {
            activateAnchor: () => false,
            dispose() {},
            move: () => false,
            released() {},
            setCurrent() {},
            setFilter() {},
            setShown() {},
          };
        },
      }),
      location: () => location,
      openPull: () => Promise.resolve(),
      pageFor: () => ({
        hasStack: () => stack.inStack,
        moveStack(delta) {
          did.push(`moved ${delta > 0 ? "toward the stack's top" : "toward its base"}`);
          return true;
        },
      }),
      pushHref: (href) => history.pushState(null, "", href),
      registerPanel: (panel) => mainTabs.register(panel),
      routes: context.MetabrowserPullRoute,
      schedulePrefetch: () => null,
      scrollRoot: () => treeContent,
      showFailure() {},
    });
    pulls.start();
  }
  let unregisterPulls = [];

  /** initKeyboardInfrastructure, in app.js's order. */
  function build() {
    shortcuts = context.MetabrowserKeyboardShortcuts.create({ document });
    mainTabs.bindShortcuts(shortcuts);
    if (pulls) {
      unregisterPulls = context.MetabrowserPullsNav.registerKeys(pulls, shortcuts);
    }
    help = context.MetabrowserKeyboardHelp.create({
      document,
      hintHost: hints,
      overlay: context.MetabrowserOverlay,
      shortcuts,
    });
    tree = context.MetabrowserTreeKeyboardNavigation.create({
      activate: (row) => row,
      container: filesPanel,
      document,
      navigate: (row) => did.push(`the tree opened ${row.dataset.path}`),
      setFolderExpanded() {},
      shortcuts,
    });
    keymap = context.MetabrowserShellKeymap.createShellKeymap({ shell, shortcuts });
    reveal = context.MetabrowserKeyReveal.createKeyReveal({
      cancel: clock.cancel,
      document,
      schedule: clock.schedule,
      shortcuts,
      visibility: () => document.visibilityState,
      window: browserWindow,
    });
    palette = context.MetabrowserSearchPalette.create({
      controller: { cancel() {}, subscribe: () => () => {} },
      describeOpenFailure: () => ({ message: "" }),
      document,
      getCatalogSnapshot: () => ({ complete: true, observedCount: 0, truncated: false }),
      openFile: async () => ({ status: "opened" }),
      overlay: context.MetabrowserOverlay,
      shortcuts,
    });
  }

  /** disposeKeyboardInfrastructure, for a real pagehide. */
  function teardown() {
    palette.dispose();
    reveal.dispose();
    keymap.dispose();
    tree.dispose();
    help.dispose();
    for (const release of unregisterPulls) {
      release();
    }
    shortcuts.dispose();
  }

  // ── Reading what the page shows ───────────────────────────────
  const shellKeys = new Set();
  function liveKeys() {
    const ids = shortcuts
      .snapshot("help", { includeInactive: true })
      .flatMap((group) => group.commands)
      .flatMap((command) => command.commandIds);
    for (const id of ids) {
      const scope = shortcuts.present(id).scope;
      if (scope !== "view-tabs" && scope !== "help" && scope !== "quick-file") {
        for (const label of shortcuts.present(id).bindings.visible) {
          if (/^[A-Z0-9]$/.test(label)) {
            shellKeys.add(label.toLowerCase());
          }
        }
      }
    }
    return ids
      .filter((id) => shortcuts.isLive(id))
      .map((id) => [
        shortcuts.present(id).bindings.visible.join(" or "),
        id,
        describe(shortcuts.liveTarget(id)),
      ]);
  }

  function badges() {
    return document.body.querySelectorAll(".kbd-badge").map((badge) => {
      const placement = badge.dataset.kbdPlacement;
      const host = badge.parentNode;
      return [
        badge.textContent,
        placement === "beside" ? `beside, in ${host.className}` : describe(host),
      ];
    });
  }

  function strip() {
    const layer = hints.querySelector(".nav-shortcut-reveal");
    const items = (host) =>
      host.children
        .filter((child) => !child.classList.contains("nav-shortcut-reveal"))
        .map(
          (item) =>
            `${item
              .querySelectorAll("kbd")
              .map((keycap) => keycap.textContent)
              .join(" or ")} ${item.querySelector(".nav-shortcut-label")?.textContent}`,
        );
    return layer
      ? { surface: "reveal", items: items(layer) }
      : { surface: "nav", items: items(hints) };
  }

  /** What one step shows, and what the stand-ins were asked since the last step. */
  function record(step, extra = {}) {
    const entry = {
      step,
      reveal: reveal.snapshot().state,
      rootMarked: document.documentElement.hasAttribute("data-key-reveal"),
      keys: liveKeys(),
      badges: badges(),
      strip: strip(),
      help: shortcuts.snapshot("help", { includeInactive: true }).map((group) => group.id),
      ...extra,
    };
    if (did.length > 0) {
      entry.did = did.splice(0);
    }
    return entry;
  }

  // ── Input ─────────────────────────────────────────────────────
  const focused = () => document.activeElement ?? document.body;
  function key(type, name, init = {}) {
    const event = keyEvent(type, name, { target: focused(), ...init });
    focused().dispatchEvent(event);
    return event.defaultPrevented;
  }
  function press(name, init = {}) {
    const handled = key("keydown", name, init);
    key("keyup", name, { shiftKey: init.shiftKey ?? false, ...init, repeat: false });
    return handled;
  }
  const shiftDown = (init = {}) => key("keydown", "Shift", { shiftKey: true, ...init });
  const shiftUp = () => key("keyup", "Shift", { shiftKey: false });
  function pointer(type, x, y) {
    document.body.dispatchEvent({ clientX: x, clientY: y, target: document.body, type });
  }

  return {
    build,
    clock,
    discoverGit,
    document,
    get kbdCreated() {
      return kbdCreated;
    },
    location,
    mainTabs,
    mountSelector,
    open,
    openCommit,
    openPullPage,
    pointer,
    press,
    record,
    renderFilters,
    rows,
    shellKeys,
    shiftDown,
    shiftUp,
    stack,
    stage,
    teardown,
    get shortcuts() {
      return shortcuts;
    },
    window: browserWindow,
    key,
  };
}

/** JSON, with each array of plain values on one line, so a key reads as one row. */
function render(value, indent = "") {
  const inner = `${indent}  `;
  if (Array.isArray(value)) {
    if (value.every((item) => item === null || typeof item !== "object")) {
      return JSON.stringify(value);
    }
    return `[\n${value.map((item) => inner + render(item, inner)).join(",\n")}\n${indent}]`;
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value);
    if (entries.length === 0) {
      return "{}";
    }
    return `{\n${entries
      .map(([name, item]) => `${inner}${JSON.stringify(name)}: ${render(item, inner)}`)
      .join(",\n")}\n${indent}}`;
  }
  return JSON.stringify(value);
}

/** Hold Shift past the threshold. */
function revealOn(page) {
  page.shiftDown();
  page.clock.advance(HOLD_MS);
}

const folder = recording.folder;
const files = folder.files;

/** A plain folder's page with its tree, filters, and root folder, keyboard built. */
function plainPage() {
  const plain = createPage({ repository: folder.repo.body.is_repo });
  plain.renderFilters();
  plain.open(files[""]);
  plain.build();
  plain.discoverGit();
  return plain;
}

// The session's three parts, each its own command in the golden, so no transcript block
// grows past what tryscript can match: the keymap of a folder's files, the gesture, and
// the main tabs with the pull request stack and a mirror's pin.
const PARTS = {
  /** A plain folder: Files only, every multi-view kind, and the view tab letters. */
  async keymap() {
    const steps = [];
    const plain = plainPage();
    steps.push(plain.record("a plain folder shows Files only"));

    plain.open(files["README.md"]);
    steps.push(
      plain.record("a Markdown file has Document and Source", {
        pressed: { key: "s", handled: plain.press("S", { shiftKey: true }) },
      }),
    );

    plain.open(files.docs);
    steps.push(
      plain.record("a folder below the root has no Copy", {
        pressed: { key: "y", handled: plain.press("y") },
      }),
    );
    plain.press("u");
    steps.push(plain.record("U opens the folder above"));

    plain.open(files[""]);
    steps.push(
      plain.record("the root folder has no Up", {
        pressed: { key: "u", handled: plain.press("u") },
      }),
    );
    plain.press("m");
    steps.push(plain.record("M shows the Treemap"));

    plain.open(files["session.jsonl"]);
    steps.push(plain.record("an agent log has Log, Charts, and Raw JSON"));

    // The view tab letters follow the committed bar, and a stage that is cancelled before
    // it commits registers nothing, so the bar on screen keeps its keys.
    plain.open(files["data.json"]);
    const treeR = plain.shortcuts.liveTarget("view-tabs.r");
    plain.open(files["session.jsonl"]);
    const logR = plain.shortcuts.liveTarget("view-tabs.r");
    plain.open(files["data.json"]);
    const cancelled = plain.stage(files["session.jsonl"]);
    const whileStaged = plain.shortcuts.liveTarget("view-tabs.r");
    cancelled.cancel();
    steps.push(
      plain.record("R follows the committed bar, and a cancelled stage changes nothing", {
        r: {
          structured: treeR?.textContent,
          agentLog: logR?.textContent,
          back: plain.shortcuts.liveTarget("view-tabs.r")?.textContent,
          whileStaged: whileStaged?.textContent,
          afterCancel: plain.shortcuts.liveTarget("view-tabs.r")?.textContent,
        },
      }),
    );

    plain.open(folder.inactive_html);
    steps.push(plain.record("an HTML file without active content has no tab keys"));
    return { steps, pages: [plain] };
  },

  /** Holding Shift: what reveals, what does not, and what ends a reveal. */
  async gestures() {
    const steps = [];
    const plain = plainPage();
    plain.open(files["README.md"]);
    plain.shiftDown();
    plain.clock.advance(HOLD_MS - 1);
    steps.push(plain.record("Shift held below the threshold shows nothing yet"));
    plain.clock.advance(1);
    steps.push(plain.record("Shift held past the threshold reveals"));
    plain.shiftUp();
    steps.push(plain.record("releasing Shift puts everything back"));

    plain.shiftDown();
    plain.clock.advance(50);
    const capital = plain.press("Z", { shiftKey: true });
    plain.clock.advance(HOLD_MS);
    steps.push(
      plain.record("a capital typed within the threshold never reveals", {
        pressed: { key: "Z", handled: capital },
      }),
    );
    plain.shiftUp();

    plain.shiftDown();
    plain.clock.advance(50);
    plain.key("keydown", "?", { shiftKey: true });
    plain.clock.advance(HOLD_MS);
    steps.push(plain.record("? within the threshold opens Help and never reveals"));
    plain.key("keyup", "?", { shiftKey: true });
    plain.shiftUp();
    plain.press("Escape");

    plain.shiftDown();
    plain.document.body.dispatchEvent({ target: plain.document.body, type: "wheel" });
    plain.clock.advance(HOLD_MS);
    steps.push(plain.record("Shift+wheel never reveals"));
    plain.shiftUp();

    plain.pointer("pointermove", 10, 10);
    plain.shiftDown();
    plain.pointer("pointermove", 13, 10);
    plain.pointer("pointermove", 30, 12);
    plain.clock.advance(HOLD_MS);
    steps.push(plain.record("Shift with the pointer travelling to a click never reveals"));
    plain.pointer("pointerdown", 30, 12);
    plain.pointer("pointerup", 30, 12);
    plain.shiftUp();

    plain.pointer("pointermove", 30, 12);
    plain.shiftDown();
    plain.pointer("pointermove", 32, 13);
    plain.clock.advance(HOLD_MS);
    steps.push(plain.record("a resting hand within the slop still reveals"));
    plain.pointer("pointerdown", 32, 13);
    steps.push(plain.record("a pointer press while revealed dismisses it"));
    plain.pointer("pointerup", 32, 13);
    plain.shiftUp();

    // Tree keys keep the reveal; a repeat does no reveal work.
    plain.rows[1].focus();
    revealOn(plain);
    const mountsBefore = plain.kbdCreated;
    const up = plain.key("keydown", "ArrowUp", { shiftKey: true });
    steps.push(
      plain.record("↑ on a tree row moves one row and keeps the reveal", {
        pressed: { key: "ArrowUp", handled: up },
        focusedRow: plain.document.activeElement.dataset.path,
        badgesRemounted: plain.kbdCreated - mountsBefore,
      }),
    );
    plain.key("keydown", "j", { shiftKey: true });
    const afterFirst = plain.kbdCreated;
    plain.key("keydown", "j", { repeat: true, shiftKey: true });
    plain.key("keydown", "j", { repeat: true, shiftKey: true });
    steps.push(
      plain.record("a held J moves rows and does no reveal work on its repeats", {
        focusedRow: plain.document.activeElement.dataset.path,
        badgesRemountedByRepeats: plain.kbdCreated - afterFirst,
      }),
    );
    plain.window.fire("blur");
    steps.push(plain.record("the window losing focus ends the reveal"));
    plain.shiftUp();

    revealOn(plain);
    plain.key("keydown", "j", { shiftKey: false });
    steps.push(plain.record("a key without Shift ends a reveal whose keyup was lost"));
    plain.key("keyup", "j");

    revealOn(plain);
    plain.document.visibilityState = "hidden";
    plain.document.dispatchEvent({ target: plain.document, type: "visibilitychange" });
    steps.push(plain.record("the page going hidden ends the reveal"));
    plain.document.visibilityState = "visible";
    plain.shiftUp();

    // Shift in Quick Search's field types capitals; Help shows only its own keys.
    plain.document.body.focus();
    plain.press("t");
    plain.shiftDown();
    plain.clock.advance(HOLD_MS);
    steps.push(
      plain.record("Shift in Quick Search's field never reveals", {
        focus: plain.document.activeElement.getAttribute("role"),
      }),
    );
    plain.shiftUp();
    plain.press("Escape");
    plain.press("?", { shiftKey: true });
    revealOn(plain);
    steps.push(plain.record("with Help open only Help's keys are live"));
    plain.shiftUp();
    plain.press("Escape");

    // The keymap is created after the page has rendered, and rebuilt after a pagehide.
    const before = plain.record("the keymap the page built at first");
    plain.teardown();
    plain.build();
    const after = plain.record("the keymap after a pageshow rebuild");
    steps.push({
      ...after,
      sameAsBefore: JSON.stringify(after.keys) === JSON.stringify(before.keys),
    });
    return { steps, pages: [plain] };
  },

  /** The main tabs, the commit view, the pull request stack, and a mirror's pin. */
  async tabs() {
    const steps = [];
    const repo = createPage({ repository: recording.repository.repo.body.is_repo });
    repo.renderFilters();
    repo.open(files[""]);
    repo.build();
    repo.discoverGit();
    steps.push(repo.record("a Git repository shows Files and Commits"));

    revealOn(repo);
    const two = repo.press("@", { code: "Digit2", shiftKey: true });
    steps.push(
      repo.record("2 with Shift still held opens Commits, focuses its row, and keeps the reveal", {
        pressed: { key: "2", handled: two },
        active: repo.mainTabs.active(),
        focus: repo.document.activeElement.textContent,
      }),
    );
    const one = repo.press("!", { code: "Digit1", shiftKey: true });
    steps.push(
      repo.record("1 during the reveal shows the filter bar, and X and A gain badges", {
        pressed: { key: "1", handled: one },
        active: repo.mainTabs.active(),
        focus: repo.document.activeElement.dataset.path ?? repo.document.activeElement.textContent,
      }),
    );
    repo.shiftUp();
    steps.push(repo.record("releasing Shift ends the reveal"));

    repo.press("2");
    repo.document.querySelector("#tab-git .git-graph-row").focus();
    revealOn(repo);
    repo.key("keydown", "j", { shiftKey: true });
    steps.push(repo.record("J on a commit row ends the reveal, since the row handles it itself"));
    repo.key("keyup", "j");
    repo.shiftUp();

    repo.openCommit();
    steps.push(
      repo.record("a commit view's Y copies its revision", {
        pressed: { key: "y", handled: repo.press("y") },
      }),
    );
    repo.press("1");
    await settle();

    // ── Pulls drawn before Git discovery, and a pull request stack ─
    const hosted = createPage({
      repository: recording.repository.repo.body.is_repo,
      tabs: ["files", "pulls"],
    });
    hosted.renderFilters();
    hosted.open(files[""]);
    hosted.build();
    steps.push(
      hosted.record("Pulls drawn before Commits keeps 3, and 2 stays reserved", {
        pressed: { key: "2", handled: hosted.press("2") },
      }),
    );
    hosted.discoverGit();
    steps.push(hosted.record("a repository with a hosted origin shows Files, Commits, and Pulls"));

    hosted.open(files["page.html"]);
    steps.push(
      hosted.record("the Preview tab's P sits beside the stack's P", {
        pressed: { key: "p", handled: hosted.press("p") },
      }),
    );

    hosted.press("3");
    await settle();
    steps.push(
      hosted.record("3 again, once the list has rows, moves focus to the selected row", {
        pressed: { key: "3", handled: hosted.press("3") },
        focus: hosted.document.activeElement.textContent,
      }),
    );
    hosted.location.pathname = "/pull/7";
    hosted.openPullPage(7);
    steps.push(
      hosted.record("a pull request outside a stack has no N or P", {
        focus: hosted.document.activeElement.textContent,
        pressed: { key: "n", handled: hosted.press("n") },
      }),
    );
    hosted.stack.inStack = true;
    hosted.document.body.focus();
    revealOn(hosted);
    steps.push(
      hosted.record("a pull request in a stack lists N or P on the strip", {
        pressed: { key: "n", handled: hosted.press("N", { shiftKey: true }) },
      }),
    );
    hosted.shiftUp();
    steps.push(
      hosted.record("P walks the stack toward its base", {
        pressed: { key: "p", handled: hosted.press("p") },
      }),
    );

    // ── A mirror's pin: the branch switcher, and no modified-within filter ─
    const pinned = createPage({
      pin: recording.pin.status.body,
      repository: recording.pin.repo.body.is_repo,
    });
    pinned.renderFilters();
    pinned.open(recording.pin.files[""]);
    pinned.build();
    pinned.mountSelector();
    steps.push(
      pinned.record("a mirror's pin has W and no A", {
        pressed: { key: "w", handled: pinned.press("w") },
        a: pinned.press("a"),
      }),
    );

    return { steps, pages: [repo, hosted, pinned] };
  },
};

async function main() {
  const part = process.argv[2] ?? "keymap";
  if (!Object.hasOwn(PARTS, part)) {
    throw new Error(`Unknown part ${part}; the parts are ${Object.keys(PARTS).join(", ")}`);
  }
  const { steps, pages } = await PARTS[part]();
  const shellKeys = new Set(pages.flatMap((page) => [...page.shellKeys]));
  process.stdout.write(`${render({ part, steps, shellKeys: [...shellKeys].sort() })}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
