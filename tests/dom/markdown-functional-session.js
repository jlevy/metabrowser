// Cohesive browserless transcript for Markdown catalog and lifecycle behavior.

const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createSdkSandbox, linkCardRegistration } = require("./sdk-sandbox.js");

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

  append(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
      this.elements.push(node);
    }
  }

  get children() {
    return this.elements;
  }

  remove() {
    if (this.parentElement) {
      this.parentElement.elements = this.parentElement.elements.filter((node) => node !== this);
      this.parentElement = null;
    }
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
    if (/^\w+$/.test(selector)) {
      return this.tagName === selector.toUpperCase();
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

  // A template's content is the template itself here: its parsed elements.
  get content() {
    return this;
  }

  replaceChildren(...nodes) {
    const [only] = nodes;
    const fragment = nodes.length === 1 && only.tagName === "TEMPLATE";
    this._innerHTML = fragment ? only._innerHTML : "";
    this.elements = fragment ? only.elements : [...nodes];
    for (const element of this.elements) {
      element.parentElement = this;
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
  const pattern = /<(a|span|object)\b([^>]*)>(.*?)<\/\1>|<(img)\b([^>]*)>/g;
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

/** The text a reader reads in *element*: its own, or its children's, in order. */
function reads(element) {
  return element.elements.length === 0
    ? element.textContent
    : element.elements.map((child) => reads(child)).join(" · ");
}

/** A plain primary click on *target*, or one with *modifiers*, as the container hears it. */
function click(container, target, modifiers = {}) {
  const event = {
    altKey: false,
    button: 0,
    ctrlKey: false,
    defaultPrevented: false,
    metaKey: false,
    shiftKey: false,
    ...modifiers,
    target,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
  container.listeners.get("click")(event);
  return event.defaultPrevented;
}

/** Let posted reconciliation slices, the plugin's load, and the preview's answer settle. */
async function settled() {
  for (let round = 0; round < 20; round += 1) {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

/**
 * A document's PDFs, through the same chain as the root document above (rendered.js, the
 * link enhancer, the wiki enhancer) and the pdf plugin's production card
 * (builtin_plugins/pdf/card.js, the `mountPdfCard` its index.js exports and
 * `mb.plugins.load("pdf")` answers). The render holds what KPress keeps of each way to
 * name a PDF (cli-api-render-diagnostics.tryscript.md pins it) -- a link, `![](…)` and
 * `<img>` as an image, and the wiki preprocessor's own placeholders for `![[…]]` and
 * `[[…]]` -- with an `<object>`, which the enhancer's selector admits though KPress drops
 * it, and an image of a PDF named without `.pdf`. The preview route answers as the server
 * did for `papers/report.pdf` in a trusted folder (tests/fixtures/pdf-surfaces-responses.json).
 */
async function pdfEmbedSession(renderedMarkdown, wikiParser, printReady) {
  const card = await import(
    pathToFileURL(path.join(repoRoot, "src/metabrowser/builtin_plugins/pdf/card.js")).href
  );
  const recorded = require("../fixtures/pdf-surfaces-responses.json");
  const wikiTargets = wikiParser.preprocessObsidianWiki("![[report.pdf]] [[report.pdf]]\n");
  const [wikiEmbed, wikiLink] = wikiTargets.source
    .trim()
    .split(" <span")
    .map((part, index) => (index === 0 ? part : `<span${part}`));
  // Each way the document names a PDF, and what KPress hands the enhancer for it.
  const forms = [
    ["[the report](report.pdf)", '<a href="report.pdf">the report</a>'],
    ["![The report](report.pdf)", '<img src="report.pdf" alt="The report">'],
    ['<object data="report.pdf">', '<object data="report.pdf">The report</object>'],
    ["![[report.pdf]]", wikiEmbed],
    ["[[report.pdf]]", wikiLink],
    ["![A scan](scan)", '<img src="scan" alt="A scan">'],
  ];
  const html = forms.map(([, rendered]) => rendered).join("");
  const answers = {
    "/api/plugin/pdf/preview?path=papers%2Freport.pdf":
      recorded.folder.files["papers/report.pdf"].preview,
  };
  const previews = [];
  globalThis.fetch = async (address) => {
    previews.push(address);
    const answer = answers[address];
    return { ok: answer !== undefined, json: async () => answer };
  };
  globalThis.Element = FakeElement;
  globalThis.window = { addEventListener() {}, removeEventListener() {} };
  globalThis.requestAnimationFrame = () => 0;
  globalThis.cancelAnimationFrame = () => {};
  // The SDK, through which each link the document opens here has its link card
  // (`metabrowser.previewLink`, static/plugin-sdk-views.js), on a page with no resolver: a
  // stand-in that records each card, by its link, with its root and target, and the SDK's
  // own hand-over of a link's titles to its card, given back as the card ends.
  const linkCards = new Map();
  const disposedRoots = [];
  const { takeAuthorTitles, giveAuthorTitlesBack } = linkCardRegistration();
  const cardRegistration = {
    previewLink(root, anchor, target) {
      linkCards.set(anchor, { root, target });
      return true;
    },
    takeAuthorTitles,
    forgetPreview(anchor) {
      linkCards.delete(anchor);
      giveAuthorTitlesBack(anchor);
    },
    disposePreviews(root) {
      disposedRoots.push(root);
      for (const [anchor, entry] of linkCards) {
        if (entry.root === root) {
          linkCards.delete(anchor);
          giveAuthorTitlesBack(anchor);
        }
      }
    },
  };

  /** Mount the document, with the plugin's load answered by *load*. */
  async function mount(load) {
    const container = new FakeContainer([]);
    const loads = [];
    const opened = [];
    const handle = renderedMarkdown.mountRenderedMarkdown(
      container,
      { path: "papers/notes.md", raw: { content: "notes", content_truncated: false } },
      {
        decorateExternalLink: createSdkSandbox().metabrowser.decorateExternalLink,
        errors: { isAbortError: (error) => error?.name === "AbortError" },
        escapeHtml: String,
        fetchKpressRender: async () => ({ diagnostics: [], html }),
        fileCatalog: {
          snapshot: () => snapshot(["papers/notes.md", "papers/report.pdf", "papers/scan"]),
          subscribe: () => () => {},
        },
        kpressInitToc: () => () => {},
        navigation: {
          current: () => ({ path: "papers/notes.md" }),
          href: (target) => `/view/${target.path}`,
          open: async (target) => opened.push(target),
        },
        plugins: {
          load: (name) => {
            loads.push(name);
            return load();
          },
        },
        // A plain folder's page, with no GitHub identity, which `loadRepositoryLinks`
        // answers with no resolver (plugin-sdk-views.js): its links have their cards still.
        repository: null,
        loadRepositoryLinks: async () => null,
        ...cardRegistration,
      },
    );
    await handle.ready;
    await settled();
    return { container, handle, loads, opened };
  }

  /** What each form became: a link, an image, or a PDF's slot and what it holds. */
  function describeDocument(container, only = null) {
    const described = {};
    container.elements.forEach((element, index) => {
      const [form] = forms[index];
      if (element.getAttribute("class") !== "metabrowser-pdf-embed") {
        if (only === null) {
          const address = element.getAttribute("href") ?? element.getAttribute("src");
          described[form] = `${element.tagName.toLowerCase()} → ${address}`;
        }
        return;
      }
      const [held] = element.elements;
      if (held === undefined) {
        described[form] = "pdf slot: empty";
      } else if (element.getAttribute("data-metabrowser-pdf-embed") === "link") {
        described[form] = `pdf slot: link "${held.textContent}" → ${held.getAttribute("href")}`;
      } else {
        const [page, caption] = held.elements;
        const image = page.elements[0];
        const view = caption.elements[2].elements[0];
        described[form] =
          `pdf slot: card ${held.getAttribute("data-pdf-preview")}, ` +
          `${image ? `image ${image.getAttribute("src")}` : "no image"}, ` +
          `"${reads(caption)}", View → ${view.getAttribute("href")}`;
      }
    });
    return described;
  }

  /** Every element under *container*. */
  function walk(container) {
    const found = [];
    const visit = (element) => {
      found.push(element);
      for (const child of element.elements) {
        visit(child);
      }
    };
    for (const element of container.elements) {
      visit(element);
    }
    return found;
  }

  // The plugin loads when the first PDF is drawn, and until it answers each slot is a
  // plain link to the view.
  let release = () => {};
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const drawn = await mount(() => gate.then(() => ({ mountPdfCard: card.mountPdfCard })));
  const beforeLoad = describeDocument(drawn.container);
  const fallback = drawn.container.elements[1].elements[0];
  const fallbackOpens = click(drawn.container, fallback);
  release();
  await settled();
  const shown = describeDocument(drawn.container);
  const nodes = walk(drawn.container);
  const pdfAddresses = nodes.flatMap((node) =>
    [...node.attributes.values()].filter((value) =>
      /^\/raw\?path=papers%2Freport\.pdf/.test(value),
    ),
  );
  const viewers = nodes.filter((node) => ["EMBED", "OBJECT", "IFRAME"].includes(node.tagName));
  const views = nodes.filter((node) => node.tagName === "A" && node.textContent === "View");
  const plainClickOpens = click(drawn.container, views[0]);
  const modifiedClickOpens = click(drawn.container, views[0], { metaKey: true });
  // Printing a document makes each image that has not loaded eager, the card's too.
  printReady.loadImagesForPrint(drawn.container);
  const printLoading = nodes
    .filter((node) => node.getAttribute("class") === "pdf-card-image")
    .map((image) => image.getAttribute("loading"));
  const askedBeforeDispose = previews.length;
  const slots = drawn.container.elements.filter(
    (element) => element.getAttribute("class") === "metabrowser-pdf-embed",
  );
  // Each link the document opens here has its card, registered with the rendered root: a
  // link to the PDF by its path, a wiki link, and each slot's link to the PDF's view.
  const linksDrawn = walk(drawn.container).filter((node) => node.tagName === "A");
  const cardsShown = linksDrawn.map((link) => {
    const entry = linkCards.get(link);
    if (entry === undefined) {
      return `${reads(link)}: none`;
    }
    const { root, target } = entry;
    const rooted = root === drawn.container ? "" : ", not the rendered root's";
    return `${reads(link)}: ${target.kind} ${target.localization} ${target.target.path}${rooted}`;
  });
  drawn.handle.dispose();
  const disposal = {
    cardsLeft: slots.filter((slot) => slot.elements.length > 0).length,
    slots: slots.length,
    linkCardsLeft: linksDrawn.filter((link) => linkCards.has(link)).length,
  };

  // A document replaced before the plugin answers mounts no card, and asks for no preview.
  let releaseLate = () => {};
  const lateGate = new Promise((resolve) => {
    releaseLate = resolve;
  });
  const replaced = await mount(() => lateGate.then(() => ({ mountPdfCard: card.mountPdfCard })));
  replaced.handle.dispose();
  releaseLate();
  await settled();
  const replacedBeforeLoad = {
    asked: previews.length - askedBeforeDispose,
    shows: describeDocument(replaced.container, "pdf"),
  };

  // A page whose pdf plugin cannot load keeps the links.
  const missing = await mount(() => Promise.reject(new Error("plugins.load: no plugin pdf")));
  const withoutPlugin = describeDocument(missing.container, "pdf");
  missing.handle.dispose();

  delete globalThis.fetch;
  delete globalThis.Element;
  delete globalThis.window;
  delete globalThis.requestAnimationFrame;
  delete globalThis.cancelAnimationFrame;
  const result = {
    beforeLoad,
    shown,
    clicks: {
      fallback: { opened: fallbackOpens, target: drawn.opened[0] },
      view: { opened: plainClickOpens, target: drawn.opened[1] },
      modified: { opened: modifiedClickOpens },
    },
    pluginLoads: { calls: drawn.loads.length, names: [...new Set(drawn.loads)] },
    previewsAsked: previews.slice(0, askedBeforeDispose),
    print: printLoading,
    linkCards: cardsShown,
    disposal,
    replacedBeforeLoad,
    withoutPlugin,
    viewersDrawn: viewers.length,
    rawAddressesOfThePdf: pdfAddresses.length,
  };
  if (
    viewers.length !== 0 ||
    pdfAddresses.length !== 0 ||
    disposal.cardsLeft !== 0 ||
    disposal.linkCardsLeft !== 0 ||
    !disposedRoots.includes(drawn.container) ||
    replacedBeforeLoad.asked !== 0 ||
    !plainClickOpens ||
    modifiedClickOpens
  ) {
    throw new Error(`a document's PDF embeds broke an invariant: ${JSON.stringify(result)}`);
  }
  return result;
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
  // A heading's anchors open its inline content, one per hierarchical name and
  // each name once, and add no line; a list item above `---` is no heading.
  const headingPreparation = wikiParser.preprocessObsidianWiki(
    "# Guide\n## Setup\nUsage\n=====\n- step\n---\n## Setup\n",
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
  const rootPluginLoads = [];
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
      // A document that embeds no PDF never loads the pdf plugin.
      plugins: {
        load: async (name) => {
          rootPluginLoads.push(name);
          return {};
        },
      },
      repository: null,
      ...linkCardRegistration(),
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
  const pdfEmbeds = {
    pluginLoadsWithoutAPdf: rootPluginLoads.length,
    ...(await pdfEmbedSession(
      renderedMarkdown,
      wikiParser,
      await import(moduleUrl("print-ready.js")),
    )),
  };

  // Every Markdown mount on a page shares one Worker. References release it only
  // when the last one is disposed, and a fatal failure is replaced on the next
  // request rather than disabling preprocessing for the rest of the page.
  const workerClient = await import(moduleUrl("markdown-worker-client.js"));
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
  const terminatedAfterLastRelease = workers.every((worker) => worker.terminated);
  delete globalThis.Worker;

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
        pdfEmbeds,
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
          headings: headingPreparation.source.split("\n"),
          taskList: {
            source: taskListPreparation.source.split("\n"),
            targetCount: taskListPreparation.targetCount,
          },
        },
        workerSharing: {
          aliveAfterOneRelease,
          concurrentWorkers,
          fatalError,
          recovered,
          stagedDispatchOrder,
          terminatedAfterLastRelease,
          workersAfterRecovery,
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
