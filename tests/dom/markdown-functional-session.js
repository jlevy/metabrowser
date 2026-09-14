// Cohesive browserless transcript for Markdown catalog and lifecycle behavior.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const markdownRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");
const moduleUrl = (name) => pathToFileURL(path.join(markdownRoot, name)).href;

function knownFile(filePath) {
  return Object.freeze({
    basename: filePath.slice(filePath.lastIndexOf("/") + 1),
    path: filePath,
  });
}

function snapshot(paths, complete = true) {
  return Object.freeze({
    complete,
    files: Object.freeze([...paths].sort().map(knownFile)),
    revision: complete ? 2 : 1,
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

  console.log(
    JSON.stringify(
      {
        catalogReconciliation: {
          firstSliceCommits,
          poisonReports: sliceReports.length,
          queuedAfterFirstSlice,
          revisionStates,
          settledCommits: sliceStates.filter((status) => status === "internal").length,
        },
        publishedRoutes: {
          complete: completeAdapter,
          incomplete: incompleteAdapter,
          percent: percentAdapter,
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
        },
        wikiPreprocessing: {
          taskList: {
            source: taskListPreparation.source.split("\n"),
            targetCount: taskListPreparation.targetCount,
          },
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
