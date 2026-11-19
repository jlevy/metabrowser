// Draw a rendered document's Mermaid diagrams, as GitHub does, and better where it can.
//
// KPress marks a `mermaid` fence as a figure that holds its source
// (`[data-kpress-diagram="mermaid"]` around `.kpress-diagram-source`); an inert render
// reduces that figure to GitHub's own fallback, `<pre lang="mermaid">`
// (src/metabrowser/inert_html.py). This module finds either, loads the vendored Mermaid
// entry through the on-demand tier (`mb.ensureModule("mermaid")`, static/asset-loader.js)
// only when a root holds one, and draws each diagram in document order.
//
// A trusted render places the SVG in the document, so it follows the theme, prints, and
// selects with the prose. An inert render, whose source a fork's author may control,
// places it as an image (`<img src="data:image/svg+xml…">`): an SVG document shown as an
// image runs no script, loads nothing, and navigates nowhere, whatever Mermaid let
// through. A `.mmd` file's view uses the image too (`mermaid-view.js`).
//
// Mermaid is initialized with GitHub's observable configuration (read from its renderer
// bundle on 2026-11-18, docs/project/specs/active/plan-2026-08-21-mermaid-diagram-rendering.md)
// except `securityLevel`, which is `strict`: Mermaid sanitizes labels the same way under
// `strict` and GitHub's `antiscript`, and `strict` also disables `click`, whose navigation
// GitHub's frame policy blocks anyway. KPress's own `js/diagrams.js` is never given a
// Mermaid (plugin-sdk.js skips loading it), so it cannot draw a figure twice.
//
// Each drawn figure gets a toolbar (copy source, show source, expand), and expand opens a
// dialog with GitHub's zoom and pan buttons plus wheel, pinch, drag, and keys. The zoom
// and pan arithmetic is the pure `viewAction` below, which the browserless session
// (tests/dom/markdown-diagrams-session.js) drives.

/** A KPress Mermaid figure in a trusted render. */
export const KPRESS_DIAGRAM_SELECTOR = '[data-kpress-diagram="mermaid"]';
/** A Mermaid block in an inert render, as `inert_html.py` reduces the figure. */
export const INERT_DIAGRAM_SELECTOR = 'pre[lang="mermaid"]';
const DIAGRAM_SELECTOR = `${KPRESS_DIAGRAM_SELECTOR}, ${INERT_DIAGRAM_SELECTOR}`;

/**
 * Mermaid's own default `maxTextSize`, which GitHub keeps. A longer source is refused
 * here with a message rather than drawn as Mermaid's "Maximum text size" placeholder.
 */
export const MAX_DIAGRAM_TEXT = 50_000;

/** How much one zoom step scales: the dialog's buttons, keys, and one wheel notch. */
export const ZOOM_STEP = 1.25;
/** The dialog's zoom bounds, relative to the diagram's natural size. */
export const MIN_SCALE = 0.1;
export const MAX_SCALE = 10;
/** The most the dialog's first view, and reset, enlarge a small diagram to fit. */
export const MAX_FIT_SCALE = 2;
/** How far one pan button press or arrow key moves the diagram, in CSS pixels. */
export const PAN_STEP = 80;

// Lucide v1.17.0 glyphs (ISC; https://lucide.dev), drawn only by this module, so they
// live here rather than in the shell's startup registry (static/icons.js).
const SA =
  'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
const GLYPHS = Object.freeze({
  // Lucide `code`
  code: `<svg ${SA}><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`,
  // Lucide `maximize-2`
  expand: `<svg ${SA}><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" x2="14" y1="3" y2="10"/><line x1="3" x2="10" y1="21" y2="14"/></svg>`,
  // Lucide `zoom-in`
  zoomIn: `<svg ${SA}><circle cx="11" cy="11" r="8"/><line x1="21" x2="16.65" y1="21" y2="16.65"/><line x1="11" x2="11" y1="8" y2="14"/><line x1="8" x2="14" y1="11" y2="11"/></svg>`,
  // Lucide `zoom-out`
  zoomOut: `<svg ${SA}><circle cx="11" cy="11" r="8"/><line x1="21" x2="16.65" y1="21" y2="16.65"/><line x1="8" x2="14" y1="11" y2="11"/></svg>`,
  // Lucide `rotate-ccw`
  reset: `<svg ${SA}><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>`,
  // Lucide `chevron-up`
  panUp: `<svg ${SA}><path d="m18 15-6-6-6 6"/></svg>`,
  // Lucide `chevron-down`
  panDown: `<svg ${SA}><path d="m6 9 6 6 6-6"/></svg>`,
  // Lucide `chevron-left`
  panLeft: `<svg ${SA}><path d="m15 18-6-6 6-6"/></svg>`,
  // Lucide `chevron-right`
  panRight: `<svg ${SA}><path d="m9 18 6-6-6-6"/></svg>`,
  // Lucide `x`
  close: `<svg ${SA}><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>`,
});

