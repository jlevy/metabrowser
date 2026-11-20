// What a rendered document needs before it prints: the KPress print model's inputs, which
// the screen never loads, made ready, so the print is the one KPress's own export draws.
//
// - Images. KPress writes `loading="lazy"` on a document's images, and an image the reader
//   has not scrolled to has no bytes. Chrome fetches them for a print; WebKit, the macOS
//   app's engine, prints them as nothing, and switching them to eager at `beforeprint` is
//   too late: its print operation draws first, and an image already shown went blank
//   with them (measured 2026-11-19 through apps/macos/webkit-gate's driver).
// - Print faces. KPress declares its static sans instances ("KPress Print Sans",
//   print-fonts.css) inside `@media print`, so nothing fetches them until print layout
//   asks, and a print issued then draws before they arrive, in the variable face's Type3
//   outlines. KPress's PDF export waits for them (kpress/format/pdf.py,
//   `_PRINT_FONTS_READY_JS`); a page cannot force print layout, so this adds the same
//   faces, read from KPress's own rules, to the page's font set and loads them.
// - Diagrams. A Mermaid diagram not yet drawn prints as its source.
// - A heading before an image. WebKit ignores KPress's `break-after: avoid`, and an image
//   cannot break, so a heading with too little room below it for the image printed alone
//   at a page's foot. markdown.css reserves room below every heading for the next lines;
//   once the image has loaded its size is known, and the heading reserves the image too.
//
// The print button (print-indicator.js) waits for `preparePrint` and then calls
// `window.print()`. docs/design-system.md, "Print", has the rule.
//
// Loading tier: on demand. print-indicator.js imports it when the button is clicked, since
// the click waits for the document anyway; it imports nothing.

/**
 * The longest a print waits for its document, after which it prints what has arrived.
 *
 * Measured 2026-11-19 on a 10-core Mac at a load average of 70 to 90, in headless Chrome
 * 152 against a served folder, from the click to the page's `window.print()`: 33 to 37 ms
 * for this repository's README (two images, one not yet shown, and the twelve print
 * faces, 185 KB), 23 to 62 ms for the same README on the folder's Overview, and 16 to
 * 19 ms for a 4,700-word document with three screenshots below the fold. In the app's
 * WKWebView, through apps/macos/webkit-gate's driver, the whole print of that document,
 * the wait and the print operation, took 2.0 to 3.5 s. The bound is not that cost: it
 * is for an image that never answers, which should not keep a print from starting.
 */
export const PRINT_READY_BOUND_MS = 3000;

/**
 * Make each image in *root* that has not loaded eager, and resolve, with how many it
 * waited for, once each has loaded or failed.
 *
 * An image that has loaded is left alone: in WebKit, setting `loading` on one that is
 * shown made it blank for the print.
 *
 * @param {ParentNode} root
 * @returns {Promise<number>}
 */
export function loadImagesForPrint(root) {
  /** @type {Promise<void>[]} */
  const pending = [];
  for (const image of /** @type {Iterable<HTMLImageElement>} */ (root.querySelectorAll("img"))) {
    if (image.complete) {
      continue;
    }
    pending.push(
      new Promise((resolve) => {
        const settle = () => {
          image.removeEventListener("load", settle);
          image.removeEventListener("error", settle);
          resolve();
        };
        image.addEventListener("load", settle);
        image.addEventListener("error", settle);
      }),
    );
    if (image.getAttribute("loading") === "lazy") {
      image.setAttribute("loading", "eager");
    }
  }
  return Promise.all(pending).then(() => pending.length);
}

/** An image, alone or as a link's or a picture's. */
const IMAGE = ":scope > img, :scope > a > img, :scope > picture > img";

/**
 * The image that is all of *block*, a heading's next sibling, or null: the image itself,
 * as the inert render keeps one (its sanitizer drops KPress's `figure`), or a figure,
 * paragraph, link, or picture holding one image and no words.
 *
 * @param {Element | null} block
 * @returns {HTMLImageElement | null}
 */
function soleImage(block) {
  if (!block) {
    return null;
  }
  if (block.matches("img")) {
    return /** @type {HTMLImageElement} */ (block);
  }
  if (!block.matches("figure, p, a, picture")) {
    return null;
  }
  const image = block.querySelector(IMAGE) ?? block.querySelector(":scope > a > picture > img");
  if (!image) {
    return null;
  }
  // A paragraph with words beside its image is prose, which can break; a figure's words
  // are its caption.
  if (!block.matches("figure") && (block.textContent || "").trim() !== "") {
    return null;
  }
  return /** @type {HTMLImageElement} */ (image);
}

/**
 * Give each heading in *root* that an image follows the image's size, which markdown.css
 * reserves below the heading in print: `--print-next-image-width`, the width it is drawn
 * at most (its `width` attribute, or its own), and `--print-next-image-ratio`, its height
 * over its width. Resolve with how many headings it marked. An image that did not load
 * has no size and marks nothing.
 *
 * @param {ParentNode} root
 * @returns {number}
 */
export function keepHeadingsWithImages(root) {
  let marked = 0;
  for (const heading of /** @type {Iterable<HTMLElement>} */ (
    root.querySelectorAll("h1, h2, h3, h4, h5, h6")
  )) {
    const image = soleImage(heading.nextElementSibling);
    const natural = image && image.naturalWidth > 0 && image.naturalHeight > 0;
    if (!image || !natural) {
      heading.style.removeProperty("--print-next-image-width");
      heading.style.removeProperty("--print-next-image-ratio");
      continue;
    }
    const authored = Number.parseFloat(image.getAttribute("width") || "");
    const width = authored > 0 ? authored : image.naturalWidth;
    heading.style.setProperty("--print-next-image-width", `${width}px`);
    heading.style.setProperty(
      "--print-next-image-ratio",
      String(image.naturalHeight / image.naturalWidth),
    );
    marked += 1;
  }
  return marked;
}

