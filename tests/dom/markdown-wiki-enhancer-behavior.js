const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class FakeElement {
  constructor(tagName, attributes = {}, textContent = "") {
    this.attributes = new Map(Object.entries(attributes));
    this.innerHTML = "";
    this.parentElement = null;
    this.tagName = tagName.toUpperCase();
    this.textContent = textContent;
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  replaceWith(replacement) {
    const index = this.parentElement.elements.indexOf(this);
    this.parentElement.elements[index] = replacement;
    replacement.parentElement = this.parentElement;
    this.parentElement = null;
  }
}

class FakeContainer extends FakeElement {
  constructor(elements) {
    super("main");
    this.elements = elements;
    this.ownerDocument = { createElement: (tagName) => new FakeElement(tagName) };
    for (const element of elements) {
      element.parentElement = this;
    }
  }

  querySelectorAll(selector) {
    return selector === "[data-mb-wiki-target]"
      ? this.elements.filter((element) => element.hasAttribute("data-mb-wiki-target"))
      : [];
  }
}

function createScheduler() {
  const frames = new Map();
  let sequence = 0;
  return {
    cancel: (handle) => frames.delete(handle),
    frames,
    runAll() {
      let guard = 0;
      while (frames.size) {
        guard += 1;
        if (guard > 10_000) {
          throw new Error("wiki enhancer scheduler did not settle");
        }
        const [handle, callback] = frames.entries().next().value;
        frames.delete(handle);
        callback(0);
      }
    },
    schedule(callback) {
      sequence += 1;
      frames.set(sequence, callback);
      return sequence;
    },
  };
}

function catalogFiles(paths) {
  return [...paths].sort().map((filePath) => ({
    basename: filePath.slice(filePath.lastIndexOf("/") + 1),
    path: filePath,
  }));
}

async function loadModule() {
  const parserSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-parser.js"),
    "utf8",
  );
  const parserUrl = `data:text/javascript;base64,${Buffer.from(parserSource).toString("base64")}`;
  const workerStub =
    `import {prepareTransclusionMarkdownSource} from ${JSON.stringify(parserUrl)};` +
    "export function acquireMarkdownWorkerClient(){return {dispose(){}," +
    "run(_op,payload){return Promise.resolve(prepareTransclusionMarkdownSource(payload.source,payload.fragment))}}}";
  const workerUrl = `data:text/javascript;base64,${Buffer.from(workerStub).toString("base64")}`;
  const traversalSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/dom-traversal.js"),
    "utf8",
  );
  const traversalUrl = `data:text/javascript;base64,${Buffer.from(traversalSource).toString("base64")}`;
  const tocFallbackStub =
    "export function initTocWithIntersectionFallback(init){return init()||(()=>{})}";
  const tocFallbackUrl = `data:text/javascript;base64,${Buffer.from(tocFallbackStub).toString("base64")}`;
  const transclusionSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/transclusion.js"),
      "utf8",
    )
    .replace('"./toc-intersection-fallback.js"', JSON.stringify(tocFallbackUrl))
    .replace(
      '"./inert-render.js"',
      JSON.stringify(
        require("node:url").pathToFileURL(
          path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/inert-render.js"),
        ).href,
      ),
    )
    .replace('"./markdown-worker-client.js"', JSON.stringify(workerUrl))
    .replace('"./wiki-parser.js"', JSON.stringify(parserUrl));
  const transclusionUrl = `data:text/javascript;base64,${Buffer.from(transclusionSource).toString("base64")}`;
  const resolverSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-resolver.js"),
    "utf8",
  );
  const resolverUrl = `data:text/javascript;base64,${Buffer.from(resolverSource).toString("base64")}`;
  const linksSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/links.js"),
    "utf8",
  );
  const linksUrl = `data:text/javascript;base64,${Buffer.from(linksSource).toString("base64")}`;
  const adaptersSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/project-adapters.js"),
    "utf8",
  );
  const adaptersUrl = `data:text/javascript;base64,${Buffer.from(adaptersSource).toString("base64")}`;
  const coordinatorSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/reconciliation-coordinator.js"),
      "utf8",
    )
    .replace('"./links.js"', JSON.stringify(linksUrl))
    .replace('"./project-adapters.js"', JSON.stringify(adaptersUrl))
    .replace('"./wiki-resolver.js"', JSON.stringify(resolverUrl));
  const coordinatorUrl = `data:text/javascript;base64,${Buffer.from(coordinatorSource).toString("base64")}`;
  const enhancerSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-enhancer.js"),
      "utf8",
    )
    .replace('"./transclusion.js"', JSON.stringify(transclusionUrl))
    .replace('"./dom-traversal.js"', JSON.stringify(traversalUrl))
    .replace('"./markdown-worker-client.js"', JSON.stringify(workerUrl))
    .replace('"./reconciliation-coordinator.js"', JSON.stringify(coordinatorUrl));
  return {
    enhancer: await import(
      `data:text/javascript;base64,${Buffer.from(enhancerSource).toString("base64")}`
    ),
    transclusion: await import(transclusionUrl),
  };
}

