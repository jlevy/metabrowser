const fs = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class ElementShim {}
global.Element = ElementShim;

class FakeElement extends ElementShim {
  constructor(tagName, attributes = {}) {
    super();
    this.tagName = tagName.toUpperCase();
    this.parentElement = null;
    this.attributes = new Map(Object.entries(attributes));
    this.id = attributes.id || "";
    this.scrolled = false;
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  setAttribute(name, value) {
    this.attributes.set(name, value);
  }

  scrollIntoView() {
    this.scrolled = true;
  }

  matches(selector) {
    if (selector === "[id]") {
      return Boolean(this.id);
    }
    if (selector === "[data-mb-wiki-target]") {
      return this.hasAttribute("data-mb-wiki-target");
    }
    return (
      this.hasAttribute("data-mb-wiki-target") ||
      (this.tagName === "A" && this.hasAttribute("href")) ||
      (["IMG", "AUDIO", "VIDEO", "SOURCE"].includes(this.tagName) && this.hasAttribute("src")) ||
      (this.tagName === "OBJECT" && this.hasAttribute("data"))
    );
  }
}

class FakeContainer extends FakeElement {
  constructor(elements) {
    super("main");
    this.elements = elements;
    this.listeners = new Map();
    for (const element of elements) {
      element.parentElement = this;
    }
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  removeEventListener(name, listener) {
    if (this.listeners.get(name) === listener) {
      this.listeners.delete(name);
    }
  }

  querySelector(selector) {
    const match = /^\[id="((?:[^"\\]|\\.)*)"\]$/s.exec(selector);
    if (!match) {
      return null;
    }
    const id = match[1].replace(/\\(.)/g, "$1");
    return this.elements.find((element) => element.id === id) || null;
  }

  querySelectorAll(selector) {
    if (
      selector ===
      "a[href],img[src],audio[src],video[src],source[src],object[data],[data-mb-wiki-target]"
    ) {
      return this.elements.filter(
        (element) =>
          element.hasAttribute("data-mb-wiki-target") ||
          (element.tagName === "A" && element.hasAttribute("href")) ||
          (["IMG", "AUDIO", "VIDEO", "SOURCE"].includes(element.tagName) &&
            element.hasAttribute("src")) ||
          (element.tagName === "OBJECT" && element.hasAttribute("data")),
      );
    }
    if (selector === "a[href]") {
      return this.elements.filter(
        (element) => element.tagName === "A" && element.hasAttribute("href"),
      );
    }
    if (selector === "[id]") {
      return this.elements.filter((element) => element.id);
    }
    const match = /^(\w+)\[(\w+)]$/.exec(selector);
    return match
      ? this.elements.filter(
          (element) => element.tagName === match[1].toUpperCase() && element.hasAttribute(match[2]),
        )
      : [];
  }
}

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(name, listener) {
    this.listeners.set(name, listener);
  }

  removeEventListener(name, listener) {
    if (this.listeners.get(name) === listener) {
      this.listeners.delete(name);
    }
  }

  dispatch(name, detail) {
    this.listeners.get(name)?.({ detail });
  }
}

function click(target, overrides = {}) {
  const event = {
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
    ...overrides,
  };
  return event;
}

