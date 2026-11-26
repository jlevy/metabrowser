// Browserless session: the Shift key reveal and the shell's keymap, on the production code.
//
// The shortcut registry, the reveal (static/key-reveal.js), the shell keymap
// (static/shell-keymap.js), Help and its strip with the real overlay layer, the file
// tree's keys, Quick Search, the main tabs (static/main-tabs.js), the Pulls tab's keys
// (static/pulls-nav.js), and the filter bar's dropdowns (static/filter-controls.js) load
// whole, with injected time, pointer, and visibility, on a stand-in DOM whose window is
// on every event's path. What app.js would do is played here: it renders each file's
// header and view tab bar from the server's answer, stages it in an inert layer, and
// commits it, calling the keymap where app.js does; it renders the filter bar from the
// filter controls' markup and opens a menu as a trigger's click does; and it stands in
// for the other activation paths (selectPreviewTab, the selector's handle, the Up
// navigation), recording what each was asked. tests/test_shell_keymap_integration.py
// holds app.js's own markup to the hooks the keymap reads. The file header and a
// stand-in commit view carry their copy buttons, which are ancillary and must carry no
// key, and a stand-in pull request page offers hasStack() and moveStack().
//
// The filters are situational, so they take numbers, 1 to 9 in reading order, from the
// registry's one numbering; Help lists the numbers once, as positional, and never gives
// a digit a fixed meaning, which the session checks as it records Help.
//
// The server's side is tests/fixtures/key-reveal-responses.json: the `/api/file`,
// `/api/git/repo`, and `/api/source/status` answers of the in-process application, which
// tests/test_key_reveal_session.py records and holds the shell keys printed here to.
//
// Each step records the reveal's state, the live keymap as key, command, and target, the
// badges mounted, the strip's surface and items, and Help's groups. A step with a `cost`
// records what one navigation or key cost: the registry's publications, its liveness
// reads of targets, and the keycaps built.

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
  "formatters.js",
  "navigation.js",
  "pull-route.js",
  "filter-controls.js",
  "main-tabs.js",
  "menus.js",
  "keyboard-shortcuts.js",
  "overlay-layer.js",
  "keyboard-help.js",
  "key-reveal.js",
  "nav-collapse.js",
  "shell-keymap.js",
  "tree-keyboard-navigation.js",
  "search-palette.js",
  "pulls-nav.js",
];
const SOURCES = new Map(
  MODULES.map((name) => [name, fs.readFileSync(path.join(staticDir, name), "utf8")]),
);
const TAB_LABELS = { files: "Files", git: "Commits", pulls: "Pulls" };