/** @typedef {{scale: number, x: number, y: number}} DiagramView */
/** @typedef {{width: number, height: number}} Size */
/**
 * @typedef {"zoom-in" | "zoom-out" | "reset" | "pan-up" | "pan-down" | "pan-left" | "pan-right"} ViewActionName
 */

/** @param {number} value @param {number} low @param {number} high */
function clamp(value, low, high) {
  return Math.min(high, Math.max(low, value));
}

/** @param {number} value */
function round(value) {
  return Math.round(value * 1000) / 1000;
}

/**
 * The view that fits *content* inside *viewport*, centered, enlarged at most
 * `MAX_FIT_SCALE` times.
 *
 * @param {Size} content
 * @param {Size} viewport
 * @returns {DiagramView}
 */
export function fitView(content, viewport) {
  if (!(content.width > 0 && content.height > 0 && viewport.width > 0 && viewport.height > 0)) {
    return { scale: 1, x: 0, y: 0 };
  }
  const scale = clamp(
    Math.min(viewport.width / content.width, viewport.height / content.height, MAX_FIT_SCALE),
    MIN_SCALE,
    MAX_SCALE,
  );
  return {
    scale: round(scale),
    x: round((viewport.width - content.width * scale) / 2),
    y: round((viewport.height - content.height * scale) / 2),
  };
}

/**
 * *view* scaled by *factor* about *origin*, a point in the viewport, which stays put.
 *
 * @param {DiagramView} view
 * @param {number} factor
 * @param {{x: number, y: number}} origin
 * @returns {DiagramView}
 */
export function zoomAbout(view, factor, origin) {
  const scale = clamp(view.scale * factor, MIN_SCALE, MAX_SCALE);
  const ratio = scale / view.scale;
  return {
    scale: round(scale),
    x: round(origin.x - (origin.x - view.x) * ratio),
    y: round(origin.y - (origin.y - view.y) * ratio),
  };
}

/**
 * *view* moved by (*dx*, *dy*) viewport pixels.
 *
 * @param {DiagramView} view
 * @param {number} dx
 * @param {number} dy
 * @returns {DiagramView}
 */
export function panBy(view, dx, dy) {
  return { scale: view.scale, x: round(view.x + dx), y: round(view.y + dy) };
}

/**
 * The view after one of the dialog's buttons or keys. A zoom keeps the viewport's center
 * still; a pan button moves the view the way its arrow points, as GitHub's do; reset fits.
 *
 * @param {DiagramView} view
 * @param {ViewActionName} action
 * @param {{content: Size, viewport: Size}} sizes
 * @returns {DiagramView}
 */
export function viewAction(view, action, sizes) {
  const center = { x: sizes.viewport.width / 2, y: sizes.viewport.height / 2 };
  switch (action) {
    case "zoom-in":
      return zoomAbout(view, ZOOM_STEP, center);
    case "zoom-out":
      return zoomAbout(view, 1 / ZOOM_STEP, center);
    case "reset":
      return fitView(sizes.content, sizes.viewport);
    case "pan-up":
      return panBy(view, 0, PAN_STEP);
    case "pan-down":
      return panBy(view, 0, -PAN_STEP);
    case "pan-left":
      return panBy(view, PAN_STEP, 0);
    case "pan-right":
      return panBy(view, -PAN_STEP, 0);
    default:
      return view;
  }
}

/**
 * The dialog action a key names, or null.
 *
 * @param {{key: string, ctrlKey?: boolean, metaKey?: boolean, altKey?: boolean}} event
 * @returns {ViewActionName | null}
 */
