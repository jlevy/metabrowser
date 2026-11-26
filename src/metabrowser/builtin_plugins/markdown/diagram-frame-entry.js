// The one script of the isolated diagram frame (diagram-frame.js), run in that frame's
// realm. The page calls `load` with the vendored Mermaid entry's URL, so Mermaid is
// evaluated here and lays its diagrams out in this frame's document, under this frame's
// policy, and never in the page's.

/** @type {{metabrowserDiagramFrame?: {load(url: string): Promise<unknown>}}} */ (
  /** @type {unknown} */ (globalThis)
).metabrowserDiagramFrame = Object.freeze({
  /** @param {string} url */
  load: (url) => import(url),
});
