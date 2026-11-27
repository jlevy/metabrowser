const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createSdkSandbox, linkCardRegistration } = require("./sdk-sandbox.js");

const repoRoot = path.resolve(process.argv[2] || ".");
const markdownModuleRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");
const folderModuleRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins/folder");

// The folder plugin's modules have no package.json saying they are modules, which the
// browser never asks about. Node's warning names the process and the checkout, so it is
// kept out of the transcript.
const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

function dataUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

function installedKpressModulePath(name) {
  const relative = path.join("site-packages", "kpress", "format", "static", "js", name);
  const candidates = [path.join(repoRoot, ".venv", "Lib", relative)];
  const unixLib = path.join(repoRoot, ".venv", "lib");
  if (fs.existsSync(unixLib)) {
    for (const entry of fs.readdirSync(unixLib, { withFileTypes: true })) {
      if (entry.isDirectory()) {
        candidates.push(path.join(unixLib, entry.name, relative));
      }
    }
  }
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  if (!found) {
    throw new Error(`installed KPress ${name} not found; run make install first`);
  }
  return found;
}

async function loadProductionModules() {
  const overlayUrl = dataUrl("export function toggleBackdrop(){}");
  const runtimeUrl = dataUrl("export const behaviors={register(){}};");
  // KPress's own viewport helpers, which import nothing: they find the pane marked
  // `[data-kpress-viewport]`, register its scroll listener, read its bounds, and hear its
  // resizes through a ResizeObserver and the window's.
  const viewportUrl = dataUrl(fs.readFileSync(installedKpressModulePath("viewport.js"), "utf8"));
  const tocSource = fs
    .readFileSync(installedKpressModulePath("toc.js"), "utf8")
    .replace('"./overlay.js"', JSON.stringify(overlayUrl))
    .replace('"./runtime.js"', JSON.stringify(runtimeUrl))
    .replace('"./viewport.js"', JSON.stringify(viewportUrl));
  const [rendered, kpressToc, linkEnhancer, tocToggle, readmePanel] = await Promise.all([
    import(pathToFileURL(path.join(markdownModuleRoot, "rendered.js")).href),
    import(dataUrl(tocSource)),
    import(pathToFileURL(path.join(markdownModuleRoot, "link-enhancer.js")).href),
    import(pathToFileURL(path.join(markdownModuleRoot, "toc-toggle.js")).href),
    import(pathToFileURL(path.join(folderModuleRoot, "readme-panel.js")).href),
  ]);
  return {
    kpressToc,
    linkEnhancer,
    readmePanel,
    rendered,
    tocToggle,
  };
}

class EventTargetShim {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(name, listener, options) {
    const listeners = this.listeners.get(name) || new Map();
    listeners.set(listener, options);
    this.listeners.set(name, listeners);
  }

  removeEventListener(name, listener) {
    this.listeners.get(name)?.delete(listener);
  }

  dispatch(name, event = {}) {
    for (const listener of [...(this.listeners.get(name)?.keys() || [])]) {
      listener(event);
    }
  }

  listenerCount(name) {
    return this.listeners.get(name)?.size || 0;
  }

  listenerOptions(name) {
    return [...(this.listeners.get(name)?.values() || [])];
  }

  totalListenerCount() {
    return [...this.listeners.values()].reduce((total, listeners) => total + listeners.size, 0);
  }
}

class ClassListShim {
  constructor() {
    this.names = new Set();
  }

  add(name) {
    this.names.add(name);
  }

  remove(name) {
    this.names.delete(name);
  }

  toggle(name, force) {
    const enabled = force === undefined ? !this.names.has(name) : Boolean(force);
    if (enabled) {
      this.names.add(name);
    } else {
      this.names.delete(name);
    }
    return enabled;
  }
}

class ElementShim extends EventTargetShim {
  constructor(tagName, attributes = {}) {
    super();
    this.nodeType = 1;
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map(Object.entries(attributes));
    this.style = {};
    this.classList = new ClassListShim();
    this.className = attributes.class || "";
    this.parentElement = null;
    this.id = attributes.id || "";
    this.clientHeight = 0;
    this.scrollHeight = 0;
    this.scrollTop = 0;
    this.queryOne = new Map();
    this.queryMany = new Map();
  }