export function keyAction(event) {
  if (event.ctrlKey || event.metaKey || event.altKey) {
    return null;
  }
  /** @type {Record<string, ViewActionName>} */
  const keys = {
    "+": "zoom-in",
    "=": "zoom-in",
    "-": "zoom-out",
    _: "zoom-out",
    0: "reset",
    ArrowUp: "pan-up",
    ArrowDown: "pan-down",
    ArrowLeft: "pan-left",
    ArrowRight: "pan-right",
  };
  return keys[event.key] ?? null;
}

/**
 * The view after a wheel event at *origin*. A pinch, which browsers report as a wheel
 * with the control key, and a wheel with the control or command key held zoom about the
 * pointer; a plain wheel or two-finger scroll pans.
 *
 * @param {DiagramView} view
 * @param {{deltaX: number, deltaY: number, ctrlKey?: boolean, metaKey?: boolean}} wheel
 * @param {{x: number, y: number}} origin
 * @returns {DiagramView}
 */
export function wheelView(view, wheel, origin) {
  if (wheel.ctrlKey || wheel.metaKey) {
    return zoomAbout(view, Math.exp(-wheel.deltaY / 200), origin);
  }
  return panBy(view, -wheel.deltaX, -wheel.deltaY);
}

/** @param {DiagramView} view */
export function viewTransform(view) {
  return `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
}

/**
 * Mermaid's site configuration for a resolved app theme: GitHub's, with
 * `securityLevel: "strict"`. A diagram's own `%%{init}%%` or front-matter theme wins.
 *
 * @param {"dark" | "light"} theme
 */
export function mermaidConfig(theme) {
  return {
    startOnLoad: false,
    securityLevel: "strict",
    suppressErrorRendering: true,
    theme: theme === "dark" ? "dark" : "default",
    flowchart: { diagramPadding: 48 },
    sequence: { diagramMarginY: 40 },
  };
}

/** @param {ParentNode} root */
export function hasDiagrams(root) {
  return !!root.querySelector?.(DIAGRAM_SELECTOR);
}

/**
 * @typedef {{
 *   initialize(config: Record<string, unknown>): void,
 *   render(id: string, text: string, container?: Element): Promise<{svg: string}>,
 * }} MermaidApi
 */

/**
 * @typedef {{
 *   mode?: "document" | "image",
 *   loadMermaid?: () => Promise<MermaidApi>,
 *   theme?: () => "dark" | "light",
 *   subscribeTheme?: (listener: () => void) => () => void,
 *   ownDelegate?: <T extends Element>(element: T) => T,
 *   yieldBetween?: () => Promise<void>,
 * }} DiagramOptions
 */

let diagramSequence = 0;

/** The resolved theme the page shows. */
function documentTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

/** @param {() => void} listener */
function subscribePageTheme(listener) {
  const runtime = /** @type {{MetabrowserTheme?: {subscribe(fn: () => void): () => void}}} */ (
    /** @type {unknown} */ (globalThis)
  ).MetabrowserTheme;
  return runtime ? runtime.subscribe(listener) : () => {};
}

/** @param {unknown} namespace @returns {MermaidApi} */
function mermaidFrom(namespace) {
  const candidate =
    namespace && typeof namespace === "object" && "default" in namespace
      ? /** @type {{default: unknown}} */ (namespace).default
      : namespace;
  if (
    !candidate ||
    typeof candidate !== "object" ||
    typeof (/** @type {MermaidApi} */ (candidate).render) !== "function" ||
    typeof (/** @type {MermaidApi} */ (candidate).initialize) !== "function"
  ) {
    throw new TypeError("The Mermaid module has no render and initialize");
  }
  return /** @type {MermaidApi} */ (candidate);
}

/** @param {unknown} error */
export function diagramErrorMessage(error) {
  const message =
    error instanceof Error
      ? error.message
      : error && typeof error === "object" && "message" in error
        ? String(/** @type {{message: unknown}} */ (error).message)
        : String(error ?? "");
  const trimmed = message.trim();
  return trimmed || "Mermaid could not draw this diagram.";
}

/**
 * *svg*, Mermaid's markup, as a well-formed standalone SVG document an image can load:
 * serialized as XML (Mermaid's HTML labels hold `<br>`), sized to its view box.
 *
 * @param {string} svg
 */
export function svgImageSource(svg) {
  const template = document.createElement("template");
  template.innerHTML = svg;
  const element = template.content.querySelector("svg");
  if (!element) {
    throw new Error("Mermaid returned no SVG");
  }
  const box = (element.getAttribute("viewBox") || "").split(/[\s,]+/).map(Number);
  if (box.length === 4 && box[2] > 0 && box[3] > 0) {
    element.setAttribute("width", String(round(box[2])));
    element.setAttribute("height", String(round(box[3])));
  }
  element.removeAttribute("style");
  element.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const text = new XMLSerializer().serializeToString(element);
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(text)}`;
}

