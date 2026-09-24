// Place a KPress render in the page, as rich HTML or, for an untrusted source, inert.
//
// The server marks a render `inert` when active content is off -- every served mirror,
// and a folder served with --untrusted -- after reducing its HTML to the allowlist in
// src/metabrowser/inert_html.py and dropping every KPress script from its assets. The
// page applies the same allowlist again with static/inert-html.js: it parses the HTML
// into an inert template and rebuilds only allowlisted nodes, in a document of their
// own inside a KPress article container this module builds, so KPress's stylesheets
// still set the reading type. The link enhancer resolves the article's links and images
// there, before the page adopts it, so an image loads only the address the enhancer
// gave it; a link or image past the enhancer's limit loses its address. When KPress
// drew a table of contents, the article gets the page's own, from the render's entries
// (inert-toc.js), ahead of the prose. A trusted render is inserted as it always was, and
// enhanced after.

// From the leaf module, not the enhancer: the enhancer reaches this module through its
// transclusions, and an import back would be a cycle.
import { MAX_ENHANCED_TARGETS } from "./dom-traversal.js";
import { buildInertToc, inertTocEntries, wireInertToc } from "./inert-toc.js";

export { wireInertToc };

/** @param {unknown} rendered */
export function isInertRender(rendered) {
  return (
    rendered !== null &&
    typeof rendered === "object" &&
    /** @type {{inert?: unknown}} */ (rendered).inert === true
  );
}

/**
 * The inert article `placeRendered` put in *root*, whose table of contents the page runs
 * with `wireInertToc`, or null for a trusted render, whose KPress runs.
 *
 * @param {Element} root
 */
export function inertArticle(root) {
  return root.querySelector(":scope > article.kpress-inert");
}

/**
 * Remove the address of every link and image past the enhancer's limit, which it would
 * leave as authored. Their text stays.
 *
 * @param {ParentNode} root
 */
export function dropUnadmittedTargets(root) {
  const targets = Array.from(root.querySelectorAll("a[href], img[src]"));
  for (const target of targets.slice(MAX_ENHANCED_TARGETS)) {
    target.removeAttribute(target.tagName.toLowerCase() === "a" ? "href" : "src");
  }
  return Math.max(0, targets.length - MAX_ENHANCED_TARGETS);
}

/**
 * Put *rendered*'s HTML into *target*, replacing what is there, and resolve its links.
 *
 * @template T
 * @param {HTMLElement} target
 * @param {{html: string, inert?: boolean, toc?: boolean, model?: {headings?: unknown}}} rendered
 * @param {MetabrowserPublicSdk} mb
 * @param {((root: HTMLElement) => T) | null} [enhance] Resolves the render's links and
 *   images under *root*. For an inert render it runs before the page adopts the nodes,
 *   on the prose alone: the page's table of contents, which navigates by itself
 *   (inert-toc.js), takes none of the enhancer's limit from the document's own links.
 * @returns {Promise<T | null>}
 */
export async function placeRendered(target, rendered, mb, enhance = null) {
  if (!isInertRender(rendered)) {
    target.innerHTML = rendered.html;
    return enhance ? enhance(target) : null;
  }
  await mb.ensureAsset("inert-html");
  const inert = window.MetabrowserInertHtml;
  if (!inert) {
    throw new Error("The untrusted-Markdown sanitizer is unavailable.");
  }
  // A null base: references inside the document stay as written, for the link
  // enhancer to resolve inside the served root or pin.
  const nodes = inert.sanitizeHtml(String(rendered.html), null);
  const scratch = nodes[0]?.ownerDocument ?? document.implementation.createHTMLDocument("");
  const article = scratch.createElement("article");
  article.className = "kpress kpress-doc kpress-inert";
  const layout = scratch.createElement("div");
  layout.className = "kpress-doc-layout";
  const prose = scratch.createElement("div");
  prose.className = "kpress-prose";
  prose.append(...nodes);
  const toc =
    rendered.toc === true
      ? buildInertToc(scratch, inertTocEntries(rendered.model?.headings, prose))
      : null;
  if (toc) {
    layout.classList.add("kpress-content-with-toc");
    layout.append(...toc);
  }
  layout.append(prose);
  article.append(layout);
  dropUnadmittedTargets(prose);
  const enhanced = enhance
    ? enhance(/** @type {HTMLElement} */ (/** @type {unknown} */ (prose)))
    : null;
  target.replaceChildren(article);
  return enhanced;
}
