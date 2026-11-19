// Browserless session: a rendered document's Mermaid diagrams (diagrams.js).
//
// The production placement module (place-rendered.js) finds a render's diagrams and
// imports the production renderer, which draws them through a stand-in Mermaid: what
// Mermaid draws is layout, measured in headless Chrome by
// tests/dom/markdown-diagrams-chrome.mjs, and not this session's subject. The DOM is a
// small one of this file's own, enough for the renderer: elements and text, classes,
// attributes and `data-*`, bubbling listeners, a little HTML parsing, and the selectors
// the renderer uses. The SDK's owner mark is the production SDK's (sdk-sandbox.js).
//
// It shows that a document with no diagram imports neither the renderer nor Mermaid;
// that each diagram moves from `source` through `rendering` to `rendered` in document
// order, or to `error` with Mermaid's message and its source shown; that an over-long
// source is refused before Mermaid sees it; that a failed load says so on every figure;
// that an inert render's `<pre lang="mermaid">` becomes a figure drawn as an image; that
// a theme change draws again in the new theme; the toolbar's copy and source toggle; the
// dialog's zoom and pan from buttons, keys, wheel, pinch, and drag; and that disposing
// stops drawing, unsubscribes the theme, and removes the dialog and every listener.
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

let listenerTotal = 0;

class Node {
  constructor(ownerDocument) {
    this.ownerDocument = ownerDocument;
    this.parentNode = null;
    this.childNodes = [];
    this.listeners = new Map();
  }

  get parentElement() {
    return this.parentNode instanceof Element ? this.parentNode : null;
  }

  get children() {
    return this.childNodes.filter((node) => node instanceof Element);
  }

  get textContent() {
    return this.childNodes.map((node) => node.textContent).join("");
  }

  set textContent(value) {
    this.replaceChildren(new Text(this.ownerDocument, String(value)));
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || new Set();
    if (!listeners.has(listener)) {
      listenerTotal += 1;
    }
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type, listener) {
    if (this.listeners.get(type)?.delete(listener)) {
      listenerTotal -= 1;
    }
  }

  dispatchEvent(event) {
    event.target = event.target || this;
    event.defaultPrevented = false;
    event.preventDefault = () => {
      event.defaultPrevented = true;
    };
    for (let node = this; node; node = event.bubbles === false ? null : node.parentNode) {
      for (const listener of [...(node.listeners.get(event.type) || [])]) {
        listener(event);
      }
    }
    return !event.defaultPrevented;
  }

  adopt(nodes) {
    const flat = [];
    for (const node of nodes) {
      if (node instanceof Fragment) {
        flat.push(...node.childNodes);
      } else {
        flat.push(typeof node === "string" ? new Text(this.ownerDocument, node) : node);
      }
    }
    for (const node of flat) {
      node.remove();
      node.parentNode = this;
    }
    return flat;
  }

  append(...nodes) {
    this.childNodes.push(...this.adopt(nodes));
  }

  prepend(...nodes) {
    this.childNodes.unshift(...this.adopt(nodes));
  }

  insertBefore(node, reference) {
    const [adopted] = this.adopt([node]);
    const index = reference ? this.childNodes.indexOf(reference) : -1;
    if (index < 0) {
      this.childNodes.push(adopted);
    } else {
      this.childNodes.splice(index, 0, adopted);
    }
    return adopted;
  }

