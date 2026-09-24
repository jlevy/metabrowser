// The table of contents of an inert render, which the page draws and runs itself.
//
// Under the untrusted profile the server takes KPress's table of contents out of the
// HTML and sends none of KPress's scripts, since the page's Content-Security-Policy runs
// scripts only from its own static paths (capabilities.untrusted_shell_csp). The render
// keeps KPress's entries -- `model.headings`, each pointing at its heading's
// `user-content-` anchor (kpress_adapter.inert_render) -- and `toc` says whether KPress
// drew one. `buildInertToc` draws it from those entries in KPress's markup, so KPress's
// stylesheets place it in the side rail or the narrow drawer, and `wireInertToc` runs
// what KPress's toc.js would: the entry for the section at the reading line is active,
// and the narrow toggle opens and closes the drawer. The entry titles are the
// document's text; they only ever become text nodes.

import { findElementById } from "./dom-traversal.js";
import { selectTocTargetAtReadingLine } from "./toc-intersection-fallback.js";

/** KPress's reading line: the bottom of the top quarter of the scroll viewport. */
const READING_LINE = 0.25;
/** How far the reader scrolls before the narrow toggle shows, as in KPress. */
const TOGGLE_SCROLL_THRESHOLD_PX = 100;
const ANCHOR_HREF = "#user-content-";

/**
 * The entries of *headings* whose target is in *root*: KPress's depth, title, and the
 * anchor they point at.
 *
 * @param {unknown} headings
 * @param {ParentNode} root
 * @returns {Array<{level: number, title: string, href: string}>}
 */
export function inertTocEntries(headings, root) {
  if (!Array.isArray(headings)) {
    return [];
  }
  return headings.flatMap((entry) => {
    if (!entry || typeof entry !== "object") {
      return [];
    }
    const { href, level, title } = /** @type {Record<string, unknown>} */ (entry);
    if (
      typeof href !== "string" ||
      !href.startsWith(ANCHOR_HREF) ||
      typeof title !== "string" ||
      !Number.isInteger(level) ||
      !findElementById(root, href.slice(1))
    ) {
      return [];
    }
    return [{ href, level: Math.min(Math.max(Number(level), 1), 6), title }];
  });
}

/**
 * KPress's table-of-contents markup for *entries*: the narrow toggle, its backdrop, and
 * the nav, in that order, for the layout ahead of the prose. Null for no entries.
 *
 * @param {Pick<Document, "createElement" | "createTextNode">} doc
 * @param {ReadonlyArray<{level: number, title: string, href: string}>} entries
 * @returns {Element[] | null}
 */
export function buildInertToc(doc, entries) {
  if (!entries.length) {
    return null;
  }
  const toggle = doc.createElement("button");
  toggle.className = "kpress-toc-toggle";
  toggle.setAttribute("type", "button");
  toggle.setAttribute("aria-expanded", "false");
  toggle.setAttribute("aria-label", "Table of contents");
  toggle.setAttribute("title", "Table of contents");
  toggle.append(doc.createTextNode("☰"));
  const backdrop = doc.createElement("div");
  backdrop.className = "kpress-toc-backdrop";
  backdrop.setAttribute("aria-hidden", "true");
  const nav = doc.createElement("nav");
  nav.className = "kpress-toc kpress-no-print";
  nav.setAttribute("aria-label", "Table of contents");
  const heading = doc.createElement("div");
  heading.className = "kpress-toc-title toc-title";
  heading.append(doc.createTextNode("Contents"));
  const list = doc.createElement("ol");
  list.className = "toc-list";
  for (const entry of entries) {
    const item = doc.createElement("li");
    item.className = `kpress-toc-level-${entry.level} toc-h${entry.level}`;
    const link = doc.createElement("a");
    link.className = "toc-link";
    link.setAttribute("href", entry.href);
    link.append(doc.createTextNode(entry.title));
    item.append(link);
    list.append(item);
  }
  nav.append(heading, list);
  return [toggle, backdrop, nav];
}

