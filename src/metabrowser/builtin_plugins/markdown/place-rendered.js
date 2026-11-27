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
//
// This module itself stays in the plugin's static tree, because every Markdown view
// places its render through it. It also keeps the record of the images the page holds,
// which the link enhancer reads and writes, because placing a render is where an image
// from outside the served tree gets its loading: the enhancer imports this module, and
// this one importing the enhancer back would be a cycle through transclusion.js. It
// imports nothing statically, so it adds no level. Measured 2026-11-14 in headless Chrome
// 152 on a served folder's first Markdown view: 3,501 bytes transferred and 7,867 decoded,
// of 67,236 for the plugin's files, 17 of them modules as before; the enhancer, which gave
// up the record, went from 22,045 bytes decoded to 19,500. toc-toggle.js has joined the
// static tree since; its header has its measurement, dated 2026-11-17.

/**
 * The images this page has loaded whose address names their bytes, by address, least
 * recently loaded first.
 *
 * KPress writes `loading="lazy"` on a document's images, and entering a file again builds
 * its document again. WebKit, the macOS app's engine, does not give a new lazy image the
 * copy the page holds: once layout shows the image it asks the network again, so the
 * images at the top of a document entered again had none for the round trip. An image
 * made eager before its address is set takes the held copy, as a lazy one does in Chrome.
 * An image the page has not loaded stays lazy. docs/design-system.md, "A Repaint Keeps
 * Its Images", has the measurements.
 *
 * Only an address that names its bytes is held, so reuse is safe by construction: a
 * served file's address carries the version the render gave it (`raw_versions`), and a
 * replaced file has a new one; a pinned revision's files never change; and an image from
 * another origin is that host's to keep fresh, as Chrome reuses it anyway. An unversioned
 * address of a served file can change under the page, and is never held.
 *
 * @type {Set<string>}
 */
const heldImages = new Set();
/**
 * How many held images the page remembers; past it, the least recently loaded is
 * forgotten and loads lazily again. A document's first images load first, so one with
 * more images than this loses its first ones first.
 *
 * Measured 2026-11-13 through the link enhancer in the app's WKWebView (WebKit 21624) and
 * headless Chrome 152, with 60-character paths. An entry is 140 bytes of V8 heap after a
 * GC, 143 KB at this bound, and 321 bytes of JavaScriptCore heap capacity in the system
 * `jsc`, 329 KB. Remembering a load took 1 to 2.5 µs, and as long past the bound, where
 * each evicts one. Entering again a document of 1,024 held images asked for none of them
 * and showed it in 67 to 87 ms in WebKit and 50 to 66 ms in Chrome, against 58 to 62 and
 * 38 to 40 ms before images were held, with no frame over 50 ms; without them WebKit asked
 * for 224 images again. Both costs grow with the bound, and one re-entry makes at most
 * this many eager. The server versions only a document's first 256 files
 * (`_MAX_RAW_VERSIONS` in server.py), so a served image past them is never held.
 */
export const MAX_HELD_IMAGES = 1024;
/**
 * The images whose address names their bytes (`holdImage`): their loads are remembered.
 *
 * @type {WeakSet<Element>}
 */
const holdableImages = new WeakSet();

/**
 * Whether *href* is an image from another origin than the page's, which serves the
 * reader's files. Such an image keeps the address its author wrote, which is the key
 * the page holds it by.
 *
 * It is resolved against the page's address, as the browser resolves it, so a
 * scheme-relative `//host/badge.svg` is outside when its host is another (links.js
 * `resolveExternal` takes it as external), and only an http or https address is.
 *
 * @param {string} href
 */
export function isOutsideAddress(href) {
  const page = globalThis.location;
  if (!page?.href) {
    return false;
  }
  try {
    const url = new URL(href, page.href);
    return (url.protocol === "http:" || url.protocol === "https:") && url.origin !== page.origin;
  } catch (_error) {
    return false;
  }
}

/**
 * Remember *image*'s loads: its address names its bytes.
 *
 * @param {Element} image
 */
export function holdImage(image) {
  holdableImages.add(image);
}

/**
 * Make *image* eager if the page holds the image at *href*, before its address is set.
 *
 * The authored address goes first. An eager image asks for its address at once, and the
 * authored one, relative to the document, is not where the image is served.
 *
 * @param {Element} image
 * @param {string} href
 */
export function loadHeldImageEagerly(image, href) {
  if (heldImages.has(href)) {
    image.removeAttribute("src");
    image.setAttribute("loading", "eager");
  }
}

/**
 * The capture-phase load listener a rendered document's root carries.
 *
 * @param {Event} event
 */
export function rememberHeldImage(event) {
  const image = /** @type {Element | null} */ (event.target);
  if (!image || !holdableImages.has(image)) {
    return;
  }
  const href = image.getAttribute("src");
  if (!href) {
    return;
  }
  heldImages.delete(href);
  heldImages.add(href);
  if (heldImages.size > MAX_HELD_IMAGES) {
    const oldest = heldImages.values().next();
    if (!oldest.done) {
      heldImages.delete(oldest.value);
    }
  }
}

