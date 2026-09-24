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
// gave it; a link or image past the enhancer's limit loses its address. A trusted
// render is inserted as it always was, and enhanced after.

// From the leaf module, not the enhancer: the enhancer reaches this module through its
// transclusions, and an import back would be a cycle.
import { MAX_ENHANCED_TARGETS } from "./dom-traversal.js";

/** @param {unknown} rendered */
export function isInertRender(rendered) {
  return (
    rendered !== null &&
    typeof rendered === "object" &&
    /** @type {{inert?: unknown}} */ (rendered).inert === true
  );
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
 * @param {{html: string, inert?: boolean}} rendered
 * @param {MetabrowserPublicSdk} mb
 * @param {((root: HTMLElement) => T) | null} [enhance] Resolves the render's links and
 *   images under *root*. For an inert render it runs before the page adopts the nodes.
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
  layout.append(prose);
  article.append(layout);
  dropUnadmittedTargets(article);
  const enhanced = enhance
    ? enhance(/** @type {HTMLElement} */ (/** @type {unknown} */ (article)))
    : null;
  target.replaceChildren(article);
  return enhanced;
}
