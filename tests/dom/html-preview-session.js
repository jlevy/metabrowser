// Browserless HTML-preview session using the production SDK and renderer.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
let innerHtmlWrites = 0;

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = String(tagName).toUpperCase();
    this.ownerDocument = ownerDocument;
    this.parentNode = null;
    this.children = [];
    this.attributes = new Map();
    this._innerHTML = "";
    this._textContent = "";
  }

  set innerHTML(value) {
    innerHtmlWrites += 1;
    this._innerHTML = String(value);
    this.replaceChildren();
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set textContent(value) {
    this._textContent = String(value);
    this.replaceChildren();
  }

  get textContent() {
    return this._textContent;
  }

  setAttribute(name, value) {
    this.attributes.set(String(name), String(value));
  }

  getAttribute(name) {
    return this.attributes.get(String(name)) ?? null;
  }

  hasAttribute(name) {
    return this.attributes.has(String(name));
  }

  removeAttribute(name) {
    this.attributes.delete(String(name));
  }

  replaceChildren(...children) {
    for (const child of this.children) {
      child.parentNode = null;
    }
    this.children = [];
    for (const child of children) {
      if (child.parentNode) {
        child.remove();
      }
      child.parentNode = this;
      this.children.push(child);
    }
  }

  remove() {
    if (!this.parentNode) {
      return;
    }
    const parent = this.parentNode;
    parent.children = parent.children.filter((child) => child !== this);
    this.parentNode = null;
  }
}

const document = {
  addEventListener() {},
  querySelector() {
    return null;
  },
  querySelectorAll() {
    return [];
  },
  documentElement: {},
};
document.createElement = (tagName) => new FakeElement(tagName, document);
document.head = document.createElement("head");