/**
 * The figure that holds *found*'s diagram: KPress's own, or one built around an inert
 * `<pre lang="mermaid">` with KPress's classes, so both look and behave alike.
 *
 * @param {Element} found
 * @returns {HTMLElement}
 */
function diagramFigure(found) {
  if (found.matches(KPRESS_DIAGRAM_SELECTOR)) {
    return /** @type {HTMLElement} */ (found);
  }
  const figure = document.createElement("figure");
  figure.className = "kpress-diagram kpress-mermaid";
  figure.dataset.kpressDiagram = "mermaid";
  figure.dataset.kpressDiagramStatus = "source";
  found.replaceWith(figure);
  found.classList.add("kpress-diagram-source");
  figure.append(found);
  return figure;
}

/** @param {HTMLElement} figure */
function figureSource(figure) {
  const source = /** @type {HTMLElement | null} */ (
    figure.querySelector(":scope > .kpress-diagram-source") ?? figure.querySelector("pre")
  );
  const code = source?.querySelector("code") ?? source;
  return { source, text: (code?.textContent ?? "").trim() };
}

/**
 * Draw every Mermaid diagram under *root* and give each its toolbar.
 *
 * Resolves `ready` when every diagram has drawn or failed. `dispose` stops drawing,
 * unsubscribes the theme, closes any open dialog, and leaves the figures as they are.
 *
 * @param {ParentNode} root
 * @param {MetabrowserPublicSdk | {ensureModule(name: string): Promise<unknown>, ownDelegate?: <T extends Element>(element: T) => T}} mb
 * @param {DiagramOptions} [options]
 * @returns {{dispose(): void, ready: Promise<void>, figures: HTMLElement[]}}
 */
export function mountDiagrams(root, mb, options = {}) {
  const mode = options.mode ?? "document";
  const loadMermaid =
    options.loadMermaid ??
    (() => mb.ensureModule("mermaid").then((namespace) => mermaidFrom(namespace)));
  const theme = options.theme ?? documentTheme;
  const ownDelegate = options.ownDelegate ?? mb.ownDelegate;
  const yieldBetween =
    options.yieldBetween ?? (() => new Promise((resolve) => setTimeout(resolve, 0)));
  const figures = Array.from(root.querySelectorAll(DIAGRAM_SELECTOR), diagramFigure);
  let disposed = false;
  /** @type {Array<() => void>} */
  const cleanups = [];
  /** @type {Promise<void>} */
  let drawing = Promise.resolve();
  let generation = 0;

  for (const figure of figures) {
    cleanups.push(addToolbar(figure, { ownDelegate, mode, isDisposed: () => disposed }));
  }

  /** @param {number} pass */
  async function drawAll(pass) {
    if (!figures.length) {
      return;
    }
    let mermaid;
    try {
      mermaid = await loadMermaid();
    } catch (error) {
      for (const figure of figures) {
        showError(figure, `Mermaid could not load: ${diagramErrorMessage(error)}`);
      }
      return;
    }
    for (const figure of figures) {
      if (disposed || pass !== generation) {
        return;
      }
      mermaid.initialize(mermaidConfig(theme()));
      await drawFigure(figure, mermaid, mode);
      await yieldBetween();
    }
  }

  function redraw() {
    if (disposed) {
      return;
    }
    generation += 1;
    const pass = generation;
    for (const figure of figures) {
      clearDrawing(figure);
    }
    drawing = drawing.then(() => drawAll(pass));
  }

  generation += 1;
  drawing = drawAll(generation);
  if (figures.length) {
    const subscribe = options.subscribeTheme ?? subscribePageTheme;
    cleanups.push(subscribe(redraw));
  }

  return {
    figures,
    ready: drawing.then(() => drawing),
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      for (const cleanup of cleanups.splice(0)) {
        cleanup();
      }
    },
  };
}