async function loadModule() {
  const linksSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/links.js"),
    "utf8",
  );
  const linksUrl = `data:text/javascript;base64,${Buffer.from(linksSource).toString("base64")}`;
  const projectAdaptersSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/project-adapters.js"),
    "utf8",
  );
  const projectAdaptersUrl = `data:text/javascript;base64,${Buffer.from(projectAdaptersSource).toString("base64")}`;
  const githubLocalizerSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/github-localizer.js"),
    "utf8",
  );
  const githubLocalizerUrl = `data:text/javascript;base64,${Buffer.from(githubLocalizerSource).toString("base64")}`;
  const wikiResolverSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-resolver.js"),
    "utf8",
  );
  const wikiResolverUrl = `data:text/javascript;base64,${Buffer.from(wikiResolverSource).toString("base64")}`;
  const coordinatorSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/reconciliation-coordinator.js"),
      "utf8",
    )
    .replace('"./links.js"', JSON.stringify(linksUrl))
    .replace('"./project-adapters.js"', JSON.stringify(projectAdaptersUrl))
    .replace('"./wiki-resolver.js"', JSON.stringify(wikiResolverUrl));
  const coordinatorUrl = `data:text/javascript;base64,${Buffer.from(coordinatorSource).toString("base64")}`;
  const wikiParserSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-parser.js"),
    "utf8",
  );
  const wikiParserUrl = `data:text/javascript;base64,${Buffer.from(wikiParserSource).toString("base64")}`;
  const workerStub =
    `import {prepareTransclusionMarkdownSource} from ${JSON.stringify(wikiParserUrl)};` +
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
    .replace('"./wiki-parser.js"', JSON.stringify(wikiParserUrl));
  const transclusionUrl = `data:text/javascript;base64,${Buffer.from(transclusionSource).toString("base64")}`;
  const wikiEnhancerSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/wiki-enhancer.js"),
      "utf8",
    )
    .replace('"./transclusion.js"', JSON.stringify(transclusionUrl))
    .replace('"./dom-traversal.js"', JSON.stringify(traversalUrl))
    .replace('"./markdown-worker-client.js"', JSON.stringify(workerUrl))
    .replace('"./reconciliation-coordinator.js"', JSON.stringify(coordinatorUrl));
  const wikiEnhancerUrl = `data:text/javascript;base64,${Buffer.from(wikiEnhancerSource).toString("base64")}`;
  const enhancerSource = fs
    .readFileSync(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown/link-enhancer.js"),
      "utf8",
    )
    .replace('"./github-localizer.js"', JSON.stringify(githubLocalizerUrl))
    .replace('"./links.js"', JSON.stringify(linksUrl))
    .replace('"./dom-traversal.js"', JSON.stringify(traversalUrl))
    .replace('"./markdown-worker-client.js"', JSON.stringify(workerUrl))
    .replace('"./reconciliation-coordinator.js"', JSON.stringify(coordinatorUrl))
    .replace('"./transclusion.js"', JSON.stringify(transclusionUrl))
    .replace('"./wiki-enhancer.js"', JSON.stringify(wikiEnhancerUrl));
  return import(`data:text/javascript;base64,${Buffer.from(enhancerSource).toString("base64")}`);
}