/**
 * Make each image from outside the served tree in *root* that the page holds eager,
 * before the page adopts it.
 *
 * Its authored address is the one it loads, so it has to arrive eager: created lazy, it
 * asked the network again on every return in WebKit and was blank for 3 frames, and an
 * image made eager after it was created lazy was blank as long (docs/design-system.md).
 * The link enhancer then lets its loads be remembered (`holdImage`).
 *
 * @param {ParentNode} root
 */
function loadHeldOutsideImagesEagerly(root) {
  for (const image of root.querySelectorAll("img[src]")) {
    const href = image.getAttribute("src");
    if (href && heldImages.has(href) && isOutsideAddress(href)) {
      image.setAttribute("loading", "eager");
    }
  }
}

/**
 * Put *rendered*'s HTML into *target*, replacing what is there, and resolve its links.
 *
 * A trusted render is parsed in a template, whose document loads nothing, so an image
 * from outside the served tree that the page holds is eager before the page adopts it.
 * `enhanced` is what *enhance* returned. `inert` is the inert render's module for a
 * render placed inert, whose table of contents the caller runs with its `inertArticle`
 * and `wireInertToc`, and null for a trusted render, whose KPress table of contents runs.
 *
 * @template T
 * @param {HTMLElement} target
 * @param {{html: string, inert?: boolean, toc?: boolean, model?: {headings?: unknown}, diagnostics?: Array<unknown>}} rendered
 * @param {MetabrowserPublicSdk} mb
 * @param {((root: HTMLElement) => T) | null} [enhance] Resolves the render's links and
 *   images under *root*; inert-render.js says when it runs for an inert render.
 * @param {((root: HTMLElement) => void) | null} [prepare] Consumes renderer-owned
 *   markers before links are admitted or rewritten.
 * @returns {Promise<{enhanced: T | null, inert: typeof import("./inert-render.js") | null}>}
 */
export async function placeRendered(target, rendered, mb, enhance = null, prepare = null) {
  if (rendered.inert !== true) {
    const template = target.ownerDocument.createElement("template");
    template.innerHTML = rendered.html;
    loadHeldOutsideImagesEagerly(template.content);
    target.replaceChildren(template.content);
    prepare?.(target);
    return { enhanced: enhance ? enhance(target) : null, inert: null };
  }
  const inert = await import("./inert-render.js");
  return { enhanced: await inert.placeRendered(target, rendered, mb, enhance, prepare), inert };
}

/**
 * Whether *diagnostic* is a render's `frontmatter_error`: why the file's front matter,
 * read from its own bytes by the server, is not shown as metadata.
 *
 * The document shows it once, as KPress's Frontmatter error notice ahead of the prose: a
 * trusted render carries KPress's own, and inert-render.js draws one for an inert render,
 * whose allowlist cannot keep it. So the Diagnostics disclosure does not list it again.
 *
 * @param {unknown} diagnostic
 * @returns {diagnostic is {type: "frontmatter_error", message: string}}
 */
export function isFrontmatterError(diagnostic) {
  if (!diagnostic || typeof diagnostic !== "object") {
    return false;
  }
  const value = /** @type {Record<string, unknown>} */ (diagnostic);
  return value.type === "frontmatter_error" && typeof value.message === "string";
}

/** What marks a Mermaid diagram in a trusted render, and in an inert one. */
const DIAGRAM_PROBE = '[data-kpress-diagram="mermaid"], pre[lang="mermaid"]';

/**
 * Draw the Mermaid diagrams a placed render holds, or do nothing when it holds none.
 *
 * The host (diagrams.js), KPress's diagram modules, and Mermaid itself are imported only
 * for a render that has a diagram, so a document without one fetches none of them. An
 * inert render's diagrams are drawn as images, and untrusted text's on a page that may have
 * no policy are drawn as images laid out in a frame of their own (diagrams.js,
 * `mountDiagrams`, has the modes). Returns null when there is nothing to draw.
 *
 * @param {ParentNode} root
 * @param {MetabrowserPublicSdk} mb
 * @param {"document" | "image" | "isolated"} mode
 * @returns {{dispose(): void, ready: Promise<void>} | null}
 */
export function drawDiagrams(root, mb, mode) {
  if (!root.querySelector(DIAGRAM_PROBE)) {
    return null;
  }
  let disposed = false;
  /** @type {{dispose(): void} | null} */
  let handle = null;
  const ready = import("./diagrams.js")
    .then((diagrams) => {
      if (disposed) {
        return undefined;
      }
      const mounted = diagrams.mountDiagrams(root, mb, { mode });
      handle = mounted;
      return mounted.ready;
    })
    .catch((error) => {
      console.warn("metabrowser markdown: the diagram renderer could not load", error);
    });
  return {
    ready,
    dispose() {
      disposed = true;
      handle?.dispose();
      handle = null;
    },
  };
}
