// Browserless session: Metabrowser's host for KPress's Mermaid diagrams.
//
// KPress draws a document's Mermaid figures (`js/diagrams.js`) and gives each a toolbar
// and a zoom and pan dialog (`js/diagram-controls.js`); KPress tests that drawing, the
// controls, their keys, and the view arithmetic itself, with vitest and happy-dom. What
// Metabrowser decides around them runs here as production code:
//
// - place-rendered.js#drawDiagrams imports the host only for a root that holds a diagram,
//   and asks for an inert render's diagrams as images;
// - diagrams.js#mountDiagrams loads both KPress modules through `mb.ensureModule`, turns
//   an inert render's `<pre lang="mermaid">` back into a figure, and hands KPress the
//   placement, a Mermaid loader, the page's theme and its runtime, and controls whose
//   buttons carry the app's tooltip (`decorateButton`) and whose copy button is the
//   shell's copy delegate;
// - mermaid-view.js#mermaidFence is the Markdown a `.mmd` file's Diagram view renders.
//
// The two KPress modules are stubs that `ensureModule` returns. Each records what it
// receives and draws nothing. As KPress's do, `initKpressDiagrams` attaches the controls
// to each figure under the root and its `dispose` runs what each attach returned, and the
// controls' `attach` makes the copy button with its label and hands it to the host's
// `decorate` and then `copy`. The DOM is a small one of this file's own: elements and
// text, attributes, a little HTML parsing, and compound selectors. The owner mark is the
// production SDK's (sdk-sandbox.js).
//
// Prints the transcript as JSON, with `failures`; exits 1 on any failure.

const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { createSdkSandbox } = require("./sdk-sandbox.js");

const repoRoot = path.resolve(__dirname, "../..");
const markdownRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins/markdown");
const moduleUrl = (name) => pathToFileURL(path.join(markdownRoot, name)).href;

const failures = [];
function check(name, condition, detail = undefined) {
  if (!condition) {
    failures.push(detail === undefined ? name : `${name}: ${JSON.stringify(detail)}`);
  }
}

// ---------------------------------------------------------------------------------------
// The session's DOM.

class Node {
  constructor(ownerDocument) {
    this.ownerDocument = ownerDocument;
    this.parentNode = null;
    this.childNodes = [];
  }