  replaceChildren(...nodes) {
    for (const child of [...this.childNodes]) {
      child.remove();
    }
    this.append(...nodes);
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

  contains(candidate) {
    for (let node = candidate; node; node = node.parentNode) {
      if (node === this) {
        return true;
      }
    }
    return false;
  }

  descendants() {
    return this.children.flatMap((child) => [child, ...child.descendants()]);
  }

  querySelectorAll(selector) {
    const chains = parseSelector(selector);
    return this.descendants().filter((node) =>
      chains.some((steps) => matchesChain(node, steps, this)),
    );
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
}

class Text extends Node {
  constructor(ownerDocument, value) {
    super(ownerDocument);
    this.nodeType = 3;
    this.value = value;
  }

  get textContent() {
    return this.value;
  }

  set textContent(value) {
    this.value = String(value);
  }

  cloneNode() {
    return new Text(this.ownerDocument, this.value);
  }
}

class Fragment extends Node {}

const kebab = (name) => name.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);

class Element extends Node {
  constructor(ownerDocument, tagName) {
    super(ownerDocument);
    this.nodeType = 1;
    this.tagName = tagName.toUpperCase();
    this.attributes = new Map();
    this.open = false;
    this.focused = false;
    this.captured = [];
    this.dataset = new Proxy(
      {},
      {
        get: (_target, key) =>
          typeof key === "string"
            ? (this.getAttribute(`data-${kebab(key)}`) ?? undefined)
            : undefined,
        set: (_target, key, value) => {
          this.setAttribute(`data-${kebab(String(key))}`, value);
          return true;
        },
      },
    );
    this.style = new Proxy(
      {},
      {
        get: (_target, key) =>
          typeof key === "string" ? (this.styles().get(kebab(key)) ?? "") : undefined,
        set: (_target, key, value) => {
          const styles = this.styles();
          if (value === "" || value === null) {
            styles.delete(kebab(String(key)));
          } else {
            styles.set(kebab(String(key)), String(value));
          }
          this.attributes.set(
            "style",
            [...styles].map(([name, entry]) => `${name}: ${entry};`).join(" "),
          );
          return true;
        },
      },
    );
    this.classList = {
      names: () => (this.getAttribute("class") || "").split(/\s+/).filter(Boolean),
      add: (...names) =>
        this.setAttribute("class", [...new Set([...this.classList.names(), ...names])].join(" ")),
      remove: (...names) =>
        this.setAttribute(
          "class",
          this.classList
            .names()
            .filter((name) => !names.includes(name))
            .join(" "),
        ),
      contains: (name) => this.classList.names().includes(name),
    };
  }

  styles() {
    const styles = new Map();
    for (const declaration of (this.attributes.get("style") || "").split(";")) {
      const colon = declaration.indexOf(":");
      if (colon > 0) {
        styles.set(declaration.slice(0, colon).trim(), declaration.slice(colon + 1).trim());
      }
    }
    return styles;
  }

  get className() {
    return this.getAttribute("class") || "";
  }

  set className(value) {
    this.setAttribute("class", value);
  }

  get id() {
    return this.getAttribute("id") || "";
  }

  get hidden() {
    return this.attributes.has("hidden");
  }

  set hidden(value) {
    if (value) {
      this.attributes.set("hidden", "");
    } else {
      this.attributes.delete("hidden");
    }
  }

  set type(value) {
    this.setAttribute("type", value);
  }

  set alt(value) {
    this.setAttribute("alt", value);
  }

  set src(value) {
    this.setAttribute("src", value);
  }

  get src() {
    return this.getAttribute("src") || "";
  }

  set tabIndex(value) {
    this.setAttribute("tabindex", String(value));
  }

  get content() {
    if (!this.fragment) {
      this.fragment = new Fragment(this.ownerDocument);
    }
    return this.fragment;
  }

  get innerHTML() {
    return this.childNodes.map(serialize).join("");
  }

  set innerHTML(value) {
    const target = this.tagName === "TEMPLATE" ? this.content : this;
    target.replaceChildren(...parseHtml(this.ownerDocument, String(value)));
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
    return parseSelector(selector).some((steps) => matchesChain(this, steps, null));
  }

  closest(selector) {
    for (let node = this; node instanceof Element; node = node.parentNode) {
      if (node.matches(selector)) {
        return node;
      }
    }
    return null;
  }

  cloneNode(deep) {
    const copy = new Element(this.ownerDocument, this.tagName);
    for (const [name, value] of this.attributes) {
      copy.attributes.set(name, value);
    }
    if (deep) {
      copy.append(...this.childNodes.map((node) => node.cloneNode(true)));
    }
    return copy;
  }

  click() {
    this.dispatchEvent({ type: "click", bubbles: true });
  }

  focus() {
    this.focused = true;
  }

  showModal() {
    this.open = true;
  }

  close() {
    this.open = false;
    this.dispatchEvent({ type: "close", bubbles: false });
  }

  setPointerCapture(id) {
    this.captured.push(id);
  }

  // The dialog's viewport is 1000 by 600; its stage holds a diagram of 400 by 200.
  getBoundingClientRect() {
    return { left: 10, top: 20, width: 1000, height: 600 };
  }

  get scrollWidth() {
    return this.classList.contains("metabrowser-diagram-stage") ? 400 : 0;
  }

