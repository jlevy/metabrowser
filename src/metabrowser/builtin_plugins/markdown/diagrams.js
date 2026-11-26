// Metabrowser's host for KPress's Mermaid diagrams.
//
// KPress marks a `mermaid` fence as a figure that holds its source, and its
// `js/diagrams.js` draws those figures with a Mermaid the host supplies; its opt-in
// `js/diagram-controls.js` adds the toolbar (copy, show source, expand) and the zoom and
// pan dialog (KPress's host-integration guide, "Mermaid Diagrams"). This module is what
// Metabrowser decides around them:
//
// - **Loading.** The vendored Mermaid entry and both KPress modules are on-demand module
//   bundles (`mb.ensureModule`, static/asset-loader.js), fetched only for a root that
//   holds a diagram. The KPress modules are published at the stamped URLs a render's
//   manifest names, so they share the document's one KPress runtime.
// - **Trust.** A trusted render places the SVG in the document. An inert render, whose
//   source a fork's author may control, places each diagram as an image
//   (`placement: "image"`), which runs no script and loads nothing; `inert_html.py`
//   reduces KPress's figure to GitHub's own fallback, `<pre lang="mermaid">`, which
//   `mermaidFigureFor` turns back into a figure here. A `.mmd` file's view is the Document
//   view of its text (`mermaid-view.js`), so it follows the same trust. Mermaid lays an
//   image out in the page first, where the page's policy bounds what its CSS loads; an
//   untrusted text on a page that may have no policy, a pull request's, is laid out in a
//   frame whose own policy loads nothing (`mode: "isolated"`, diagram-frame.js).
// - **Theme.** The page's resolved `data-theme`, redrawn through `MetabrowserTheme`.
// - **Chrome.** The copy button is the shell's copy delegate and every button's tooltip
//   is the app's. The glyphs are KPress's sprites, which KPress fetches for an inert
//   render whose allowlist dropped them (`ensureDiagramSprites`).

import { leaseDiagramFrame } from "./diagram-frame.js";

/** A KPress Mermaid figure in a trusted render. */
export const KPRESS_DIAGRAM_SELECTOR = '[data-kpress-diagram="mermaid"]';
/** A Mermaid block in an inert render, as `inert_html.py` reduces the figure. */
export const INERT_DIAGRAM_SELECTOR = 'pre[lang="mermaid"]';

/**
 * Give a KPress control button the app's tooltip in place of the browser's.
 *
 * @param {HTMLButtonElement} button
 */
export function decorateButton(button) {
  const label = button.getAttribute("aria-label");
  if (label) {
    button.setAttribute("data-tip-text", label);
  }
  button.removeAttribute("title");
}

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

/**
 * The parts of KPress's `js/diagrams.js` this host calls.
 *
 * @typedef {{
 *   initKpressDiagrams(root: ParentNode, options: Record<string, unknown>): {
 *     figures: HTMLElement[], ready: Promise<void>, rerender(): void, dispose(): void
 *   },
 *   mermaidFigureFor(element: Element): HTMLElement,
 * }} KpressDiagrams
 */
/**
 * The part of KPress's `js/diagram-controls.js` this host calls.
 *
 * @typedef {{diagramControls(options: Record<string, unknown>): unknown}} KpressDiagramControls
 */

/**
 * @typedef {{
 *   ensureModule(name: string): Promise<unknown>,
 *   moduleUrl(name: string): string | null,
 *   ownDelegate?: <T extends Element>(element: T) => T,
 * }} DiagramSdk
 */

/**
 * Draw the Mermaid diagrams under *root* with KPress.
 *
 * `mode` is "document" for a trusted render, "image" for an inert render or a file view,
 * whose page's policy bounds Mermaid's layout, and "isolated" for untrusted text on a page
 * that may have none: images, laid out in the shared diagram frame (diagram-frame.js). The
 * returned `figures` fills once KPress has bound; `ready` settles when every diagram has
 * drawn or failed; `dispose` stops drawing, unsubscribes the theme, closes any open
 * dialog, releases the frame, and leaves the figures as they are.
 *
 * @param {ParentNode} root
 * @param {DiagramSdk} mb
 * @param {{
 *   mode?: "document" | "image" | "isolated",
 *   theme?: () => "dark" | "light",
 *   subscribeTheme?: (listener: () => void) => () => void,
 *   yieldBetween?: () => Promise<unknown>,
 * }} [options]
 * @returns {{dispose(): void, ready: Promise<void>, figures: HTMLElement[]}}
 */
export function mountDiagrams(root, mb, options = {}) {
  const isolated = options.mode === "isolated";
  const placement = isolated || options.mode === "image" ? "image" : "document";
  const frame = isolated ? leaseDiagramFrame(mb) : null;
  /** @type {HTMLElement[]} */
  const figures = [];
  let disposed = false;
  /** @type {{dispose(): void} | null} */
  let binding = null;

  async function bind() {
    const [diagrams, controls] = /** @type {[KpressDiagrams, KpressDiagramControls]} */ (
      await Promise.all([
        mb.ensureModule("kpress-diagrams"),
        mb.ensureModule("kpress-diagram-controls"),
      ])
    );
    if (disposed) {
      return;
    }
    for (const pre of root.querySelectorAll(INERT_DIAGRAM_SELECTOR)) {
      if (!pre.closest(KPRESS_DIAGRAM_SELECTOR)) {
        diagrams.mermaidFigureFor(pre);
      }
    }
    const bound = diagrams.initKpressDiagrams(root, {
      mermaid: frame ? () => frame.mermaid() : () => mb.ensureModule("mermaid"),
      theme: options.theme ?? documentTheme,
      subscribeTheme: options.subscribeTheme ?? subscribePageTheme,
      placement,
      yieldBetween: options.yieldBetween,
      controls: controls.diagramControls({
        decorate: decorateButton,
        /** @param {HTMLButtonElement} button @param {string} text */
        copy(button, text) {
          button.setAttribute("data-mb-copy", "text");
          button.setAttribute("data-mb-copy-text", text);
          button.setAttribute("data-mb-copy-label", "Copy diagram source");
          mb.ownDelegate?.(button);
        },
      }),
    });
    binding = bound;
    figures.push(...bound.figures);
    await bound.ready;
  }

  const ready = bind().catch((error) => {
    if (!disposed) {
      console.warn("metabrowser markdown: the diagrams could not be drawn", error);
    }
  });
  return {
    ready,
    figures,
    dispose() {
      disposed = true;
      binding?.dispose();
      binding = null;
      frame?.release();
    },
  };
}
