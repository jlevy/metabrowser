// Browserless session: the diagram frame Mermaid lays untrusted diagrams out in
// (builtin_plugins/markdown/diagram-frame.js), run as production code.
//
// Mermaid lays a diagram out in a document before KPress shows it as an image, and there
// the diagram's own CSS can load a URL. A text from a pull request is laid out in a frame
// whose own policy loads nothing, so it is bounded on a page with no policy of its own.
// That the browser enforces the frame's policy is platform behavior, measured in headless
// Chrome (tests/test_markdown_diagrams_chrome.py). What Metabrowser decides runs here:
//
// - `framePolicy`: scripts only from the frame's entry and the Mermaid bundle's directory,
//   the frame's stylesheet and inline style, `data:` images, and nothing else;
// - the frame: sandboxed to scripts and its origin, hidden, out of the tab order, its
//   document the policy, then the stylesheet, then the entry;
// - the SDK's `moduleUrl`, read through asset-loader.js's `moduleSource`;
// - leases: the first lease's `mermaid()` opens the one frame, every other lease shares
//   it and its one Mermaid import, and the last release removes it;
// - the frame's Mermaid: `initialize` gets the frame's own copy of the configuration, and
//   `render` lays the diagram out in a host in the frame's document carrying the measuring
//   host's style, returns only the SVG text, and removes the host; an image shape's
//   failure says that its image is not loaded;
// - a render in flight when the frame closes rejects, so KPress's queue of Mermaid calls
//   moves on; a released lease's `mermaid()` rejects; a later lease opens a new frame;
// - a frame taken out of the page or navigated away closes as a release does, and the
//   lease's next render opens a new frame with the binding's configuration;
// - a frame whose entry never ran, a frame released or taken out before it loaded, and a
//   page with no Mermaid bundle each reject, and none of them is kept.
//
// The page's DOM is a small one of this file's own. A frame "loads" a turn after it is
// put in the page, as a srcdoc frame does, and its window holds the real entry
// (diagram-frame-entry.js), which imports the Mermaid bundle's URL: a fixture module
// (diagram-frame-mermaid-fixture.mjs) whose Mermaid is this session's, recording calls.
//
// Prints the transcript as JSON, with `failures`; exits 1 on any failure.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const { createSdkSandbox } = require("./sdk-sandbox.js");

const repoRoot = path.resolve(__dirname, "../..");
const rootUrl = pathToFileURL(repoRoot).href;
const markdownRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");
const fixtureUrl = pathToFileURL(path.join(__dirname, "diagram-frame-mermaid-fixture.mjs")).href;
/** A URL as the transcript names it: relative to the package, or else the repository. */
const shown = (url) =>
  String(url).replaceAll(`${rootUrl}/src/metabrowser/`, "").replaceAll(`${rootUrl}/`, "");

const failures = [];
function check(name, condition, detail = undefined) {
  if (!condition) {
    failures.push(detail === undefined ? name : `${name}: ${JSON.stringify(detail)}`);
  }
}

// ---------------------------------------------------------------------------------------
// The page's DOM, and each frame's.

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.parentNode = null;
    this.attributes = new Map();
    this.style = {};
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  get isConnected() {
    return this.parentNode !== null;
  }

  remove() {
    const parent = this.parentNode;
    if (parent) {
      parent.children = parent.children.filter((node) => node !== this);
      this.parentNode = null;
      // A MutationObserver's records arrive a microtask later.
      queueMicrotask(() => {
        for (const observer of [...observers]) {
          if (observer.target === parent) {
            observer.callback([]);
          }
        }
      });
    }
  }
}

/** The page's MutationObservers, watching a parent's children. */
const observers = new Set();
globalThis.MutationObserver = class {
  constructor(callback) {
    this.callback = callback;
    this.target = null;
  }

  observe(target, options) {
    if (options?.childList) {
      this.target = target;
      observers.add(this);
    }
  }

  disconnect() {
    observers.delete(this);
  }
};

class FakeBody {
  constructor() {
    this.children = [];
    this.style = {};
  }

  append(node) {
    node.parentNode = this;
    this.children.push(node);
    node.attached?.();
  }
}