/** @param {HTMLElement} figure */
function clearDrawing(figure) {
  figure.querySelector(":scope > .kpress-diagram-rendered")?.remove();
  figure.querySelector(":scope > .metabrowser-diagram-error")?.remove();
  figure.dataset.kpressDiagramStatus = "source";
  const { source } = figureSource(figure);
  if (source) {
    source.hidden = false;
  }
}

/**
 * @param {HTMLElement} figure
 * @param {MermaidApi} mermaid
 * @param {"document" | "image"} mode
 */
async function drawFigure(figure, mermaid, mode) {
  const { source, text } = figureSource(figure);
  if (!text) {
    return;
  }
  if (text.length > MAX_DIAGRAM_TEXT) {
    showError(
      figure,
      `This diagram's source is ${text.length.toLocaleString("en-US")} characters; Mermaid draws at most ${MAX_DIAGRAM_TEXT.toLocaleString("en-US")}.`,
    );
    return;
  }
  figure.dataset.kpressDiagramStatus = "rendering";
  diagramSequence += 1;
  const id = `metabrowser-mermaid-${diagramSequence}`;
  const host = mode === "image" ? measuringHost() : null;
  try {
    const { svg } = await mermaid.render(id, text, host ?? undefined);
    if (!svg) {
      throw new Error("Mermaid returned no SVG");
    }
    const rendered = document.createElement("div");
    rendered.className = "kpress-diagram-rendered";
    if (mode === "image") {
      const image = document.createElement("img");
      image.className = "metabrowser-diagram-image";
      image.alt = "Mermaid diagram";
      image.src = svgImageSource(svg);
      rendered.append(image);
    } else {
      rendered.innerHTML = svg;
    }
    figure.insertBefore(rendered, source ?? null);
    figure.dataset.kpressDiagramStatus = "rendered";
    applySourceToggle(figure);
  } catch (error) {
    // Mermaid leaves its scratch element behind when a render throws.
    document.getElementById(`d${id}`)?.remove();
    showError(figure, diagramErrorMessage(error));
  } finally {
    host?.remove();
  }
}

/**
 * Where an image-mode diagram is measured. Mermaid lays a diagram out in the page,
 * reading each label's box, and sets their face and size with a `<style>` inside its
 * SVG. The untrusted page's CSP admits no `<style>` element, only `style` attributes
 * (capabilities.untrusted_shell_csp), so the labels would be measured in the page's
 * face and drawn, inside the image, in Mermaid's: wider text clipped. The host carries
 * Mermaid's own theme face and size as attributes, so both agree.
 */
function measuringHost() {
  const host = document.createElement("div");
  host.setAttribute(
    "style",
    'position:fixed;left:-100000px;top:0;width:1200px;visibility:hidden;font-family:"trebuchet ms",verdana,arial,sans-serif;font-size:16px;line-height:normal;',
  );
  host.setAttribute("aria-hidden", "true");
  document.body.append(host);
  return host;
}

/** @param {HTMLElement} figure @param {string} message */
function showError(figure, message) {
  figure.querySelector(":scope > .metabrowser-diagram-error")?.remove();
  figure.dataset.kpressDiagramStatus = "error";
  const note = document.createElement("div");
  note.className = "metabrowser-diagram-error";
  note.setAttribute("role", "note");
  const title = document.createElement("strong");
  title.textContent = "Could not draw this diagram.";
  const detail = document.createElement("pre");
  detail.className = "metabrowser-diagram-error-detail";
  detail.textContent = message;
  note.append(title, detail);
  const { source } = figureSource(figure);
  figure.insertBefore(note, source ?? null);
  if (source) {
    source.hidden = false;
  }
}

/** Show the figure's source or its drawing, as its toggle says. @param {HTMLElement} figure */
function applySourceToggle(figure) {
  const showSource = figure.dataset.metabrowserDiagramShowSource === "true";
  const rendered = /** @type {HTMLElement | null} */ (
    figure.querySelector(":scope > .kpress-diagram-rendered")
  );
  const { source } = figureSource(figure);
  if (rendered) {
    rendered.hidden = showSource;
  }
  if (source) {
    source.hidden = !!rendered && !showSource;
  }
  // An action button whose name says what it does next, not a pressed toggle: the
  // figure's own content says which side is shown.
  const toggle = figure.querySelector(".metabrowser-diagram-toggle-source");
  const label = showSource ? "Show diagram" : "Show source";
  toggle?.setAttribute("aria-label", label);
  toggle?.setAttribute("data-tip-text", label);
}