/**
 * The print faces this page has added, by the rule's text, so a second print adds none.
 *
 * @type {Map<string, FontFace>}
 */
const printFaces = new Map();

/**
 * The `@font-face` rules *doc*'s stylesheets declare inside `@media print`, each with the
 * address its sources resolve against.
 *
 * @param {Document} doc
 * @returns {Array<{rule: CSSFontFaceRule, base: string}>}
 */
function printFaceRules(doc) {
  const view = doc.defaultView;
  if (!view) {
    return [];
  }
  /** @type {Array<{rule: CSSFontFaceRule, base: string}>} */
  const found = [];
  for (const sheet of Array.from(doc.styleSheets)) {
    /** @type {CSSRuleList} */
    let rules;
    try {
      rules = sheet.cssRules;
    } catch {
      // A stylesheet from another origin hides its rules; KPress's are the page's own.
      continue;
    }
    const base = sheet.href || doc.baseURI;
    for (const rule of Array.from(rules)) {
      if (!(rule instanceof view.CSSMediaRule) || !rule.media.mediaText.includes("print")) {
        continue;
      }
      for (const inner of Array.from(rule.cssRules)) {
        if (inner instanceof view.CSSFontFaceRule) {
          found.push({ rule: inner, base });
        }
      }
    }
  }
  return found;
}

/**
 * A `src` descriptor with each `url(…)` resolved against *base*, which a FontFace, unlike
 * its stylesheet, does not know.
 *
 * @param {string} src
 * @param {string} base
 */
function absoluteSources(src, base) {
  return src.replace(/url\(\s*(["']?)([^"')]+)\1\s*\)/g, (_match, _quote, address) => {
    return `url("${new URL(address, base).href}")`;
  });
}

/**
 * Add the faces *doc* declares for print to its font set, and load them; resolve with how
 * many it loaded. A face that fails is skipped: the print falls back as it would have.
 *
 * @param {Document} doc
 * @returns {Promise<number>}
 */
export function loadPrintFaces(doc) {
  const view = doc.defaultView;
  if (!view || typeof view.FontFace !== "function" || !doc.fonts) {
    return Promise.resolve(0);
  }
  /** @type {Promise<unknown>[]} */
  const loads = [];
  for (const { rule, base } of printFaceRules(doc)) {
    const style = rule.style;
    const family = style.getPropertyValue("font-family").trim();
    const src = style.getPropertyValue("src").trim();
    if (!family || !src) {
      continue;
    }
    const key = rule.cssText;
    let face = printFaces.get(key);
    if (!face) {
      /** @type {FontFaceDescriptors} */
      const descriptors = {};
      const weight = style.getPropertyValue("font-weight").trim();
      const fontStyle = style.getPropertyValue("font-style").trim();
      const range = style.getPropertyValue("unicode-range").trim();
      if (weight) {
        descriptors.weight = weight;
      }
      if (fontStyle) {
        descriptors.style = fontStyle;
      }
      if (range) {
        descriptors.unicodeRange = range;
      }
      face = new view.FontFace(
        family.replace(/^["']|["']$/g, ""),
        absoluteSources(src, base),
        descriptors,
      );
      printFaces.set(key, face);
      doc.fonts.add(face);
    }
    loads.push(face.load().catch(() => undefined));
  }
  return Promise.all(loads).then(() => loads.length);
}

/**
 * Make the document in *container* ready to print, as KPress's export does before it
 * draws, and resolve with what it waited for. It resolves at `PRINT_READY_BOUND_MS` at
 * the latest, with `timedOut` set, and never rejects.
 *
 * @param {HTMLElement} container
 * @param {{diagrams?: (() => Promise<unknown> | null | undefined) | null, boundMs?: number}} [options]
 * @returns {Promise<{images: number, faces: number, diagrams: boolean, headings: number, timedOut: boolean}>}
 */
export function preparePrint(container, options = {}) {
  const doc = container.ownerDocument;
  const diagrams = options.diagrams?.() ?? null;
  const images = loadImagesForPrint(container).catch(() => 0);
  const ready = Promise.all([
    images,
    loadPrintFaces(doc).catch(() => 0),
    diagrams ? Promise.resolve(diagrams).catch(() => undefined) : Promise.resolve(),
  ]).then(([loaded, faces]) => ({
    images: loaded,
    faces,
    diagrams: diagrams !== null,
    headings: keepHeadingsWithImages(container),
    timedOut: false,
  }));
  const boundMs = options.boundMs ?? PRINT_READY_BOUND_MS;
  /** @type {ReturnType<typeof setTimeout> | undefined} */
  let timer;
  const bound = new Promise((resolve) => {
    timer = setTimeout(() => {
      // What has loaded by now prints; its headings keep with it.
      const headings = keepHeadingsWithImages(container);
      resolve({ images: -1, faces: -1, diagrams: diagrams !== null, headings, timedOut: true });
    }, boundMs);
  });
  return /** @type {Promise<{images: number, faces: number, diagrams: boolean, headings: number, timedOut: boolean}>} */ (
    Promise.race([ready, bound]).finally(() => clearTimeout(timer))
  );
}
