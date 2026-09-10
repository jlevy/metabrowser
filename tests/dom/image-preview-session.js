// Browserless image-preview session using the production SDK and renderer.

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
  }

  set innerHTML(value) {
    innerHtmlWrites += 1;
    this._innerHTML = String(value);
    this.replaceChildren();
  }

  get innerHTML() {
    return this._innerHTML;
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
  fetch: () => Promise.reject(new Error("fetch is unavailable in the image session")),
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

(async () => {
  const compositor = sandbox.MetabrowserViewComposition;
  const descriptor = {
    id: "preview",
    label: "Image",
    default: true,
    container_class: "content-body metabrowser-image-host",
    render_runtime: "client",
  };
  let rendererLoaded = false;
  const assetRequests = [];
  const ensureKindAssets = async (kind) => {
    assetRequests.push(kind);
    if (!rendererLoaded) {
      runProduction("src/metabrowser/builtin_plugins/image/index.js");
      rendererLoaded = true;
    }
  };
  const prepare = (isCurrent = () => true) =>
    compositor.prepare({
      kind: "image",
      views: [descriptor],
      preferredViewId: "preview",
      ensureKindAssets,
      getRegisteredView: sandbox.metabrowser.getRegisteredView,
      isCurrent,
    });

  assert(
    sandbox.metabrowser.getRegisteredView("image", "preview") === null,
    "image renderer was eager instead of loading through composition",
  );
  const prepared = await prepare();
  const renderer = prepared.views[0]?.renderer;
  assert(prepared.status === "ready", "image composition did not become ready");
  assert(renderer && typeof renderer.render === "function", "image preview did not register");

  const lifecycle = compositor.createLifecycle();
  const host = document.createElement("main");
  const firstContainer = document.createElement("section");
  const firstStage = lifecycle.begin();
  const hostilePath = 'images/<unsafe "quoted" & file>.png';
  const firstStatus = await compositor.mount(
    firstContainer,
    renderer,
    { kind: "image", path: hostilePath },
    firstStage.disposers,
  );
  const rendererInnerHtmlWrites = innerHtmlWrites;
  const firstImage = firstContainer.children[0];
  const firstMount = {
    alt: firstImage?.getAttribute("alt"),
    childCount: firstContainer.children.length,
    className: firstImage?.getAttribute("class"),
    committed: firstStage.commit(() => host.replaceChildren(firstContainer)),
    hasInlineHandler: Array.from(firstImage?.attributes.keys() || []).some((name) =>
      name.startsWith("on"),
    ),
    rawUrl: firstImage?.getAttribute("src"),
    status: firstStatus,
    tagName: firstImage?.tagName,
  };

  const secondContainer = document.createElement("section");
  const secondStage = lifecycle.begin();
  const secondPath = "next/diagram #2.svg";
  const secondStatus = await compositor.mount(
    secondContainer,
    renderer,
    { kind: "image", path: secondPath },
    secondStage.disposers,
  );
  const secondImage = secondContainer.children[0];
  const replacement = {
    committed: secondStage.commit(() => host.replaceChildren(secondContainer)),
    firstDetached: firstImage.parentNode === null,
    secondAlt: secondImage?.getAttribute("alt"),
    secondRawUrl: secondImage?.getAttribute("src"),
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
    { kind: "image", path: "cancelled.png" },
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
    { kind: "image", path: "broken.png" },
    errorStage.disposers,
    { onError: (error) => loggedErrors.push(error.message) },
  );
  const errorCommitted = errorStage.commit(() => host.replaceChildren(errorContainer));

  const cancelledPreparation = await prepare(() => false);
  const missingView = await compositor.prepare({
    kind: "image",
    views: [{ id: "missing" }],
    ensureKindAssets,
    getRegisteredView: sandbox.metabrowser.getRegisteredView,
  });

  lifecycle.disposeActive();
  lifecycle.disposeActive();
  const disposal = {
    activeContainerCount: host.children.length,
    idempotent: secondContainer.children.length === 0,
    secondDetached: secondImage.parentNode === null,
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
  };

  assert(firstMount.tagName === "IMG", "renderer did not construct an image element");
  assert(firstMount.childCount === 1, "renderer did not replace the container contents");
  assert(firstMount.className === "file-image", "renderer lost its plugin style hook");
  assert(firstMount.alt === hostilePath, "renderer changed the image alternative text");
  assert(
    firstMount.rawUrl === "/raw?path=images%2F%3Cunsafe%20%22quoted%22%20%26%20file%3E.png",
    "renderer did not encode the raw-file path",
  );
  assert(!firstMount.hasInlineHandler, "renderer emitted an inline event handler");
  assert(rendererInnerHtmlWrites === 0, "image renderer constructed markup with innerHTML");
  assert(replacement.firstDetached, "replacement retained the prior image");
  assert(replacement.staleCommitPreservedReplacement, "stale commit removed the replacement");
  assert(cancellation.lateHandleDisposed, "cancelled async renderer leaked its late handle");
  assert(error.accessible && error.status === "error", "renderer error was not accessible");
  assert(disposal.idempotent && disposal.secondDetached, "active disposal was not idempotent");
  assert(composition.missingRenderer, "missing registry entry was not preserved for fallback");

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
