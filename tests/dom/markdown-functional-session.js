// Cohesive browserless transcript for Markdown catalog and lifecycle behavior.

const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createSdkSandbox } = require("./sdk-sandbox.js");

const repoRoot = path.resolve(__dirname, "../..");
const markdownRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");
const moduleUrl = (name) => pathToFileURL(path.join(markdownRoot, name)).href;

function knownFile(filePath) {
  return Object.freeze({
    basename: filePath.slice(filePath.lastIndexOf("/") + 1),
    path: filePath,
  });
}

function snapshot(paths, complete = true, truncated = false) {
  return Object.freeze({
    complete,
    files: Object.freeze([...paths].sort().map(knownFile)),
    revision: complete || truncated ? 2 : 1,
    truncated,
  });
}

function settle(application, maxPathVisits = 31) {
  let steps = 0;
  let pathVisits = 0;
  while (true) {
    const step = application.step(maxPathVisits);
    if (step.pathVisits > maxPathVisits) {
      throw new Error("wiki application exceeded its declared path budget");
    }
    steps += 1;
    pathVisits += step.pathVisits;
    if (step.done) {
      return { pathVisits, result: step.result, steps };
    }
  }
}

function scheduler() {
  let sequence = 0;
  const callbacks = new Map();
  return {
    callbacks,
    cancel(handle) {
      callbacks.delete(handle);
    },
    drain(limit = 1000) {
      let calls = 0;
      while (callbacks.size) {
        const [handle, callback] = callbacks.entries().next().value;
        callbacks.delete(handle);
        callback(0);
        calls += 1;
        if (calls > limit) {
          throw new Error("Markdown reconciliation did not settle");
        }
      }
      return calls;
    },
    runNext() {
      const [handle, callback] = callbacks.entries().next().value;
      callbacks.delete(handle);
      callback(0);
    },
    schedule(callback) {
      sequence += 1;
      callbacks.set(sequence, callback);
      return sequence;
    },
  };
}

class FakeElement {
  constructor(tagName, textContent = "") {
    this.attributes = new Map();
    this._innerHTML = "";
    this.elements = [];
    this.listeners = new Map();
    this.classList = { add() {} };
    this.ownerDocument = null;
    this.parentElement = null;
    this.tagName = tagName.toUpperCase();
    this.textContent = textContent;
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this.elements = parseFakeHtml(this._innerHTML, this.ownerDocument);
    for (const element of this.elements) {
      element.parentElement = this;
    }
  }

  matches(selector) {
    if (selector === "[data-mb-wiki-target]") {
      return this.hasAttribute("data-mb-wiki-target");
    }
    if (selector === "[id]") {
      return Boolean(this.id);
    }
    if (selector.includes(",")) {
      return selector.split(",").some((part) => this.matches(part.trim()));
    }
    const match = /^(\w+)\[([\w-]+)]$/.exec(selector);
    return Boolean(match && this.tagName === match[1].toUpperCase() && this.hasAttribute(match[2]));
  }

  querySelector() {
    return null;
  }

  querySelectorAll(selector) {
    const descendants = [];
    const visit = (element) => {
      if (element.matches(selector)) {
        descendants.push(element);
      }
      for (const child of element.elements) {
        visit(child);
      }
    };
    for (const element of this.elements) {
      visit(element);
    }
    return descendants;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  removeEventListener(name, listener) {
    if (this.listeners.get(name) === listener) {
      this.listeners.delete(name);
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name === "id") {
      this.id = String(value);
    }
  }

  replaceWith(replacement) {
    const index = this.parentElement.elements.indexOf(this);
    this.parentElement.elements[index] = replacement;
    replacement.parentElement = this.parentElement;
    this.parentElement = null;
  }
}

class FakeContainer extends FakeElement {
  constructor(element) {
    super("main");
    const document = {
      createElement: (tagName) => {
        const created = new FakeElement(tagName);
        created.ownerDocument = document;
        return created;
      },
    };
    this.ownerDocument = document;
    this.elements = Array.isArray(element) ? element : [element];
    for (const child of this.elements) {
      child.ownerDocument = document;
      child.parentElement = this;
    }
  }
}

function parseFakeHtml(html, document) {
  const elements = [];
  const pattern = /<(a|span)\b([^>]*)>(.*?)<\/\1>|<(img)\b([^>]*)>/g;
  for (const match of html.matchAll(pattern)) {
    const element = new FakeElement(match[1] || match[4], (match[3] || "").replace(/<[^>]*>/g, ""));
    element.ownerDocument = document;
    for (const attribute of (match[2] || match[5]).matchAll(/([\w-]+)="([^"]*)"/g)) {
      element.setAttribute(attribute[1], attribute[2]);
    }
    elements.push(element);
  }
  return elements;
}