/**
 * Run the table of contents `buildInertToc` drew in *article*: the entry for the section
 * at the reading line is active, and the narrow toggle opens and closes the drawer.
 *
 * @param {Element} article
 * @param {{
 *   cancel?: (handle: number) => void,
 *   schedule?: (callback: FrameRequestCallback) => number,
 *   windowTarget?: Pick<Window, "addEventListener" | "removeEventListener" | "innerHeight" | "scrollY">,
 * }} [options]
 * @returns {() => void}
 */
export function wireInertToc(article, options = {}) {
  const nav = article.querySelector(".kpress-toc");
  const toggle = article.querySelector(".kpress-toc-toggle");
  const backdrop = article.querySelector(".kpress-toc-backdrop");
  if (!nav || !toggle) {
    return () => {};
  }
  const schedule = options.schedule ?? ((callback) => requestAnimationFrame(callback));
  const cancel = options.cancel ?? ((handle) => cancelAnimationFrame(handle));
  const windowTarget = options.windowTarget ?? window;
  const viewport = /** @type {HTMLElement | null} */ (article.closest("[data-kpress-viewport]"));
  const scroller = viewport ?? windowTarget;
  const links = Array.from(nav.querySelectorAll("a.toc-link"));
  const targets = links.flatMap((link) => {
    const target = findElementById(article, (link.getAttribute("href") ?? "").slice(1));
    return target ? [{ link, target }] : [];
  });
  /** @type {Array<() => void>} */
  const cleanups = [];
  /**
   * @param {Pick<EventTarget, "addEventListener" | "removeEventListener">} target
   * @param {string} type
   * @param {EventListener} listener
   */
  const on = (target, type, listener) => {
    target.addEventListener(type, listener);
    cleanups.push(() => target.removeEventListener(type, listener));
  };

  /** @param {Element | undefined} active */
  const setActive = (active) => {
    for (const link of links) {
      const isActive = link === active;
      link.classList.toggle("active", isActive);
      if (isActive) {
        link.setAttribute("data-active", "true");
      } else {
        link.removeAttribute("data-active");
      }
    }
  };
  /** @param {boolean} expanded */
  const setExpanded = (expanded) => {
    toggle.setAttribute("aria-expanded", String(expanded));
    nav.classList.toggle("kpress-mobile-visible", expanded);
    backdrop?.classList.toggle("kpress-visible", expanded);
    backdrop?.setAttribute("aria-hidden", String(!expanded));
  };
  const scrollTop = () => (viewport ? viewport.scrollTop : windowTarget.scrollY);
  const readingLine = () => {
    if (viewport) {
      const rect = viewport.getBoundingClientRect();
      return rect.top + (rect.height || viewport.clientHeight) * READING_LINE;
    }
    return windowTarget.innerHeight * READING_LINE;
  };
  const update = () => {
    toggle.classList.toggle("show-toggle", scrollTop() > TOGGLE_SCROLL_THRESHOLD_PX);
    const selected = selectTocTargetAtReadingLine(
      targets.map(({ target }) => target),
      readingLine(),
    );
    const current = targets.find(({ target }) => target === selected?.target);
    setActive((current ?? targets[0])?.link);
  };

  let frame = 0;
  on(scroller, "scroll", () => {
    if (!frame) {
      frame = schedule(() => {
        frame = 0;
        update();
      });
    }
  });
  on(toggle, "click", () => setExpanded(toggle.getAttribute("aria-expanded") !== "true"));
  if (backdrop) {
    on(backdrop, "click", () => setExpanded(false));
  }
  for (const link of links) {
    on(link, "click", () => {
      setActive(link);
      setExpanded(false);
    });
  }
  update();
  return () => {
    for (const cleanup of cleanups) {
      cleanup();
    }
    if (frame) {
      cancel(frame);
      frame = 0;
    }
  };
}