  get scrollHeight() {
    return this.classList.contains("metabrowser-diagram-stage") ? 200 : 0;
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
  const root = new Fragment(ownerDocument);
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

function serialize(node) {
  if (node instanceof Text) {
    return encode(node.value);
  }
  const tag = node.tagName.toLowerCase();
  const attributes = [...node.attributes]
    .map(([name, value]) => ` ${name}="${encode(value).replace(/"/g, "&quot;")}"`)
    .join("");
  return VOID.has(tag)
    ? `<${tag}${attributes}>`
    : `<${tag}${attributes}>${node.childNodes.map(serialize).join("")}</${tag}>`;
}

function parseCompound(text) {
  const match = /^([a-z][a-z0-9-]*)?((?:\.[\w-]+)*)((?:\[[\w-]+(?:="[^"]*")?\])*)$/i.exec(text);
  if (!match) {
    throw new Error(`the session's DOM has no selector ${text}`);
  }
  return {
    attributes: [...match[3].matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)].map((part) => [
      part[1],
      part[2],
    ]),
    classes: match[2].split(".").filter(Boolean),
    tag: match[1]?.toUpperCase() ?? null,
  };
}

function matchesCompound(element, compound) {
  return (
    element instanceof Element &&
    (compound.tag === null || element.tagName === compound.tag) &&
    compound.classes.every((name) => element.classList.contains(name)) &&
    compound.attributes.every(([name, value]) =>
      value === undefined ? element.hasAttribute(name) : element.getAttribute(name) === value,
    )
  );
}

function matchesChain(element, steps, scope) {
  let current = element;
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const step = steps[index];
    if (index === steps.length - 1) {
      if (!matchesCompound(current, step.compound)) {
        return false;
      }
    } else if (step.compound === ":scope") {
      return step.next === ">" ? current.parentNode === scope : scope.contains(current);
    } else if (step.next === ">") {
      current = current.parentElement;
      if (!current || !matchesCompound(current, step.compound)) {
        return false;
      }
    } else {
      do {
        current = current.parentElement;
      } while (current && !matchesCompound(current, step.compound));
      if (!current) {
        return false;
      }
    }
  }
  return true;
}

function parseSelector(selector) {
  return selector.split(",").map((part) => {
    const tokens = part
      .trim()
      .split(/\s*(>)\s*|\s+/)
      .filter(Boolean);
    const steps = [];
    for (let index = 0; index < tokens.length; index += 1) {
      if (tokens[index] === ">") {
        continue;
      }
      steps.push({
        compound: tokens[index] === ":scope" ? ":scope" : parseCompound(tokens[index]),
        next: tokens[index + 1] === ">" ? ">" : " ",
      });
    }
    return steps;
  });
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

  getElementById(id) {
    return this.descendants().find((node) => node.id === id) ?? null;
  }
}

// ---------------------------------------------------------------------------------------
// The page.

const document = new Document();
globalThis.document = document;
globalThis.XMLSerializer = class {
  serializeToString(node) {
    return serialize(node);
  }
};
const themeListeners = new Set();
globalThis.MetabrowserTheme = {
  subscribe(listener) {
    themeListeners.add(listener);
    return () => themeListeners.delete(listener);
  },
};
globalThis.MetabrowserIcons = { copy: '<svg class="copy-glyph"></svg>' };
document.documentElement.setAttribute("data-theme", "light");

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  for (const listener of [...themeListeners]) {
    listener({ mode: theme, resolved: theme });
  }
}

// A stand-in Mermaid: it records each configuration and render, rejects a source that
// says `fail`, and draws a 400 by 200 SVG naming the theme it was drawn in.
function createMermaid() {
  const calls = { initialize: [], render: [] };
  let theme = "default";
  let gate = null;
  return {
    calls,
    hold() {
      let release;
      gate = new Promise((resolve) => {
        release = resolve;
      });
      return () => {
        gate = null;
        release();
      };
    },
    api: {
      initialize(config) {
        calls.initialize.push(config);
        theme = config.theme;
      },
      async render(id, text, container) {
        calls.render.push({
          id,
          text: text.split("\n")[0],
          source: text,
          host: container?.getAttribute("style") ? "measuring" : "page",
          hostAttached: container ? document.body.contains(container) : null,
        });
        if (gate) {
          await gate;
        }
        if (text.includes("fail")) {
          throw new Error("Parse error on line 2:\nfail\n^");
        }
        return {
          svg: `<svg id="${id}" viewBox="0 0 400 200" style="max-width: 400px;" data-theme="${theme}"><g><text>${encode(text.split("\n")[0])}</text></g></svg>`,
        };
      },
    },
  };
}

function figureMarkup(source) {
  return (
    '<figure class="kpress-diagram kpress-mermaid" data-kpress-diagram="mermaid" data-kpress-diagram-provider="mermaid" data-kpress-diagram-status="source">' +
    `<pre class="kpress-diagram-source"><code class="language-mermaid">${encode(source)}</code></pre></figure>`
  );
}

function article(html) {
  const root = document.createElement("div");
  root.className = "content-body";
  root.innerHTML = html;
  document.body.append(root);
  return root;
}

function describeFigure(figure) {
  const rendered = figure.querySelector(":scope > .kpress-diagram-rendered");
  const source = figure.querySelector(":scope > .kpress-diagram-source");
  const error = figure.querySelector(":scope > .metabrowser-diagram-error");
  const drawing = rendered?.children[0];
  return {
    status: figure.dataset.kpressDiagramStatus,
    drawing: drawing
      ? drawing.tagName === "IMG"
        ? "image"
        : `svg in ${drawing.getAttribute("data-theme")} theme`
      : null,
    drawingShown: rendered ? !rendered.hidden : null,
    sourceShown: source ? !source.hidden : null,
    error: error ? error.querySelector("pre").textContent.split("\n")[0] : null,
  };
}

function describeToolbar(figure, sdk) {
  const toolbar = figure.querySelector(":scope > .metabrowser-diagram-toolbar");
  const copy = toolbar.querySelector(".metabrowser-diagram-copy");
  return {
    buttons: toolbar.children.map((button) => button.getAttribute("aria-label")),
    copies: copy.getAttribute("data-mb-copy-text"),
    copyIsOwned: sdk.ownsElement(copy),
    toggle: toolbar.querySelector(".metabrowser-diagram-toggle-source").getAttribute("aria-label"),
  };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 5));

async function main() {
  const placement = await import(moduleUrl("place-rendered.js"));
  const diagrams = await import(moduleUrl("diagrams.js"));
  const fileView = await import(moduleUrl("mermaid-view.js"));
  const sandbox = createSdkSandbox();
  const sdk = {
    ownDelegate: sandbox.metabrowser.ownDelegate,
    ownsElement: sandbox.MetabrowserPluginHost.ownsElement,
  };
  const transcript = {};

  // --- The view arithmetic the dialog runs.
  const content = { width: 400, height: 200 };
  const viewport = { width: 1000, height: 600 };
  const sizes = { content, viewport };
  let view = diagrams.fitView(content, viewport);
  const steps = [{ action: "fit", view }];
  for (const action of [
    "zoom-in",
    "zoom-in",
    "pan-left",
    "pan-up",
    "zoom-out",
    "pan-right",
    "pan-down",
    "reset",
  ]) {
    view = diagrams.viewAction(view, action, sizes);
    steps.push({ action, view });
  }
  let clamp = { scale: 1, x: 0, y: 0 };
  for (let index = 0; index < 40; index += 1) {
    clamp = diagrams.viewAction(clamp, "zoom-in", sizes);
  }
  const zoomedIn = clamp.scale;
  for (let index = 0; index < 80; index += 1) {
    clamp = diagrams.viewAction(clamp, "zoom-out", sizes);
  }
  transcript.view = {
    steps,
    bounds: { most: zoomedIn, least: clamp.scale },
    largeDiagramFits: diagrams.fitView({ width: 4000, height: 300 }, viewport),
    keys: Object.fromEntries(
      ["+", "=", "-", "_", "0", "ArrowUp", "ArrowLeft", "a"].map((key) => [
        key,
        diagrams.keyAction({ key }),
      ]),
    ),
    keyWithCommand: diagrams.keyAction({ key: "+", metaKey: true }),
    pinch: diagrams.wheelView(
      { scale: 1, x: 0, y: 0 },
      { deltaX: 0, deltaY: -100, ctrlKey: true },
      { x: 100, y: 100 },
    ),
    scroll: diagrams.wheelView(
      { scale: 1, x: 0, y: 0 },
      { deltaX: 30, deltaY: 40 },
      { x: 100, y: 100 },
    ),
    transform: diagrams.viewTransform({ scale: 1.5, x: -20, y: 10 }),
  };
  check(
    "fit centers a small diagram, enlarged to the cap",
    steps[0].view.scale === diagrams.MAX_FIT_SCALE,
    steps[0],
  );
  check(
    "reset returns to the fit",
    JSON.stringify(steps.at(-1).view) === JSON.stringify(steps[0].view),
    steps,
  );
  check(
    "zoom stops at its bounds",
    zoomedIn === diagrams.MAX_SCALE && clamp.scale === diagrams.MIN_SCALE,
    transcript.view.bounds,
  );

  transcript.config = {
    light: diagrams.mermaidConfig("light"),
    dark: diagrams.mermaidConfig("dark").theme,
  };
  check("strict security, as the plan says", transcript.config.light.securityLevel === "strict");

  // --- A document with no diagram imports nothing.
  const plain = article("<p>No diagrams.</p><pre><code>flowchart LR</code></pre>");
  const ensured = [];
  const mb = {
    ensureModule: async (name) => {
      ensured.push(name);
      return { default: mermaid.api };
    },
    ownDelegate: sdk.ownDelegate,
  };
  let mermaid = createMermaid();
  transcript.noDiagram = {
    handle: placement.drawDiagrams(plain, mb, false),
    modulesAsked: [...ensured],
  };
  check(
    "a diagram-free document draws nothing",
    transcript.noDiagram.handle === null && ensured.length === 0,
  );
  plain.remove();

  // --- A trusted render: two diagrams and a broken one, in document order.
  const trusted = article(
    `<p>Before.</p>${figureMarkup("flowchart LR\n  A --> B")}${figureMarkup("sequenceDiagram\n  fail")}${figureMarkup("graph TD\n  C --> D")}`,
  );
  const figures = trusted.querySelectorAll('[data-kpress-diagram="mermaid"]');
  const seen = [];
  const release = mermaid.hold();
  const handle = placement.drawDiagrams(trusted, mb, false);
  await settle();
  seen.push(figures.map((figure) => figure.dataset.kpressDiagramStatus));
  release();
  await handle.ready;
  transcript.trusted = {
    modulesAsked: [...ensured],
    whileTheFirstDraws: seen[0],
    figures: figures.map(describeFigure),
    renders: mermaid.calls.render.map((call) => `${call.text} (${call.host})`),
    themes: mermaid.calls.initialize.map((config) => config.theme),
    toolbar: describeToolbar(figures[0], sdk),
  };
  check("the copy button is the page's own", transcript.trusted.toolbar.copyIsOwned === true);
  check("Mermaid is asked for once", ensured.length === 1 && ensured[0] === "mermaid", ensured);
  check("the first draws while the rest wait", seen[0].join() === "rendering,source,source", seen);
  check(
    "drawn, failed, drawn",
    figures.map((figure) => figure.dataset.kpressDiagramStatus).join() ===
      "rendered,error,rendered",
  );

  // The toolbar's source toggle.
  const toggle = figures[0].querySelector(".metabrowser-diagram-toggle-source");
  toggle.click();
  const toggledOn = describeFigure(figures[0]);
  const toggledLabel = toggle.getAttribute("aria-label");
  toggle.click();
  transcript.toggle = { on: toggledOn, label: toggledLabel, off: describeFigure(figures[0]) };
  check("the toggle shows the source", toggledOn.sourceShown && !toggledOn.drawingShown, toggledOn);

  // A theme change draws every diagram again in the new theme; a toggled source stays.
  toggle.click();
  setTheme("dark");
  await settle();
  await settle();
  transcript.themeChange = {
    figures: figures.map(describeFigure),
    themes: mermaid.calls.initialize.map((config) => config.theme),
  };
  check(
    "drawn again in the dark theme",
    transcript.themeChange.figures[2].drawing === "svg in dark theme",
    transcript.themeChange,
  );
  check("a toggled source stays shown", transcript.themeChange.figures[0].sourceShown === true);
  toggle.click();

  // The dialog.
  const listenersBeforeDialog = listenerTotal;
  figures[2].querySelector(".metabrowser-diagram-expand").click();
  const dialog = document.body.querySelector(".metabrowser-diagram-dialog");
  const stage = dialog.querySelector(".metabrowser-diagram-stage");
  const viewportElement = dialog.querySelector(".metabrowser-diagram-viewport");
  const transforms = [stage.style.transform];
  dialog.querySelector('[data-diagram-action="zoom-in"]').click();
  transforms.push(stage.style.transform);
  viewportElement.dispatchEvent({ type: "keydown", key: "-", bubbles: true });
  transforms.push(stage.style.transform);
  viewportElement.dispatchEvent({ type: "keydown", key: "ArrowLeft", bubbles: true });
  transforms.push(stage.style.transform);
  viewportElement.dispatchEvent({
    type: "wheel",
    deltaX: 0,
    deltaY: -100,
    ctrlKey: true,
    clientX: 110,
    clientY: 120,
    bubbles: true,
  });
  transforms.push(stage.style.transform);
  viewportElement.dispatchEvent({
    type: "pointerdown",
    button: 0,
    pointerId: 7,
    clientX: 300,
    clientY: 300,
    bubbles: true,
  });
  viewportElement.dispatchEvent({
    type: "pointermove",
    pointerId: 7,
    clientX: 340,
    clientY: 280,
    bubbles: true,
  });
  viewportElement.dispatchEvent({ type: "pointerup", pointerId: 7, bubbles: true });
  transforms.push(stage.style.transform);
  dialog.querySelector('[data-diagram-action="reset"]').click();
  transforms.push(stage.style.transform);
  const stageDrawing = stage.children[0];
  transcript.dialog = {
    open: dialog.open,
    label: dialog.getAttribute("aria-label"),
    controls: dialog
      .querySelector(".metabrowser-diagram-dialog-controls")
      .children.map((button) => button.getAttribute("aria-label")),
    drawing: {
      tag: stageDrawing.tagName.toLowerCase(),
      width: stageDrawing.style.width,
      maxWidth: stageDrawing.style.maxWidth,
    },
    transforms,
    pointerCaptured: viewportElement.captured,
    viewportFocused: viewportElement.focused,
  };
  dialog.querySelector(".metabrowser-diagram-dialog-close").click();
  transcript.dialog.removedOnClose = !document.body.contains(dialog);
  transcript.dialog.listenersLeft = listenerTotal - listenersBeforeDialog;
  check(
    "the dialog closes and leaves no listener",
    transcript.dialog.removedOnClose && transcript.dialog.listenersLeft === 0,
    transcript.dialog,
  );

  // Escape closes the dialog the way the browser does: its close event.
  figures[0].querySelector(".metabrowser-diagram-expand").click();
  const escaped = document.body.querySelector(".metabrowser-diagram-dialog");
  escaped.close();
  transcript.escapeRemovesDialog = !document.body.contains(escaped);

  // Disposal: the theme is no longer heard, an open dialog goes, listeners go.
  figures[0].querySelector(".metabrowser-diagram-expand").click();
  const renderCount = mermaid.calls.render.length;
  handle.dispose();
  setTheme("light");
  await settle();
  transcript.dispose = {
    dialogsLeft: document.body.querySelectorAll(".metabrowser-diagram-dialog").length,
    rendersAfterDispose: mermaid.calls.render.length - renderCount,
    themeListeners: themeListeners.size,
    figuresKept: figures.map((figure) => figure.dataset.kpressDiagramStatus),
  };
  check(
    "disposal leaves nothing listening",
    transcript.dispose.dialogsLeft === 0 &&
      transcript.dispose.themeListeners === 0 &&
      transcript.dispose.rendersAfterDispose === 0,
    transcript.dispose,
  );
  trusted.remove();

  // Disposal in the middle of drawing stops before the next diagram.
  mermaid = createMermaid();
  const midway = article(`${figureMarkup("graph A")}${figureMarkup("graph B")}`);
  const hold = mermaid.hold();
  const stopped = diagrams.mountDiagrams(midway, mb, {
    mode: "document",
    loadMermaid: async () => mermaid.api,
  });
  await settle();
  stopped.dispose();
  hold();
  await stopped.ready;
  transcript.disposeWhileDrawing = {
    rendersStarted: mermaid.calls.render.length,
    figures: stopped.figures.map((figure) => figure.dataset.kpressDiagramStatus),
  };
  check(
    "no diagram starts after disposal",
    mermaid.calls.render.length === 1,
    transcript.disposeWhileDrawing,
  );
  midway.remove();

  // A source past Mermaid's limit is refused before Mermaid sees it.
  mermaid = createMermaid();
  const long = article(figureMarkup(`graph TD\n${"x".repeat(diagrams.MAX_DIAGRAM_TEXT)}`));
  const refused = diagrams.mountDiagrams(long, mb, {
    loadMermaid: async () => mermaid.api,
    subscribeTheme: () => () => {},
  });
  await refused.ready;
  transcript.tooLong = {
    figure: describeFigure(refused.figures[0]),
    renders: mermaid.calls.render.length,
  };
  check(
    "too long is refused",
    transcript.tooLong.figure.status === "error" && transcript.tooLong.renders === 0,
  );
  refused.dispose();
  long.remove();

  // A Mermaid that cannot load says so on every figure.
  const offline = article(`${figureMarkup("graph A")}${figureMarkup("graph B")}`);
  const unloaded = diagrams.mountDiagrams(offline, mb, {
    loadMermaid: async () => {
      throw new Error("Failed to fetch dynamically imported module");
    },
    subscribeTheme: () => () => {},
  });
  await unloaded.ready;
  transcript.loadFailure = unloaded.figures.map(describeFigure);
  unloaded.dispose();
  offline.remove();

  // An inert render: GitHub's fallback block becomes a figure drawn as an image.
  mermaid = createMermaid();
  const inert = article(
    '<p>Inert.</p><pre lang="mermaid"><code>flowchart LR\n  A --&gt; B</code></pre>',
  );
  ensured.length = 0;
  const inertHandle = placement.drawDiagrams(inert, mb, true);
  await inertHandle.ready;
  const inertFigure = inert.querySelector('[data-kpress-diagram="mermaid"]');
  const image = inertFigure.querySelector("img");
  const decoded = decodeURIComponent(image.src.slice(image.src.indexOf(",") + 1));
  transcript.inert = {
    figure: describeFigure(inertFigure),
    wrapsTheBlock: inertFigure.querySelector(':scope > pre[lang="mermaid"]') !== null,
    imageAddress: image.src.slice(0, image.src.indexOf(",")),
    imageSvg: decoded,
    render: mermaid.calls.render.map((call) => ({ host: call.host, attached: call.hostAttached })),
    measuringHostsLeft: document.body.children.filter(
      (node) => node.getAttribute("aria-hidden") === "true",
    ).length,
  };
  check(
    "the inert block is drawn as an image",
    transcript.inert.figure.drawing === "image",
    transcript.inert,
  );
  check(
    "measured in an attached host that is then removed",
    transcript.inert.render[0].attached === true && transcript.inert.measuringHostsLeft === 0,
    transcript.inert,
  );
  inertHandle.dispose();
  inert.remove();

  // A `.mmd` file's Diagram view: a truncated file is read whole, then drawn as an image.
  mermaid = createMermaid();
  const fileHost = document.createElement("div");
  document.body.append(fileHost);
  const completed = [];
  const fileSdk = {
    ...mb,
    fetchCompleteText: async (ctx) => {
      completed.push(ctx.path);
      return "flowchart TD\n  Whole --> File";
    },
    errors: { isAbortError: () => false },
  };
  const file = fileView.mountMermaidFile(
    fileHost,
    { path: "flow.mmd", raw: { content: "flowchart TD\n  Wh", content_truncated: true } },
    fileSdk,
  );
  await file.ready;
  const fileFigure = fileHost.querySelector('[data-kpress-diagram="mermaid"]');
  transcript.fileView = {
    figure: describeFigure(fileFigure),
    classes: fileFigure.getAttribute("class"),
    readWhole: completed,
    drew: mermaid.calls.render.map((call) => call.source.split("\n")[1].trim()),
  };
  check(
    "a truncated file is drawn from its whole text",
    transcript.fileView.drew[0] === "Whole --> File",
    transcript.fileView,
  );
  check(
    "a file view draws an image",
    transcript.fileView.figure.drawing === "image",
    transcript.fileView,
  );
  file.dispose();
  fileHost.remove();

  transcript.listenersLeft = listenerTotal;
  check("no listener is left anywhere", listenerTotal === 0, listenerTotal);
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