/** How the next frame put in the page starts. */
let nextStart = "starts";
/** Every frame put in the page, in order. */
const frames = [];
/** Configurations a frame's `structuredClone` made, as that frame's own objects. */
const frameClones = new WeakSet();
/** The Mermaid bundle URLs a frame's entry imported. */
const imports = [];
/** The real entry's API, captured once (`main`). */
let entry = null;

class FakeFrame extends FakeElement {
  constructor() {
    super("iframe");
    this.listeners = [];
    this.contentWindow = null;
    this.contentDocument = null;
    this.start = nextStart;
  }

  addEventListener(type, listener) {
    if (type === "load") {
      this.listeners.push(listener);
    }
  }

  // A srcdoc frame loads a turn after it is in the page, if it still is.
  attached() {
    frames.push(this);
    setTimeout(() => {
      if (!this.parentNode || this.start === "never-loads") {
        return;
      }
      const body = new FakeBody();
      this.contentDocument = { body, createElement: (tag) => new FakeElement(tag) };
      const pagehide = [];
      this.navigate = () => {
        for (const listener of pagehide.splice(0)) {
          listener();
        }
      };
      this.contentWindow = {
        addEventListener(type, listener) {
          if (type === "pagehide") {
            pagehide.push(listener);
          }
        },
        structuredClone(value) {
          const copy = structuredClone(value);
          frameClones.add(copy);
          return copy;
        },
      };
      if (this.start === "starts") {
        this.contentWindow.metabrowserDiagramFrame = {
          load(url) {
            imports.push(shown(url));
            return entry.load(url);
          },
        };
      }
      for (const listener of this.listeners.splice(0)) {
        listener();
      }
    }, 0);
  }
}

const body = new FakeBody();
globalThis.document = {
  body,
  createElement: (tag) => (tag === "iframe" ? new FakeFrame() : new FakeElement(tag)),
};

/** The frames in the page now. */
const inPage = () => body.children.filter((node) => node instanceof FakeFrame).length;

// ---------------------------------------------------------------------------------------
// The frame's Mermaid.

const calls = [];
/** A render held until the session lets it go. */
let hold = null;
globalThis.diagramFrameSessionMermaid = {
  initialize(config) {
    calls.push({ initialize: config.theme, theFramesOwnCopy: frameClones.has(config) });
  },
  render(id, text, into) {
    const frame = frames.at(-1);
    calls.push({
      render: id,
      text,
      hostStyle: into.style.cssText,
      inTheFramesDocument: into.parentNode === frame.contentDocument.body,
    });
    if (text === "held") {
      return new Promise((resolve) => {
        hold = resolve;
      });
    }
    if (text === "broken") {
      return Promise.reject(new Error("Parse error on line 1"));
    }
    if (text.includes("img:")) {
      return Promise.reject(new Error("The source image cannot be decoded."));
    }
    return Promise.resolve({ svg: `<svg id="${id}"></svg>`, bindFunctions() {} });
  },
};

// The production SDK (plugin-sdk.js with plugin-sdk-views.js) and asset loader, whose
// `moduleUrl` reads the bundles the server publishes: one with the fixture as its
// `mermaid` bundle, and one with none.
const assetLoader = path.join(repoRoot, "src/metabrowser/static/asset-loader.js");
const sdkSandbox = (bundles) => {
  const sandbox = createSdkSandbox({
    METABROWSER_ASSET_BUNDLES: bundles,
    location: { href: "http://127.0.0.1:8000/pull/7", origin: "http://127.0.0.1:8000" },
  });
  vm.runInContext(fs.readFileSync(assetLoader, "utf8"), sandbox, { filename: assetLoader });
  return sandbox.metabrowser;
};
const published = sdkSandbox({ mermaid: [{ module: fixtureUrl }] });
const unpublished = sdkSandbox({});
const sdk = (url = fixtureUrl) => (url ? published : unpublished);

const settle = () => new Promise((resolve) => setTimeout(resolve, 5));

/** What a promise settled to, as the transcript names it. */
async function outcome(promise) {
  try {
    const value = await promise;
    return { resolved: value && typeof value === "object" ? Object.keys(value) : value };
  } catch (error) {
    return { rejected: error.message };
  }
}

function unescapeAttribute(value) {
  return value
    .replaceAll("&quot;", '"')
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&");
}

/**
 * A frame as the page holds it: its attributes, style, and srcdoc's policy, stylesheet,
 * and script.
 */
