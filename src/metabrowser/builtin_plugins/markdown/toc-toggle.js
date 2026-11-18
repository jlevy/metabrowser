// When a rendered document's narrow table-of-contents toggle shows, for every table of
// contents Metabrowser runs: KPress's own (toc.js) for a trusted render, through the policy
// KPress lets a host replace, and the page's own (inert-toc.js) for an inert one.
//
// KPress shows the toggle once its scroll viewport has scrolled past a threshold, which
// assumes the document starts the viewport. In Metabrowser the pane holds more than the
// document: a file's header above it, or the Folder Overview's other panels above its
// README. So the toggle also waits for the reader to reach the document, its top at or
// above the pane's, and goes again once the reader is above or past it. A file's document
// starts within the threshold of the pane's top, so the threshold decides there as in
// KPress; the README starts further down, so reaching it decides, and its toggle appears
// as the reader scrolls to its beginning.

/**
 * How far the pane scrolls before a toggle shows: KPress's `TOC_TOGGLE_SCROLL_THRESHOLD_PX`
 * in toc.js, which tests/golden/cli-ui-markdown-scrollspy.tryscript.md records beside this.
 */
export const TOC_TOGGLE_SCROLL_THRESHOLD_PX = 100;

/**
 * A scroll viewport: how far it has scrolled, and its top edge in client coordinates.
 *
 * @typedef {{scrollTop: number, top: number}} TocScrollViewport
 */

/**
 * Whether the narrow toggle of *documentElement*'s table of contents shows in *viewport*:
 * the viewport has scrolled past the threshold, and the document is under its top edge.
 *
 * *documentElement* is the element the document is mounted in, for both tables of
 * contents, since that is the box a host collapses. A collapsed Overview panel's body
 * keeps its width and has no height, so it spans no part of the pane's top and the toggle
 * stays hidden, although the article clipped inside it keeps its full height.
 *
 * @param {Element} documentElement
 * @param {TocScrollViewport} viewport
 * @returns {boolean}
 */
export function tocToggleVisible(documentElement, viewport) {
  if (viewport.scrollTop <= TOC_TOGGLE_SCROLL_THRESHOLD_PX) {
    return false;
  }
  const rect = documentElement.getBoundingClientRect();
  return rect.top <= viewport.top && rect.bottom > viewport.top;
}

/**
 * KPress's table-of-contents configuration for *documentElement*: its toggle policy,
 * reading the pane KPress scrolls in, which the shell marks `[data-kpress-viewport]`.
 *
 * @param {Element} documentElement
 * @returns {{visible: (context: {scrollTop(): number}) => boolean}}
 */
export function kpressTocConfig(documentElement) {
  return {
    visible: (context) => {
      const pane = documentElement.closest("[data-kpress-viewport]");
      return tocToggleVisible(documentElement, {
        scrollTop: context.scrollTop(),
        top: pane ? pane.getBoundingClientRect().top : 0,
      });
    },
  };
}
