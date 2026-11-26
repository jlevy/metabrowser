// Exact browserless session for the view tabs of a file the pane is still bringing up.
//
// The shell stages a file out of sight, with its tab bar, and holds the first paint
// until the view in front has its data (renderFile in app.js). A tab chosen meanwhile
// has to win: by a click on the staged bar, by name (showPreviewTab, which a second
// navigation to the file's address runs), or on the bar the reader sees while the same
// file is staged again, as Load more does. The commit used to put the first view in
// front whatever was chosen, and the chosen view never mounted (mb-s588).
//
// What decides this is production code: the compositor's tab functions (bindTabs,
// selectTab, setActiveView and stagedFile in view-composition.js), run from the whole
// file, and the app.js functions that order them, renderFile and showPreviewTab with
// their helpers, extracted verbatim, over the production view state (view-state.js) and
// pane lifecycle (navigation.js). The DOM is the stand-in in key-reveal-dom.js, which
// parses the markup renderFile writes. The renderers, the view header, the performance
// probe and the shell services renderFile only notifies are doubles. Nothing here
// restates the order the production code runs in.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const { FakeDocument, FakeElement, element } = require("./key-reveal-dom.js");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");

/** One app.js declaration, bounded by its closing line at column zero. */
function appDeclaration(pattern, label) {
  const match = appSource.match(pattern);
  if (!match) {
    throw new Error(`app.js ${label} is not extractable`);
  }
  return match[0];
}

const SHELL_FUNCTIONS = [
  "esc",
  "queryHtml",
  "queryHtmlAll",
  "filePerfMeta",
  "boolData",
  "viewIsPrintable",
  "viewPrintProfile",
  "viewRenderRuntime",
  "viewMetaAttrs",
  "isPreviewClaimCurrent",
  "cancelPendingFilePreviewStage",
  "createFilePreviewStage",
  "renderFile",
  "takeAwaitedPreviewView",
  "showPreviewTab",
  "selectPreviewTab",
];

const shellSource = [
  appDeclaration(/^var previewPane = [^\n]*;$/m, "preview pane"),
  appDeclaration(/^var pendingFilePreviewStageCleanup = null;$/m, "pending stage cleanup"),
  appDeclaration(/^var filePreviewClaim = null;$/m, "file preview claim"),
  appDeclaration(/^var awaitedPreviewView = null;$/m, "awaited view"),
  appDeclaration(/^var shellKeymap = null;$/m, "shell keymap"),
  ...SHELL_FUNCTIONS.map((name) =>
    appDeclaration(
      new RegExp(`^(?:async )?function ${name}\\([^)]*\\) \\{[\\s\\S]*?^\\}`, "m"),
      `function ${name}`,
    ),
  ),
].join("\n\n");

