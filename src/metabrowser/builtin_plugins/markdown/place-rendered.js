// Place a KPress render in the page, importing the inert path only for an inert render.
//
// The server marks a render `inert` when active content is off: every served mirror, and
// a folder served with --untrusted. inert-render.js rebuilds such a render from the
// allowlist and inert-toc.js draws its table of contents. A trusted folder never
// receives one, so neither module is part of what its Markdown view needs, and both are
// imported here on the first inert render instead of with the plugin's module tree.
//
// Measured 2026-09-30 in Chrome 152 on a trusted folder's first Markdown view: with the
// two imported statically the plugin fetched 18 modules, 66,982 bytes transferred and
// 217,471 decoded, and a fourth level of imports; the two are 5,365 and 12,691 of those
// bytes. See explorations/performance-loop/experiments/exp-037.

/**
 * Put *rendered*'s HTML into *target*, replacing what is there, and resolve its links.
 *
 * `enhanced` is what *enhance* returned. `inert` is the inert render's module for a
 * render placed inert, whose table of contents the caller runs with its `inertArticle`
 * and `wireInertToc`, and null for a trusted render, whose KPress table of contents runs.
 *
 * @template T
 * @param {HTMLElement} target
 * @param {{html: string, inert?: boolean, toc?: boolean, model?: {headings?: unknown}}} rendered
 * @param {MetabrowserPublicSdk} mb
 * @param {((root: HTMLElement) => T) | null} [enhance] Resolves the render's links and
 *   images under *root*; inert-render.js says when it runs for an inert render.
 * @returns {Promise<{enhanced: T | null, inert: typeof import("./inert-render.js") | null}>}
 */
export async function placeRendered(target, rendered, mb, enhance = null) {
  if (rendered.inert !== true) {
    target.innerHTML = rendered.html;
    return { enhanced: enhance ? enhance(target) : null, inert: null };
  }
  const inert = await import("./inert-render.js");
  return { enhanced: await inert.placeRendered(target, rendered, mb, enhance), inert };
}