  get children() {
    return this.childNodes.filter((node) => node instanceof Element);
  }

  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }

  append(...nodes) {
    for (const node of nodes) {
      const child = typeof node === "string" ? new Text(this.ownerDocument, node) : node;
      child.remove();
      child.parentNode = this;
      this.childNodes.push(child);
    }
  }

  insertBefore(node, reference) {
    node.remove();
    node.parentNode = this;
    const index = reference ? this.childNodes.indexOf(reference) : -1;
    if (index < 0) {
      this.childNodes.push(node);
    } else {
      this.childNodes.splice(index, 0, node);
    }
    return node;
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.childNodes = this.parentNode.childNodes.filter((node) => node !== this);
      this.parentNode = null;
    }
  }

  replaceWith(node) {
    const parent = this.parentNode;
    if (parent) {
      parent.insertBefore(node, this);
      this.remove();
    }
  }

  descendants() {
    return this.children.flatMap((child) => [child, ...child.descendants()]);
  }

  querySelectorAll(selector) {
    const compounds = parseSelector(selector);
    return this.descendants().filter((node) =>
      compounds.some((compound) => matchesCompound(node, compound)),
    );
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

class Text extends Node {
  constructor(ownerDocument, value) {
    super(ownerDocument);
    this.value = value;
  }

  get textContent() {
    return this.value;
  }
}

class Element extends Node {
  constructor(ownerDocument, tagName) {
    super(ownerDocument);
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map();
  }

  set innerHTML(value) {
    for (const child of [...this.childNodes]) {
      child.remove();
    }
    this.append(...parseHtml(this.ownerDocument, String(value)));
  }

  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  removeAttribute(name) {
    this.attributes.delete(name);
  }

  matches(selector) {
    return parseSelector(selector).some((compound) => matchesCompound(this, compound));
  }

  closest(selector) {
    for (let node = this; node instanceof Element; node = node.parentNode) {
      if (node.matches(selector)) {
        return node;
      }
    }
    return null;
  }
}

class Document extends Node {
  constructor() {
    super(null);
    this.ownerDocument = this;
    this.documentElement = new Element(this, "html");
    this.body = new Element(this, "body");
    this.documentElement.append(this.body);
    this.append(this.documentElement);
  }

  createElement(tag) {
    return new Element(this, tag);
  }
}

const VOID = new Set(["br", "img", "hr", "input", "meta", "link"]);
const decode = (text) =>
  text
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&");
const encode = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function parseHtml(ownerDocument, html) {
  const root = new Element(ownerDocument, "template");
  let current = root;
  const pattern =
    /<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)((?:\s+[\w:-]+(?:="[^"]*")?)*)\s*(\/?)>|([^<]+)/g;
  for (const match of html.matchAll(pattern)) {
    if (match[1]) {
      current = current.parentNode || root;
    } else if (match[2]) {
      const element = new Element(ownerDocument, match[2]);
      for (const attribute of (match[3] || "").matchAll(/([\w:-]+)(?:="([^"]*)")?/g)) {
        element.attributes.set(attribute[1], decode(attribute[2] ?? ""));
      }
      current.append(element);
      if (!match[4] && !VOID.has(match[2].toLowerCase())) {
        current = element;
      }
    } else if (match[5]) {
      current.append(new Text(ownerDocument, decode(match[5])));
    }
  }
  return [...root.childNodes];
}

// A selector list of compound selectors: `tag.class[attr="value"]`. Anything else is a
// selector the host did not use when this session was written, and fails loudly.
function parseSelector(selector) {
  return selector.split(",").map((part) => {
    const text = part.trim();
    const match = /^([a-z][a-z0-9-]*)?((?:\.[\w-]+)*)((?:\[[\w-]+(?:="[^"]*")?\])*)$/i.exec(text);
    if (!match || !text) {
      throw new Error(`the session's DOM has no selector ${JSON.stringify(text)}`);
    }
    return {
      attributes: [...match[3].matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)].map((entry) => [
        entry[1],
        entry[2],
      ]),
      classes: match[2].split(".").filter(Boolean),
      tag: match[1]?.toUpperCase() ?? null,
    };
  });
}

function matchesCompound(element, compound) {
  const classes = (element.getAttribute?.("class") || "").split(/\s+/);
  return (
    element instanceof Element &&
    (compound.tag === null || element.tagName === compound.tag) &&
    compound.classes.every((name) => classes.includes(name)) &&
    compound.attributes.every(([name, value]) =>
      value === undefined ? element.hasAttribute(name) : element.getAttribute(name) === value,
    )
  );
}

// ---------------------------------------------------------------------------------------
// The page, the SDK, and KPress's two modules.

const document = new Document();
globalThis.document = document;
document.documentElement.setAttribute("data-theme", "light");

const themeListeners = new Set();
const themeRuntime = {
  subscribe(listener) {
    themeListeners.add(listener);
    return () => themeListeners.delete(listener);
  },
};
globalThis.MetabrowserTheme = themeRuntime;

// Every warning the host writes, taken by the section that expects it.
const warnings = [];
console.warn = (message, error) => {
  warnings.push([message, error instanceof Error ? error.message : String(error)]);
};

const sandbox = createSdkSandbox();
const ownsElement = sandbox.MetabrowserPluginHost.ownsElement;

/** What `ensureModule("mermaid")` returns: the vendored entry's module namespace. */
const MERMAID_MODULE = Object.freeze({ default: { name: "the vendored Mermaid" } });

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const FIGURE_SELECTOR = '[data-kpress-diagram="mermaid"]';

/** KPress's `js/diagrams.js` and `js/diagram-controls.js`, as stubs that record. */
function createKpress() {
  const kpress = {
    /** Hold each binding's `ready` until the session resolves it. */
    holdReady: false,
    /** The blocks `mermaidFigureFor` wrapped. */
    wrapped: [],
    /** Each `initKpressDiagrams` call: its options, figures, and disposals. */
    bindings: [],
    /** Each `diagramControls` call: its options, and the buttons its `attach` made. */
    controls: [],
  };
  kpress.diagrams = {
    // As KPress's: the block moves into a figure that holds it as its source.
    mermaidFigureFor(element) {
      kpress.wrapped.push(element);
      const figure = document.createElement("figure");
      figure.setAttribute("class", "kpress-diagram kpress-mermaid");
      figure.setAttribute("data-kpress-diagram", "mermaid");
      element.replaceWith(figure);
      figure.append(element);
      return figure;
    },
    // As KPress's: binds every figure under *root*, attaches the controls to each, and
    // runs what each attach returned when disposed. It draws nothing.
    initKpressDiagrams(root, options) {
      const binding = {
        options,
        figures: root.querySelectorAll(FIGURE_SELECTOR),
        ready: deferred(),
        cleanups: [],
        disposals: 0,
      };
      if (!kpress.holdReady) {
        binding.ready.resolve();
      }
      kpress.bindings.push(binding);
      for (const figure of binding.figures) {
        binding.cleanups.push(options.controls.attach(figure));
      }
      return {
        figures: binding.figures,
        ready: binding.ready.promise,
        rerender() {},
        dispose() {
          binding.disposals += 1;
          for (const cleanup of binding.cleanups.splice(0)) {
            cleanup();
          }
        },
      };
    },
  };
  kpress.diagramControls = {
    // As KPress's: `attach` labels the copy button, lets the host decorate it, then hands
    // it to the host's `copy` with the figure's source text.
    diagramControls(options) {
      const made = {
        options,
        buttons: [],
        detached: 0,
        attach(figure) {
          const button = document.createElement("button");
          button.setAttribute("aria-label", "Copy diagram source");
          button.setAttribute("title", "Copy diagram source");
          options.decorate?.(button, "copy");
          options.copy?.(button, (figure.querySelector("code") ?? figure).textContent.trim());
          made.buttons.push(button);
          return () => {
            made.detached += 1;
          };
        },
      };
      kpress.controls.push(made);
      return made;
    },
  };
  return kpress;
}

/**
 * The SDK the host receives: `ensureModule` records each name and returns the stub, and
 * `ownDelegate` is the production SDK's, recorded.
 */
function createSdk(kpress, { gate = null, fail = null, ownDelegate = true } = {}) {
  const modules = {
    "kpress-diagrams": kpress.diagrams,
    "kpress-diagram-controls": kpress.diagramControls,
    mermaid: MERMAID_MODULE,
  };
  const sdk = {
    asked: [],
    owned: [],
    async ensureModule(name) {
      sdk.asked.push(name);
      if (gate) {
        await gate;
      }
      if (name === fail) {
        throw new Error("Failed to fetch dynamically imported module");
      }
      return modules[name];
    },
  };
  if (ownDelegate) {
    sdk.ownDelegate = (element) => {
      sdk.owned.push(element);
      return sandbox.metabrowser.ownDelegate(element);
    };
  }
  return sdk;
}

function figureMarkup(source) {
  return (
    `<figure class="kpress-diagram kpress-mermaid" data-kpress-diagram="mermaid">` +
    `<pre class="kpress-diagram-source"><code class="language-mermaid">${encode(source)}</code></pre></figure>`
  );
}

function article(html) {
  const root = document.createElement("div");
  root.setAttribute("class", "content-body");
  root.innerHTML = html;
  document.body.append(root);
  return root;
}

function describeButton(button) {
  return {
    label: button.getAttribute("aria-label"),
    tooltip: button.getAttribute("data-tip-text"),
    title: button.getAttribute("title"),
    copy: button.getAttribute("data-mb-copy"),
    copyText: button.getAttribute("data-mb-copy-text"),
    copyLabel: button.getAttribute("data-mb-copy-label"),
    ownedByThePage: ownsElement(button),
  };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 5));

// A CommonMark backtick fence read back: the info string and the text inside, or null
// when the fence never closes before the end.
function readFence(markdown) {
  const lines = markdown.split("\n");
  const open = /^(`{3,})([^`]*)$/.exec(lines[0]);
  if (!open) {
    return null;
  }
  const body = [];
  for (let index = 1; index < lines.length; index += 1) {
    const close = /^ {0,3}(`+)[ \t]*$/.exec(lines[index]);
    if (close && close[1].length >= open[1].length) {
      return {
        info: open[2].trim(),
        text: body.map((line) => `${line}\n`).join(""),
        after: lines.slice(index + 1).join("\n"),
      };
    }
    body.push(lines[index]);
  }
  return null;
}

function roundTrips(markdown, text) {
  const read = readFence(markdown);
  const expected = text.endsWith("\n") ? text : `${text}\n`;
  return read !== null && read.info === "mermaid" && read.text === expected && read.after === "";
}

async function main() {
  const placement = await import(moduleUrl("place-rendered.js"));
  const diagrams = await import(moduleUrl("diagrams.js"));
  const fileView = await import(moduleUrl("mermaid-view.js"));
  const transcript = {};

  // --- A root with no diagram: no handle, and nothing asked for.
  {
    const kpress = createKpress();
    const sdk = createSdk(kpress);
    const plain = article(
      '<p>No diagrams.</p><pre lang="python"><code>print(1)</code></pre><pre><code class="language-mermaid">graph A</code></pre>',
    );
    const handle = placement.drawDiagrams(plain, sdk, false);
    await settle();
    transcript.noDiagram = { handle, modulesAsked: sdk.asked };
    check(
      "a root with no diagram draws nothing",
      handle === null && sdk.asked.length === 0 && kpress.bindings.length === 0,
      transcript.noDiagram,
    );
    plain.remove();
  }

  // --- A trusted render: KPress's figures, drawn in the document.
  {
    const kpress = createKpress();
    kpress.holdReady = true;
    const sdk = createSdk(kpress);
    const trusted = article(
      `<p>Before.</p>${figureMarkup("flowchart LR\n  A --> B")}${figureMarkup("sequenceDiagram\n  Alice->>Bob: Hi")}`,
    );
    const handle = placement.drawDiagrams(trusted, sdk, false);
    let readySettled = false;
    handle.ready.then(() => {
      readySettled = true;
    });
    await settle();
    const [binding] = kpress.bindings;
    const { options } = binding;
    const askedBeforeTheLoader = [...sdk.asked];

    // The Mermaid loader asks for the `mermaid` module only when KPress calls it.
    const loaded = await options.mermaid();
    const askedAfterTheLoader = [...sdk.asked];

    // The default theme is the page's resolved `data-theme`; anything but dark is light.
    const theme = {};
    for (const value of ["dark", "light", "sepia", null]) {
      if (value === null) {
        document.documentElement.removeAttribute("data-theme");
      } else {
        document.documentElement.setAttribute("data-theme", value);
      }
      theme[value === null ? "(none)" : value] = options.theme();
    }
    document.documentElement.setAttribute("data-theme", "light");

    // The default theme subscription is the page's `MetabrowserTheme`, and a no-op
    // without one.
    const heard = [];
    const unsubscribe = options.subscribeTheme(() => heard.push("redraw"));
    const listening = themeListeners.size;
    for (const listener of [...themeListeners]) {
      listener({ mode: "dark", resolved: "dark" });
    }
    unsubscribe();
    delete globalThis.MetabrowserTheme;
    const withoutRuntime = options.subscribeTheme(() => heard.push("never"));
    withoutRuntime();
    globalThis.MetabrowserTheme = themeRuntime;

    const [controls] = kpress.controls;
    transcript.trusted = {
      modulesAsked: askedBeforeTheLoader,
      wrapped: kpress.wrapped.length,
      options: Object.keys(options).sort(),
      placement: options.placement,
      yieldBetween: options.yieldBetween === undefined ? "not passed" : "passed",
      figuresBound: binding.figures.length,
      mermaidLoader: {
        modulesAsked: askedAfterTheLoader.slice(askedBeforeTheLoader.length),
        returnsTheModule: loaded === MERMAID_MODULE,
      },
      theme,
      themeSubscription: {
        listening,
        heard,
        listeningAfterUnsubscribe: themeListeners.size,
        withoutRuntime: typeof withoutRuntime,
      },
      controls: {
        hostHooks: Object.keys(controls.options).sort(),
        handedToKpress: options.controls === controls,
        copyButtons: controls.buttons.map(describeButton),
        delegatesOwned: sdk.owned.length,
      },
      readyBeforeKpress: readySettled,
    };
    check(
      "the KPress modules, then Mermaid only when asked",
      askedBeforeTheLoader.join() === "kpress-diagrams,kpress-diagram-controls" &&
        transcript.trusted.mermaidLoader.modulesAsked.join() === "mermaid",
      { askedBeforeTheLoader, askedAfterTheLoader },
    );
    check("a trusted render is placed in the document", options.placement === "document");
    check(
      "the theme follows data-theme",
      theme.dark === "dark" && theme.light === "light" && theme.sepia === "light",
      theme,
    );
    check(
      "the theme runtime is subscribed and released",
      listening === 1 && heard.join() === "redraw" && themeListeners.size === 0,
      transcript.trusted.themeSubscription,
    );
    const sources = ["flowchart LR\n  A --> B", "sequenceDiagram\n  Alice->>Bob: Hi"];
    check(
      "every copy button is the page's delegate for its source, with the app's tooltip",
      controls.buttons.length === 2 &&
        transcript.trusted.controls.copyButtons.every(
          (button, index) =>
            button.ownedByThePage &&
            button.tooltip === button.label &&
            button.title === null &&
            button.copy === "text" &&
            button.copyText === sources[index] &&
            button.copyLabel === "Copy diagram source",
        ),
      transcript.trusted.controls,
    );
    check("ready waits for KPress's", readySettled === false);

    binding.ready.resolve();
    await handle.ready;
    handle.dispose();
    handle.dispose();
    transcript.trusted.readyAfterKpress = readySettled;
    transcript.trusted.dispose = {
      bindingDisposals: binding.disposals,
      controlsDetached: controls.detached,
      figuresLeft: trusted.querySelectorAll(FIGURE_SELECTOR).length,
    };
    check(
      "disposing twice disposes KPress's binding once and keeps the figures",
      binding.disposals === 1 && controls.detached === 2 && readySettled,
      transcript.trusted.dispose,
    );
    trusted.remove();
  }

  // --- An inert render: GitHub's fallback blocks become figures, drawn as images.
  {
    const kpress = createKpress();
    const sdk = createSdk(kpress);
    const inert = article(
      '<p>Inert.</p><pre lang="mermaid"><code>flowchart LR\n  A --&gt; B</code></pre>' +
        '<pre lang="python"><code>print(1)</code></pre>' +
        '<pre lang="mermaid"><code>graph TD\n  C --&gt; D</code></pre>',
    );
    const handle = placement.drawDiagrams(inert, sdk, true);
    await handle.ready;
    const [binding] = kpress.bindings;
    transcript.inert = {
      modulesAsked: sdk.asked,
      placement: binding.options.placement,
      wrapped: kpress.wrapped.map((pre) => `pre lang=${pre.getAttribute("lang")}`),
      eachInAFigure: kpress.wrapped.every((pre) => pre.parentNode?.matches(FIGURE_SELECTOR)),
      figuresBound: binding.figures.length,
      copyTexts: kpress.controls[0].buttons.map((button) =>
        button.getAttribute("data-mb-copy-text"),
      ),
      otherBlocksLeft: inert.querySelectorAll('pre[lang="python"]')[0].parentNode === inert,
    };
    check(
      "an inert render's blocks are wrapped and placed as images",
      binding.options.placement === "image" &&
        kpress.wrapped.length === 2 &&
        binding.figures.length === 2 &&
        transcript.inert.eachInAFigure,
      transcript.inert,
    );
    handle.dispose();
    inert.remove();
  }

  // --- A block already inside a figure is not wrapped again.
  {
    const kpress = createKpress();
    const sdk = createSdk(kpress);
    const root = article(
      `<figure data-kpress-diagram="mermaid"><pre lang="mermaid"><code>graph A</code></pre></figure>`,
    );
    const mounted = diagrams.mountDiagrams(root, sdk, { mode: "image" });
    await mounted.ready;
    transcript.blockInAFigure = {
      wrapped: kpress.wrapped.length,
      figuresBound: kpress.bindings[0].figures.length,
    };
    check(
      "a figure's own block stays as it is",
      kpress.wrapped.length === 0 && kpress.bindings[0].figures.length === 1,
      transcript.blockInAFigure,
    );
    mounted.dispose();
    root.remove();
  }

  // --- What `mountDiagrams` passes through, and how it names the placement.
  {
    const placementByMode = {};
    for (const mode of ["document", "image", "svg", undefined]) {
      const kpress = createKpress();
      const root = article(figureMarkup("graph A"));
      const mounted = diagrams.mountDiagrams(
        root,
        createSdk(kpress),
        mode === undefined ? undefined : { mode },
      );
      await mounted.ready;
      placementByMode[mode ?? "(none)"] = kpress.bindings[0].options.placement;
      mounted.dispose();
      root.remove();
    }
    const kpress = createKpress();
    const root = article(`${figureMarkup("graph A")}${figureMarkup("graph B")}`);
    const theme = () => "dark";
    const subscribeTheme = () => () => {};
    const yieldBetween = () => Promise.resolve();
    const mounted = diagrams.mountDiagrams(root, createSdk(kpress), {
      mode: "image",
      theme,
      subscribeTheme,
      yieldBetween,
    });
    const figuresBeforeBinding = mounted.figures.length;
    await mounted.ready;
    const { options } = kpress.bindings[0];
    transcript.mountOptions = {
      placementByMode,
      passedThrough: {
        theme: options.theme === theme,
        subscribeTheme: options.subscribeTheme === subscribeTheme,
        yieldBetween: options.yieldBetween === yieldBetween,
      },
      figures: { beforeBinding: figuresBeforeBinding, afterReady: mounted.figures.length },
    };
    check(
      "only image is image",
      placementByMode.image === "image" &&
        placementByMode.document === "document" &&
        placementByMode.svg === "document" &&
        placementByMode["(none)"] === "document",
      placementByMode,
    );
    check(
      "the host's own theme, subscription, and yield reach KPress",
      Object.values(transcript.mountOptions.passedThrough).every(Boolean),
      transcript.mountOptions.passedThrough,
    );
    check(
      "figures fill once KPress has bound",
      figuresBeforeBinding === 0 && mounted.figures.length === 2,
      transcript.mountOptions.figures,
    );
    mounted.dispose();
    root.remove();
  }

  // --- The tooltip decoration, on its own.
  {
    const labelled = document.createElement("button");
    labelled.setAttribute("aria-label", "Zoom in");
    labelled.setAttribute("title", "Zoom in");
    diagrams.decorateButton(labelled);
    const unlabelled = document.createElement("button");
    unlabelled.setAttribute("title", "Close");
    diagrams.decorateButton(unlabelled);
    const describe = (button) => ({
      tooltip: button.getAttribute("data-tip-text"),
      title: button.getAttribute("title"),
    });
    transcript.decorateButton = { labelled: describe(labelled), unlabelled: describe(unlabelled) };
    check(
      "the label becomes the app's tooltip and the browser's goes",
      labelled.getAttribute("data-tip-text") === "Zoom in" &&
        !labelled.hasAttribute("title") &&
        !unlabelled.hasAttribute("data-tip-text") &&
        !unlabelled.hasAttribute("title"),
      transcript.decorateButton,
    );
  }

  // --- The copy hook with an SDK that has no `ownDelegate`.
  {
    const kpress = createKpress();
    const root = article(figureMarkup("graph A"));
    const mounted = diagrams.mountDiagrams(root, createSdk(kpress, { ownDelegate: false }));
    await mounted.ready;
    transcript.copyWithoutOwnDelegate = describeButton(kpress.controls[0].buttons[0]);
    check(
      "the copy attributes are set without an owner",
      transcript.copyWithoutOwnDelegate.copy === "text" &&
        transcript.copyWithoutOwnDelegate.ownedByThePage === false,
      transcript.copyWithoutOwnDelegate,
    );
    mounted.dispose();
    root.remove();
  }

  // --- Disposal before the KPress modules arrive binds nothing.
  {
    const gate = deferred();
    const kpress = createKpress();
    const sdk = createSdk(kpress, { gate: gate.promise });
    const root = article('<pre lang="mermaid"><code>graph A</code></pre>');
    const mounted = diagrams.mountDiagrams(root, sdk, { mode: "image" });
    mounted.dispose();
    gate.resolve();
    await mounted.ready;
    transcript.disposeBeforeModules = {
      modulesAsked: sdk.asked,
      wrapped: kpress.wrapped.length,
      bound: kpress.bindings.length,
      figures: mounted.figures.length,
      warnings: warnings.splice(0),
    };
    check(
      "nothing is wrapped or bound after disposal",
      kpress.wrapped.length === 0 && kpress.bindings.length === 0,
      transcript.disposeBeforeModules,
    );
    root.remove();
  }

  // --- `drawDiagrams` disposed at once, before the host has imported: nothing is asked.
  {
    const kpress = createKpress();
    const sdk = createSdk(kpress);
    const root = article(figureMarkup("graph A"));
    const handle = placement.drawDiagrams(root, sdk, false);
    handle.dispose();
    await handle.ready;
    transcript.drawDisposedAtOnce = { modulesAsked: sdk.asked, bound: kpress.bindings.length };
    check(
      "a handle disposed at once mounts nothing",
      sdk.asked.length === 0 && kpress.bindings.length === 0,
      transcript.drawDisposedAtOnce,
    );
    root.remove();
  }

  // --- A KPress module that fails to load: one warning, and `ready` settles.
  {
    const kpress = createKpress();
    const sdk = createSdk(kpress, { fail: "kpress-diagram-controls" });
    const root = article(figureMarkup("graph A"));
    const handle = placement.drawDiagrams(root, sdk, false);
    const ready = await handle.ready.then(() => "settled");
    handle.dispose();
    transcript.loadFailure = {
      modulesAsked: sdk.asked,
      bound: kpress.bindings.length,
      ready,
      warnings: warnings.splice(0),
    };
    check(
      "a failed load warns once and settles",
      ready === "settled" &&
        kpress.bindings.length === 0 &&
        transcript.loadFailure.warnings.length === 1,
      transcript.loadFailure,
    );
    root.remove();
  }

  // --- The same failure after disposal is silent.
  {
    const gate = deferred();
    const kpress = createKpress();
    const sdk = createSdk(kpress, { gate: gate.promise, fail: "kpress-diagrams" });
    const root = article(figureMarkup("graph A"));
    const mounted = diagrams.mountDiagrams(root, sdk);
    mounted.dispose();
    gate.resolve();
    await mounted.ready;
    transcript.loadFailureAfterDispose = { warnings: warnings.splice(0) };
    check(
      "a failure after disposal is not reported",
      transcript.loadFailureAfterDispose.warnings.length === 0,
      transcript.loadFailureAfterDispose,
    );
    root.remove();
  }

  // --- A `.mmd` file's text as the Markdown its Diagram view renders.
  {
    const cases = [
      ["plain", "flowchart LR\n  A --> B"],
      ["ends in a newline", "flowchart LR\n  A --> B\n"],
      ["a backtick label", 'flowchart LR\n  A["`**bold**`"] --> B'],
      ["a line that is a fence", "graph TD\n```\n  A --> B"],
      ["a longer run inside", 'graph TD\n  A["`````"] --> B\n  C["```"] --> D'],
      ["empty", ""],
    ];
    transcript.mermaidFence = cases.map(([name, text]) => {
      const markdown = fileView.mermaidFence(text);
      const body = text.endsWith("\n") ? text : `${text}\n`;
      return {
        case: name,
        markdown,
        roundTrips: roundTrips(markdown, text),
        aThreeBacktickFenceWould: roundTrips(`\`\`\`mermaid\n${body}\`\`\`\n`, text),
      };
    });
    check(
      "every text reads back whole from its fence",
      transcript.mermaidFence.every((entry) => entry.roundTrips),
      transcript.mermaidFence,
    );
  }

  transcript.warningsLeft = warnings;
  check("no warning is unaccounted for", warnings.length === 0, warnings);
  transcript.failures = failures;
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  if (failures.length) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