// The view header's builders, from the production view-header.js over app.js's own `esc`,
// lifted verbatim, since app.js cannot load without a document: the header's structure
// and its Up control are the shell's own, so a change to either reaches the keymap here.
// The collaborators that do not branch on the structure are stubs.
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");
// The shell's motion for chrome that appears, which the navigation pane's slide reads from
// the stylesheet: read from styles.css here too, so the session runs the value it ships.
const MOTION_REVEAL = /^\s*--motion-reveal:\s*([^;]+);/m.exec(
  fs.readFileSync(path.join(staticDir, "styles.css"), "utf8"),
)[1];
// The navigation pane's width in the stand-in, which lays nothing out: the slide runs it.
const NAV_PANE_WIDTH = 300;
// A centered reading column's inset with the pane hidden, `--reading-inset` in styles.css,
// which the stand-in, laying nothing out, sets as the stylesheet would: the content's glide
// runs it.
const READING_INSET = 415;
const liftApp = (name) => {
  const match = appSource.match(new RegExp(`\\nfunction ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`));
  if (!match) {
    throw new Error(`${name} not found in app.js`);
  }
  return match[0];
};
const viewHeader = (() => {
  const page = {
    MetabrowserNavigationRoute: { displayPath: (/** @type {string} */ p) => p },
  };
  page.window = page;
  vm.createContext(page);
  vm.runInContext(fs.readFileSync(path.join(staticDir, "view-header.js"), "utf8"), page);
  const esc = vm.runInContext(`${liftApp("esc")}\nesc;`, page);
  const notDrawnHere = () => {
    throw new Error("this session's headers draw only their structure and Up");
  };
  return page.MetabrowserViewHeader.create({
    esc,
    servedRoot: notDrawnHere,
    pathBaseName: notDrawnHere,
    ownedControlAttr: () => "",
    mirrorHeading: notDrawnHere,
    getFileIcon: notDrawnHere,
    getLogicalName: notDrawnHere,
    sizeHtml: notDrawnHere,
    countHtml: notDrawnHere,
    formatAge: notDrawnHere,
    activeFiles: new Map(),
  });
})();
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
  if (target.classList.contains("chip-menu-item")) {
    return `${target.querySelector(".menu-item-label")?.textContent} row`;
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
  // The document's own window, on every event's path: a capture listener there hears an
  // element's `blur` when a key moves focus, as it does in a browser.
  const browserWindow = document.defaultView;
  let kbdCreated = 0;
  const createElement = document.createElement.bind(document);
  document.createElement = (tagName) => {
    if (tagName === "kbd") {
      kbdCreated += 1;
    }
    return createElement(tagName);
  };
  // What a step costs. Without checkVisibility(), as here, the registry reads a target's
  // liveness through its computed style, and reads the target's own `display` once each
  // time; a badge placed beside its target reads its `direction` once as it mounts.
  let targetReads = 0;
  const computedStyle = browserWindow.getComputedStyle.bind(browserWindow);
  browserWindow.getComputedStyle = (node) => {
    const style = computedStyle(node);
    // The root's custom properties, and the main frame's transform mid-slide, are the two
    // computed values static/nav-collapse.js reads.
    if (node === document.documentElement) {
      return Object.assign(Object.create(style), {
        getPropertyValue: (name) => (name === "--motion-reveal" ? MOTION_REVEAL : ""),
      });
    }
    if (node === frame) {
      return Object.assign(Object.create(style), { transform: frameTransform() });
    }
    if (node === column) {
      const inset = app.hasAttribute("data-nav-collapsed") ? READING_INSET : 0;
      return Object.assign(Object.create(style), {
        getPropertyValue: (name) => (name === "--reading-inset" ? `${inset}px` : ""),
        transform: glideTransform(),
      });
    }
    if (!node.hasAttribute?.("aria-keyshortcuts")) {
      return style;
    }
    return {
      get display() {
        targetReads += 1;
        return style.display;
      },
      get visibility() {
        return style.visibility;
      },
      get direction() {
        return style.direction;
      },
      // A toggle reads where a box in the main view is laid out and drawn.
      getPropertyValue: (name) => style.getPropertyValue(name),
      get transform() {
        return style.transform;
      },
    };
  };
  /** The registry's publications since the last measure(), by kind. */
  const published = [];

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
    addEventListener: (type, listener, options) =>
      browserWindow.addEventListener(type, listener, options),
    clearTimeout: (timer) => clock.cancel(timer),
    console: { error() {}, warn() {}, log() {} },
    document,
    history,
    location,
    metabrowser: {
      decorateExternalLink() {},
      ensureAsset: () => new Promise(() => {}),
    },
    // source-ref-selector.js, which keeps the selector it mounted for the branch key.
    MetabrowserSourceRefSelector: {
      mounted: () => selector,
    },
    queueMicrotask,
    removeEventListener: (type, listener, options) =>
      browserWindow.removeEventListener(type, listener, options),
    setTimeout: (callback, delayMs) => clock.schedule(callback, delayMs),
    // A Mac's navigator: the stack's Control chords are bound only where Control reaches
    // the page (static/keyboard-shortcuts.js, `controlReachesPage`), and
    // pulls-nav-session.js shows Windows and Linux binding none.
    navigator: { platform: "MacIntel" },
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
  // The Files tab's toolbar in the navigation's toolbar slot, which main-tabs.js hides
  // while another tab is in front, as the server's shell marks it.
  const filterBar = element(document, "div", { id: "nav-filter-bar", "data-nav-toolbar": "files" });
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
  // The nav's header as server.py writes it: the folder's name, which is Home and `0`'s
  // target, labelled "Home:" and its own text, and the navigation's Refresh, an icon button
  // the keymap numbers first, in a header that anchors the badges.
  const navHeader = element(
    document,
    "header",
    { class: "app-header", "data-kbd-badge-anchor": "" },
    element(
      document,
      "a",
      {
        "aria-labelledby": "header-home-label header-home-name",
        class: "header-path",
        href: "/view/",
        id: "header-home",
      },
      element(document, "span", { class: "header-home-name", id: "header-home-name" }, "squares"),
    ),
    element(document, "span", { hidden: "", id: "header-home-label" }, "Home:"),
    element(document, "button", {
      "aria-label": "Refresh",
      class: "icon-btn nav-refresh",
      "data-tip-text": "Refresh",
      id: "nav-refresh",
      type: "button",
    }),
  );
  const navPane = element(
    document,
    "nav",
    { class: "tree-pane" },
    navHeader,
    navBar,
    filterBar,
    treeContent,
    hints,
  );
  const selectorHost = element(document, "div", { id: "source-ref-selector" });
  const preview = element(document, "main", { id: "preview-pane" });
  // The chevron that hides the navigation pane, in the main frame beside the page, as
  // server.py writes it; static/nav-collapse.js runs on it as app.js creates it.
  const navToggleButton = element(document, "button", {
    "aria-controls": "tree-pane",
    "aria-expanded": "true",
    "aria-label": "Hide navigation",
    class: "icon-btn nav-collapse-toggle disclosure-toggle",
    id: "nav-collapse-toggle",
    type: "button",
  });
  // A reading column in the main view's body, which the stylesheet centers with the pane
  // hidden, and which static/nav-collapse.js finds by its place in the main view.
  const column = element(document, "article", { class: "kpress-doc" });
  preview.append(element(document, "div", { class: "content-body" }, column));
  const frame = element(document, "div", { class: "preview-frame" }, preview, navToggleButton);
  const app = element(document, "div", { class: "app" }, navPane, selectorHost, frame);
  document.body.append(app);
  Object.defineProperty(navPane, "offsetWidth", { value: NAV_PANE_WIDTH });
  // The frame's slide, as Web Animations runs it, held at the share of its way the session
  // sets: nav-collapse.js reads the frame's transform when a key turns a slide back, and
  // the session finishes each slide as its end would.
  /** @type {any[]} */
  const slides = [];
  const offsetOf = (keyframe) =>
    Number.parseFloat(/translate3d\((-?[\d.]+)px/.exec(keyframe.transform)?.[1] ?? "0");
  /**
   * Web Animations' `animate`, held at the share of its way the session sets.
   *
   * @param {any[]} list
   */
  const animator = (list) => (keyframes, timing) => {
    let resolve = () => {};
    let reject = () => {};
    const slide = {
      from: offsetOf(keyframes[0]),
      to: offsetOf(keyframes.at(-1)),
      duration: timing.duration,
      easing: timing.easing,
      fill: timing.fill ?? "none",
      progress: 0,
      state: "running",
      finished: new Promise((onFinish, onCancel) => {
        resolve = onFinish;
        reject = onCancel;
      }),
      cancel() {
        if (slide.state === "running") {
          slide.state = "cancelled";
          reject(new Error("The slide was cancelled"));
        }
      },
      finish() {
        slide.progress = 1;
        slide.state = "finished";
        resolve(slide);
      },
    };
    // Web Animations marks a cancelled animation's `finished` promise handled, so cancelling
    // one that nothing awaits, as a glide is, raises nothing.
    slide.finished.catch(() => {});
    list.push(slide);
    return slide;
  };
  frame.animate = animator(slides);
  // The column's glide beside the frame's slide, which static/nav-collapse.js runs on what
  // app.js names as the content a centered column moves.
  /** @type {any[]} */
  const glides = [];
  column.animate = animator(glides);
  const runningSlide = () => slides.find((slide) => slide.state === "running") ?? null;
  const runningGlide = () => glides.find((glide) => glide.state === "running") ?? null;
  /** @param {any} animation */
  const matrixAt = (animation) =>
    animation
      ? `matrix(1, 0, 0, 1, ${animation.from + (animation.to - animation.from) * animation.progress}, 0)`
      : "none";
  function frameTransform() {
    return matrixAt(runningSlide());
  }
  function glideTransform() {
    return matrixAt(runningGlide());
  }
  const navCollapse = context.MetabrowserNavCollapse.create({
    button: navToggleButton,
    container: app,
    document,
    focusFallback: () => preview,
    frame,
    // app.js closes an open filter menu, as hiding the Files panel does.
    onHide: () => {
      if (filterOpenMenu !== null) {
        shell.toggleFilterMenu(filterOpenMenu, false);
      }
    },
    pane: navPane,
  });
  /** The slide running now, as its ends and timing, and the column's glide, or null. */
  function slide() {
    const running = runningSlide();
    const glide = runningGlide();
    return (
      running && {
        from: running.from,
        to: running.to,
        duration: running.duration,
        easing: running.easing,
        cancelled: slides.filter((each) => each.state === "cancelled").length,
        glide: glide && {
          from: glide.from,
          to: glide.to,
          duration: glide.duration,
          fill: glide.fill,
          cancelled: glides.filter((each) => each.state === "cancelled").length,
        },
      }
    );
  }
  /** Move the running slide and glide to a share of their way. */
  function slideTo(progress) {
    for (const running of [runningSlide(), runningGlide()]) {
      if (running) {
        running.progress = progress;
      }
    }
  }
  /** End every running slide and glide, as the time passing would, and let them settle. */
  async function finishSlides() {
    for (const running of [...slides, ...glides].filter((each) => each.state === "running")) {
      running.finish();
    }
    await settle();
  }
  /** The navigation pane's state, as the chevron and the layout say it. */
  function nav() {
    return {
      inert: navPane.hasAttribute("inert"),
      inLayout: !app.hasAttribute("data-nav-collapsed"),
      expanded: navToggleButton.getAttribute("aria-expanded"),
      label: navToggleButton.getAttribute("aria-label"),
    };
  }

  // ── What app.js does around the modules ───────────────────────
  /** @type {any} */
  let shortcuts = null;
  let help = null;
  let tree = null;
  let keymap = null;
  let reveal = null;
  let palette = null;
  let selector = null;
  let filterOpenMenu = null;
  // Group by's value, which its menu's rows choose.
  let groupBy = "none";
  // The filter drawer starts closed, as the shell's does, and a filter's number opens it.
  let filterDrawerOpen = false;
  const stack = { inStack: false };

  const committedBar = () => keymap?.committedBar() ?? null;

  // app.js shellKeymapShell: the state only app.js holds, and the paths its controls run.
  const shell = Object.freeze({
    // app.js goHome, the folder's name's click; tests/dom/preview-pane-state-session.js
    // runs it.
    goHome() {
      did.push("went home");
    },
    navToggle: () => navToggleButton,
    // app.js toggleNav, the chevron's click, through the production nav-collapse.js.
    toggleNav() {
      navCollapse.toggle();
      did.push(`${navCollapse.isCollapsed() ? "hid" : "showed"} the navigation pane`);
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
    // app.js toggleFilterMenu, a trigger's click: remember the open menu and render the
    // bar again, which reports the new triggers to the keymap.
    toggleFilterMenu(key, open) {
      filterOpenMenu = open ? key : null;
      // The filters live in the drawer: opening one opens the drawer with it.
      if (open && key !== "group") {
        filterDrawerOpen = true;
      }
      renderFilters();
      did.push(`${open ? "opened" : "closed"} the ${key} menu`);
    },
  });
  // initFilterBar: a trigger's click, Escape, and a press outside run toggleFilterMenu; a
  // row's click, and its letter through filterControls.activateMenuRow, run onMenuPick, which
  // for Group by sets the value and closes the menu, as a single-select pick does, and for
  // File type leaves it open, as a multi-select one does. Either renders the bar again,
  // as the filter state's subscriber does in app.js.
  context.metabrowser.filterControls.bind(filterBar, {
    onMenuPick(key, value) {
      did.push(`chose ${value ?? "the any-row"} in the ${key} menu`);
      if (key === "group") {
        groupBy = value ?? "none";
        filterOpenMenu = null;
      }
      renderFilters();
    },
    onMenuToggle: shell.toggleFilterMenu,
  });

  /** The end of every install of main-pane content: app.js finishRetainedPullPage. */
  function installed() {
    keymap?.syncPane();
  }

  /** renderFolderHeader and renderFileHeader, through app.js's own builders. */
  function header(data) {
    const segments = data.path ? data.path.split("/") : [];
    // The eyebrow's address: the root's crumb, then each folder above the item, each
    // followed by its separator.
    const separator = '<span class="folder-crumb-sep">/</span>';
    const crumbs =
      segments.length === 0
        ? ""
        : `<button class="folder-crumb folder-crumb-root" data-nav-dir=""><bdi>~/wrk/project</bdi></button>${separator}`;
    const folders = segments
      .slice(0, -1)
      .map(
        (segment, index) =>
          `<button class="folder-crumb" data-nav-dir="${segments.slice(0, index + 1).join("/")}">${segment}</button>${separator}`,
      )
      .join("");
    const copy =
      data.kind === "folder"
        ? ""
        : `<button class="icon-btn icon-btn-reveal file-header-copy" aria-label="Copy path" data-mb-copy="text" data-mb-copy-text="${data.path}"></button>`;
    const holder = element(document, "div");
    holder.innerHTML = viewHeader.viewHeaderHtml({
      className: data.kind === "folder" ? "folder-header" : "",
      eyebrow:
        viewHeader.viewHeaderUpHtml(data.path ?? "") +
        `<span class="file-header-path folder-breadcrumb">${crumbs}${folders}</span>${copy}`,
      iconHtml: "",
      title: segments.at(-1) ?? "root",
      end: "",
      line: "",
    });
    return holder.firstElementChild;
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
    // Every file has the bar, a lone view's too, and only a bar of two or more views
    // carries the views' keys.
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
            "data-view-key": (views.length > 1 && view.key) || false,
            role: "tab",
            type: "button",
          },
          view.label,
        ),
      );
    }
    staging.append(bar);
    // The file's body, which holds the page's reading column.
    staging.append(element(document, "div", { class: "content-body" }, column));
    preview.append(staging);
    return {
      commit() {
        preview.replaceChildren(...staging.childNodes);
        keymap?.commitViewTabs(committedBar());
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

  /** The Git panel's commit view, whose Copy revision is ancillary and has no key. */
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
      element(document, "div", { class: "git-commit-header" }, copy),
    );
    preview.replaceChildren(view);
    installed();
  }

  /**
   * renderNavFilterBar: Group by on the row and, in the open drawer, the two filter
   * dropdowns, from the production filter controls, so the triggers, panels, and checked
   * rows the filter numbers reach are that module's markup. A pin has no modified-within
   * filter and no By age, as filterGroupOptions leaves out. The options are a stand-in
   * for the tallies.
   */
  function renderFilters() {
    const controls = context.metabrowser.filterControls;
    const recency = pin
      ? ""
      : controls.menuGroupHtml({
          anyLabel: "Any age",
          anyValue: "all",
          key: "recency",
          label: "Modified within",
          menuId: "filter-recency-menu",
          open: filterOpenMenu === "recency",
          options: [
            { label: "Past hour", value: "1h" },
            { label: "Past day", value: "24h" },
          ],
          select: "one",
          value: "all",
        });
    const types = controls.menuGroupHtml({
      anyLabel: "Any type",
      key: "types",
      label: "File type",
      menuId: "filter-type-menu",
      open: filterOpenMenu === "types",
      options: [
        { count: 2, label: ".md", value: ".md" },
        { count: 1, label: ".json", value: ".json" },
      ],
      value: null,
    });
    const group = controls.menuGroupHtml({
      anyKey: "n",
      anyLabel: "No grouping",
      anyValue: "none",
      key: "group",
      label: "Group by",
      menuId: "filter-group-menu",
      open: filterOpenMenu === "group",
      options: [
        { key: "a", label: "By age", value: "age" },
        { key: "t", label: "By file type", value: "type" },
      ].filter((option) => !pin || option.value !== "age"),
      select: "one",
      value: groupBy,
    });
    // The row end's stand-ins number the closed, inert drawer's filters (app.js,
    // filterKeySlotsHtml).
    const slots = (pin ? ["types"] : ["recency", "types"])
      .map(
        (key) =>
          `<span class="filter-key-slot" data-filter-key-slot="${key}" aria-hidden="true"` +
          ` aria-label="${key === "recency" ? "Modified within" : "File type"}"></span>`,
      )
      .join("");
    // The rebuild keeps focus on the control that had it, as app.js's does.
    const restoreFocus = controls.keepFocus(filterBar);
    filterBar.innerHTML =
      `<div class="nav-filter-bar-main">${group}<span class="nav-filter-bar-end">${slots}</span></div>` +
      `<div class="filter-drawer" id="filter-drawer" data-open="${filterDrawerOpen}"${filterDrawerOpen ? "" : " inert"}>` +
      `<div class="filter-drawer-row">${recency}${types}</div></div>`;
    keymap?.syncFilters();
    restoreFocus();
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
    filesShown() {},
    filesHidden() {},
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
    shortcuts.subscribe((event) =>
      published.push(event.kind === "batch" ? `batch(${event.kinds.join(",")})` : event.kind),
    );
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
    // As app.js creates it: the window is the document's own.
    reveal = context.MetabrowserKeyReveal.createKeyReveal({
      cancel: clock.cancel,
      document,
      schedule: clock.schedule,
      shortcuts,
      visibility: () => document.visibilityState,
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
    mainTabs.bindShortcuts(null);
    shortcuts.dispose();
  }

  // ── Reading what the page shows ───────────────────────────────
  const shellKeys = new Set();
  /** Each shell letter with the command it is bound to and that command's own action,
   * from the registry's presentation: tests/test_keymap.py holds the design system's
   * table to these, so a documented meaning is checked against the command, not only
   * the letter. */
  const shellCommands = new Set();
  function liveKeys() {
    const ids = shortcuts
      .snapshot("help", { includeInactive: true })
      .flatMap((group) => group.commands)
      .flatMap((command) => command.commandIds);
    for (const id of ids) {
      const { bindings, copy, scope } = shortcuts.present(id);
      // A menu's row letters are its own, in its own scope, and never the shell's.
      if (
        scope !== "view-tabs" &&
        scope !== "help" &&
        scope !== "quick-file" &&
        !scope.startsWith("menu:")
      ) {
        // A run, the situational numbers, is written by its ends and binds every key
        // between them.
        const labels = bindings.range
          ? Array.from(
              { length: Number(bindings.visible[1]) - Number(bindings.visible[0]) + 1 },
              (_, index) => String(Number(bindings.visible[0]) + index),
            )
          : bindings.visible;
        for (const label of labels) {
          if (/^[A-Z0-9]$/.test(label)) {
            shellKeys.add(label.toLowerCase());
          }
          // A letter, or `0`, Home: the one digit with a fixed meaning, whose row the
          // design system's table gives like a letter's.
          if (/^[A-Z0]$/.test(label) && !bindings.range) {
            shellCommands.add(`${label.toLowerCase()} ${id}: ${copy.action}`);
          }
          // A Control chord, written as a Mac writes it.
          const chord = /^⌃([A-Z])$/.exec(label);
          if (chord) {
            shellKeys.add(`control-${chord[1].toLowerCase()}`);
            shellCommands.add(`control-${chord[1].toLowerCase()} ${id}: ${copy.action}`);
          }
        }
      }
    }
    return ids
      .filter((id) => shortcuts.isLive(id))
      .map((id) => {
        const { bindings } = shortcuts.present(id);
        return [
          bindings.visible.join(bindings.range ? "–" : " or "),
          id,
          describe(shortcuts.liveTarget(id)),
        ];
      });
  }

  /** What each number reaches now, in order: the first is 1. */
  function numbers() {
    return shortcuts.liveNumbers().map((target) => describe(target));
  }

  /**
   * Help's rows that bind a digit, each as its keys and whether they are a run. The
   * numbers are positional, so such a row is the one run 1 to 9, or `0`, Home, the one
   * digit with a fixed meaning: any other row giving a digit a fixed meaning fails the
   * session.
   */
  function helpDigits() {
    const rows = shortcuts
      .snapshot("help", { includeInactive: true })
      .flatMap((group) => group.commands)
      .filter((command) => command.bindings.visible.some((label) => /^[0-9]$/.test(label)))
      .map((command) => ({
        keys: command.bindings.visible.join(command.bindings.range ? "–" : " or "),
        range: command.bindings.range === true,
        action: command.copy.action,
      }));
    const fixed = rows.filter((row) => !row.range && !(row.keys === "0" && row.action === "Home"));
    if (fixed.length > 0) {
      throw new Error(`Help gives a digit a fixed meaning: ${JSON.stringify(fixed)}`);
    }
    return rows;
  }

  /**
   * The copy controls on screen, each with the key it carries and whether a badge sits on
   * or beside it. Copying is ancillary, so each has none: a keyed one fails the session.
   */
  function ancillary() {
    const copies = document.body.querySelectorAll("[data-mb-copy]");
    const keyed = copies.filter(
      (control) =>
        control.hasAttribute("aria-keyshortcuts") ||
        control.querySelector(".kbd-badge") !== null ||
        shortcuts.liveNumbers().includes(control),
    );
    if (keyed.length > 0) {
      throw new Error(`An ancillary control has a key: ${keyed.map(describe).join(", ")}`);
    }
    return copies.map((control) => describe(control));
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

  /**
   * What `work` cost: the registry's publications, how many times it read a target's
   * liveness, and how many keycaps it built, for badges and the strip together.
   */
  function measure(work) {
    published.length = 0;
    targetReads = 0;
    const keycapsBefore = kbdCreated;
    work();
    return {
      publications: published.splice(0),
      targetReads,
      keycapsCreated: kbdCreated - keycapsBefore,
    };
  }

  /** What one step shows, and what the stand-ins were asked since the last step. */
  function record(step, extra = {}) {
    const entry = {
      step,
      reveal: reveal.snapshot().state,
      rootMarked: document.documentElement.hasAttribute("data-key-reveal"),
      keys: liveKeys(),
      numbers: numbers(),
      badges: badges(),
      strip: strip(),
      help: shortcuts.snapshot("help", { includeInactive: true }).map((group) => group.id),
      ...extra,
    };
    helpDigits();
    ancillary();
    if (did.length > 0) {
      entry.did = did.splice(0);
    }
    return entry;
  }

  /** The filter menu row that has focus, as its menu, label, and checked state. */
  /** Whether the filter drawer is open, as its markup says. */
  function drawerOpen() {
    return filterBar.querySelector("#filter-drawer")?.getAttribute("data-open") === "true";
  }

  function menuFocus() {
    const row = document.activeElement;
    const panel = row?.closest(".chip-menu-panel");
    if (!panel || !row.classList.contains("chip-menu-item")) {
      return null;
    }
    return {
      menu: panel.id,
      row: row.querySelector(".menu-item-label")?.textContent ?? null,
      checked: row.getAttribute("aria-checked"),
      open: panel.parentNode.getAttribute("aria-expanded"),
    };
  }

  /**
   * Where focus is, for the filter bar's keys: a menu row as `menuFocus` says, a trigger by
   * its menu, the body, or an element no longer in the page, which a browser would report
   * as the body.
   */
  function filterFocus() {
    const active = document.activeElement;
    if (!active || active === document.body) {
      return "body";
    }
    if (!active.isConnected) {
      return "a replaced element";
    }
    const trigger = active.getAttribute("data-chip-menu-toggle");
    return menuFocus() ?? (trigger ? `the ${trigger} trigger` : describe(active));
  }

  /** One Help group's rows, each as its keys, action, and description. */
  function helpGroup(id) {
    return (
      shortcuts
        .snapshot("help", { includeInactive: true })
        .find((group) => group.id === id)
        ?.commands.map((command) => [
          command.bindings.visible.join(" or "),
          command.copy.action,
          command.copy.description,
        ]) ?? null
    );
  }

  /** A filter dropdown's trigger. */
  const trigger = (key) => filterBar.querySelector(`[data-chip-menu-toggle="${key}"]`);

  /** The words on Group by's closed trigger. */
  const groupTrigger = () =>
    filterBar.querySelector('[data-chip-menu-toggle="group"]')?.textContent.trim() ?? null;

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

  /** The main tabs in the order the bar draws them. */
  const tabOrder = () => navBar.querySelectorAll(".tab-btn").map((tab) => labelOf(tab));

  return {
    ancillary,
    build,
    clock,
    discoverGit,
    document,
    helpDigits,
    get kbdCreated() {
      return kbdCreated;
    },
    location,
    mainTabs,
    navCollapse,
    nav,
    slide,
    slideTo,
    finishSlides,
    get filterOpenMenu() {
      return filterOpenMenu;
    },
    measure,
    menuFocus,
    drawerOpen,
    filterFocus,
    groupTrigger,
    helpGroup,
    trigger,
    mountSelector,
    open,
    openCommit,
    openPullPage,
    pointer,
    press,
    record,
    renderFilters,
    rows,
    shellCommands,
    shellKeys,
    shiftDown,
    shiftUp,
    stack,
    stage,
    tabOrder,
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

/**
 * A repository with a hosted origin, its Pulls tab in front on pull request 7, which is in
 * a stack: where Control-N and Control-P walk.
 */
async function stackedPullPage() {
  const hosted = createPage({
    repository: recording.repository.repo.body.is_repo,
    tabs: ["files", "pulls"],
  });
  hosted.renderFilters();
  hosted.open(files[""]);
  hosted.build();
  hosted.discoverGit();
  hosted.mainTabs.open("pulls");
  await settle();
  hosted.location.pathname = "/pull/7";
  hosted.openPullPage(7);
  hosted.stack.inStack = true;
  hosted.record("the stacked pull request is open"); // takes what opening it did
  return hosted;
}

/**
 * Enter one place focus can be and press every key there with each chord, as the
 * `modified` part records it: what each chord took, what that did, and where focus went.
 */
function pressChords(page, place, enter, keys, chords) {
  page.document.body.focus();
  enter();
  page.record(place); // takes what entering did, so `did` below is the chords' own
  const where = () =>
    page.document.activeElement === page.document.body
      ? "body"
      : describe(page.document.activeElement);
  const focus = where();
  let presses = 0;
  const taken = [];
  for (const [chord, init] of Object.entries(chords)) {
    for (const name of keys) {
      if (chord === "Option" && name === "Tab") {
        continue;
      }
      presses += 1;
      if (page.press(name, init)) {
        taken.push(`${chord}-${name === " " ? "Space" : name}`);
      }
    }
  }
  const after = page.record(place);
  const focusAfter = where();
  page.press("Escape");
  return {
    place,
    focus,
    presses,
    commandR: taken.includes("Command-r") ? "taken" : "left to the browser",
    taken,
    did: after.did ?? [],
    focusMoved: focusAfter === focus ? null : focusAfter,
  };
}

// The session's parts, each its own command in the golden, so no transcript block grows
// past what tryscript can match: the keymap of a folder's files, the gesture, the main
// tabs with the pull request stack and a mirror's pin, and the chords left to the browser.
// The first three print the shell keys they registered (tests/test_keymap.py reads them).
const PARTS = {
  /** A plain folder: Files only, every multi-view kind, and the view tab letters. */
  async keymap() {
    const steps = [];
    const plain = plainPage();
    steps.push(plain.record("a plain folder shows Files only"));
    // The trigger's own path opens the menu, and focus goes to its checked row, so the
    // menu's arrow keys work next; Escape closes it through the same path.
    // The filters are situational, numbered by their place after the navigation's Refresh,
    // which is 1 in the header above them: Group by is 2 on the row, Any age 3 and Any type
    // 4, on stand-ins beside the chevron while the drawer is closed. A filter's number opens
    // the drawer with its menu.
    const drawerBefore = plain.drawerOpen();
    steps.push(
      plain.record(
        "4 opens the closed drawer and the file type filter, and focuses its checked row",
        {
          drawerBefore,
          pressed: { key: "4", handled: plain.press("4") },
          drawerAfter: plain.drawerOpen(),
          focus: plain.menuFocus(),
        },
      ),
    );
    plain.press("ArrowDown");
    const next = plain.menuFocus();
    // A pick in the multi-select menu renders the bar again and leaves the menu open:
    // focus stays on the row picked, so the next key still works.
    plain.document.activeElement.click();
    const picked = plain.filterFocus();
    // So does any other rebuild while a row has focus, as a tally refresh is.
    plain.renderFilters();
    const rebuilt = plain.filterFocus();
    plain.press("Escape");
    const escaped = plain.filterFocus();
    plain.document.body.focus();
    steps.push(
      plain.record(
        "↓ moves to the next row, a pick or a rebuild keeps focus there, and Escape closes the menu onto its trigger",
        { next, picked, rebuilt, escaped },
      ),
    );

    // Every way a dropdown opens puts focus in it the same way, through the filter
    // controls' one path: a number, a trigger's click (Enter and Space click it), and ↓ on
    // the trigger; Escape, a second click, and a choice that closes it give focus back to
    // the trigger (docs/design-system.md, "Keys in a Menu").
    plain.press("3");
    const byNumber = plain.filterFocus();
    plain.press("Escape");
    const byNumberEscaped = plain.filterFocus();
    plain.trigger("group").focus();
    plain.press("ArrowDown");
    const byArrow = plain.filterFocus();
    plain.press("Escape");
    const byArrowEscaped = plain.filterFocus();
    plain.trigger("group").click();
    const byClick = plain.filterFocus();
    plain.trigger("group").click();
    const byClickClosed = plain.filterFocus();
    plain.document.body.focus();
    steps.push(
      plain.record(
        "each way a menu opens focuses its checked row, and each way it closes its trigger",
        {
          byNumber,
          byNumberEscaped,
          byArrow,
          byArrowEscaped,
          byClick,
          byClickClosed,
        },
      ),
    );

    // Group by's rows take the letters they declare, N, A, and T, while its menu is open
    // and has focus, and Help lists them under Menus (docs/design-system.md, "Keys in a
    // Menu"). Each runs the row's click path.
    steps.push(
      plain.record("Help lists Group by's letters under Menus", {
        menus: plain.helpGroup("menus"),
      }),
    );
    plain.press("2");
    steps.push(
      plain.record("2 opens Group by and focuses its checked row, whose letters are live", {
        focus: plain.filterFocus(),
      }),
    );
    revealOn(plain);
    steps.push(plain.record("Shift held in the open menu badges its rows' letters"));
    plain.shiftUp();
    const chooseAge = { key: "a", handled: plain.press("a") };
    steps.push(
      plain.record("A chooses By age and closes the menu", {
        pressed: chooseAge,
        trigger: plain.groupTrigger(),
        focus: plain.filterFocus(),
      }),
    );
    plain.document.body.focus();
    const closedT = { key: "t", handled: plain.press("t") };
    steps.push(
      plain.record("with the menu closed, T is Quick Search", {
        pressed: closedT,
        focus: plain.document.activeElement.getAttribute("role"),
      }),
    );
    plain.press("Escape");
    plain.press("2");
    const checkedAge = plain.filterFocus();
    const chooseType = { key: "t", handled: plain.press("t") };
    steps.push(
      plain.record("2 focuses By age, the checked row, and T chooses By file type", {
        focus: checkedAge,
        pressed: chooseType,
        trigger: plain.groupTrigger(),
      }),
    );
    // Focus gone from the open menu to nothing, as when its focused row is removed: its
    // letters wait, and T is Quick Search's, whose box taking focus closes the menu
    // (docs/design-system.md, "Every Menu Closes Alike").
    plain.press("2");
    plain.document.activeElement.blur();
    const outsideT = { key: "t", handled: plain.press("t") };
    steps.push(
      plain.record("with focus outside the open menu, T is Quick Search, which closes it", {
        pressed: outsideT,
        focus: plain.document.activeElement.getAttribute("role"),
        trigger: plain.groupTrigger(),
      }),
    );
    plain.press("Escape");
    plain.press("2");
    const chooseNone = { key: "n", handled: plain.press("n") };
    plain.document.body.focus();
    steps.push(
      plain.record("N chooses No grouping", { pressed: chooseNone, trigger: plain.groupTrigger() }),
    );

    plain.open(files["README.md"]);
    steps.push(
      plain.record("a Markdown file has Document and Source", {
        pressed: { key: "s", handled: plain.press("S", { shiftKey: true }) },
      }),
    );
    // The letters both bars declare keep their commands and move to the new tabs, so a
    // move between two files of one kind registers nothing, and the resting strip, which
    // follows registrations, is not rebuilt; nothing reads a target at rest.
    steps.push(
      plain.record("a move between two files of one kind registers nothing", {
        cost: plain.measure(() => plain.open(files["README.md"])),
      }),
    );

    steps.push(
      plain.record("copying is ancillary: the Copy path button has no key, and Y does nothing", {
        pressed: { key: "y", handled: plain.press("y") },
        ancillary: plain.ancillary(),
      }),
    );
    plain.open(files.docs);
    steps.push(plain.record("a folder below the root has Up"));
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

    // `0` is Home on any screen, with Shift too: US Shift-0 types `)`, which the registry
    // matches by its digit-row key, as it does Shift with a number.
    plain.open(files["data.json"]);
    steps.push(
      plain.record("0 goes home, through the folder's name's own path", {
        pressed: { key: "0", handled: plain.press("0", { code: "Digit0" }) },
      }),
    );
    steps.push(
      plain.record("Shift-0, which types ) on a US keyboard, goes home too", {
        pressed: {
          key: ")",
          handled: plain.press(")", { code: "Digit0", shiftKey: true }),
        },
      }),
    );

    plain.open(files["session.jsonl"]);
    steps.push(plain.record("an agent log has Log, Charts, and Raw JSON"));

    // The view tab letters follow the committed bar, and a stage that is cancelled before
    // it commits registers nothing, so the bar on screen keeps its keys. V is each kind's
    // rendered view, under its own label: Tree for structured data, Log for an agent log.
    plain.open(files["data.json"]);
    const treeV = plain.shortcuts.liveTarget("view-tabs.v");
    plain.open(files["session.jsonl"]);
    const logV = plain.shortcuts.liveTarget("view-tabs.v");
    plain.open(files["data.json"]);
    const cancelled = plain.stage(files["session.jsonl"]);
    const whileStaged = plain.shortcuts.liveTarget("view-tabs.v");
    cancelled.cancel();
    steps.push(
      plain.record("V follows the committed bar, and a cancelled stage changes nothing", {
        v: {
          structured: treeV?.textContent,
          agentLog: logV?.textContent,
          back: plain.shortcuts.liveTarget("view-tabs.v")?.textContent,
          whileStaged: whileStaged?.textContent,
          afterCancel: plain.shortcuts.liveTarget("view-tabs.v")?.textContent,
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
    // A navigation while revealed changes many targets inside one batch, and the badges
    // follow once, as it ends: one liveness read per target, and one publication.
    steps.push(
      plain.record("a navigation while revealed moves the badges in one pass", {
        cost: plain.measure(() => plain.open(files["data.json"])),
      }),
    );
    plain.open(files["README.md"]);
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

    // A press that moves focus is still a press until it ends: the element losing focus
    // hears `blur`, and Shift pressed before the pointer comes up never arms.
    plain.rows[0].focus();
    plain.pointer("pointerdown", 40, 20);
    plain.rows[2].focus();
    plain.shiftDown();
    plain.clock.advance(HOLD_MS);
    steps.push(
      plain.record("Shift during a press that moved focus never reveals", {
        focusedRow: plain.document.activeElement.dataset.path,
      }),
    );
    plain.pointer("pointerup", 40, 20);
    plain.shiftUp();

    // Tree keys keep the reveal; a repeat does no reveal work.
    plain.rows[1].focus();
    revealOn(plain);
    let up = false;
    const upCost = plain.measure(() => {
      up = plain.key("keydown", "ArrowUp", { shiftKey: true });
    });
    steps.push(
      plain.record("↑ on a tree row moves one row and keeps the reveal", {
        pressed: { key: "ArrowUp", handled: up },
        focusedRow: plain.document.activeElement.dataset.path,
        cost: upCost,
      }),
    );
    plain.key("keydown", "j", { shiftKey: true });
    const repeats = plain.measure(() => {
      plain.key("keydown", "j", { repeat: true, shiftKey: true });
      plain.key("keydown", "j", { repeat: true, shiftKey: true });
    });
    steps.push(
      plain.record("a held J moves rows and does no reveal work on its repeats", {
        focusedRow: plain.document.activeElement.dataset.path,
        repeats,
      }),
    );
    plain.window.loseFocus();
    steps.push(plain.record("the window losing focus ends the reveal"));
    plain.window.regainFocus();
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

  /**
   * Hiding the navigation pane: `\` and Shift-\ from the main page and from a tree row,
   * through the production static/nav-collapse.js. tests/dom/nav-collapse-session.js runs
   * it, and cli-ui-nav-collapse.tryscript.md pins it.
   */
  async nav() {
    const steps = [];
    const page = plainPage();
    page.open(files["data.json"]);
    steps.push(page.record("a file is open with the navigation pane shown", { nav: page.nav() }));
    // `\` hides the navigation pane from anywhere, through the chevron's own path. Hidden,
    // the pane is inert, so its keys leave the live keymap and focus on one of its rows
    // goes to the main page; `\` stays live on the chevron, which the main frame holds. The
    // frame slides over the pane for --motion-reveal's time, read from styles.css.
    page.document.querySelector(".tree-item")?.focus();
    const hide = { key: "\\", handled: page.press("\\", { code: "Backslash" }) };
    const hiding = page.slide();
    await page.finishSlides();
    steps.push(
      page.record("\\ hides the navigation pane, and only the main page's keys stay live", {
        pressed: hide,
        slide: hiding,
        // Focus was on a tree row, which the inert pane cannot hold: the main page takes it.
        nav: { ...page.nav(), focus: page.document.activeElement.id },
      }),
    );
    // Shift-\ types | on a US keyboard, and | is \'s Shift form, so it shows the pane
    // again. The pane is live as the slide starts and takes its place in the layout when
    // the slide ends.
    const show = {
      key: "|",
      handled: page.press("|", { code: "Backslash", shiftKey: true }),
    };
    const showing = { slide: page.slide(), nav: page.nav() };
    await page.finishSlides();
    steps.push(
      page.record("Shift-\\, which types | on a US keyboard, shows it again", {
        pressed: show,
        sliding: showing,
        nav: page.nav(),
      }),
    );
    // The same physical key is # on a UK or German keyboard: a key is its character, so
    // that is not \.
    steps.push(
      page.record("# on the key US keyboards have \\ on is not \\", {
        pressed: { key: "#", handled: page.press("#", { code: "Backslash" }) },
        slide: page.slide(),
        nav: page.nav(),
      }),
    );
    // A second `\` mid-slide turns the frame back from where it is, for the share of the
    // time that distance is, and leaves the pane shown, live, and in the layout.
    page.press("\\", { code: "Backslash" });
    page.slideTo(0.5);
    const back = { key: "\\", handled: page.press("\\", { code: "Backslash" }) };
    const turned = page.slide();
    await page.finishSlides();
    steps.push(
      page.record("\\ again halfway through the slide turns it back from there", {
        pressed: back,
        slide: turned,
        nav: page.nav(),
      }),
    );
    // A menu the pane holds would stay open under the frame with its trigger inert, so
    // hiding the pane closes it.
    page.press("2");
    const opened = page.filterOpenMenu;
    const closing = { key: "\\", handled: page.press("\\", { code: "Backslash" }) };
    await page.finishSlides();
    steps.push(
      page.record("\\ with Group by open closes the menu as it hides the pane", {
        pressed: closing,
        menu: { before: opened, after: page.filterOpenMenu },
        nav: { ...page.nav(), focus: page.document.activeElement.id },
      }),
    );

    return { steps, pages: [page] };
  },

  /**
   * Command, Control, and Option chords are the browser's (mb-i1wy): Command-R reloads
   * wherever focus is, and so does every other chord. Each place focus can be is entered
   * once, and every letter, digit, and named key is pressed there with each chord; none
   * may be taken (`preventDefault`), run a command, or move focus. Option-Tab is the one
   * exception, and is not pressed: a modal's focus trap keeps it, since Safari moves focus
   * with it. Control-N and Control-P are the registry's two Control chords (mb-lnqj): on
   * a pull request in a stack they walk the stack and are the only chords taken, and a
   * text field keeps them there too.
   */
  async modified() {
    const page = plainPage();
    const stacked = await stackedPullPage();
    const keys = [
      ..."abcdefghijklmnopqrstuvwxyz123456789?/",
      ...["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"],
      ...["Enter", " ", "Escape", "Tab", "Backspace"],
    ];
    const chords = {
      Command: { metaKey: true },
      "Shift-Command": { metaKey: true, shiftKey: true },
      Control: { ctrlKey: true },
      Option: { altKey: true },
    };
    const walked = ["moved toward the stack's top", "moved toward its base"];
    // Each place: its page, how focus gets there, and the chords it takes with what they did.
    const places = [
      ["the page", page, () => page.document.body.focus()],
      ["a tree row", page, () => page.rows[0].focus()],
      ["Quick Search's field", page, () => page.press("t")],
      ["Help", page, () => page.press("?", { shiftKey: true })],
      ["the file type filter's open menu", page, () => page.press("4")],
      ["the Group by menu, whose rows have letters", page, () => page.press("2")],
      [
        "a pull request in a stack",
        stacked,
        () => stacked.document.body.focus(),
        { taken: ["Control-n", "Control-p"], did: walked },
      ],
      ["Quick Search's field on a pull request in a stack", stacked, () => stacked.press("t")],
    ];
    const steps = [];
    const failed = [];
    for (const [place, at, enter, expected = { taken: [], did: [] }] of places) {
      const step = pressChords(at, place, enter, keys, chords);
      steps.push(step);
      if (
        JSON.stringify(step.taken) !== JSON.stringify(expected.taken) ||
        JSON.stringify(step.did) !== JSON.stringify(expected.did) ||
        step.focusMoved
      ) {
        failed.push(step);
      }
    }
    if (failed.length > 0) {
      throw new Error(`a page key took a chord: ${JSON.stringify(failed, null, 2)}`);
    }
    return { steps, pages: [page, stacked], chords: Object.keys(chords), keys: keys.length };
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

    // From a Files row, so the letter moves focus from one element to another.
    repo.rows[0].focus();
    revealOn(repo);
    const history = repo.press("H", { shiftKey: true });
    steps.push(
      repo.record("H with Shift still held opens Commits, focuses its row, and keeps the reveal", {
        pressed: { key: "h", handled: history },
        active: repo.mainTabs.active(),
        focus: repo.document.activeElement.textContent,
      }),
    );
    const toFiles = repo.press("F", { shiftKey: true });
    steps.push(
      repo.record(
        "F during the reveal shows the filter bar, and Group by and its filters gain 2 to 4",
        {
          pressed: { key: "f", handled: toFiles },
          active: repo.mainTabs.active(),
          focus:
            repo.document.activeElement.dataset.path ?? repo.document.activeElement.textContent,
        },
      ),
    );
    repo.shiftUp();
    steps.push(repo.record("releasing Shift ends the reveal"));

    repo.press("h");
    repo.document.querySelector("#tab-git .git-graph-row").focus();
    revealOn(repo);
    repo.key("keydown", "j", { shiftKey: true });
    steps.push(repo.record("J on a commit row ends the reveal, since the row handles it itself"));
    repo.key("keyup", "j");
    repo.shiftUp();

    repo.openCommit();
    steps.push(
      repo.record("a commit view's Copy revision is ancillary and has no key", {
        pressed: { key: "y", handled: repo.press("y") },
        ancillary: repo.ancillary(),
      }),
    );
    repo.press("f");
    await settle();

    // ── A panel registered while the registry is down ────────────
    // Git discovery can finish between a real pagehide, which disposes the registry, and
    // the pageshow that rebuilds it. The tab and its container appear then anyway, and the
    // rebuild makes the tab its letter's target.
    const late = createPage({ repository: recording.repository.repo.body.is_repo });
    late.renderFilters();
    late.open(files[""]);
    late.build();
    late.teardown();
    let threw = null;
    try {
      late.discoverGit();
    } catch (error) {
      threw = error.message;
    }
    const commitsTab = () => late.document.querySelector('.nav-tab-bar .tab-btn[data-tab="git"]');
    const whileDown = {
      threw,
      tab: commitsTab() !== null,
      container: late.document.getElementById("tab-git") !== null,
      key: commitsTab()?.getAttribute("aria-keyshortcuts") ?? null,
    };
    late.build();
    steps.push(
      late.record("Commits registered while the registry is down gets its tab, then its key", {
        whileDown,
        key: commitsTab()?.getAttribute("aria-keyshortcuts") ?? null,
        pressed: { key: "h", handled: late.press("h") },
        active: late.mainTabs.active(),
      }),
    );
    late.press("f");
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
      hosted.record("Pulls drawn before Commits has P, and H does nothing until Commits comes", {
        pressed: { key: "h", handled: hosted.press("h") },
        tabs: hosted.tabOrder(),
      }),
    );
    hosted.discoverGit();
    steps.push(
      hosted.record("a repository with a hosted origin shows Files, Pulls, and Commits", {
        tabs: hosted.tabOrder(),
      }),
    );

    // V is the rendered view everywhere, and Control-P, "previous", does nothing outside a
    // pull request stack.
    hosted.open(files["page.html"]);
    steps.push(
      hosted.record("the Preview tab is V, and Control-P outside a stack does nothing", {
        pressed: { key: "v", handled: hosted.press("v") },
        controlP: hosted.press("p", { ctrlKey: true }),
      }),
    );

    // P is the Pulls tab (mb-6rfu); the stack's walk is Control-N and Control-P.
    const toPulls = hosted.press("p");
    await settle();
    steps.push(
      hosted.record("P opens the Pulls tab from a file", {
        pressed: { key: "p", handled: toPulls },
        active: hosted.mainTabs.active(),
      }),
    );
    steps.push(
      hosted.record("P again, once the list has rows, moves focus to the selected row", {
        pressed: { key: "p", handled: hosted.press("p") },
        focus: hosted.document.activeElement.textContent,
      }),
    );
    hosted.location.pathname = "/pull/7";
    hosted.openPullPage(7);
    steps.push(
      hosted.record("a pull request outside a stack has no Control-N or Control-P", {
        focus: hosted.document.activeElement.textContent,
        pressed: { key: "Control-n", handled: hosted.press("n", { ctrlKey: true }) },
      }),
    );
    hosted.stack.inStack = true;
    hosted.document.body.focus();
    revealOn(hosted);
    steps.push(
      hosted.record("a pull request in a stack lists Control-N or Control-P on the strip"),
    );
    // A chord ends the reveal, as any modifier does, and still walks the stack: Shift
    // changes nothing.
    steps.push(
      hosted.record("Control-N with Shift held walks the stack and ends the reveal", {
        pressed: {
          key: "Control-n",
          handled: hosted.press("N", { ctrlKey: true, shiftKey: true }),
        },
      }),
    );
    hosted.shiftUp();
    steps.push(
      hosted.record("Control-P walks the stack toward its base", {
        pressed: { key: "Control-p", handled: hosted.press("p", { ctrlKey: true }) },
      }),
    );
    // N alone is free, AltGr, which reports Control and Alt, types its character rather
    // than walking, and P alone is the Pulls tab's, which is in front, so it moves focus
    // to the list and walks nothing.
    hosted.document.body.focus();
    const alone = {
      n: hosted.press("n"),
      altGr: hosted.press("n", { altKey: true, ctrlKey: true }),
    };
    steps.push(
      hosted.record("N alone and Control-Alt-N walk nothing, and P alone is the Pulls tab", {
        ...alone,
        p: {
          handled: hosted.press("p"),
          active: hosted.mainTabs.active(),
          focus: hosted.document.activeElement.textContent,
        },
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
      pinned.record("a mirror's pin has W, Group by is 2, and its one filter is 3", {
        pressed: { key: "w", handled: pinned.press("w") },
        four: pinned.press("4"),
      }),
    );
    pinned.press("Escape");
    pinned.document.body.focus();
    revealOn(pinned);
    steps.push(
      pinned.record("Help lists the numbers once, as positional", {
        helpDigits: pinned.helpDigits(),
        // A pin has no By age, so Group by's letters are N and T (app.js,
        // filterGroupOptions).
        menus: pinned.helpGroup("menus"),
      }),
    );
    pinned.shiftUp();

    return { steps, pages: [repo, late, hosted, pinned] };
  },
};

/** Run one part and print its transcript: the command line's, or the one a caller names. */
async function main(part = process.argv[2] ?? "keymap") {
  if (!Object.hasOwn(PARTS, part)) {
    throw new Error(`Unknown part ${part}; the parts are ${Object.keys(PARTS).join(", ")}`);
  }
  const { steps, pages, chords, keys } = await PARTS[part]();
  // The keymap's parts print the shell keys they registered; these register the same
  // keymap and print only what their keys did.
  if (part === "modified") {
    process.stdout.write(`${render({ part, chords, keys, steps })}\n`);
    return;
  }
  if (part === "nav") {
    process.stdout.write(`${render({ part, steps })}\n`);
    return;
  }
  const shellKeys = new Set(pages.flatMap((page) => [...page.shellKeys]));
  const shellCommands = new Set(pages.flatMap((page) => [...page.shellCommands]));
  process.stdout.write(
    `${render({ part, steps, shellKeys: [...shellKeys].sort(), shellCommands: [...shellCommands].sort() })}\n`,
  );
}

// tests/dom/nav-collapse-session.js runs the `nav` part as a session of its own.
if (require.main === module) {
  main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
module.exports = { main };
