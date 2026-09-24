// Place a KPress render in the page, as rich HTML or, for an untrusted source, inert.
//
// The server marks a render `inert` when active content is off -- every served mirror,
// and a folder served with --untrusted -- after reducing its HTML to the allowlist in
// src/metabrowser/inert_html.py and dropping every KPress script from its assets. The
// page applies the same allowlist again with static/inert-html.js: it parses the HTML
// into an inert template and inserts only nodes rebuilt from the allowlist, inside a
// KPress article container this module builds, so KPress's stylesheets still set the
// reading type. A trusted render is inserted as it always was.

/** @param {unknown} rendered */
export function isInertRender(rendered) {
  return (
    rendered !== null &&
    typeof rendered === "object" &&
    /** @type {{inert?: unknown}} */ (rendered).inert === true
  );
}

/**
 * Put *rendered*'s HTML into *target*, replacing what is there.
 *
 * @param {HTMLElement} target
 * @param {{html: string, inert?: boolean}} rendered
 * @param {MetabrowserPublicSdk} mb
 */
export async function placeRendered(target, rendered, mb) {
  if (!isInertRender(rendered)) {
    target.innerHTML = rendered.html;
    return;
  }
  await mb.ensureAsset("inert-html");
  const inert = window.MetabrowserInertHtml;
  if (!inert) {
    throw new Error("The untrusted-Markdown sanitizer is unavailable.");
  }
  const article = document.createElement("article");
  article.className = "kpress kpress-doc kpress-inert";
  const layout = document.createElement("div");
  layout.className = "kpress-doc-layout";
  const prose = document.createElement("div");
  prose.className = "kpress-prose";
  // A null base: references inside the document stay as written, for the link
  // enhancer to resolve inside the served root or pin.
  prose.replaceChildren(...inert.sanitizeHtml(String(rendered.html), null));
  layout.append(prose);
  article.append(layout);
  target.replaceChildren(article);
}
