// A rendered document's print button: the printer glyph in the upper right corner of its
// card, which makes the document ready to print (print-ready.js) and then prints the view
// the browser's way, as Command-P does.
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
// files. Every Document view and the Overview's README use it. What a click prints with,
// print-ready.js, is on demand: the click waits for the document anyway, and a view
// nobody prints never fetches it.

/** The button's accessible name and tooltip. */
export const PRINT_INDICATOR_LABEL = "Print document";

/** How many rendered documents hold the print theme (`holdLightPrintTheme`). */
let printThemeHolders = 0;
/** The theme a print replaced, while one is printing; null otherwise. */
let replacedTheme =
  /** @type {{theme: string | null, kpress: string | null, anim: boolean} | null} */ (null);

/**
 * Paper is light: KPress's print palette (print.css) and its light syntax colors, whatever
 * the app's theme. KPress keys its dark palette on the page's resolved theme
 * (`data-kpress-resolved-theme`, which app.js sets with `data-theme`), and so did a
 * document printed in the dark theme: light code on white paper, a dark ground behind a
 * table's header. For the print, the page resolves light, and after it, as it was.
 *
 * `beforeprint` comes before the print's layout in Chrome, for Command-P and the button
 * alike, and in WebKit's print operation, the app's File > Print. The theme crossfade
 * (`html.theme-anim`) is off meanwhile, so the print does not catch a color between the
 * two. Nothing is told the theme changed, so a Mermaid diagram keeps the colors it was
 * drawn in.
 */
function printLight() {
  const root = document.documentElement;
  if (replacedTheme !== null || root.getAttribute("data-theme") !== "dark") {
    return;
  }
  replacedTheme = {
    theme: root.getAttribute("data-theme"),
    kpress: root.getAttribute("data-kpress-resolved-theme"),
    anim: root.classList.contains("theme-anim"),
  };
  root.classList.remove("theme-anim");
  root.setAttribute("data-theme", "light");
  root.setAttribute("data-kpress-resolved-theme", "light");
}

/** After a print, the theme `printLight` replaced. */
function restoreTheme() {
  const replaced = replacedTheme;
  if (replaced === null) {
    return;
  }
  replacedTheme = null;
  const root = document.documentElement;
  for (const [name, value] of /** @type {const} */ ([
    ["data-theme", replaced.theme],
    ["data-kpress-resolved-theme", replaced.kpress],
  ])) {
    if (value === null) {
      root.removeAttribute(name);
    } else {
      root.setAttribute(name, value);
    }
  }
  if (replaced.anim) {
    root.classList.add("theme-anim");
  }
}

/**
 * Print in the light theme while a rendered document is on the page (`printLight`), and
 * return its release. The window's two listeners are added for the first holder and
 * removed with the last. Where there is no window, as in a browserless session that mounts
 * a document to read its markup, nothing prints, and the release does nothing.
 *
 * @returns {() => void}
 */
export function holdLightPrintTheme() {
  if (typeof window === "undefined") {
    return () => {};
  }
  printThemeHolders += 1;
  if (printThemeHolders === 1) {
    window.addEventListener("beforeprint", printLight);
    window.addEventListener("afterprint", restoreTheme);
  }
  let released = false;
  return () => {
    if (released) {
      return;
    }
    released = true;
    printThemeHolders -= 1;
    if (printThemeHolders === 0) {
      window.removeEventListener("beforeprint", printLight);
      window.removeEventListener("afterprint", restoreTheme);
      restoreTheme();
    }
  };
}

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
 * A click waits for the document to be ready to print, its images, KPress's print faces,
 * and its diagrams (print-ready.js), at most `PRINT_READY_BOUND_MS`, and then prints; a
 * click while it waits prints nothing more.
 *
 * @param {HTMLElement} container
 * @param {Pick<MetabrowserPublicSdk, "icons" | "ownDelegate">} mb
 * @param {{diagrams?: () => Promise<unknown> | null | undefined}} [options] `diagrams`
 *   returns the promise that settles once the document's diagrams are drawn, if any.
 * @returns {() => void}
 */
export function mountPrintIndicator(container, mb, options = {}) {
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
  let disposed = false;
  let preparing = false;
  // The print the browser runs for Command-P, and the macOS app for File > Print, which
  // answers a page's `window.print()` (apps/macos PagePrint.swift).
  const onClick = () => {
    if (preparing) {
      return;
    }
    preparing = true;
    button.setAttribute("aria-busy", "true");
    void import("./print-ready.js")
      .then(({ preparePrint }) => preparePrint(container, { diagrams: options.diagrams }))
      .catch((error) => {
        console.warn("metabrowser markdown: the document could not be made ready to print", error);
      })
      .then(() => {
        preparing = false;
        button.removeAttribute("aria-busy");
        if (!disposed) {
          window.print();
        }
      });
  };
  button.addEventListener("click", onClick);
  card.append(button);
  return () => {
    if (disposed) {
      return;
    }
    disposed = true;
    button.removeEventListener("click", onClick);
    button.remove();
  };
}