(async () => {
  const loaded = await loadModule();
  const module = loaded.enhancer;
  const exact = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Exact" },
    "Exact label",
  );
  const unique = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Unique" },
    "Unique",
  );
  const ambiguous = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Duplicate" },
    "Duplicate",
  );
  const missing = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Missing" },
    "Missing",
  );
  const image = new FakeElement(
    "span",
    {
      "data-mb-wiki-action": "embed",
      "data-mb-wiki-height": "480",
      "data-mb-wiki-target": "image.png",
      "data-mb-wiki-width": "640",
    },
    "Diagram",
  );
  const noteEmbed = new FakeElement(
    "span",
    { "data-mb-wiki-action": "embed", "data-mb-wiki-target": "Exact" },
    "Exact embed",
  );
  const container = new FakeContainer([exact, unique, ambiguous, missing, image, noteEmbed]);
  const files = [
    { basename: "Exact.md", path: "docs/Exact.md" },
    { basename: "image.png", path: "docs/image.png" },
    { basename: "Unique.md", path: "else/Unique.md" },
    { basename: "Duplicate.md", path: "one/Duplicate.md" },
    { basename: "Duplicate.md", path: "two/Duplicate.md" },
  ];
  let complete = false;
  let catalogListener = null;
  let unsubscribeCount = 0;
  let frameSequence = 0;
  const frames = new Map();
  const scheduler = {
    cancel: (handle) => frames.delete(handle),
    schedule: (callback) => {
      frameSequence += 1;
      frames.set(frameSequence, callback);
      return frameSequence;
    },
  };
  const registered = [];
  const mb = {
    fetchKpressRender: async () => ({ html: '<article class="kpress">Embedded</article>' }),
    fetchText: async () => "# Embedded note\n",
    fileCatalog: {
      snapshot: () => ({ complete, files }),
      subscribe: (listener) => {
        catalogListener = listener;
        return () => {
          catalogListener = null;
          unsubscribeCount += 1;
        };
      },
    },
    navigation: {
      href: (target) =>
        `/view/${target.path}${target.fragment ? `#${encodeURIComponent(target.fragment)}` : ""}`,
    },
  };

  const handle = module.enhanceWikiLinks(
    container,
    "docs/current.md",
    mb,
    (element, target) => {
      registered.push({ element, target });
    },
    scheduler,
  );
  check("initial wiki reconciliation is deferred", frames.size === 1);
  check("exact link unchanged before scheduled work", container.elements[0] === exact);
  const initialFrame = [...frames.entries()][0];
  frames.delete(initialFrame[0]);
  initialFrame[1](0);
  check("exact link resolves before complete", container.elements[0].tagName === "A");
  check(
    "exact link canonical href",
    container.elements[0].getAttribute("href") === "/view/docs/Exact.md",
  );
  check("exact label preserved", container.elements[0].textContent === "Exact label");
  check(
    "unique link starts pending",
    unique.getAttribute("data-metabrowser-link-status") === "pending",
  );
  check("pending state visible", unique.textContent.includes("resolving link"));
  check("pending inventory subscription", typeof catalogListener === "function");
  const renderedImage = container.elements[4];
  check("image embed element", renderedImage.tagName === "IMG");
  check(
    "image embed safe raw source",
    renderedImage.getAttribute("src") === "/raw?path=docs%2Fimage.png",
  );
  check(
    "image embed dimensions",
    renderedImage.getAttribute("width") === "640" && renderedImage.getAttribute("height") === "480",
  );
  check("image accessible label", renderedImage.getAttribute("alt") === "Diagram");
  const noteTransclusion = container.elements[5];
  check("note transclusion region", noteTransclusion.tagName === "ASIDE");
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "note transclusion rendered",
    noteTransclusion.getAttribute("data-metabrowser-transclusion-status") === "ready",
  );

  complete = true;
  catalogListener();
  check("catalog publication only schedules DOM reconciliation", frames.size === 1);
  check("scheduled link remains pending", container.elements[1] === unique);
  for (const callback of [...frames.values()]) {
    frames.clear();
    callback(0);
  }
  check("unique link resolves after completion", container.elements[1].tagName === "A");
  check(
    "unique link target",
    container.elements[1].getAttribute("href") === "/view/else/Unique.md",
  );
  check("ambiguous remains visible", ambiguous.textContent.includes("ambiguous link"));
  check("ambiguous link semantics", ambiguous.getAttribute("role") === "link");
  check(
    "ambiguous candidates announced",
    ambiguous.getAttribute("aria-label").includes("one/Duplicate.md"),
  );
  check("missing remains visible", missing.textContent.includes("missing link"));
  check("subscription released after settling", catalogListener === null && unsubscribeCount === 1);
  check("navigation registrations", registered.length === 2);
  handle.dispose();
  check("settled disposal is idempotent", unsubscribeCount === 1);

  const hugeCandidateElement = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Huge" },
    "Huge",
  );
  const hugeCandidateScheduler = createScheduler();
  const hugeCandidatePaths = Array.from(
    { length: 25 },
    (_, index) => `${String(index).padStart(2, "0")}/${"p".repeat(100_000)}/Huge.md`,
  );
  const hugeCandidateHandle = module.enhanceWikiLinks(
    new FakeContainer([hugeCandidateElement]),
    "docs/current.md",
    {
      ...mb,
      fileCatalog: {
        snapshot: () => ({ complete: true, files: catalogFiles(hugeCandidatePaths) }),
        subscribe: () => () => {},
      },
    },
    () => {},
    hugeCandidateScheduler,
  );
  hugeCandidateScheduler.runAll();
  const hugeAnnouncement = hugeCandidateElement.getAttribute("aria-label");
  check(
    "provider-long ambiguous candidates use a bounded display projection",
    hugeAnnouncement.length < 2300 &&
      hugeAnnouncement.includes("…") &&
      hugeAnnouncement.includes("and 21 more"),
    String(hugeAnnouncement.length),
  );
  hugeCandidateHandle.dispose();

  const pendingOnly = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Later" },
    "Later",
  );
  complete = false;
  const pendingHandle = module.enhanceWikiLinks(
    new FakeContainer([pendingOnly]),
    "docs/current.md",
    mb,
    () => {},
    scheduler,
  );
  check("second mount subscribed", typeof catalogListener === "function");
  pendingHandle.dispose();
  check(
    "dispose releases pending subscription",
    catalogListener === null && unsubscribeCount === 2,
  );

  // A walk that stopped at the file cap is final for its index. A fallback wiki
  // link and a note embed settle as disabled explanations instead of resolving
  // forever, and a later complete walk still resolves them.
  const cappedLink = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Unique" },
    "Unique",
  );
  const cappedEmbed = new FakeElement(
    "span",
    { "data-mb-wiki-action": "embed", "data-mb-wiki-target": "Unique" },
    "Unique embed",
  );
  const cappedScheduler = createScheduler();
  let cappedListener = null;
  let cappedSnapshot = { complete: false, files, truncated: false };
  const cappedContainer = new FakeContainer([cappedLink, cappedEmbed]);
  const cappedHandle = module.enhanceWikiLinks(
    cappedContainer,
    "docs/current.md",
    {
      ...mb,
      fileCatalog: {
        snapshot: () => cappedSnapshot,
        subscribe: (listener) => {
          cappedListener = listener;
          return () => {
            cappedListener = null;
          };
        },
      },
    },
    () => {},
    cappedScheduler,
  );
  cappedScheduler.runAll();
  check(
    "a fallback link on a partial catalog is pending",
    cappedLink.getAttribute("data-metabrowser-link-status") === "pending",
  );
  cappedSnapshot = { complete: false, files, truncated: true };
  cappedListener();
  cappedScheduler.runAll();
  check(
    "a fallback link on a truncated catalog is disabled with an explanation",
    cappedLink.getAttribute("data-metabrowser-link-status") === "unsupported" &&
      cappedLink.getAttribute("aria-disabled") === "true" &&
      cappedLink.getAttribute("title") === "Unsupported link (catalog-truncated)." &&
      !cappedLink.textContent.includes("resolving"),
    `${cappedLink.getAttribute("title")} / ${cappedLink.textContent}`,
  );
  check(
    "a note embed on a truncated catalog explains why it is not embedded",
    cappedEmbed.getAttribute("data-metabrowser-link-status") === "unsupported" &&
      cappedEmbed.getAttribute("title") === "Unsupported link (catalog-truncated).",
    String(cappedEmbed.getAttribute("title")),
  );
  check("a truncated catalog keeps the wiki subscription", typeof cappedListener === "function");
  cappedSnapshot = { complete: true, files, truncated: false };
  cappedListener();
  cappedScheduler.runAll();
  const upgradedLink = cappedContainer.elements[0];
  check(
    "a later complete catalog resolves the link the cap disabled and pins",
    upgradedLink !== cappedLink &&
      upgradedLink.tagName.toLowerCase() === "a" &&
      upgradedLink.getAttribute("data-metabrowser-link-status") === null &&
      cappedListener === null,
    `${upgradedLink.tagName} ${upgradedLink.getAttribute("data-metabrowser-link-status")}`,
  );
  cappedHandle.dispose();

  const largeElements = ["MissingA", "MissingB", "MissingC"].map(
    (target) =>
      new FakeElement(
        "span",
        { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": target },
        target,
      ),
  );
  const largeContainer = new FakeContainer(largeElements);
  const largeFrames = new Map();
  let largeFrameSequence = 0;
  let largeCatalogListener = null;
  let largePathReads = 0;
  const largeFiles = Array.from({ length: 300_000 }, (_, index) =>
    Object.defineProperties(
      {},
      {
        basename: { value: `${String(index).padStart(6, "0")}.md` },
        path: {
          get() {
            largePathReads += 1;
            return `docs/${String(index).padStart(6, "0")}.md`;
          },
        },
      },
    ),
  );
  const largeHandle = module.enhanceWikiLinks(
    largeContainer,
    "docs/current.md",
    {
      ...mb,
      fileCatalog: {
        snapshot: () => ({ complete: true, files: largeFiles }),
        subscribe: (listener) => {
          largeCatalogListener = listener;
          return () => {
            largeCatalogListener = null;
          };
        },
      },
    },
    () => {},
    {
      cancel: (frame) => largeFrames.delete(frame),
      schedule: (callback) => {
        largeFrameSequence += 1;
        largeFrames.set(largeFrameSequence, callback);
        return largeFrameSequence;
      },
    },
  );
  check(
    "300k unresolved fallback is deferred before any catalog read",
    largePathReads === 0 && largeContainer.elements.every((element) => element.tagName === "SPAN"),
  );
  check("300k reconciliation defers remaining targets", largeFrames.size === 1);
  const firstLargeFrame = [...largeFrames.entries()][0];
  largeFrames.delete(firstLargeFrame[0]);
  firstLargeFrame[1](0);
  const readsAfterInitialSlice = largePathReads;
  check(
    "300k initial slice bounds real path visits",
    readsAfterInitialSlice > 0 && readsAfterInitialSlice <= 16_384,
    String(readsAfterInitialSlice),
  );
  const secondLargeFrame = [...largeFrames.entries()][0];
  largeFrames.delete(secondLargeFrame[0]);
  secondLargeFrame[1](0);
  check(
    "300k continuation bounds real path visits",
    largePathReads - readsAfterInitialSlice > 0 &&
      largePathReads - readsAfterInitialSlice <= 16_384,
    String(largePathReads - readsAfterInitialSlice),
  );
  check("300k continuation stays scheduled", largeFrames.size === 1);
  check(
    "complete reconciliation pins and releases its catalog listener",
    largeFrames.size === 1 && largeCatalogListener === null,
  );
  const staleLargeFrame = [...largeFrames.values()][0];
  const readsBeforeLargeDispose = largePathReads;
  largeHandle.dispose();
  check("300k disposal cancels continuation", largeFrames.size === 0);
  staleLargeFrame(0);
  check(
    "stale continuation cannot read or mutate after disposal",
    largePathReads === readsBeforeLargeDispose &&
      largeContainer.elements.every((element) => element.tagName === "SPAN"),
  );

  const transitionNavigate = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Flip" },
    "Flip",
  );
  const transitionEmbed = new FakeElement(
    "span",
    { "data-mb-wiki-action": "embed", "data-mb-wiki-target": "Embed" },
    "Embed",
  );
  const transitionContainer = new FakeContainer([transitionNavigate, transitionEmbed]);
  const transitionScheduler = createScheduler();
  let transitionSnapshot = {
    complete: false,
    files: catalogFiles(["docs/Embed.md", "docs/Flip.md"]),
  };
  let transitionListener = null;
  let resolveStaleFetch = null;
  let staleFetchSignal = null;
  let transitionFetches = 0;
  let transitionRenders = 0;
  const transitionBudget = loaded.transclusion.createTransclusionBudget({ maxDocuments: 8 });
  const transitionHandle = module.enhanceWikiLinks(
    transitionContainer,
    "docs/current.md",
    {
      fetchKpressRender: async () => {
        transitionRenders += 1;
        return { html: "<p>stale</p>" };
      },
      fetchText: (_target, options) => {
        transitionFetches += 1;
        staleFetchSignal = options.signal;
        return new Promise((resolve) => {
          resolveStaleFetch = resolve;
        });
      },
      fileCatalog: {
        snapshot: () => transitionSnapshot,
        subscribe: (listener) => {
          transitionListener = listener;
          return () => {
            transitionListener = null;
          };
        },
      },
      navigation: mb.navigation,
    },
    () => {},
    { ...transitionScheduler, budget: transitionBudget },
  );
  transitionScheduler.runAll();
  await Promise.resolve();
  const firstTransitionAnchor = transitionContainer.elements[0];
  const firstTransitionAside = transitionContainer.elements[1];
  check("incomplete exact navigation mounts", firstTransitionAnchor.tagName === "A");
  check("incomplete exact embed mounts", firstTransitionAside.tagName === "ASIDE");
  check("first embed claims one document", transitionBudget.state.documents === 1);
  check("first embed starts one fetch", transitionFetches === 1);

  transitionSnapshot = {
    complete: false,
    files: catalogFiles(["docs/Embed.md", "docs/Flip.md"]),
  };
  transitionListener();
  transitionScheduler.runAll();
  check(
    "same internal navigation across revisions is not replaced",
    transitionContainer.elements[0] === firstTransitionAnchor,
  );
  check(
    "same internal embed across revisions is not remounted",
    transitionContainer.elements[1] === firstTransitionAside &&
      transitionBudget.state.documents === 1 &&
      transitionFetches === 1,
  );

  transitionSnapshot = { complete: true, files: [] };
  transitionListener();
  transitionScheduler.runAll();
  check(
    "internal navigation can converge to missing on the pinned complete revision",
    transitionContainer.elements[0].tagName === "SPAN" &&
      transitionContainer.elements[0].getAttribute("data-metabrowser-link-status") === "missing",
  );
  check(
    "internal embed can converge to missing without refunding its claim",
    transitionContainer.elements[1].tagName === "SPAN" &&
      transitionContainer.elements[1].getAttribute("data-metabrowser-link-status") === "missing" &&
      transitionBudget.state.documents === 1,
  );
  check("changed embed aborts its in-flight source fetch", staleFetchSignal.aborted);
  resolveStaleFetch("# stale source\n");
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "disposed in-flight embed cannot render or replace the final state",
    transitionRenders === 0 &&
      transitionContainer.elements[1].getAttribute("data-metabrowser-link-status") === "missing",
  );
  transitionHandle.dispose();

  const lateElement = new FakeElement(
    "span",
    { "data-mb-wiki-action": "navigate", "data-mb-wiki-target": "Later" },
    "Later",
  );
  const lateContainer = new FakeContainer([lateElement]);
  const lateScheduler = createScheduler();
  let lateSnapshot = { complete: false, files: [] };
  let lateListener = null;
  const lateHandle = module.enhanceWikiLinks(
    lateContainer,
    "docs/current.md",
    {
      ...mb,
      fileCatalog: {
        snapshot: () => lateSnapshot,
        subscribe: (listener) => {
          lateListener = listener;
          return () => {
            lateListener = null;
          };
        },
      },
    },
    () => {},
    lateScheduler,
  );
  lateScheduler.runAll();
  check(
    "early absence remains pending",
    lateContainer.elements[0].getAttribute("data-metabrowser-link-status") === "pending",
  );
  lateSnapshot = { complete: true, files: catalogFiles(["other/Later.md"]) };
  lateListener();
  lateScheduler.runAll();
  check(
    "missing-to-internal transition uses the pinned complete catalog",
    lateContainer.elements[0].tagName === "A" &&
      lateContainer.elements[0].getAttribute("href") === "/view/other/Later.md",
  );
  lateHandle.dispose();

  const movedEmbed = new FakeElement(
    "span",
    { "data-mb-wiki-action": "embed", "data-mb-wiki-target": "Move" },
    "Move",
  );
  const movedContainer = new FakeContainer([movedEmbed]);
  const movedScheduler = createScheduler();
  let movedSnapshot = { complete: false, files: catalogFiles(["docs/Move.md"]) };
  let movedListener = null;
  const movedPaths = [];
  const movedBudget = loaded.transclusion.createTransclusionBudget({ maxDocuments: 8 });
  const movedHandle = module.enhanceWikiLinks(
    movedContainer,
    "docs/current.md",
    {
      fetchKpressRender: async () => ({ html: "<p>moved</p>" }),
      fetchText: async ({ path: filePath }) => {
        movedPaths.push(filePath);
        return "# Moved\n";
      },
      fileCatalog: {
        snapshot: () => movedSnapshot,
        subscribe: (listener) => {
          movedListener = listener;
          return () => {
            movedListener = null;
          };
        },
      },
      navigation: mb.navigation,
    },
    () => {},
    { ...movedScheduler, budget: movedBudget },
  );
  movedScheduler.runAll();
  await new Promise((resolve) => setImmediate(resolve));
  const firstMovedAside = movedContainer.elements[0];
  movedSnapshot = { complete: true, files: catalogFiles(["other/Move.md"]) };
  movedListener();
  movedScheduler.runAll();
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "a changed internal embed remounts exactly once",
    movedContainer.elements[0].tagName === "ASIDE" &&
      movedContainer.elements[0] !== firstMovedAside &&
      JSON.stringify(movedPaths) === '["docs/Move.md","other/Move.md"]',
  );
  check(
    "only an actual changed remount consumes another non-refundable claim",
    movedBudget.state.documents === 2,
  );
  movedHandle.dispose();

  // A fallback embed resolves only once the catalog completes, which can be long
  // after an exact embed in the same document started loading. The late embed
  // is timed from its own claim, not from the first embed's. Date.now follows
  // the virtual clock so a wall-clock deadline regression is observed as well.
  let virtualNow = 1_000_000;
  const virtualTimers = new Map();
  let virtualTimerSequence = 0;
  const virtualClock = {
    clearTimeout: (timer) => virtualTimers.delete(timer),
    now: () => virtualNow,
    setTimeout(callback, delayMs) {
      virtualTimerSequence += 1;
      virtualTimers.set(virtualTimerSequence, { callback, due: virtualNow + delayMs });
      return virtualTimerSequence;
    },
  };
  const nativeDateNow = Date.now;
  Date.now = () => virtualNow;
  try {
    const earlyEmbed = new FakeElement(
      "span",
      { "data-mb-wiki-action": "embed", "data-mb-wiki-target": "Early" },
      "Early",
    );
    const lateEmbed = new FakeElement(
      "span",
      { "data-mb-wiki-action": "embed", "data-mb-wiki-target": "Late" },
      "Late",
    );
    const staggeredContainer = new FakeContainer([earlyEmbed, lateEmbed]);
    const staggeredScheduler = createScheduler();
    let staggeredSnapshot = {
      complete: false,
      files: catalogFiles(["docs/Early.md", "notes/Late.md"]),
    };
    let staggeredListener = null;
    const staggeredHandle = module.enhanceWikiLinks(
      staggeredContainer,
      "docs/current.md",
      {
        fetchKpressRender: async () => ({ html: "<p>embedded</p>" }),
        fetchText: async () => "# Embedded\n",
        fileCatalog: {
          snapshot: () => staggeredSnapshot,
          subscribe: (listener) => {
            staggeredListener = listener;
            return () => {
              staggeredListener = null;
            };
          },
        },
        navigation: mb.navigation,
      },
      () => {},
      {
        ...staggeredScheduler,
        budget: loaded.transclusion.createTransclusionBudget({}, { clock: virtualClock }),
      },
    );
    staggeredScheduler.runAll();
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "an exact embed renders before the catalog completes",
      staggeredContainer.elements[0].getAttribute("data-metabrowser-transclusion-status") ===
        "ready",
    );
    check(
      "a fallback embed waits for the complete catalog",
      staggeredContainer.elements[1].getAttribute("data-metabrowser-link-status") === "pending",
    );
    virtualNow += 6_000;
    staggeredSnapshot = { complete: true, files: staggeredSnapshot.files };
    staggeredListener();
    staggeredScheduler.runAll();
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "a fallback embed resolved six seconds later renders instead of timing out",
      staggeredContainer.elements[1].getAttribute("data-metabrowser-transclusion-status") ===
        "ready",
      String(staggeredContainer.elements[1].getAttribute("data-metabrowser-transclusion-error")),
    );
    staggeredHandle.dispose();
    check("staggered embeds leave no deadline timer", virtualTimers.size === 0);
  } finally {
    Date.now = nativeDateNow;
  }

  if (failures.length) {
    console.error(`markdown wiki enhancer FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("markdown wiki enhancer OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