/**
 * @param {keyof typeof GLYPHS | null} name the glyph, or null for a caller that draws its own
 * @param {string} label
 * @param {string} className
 */
function iconButton(name, label, className) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `icon-btn ${className}`;
  button.setAttribute("aria-label", label);
  button.setAttribute("data-tip-text", label);
  button.innerHTML = name ? GLYPHS[name] : "";
  return button;
}

/**
 * Give *figure* its toolbar; returns what removes the toolbar's dialog and listeners.
 *
 * @param {HTMLElement} figure
 * @param {{ownDelegate?: <T extends Element>(element: T) => T, mode: "document" | "image", isDisposed: () => boolean}} context
 */
function addToolbar(figure, context) {
  figure.querySelector(":scope > .metabrowser-diagram-toolbar")?.remove();
  const toolbar = document.createElement("div");
  toolbar.className = "metabrowser-diagram-toolbar kpress-no-print";
  const { text } = figureSource(figure);

  const copy = iconButton(null, "Copy diagram source", "metabrowser-diagram-copy");
  copy.innerHTML =
    /** @type {{MetabrowserIcons?: {copy?: string}}} */ (/** @type {unknown} */ (globalThis))
      .MetabrowserIcons?.copy ?? "";
  copy.setAttribute("data-mb-copy", "text");
  copy.setAttribute("data-mb-copy-text", text);
  copy.setAttribute("data-mb-copy-label", "Copy diagram source");
  context.ownDelegate?.(copy);

  const toggle = iconButton("code", "Show source", "metabrowser-diagram-toggle-source");
  const expand = iconButton("expand", "Expand diagram", "metabrowser-diagram-expand");

  toolbar.append(copy, toggle, expand);
  figure.prepend(toolbar);

  /** @type {(() => void) | null} */
  let closeDialog = null;
  /** @param {Event} event */
  const onToolbarClick = (event) => {
    const target = /** @type {Element | null} */ (event.target);
    const button = target?.closest?.("button");
    if (!button || context.isDisposed()) {
      return;
    }
    if (button === toggle) {
      figure.dataset.metabrowserDiagramShowSource =
        figure.dataset.metabrowserDiagramShowSource === "true" ? "false" : "true";
      applySourceToggle(figure);
    } else if (button === expand) {
      closeDialog?.();
      closeDialog = openDiagramDialog(figure, () => {
        closeDialog = null;
      });
    }
  };
  toolbar.addEventListener("click", onToolbarClick);
  return () => {
    toolbar.removeEventListener("click", onToolbarClick);
    closeDialog?.();
    closeDialog = null;
  };
}

/**
 * Open *figure*'s drawing in a modal dialog with zoom and pan; returns what closes it.
 *
 * @param {HTMLElement} figure
 * @param {() => void} onClosed
 */