(async () => {
  const module = await loadModule();
  const sameDocument = new FakeElement("a", { href: "#Install" });
  const internal = new FakeElement("a", { href: "guide.md#Install" });
  const published = new FakeElement("a", { href: "/published/", title: "Published guide" });
  const external = new FakeElement("a", { href: "https://example.com/docs" });
  const revision = "a".repeat(40);
  const github = new FakeElement("a", {
    href: `https://github.com/example/docs/blob/${revision}/docs/guide.md#Install`,
  });
  const unsafe = new FakeElement("a", { href: "javascript:alert(1)" });
  const download = new FakeElement("a", { download: "", href: "files/archive.zip" });
  const newTab = new FakeElement("a", { href: "other.md", target: "_blank" });
  const image = new FakeElement("img", { src: "../images/map 1.svg#layer" });
  const remoteImage = new FakeElement("img", { src: "https://example.com/map.svg" });
  const unsafeImage = new FakeElement("img", { src: "data:image/png;base64,AA" });
  const heading = new FakeElement("h2", { id: "Install" });
  // An inert render's heading anchor, which a GitHub address's `#usage` reaches.
  const anchored = new FakeElement("h2", { id: "user-content-usage" });
  const container = new FakeContainer([
    sameDocument,
    internal,
    published,
    external,
    github,
    unsafe,
    download,
    newTab,
    image,
    remoteImage,
    unsafeImage,
    heading,
    anchored,
  ]);
  const eventTarget = new FakeEventTarget();
  const frames = new Map();
  let frameSequence = 0;
  let catalogSnapshotCalls = 0;
  const opened = [];
  let current = { path: "docs/readme.md", fragment: "Install" };
  const mb = {
    repository: {
      branch: "main",
      host: "github.com",
      name: "docs",
      owner: "example",
      revision,
      served_prefix: "",
    },
    fileCatalog: {
      snapshot: () => {
        catalogSnapshotCalls += 1;
        return {
          complete: true,
          files: [
            { basename: "published.md", path: "docs/published.md" },
            { basename: "mkdocs.yml", path: "mkdocs.yml" },
          ],
        };
      },
      subscribe: () => () => {},
    },
    navigation: {
      current: () => current,
      href: (target) => `/view/${target.path}${target.fragment ? `#${target.fragment}` : ""}`,
      open: async (target) => opened.push(target),
    },
  };
  const handle = module.enhanceRenderedLinks(container, "docs/readme.md", mb, {
    cancel: (id) => frames.delete(id),
    eventTarget,
    schedule: (callback) => {
      frameSequence += 1;
      frames.set(frameSequence, callback);
      return frameSequence;
    },
  });

  check("same-document fragment preserved", sameDocument.getAttribute("href") === "#Install");
  check("canonical internal href", internal.getAttribute("href") === "/view/docs/guide.md#Install");
  check(
    "configured published route catalog work is deferred",
    frames.size >= 1 && catalogSnapshotCalls === 0 && !published.hasAttribute("href"),
  );
  const earlyPublishedClick = click(published);
  container.listeners.get("click")(earlyPublishedClick);
  check(
    "published route stays inert before its catalog pass",
    !earlyPublishedClick.defaultPrevented && opened.length === 0,
  );
  check("external href preserved", external.getAttribute("href") === "https://example.com/docs");
  check(
    "verified GitHub href localized",
    github.getAttribute("href") === "/view/docs/guide.md#Install",
  );
  check(
    "GitHub localization disclosed",
    github.getAttribute("data-metabrowser-github-localization") === "revision",
  );
  check("unsafe href removed", !unsafe.hasAttribute("href"));
  check("unsafe link keyboard reachable", unsafe.getAttribute("tabindex") === "0");
  check("unsafe link explained", unsafe.getAttribute("aria-disabled") === "true");
  check(
    "local image raw URL",
    image.getAttribute("src") === "/raw?path=images%2Fmap%201.svg#layer",
  );
  check(
    "remote image preserved",
    remoteImage.getAttribute("src") === "https://example.com/map.svg",
  );
  check("unsafe image source removed", !unsafeImage.hasAttribute("src"));

  for (const callback of [...frames.values()]) {
    callback(0);
  }
  frames.clear();
  check("initial fragment after enhancement", heading.scrolled);
  current = { path: "docs/readme.md", fragment: "usage" };
  eventTarget.dispatch("metabrowser:navigation-fragment", { target: current });
  for (const callback of [...frames.values()]) {
    callback(0);
  }
  frames.clear();
  check("a GitHub fragment reaches its user-content- anchor", anchored.scrolled);
  current = { path: "docs/readme.md", fragment: "Install" };
  check(
    "configured published route href",
    published.getAttribute("href") === "/view/docs/published.md",
  );
  check(
    "a resolved published route keeps its authored title",
    published.getAttribute("title") === "Published guide" &&
      !published.hasAttribute("data-metabrowser-authored-title"),
    String(published.getAttribute("title")),
  );
  check(
    "configured adapter disclosed",
    published.getAttribute("data-metabrowser-link-adapter") === "mkdocs" &&
      catalogSnapshotCalls === 1,
  );

  const internalClick = click(internal);
  container.listeners.get("click")(internalClick);
  await new Promise((resolve) => setImmediate(resolve));
  check("plain click intercepted", internalClick.defaultPrevented);
  check("plain click opened once", opened.length === 1);
  check("resolved click target", opened[0].path === "docs/guide.md");

  const sameDocumentClick = click(sameDocument);
  container.listeners.get("click")(sameDocumentClick);
  await new Promise((resolve) => setImmediate(resolve));
  check("same-document click intercepted", sameDocumentClick.defaultPrevented);
  check("same-document click opened once", opened.length === 2);
  check(
    "same-document click target",
    opened[1].path === "docs/readme.md" && opened[1].fragment === "Install",
    JSON.stringify(opened[1]),
  );

  for (const [name, anchor, overrides] of [
    ["modifier", internal, { metaKey: true }],
    ["middle", internal, { button: 1 }],
    ["download", download, {}],
    ["new browsing context", newTab, {}],
  ]) {
    const nativeClick = click(anchor, overrides);
    container.listeners.get("click")(nativeClick);
    check(`${name} click preserved`, !nativeClick.defaultPrevented);
  }
  check("native variants did not open", opened.length === 2);

  const embeddedFragment = new FakeElement("a", { href: "#Details" });
  const embeddedNewTab = new FakeElement("a", { href: "#Details", target: "_blank" });
  const embeddedContainer = new FakeContainer([embeddedFragment, embeddedNewTab]);
  const embeddedEventTarget = new FakeEventTarget();
  const embeddedHandle = module.enhanceRenderedLinks(embeddedContainer, "docs/embedded.md", mb, {
    cancel: () => {},
    eventTarget: embeddedEventTarget,
    schedule: () => 0,
  });
  check(
    "embedded fragment has canonical native href",
    embeddedFragment.getAttribute("href") === "/view/docs/embedded.md#Details",
    embeddedFragment.getAttribute("href"),
  );
  check(
    "embedded target-blank fragment has canonical native href",
    embeddedNewTab.getAttribute("href") === "/view/docs/embedded.md#Details",
    embeddedNewTab.getAttribute("href"),
  );

  const embeddedClick = click(embeddedFragment);
  embeddedContainer.listeners.get("click")(embeddedClick);
  await new Promise((resolve) => setImmediate(resolve));
  check("embedded plain click intercepted", embeddedClick.defaultPrevented);
  check(
    "embedded plain click target",
    opened[2]?.path === "docs/embedded.md" && opened[2]?.fragment === "Details",
    JSON.stringify(opened[2]),
  );

  const embeddedModifierClick = click(embeddedFragment, { metaKey: true });
  embeddedContainer.listeners.get("click")(embeddedModifierClick);
  check("embedded modifier click preserved", !embeddedModifierClick.defaultPrevented);
  const embeddedNewTabClick = click(embeddedNewTab);
  embeddedContainer.listeners.get("click")(embeddedNewTabClick);
  check("embedded new-tab click preserved", !embeddedNewTabClick.defaultPrevented);
  check("embedded native variants did not delegate", opened.length === 3);

  embeddedHandle.dispose();
  check("embedded dispose removes click listener", !embeddedContainer.listeners.has("click"));
  check(
    "embedded dispose removes fragment listener",
    !embeddedEventTarget.listeners.has("metabrowser:navigation-fragment"),
  );

  const firstAdmittedImage = new FakeElement("img", { src: "first.png" });
  const starvedAnchor = new FakeElement("a", { href: "later.md" });
  let admissionClaims = 0;
  const admissionContainer = new FakeContainer([firstAdmittedImage, starvedAnchor]);
  const admissionHandle = module.enhanceRenderedLinks(admissionContainer, "docs/readme.md", mb, {
    enhancementBudget: {
      claim() {
        admissionClaims += 1;
        return admissionClaims <= 1;
      },
      exhausted() {
        return admissionClaims >= 1;
      },
    },
    cancel() {},
    eventTarget: new FakeEventTarget(),
    schedule: () => 0,
  });
  check(
    "root-wide admission follows DOM order across resource and anchor kinds",
    firstAdmittedImage.getAttribute("src") === "/raw?path=docs%2Ffirst.png" &&
      starvedAnchor.getAttribute("href") === "later.md" &&
      admissionClaims === 2,
  );
  admissionHandle.dispose();

  const aggregateTargets = Array.from({ length: 4097 }, (_, index) =>
    index % 2 === 0
      ? new FakeElement("img", { src: `asset-${index}.png` })
      : new FakeElement("a", { href: `target-${index}.md` }),
  );
  const aggregateContainer = new FakeContainer(aggregateTargets);
  const aggregateHandle = module.enhanceRenderedLinks(aggregateContainer, "docs/readme.md", mb, {
    cancel() {},
    eventTarget: new FakeEventTarget(),
    schedule: () => 0,
  });
  const aggregateEnhanced = aggregateTargets.filter((element) => {
    const target = element.getAttribute(element.tagName === "IMG" ? "src" : "href");
    return target?.startsWith(element.tagName === "IMG" ? "/raw?path=" : "/view/");
  });
  check(
    "production root admission caps one DOM-order prefix across target kinds",
    aggregateEnhanced.length === 4096 &&
      aggregateTargets[4096].getAttribute("src") === "asset-4096.png",
    String(aggregateEnhanced.length),
  );
  aggregateHandle.dispose();

  const dualTargets = Array.from(
    { length: 4096 },
    (_, index) =>
      new FakeElement("a", {
        "data-mb-wiki-action": "navigate",
        "data-mb-wiki-target": `Missing-${index}`,
        href: `wrong-${index}.md`,
      }),
  );
  const dualFrames = new Map();
  let dualFrameSequence = 0;
  const dualSourcePath = `${"provider-segment/".repeat(1200)}readme.md`;
  const dualHandle = module.enhanceRenderedLinks(
    new FakeContainer(dualTargets),
    dualSourcePath,
    mb,
    {
      cancel: (handle) => dualFrames.delete(handle),
      eventTarget: new FakeEventTarget(),
      schedule: (callback) => {
        dualFrameSequence += 1;
        dualFrames.set(dualFrameSequence, callback);
        return dualFrameSequence;
      },
    },
  );
  while (dualFrames.size) {
    const [frame, callback] = dualFrames.entries().next().value;
    dualFrames.delete(frame);
    callback(0);
  }
  check(
    "wiki metadata is authoritative across the root reconciliation ceiling",
    dualTargets.every(
      (target, index) =>
        target.getAttribute("href") === `wrong-${index}.md` &&
        target.getAttribute("data-metabrowser-link-status") === "missing",
    ),
  );
  dualHandle.dispose();

  const publishedAnchors = Array.from(
    { length: 65 },
    (_, index) => new FakeElement("a", { href: `/guide-${String(index).padStart(3, "0")}/` }),
  );
  const publishedContainer = new FakeContainer(publishedAnchors);
  const publishedFrames = new Map();
  let publishedFrameSequence = 0;
  let publishedSnapshot = {
    complete: false,
    files: [{ basename: "mkdocs.yml", path: "mkdocs.yml" }],
  };
  let publishedListener = null;
  const publishedHandle = module.enhanceRenderedLinks(
    publishedContainer,
    "docs/readme.md",
    {
      ...mb,
      fileCatalog: {
        snapshot: () => publishedSnapshot,
        subscribe: (listener) => {
          publishedListener = listener;
          return () => {
            publishedListener = null;
          };
        },
      },
      navigation: { ...mb.navigation, current: () => ({ path: "docs/readme.md" }) },
    },
    {
      cancel: (id) => publishedFrames.delete(id),
      eventTarget: new FakeEventTarget(),
      schedule: (callback) => {
        publishedFrameSequence += 1;
        publishedFrames.set(publishedFrameSequence, callback);
        return publishedFrameSequence;
      },
    },
  );
  check(
    "published routes subscribe while catalog is incomplete",
    typeof publishedListener === "function" &&
      publishedAnchors.every(
        (anchor) =>
          !anchor.hasAttribute("href") &&
          anchor.getAttribute("data-metabrowser-link-status") === "pending",
      ),
  );
  const earlyIncompletePublishedClick = click(publishedAnchors[0]);
  publishedContainer.listeners.get("click")(earlyIncompletePublishedClick);
  check(
    "incomplete published route stays inert before its catalog pass",
    !earlyIncompletePublishedClick.defaultPrevented && opened.length === 3,
  );
  const initialPublishedFrame = [...publishedFrames.entries()][0];
  publishedFrames.delete(initialPublishedFrame[0]);
  initialPublishedFrame[1](0);
  check(
    "initial incomplete route pass is item bounded",
    publishedAnchors.filter((anchor) =>
      anchor.getAttribute("title")?.includes("catalog-incomplete"),
    ).length === 32 && publishedFrames.size === 1,
  );
  publishedSnapshot = {
    complete: true,
    files: [
      ...Array.from({ length: 65 }, (_, index) => ({
        basename: `guide-${String(index).padStart(3, "0")}.md`,
        path: `docs/guide-${String(index).padStart(3, "0")}.md`,
      })),
      { basename: "mkdocs.yml", path: "mkdocs.yml" },
    ],
  };
  publishedListener();
  check("catalog publication defers published-route DOM work", publishedFrames.size === 1);
  check("published route unchanged before continuation", !publishedAnchors[0].hasAttribute("href"));
  const runNextPublishedFrame = () => {
    const next = [...publishedFrames.entries()][0];
    publishedFrames.delete(next[0]);
    next[1](0);
  };
  runNextPublishedFrame();
  check(
    "published-route first continuation is item bounded",
    publishedAnchors.filter((anchor) => anchor.hasAttribute("data-metabrowser-link-adapter"))
      .length === 32 && publishedFrames.size === 1,
  );
  runNextPublishedFrame();
  check(
    "published-route second continuation remains item bounded",
    publishedAnchors.filter((anchor) => anchor.hasAttribute("data-metabrowser-link-adapter"))
      .length === 64 && publishedFrames.size === 1,
  );
  runNextPublishedFrame();
  check(
    "published-route reconciliation settles complete snapshot",
    publishedAnchors.every((anchor) => anchor.hasAttribute("data-metabrowser-link-adapter")) &&
      publishedFrames.size === 0 &&
      publishedListener === null,
  );
  publishedHandle.dispose();

  // A rooted extensionless link on a tree whose walk stopped at the file cap
  // must not say "resolving" forever: the terminal state disables it with an
  // explanation and releases the catalog subscription.
  const cappedAnchor = new FakeElement("a", { href: "/guide/", title: "Authored guide" });
  const cappedFrames = new Map();
  let cappedFrameSequence = 0;
  let cappedListener = null;
  let cappedComplete = false;
  const cappedHandle = module.enhanceRenderedLinks(
    new FakeContainer([cappedAnchor]),
    "docs/readme.md",
    {
      ...mb,
      fileCatalog: {
        snapshot: () => ({
          complete: cappedComplete,
          files: [
            { basename: "guide.md", path: "docs/guide.md" },
            { basename: "mkdocs.yml", path: "mkdocs.yml" },
          ],
          truncated: !cappedComplete,
        }),
        subscribe: (listener) => {
          cappedListener = listener;
          return () => {
            cappedListener = null;
          };
        },
      },
      navigation: { ...mb.navigation, current: () => ({ path: "docs/readme.md" }) },
    },
    {
      cancel: (id) => cappedFrames.delete(id),
      eventTarget: new FakeEventTarget(),
      schedule: (callback) => {
        cappedFrameSequence += 1;
        cappedFrames.set(cappedFrameSequence, callback);
        return cappedFrameSequence;
      },
    },
  );
  while (cappedFrames.size) {
    const [frame, callback] = cappedFrames.entries().next().value;
    cappedFrames.delete(frame);
    callback(0);
  }
  check(
    "a published route on a truncated catalog is disabled with an explanation",
    !cappedAnchor.hasAttribute("href") &&
      cappedAnchor.getAttribute("data-metabrowser-link-status") === "unsupported" &&
      cappedAnchor.getAttribute("aria-disabled") === "true" &&
      cappedAnchor.getAttribute("title") ===
        "Metabrowser cannot resolve this destination (catalog-truncated).",
    String(cappedAnchor.getAttribute("title")),
  );
  check(
    "a truncated catalog keeps the published-route subscription",
    typeof cappedListener === "function",
  );
  cappedComplete = true;
  cappedListener();
  while (cappedFrames.size) {
    const [frame, callback] = cappedFrames.entries().next().value;
    cappedFrames.delete(frame);
    callback(0);
  }
  check(
    "a later complete catalog resolves the published route the cap disabled",
    cappedAnchor.getAttribute("data-metabrowser-link-status") === null &&
      cappedAnchor.getAttribute("aria-disabled") === null &&
      cappedAnchor.getAttribute("data-metabrowser-link-adapter") === "mkdocs" &&
      cappedListener === null,
    `${cappedAnchor.getAttribute("href")} ${cappedAnchor.getAttribute("title")}`,
  );
  cappedHandle.dispose();

  const longDirectory = "provider-segment/".repeat(1200);
  const longSourcePath = `${longDirectory}readme.md`;
  const longSourceAnchor = new FakeElement("a", { href: "next.md" });
  const longSourceWiki = new FakeElement("span", {
    "data-mb-wiki-action": "navigate",
    "data-mb-wiki-target": "./Missing",
  });
  const longSourceContainer = new FakeContainer([longSourceAnchor, longSourceWiki]);
  const longSourceFrames = new Map();
  let longSourceFrameSequence = 0;
  const longSourceHandle = module.enhanceRenderedLinks(
    longSourceContainer,
    longSourcePath,
    {
      ...mb,
      navigation: {
        ...mb.navigation,
        current: () => ({ path: longSourcePath }),
        href: (target) => `/view/${target.path}`,
      },
    },
    {
      cancel: (handle) => longSourceFrames.delete(handle),
      eventTarget: new FakeEventTarget(),
      schedule: (callback) => {
        longSourceFrameSequence += 1;
        longSourceFrames.set(longSourceFrameSequence, callback);
        return longSourceFrameSequence;
      },
    },
  );
  check(
    "provider-long standard source preparation is deferred",
    longSourceAnchor.getAttribute("href") === "next.md" && longSourceFrames.size === 1,
  );
  let longSourceSlices = 0;
  while (longSourceFrames.size) {
    const [frame, callback] = longSourceFrames.entries().next().value;
    longSourceFrames.delete(frame);
    callback(0);
    longSourceSlices += 1;
  }
  check(
    "provider-admitted long source identity resolves in the composed standard and wiki enhancer",
    longSourceAnchor.getAttribute("href") === `/view/${longDirectory}next.md` &&
      longSourceWiki.getAttribute("data-metabrowser-link-status") === "missing" &&
      longSourceSlices > 1,
  );
  longSourceHandle.dispose();

  heading.scrolled = false;
  current = { path: "docs/readme.md", fragment: "Install" };
  eventTarget.dispatch("metabrowser:navigation-fragment", { target: current });
  handle.dispose();
  check("dispose removes click listener", !container.listeners.has("click"));
  check(
    "dispose removes fragment listener",
    !eventTarget.listeners.has("metabrowser:navigation-fragment"),
  );
  check("dispose cancels pending scroll", frames.size === 0);

  // On a pinned GitHub mirror the served tree is addressed by GitPath wire, so a
  // localized github.com link is too, and a tree link keeps its trailing slash.
  const githubPinBlob = new FakeElement("a", {
    href: `https://github.com/example/docs/blob/main/docs/guide.md#L3-L4`,
  });
  const githubPinTree = new FakeElement("a", {
    href: "https://github.com/example/docs/tree/main/docs",
  });
  const githubPinContainer = new FakeContainer([githubPinBlob, githubPinTree]);
  const githubPinHandle = module.enhanceRenderedLinks(
    githubPinContainer,
    "g1-UkVBRE1FLm1k",
    { ...mb, sourceKind: () => "git_revision" },
    { cancel: () => {}, eventTarget: new FakeEventTarget(), schedule: () => 0 },
  );
  check(
    "pinned GitHub blob link localized to a GitPath wire",
    githubPinBlob.getAttribute("href") === "/view/g1-ZG9jcw/g1-Z3VpZGUubWQ#L3-L4",
  );
  check(
    "pinned GitHub tree link keeps its trailing slash",
    githubPinTree.getAttribute("href") === "/view/g1-ZG9jcw/",
  );
  githubPinHandle.dispose();

  // A large rendered document: most elements are neither links nor ids, and
  // the container exposes a real-DOM TreeWalker. Every in-document navigation
  // must still scroll, however many came before it.
  const deepHeading = new FakeElement("h2", { id: "Deep" });
  const largeElements = Array.from({ length: 18_000 }, () => new FakeElement("p"));
  largeElements.push(new FakeElement("a", { href: "#Deep" }), deepHeading);
  const largeContainer = new FakeContainer(largeElements);
  largeContainer.ownerDocument = {
    createTreeWalker() {
      let index = 0;
      return { nextNode: () => largeElements[index++] || null };
    },
  };
  const largeFrames = [];
  const largeEventTarget = new FakeEventTarget();
  let largeCurrent = { path: "docs/large.md", fragment: "" };
  const largeHandle = module.enhanceRenderedLinks(
    largeContainer,
    "docs/large.md",
    { ...mb, navigation: { ...mb.navigation, current: () => largeCurrent } },
    {
      cancel: () => {},
      eventTarget: largeEventTarget,
      schedule: (callback) => largeFrames.push(callback),
    },
  );
  let largeScrolls = 0;
  for (let navigation = 0; navigation < 12; navigation += 1) {
    deepHeading.scrolled = false;
    largeCurrent = { path: "docs/large.md", fragment: "Deep" };
    largeEventTarget.dispatch("metabrowser:navigation-fragment", { target: largeCurrent });
    while (largeFrames.length > 0) {
      largeFrames.shift()(0);
    }
    largeScrolls += deepHeading.scrolled ? 1 : 0;
  }
  check(
    "every in-document navigation in a large document scrolls",
    largeScrolls === 12,
    String(largeScrolls),
  );
  largeHandle.dispose();

  // A pinned Git revision addresses files by GitPath wire, so a relative link
  // in a rendered document resolves into that spelling rather than into a
  // filesystem identity. The enhancer learns which subject it is rendering
  // from the SDK, and this is the only place that answer is observable end to
  // end: drop it and every link below silently resolves to a path the pin has
  // no object for.
  const pinnedLink = new FakeElement("a", { href: "guide.md#Install" });
  const pinnedParentLink = new FakeElement("a", { href: "../top.md" });
  const pinnedImage = new FakeElement("img", { src: "images/map 1.svg" });
  const pinnedExternal = new FakeElement("a", { href: "https://example.com/docs" });
  const pinnedContainer = new FakeContainer([
    pinnedLink,
    pinnedParentLink,
    pinnedImage,
    pinnedExternal,
  ]);
  const pinnedMb = { ...mb, sourceKind: () => "git_revision" };
  const pinnedHandle = module.enhanceRenderedLinks(
    pinnedContainer,
    "g1-ZG9jcw/g1-cmVhZG1lLm1k",
    pinnedMb,
    { cancel: () => {}, eventTarget: new FakeEventTarget(), schedule: () => 0 },
  );
  check(
    "pinned sibling link resolves to a GitPath wire",
    pinnedLink.getAttribute("href") === "/view/g1-ZG9jcw/g1-Z3VpZGUubWQ#Install",
    pinnedLink.getAttribute("href"),
  );
  check(
    "pinned parent link resolves to a GitPath wire",
    pinnedParentLink.getAttribute("href") === "/view/g1-dG9wLm1k",
    pinnedParentLink.getAttribute("href"),
  );
  check(
    "pinned image source resolves to a GitPath wire",
    pinnedImage.getAttribute("src") === "/raw?path=g1-ZG9jcw%2Fg1-aW1hZ2Vz%2Fg1-bWFwIDEuc3Zn",
    pinnedImage.getAttribute("src"),
  );
  check(
    "pinned external href is untouched",
    pinnedExternal.getAttribute("href") === "https://example.com/docs",
    pinnedExternal.getAttribute("href"),
  );
  pinnedHandle.dispose();

  if (failures.length) {
    console.error(`markdown link enhancer FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  if (process.argv.includes("--report")) {
    console.log(
      JSON.stringify(
        {
          crossDocumentHref: internal.getAttribute("href"),
          embeddedDelegatedTarget: opened[2],
          embeddedFragmentHref: embeddedFragment.getAttribute("href"),
          embeddedModifierClickPrevented: embeddedModifierClick.defaultPrevented,
          embeddedNewTabClickPrevented: embeddedNewTabClick.defaultPrevented,
          embeddedTargetBlankHref: embeddedNewTab.getAttribute("href"),
          sameDocumentDelegatedTarget: opened[1],
          sameDocumentHref: sameDocument.getAttribute("href"),
        },
        null,
        2,
      ),
    );
  } else {
    console.log("markdown link enhancer OK");
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
