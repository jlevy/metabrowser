const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(process.argv[2] || ".");
const markdownModuleRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");

function dataUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

function installedKpressTocPath() {
  const relative = path.join("site-packages", "kpress", "format", "static", "js", "toc.js");
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
    throw new Error("installed KPress toc.js not found; run make install first");
  }
  return found;
}

async function loadProductionModules() {
  const overlayUrl = dataUrl("export function toggleBackdrop(){}");
  const runtimeUrl = dataUrl("export const behaviors={register(){}};");
  const viewportUrl = dataUrl(
    "export function resolveKpressViewport(){return globalThis.__tocViewport;}" +
      "export function viewportScrollContext(){return globalThis.__tocViewportContext;}",
  );
  const tocSource = fs
    .readFileSync(installedKpressTocPath(), "utf8")
    .replace('"./overlay.js"', JSON.stringify(overlayUrl))
    .replace('"./runtime.js"', JSON.stringify(runtimeUrl))
    .replace('"./viewport.js"', JSON.stringify(viewportUrl));
  const [rendered, fallback, kpressToc] = await Promise.all([
    import(pathToFileURL(path.join(markdownModuleRoot, "rendered.js")).href),
    import(pathToFileURL(path.join(markdownModuleRoot, "toc-intersection-fallback.js")).href),
    import(dataUrl(tocSource)),
  ]);
  return {
    fallback,
    kpressToc,
    rendered,
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
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map(Object.entries(attributes));
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
    return this.closestMatches?.get(selector) || null;
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

(async () => {
  const { fallback, kpressToc, rendered } = await loadProductionModules();
  const { initTocWithIntersectionFallback } = fallback;
  const { initKpressToc } = kpressToc;
  const { mountRenderedMarkdown } = rendered;
  const viewport = new ElementShim("main");
  viewport.clientHeight = 800;
  viewport.getBoundingClientRect = () => ({ height: 800, top: 100 });
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
  toc.queryMany.set('ol a[href^="#"]', links);
  const container = new ElementShim("article");
  container.queryMany.set("a[href]", links);
  container.queryMany.set("[id]", headings);
  container.queryMany.set("[data-kpress-toc]", [toc]);
  for (const link of links) {
    link.parentElement = toc;
  }
  toc.parentElement = scope;
  scope.parentElement = container;

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
  const viewportContext = {
    lock() {},
    observerRoot: () => viewport,
    offScroll: (listener) => viewport.removeEventListener("scroll", listener),
    onScroll: (listener) => viewport.addEventListener("scroll", listener, { passive: true }),
    scrollToTop() {
      viewport.scrollTop = 0;
    },
    scrollTop: () => viewport.scrollTop,
    unlock() {},
  };
  global.__tocViewport = viewport;
  global.__tocViewportContext = viewportContext;
  global.window = windowTarget;
  global.requestAnimationFrame = schedule;
  global.cancelAnimationFrame = cancel;

  const sourcePath = "docs/project/specs/active/plan.md";
  const authoredHref = links[2].getAttribute("href");
  const opened = [];
  let catalogSnapshots = 0;
  let enhancerHadRunAtTocMount = false;
  const mb = {
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
    kpressInitToc: (target) => {
      enhancerHadRunAtTocMount = catalogSnapshots > 0;
      return initKpressToc(target);
    },
    navigation: {
      current: () => ({ path: sourcePath }),
      href: (target) => `/view/${target.path}${target.fragment ? `#${target.fragment}` : ""}`,
      open: async (target) => opened.push(target),
    },
    repository: null,
  };
  const mountHandle = mountRenderedMarkdown(
    container,
    { path: sourcePath, raw: { content: "# Plan", content_truncated: false } },
    mb,
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

  const runtime = globalThis;
  if ("IntersectionObserver" in runtime) {
    throw new Error("session requires a runtime without native IntersectionObserver");
  }
  const fallbackWasScoped = !("IntersectionObserver" in runtime);
  const passiveScrollListener = viewport.listenerOptions("scroll")[0]?.passive === true;
  flush();

  const steps = [];
  const activeId = () => {
    const index = links.findIndex((link) => link.getAttribute("data-active") === "true");
    return index < 0 ? null : headings[index].id;
  };
  const record = (label) => {
    steps.push({ active: activeId(), label, scrollTop: viewport.scrollTop });
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
    window: windowTarget.totalListenerCount(),
  };
  const tocBindingDisposed = toc.getAttribute("data-kpress-toc-bound") === null;
  tocExpansion.afterDispose = {
    collapsedRows: collapsedRows(),
    expanded: expandAllButton.getAttribute("aria-expanded"),
    label: expandAllButton.getAttribute("aria-label"),
  };

  class NativeIntersectionObserver {}
  runtime.IntersectionObserver = NativeIntersectionObserver;
  let nativeSeen = false;
  const nativeDispose = initTocWithIntersectionFallback(
    () => {
      nativeSeen = runtime.IntersectionObserver === NativeIntersectionObserver;
      return () => {};
    },
    { cancel, runtime, schedule, windowTarget },
  );
  nativeDispose();
  const nativeRuntimePreserved =
    nativeSeen && runtime.IntersectionObserver === NativeIntersectionObserver;
  delete runtime.IntersectionObserver;

  const result = {
    coalescedFrames,
    dispose: { listenersAfterDispose, pendingFramesAfterDispose, tocBindingDisposed },
    fallbackWasScoped,
    links: {
      authoredHref,
      delegatedClickPrevented: delegatedClick.defaultPrevented,
      delegatedTarget,
      enhancedHref,
    },
    maxHeadingGeometryReadsPerUpdate: Math.max(...geometryReadsPerUpdate),
    nativeRuntimePreserved,
    passiveScrollListener,
    productionModules: {
      kpressToc: true,
      renderedMarkdownMount: true,
      tocIntersectionFallback: true,
    },
    productionOrder: { enhancerHadRunAtTocMount },
    steps,
    tocExpansion,
  };
  const expectedActive = [
    "overview",
    "design",
    "implementation-plan",
    "implementation-plan",
    "testing",
  ];
  const actualActive = steps.map((step) => step.active);
  const expectedTarget = { path: sourcePath, fragment: "implementation-plan" };
  if (
    authoredHref !== "#implementation-plan" ||
    enhancedHref !== authoredHref ||
    !delegatedClick.defaultPrevented ||
    JSON.stringify(delegatedTarget) !== JSON.stringify(expectedTarget) ||
    JSON.stringify(actualActive) !== JSON.stringify(expectedActive) ||
    coalescedFrames !== 1 ||
    !fallbackWasScoped ||
    !enhancerHadRunAtTocMount ||
    result.maxHeadingGeometryReadsPerUpdate > Math.ceil(Math.log2(headings.length)) + 1 ||
    !passiveScrollListener ||
    !nativeRuntimePreserved ||
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