export function openDiagramDialog(figure, onClosed) {
  const drawing = figure.querySelector(
    ":scope > .kpress-diagram-rendered > svg, :scope > .kpress-diagram-rendered > img",
  );
  const dialog = document.createElement("dialog");
  dialog.className = "metabrowser-diagram-dialog";
  dialog.setAttribute("aria-label", "Diagram");
  const controls = document.createElement("div");
  controls.className = "metabrowser-diagram-dialog-controls";
  /** @type {Array<[ViewActionName, keyof typeof GLYPHS, string]>} */
  const actions = [
    ["zoom-in", "zoomIn", "Zoom in"],
    ["zoom-out", "zoomOut", "Zoom out"],
    ["reset", "reset", "Reset view"],
    ["pan-up", "panUp", "Pan up"],
    ["pan-down", "panDown", "Pan down"],
    ["pan-left", "panLeft", "Pan left"],
    ["pan-right", "panRight", "Pan right"],
  ];
  for (const [action, glyph, label] of actions) {
    const button = iconButton(glyph, label, "metabrowser-diagram-view-action");
    button.dataset.diagramAction = action;
    controls.append(button);
  }
  const close = iconButton("close", "Close", "metabrowser-diagram-dialog-close");
  controls.append(close);
  const viewport = document.createElement("div");
  viewport.className = "metabrowser-diagram-viewport";
  viewport.tabIndex = 0;
  const stage = document.createElement("div");
  stage.className = "metabrowser-diagram-stage";
  if (drawing) {
    const copy = /** @type {HTMLElement} */ (drawing.cloneNode(true));
    // Mermaid sizes its SVG as `width: 100%` up to a `max-width` of its natural width;
    // on the stage it takes that natural width, which the view then scales.
    if (copy.tagName.toLowerCase() === "svg" && copy.style.maxWidth) {
      copy.style.width = copy.style.maxWidth;
      copy.style.maxWidth = "none";
      copy.removeAttribute("width");
    }
    stage.append(copy);
  } else {
    const { text } = figureSource(figure);
    const pre = document.createElement("pre");
    pre.textContent = text;
    stage.append(pre);
  }
  viewport.append(stage);
  dialog.append(controls, viewport);
  document.body.append(dialog);

  /** @type {DiagramView} */
  let view = { scale: 1, x: 0, y: 0 };
  const sizes = () => {
    const box = viewport.getBoundingClientRect();
    return {
      content: { width: stage.scrollWidth || 1, height: stage.scrollHeight || 1 },
      viewport: { width: box.width, height: box.height },
    };
  };
  /** @param {DiagramView} next */
  const apply = (next) => {
    view = next;
    stage.style.transform = viewTransform(view);
  };
  /** @param {{clientX: number, clientY: number}} point */
  const local = (point) => {
    const box = viewport.getBoundingClientRect();
    return { x: point.clientX - box.left, y: point.clientY - box.top };
  };

  /** @param {Event} event */
  const onClick = (event) => {
    const button = /** @type {Element | null} */ (event.target)?.closest?.("button");
    if (!button) {
      return;
    }
    if (button === close) {
      closeNow();
      return;
    }
    const action = /** @type {ViewActionName | undefined} */ (
      /** @type {HTMLElement} */ (button).dataset.diagramAction
    );
    if (action) {
      apply(viewAction(view, action, sizes()));
    }
  };
  /** @param {KeyboardEvent} event */
  const onKey = (event) => {
    const action = keyAction(event);
    if (action) {
      event.preventDefault();
      apply(viewAction(view, action, sizes()));
    }
  };
  /** @param {WheelEvent} event */
  const onWheel = (event) => {
    event.preventDefault();
    apply(wheelView(view, event, local(event)));
  };
  /** @type {{id: number, x: number, y: number} | null} */
  let drag = null;
  /** @param {PointerEvent} event */
  const onPointerDown = (event) => {
    if (event.button !== 0) {
      return;
    }
    drag = { id: event.pointerId, x: event.clientX, y: event.clientY };
    viewport.setPointerCapture?.(event.pointerId);
    viewport.classList.add("is-dragging");
  };
  /** @param {PointerEvent} event */
  const onPointerMove = (event) => {
    if (!drag || drag.id !== event.pointerId) {
      return;
    }
    apply(panBy(view, event.clientX - drag.x, event.clientY - drag.y));
    drag = { id: drag.id, x: event.clientX, y: event.clientY };
  };
  const onPointerUp = () => {
    drag = null;
    viewport.classList.remove("is-dragging");
  };
  const onCancel = () => closeNow();

  dialog.addEventListener("click", onClick);
  dialog.addEventListener("keydown", onKey);
  dialog.addEventListener("close", onCancel);
  viewport.addEventListener("wheel", onWheel, { passive: false });
  viewport.addEventListener("pointerdown", onPointerDown);
  viewport.addEventListener("pointermove", onPointerMove);
  viewport.addEventListener("pointerup", onPointerUp);
  viewport.addEventListener("pointercancel", onPointerUp);

  let closed = false;
  function closeNow() {
    if (closed) {
      return;
    }
    closed = true;
    dialog.removeEventListener("click", onClick);
    dialog.removeEventListener("keydown", onKey);
    dialog.removeEventListener("close", onCancel);
    viewport.removeEventListener("wheel", onWheel);
    viewport.removeEventListener("pointerdown", onPointerDown);
    viewport.removeEventListener("pointermove", onPointerMove);
    viewport.removeEventListener("pointerup", onPointerUp);
    viewport.removeEventListener("pointercancel", onPointerUp);
    if (dialog.open) {
      dialog.close();
    }
    dialog.remove();
    onClosed();
  }

  if (typeof dialog.showModal === "function") {
    dialog.showModal();
  } else {
    dialog.setAttribute("open", "");
  }
  apply(fitView(sizes().content, sizes().viewport));
  viewport.focus?.({ preventScroll: true });
  return closeNow;
}