  closest(selector) {
    const mapped = this.closestMatches?.get(selector);
    if (mapped) {
      return mapped;
    }
    for (let element = this; element; element = element.parentElement) {
      if (element.matches(selector)) {
        return element;
      }
    }
    return null;
  }

  // Only a bare attribute selector, such as KPress's `[data-kpress-viewport]`.
  matches(selector) {
    const attribute = /^\[([\w-]+)\]$/.exec(selector);
    return attribute !== null && this.hasAttribute(attribute[1]);
  }

  contains(candidate) {
    for (let element = candidate; element; element = element.parentElement) {
      if (element === this) {
        return true;
      }
    }
    return false;
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  querySelector(selector) {
    return this.queryOne.get(selector) || null;
  }

  querySelectorAll(selector) {
    return this.queryMany.get(selector) || [];
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
}

function plainClick(target) {
  return {
    altKey: false,
    button: 0,
    ctrlKey: false,
    defaultPrevented: false,
    metaKey: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
    shiftKey: false,
    target,
  };
}

/**
 * The README of a folder's Overview: the production README panel mounts the production
 * Markdown mount on the folder's page, whose File Overview puts the document 1,000px down
 * the pane. KPress's toc.js runs with the toggle policy the mount supplies, so the narrow
 * toggle stays hidden past KPress's threshold until the reader reaches the README, and the
 * entries keep their fragment-only links: a click opens the heading on the folder's page,
 * and that page's fragment scrolls the README's heading into view. The folder's address
 * names a README heading when the Overview mounts, as a deep link does, so the mount's
 * first delivery of that fragment scrolls it into view: the page's path, not the README's,
 * is the one the address must name.
 */
async function overviewReadmeSession({
  documentTarget,
  flush,
  frames,
  headingById,
  initKpressToc,
  mountRenderedMarkdown,
  readmePanel,
  windowTarget,
}) {
  const README_TOP = 1_000;
  const pane = new ElementShim("main", { "data-kpress-viewport": "" });
  pane.clientHeight = 800;
  pane.getBoundingClientRect = () => ({
    bottom: 100 + pane.clientHeight,
    height: pane.clientHeight,
    left: 0,
    right: 1_200,
    top: 100,
    width: 1_200,
  });
  const scrolledTo = [];
  const headings = [
    { id: "why", offset: 0 },
    { id: "quick-start", offset: 600 },
    { id: "direction", offset: 1_800 },
  ].map(({ id, offset }) => {
    const heading = new ElementShim("h2", { id });
    heading.getBoundingClientRect = () => ({ top: 100 + README_TOP + offset - pane.scrollTop });
    heading.scrollIntoView = () => scrolledTo.push(id);
    headingById.set(id, heading);
    return heading;
  });
  const links = headings.map((heading) => new ElementShim("a", { href: `#${heading.id}` }));
  const list = new ElementShim("ol");
  list.queryMany.set(
    ":scope > li",
    links.map((link) => {
      const item = new ElementShim("li", { class: "kpress-toc-level-1" });
      item.queryOne.set("a", link);
      return item;
    }),
  );
  const toggle = new ElementShim("button", { "aria-expanded": "false" });
  const scope = new ElementShim("section");
  scope.queryOne.set("[data-kpress-toc-toggle], .kpress-toc-toggle", toggle);
  const toc = new ElementShim("nav", { "data-kpress-toc": "" });
  toc.closestMatches = new Map([[".kpress-content-with-toc", scope]]);
  toc.queryOne.set("ol", list);
  toc.queryMany.set("ol a[href]", links);
  // The README panel's body, which the Markdown mount renders into.
  const body = new ElementShim("div");
  body.getBoundingClientRect = () => ({
    bottom: 100 + README_TOP - pane.scrollTop + 4_000,
    height: 4_000,
    top: 100 + README_TOP - pane.scrollTop,
    width: 1_000,
  });
  body.ownerDocument = {
    createElement: () => ({ content: { querySelectorAll: () => [] }, innerHTML: "" }),
  };
  body.replaceChildren = () => {};
  body.queryMany.set("a[href]", links);
  body.queryMany.set(
    "a[href],img[src],audio[src],video[src],source[src],object[data],[data-mb-wiki-target]",
    links,
  );
  body.queryMany.set("[data-kpress-toc]", [toc]);
  for (const heading of headings) {
    body.queryOne.set(`[id="${heading.id}"]`, heading);
  }
  for (const link of links) {
    link.parentElement = toc;
  }
  toc.parentElement = scope;
  scope.parentElement = body;
  body.parentElement = pane;

  let current = { path: "", fragment: "quick-start" };
  const opened = [];
  let mountOptions = null;
  const mb = {
    decorateExternalLink: createSdkSandbox().metabrowser.decorateExternalLink,
    ...linkCardRegistration(),
    plugins: {
      // index.js's mountRendered, with the session's stand-in for the Markdown Worker.
      load: async () => ({
        mountRendered: (container, ctx, options) => {
          mountOptions = options;
          return mountRenderedMarkdown(container, ctx, mb, {
            ...options,
            workerClient: {
              dispose() {},
              run: async () => ({ changed: false, complete: true, diagnostics: [], source: null }),
            },
          });
        },
      }),
    },
    errors: { isAbortError: () => false },
    escapeHtml: (value) => value,
    fetchKpressRender: async () => ({ diagnostics: [], html: "<article></article>" }),
    fileCatalog: { snapshot: () => ({ complete: true, files: [] }), subscribe: () => () => {} },
    kpressInitToc: (target, config) => initKpressToc(target, config),
    navigation: {
      current: () => current,
      href: (target) => `/view/${target.path}${target.fragment ? `#${target.fragment}` : ""}`,
      open: async (target) => opened.push(target),
    },
    repository: null,
  };
  const handle = await readmePanel
    .createReadmePanel(mb)
    .mount(body, { path: "", raw: {} }, { path: "README.md" }, {});
  await handle.ready;
  flush();
  const deepLinked = [...scrolledTo];

  const steps = [];
  const activeId = () => {
    const index = links.findIndex((link) => link.getAttribute("data-active") === "true");
    return index < 0 ? null : headings[index].id;
  };
  const scrollTo = (label, scrollTop) => {
    pane.scrollTop = scrollTop;
    pane.dispatch("scroll");
    flush();
    steps.push({
      active: activeId(),
      label,
      scrollTop,
      toggleShown: toggle.classList.names.has("show-toggle"),
    });
  };
  scrollTo("top of the Overview", 0);
  scrollTo("past the threshold, in the File Overview", 500);
  scrollTo("the README just below the pane's top", README_TOP - 20);
  scrollTo("the README's beginning reached", README_TOP + 5);
  scrollTo("reading Quick Start", README_TOP + 650);
  scrollTo("back up in the File Overview", 500);

  const click = plainClick(links[2]);
  body.dispatch("click", click);
  await Promise.resolve();
  current = { path: "", fragment: "direction" };
  windowTarget.dispatch("metabrowser:navigation-fragment", { detail: { target: current } });
  flush();

  handle.dispose();
  return {
    click: { defaultPrevented: click.defaultPrevented, opened },
    fragment: { deepLinked, scrolledTo, pendingFrames: frames.size },
    hrefs: links.map((link) => link.getAttribute("href")),
    listenersAfterDispose: {
      body: body.totalListenerCount(),
      document: documentTarget.totalListenerCount(),
      pane: pane.listenerCount("scroll"),
      toc: toc.totalListenerCount(),
      toggle: toggle.totalListenerCount(),
      window: windowTarget.totalListenerCount(),
    },
    mountOptions: { includeToc: mountOptions?.includeToc, pagePath: mountOptions?.pagePath },
    readmeTop: README_TOP,
    steps,
  };
}

(async () => {
  const { kpressToc, linkEnhancer, readmePanel, rendered, tocToggle } =
    await loadProductionModules();
  const { enhanceRenderedLinks } = linkEnhancer;
  const { initKpressToc } = kpressToc;
  const { mountRenderedMarkdown } = rendered;
  // The preview pane, marked as KPress's viewport and its own scroll container.
  const viewport = new ElementShim("main", { "data-kpress-viewport": "" });
  viewport.clientHeight = 800;
  viewport.getBoundingClientRect = () => ({
    bottom: 100 + viewport.clientHeight,
    height: viewport.clientHeight,
    left: 0,
    right: 1_200,
    top: 100,
    width: 1_200,
  });
  const windowTarget = new EventTargetShim();
  windowTarget.innerHeight = 800;
  let headingGeometryReads = 0;
  const headingSpecs = [
    { id: "overview", offset: 0 },
    { id: "design", offset: 600 },
    { id: "implementation-plan", offset: 4_000 },
    { id: "testing", offset: 14_000 },
    ...Array.from({ length: 64 }, (_, index) => ({
      id: `appendix-${index + 1}`,
      offset: 15_000 + index * 1_000,
    })),
  ];
  const headings = headingSpecs.map(({ id, offset }) => {
    const heading = new ElementShim("h2", { id });
    heading.getBoundingClientRect = () => {
      headingGeometryReads += 1;
      return { top: 100 + offset - viewport.scrollTop };
    };
    return heading;
  });
  const headingById = new Map(headings.map((heading) => [heading.id, heading]));
  const links = headings.map((heading) => new ElementShim("a", { href: `#${heading.id}` }));
  const list = new ElementShim("ol");
  const button = new ElementShim("button", { "aria-expanded": "false" });
  const expandAllButton = new ElementShim("button", {
    "aria-expanded": "false",
    "aria-label": "Expand TOC",
    "data-kpress-toc-expand-all": "",
  });
  const tocItems = links.map((link, index) => {
    const level = index === 0 ? 1 : index === 1 || index === 3 ? 2 : 3;
    const item = new ElementShim("li", { class: `kpress-toc-level-${level}` });
    item.queryOne.set("a", link);
    return item;
  });
  list.queryMany.set(":scope > li", tocItems);
  const scope = new ElementShim("section");
  scope.queryOne.set("[data-kpress-toc-toggle], .kpress-toc-toggle", button);
  const toc = new ElementShim("nav", {
    "data-kpress-toc": "",
    "data-kpress-toc-collapse-depth": "2",
  });
  toc.closestMatches = new Map([[".kpress-content-with-toc", scope]]);
  toc.queryOne.set("ol", list);
  toc.queryOne.set("[data-kpress-toc-expand-all]", expandAllButton);
  toc.queryMany.set("ol a[href]", links);
  const container = new ElementShim("article");
  // An opened file: its document starts the pane's scroll, as a file's does under its header.
  container.getBoundingClientRect = () => ({
    bottom: 100 - viewport.scrollTop + 80_000,
    height: 80_000,
    top: 100 - viewport.scrollTop,
    width: 1_000,
  });
  // The render is placed through a template (place-rendered.js); the document it places
  // is the one built above, so placing it keeps the container's children.
  container.ownerDocument = {
    createElement: () => ({ content: { querySelectorAll: () => [] }, innerHTML: "" }),
  };
  container.replaceChildren = () => {};
  container.queryMany.set("a[href]", links);
  container.queryMany.set(
    "a[href],img[src],audio[src],video[src],source[src],object[data],[data-mb-wiki-target]",
    links,
  );
  container.queryMany.set("[id]", headings);
  container.queryMany.set("[data-kpress-toc]", [toc]);
  for (const link of links) {
    link.parentElement = toc;
  }
  toc.parentElement = scope;
  scope.parentElement = container;
  container.parentElement = viewport;

  const documentTarget = new EventTargetShim();
  documentTarget.documentElement = { clientHeight: 800, clientWidth: 1_200 };
  documentTarget.getElementById = (id) => headingById.get(id) || null;
  global.document = documentTarget;
  global.Element = ElementShim;
  global.Node = ElementShim;

  const frames = new Map();
  let frameSequence = 0;
  const schedule = (callback) => {
    frameSequence += 1;
    frames.set(frameSequence, callback);
    return frameSequence;
  };
  const cancel = (handle) => frames.delete(handle);
  const geometryReadsPerUpdate = [];
  const flush = () => {
    const readsBefore = headingGeometryReads;
    const pending = [...frames.entries()];
    frames.clear();
    for (const [, callback] of pending) {
      callback(0);
    }
    if (pending.length > 0) {
      geometryReadsPerUpdate.push(headingGeometryReads - readsBefore);
    }
  };
  // What KPress's addViewportResizeListener observes the pane with: each observer, what it
  // observes, and its callback, which a pane resize calls.
  const resizeObservers = [];
  global.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
      this.targets = new Set();
      resizeObservers.push(this);
    }

    observe(target) {
      this.targets.add(target);
    }

    unobserve(target) {
      this.targets.delete(target);
    }

    disconnect() {
      this.targets.clear();
    }
  };
  const paneObservers = () => resizeObservers.filter((observer) => observer.targets.has(viewport));
  global.window = windowTarget;
  global.requestAnimationFrame = schedule;
  global.cancelAnimationFrame = cancel;

  const sourcePath = "docs/project/specs/active/plan.md";
  const authoredHref = links[2].getAttribute("href");
  const opened = [];
  let catalogSnapshots = 0;
  let tocMountedWithoutCatalogSnapshot = false;
  const mb = {
    decorateExternalLink: createSdkSandbox().metabrowser.decorateExternalLink,
    ...linkCardRegistration(),
    errors: { isAbortError: () => false },
    escapeHtml: (value) => value,
    fetchKpressRender: async () => ({ diagnostics: [], html: "<article></article>" }),
    fileCatalog: {
      snapshot: () => {
        catalogSnapshots += 1;
        return { complete: true, files: [] };
      },
      subscribe: () => () => {},
    },
    // As the SDK does, KPress's toc.js is handed the configuration the mount supplies.
    kpressInitToc: (target, config) => {
      tocMountedWithoutCatalogSnapshot = catalogSnapshots === 0;
      return initKpressToc(target, config);
    },
    navigation: {
      current: () => ({ path: sourcePath }),
      href: (target) => `/view/${target.path}${target.fragment ? `#${target.fragment}` : ""}`,
      open: async (target) => opened.push(target),
    },
    repository: null,
  };
  // KPress chooses its observation path when the TOC binds, so the runtime has to lack
  // IntersectionObserver before the mount for this session to drive KPress's fallback.
  if ("IntersectionObserver" in globalThis) {
    throw new Error("session requires a runtime without IntersectionObserver");
  }
  const mountHandle = mountRenderedMarkdown(
    container,
    { path: sourcePath, raw: { content: "# Plan", content_truncated: false } },
    mb,
    {
      workerClient: {
        dispose() {},
        run: async () => ({ changed: false, complete: true, diagnostics: [], source: null }),
      },
    },
  );
  await mountHandle.ready;
  const collapsedRows = () =>
    tocItems.filter((item) => item.classList.names.has("kpress-toc-collapsed")).length;
  const tocExpansion = {
    beforeExpand: {
      collapsedRows: collapsedRows(),
      expanded: expandAllButton.getAttribute("aria-expanded"),
      label: expandAllButton.getAttribute("aria-label"),
    },
  };
  expandAllButton.dispatch("click");
  tocExpansion.afterExpand = {
    collapsedRows: collapsedRows(),
    expanded: expandAllButton.getAttribute("aria-expanded"),
    label: expandAllButton.getAttribute("aria-label"),
  };
  expandAllButton.dispatch("click");
  tocExpansion.afterCollapse = {
    collapsedRows: collapsedRows(),
    expanded: expandAllButton.getAttribute("aria-expanded"),
    label: expandAllButton.getAttribute("aria-label"),
  };
  const enhancedHref = links[2].getAttribute("href");
  const delegatedClick = plainClick(links[2]);
  container.dispatch("click", delegatedClick);
  await Promise.resolve();
  const delegatedTarget = opened[0] || null;

  const embeddedFragment = new ElementShim("a", { href: "#details" });
  const embeddedNewTab = new ElementShim("a", { href: "#details", target: "_blank" });
  const embeddedContainer = new ElementShim("aside");
  embeddedContainer.queryMany.set("a[href]", [embeddedFragment, embeddedNewTab]);
  embeddedContainer.queryMany.set(
    "a[href],img[src],audio[src],video[src],source[src],object[data],[data-mb-wiki-target]",
    [embeddedFragment, embeddedNewTab],
  );
  embeddedFragment.parentElement = embeddedContainer;
  embeddedNewTab.parentElement = embeddedContainer;
  const embeddedHandle = enhanceRenderedLinks(embeddedContainer, "docs/embedded.md", mb, {
    cancel,
    eventTarget: windowTarget,
    schedule,
  });
  const embeddedHref = embeddedFragment.getAttribute("href");
  const embeddedTargetBlankHref = embeddedNewTab.getAttribute("href");
  const embeddedClick = plainClick(embeddedFragment);
  embeddedContainer.dispatch("click", embeddedClick);
  await Promise.resolve();
  const embeddedDelegatedTarget = opened[1] || null;
  const embeddedModifierClick = plainClick(embeddedFragment);
  embeddedModifierClick.metaKey = true;
  embeddedContainer.dispatch("click", embeddedModifierClick);
  const embeddedNewTabClick = plainClick(embeddedNewTab);
  embeddedContainer.dispatch("click", embeddedNewTabClick);
  embeddedHandle.dispose();

  // KPress's viewportScrollContext registers the pane's scroll listeners.
  const passiveScrollListener =
    viewport.listenerCount("scroll") > 0 &&
    viewport.listenerOptions("scroll").every((options) => options?.passive === true);
  const paneResizeObservers = paneObservers().length;
  flush();
  const catalogSnapshotsAfterFirstFlush = catalogSnapshots;

  const steps = [];
  const activeId = () => {
    const index = links.findIndex((link) => link.getAttribute("data-active") === "true");
    return index < 0 ? null : headings[index].id;
  };
  const record = (label) => {
    steps.push({
      active: activeId(),
      label,
      scrollTop: viewport.scrollTop,
      toggleShown: button.classList.names.has("show-toggle"),
    });
  };
  record("top");

  viewport.scrollTop = 750;
  viewport.dispatch("scroll");
  flush();
  record("design section");

  viewport.scrollTop = 4_050;
  viewport.dispatch("scroll");
  flush();
  record("implementation plan heading");

  viewport.scrollTop = 11_000;
  viewport.dispatch("scroll");
  flush();
  record("middle of long implementation plan");

  viewport.scrollTop = 14_100;
  viewport.dispatch("scroll");
  viewport.dispatch("scroll");
  viewport.dispatch("scroll");
  const coalescedFrames = frames.size;
  flush();
  record("testing section after scroll burst");

  // A pane resize with no scroll moves the reading line, and KPress's ResizeObserver on the
  // pane updates the active section: the design heading, 150px under the pane's top, is
  // above a quarter of 800px and below a quarter of 400px.
  viewport.scrollTop = 450;
  viewport.dispatch("scroll");
  flush();
  record("design heading above the reading line");
  viewport.clientHeight = 400;
  for (const observer of paneObservers()) {
    observer.callback([], observer);
  }
  flush();
  record("pane resized to half height");
  viewport.clientHeight = 800;

  // Within KPress's threshold of the top, the toggle stays hidden, as KPress has it.
  viewport.scrollTop = 60;
  viewport.dispatch("scroll");
  flush();
  record("short of the toggle threshold");

  viewport.scrollTop = 600;
  viewport.dispatch("scroll");
  mountHandle.dispose();
  const pendingFramesAfterDispose = frames.size;
  const listenersAfterDispose = {
    container: container.totalListenerCount(),
    document: documentTarget.totalListenerCount(),
    toc: toc.totalListenerCount(),
    tocExpandAll: expandAllButton.totalListenerCount(),
    tocLinks: links.reduce((total, link) => total + link.totalListenerCount(), 0),
    viewport: viewport.listenerCount("scroll"),
    viewportResizeObservers: paneObservers().length,
    window: windowTarget.totalListenerCount(),
  };
  const tocBindingDisposed = toc.getAttribute("data-kpress-toc-bound") === null;
  tocExpansion.afterDispose = {
    collapsedRows: collapsedRows(),
    expanded: expandAllButton.getAttribute("aria-expanded"),
    label: expandAllButton.getAttribute("aria-label"),
  };

  // The README a folder's Overview shows, mounted by the production README panel on the
  // folder's page: the File Overview above it puts its document 1,000px down the pane.
  const overview = await overviewReadmeSession({
    documentTarget,
    flush,
    frames,
    headingById,
    initKpressToc,
    mountRenderedMarkdown,
    readmePanel,
    windowTarget,
  });

  const result = {
    coalescedFrames,
    dispose: { listenersAfterDispose, pendingFramesAfterDispose, tocBindingDisposed },
    links: {
      authoredHref,
      delegatedClickPrevented: delegatedClick.defaultPrevented,
      delegatedTarget,
      embeddedDelegatedTarget,
      embeddedHref,
      embeddedModifierClickPrevented: embeddedModifierClick.defaultPrevented,
      embeddedNewTabClickPrevented: embeddedNewTabClick.defaultPrevented,
      embeddedTargetBlankHref,
      enhancedHref,
    },
    maxHeadingGeometryReadsPerUpdate: Math.max(...geometryReadsPerUpdate),
    overview,
    paneResizeObservers,
    passiveScrollListener,
    productionModules: {
      kpressToc: true,
      kpressViewport: true,
      renderedMarkdownMount: true,
    },
    productionOrder: {
      tocMountedWithoutCatalogSnapshot,
      catalogSnapshotsAfterFirstFlush,
    },
    steps,
    tocExpansion,
    toggleThreshold: {
      kpress: kpressToc.TOC_TOGGLE_SCROLL_THRESHOLD_PX,
      metabrowser: tocToggle.TOC_TOGGLE_SCROLL_THRESHOLD_PX,
    },
  };
  const expectedActive = [
    "overview",
    "design",
    "implementation-plan",
    "implementation-plan",
    "testing",
    "design",
    "overview",
    "overview",
  ];
  const actualActive = steps.map((step) => step.active);
  const expectedToggle = [false, true, true, true, true, true, true, false];
  const actualToggle = steps.map((step) => step.toggleShown);
  const expectedOverviewToggle = [false, false, false, true, true, false];
  const expectedTarget = { path: sourcePath, fragment: "implementation-plan" };
  if (
    authoredHref !== "#implementation-plan" ||
    enhancedHref !== authoredHref ||
    !delegatedClick.defaultPrevented ||
    JSON.stringify(delegatedTarget) !== JSON.stringify(expectedTarget) ||
    embeddedHref !== "/view/docs/embedded.md#details" ||
    embeddedTargetBlankHref !== "/view/docs/embedded.md#details" ||
    !embeddedClick.defaultPrevented ||
    JSON.stringify(embeddedDelegatedTarget) !==
      JSON.stringify({ path: "docs/embedded.md", fragment: "details" }) ||
    embeddedModifierClick.defaultPrevented ||
    embeddedNewTabClick.defaultPrevented ||
    opened.length !== 2 ||
    JSON.stringify(actualActive) !== JSON.stringify(expectedActive) ||
    JSON.stringify(actualToggle) !== JSON.stringify(expectedToggle) ||
    result.toggleThreshold.kpress !== result.toggleThreshold.metabrowser ||
    overview.mountOptions.pagePath !== "" ||
    overview.mountOptions.includeToc !== undefined ||
    overview.hrefs.join(" ") !== "#why #quick-start #direction" ||
    JSON.stringify(overview.steps.map((step) => step.toggleShown)) !==
      JSON.stringify(expectedOverviewToggle) ||
    overview.steps[4].active !== "quick-start" ||
    !overview.click.defaultPrevented ||
    JSON.stringify(overview.click.opened) !==
      JSON.stringify([{ path: "", fragment: "direction" }]) ||
    JSON.stringify(overview.fragment.deepLinked) !== JSON.stringify(["quick-start"]) ||
    JSON.stringify(overview.fragment.scrolledTo) !== JSON.stringify(["quick-start", "direction"]) ||
    Object.values(overview.listenersAfterDispose).some((count) => count !== 0) ||
    coalescedFrames !== 1 ||
    !tocMountedWithoutCatalogSnapshot ||
    catalogSnapshotsAfterFirstFlush !== 0 ||
    result.maxHeadingGeometryReadsPerUpdate > Math.ceil(Math.log2(headings.length)) + 1 ||
    !passiveScrollListener ||
    paneResizeObservers !== 1 ||
    tocExpansion.beforeExpand.collapsedRows !== 65 ||
    tocExpansion.afterExpand.collapsedRows !== 0 ||
    tocExpansion.afterExpand.expanded !== "true" ||
    tocExpansion.afterCollapse.collapsedRows !== 65 ||
    tocExpansion.afterCollapse.expanded !== "false" ||
    tocExpansion.afterDispose.collapsedRows !== 0 ||
    tocExpansion.afterDispose.expanded !== "false" ||
    pendingFramesAfterDispose !== 0 ||
    !tocBindingDisposed ||
    Object.values(listenersAfterDispose).some((count) => count !== 0)
  ) {
    throw new Error(`unexpected composed Markdown session: ${JSON.stringify(result)}`);
  }
  console.log(JSON.stringify(result, null, 2));
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