// The page-hide event the shared Markdown Worker listens for while it is idle. Installed
// before any mount, so the Worker sections can end an earlier section's idle period.
const pagehideListeners = new Set();
globalThis.addEventListener = (type, listener) => {
  if (type === "pagehide") {
    pagehideListeners.add(listener);
  }
};
globalThis.removeEventListener = (type, listener) => {
  if (type === "pagehide") {
    pagehideListeners.delete(listener);
  }
};
function hidePage() {
  for (const listener of [...pagehideListeners]) {
    listener({ type: "pagehide", persisted: false });
  }
}

(async () => {
  const wiki = await import(moduleUrl("wiki-resolver.js"));
  const coordinatorModule = await import(moduleUrl("reconciliation-coordinator.js"));
  const adapters = await import(moduleUrl("project-adapters.js"));
  const renderedMarkdown = await import(moduleUrl("rendered.js"));
  const wikiParser = await import(moduleUrl("wiki-parser.js"));

  const ambiguousPaths = [
    ...Array.from({ length: 23 }, (_, index) => `${String(index).padStart(2, "0")}/Leaf.md`),
    "\uE000/Leaf.md",
    "😀/Leaf.md",
  ].sort();
  const wikiSnapshot = snapshot(["docs/Exact.md", ...ambiguousPaths]);
  const wikiContext = wiki.createWikiResolutionContext(wikiSnapshot);
  const exact = settle(
    wikiContext.begin({
      action: "navigate",
      authoredTarget: "./Exact",
      sourcePath: "docs/current.md",
    }),
  );
  const ambiguous = settle(
    wikiContext.begin({
      action: "navigate",
      authoredTarget: "Leaf",
      sourcePath: "docs/current.md",
    }),
  );
  wikiContext.dispose();
  const pendingContext = wiki.createWikiResolutionContext(snapshot([], false));
  const pending = settle(
    pendingContext.begin({
      action: "navigate",
      authoredTarget: "Later",
      sourcePath: "docs/current.md",
    }),
  );
  pendingContext.dispose();
  const truncatedContext = wiki.createWikiResolutionContext(
    snapshot(["docs/current.md", "notes/Later.md"], false, true),
  );
  const truncated = settle(
    truncatedContext.begin({
      action: "navigate",
      authoredTarget: "Later",
      sourcePath: "docs/current.md",
    }),
  );
  truncatedContext.dispose();
  const overflowContext = wiki.createWikiResolutionContext(
    snapshot(
      Array.from({ length: 4097 }, (_, index) => `${String(index).padStart(4, "0")}/Overflow.md`),
    ),
  );
  const overflow = settle(
    overflowContext.begin({
      action: "navigate",
      authoredTarget: "Overflow",
      sourcePath: "docs/current.md",
    }),
    16_384,
  );
  overflowContext.dispose();

  let currentSnapshot = snapshot([], false);
  let catalogListener = null;
  const catalog = {
    snapshot: () => currentSnapshot,
    subscribe(listener) {
      catalogListener = listener;
      return () => {
        catalogListener = null;
      };
    },
  };
  const reconciliationScheduler = scheduler();
  const reconciliationReports = [];
  const reconciliation = coordinatorModule.createMarkdownReconciliationCoordinator(catalogApi(), {
    ...reconciliationScheduler,
    reportError: (error) => reconciliationReports.push(String(error.message || error)),
  });
  const revisionStates = [];
  reconciliation
    .createScope()
    .wiki(
      { action: "navigate", authoredTarget: "Later", sourcePath: "docs/current.md" },
      (result) => revisionStates.push(result.status),
    );
  reconciliationScheduler.drain();
  currentSnapshot = snapshot(["docs/Later.md"]);
  catalogListener();
  reconciliationScheduler.drain();
  reconciliation.dispose();

  // A walk stopped at the file cap is final for its index: the pending job
  // settles once with an explanation and later changes re-run nothing. Only a
  // later complete walk, such as one after a restart with a higher file cap,
  // re-runs that job, and then the complete revision is pinned.
  currentSnapshot = snapshot(["docs/current.md"], false);
  const truncatedScheduler = scheduler();
  const truncatedReconciliation = coordinatorModule.createMarkdownReconciliationCoordinator(
    catalogApi(),
    truncatedScheduler,
  );
  const truncatedRevisionStates = [];
  truncatedReconciliation
    .createScope()
    .wiki(
      { action: "navigate", authoredTarget: "Later", sourcePath: "docs/current.md" },
      (result) => truncatedRevisionStates.push(`${result.status}:${result.reason ?? result.path}`),
    );
  truncatedScheduler.drain();
  currentSnapshot = snapshot(["docs/current.md", "notes/Later.md"], false, true);
  catalogListener();
  truncatedScheduler.drain();
  const listensWhileTruncated = catalogListener !== null;
  currentSnapshot = snapshot(["docs/current.md", "notes/Later.md", "zz/new.md"], false, true);
  catalogListener?.();
  truncatedScheduler.drain();
  const commitsAfterTruncatedChange = truncatedRevisionStates.length - 2;
  currentSnapshot = snapshot(["docs/current.md", "notes/Later.md", "zz/new.md"]);
  catalogListener?.();
  truncatedScheduler.drain();
  const pinnedAfterComplete = catalogListener === null;
  truncatedReconciliation.dispose();

  const sliceScheduler = scheduler();
  const sliceReports = [];
  const sliced = coordinatorModule.createMarkdownReconciliationCoordinator(
    {
      fileCatalog: {
        snapshot: () => snapshot(["docs/Target.md"]),
        subscribe: () => () => {},
      },
    },
    {
      ...sliceScheduler,
      reportError: (error) => sliceReports.push(String(error.message || error)),
    },
  );
  const sliceStates = [];
  const slicedScope = sliced.createScope();
  slicedScope.wiki(
    { action: "invalid", authoredTarget: "./Target", sourcePath: "docs/current.md" },
    () => sliceStates.push("poison-committed"),
  );
  for (let index = 0; index < 40; index += 1) {
    slicedScope.wiki(
      { action: "navigate", authoredTarget: "./Target", sourcePath: "docs/current.md" },
      (result) => sliceStates.push(result.status),
    );
  }
  sliceScheduler.runNext();
  const firstSliceCommits = sliceStates.length;
  const queuedAfterFirstSlice = sliceScheduler.callbacks.size;
  sliceScheduler.drain();
  sliced.dispose();

  // A task-list checkbox is not a link opener: its `[` must not pair with a
  // later link's `](` and hide the wiki links between them.
  const taskListPreparation = wikiParser.preprocessObsidianWiki(
    "- [ ] Review [[Meeting Notes]] per [spec](https://example.com/spec)\n" +
      "  - [x] Follow up in [[Notes#Actions|actions]] and [the [[Hidden]] log](log.md)\n",
  );

  const incompleteAdapter = adapters
    .createPublishedRouteResolutionContext(snapshot(["docs/guide.md", "mkdocs.yml"], false))
    .resolve({ authoredTarget: "/guide/", resolvedPath: "guide/" });
  const truncatedAdapter = adapters
    .createPublishedRouteResolutionContext(snapshot(["docs/guide.md", "mkdocs.yml"], false, true))
    .resolve({ authoredTarget: "/guide/", resolvedPath: "guide/" });
  const completeAdapter = adapters
    .createPublishedRouteResolutionContext(
      snapshot(["_config.yml", "_pages/guide.md", "docs/guide.md", "mkdocs.yml"]),
    )
    .resolve({ authoredTarget: "/guide/", resolvedPath: "guide/" });
  const percentAdapter = adapters
    .createPublishedRouteResolutionContext(snapshot(["docs/100%252F.md", "mkdocs.yml"]))
    .resolve({ authoredTarget: "/100%252F/", resolvedPath: "100%252F/" });

  const rootTargets = [
    '<a href="relative.md">Relative</a>',
    '<a href="javascript:alert(1)">Unsafe</a>',
    '<a href="https://example.com/out">External</a>',
    '<img src="image.png">',
    ...Array.from(
      { length: 4090 },
      (_, index) => `<a href="target-${index}.md">Target ${index}</a>`,
    ),
  ].join("");
  const rootHtml =
    `${rootTargets}<span data-mb-wiki-action="embed" ` +
    'data-mb-wiki-target="Embedded">Embedded</span>';
  const embeddedHtml =
    '<span data-mb-wiki-action="embed" data-mb-wiki-target="Nested">Nested</span>';
  const nestedHtml =
    '<span data-mb-wiki-action="navigate" data-mb-wiki-target="Starved">Starved</span>';
  const rootContainer = new FakeContainer([]);
  let fetchCount = 0;
  let tocDisposals = 0;
  globalThis.Element = FakeElement;
  globalThis.window = {
    addEventListener() {},
    removeEventListener() {},
  };
  globalThis.requestAnimationFrame = () => 0;
  globalThis.cancelAnimationFrame = () => {};
  const nestedCatalog = snapshot(["Embedded.md", "Nested.md"]);
  const rootMount = renderedMarkdown.mountRenderedMarkdown(
    rootContainer,
    { path: "root.md", raw: { content: "![[Embedded]]", content_truncated: false } },
    {
      decorateExternalLink: createSdkSandbox().metabrowser.decorateExternalLink,
      errors: { isAbortError: (error) => error?.name === "AbortError" },
      escapeHtml: String,
      fetchKpressRender: async (ctx) => ({
        diagnostics: [],
        html:
          ctx.path === "root.md"
            ? rootHtml
            : ctx.path === "Embedded.md"
              ? embeddedHtml
              : nestedHtml,
      }),
      fetchText: async ({ path: filePath }) => {
        fetchCount += 1;
        return filePath === "Embedded.md" ? "![[Nested]]" : "# Nested\n";
      },
      fileCatalog: {
        snapshot: () => nestedCatalog,
        subscribe: () => () => {},
      },
      kpressInitToc: () => () => {
        tocDisposals += 1;
      },
      navigation: {
        current: () => ({ path: "root.md" }),
        href: (target) => `/view/${target.path}`,
        open: async () => {},
      },
      repository: null,
    },
  );
  await rootMount.ready;
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const ready = allDescendants(rootContainer).filter(
      (element) => element.getAttribute("data-metabrowser-transclusion-status") === "ready",
    );
    if (ready.length === 2) {
      break;
    }
    await new Promise((resolve) => setImmediate(resolve));
  }
  const descendants = allDescendants(rootContainer);
  const rootElements = rootContainer.elements;
  const relativeHref = rootElements[0]?.getAttribute("href");
  const unsafeStatus = rootElements[1]?.getAttribute("data-metabrowser-link-status");
  const externalHref = rootElements[2]?.getAttribute("href");
  const resourceSrc = rootElements[3]?.getAttribute("src");
  const readyTransclusions = descendants.filter(
    (element) => element.getAttribute("data-metabrowser-transclusion-status") === "ready",
  );
  const enhancedStandardLinks = descendants.filter(
    (element) => element.tagName === "A" && element.getAttribute("href")?.startsWith("/view/"),
  );
  const starvedWiki = descendants.find(
    (element) => element.getAttribute("data-mb-wiki-target") === "Starved",
  );
  const starvedWikiRemainsInert =
    Boolean(starvedWiki) &&
    !starvedWiki.hasAttribute("href") &&
    !starvedWiki.hasAttribute("data-metabrowser-link-status");
  rootMount.dispose();
  delete globalThis.Element;
  delete globalThis.window;
  delete globalThis.requestAnimationFrame;
  delete globalThis.cancelAnimationFrame;
  if (
    enhancedStandardLinks.length !== 4091 ||
    relativeHref !== "/view/relative.md" ||
    unsafeStatus !== "unsafe" ||
    externalHref !== "https://example.com/out" ||
    resourceSrc !== "/raw?path=image.png" ||
    fetchCount !== 2 ||
    readyTransclusions.length !== 2 ||
    !starvedWikiRemainsInert ||
    tocDisposals !== 3
  ) {
    throw new Error("real nested Markdown chain did not preserve its shared root budgets");
  }

  // Every Markdown mount on a page shares one Worker. It outlives the last
  // reference for an idle period, so the next Markdown mount finds it, and ends
  // with that period or when the page is hidden. A fatal failure is replaced on
  // the next request rather than disabling preprocessing for the rest of the
  // page. The idle period runs on a clock the session advances.
  const workerClient = await import(moduleUrl("markdown-worker-client.js"));
  // The sections above ran the operations without a Worker and left that client idle;
  // hiding the page ends it, so this section starts with none.
  hidePage();
  const nativeSetTimeout = globalThis.setTimeout;
  const nativeClearTimeout = globalThis.clearTimeout;
  const idleTimers = new Map();
  let nextIdleTimer = 1;
  globalThis.setTimeout = (callback, delay) => {
    idleTimers.set(nextIdleTimer, { callback, delay });
    nextIdleTimer += 1;
    return nextIdleTimer - 1;
  };
  globalThis.clearTimeout = (id) => idleTimers.delete(id);
  const workers = [];
  globalThis.Worker = class SessionWorker {
    constructor() {
      this.messages = [];
      this.terminated = false;
      workers.push(this);
    }

    postMessage(message) {
      this.messages.push(message);
      queueMicrotask(() => {
        if (this.terminated) {
          return;
        }
        if (message.payload.source === "crash") {
          this.onerror?.({ message: "session worker failed" });
        } else {
          this.onmessage?.({ data: { id: message.id, result: message.payload.source } });
        }
      });
    }

    terminate() {
      this.terminated = true;
    }
  };
  const documentReference = workerClient.acquireMarkdownWorkerClient();
  const panelReference = workerClient.acquireMarkdownWorkerClient();
  await Promise.all([
    documentReference.run("prepare-primary", { source: "document" }),
    panelReference.run("prepare-primary", { source: "readme panel" }),
  ]);
  const concurrentWorkers = workers.length;
  // The shell waits for a staged document's primary preparation before it
  // disposes the outgoing document, so that primary dispatches ahead of the
  // outgoing document's queued embeds.
  const stagedReference = workerClient.acquireMarkdownWorkerClient();
  const dispatchStart = workers[0].messages.length;
  await Promise.all([
    documentReference.run("prepare-transclusion", { source: "outgoing embed 1" }),
    documentReference.run("prepare-transclusion", { source: "outgoing embed 2" }),
    stagedReference.run("prepare-primary", { source: "staged document" }),
  ]);
  const stagedDispatchOrder = workers[0].messages
    .slice(dispatchStart)
    .map((message) => message.payload.source);
  stagedReference.dispose();
  documentReference.dispose();
  const aliveAfterOneRelease = !workers[0].terminated;
  const fatalError = await panelReference.run("prepare-primary", { source: "crash" }).then(
    () => null,
    (error) => error.message,
  );
  const recovered = await panelReference.run("prepare-primary", { source: "after crash" });
  const workersAfterRecovery = workers.length;
  panelReference.dispose();
  const keptAfterLastRelease = !workers.at(-1).terminated;
  const idlePeriodMs = [...idleTimers.values()].map((timer) => timer.delay);
  // The next Markdown document, opened after a file of another kind.
  const nextDocument = workerClient.acquireMarkdownWorkerClient();
  await nextDocument.run("prepare-primary", { source: "next document" });
  const workersForNextDocument = workers.length;
  nextDocument.dispose();
  for (const [id, timer] of [...idleTimers]) {
    idleTimers.delete(id);
    timer.callback();
  }
  const terminatedAfterIdlePeriod = workers.every((worker) => worker.terminated);
  const hiddenDocument = workerClient.acquireMarkdownWorkerClient();
  await hiddenDocument.run("prepare-primary", { source: "before hiding" });
  hiddenDocument.dispose();
  for (const listener of [...pagehideListeners]) {
    listener({ type: "pagehide", persisted: false });
  }
  const terminatedOnPageHide =
    workers.every((worker) => worker.terminated) &&
    idleTimers.size === 0 &&
    pagehideListeners.size === 0;
  globalThis.setTimeout = nativeSetTimeout;
  globalThis.clearTimeout = nativeClearTimeout;
  delete globalThis.addEventListener;
  delete globalThis.removeEventListener;
  delete globalThis.Worker;

  // A mount of the envelope the shell holds places the render an earlier mount of it
  // kept, with no preparation and no request. A changed file arrives as another envelope
  // and asks again; another table-of-contents option is another render; and a folder's
  // README panel, which mounts with the folder's envelope, asks every time.
  globalThis.Element = FakeElement;
  globalThis.window = { addEventListener() {}, removeEventListener() {} };
  globalThis.requestAnimationFrame = () => 0;
  globalThis.cancelAnimationFrame = () => {};
  const renderAsks = [];
  const keptSdk = {
    decorateExternalLink: createSdkSandbox().metabrowser.decorateExternalLink,
    errors: { isAbortError: (error) => error?.name === "AbortError" },
    escapeHtml: String,
    fetchKpressRender: async (ctx, _view, options) => {
      renderAsks.push(
        `${ctx.path} ${ctx.raw?.mtime_hash} ${options.sourceText === undefined ? "GET" : "POST"} toc=${options.includeToc ?? "auto"}`,
      );
      return { diagnostics: [], html: `<p>${ctx.path} ${ctx.raw?.mtime_hash}</p>` };
    },
    fetchText: async () => "",
    fileCatalog: { snapshot: () => snapshot([]), subscribe: () => () => {} },
    kpressInitToc: () => () => {},
    navigation: {
      current: () => ({ path: "kept.md" }),
      href: (target) => `/view/${target.path}`,
      open: async () => {},
    },
    repository: null,
  };
  const shownByKeptMounts = [];
  const mountKept = async (ctx, options) => {
    const container = new FakeContainer([]);
    const handle = renderedMarkdown.mountRenderedMarkdown(container, ctx, keptSdk, options);
    await handle.ready;
    shownByKeptMounts.push(container.innerHTML);
    handle.dispose();
  };
  const keptFirst = { content: "# Kept\n", mtime_hash: "v1", path: "kept.md", type: "text" };
  await mountKept({ path: "kept.md", raw: keptFirst });
  await mountKept({ path: "kept.md", raw: keptFirst });
  const keptChanged = { ...keptFirst, content: "# Kept, changed\n", mtime_hash: "v2" };
  await mountKept({ path: "kept.md", raw: keptChanged });
  await mountKept({ path: "kept.md", raw: keptChanged });
  await mountKept({ path: "kept.md", raw: keptChanged }, { includeToc: "off" });
  const folderEnvelope = { mtime_hash: "folder", path: "docs", type: "folder" };
  for (let round = 0; round < 2; round += 1) {
    await mountKept(
      { kind: "markdown", path: "docs/README.md", raw: folderEnvelope },
      { includeToc: "off" },
    );
  }
  // Where a kept render is placed, against the input that found it: a small one in the
  // input's own task, a large one after that input's first paint, and a large one in a
  // hidden page, where nothing is painted, in the input's task again. Frames run when the
  // session paints one.
  const frames = [];
  globalThis.requestAnimationFrame = (callback) => frames.push(callback);
  globalThis.cancelAnimationFrame = (id) => {
    frames[id - 1] = null;
  };
  const endOfTask = async () => {
    for (let turn = 0; turn < 20; turn += 1) {
      await Promise.resolve();
    }
  };
  const placement = async (ctx) => {
    const container = new FakeContainer([]);
    const handle = renderedMarkdown.mountRenderedMarkdown(container, ctx, keptSdk);
    await endOfTask();
    const inInputTask = container.innerHTML.includes("<p>");
    const framesRequested = frames.filter(Boolean).length;
    for (const callback of frames.splice(0)) {
      callback?.(0);
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
    await handle.ready;
    const placed = container.innerHTML.includes("<p>");
    handle.dispose();
    return { framesRequested, inInputTask, placed };
  };
  const largeEnvelope = { content: "# Large\n", mtime_hash: "l1", path: "large.md", type: "text" };
  const largeSdk = {
    ...keptSdk,
    fetchKpressRender: async (ctx, view, options) => {
      const small = await keptSdk.fetchKpressRender(ctx, view, options);
      return {
        ...small,
        html: `${small.html}${"x".repeat(renderedMarkdown.KEPT_RENDER_INPUT_TASK_MAX_CHARS)}`,
      };
    },
  };
  const largeFirst = renderedMarkdown.mountRenderedMarkdown(
    new FakeContainer([]),
    { path: "large.md", raw: largeEnvelope },
    largeSdk,
  );
  await largeFirst.ready;
  largeFirst.dispose();
  const smallPlacement = await placement({ path: "kept.md", raw: keptChanged });
  const largePlacement = await placement({ path: "large.md", raw: largeEnvelope });
  globalThis.document = { visibilityState: "hidden" };
  const hiddenPlacement = await placement({ path: "large.md", raw: largeEnvelope });
  delete globalThis.document;
  const keptRenders = {
    asks: renderAsks,
    kept: renderedMarkdown.keptRenders.stats().entries,
    placement: {
      hiddenPageLargeRender: hiddenPlacement,
      largeRender: largePlacement,
      smallRender: smallPlacement,
    },
    shown: shownByKeptMounts,
  };
  delete globalThis.Element;
  delete globalThis.window;
  delete globalThis.requestAnimationFrame;
  delete globalThis.cancelAnimationFrame;

  console.log(
    JSON.stringify(
      {
        catalogReconciliation: {
          firstSliceCommits,
          poisonReports: sliceReports.length,
          queuedAfterFirstSlice,
          revisionStates,
          settledCommits: sliceStates.filter((status) => status === "internal").length,
          truncated: {
            commitsAfterTruncatedChange,
            listensWhileTruncated,
            pinnedAfterComplete,
            revisionStates: truncatedRevisionStates,
          },
        },
        keptRenders,
        publishedRoutes: {
          complete: completeAdapter,
          incomplete: incompleteAdapter,
          percent: percentAdapter,
          truncated: truncatedAdapter,
        },
        standardLinks: {
          externalHref,
          relativeHref,
          resourceSrc,
          unsafeStatus,
        },
        transclusion: {
          enhancedStandardLinks: enhancedStandardLinks.length,
          fetchedDocuments: fetchCount,
          readyDocuments: readyTransclusions.length,
          starvedWikiRemainsInert,
          tocDisposals,
        },
        wikiResolution: {
          ambiguous: {
            candidateCount: ambiguous.result.candidateCount,
            candidates: ambiguous.result.candidates,
            status: ambiguous.result.status,
          },
          exact: exact.result,
          overflow: overflow.result,
          pending: pending.result,
          truncated: truncated.result,
        },
        wikiPreprocessing: {
          taskList: {
            source: taskListPreparation.source.split("\n"),
            targetCount: taskListPreparation.targetCount,
          },
        },
        workerSharing: {
          aliveAfterOneRelease,
          concurrentWorkers,
          fatalError,
          idlePeriodMs,
          keptAfterLastRelease,
          recovered,
          stagedDispatchOrder,
          terminatedAfterIdlePeriod,
          terminatedOnPageHide,
          workersAfterRecovery,
          workersForNextDocument,
        },
      },
      null,
      2,
    ),
  );

  function catalogApi() {
    return { fileCatalog: catalog };
  }

  function allDescendants(container) {
    const result = [];
    const visit = (element) => {
      result.push(element);
      for (const child of element.elements) {
        visit(child);
      }
    };
    for (const element of container.elements) {
      visit(element);
    }
    return result;
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
