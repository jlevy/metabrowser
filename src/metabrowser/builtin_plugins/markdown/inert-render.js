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
// (inert-toc.js), ahead of the prose; and when the file's front matter was not read, the
// page's own Frontmatter error notice, from its diagnostic, ahead of the layout as KPress
// puts it in a trusted render. A trusted render is inserted as it always was, and
// enhanced after. The views place a render through place-rendered.js, which imports this
// module on the first inert render, so a trusted folder's Markdown view never loads it.

// From the leaf module, not the enhancer: the enhancer reaches this module through its
// transclusions, and an import back would be a cycle.
import { MAX_ENHANCED_TARGETS } from "./dom-traversal.js";
import { buildInertToc, inertTocEntries, wireInertToc } from "./inert-toc.js";
// Already loaded: it imports this module, on demand.
import { isFrontmatterError } from "./place-rendered.js";

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
 * KPress's Frontmatter error notice saying *said*, as a trusted render draws it ahead of
 * the layout (kpress/format/render.py, `_render_frontmatter_error`).
 *
 * The server takes KPress's own out of an inert render, whose allowlist would keep only
 * its words run into the prose (`kpress_adapter.inert_render`), and the sentence it said
 * stays in the render's `frontmatter_error` diagnostic; the parser's reason is the
 * answer's `frontmatter_error_detail`, which the page does not show. The page's own
 * markup carries KPress's class, as the inert table of contents does, so KPress's
 * stylesheet draws the box; the sentence is text. Its role is `status`, not KPress's
 * `alert`: the document is shown and only its metadata is not, which is a warning
 * (docs/design-system-messages.md, "Kinds of Message"), as the diagnostic's severity says.
 *
 * @param {Document} doc
 * @param {string} said
 */
function frontmatterErrorNotice(doc, said) {
  const notice = doc.createElement("aside");
  notice.className = "kpress-frontmatter-error";
  notice.setAttribute("role", "status");
  notice.setAttribute("aria-label", "Frontmatter error");
  const title = doc.createElement("strong");
  title.append(doc.createTextNode("Frontmatter error"));
  const message = doc.createElement("span");
  message.append(doc.createTextNode(said));
  notice.append(title, message);
  return notice;
}

/**
 * Put *rendered*'s HTML into *target*, replacing what is there, and resolve its links.
 *
 * @template T
 * @param {HTMLElement} target
 * @param {{html: string, inert?: boolean, toc?: boolean, frontmatter_disclosure?: boolean, model?: {headings?: unknown}, diagnostics?: Array<unknown>}} rendered
 * @param {MetabrowserPublicSdk} mb
 * @param {((root: HTMLElement) => T) | null} [enhance] Resolves the render's links and
 *   images under *root*. For an inert render it runs before the page adopts the nodes,
 *   on the prose alone: the page's table of contents, which navigates by itself
 *   (inert-toc.js), takes none of the enhancer's limit from the document's own links.
 * @param {((root: HTMLElement) => void) | null} [prepare] Consumes renderer-owned
 *   markers after sanitization and before the link budget is applied.
 * @returns {Promise<T | null>}
 */
export async function placeRendered(target, rendered, mb, enhance = null, prepare = null) {
  if (!isInertRender(rendered)) {
    target.innerHTML = rendered.html;
    prepare?.(target);
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
  // KPress's card and column, as a trusted render stamps them: `.kpress-long-text` is what
  // holds the text to the reader's measure, and without it the text is an inset-pair wider.
  article.setAttribute("data-kpress-card", "on");
  const layout = scratch.createElement("div");
  layout.className = "kpress-doc-layout";
  const prose = inert.kpressProse(nodes, scratch);
  prose.classList.add("kpress-long-text");
  const toc =
    rendered.toc === true
      ? buildInertToc(scratch, inertTocEntries(rendered.model?.headings, prose))
      : null;
  if (toc) {
    layout.classList.add("kpress-content-with-toc");
    layout.append(...toc);
  }
  layout.append(prose);
  const frontmatterError = rendered.diagnostics?.find(isFrontmatterError);
  if (frontmatterError) {
    article.append(frontmatterErrorNotice(scratch, frontmatterError.message));
  }
  // The server saw the disclosure in KPress's generated chrome before sanitizing
  // the article. That disclosure precedes every authored detail in the document.
  if (rendered.frontmatter_disclosure) {
    const metadata = prose.querySelector("details");
    if (metadata) {
      metadata.className = "kpress-frontmatter kpress-no-print";
      article.append(metadata);
    }
  }
  article.append(layout);

  const content = /** @type {HTMLElement} */ (/** @type {unknown} */ (prose));
  prepare?.(content);
  dropUnadmittedTargets(content);
  const enhanced = enhance ? enhance(content) : null;
  target.replaceChildren(article);
  return enhanced;
}
