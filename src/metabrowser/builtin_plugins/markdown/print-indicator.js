// A rendered document's print button: the printer glyph in the upper right corner of its
// card, which prints the view the browser's way, as Command-P does.
//
// A host turns it on for a mount (`printIndicator: true`, rendered.js): the Markdown file
// view and the README on a folder's Overview do, the two places whose print is the
// rendered document itself. A source view, and any other host, prints with Command-P and
// draws none. The button is absolute in the card's own padding, so placing it moves
// nothing, and it shows only where KPress draws the card, in a pane 48rem or wider;
// markdown.css has the placement, and docs/design-system.md, "Print", the rule.
//
// KPress's own document actions (its `doc-actions` widget) are where it belongs, as an
// option a host turns on, but they do not fit an embedded document yet: no markup in an
// embed's fragment, so nothing under the untrusted profile, which runs no KPress script; a
// PDF badge with a native tooltip; and a placement that pads a paragraph-first document
// down. mb-jue2 records the API and markup KPress needs, and then this module goes. Until
// then it draws the button for both trust profiles.
//
// Loading tier: eager with the Markdown plugin, a static import of rendered.js beside
// toc-toggle.js, which imports nothing, so it adds a request and no level of imports.
// Measured 2026-11-18 in headless Chrome 152 on a trusted folder's first Markdown view:
// 2,087 bytes transferred and 3,870 decoded, of 69,945 and 222,398 for the plugin's 19
// files. Every Document view and the Overview's README use it.

/** The button's accessible name and tooltip. */
export const PRINT_INDICATOR_LABEL = "Print document";

/**
 * The card of the document *container* holds: KPress's `.kpress-long-text`, the column
 * its trusted render and the inert render (inert-render.js) both draw. Null for a render
 * that failed, which has none, and never a transclusion's card nested in the document.
 *
 * @param {Element} container
 * @returns {HTMLElement | null}
 */
export function documentCard(container) {
  return /** @type {HTMLElement | null} */ (
    container.querySelector(":scope > article.kpress > .kpress-doc-layout > .kpress-long-text")
  );
}

/**
 * Place the print button in the card of the document *container* holds, and return its
 * disposer, which removes it; with no card, a disposer that does nothing.
 *
 * The button is the page's, marked with `mb.ownDelegate`, which the tooltip recognizes by
 * the element itself, so it keeps its tooltip inside the document, whose own markup takes
 * none (app.js `tipTextAnchor`), and its listener is its own, so a document that spells its
 * markup prints nothing. It goes last in the card, after the document's text, and so last
 * in focus order: first, it would take the place KPress's spacing rules give a leading
 * heading (`h1:first-child`). Command-P is the keyboard route to print.
 *
 * @param {HTMLElement} container
 * @param {Pick<MetabrowserPublicSdk, "icons" | "ownDelegate">} mb
 * @returns {() => void}
 */
export function mountPrintIndicator(container, mb) {
  const card = documentCard(container);
  if (!card) {
    return () => {};
  }
  const button = container.ownerDocument.createElement("button");
  button.type = "button";
  button.className = "icon-btn metabrowser-print-indicator";
  button.setAttribute("aria-label", PRINT_INDICATOR_LABEL);
  button.setAttribute("data-tip-text", PRINT_INDICATOR_LABEL);
  button.innerHTML = mb.icons.print || "";
  mb.ownDelegate(button);
  // The print the browser runs for Command-P, and the macOS app for File > Print, which
  // answers a page's `window.print()` (apps/macos PagePrint.swift).
  const onClick = () => window.print();
  button.addEventListener("click", onClick);
  card.append(button);
  let disposed = false;
  return () => {
    if (disposed) {
      return;
    }
    disposed = true;
    button.removeEventListener("click", onClick);
    button.remove();
  };
}