const sandbox = {
  console,
  document,
  encodeURIComponent,
  fetch: () => Promise.reject(new Error("fetch is unavailable in the html session")),
  location: { origin: "http://127.0.0.1:8411" },
  Map,
  Promise,
  Set,
  URL,
  clearInterval,
  clearTimeout,
  setInterval,
  setTimeout,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

function runProduction(relative) {
  const absolute = path.join(repoRoot, relative);
  vm.runInContext(fs.readFileSync(absolute, "utf8"), sandbox, { filename: absolute });
}

for (const relative of [
  "src/metabrowser/static/request-error.js",
  "src/metabrowser/static/formatters.js",
  "src/metabrowser/static/inventory-scope.js",
  "src/metabrowser/static/contribution-registry.js",
  "src/metabrowser/static/resource-context.js",
  "src/metabrowser/static/view-state.js",
  "src/metabrowser/static/navigation.js",
  "src/metabrowser/static/plugin-sdk.js",
  "src/metabrowser/static/view-composition.js",
]) {
  runProduction(relative);
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function sandboxTokens(value) {
  return new Set(String(value).trim().split(/\s+/).filter(Boolean));
}

(async () => {
  const compositor = sandbox.MetabrowserViewComposition;
  const descriptor = {
    id: "preview",
    label: "Preview",
    default: true,
    container_class: "content-body metabrowser-html-host",
    render_runtime: "client",
  };
  let rendererLoaded = false;
  const assetRequests = [];
  const ensureKindAssets = async (kind) => {
    assetRequests.push(kind);
    if (!rendererLoaded) {
      runProduction("src/metabrowser/builtin_plugins/html/index.js");
      rendererLoaded = true;
    }
  };
  const prepare = (isCurrent = () => true) =>
    compositor.prepare({
      kind: "html",
      views: [descriptor],
      preferredViewId: "preview",
      ensureKindAssets,
      getRegisteredView: sandbox.metabrowser.getRegisteredView,
      isCurrent,
    });

  assert(
    sandbox.metabrowser.getRegisteredView("html", "preview") === null,
    "html renderer was eager instead of loading through composition",
  );
  const prepared = await prepare();
  const renderer = prepared.views[0]?.renderer;
  assert(prepared.status === "ready", "html composition did not become ready");
  assert(renderer && typeof renderer.render === "function", "html preview did not register");

  const lifecycle = compositor.createLifecycle();
  const host = document.createElement("main");
  const firstContainer = document.createElement("section");
  const firstStage = lifecycle.begin();
  const hostilePath = 'docs/<unsafe "quoted" & file>.html';
  const firstStatus = await compositor.mount(
    firstContainer,
    renderer,
    { kind: "html", path: hostilePath },
    firstStage.disposers,
  );
  const rendererInnerHtmlWrites = innerHtmlWrites;
  const firstBar = firstContainer.children[0];
  const firstOpenLink = firstBar?.children[0];
  const firstFrame = firstContainer.children[1];
  const firstSandbox = firstFrame?.getAttribute("sandbox") ?? "";
  const firstTokens = sandboxTokens(firstSandbox);
  const inlineHandler = (element) =>
    Array.from(element?.attributes.keys() || []).some((name) => name.startsWith("on"));
  const firstMount = {
    barClassName: firstBar?.getAttribute("class"),
    barTagName: firstBar?.tagName,
    childCount: firstContainer.children.length,
    className: firstFrame?.getAttribute("class"),
    committed: firstStage.commit(() => host.replaceChildren(firstContainer)),
    hasAllowSameOrigin: firstTokens.has("allow-same-origin"),
    hasAllowTopNavigation: firstTokens.has("allow-top-navigation"),
    hasInlineHandler: inlineHandler(firstFrame) || inlineHandler(firstOpenLink),
    openClassName: firstOpenLink?.getAttribute("class"),
    openHref: firstOpenLink?.getAttribute("href"),
    openLabel: firstOpenLink?.textContent,
    openRel: firstOpenLink?.getAttribute("rel"),
    openTagName: firstOpenLink?.tagName,
    openTarget: firstOpenLink?.getAttribute("target"),
    openTipText: firstOpenLink?.getAttribute("data-tip-text"),
    openTracksFrameSource: firstOpenLink?.getAttribute("href") === firstFrame?.getAttribute("src"),
    rawUrl: firstFrame?.getAttribute("src"),
    referrerPolicy: firstFrame?.getAttribute("referrerpolicy"),
    sandbox: firstSandbox,
    status: firstStatus,
    tagName: firstFrame?.tagName,
    title: firstFrame?.getAttribute("title"),
  };

  const secondContainer = document.createElement("section");
  const secondStage = lifecycle.begin();
  const secondPath = "docs/100%25.html";
  const secondStatus = await compositor.mount(
    secondContainer,
    renderer,
    { kind: "html", path: secondPath },
    secondStage.disposers,
  );
  const secondBar = secondContainer.children[0];
  const secondFrame = secondContainer.children[1];
  const replacement = {
    committed: secondStage.commit(() => host.replaceChildren(secondContainer)),
    firstBarDetached: firstBar.parentNode === null,
    firstDetached: firstFrame.parentNode === null,
    secondOpenHref: secondBar?.children[0]?.getAttribute("href"),
    secondRawUrl: secondFrame?.getAttribute("src"),
    staleCommitRejected: firstStage.commit(() => host.replaceChildren(firstContainer)) === false,
    staleCommitPreservedReplacement: host.children[0] === secondContainer,
    status: secondStatus,
  };

  let finishCancelledRender = null;
  let lateHandleDisposed = false;
  const cancelledStage = lifecycle.begin();
  const cancelledMount = compositor.mount(
    document.createElement("section"),
    {
      render() {
        return new Promise((resolve) => {
          finishCancelledRender = () => resolve({ dispose: () => (lateHandleDisposed = true) });
        });
      },
    },
    { kind: "html", path: "cancelled.html" },
    cancelledStage.disposers,
  );
  const cancelledBeforeSettle = cancelledStage.cancel();
  finishCancelledRender();
  const cancelledStatus = await cancelledMount;

  const errorContainer = document.createElement("section");
  const errorStage = lifecycle.begin();
  const loggedErrors = [];
  const errorStatus = await compositor.mount(
    errorContainer,
    {
      render() {
        throw new Error("broken renderer");
      },
    },
    { kind: "html", path: "broken.html" },
    errorStage.disposers,
    { onError: (error) => loggedErrors.push(error.message) },
  );
  const errorCommitted = errorStage.commit(() => host.replaceChildren(errorContainer));

  const cancelledPreparation = await prepare(() => false);
  const missingView = await compositor.prepare({
    kind: "html",
    views: [{ id: "missing" }],
    ensureKindAssets,
    getRegisteredView: sandbox.metabrowser.getRegisteredView,
  });

  lifecycle.disposeActive();
  lifecycle.disposeActive();
  const disposal = {
    activeContainerCount: host.children.length,
    idempotent: secondContainer.children.length === 0,
    secondBarDetached: secondBar.parentNode === null,
    secondDetached: secondFrame.parentNode === null,
    secondSrcCleared: secondFrame.getAttribute("src") === null,
  };
  const cancellation = {
    cancelledBeforeSettle,
    lateHandleDisposed,
    status: cancelledStatus,
  };
  const error = {
    accessible: errorContainer.innerHTML.includes('role="alert"'),
    committed: errorCommitted,
    logged: loggedErrors,
    status: errorStatus,
  };
  const composition = {
    assetRequests,
    cancelledPreparation: cancelledPreparation.status,
    initialView: prepared.initialView?.id,
    missingRenderer: missingView.views[0]?.renderer === null,
    registeredAfterAssets: Boolean(renderer),
    sourceRegistered: sandbox.metabrowser.getRegisteredView("html", "source") !== null,
  };

  assert(firstMount.tagName === "IFRAME", "renderer did not construct an iframe");
  assert(firstMount.childCount === 2, "renderer did not replace the container contents");
  assert(firstMount.className === "file-html-preview", "renderer lost its plugin style hook");
  assert(firstMount.barTagName === "DIV", "renderer did not construct the preview toolbar");
  assert(firstMount.openTagName === "A", "the full-page control is not a real anchor");
  assert(firstMount.openLabel === "Open as full page", "the full-page control lost its label");
  assert(firstMount.openTarget === "_blank", "the full-page control does not open a new tab");
  assert(
    firstMount.openRel === "noopener noreferrer",
    "the full-page control leaked an opener or a referrer",
  );
  assert(firstMount.openTipText, "the full-page control has no tooltip");
  // The href and the iframe src come from one raw URL, so the framed document
  // and the full-page tab can never address different files.
  assert(
    firstMount.openTracksFrameSource,
    "the full-page control does not address the framed document",
  );
  assert(firstMount.title === hostilePath, "renderer changed the iframe title");
  assert(
    firstMount.rawUrl === "/raw/docs/%3Cunsafe%20%22quoted%22%20%26%20file%3E.html",
    "renderer did not use a path-shaped raw URL",
  );
  assert(!firstMount.rawUrl.includes("?path="), "renderer used the query-form raw URL");
  assert(
    firstMount.sandbox === "allow-scripts allow-popups allow-forms allow-downloads",
    "renderer changed the iframe sandbox tokens",
  );
  assert(!firstMount.hasAllowSameOrigin, "iframe sandbox granted same-origin");
  assert(!firstMount.hasAllowTopNavigation, "iframe sandbox granted top navigation");
  assert(firstMount.referrerPolicy === "no-referrer", "iframe omitted no-referrer");
  assert(!firstMount.hasInlineHandler, "renderer emitted an inline event handler");
  assert(rendererInnerHtmlWrites === 0, "html renderer constructed markup with innerHTML");
  assert(replacement.firstDetached, "replacement retained the prior iframe");
  assert(replacement.firstBarDetached, "replacement retained the prior toolbar");
  assert(
    replacement.secondRawUrl === "/raw/docs/100%25.html",
    "percent identity was not encoded as a filesystem /raw URL",
  );
  assert(
    replacement.secondOpenHref === replacement.secondRawUrl,
    "the replacement full-page control kept the prior document",
  );
  assert(replacement.staleCommitPreservedReplacement, "stale commit removed the replacement");
  assert(cancellation.lateHandleDisposed, "cancelled async renderer leaked its late handle");
  assert(error.accessible && error.status === "error", "renderer error was not accessible");
  assert(disposal.idempotent && disposal.secondDetached, "active disposal was not idempotent");
  assert(disposal.secondBarDetached, "disposal left the preview toolbar mounted");
  assert(disposal.secondSrcCleared, "disposal left the iframe src attached");
  assert(composition.missingRenderer, "missing registry entry was not preserved for fallback");
  assert(composition.sourceRegistered, "html source view did not register");

  console.log(
    JSON.stringify(
      {
        cancellation,
        composition,
        disposal,
        error,
        firstMount,
        innerHtmlWrites: rendererInnerHtmlWrites,
        replacement,
      },
      null,
      2,
    ),
  );
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