/** Let every pending promise chain in the shell run to completion. */
async function settle() {
  for (let round = 0; round < 10; round += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

const VIEWS = [
  { id: "overview", label: "Overview", default: true, key: "O" },
  { id: "treemap", label: "Treemap", key: "T" },
];

/** A folder's envelope, with the two views a plain folder has. */
function folder(folderPath) {
  return { kind: "folder", path: folderPath, views: VIEWS };
}

/**
 * A shell with an empty preview pane. Each view's renderer counts its mounts, and the
 * Overview's holds the first paint until `release()` when `hold` says so.
 */
function createShell() {
  const document = new FakeDocument();
  const preview = element(document, "div", { class: "preview-pane", id: "preview-pane" });
  document.body.append(preview);

  /** @type {Record<string, number>} */
  const mounts = {};
  /** The Overview's readiness, one per held mount. @type {Array<() => void>} */
  const holds = [];
  let hold = true;
  let releaseRefresh;
  const renderer = (viewId) => ({
    render(container) {
      mounts[viewId] = (mounts[viewId] ?? 0) + 1;
      container.textContent = `${viewId} of ${container.closest("[data-rendered-path]")?.dataset.renderedPath}`;
      if (viewId === "treemap") {
        return {
          async refresh(context) {
            await new Promise((resolve) => {
              releaseRefresh = resolve;
            });
            container.textContent = context.raw.content;
            return true;
          },
        };
      }
      if (!hold) {
        return undefined;
      }
      return { ready: new Promise((resolve) => holds.push(() => resolve(undefined))) };
    },
  });
  const renderers = { overview: renderer("overview"), treemap: renderer("treemap") };

  const sandbox = {
    Array,
    Error,
    HTMLElement: FakeElement,
    Element: FakeElement,
    Map,
    Object,
    Promise,
    Set,
    TypeError,
    clearTimeout,
    console,
    document,
    setTimeout,
    // The probe runs what it measures and keeps nothing.
    _perf: {
      measure: (_label, run) => run(),
      measureAsync: (_label, run) => run(),
    },
    measureNextPaint: async () => {},
    scheduleHighlightCode() {},
    animatePreviewContentArrival() {},
    startFolderHeaderSubscription() {},
    stopFolderHeaderSubscription() {},
    finishRetainedPullPage() {},
    // view-header.js's builders, which draw the header over the bar and decide nothing
    // about the tabs.
    viewHeaderBuilders: () => ({
      renderFolderHeader: (data) => `<div class="view-header folder-header">${data.path}</div>`,
      renderFileHeader: (data) => `<div class="view-header">${data.path}</div>`,
    }),
    metabrowser: {
      ensureKindAssets: async () => {},
      fetchPluginData: null,
      folderContext: { seed() {} },
      getRegisteredView: (_kind, viewId) => renderers[viewId] ?? null,
    },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  for (const script of ["navigation.js", "view-state.js", "view-composition.js"]) {
    const scriptPath = path.join(staticDir, script);
    vm.runInContext(fs.readFileSync(scriptPath, "utf8"), sandbox, { filename: scriptPath });
  }
  vm.runInContext(shellSource, sandbox, { filename: path.join(staticDir, "app.js") });
  const composition = sandbox.MetabrowserViewComposition;
  const viewComposition = Promise.resolve({
    status: "ready",
    value: Object.freeze({
      composition,
      lifecycle: composition.createLifecycle({ onDisposeError() {} }),
    }),
  });

  /**
   * A tab bar's state. The tab marked in front, the tab selected, the content shown, the
   * content marked active and the view the host names are one view when the bar is
   * whole, and then this is one line; where they differ, each is reported.
   */
  function barState(host) {
    if (!host) {
      return null;
    }
    const ids = (selector, read) => host.querySelectorAll(selector).map(read).join(",");
    const tab = ids(":scope > .tab-bar > .tab-btn.active", (button) => button.dataset.tab);
    // The stand-in keeps an element's `style` attribute and its style object apart: the
    // markup hides a view with the first and a tab switch writes the second.
    const shown = host
      .querySelectorAll(":scope > [data-tab-content]")
      .filter((content) =>
        content.style.properties.has("display")
          ? content.style.display !== "none"
          : !/display:none/.test(content.getAttribute("style") ?? ""),
      )
      .map((content) => content.dataset.tabContent)
      .join(",");
    const parts = {
      tab,
      selected: ids(
        ':scope > .tab-bar > .tab-btn[aria-selected="true"]',
        (button) => button.dataset.tab,
      ),
      shown,
      active: ids(
        ':scope > [data-tab-content][data-active-view="true"]',
        (content) => content.dataset.tabContent,
      ),
      hostActiveView: host.dataset.activeView ?? "",
    };
    const whole = Object.values(parts).every((value) => value === tab) && tab !== "";
    return whole
      ? `${host.dataset.renderedPath} in ${tab}`
      : { path: host.dataset.renderedPath, ...parts };
  }

  const stage = () => preview.querySelector(":scope > .preview-file-stage");

  return {
    /** Select a file as selectFile does, as far as the pane's claim. */
    claim(filePath) {
      const claim = sandbox.previewPane.claim("file", { folder: true, path: filePath });
      vm.runInContext(`filePreviewClaim = ${claim}; awaitedPreviewView = null;`, sandbox);
      return claim;
    },
    /** Begin the render of a claimed file; resolves as renderFile does. */
    render(data, claim, preferredViewId, refreshMounted = false) {
      return sandbox.renderFile(data, preferredViewId, claim, { viewComposition, refreshMounted });
    },
    releaseRefresh: () => releaseRefresh(),
    mountedView: () => preview.querySelector(':scope > [data-active-view="true"]'),
    /** The selection settled with content, as openedFileOutcome records it. */
    opened(claim) {
      sandbox.previewPane.settle(claim, "content");
    },
    holdFirstPaint(on) {
      hold = on;
    },
    /** Give the held Overview its data. */
    async release() {
      for (const resolve of holds.splice(0)) {
        resolve();
      }
      await settle();
    },
    /** A click on a tab: the staged bar's, out of sight, or the bar the pane shows. */
    click(where, tabId) {
      const host = where === "staged" ? stage() : preview;
      host.querySelector(`:scope > .tab-bar > .tab-btn[data-tab="${tabId}"]`).click();
    },
    name(filePath, tabId) {
      sandbox.showPreviewTab(filePath, tabId);
    },
    state() {
      const staged = stage();
      return {
        // Staged content is out of sight and inert until its commit.
        staged: staged ? (staged.inert ? barState(staged) : "a stage that is not inert") : null,
        pane: preview.dataset.renderedPath === undefined ? null : barState(preview),
        mounts: Object.entries(mounts)
          .map(([viewId, count]) => `${viewId} ${count}`)
          .join(", "),
      };
    },
  };
}

/** Open one folder and stop at the hold: the stage is drawn and the Overview waits. */
async function openHeld(shell, folderPath = "src") {
  const claim = shell.claim(folderPath);
  const rendered = shell.render(folder(folderPath), claim);
  await settle();
  return { claim, rendered };
}

/** Let the held file commit, and report it. */
async function commit(shell, opening) {
  await shell.release();
  const committed = await opening.rendered;
  shell.opened(opening.claim);
  return { committed, ...shell.state() };
}

// ── Scenarios ─────────────────────────────────────────────────

async function noChoice() {
  const shell = createShell();
  const opening = await openHeld(shell);
  const held = shell.state();
  return { held, after: await commit(shell, opening) };
}

async function clickDuringHold() {
  const shell = createShell();
  const opening = await openHeld(shell);
  shell.click("staged", "treemap");
  await settle();
  const held = shell.state();
  const after = await commit(shell, opening);
  // The first view is still there to go back to, mounted once.
  shell.click("pane", "overview");
  await settle();
  return { held, after, backToOverview: shell.state() };
}

async function namedDuringHold() {
  const shell = createShell();
  const opening = await openHeld(shell);
  shell.name("src", "treemap");
  await settle();
  const held = shell.state();
  return { held, after: await commit(shell, opening) };
}

async function namedBeforeTheStage() {
  const shell = createShell();
  // The file is selected and its envelope has not arrived: there is no bar yet.
  const claim = shell.claim("src");
  shell.name("src", "treemap");
  const before = shell.state();
  shell.holdFirstPaint(false);
  const committed = await shell.render(folder("src"), claim);
  shell.opened(claim);
  return { before, after: { committed, ...shell.state() } };
}

async function namedForAnotherFile() {
  const shell = createShell();
  // A view named for a file the pane is not loading is kept for no later render.
  const claim = shell.claim("src");
  shell.name("docs", "treemap");
  shell.holdFirstPaint(false);
  const committed = await shell.render(folder("src"), claim);
  shell.opened(claim);
  return { committed, ...shell.state() };
}

async function choiceWhileStagedAgain() {
  const shell = createShell();
  shell.holdFirstPaint(false);
  const first = shell.claim("src");
  await shell.render(folder("src"), first);
  shell.opened(first);
  const shown = shell.state();
  // The same file renders again in the tab in front, as Load more's render does, and
  // holds; the reader picks the other tab on the bar they see.
  shell.holdFirstPaint(true);
  const again = shell.render(folder("src"), first, "overview");
  await settle();
  shell.click("pane", "treemap");
  await settle();
  const held = shell.state();
  await shell.release();
  const committed = await again;
  return { shown, held, after: { committed, ...shell.state() } };
}

async function choiceWhileAnotherFileIsStaged() {
  const shell = createShell();
  shell.holdFirstPaint(false);
  const first = shell.claim("src");
  await shell.render(folder("src"), first);
  shell.opened(first);
  // Another folder is on its way; a tab picked on the one still shown is that one's.
  shell.holdFirstPaint(true);
  const opening = await openHeld(shell, "docs");
  shell.click("pane", "treemap");
  await settle();
  const held = shell.state();
  return { held, after: await commit(shell, opening) };
}

async function rereadMountedTreemap() {
  const shell = createShell();
  const first = shell.claim("src");
  await shell.render(folder("src"), first, "treemap");
  shell.opened(first);
  const before = shell.mountedView();
  const reread = shell.claim("src");
  const pending = shell.render(
    { ...folder("src"), content: "updated map" },
    reread,
    "treemap",
    true,
  );
  await settle();
  const held = shell.state();
  assert.equal(held.staged, null, "a reread does not stage an already mounted live view");
  assert.equal(shell.mountedView(), before, "the old map stays mounted while the request runs");
  const oldContent = before.textContent;
  shell.releaseRefresh();
  assert.equal(await pending, true);
  assert.equal(shell.mountedView(), before, "the same map receives the changed data");
  return { held, oldContent, newContent: before.textContent, after: shell.state() };
}

async function main() {
  const result = {
    noChoice: await noChoice(),
    clickDuringHold: await clickDuringHold(),
    namedDuringHold: await namedDuringHold(),
    namedBeforeTheStage: await namedBeforeTheStage(),
    namedForAnotherFile: await namedForAnotherFile(),
    choiceWhileStagedAgain: await choiceWhileStagedAgain(),
    choiceWhileAnotherFileIsStaged: await choiceWhileAnotherFileIsStaged(),
    rereadMountedTreemap: await rereadMountedTreemap(),
  };
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