function describeFrame(frame) {
  const policy = /content="([^"]*)"/.exec(frame.srcdoc)?.[1] ?? null;
  const stylesheet = /<link rel="stylesheet" href="([^"]*)">/.exec(frame.srcdoc)?.[1] ?? null;
  const script = /<script type="module" src="([^"]*)"><\/script>/.exec(frame.srcdoc)?.[1] ?? null;
  const at = (text) => frame.srcdoc.indexOf(text);
  return {
    className: frame.className,
    sandbox: frame.getAttribute("sandbox"),
    tabIndex: frame.tabIndex,
    ariaHidden: frame.getAttribute("aria-hidden"),
    style: frame.style,
    policyThenStylesheetThenScript:
      at("Content-Security-Policy") < at("<link") && at("<link") < at("<script"),
    policy: policy === null ? null : shown(unescapeAttribute(policy)),
    stylesheet: stylesheet === null ? null : shown(unescapeAttribute(stylesheet)),
    script: script === null ? null : shown(unescapeAttribute(script)),
  };
}

async function main() {
  // The frame's entry, run once: it installs the loader a frame's window holds.
  await import(pathToFileURL(path.join(markdownRoot, "diagram-frame-entry.js")).href);
  entry = globalThis.metabrowserDiagramFrame;
  delete globalThis.metabrowserDiagramFrame;
  const frameModule = await import(pathToFileURL(path.join(markdownRoot, "diagram-frame.js")).href);
  const { framePolicy, leaseDiagramFrame } = frameModule;
  const transcript = {};

  // --- The policy, for a page's stamped addresses.
  transcript.policy = framePolicy(
    "http://127.0.0.1:8000/plugin-static/markdown/0a1b/diagram-frame-entry.js",
    "http://127.0.0.1:8000/static/0a1b/vendor/mermaid/mermaid.esm.min.mjs",
    "http://127.0.0.1:8000/plugin-static/markdown/0a1b/diagram-frame.css",
  ).split("; ");
  transcript.entry = { frozen: Object.isFrozen(entry), keys: Object.keys(entry) };

  // --- The SDK's address of a module bundle: absolute against the page, and null for a
  //     script bundle or an unknown name.
  {
    const page = sdkSandbox({
      mermaid: [{ module: "/static/0a1b/vendor/mermaid/mermaid.esm.min.mjs" }],
      chart: [{ src: "/static/0a1b/vendor/chart.umd.min.js" }],
    });
    transcript.moduleUrl = Object.fromEntries(
      ["mermaid", "chart", "absent"].map((name) => [name, page.moduleUrl(name)]),
    );
    check(
      "a module bundle's address is absolute, and anything else has none",
      transcript.moduleUrl.mermaid ===
        "http://127.0.0.1:8000/static/0a1b/vendor/mermaid/mermaid.esm.min.mjs" &&
        transcript.moduleUrl.chart === null &&
        transcript.moduleUrl.absent === null,
      transcript.moduleUrl,
    );
  }

  // --- A lease opens nothing until KPress asks for Mermaid; then the one frame.
  {
    const first = leaseDiagramFrame(sdk());
    const beforeAsking = inPage();
    const firstMermaid = first.mermaid();
    const whileLoading = inPage();
    const api = await firstMermaid;
    const second = leaseDiagramFrame(sdk());
    const secondApi = await second.mermaid();
    const askedAgain = await first.mermaid();
    transcript.leases = {
      framesBeforeAsking: beforeAsking,
      framesWhileLoading: whileLoading,
      framesWithTwoLeases: inPage(),
      framesEverOpened: frames.length,
      askingAgainIsTheSameMermaid: askedAgain === api,
      eachLeaseHasItsOwnMermaid: secondApi !== api,
      mermaidImports: imports.splice(0),
      frame: describeFrame(frames[0]),
    };
    check(
      "one frame, opened when Mermaid is first asked for, and one import",
      beforeAsking === 0 &&
        whileLoading === 1 &&
        inPage() === 1 &&
        frames.length === 1 &&
        askedAgain === api &&
        transcript.leases.mermaidImports.length === 1,
      transcript.leases,
    );
    const markdownUrl = `${rootUrl}/src/metabrowser/builtin_plugins/markdown`;
    check(
      "the frame is sandboxed, and its policy is in its document before anything it loads",
      transcript.leases.frame.sandbox === "allow-scripts allow-same-origin" &&
        transcript.leases.frame.policyThenStylesheetThenScript &&
        transcript.leases.frame.script === "builtin_plugins/markdown/diagram-frame-entry.js" &&
        transcript.leases.frame.stylesheet === "builtin_plugins/markdown/diagram-frame.css" &&
        transcript.leases.frame.policy ===
          shown(
            framePolicy(
              `${markdownUrl}/diagram-frame-entry.js`,
              fixtureUrl,
              `${markdownUrl}/diagram-frame.css`,
            ),
          ),
      transcript.leases.frame,
    );

    // --- KPress's calls, as image placement makes them.
    const host = {
      style: { cssText: "position: fixed; font-family: trebuchet ms; font-size: 16px;" },
    };
    api.initialize({ theme: "dark", flowchart: { diagramPadding: 48 } });
    const drawn = await api.render("kpress-diagram-1", "flowchart LR; A --> B", host);
    const hostsAfterDrawing = frames[0].contentDocument.body.children.length;
    const broken = await outcome(api.render("kpress-diagram-2", "broken", host));
    const hostsAfterFailing = frames[0].contentDocument.body.children.length;
    const image = await outcome(
      api.render(
        "kpress-diagram-3",
        'flowchart LR\n  A@{ img: "https://example.com/a.png" }',
        host,
      ),
    );
    transcript.mermaid = {
      calls: calls.splice(0),
      drawn,
      hostsAfterDrawing,
      broken,
      hostsAfterFailing,
      imageShape: image,
    };
    check(
      "initialize gets the frame's own copy, and render lays out in the frame",
      transcript.mermaid.calls[0].theFramesOwnCopy &&
        transcript.mermaid.calls[1].inTheFramesDocument &&
        transcript.mermaid.calls[1].hostStyle === host.style.cssText &&
        JSON.stringify(Object.keys(drawn)) === '["svg"]' &&
        hostsAfterDrawing === 0 &&
        hostsAfterFailing === 0 &&
        broken.rejected === "Parse error on line 1" &&
        image.rejected ===
          "Images in diagrams from untrusted text, such as a pull request's, are not loaded",
      transcript.mermaid,
    );

    // --- Releasing: the frame stays while a lease holds it, and a render in flight when
    //     the last lease goes rejects.
    first.release();
    first.release();
    const framesAfterOneRelease = inPage();
    const released = await outcome(first.mermaid());
    const releasedRenders = await outcome(api.render("kpress-diagram-4", "flowchart LR; A", host));
    const held = secondApi.render("kpress-diagram-5", "held", host);
    await settle();
    second.release();
    const inFlight = await outcome(held);
    hold?.({ svg: "<svg></svg>" });
    transcript.release = {
      framesAfterOneRelease,
      releasedLeaseAsks: released,
      releasedLeaseRenders: releasedRenders,
      framesAfterTheLast: inPage(),
      renderInFlight: inFlight,
    };
    calls.splice(0);
    check(
      "the last release removes the frame and ends what was in flight",
      framesAfterOneRelease === 1 &&
        released.rejected === "The diagram frame's lease was released" &&
        releasedRenders.rejected === "The diagram frame's lease was released" &&
        inPage() === 0 &&
        inFlight.rejected === "The diagram frame closed",
      transcript.release,
    );
  }

  // --- A later lease opens a new frame, with its own Mermaid import.
  {
    const lease = leaseDiagramFrame(sdk());
    const outcomeOfAsking = await outcome(lease.mermaid());
    transcript.reopened = {
      outcome: outcomeOfAsking,
      framesEverOpened: frames.length,
      framesInPage: inPage(),
      mermaidImports: imports.splice(0).length,
    };
    lease.release();
    check(
      "a later lease opens a fresh frame",
      frames.length === 2 && transcript.reopened.framesInPage === 1 && inPage() === 0,
      transcript.reopened,
    );
  }

  // --- A frame that goes other than by release, taken out of the page or navigated away,
  //     closes: a render in flight rejects, and the lease's next render opens a new frame
  //     and gives it the binding's configuration.
  {
    const lease = leaseDiagramFrame(sdk());
    const api = await lease.mermaid();
    const host = { style: { cssText: "font-size: 16px;" } };
    api.initialize({ theme: "neutral" });
    const before = frames.length;
    const removed = api.render("kpress-diagram-6", "held", host);
    await settle();
    frames.at(-1).remove();
    const removedInFlight = await outcome(removed);
    hold?.({ svg: "<svg></svg>" });
    const framesAfterRemoval = inPage();
    const redrawn = await outcome(api.render("kpress-diagram-7", "flowchart LR; A", host));
    const navigated = api.render("kpress-diagram-8", "held", host);
    await settle();
    frames.at(-1).navigate();
    const navigatedInFlight = await outcome(navigated);
    hold?.({ svg: "<svg></svg>" });
    const framesAfterNavigating = inPage();
    const redrawnAgain = await outcome(api.render("kpress-diagram-9", "flowchart LR; B", host));
    const framesReopened = frames.length - before;
    lease.release();
    const rendered = calls.splice(0);
    transcript.lost = {
      removedInFlight,
      framesAfterRemoval,
      redrawn,
      navigatedInFlight,
      framesAfterNavigating,
      redrawnAgain,
      framesReopened,
      framesInPage: inPage(),
      mermaidImports: imports.splice(0).length,
      newFramesGotTheConfiguration: rendered
        .filter((call) => call.initialize)
        .map((call) => call.initialize),
    };
    check(
      "a frame taken out or navigated away ends what was in flight, and the next render reopens",
      removedInFlight.rejected === "The diagram frame closed" &&
        framesAfterRemoval === 0 &&
        redrawn.resolved?.[0] === "svg" &&
        navigatedInFlight.rejected === "The diagram frame closed" &&
        framesAfterNavigating === 0 &&
        redrawnAgain.resolved?.[0] === "svg" &&
        framesReopened === 2 &&
        inPage() === 0 &&
        transcript.lost.newFramesGotTheConfiguration.join() === "neutral,neutral,neutral",
      transcript.lost,
    );
  }

  // --- Frames that fail to start are not kept, and the next lease starts again.
  {
    nextStart = "entry-missing";
    const missing = leaseDiagramFrame(sdk());
    const entryMissing = await outcome(missing.mermaid());
    const framesAfterMissing = inPage();
    nextStart = "starts";
    const next = leaseDiagramFrame(sdk());
    const afterMissing = await outcome(next.mermaid());
    next.release();
    missing.release();

    nextStart = "never-loads";
    const early = leaseDiagramFrame(sdk());
    const asked = outcome(early.mermaid());
    await settle();
    early.release();
    const releasedBeforeLoading = await asked;

    const taken = leaseDiagramFrame(sdk());
    const takenAsked = outcome(taken.mermaid());
    await settle();
    frames.at(-1).remove();
    const takenOutBeforeLoading = await takenAsked;
    taken.release();
    nextStart = "starts";

    const unpublished = leaseDiagramFrame(sdk(null));
    const framesBefore = frames.length;
    const noBundle = await outcome(unpublished.mermaid());
    unpublished.release();
    transcript.failedStarts = {
      entryMissing,
      framesAfterMissing,
      nextLeaseAfterMissing: afterMissing,
      releasedBeforeLoading,
      takenOutBeforeLoading,
      noBundle,
      framesOpenedWithNoBundle: frames.length - framesBefore,
      framesInPage: inPage(),
      mermaidImports: imports.splice(0).length,
    };
    check(
      "a frame that fails to start is removed and none is kept",
      entryMissing.rejected === "The diagram frame did not start" &&
        framesAfterMissing === 0 &&
        afterMissing.resolved !== undefined &&
        releasedBeforeLoading.rejected === "The diagram frame closed" &&
        takenOutBeforeLoading.rejected === "The diagram frame closed" &&
        noBundle.rejected === "The Mermaid module bundle is not published" &&
        transcript.failedStarts.framesOpenedWithNoBundle === 0 &&
        inPage() === 0,
      transcript.failedStarts,
    );
  }

  transcript.failures = failures;
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  process.exit(failures.length === 0 ? 0 : 1);
}

main().catch((error) => {
  process.stderr.write(`${error?.stack ?? error}\n`);
  process.exit(1);
});
