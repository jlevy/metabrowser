// In-page recorder and trusted-input driver for the transition-navigation/v1 scenario
// (the revision is SCENARIO_REVISION in transitions-stats.mjs).
//
// Measurement only: it drives the unmodified product over the Chrome DevTools Protocol
// with trusted input and observes it from inside the page. Every in-page time is on the
// page clock (input event timeStamp, rAF timestamps, performance.now), so CDP round-trip
// latency never enters a number. See README.md, "Transition Navigation Scenario".
//
// The pure functions below (request classes, cache disposition, frame accounting, region
// movement, list changes) are exported for tests/dom/transitions-instrument-behavior.mjs.
import { execFileSync, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { CHROME, Connection, sleep } from "./pr-cdp.mjs";

export { sleep };

// Named regions whose per-frame post-layout box is recorded. `track` names the box
// components that count toward a transition's movement figures; the others are still
// recorded per region. Add a region here and every later run records it.
//
// `group` keeps figures apart: the page group (the default) reports as `movement`, and
// every other group under `movementByGroup`, so adding a group never changes the page
// figure. A region with `identity` is the same region only while that attribute of the
// matched element keeps its value: a tree row re-created with the same `data-path` is the
// same row and its steps count, and a different path is a replacement, not a movement.
// A `scroller` region is measured in that scroll container's content coordinates, so
// scrolling it is not movement, as Layout Instability does not count scrolling either.
export const REGIONS = {
  navTabs: { selector: ".nav-tab-bar", track: ["x", "y", "w", "h"] },
  filterBar: { selector: "#nav-filter-bar", track: ["x", "y", "w", "h"] },
  treeContent: { selector: "#tree-content", track: ["x", "y", "w"] },
  previewPane: { selector: "#preview-pane", track: ["x", "y", "w", "h"] },
  fileHeader: {
    selector: "#preview-pane > .file-header, #preview-pane > .folder-header",
    track: ["x", "y", "w"],
  },
  viewTabs: { selector: "#preview-pane > .tab-bar", track: ["x", "y", "w"] },
  activeView: { selector: '#preview-pane > [data-active-view="true"]', track: ["x", "y", "w"] },
  commitSummary: {
    selector: "#preview-pane .git-commit-view > .git-commit-summary",
    track: ["x", "y", "w"],
  },
  prHeader: {
    selector: "#preview-pane > .pull-request-host > .github-pull-header",
    track: ["x", "y", "w"],
  },
  prTabs: { selector: "#preview-pane > .pull-request-host .tab-bar", track: ["x", "y", "w"] },
  // Changes is full width and Conversation a reading column, so only its top counts.
  prBody: {
    selector: "#preview-pane > .pull-request-host > .github-pull-body",
    track: ["y"],
  },
  // The selected tree row, and the corpus's root folder below `src`, which every reveal
  // or expansion inside `src` pushes down.
  treeSelected: {
    selector: "#tab-files .tree-item.selected",
    track: ["y"],
    group: "tree",
    identity: "data-path",
    scroller: "#tree-content",
  },
  treeRowTests: {
    selector: '#tab-files .tree-item.tree-folder[data-path="tests"]',
    track: ["y"],
    group: "tree",
    identity: "data-path",
    scroller: "#tree-content",
  },
  paletteDialog: {
    selector: ".search-palette-overlay:not([hidden]) .search-palette-dialog",
    track: ["x", "y", "w"],
    group: "palette",
  },
  paletteResults: {
    selector: ".search-palette-overlay:not([hidden]) .search-palette-results",
    track: ["x", "y", "w"],
    group: "palette",
  },
  paletteSelected: {
    selector: '.search-palette-overlay:not([hidden]) [role="option"][aria-selected="true"]',
    track: ["x", "y"],
    group: "palette",
  },
};

/**
 * The recorder, evaluated at document start in every page. Serialized with
 * Function.prototype.toString, so it must not close over anything in this module.
 *
 * Every frame is read once, after that frame's own style and layout and before it
 * paints: the frame's `requestAnimationFrame` callback creates a ResizeObserver on the
 * document element, and a new observation is delivered in the same frame's rendering
 * steps, after layout, and after every ResizeObserver the page created earlier (they are
 * delivered in creation order). The reads therefore force no layout, and what they see is
 * what that frame paints unless a later resize-observation round changes it, which the
 * page's own ResizeObservers only do for content deeper than the document element.
 * @param {{ regions: Record<string, { selector: string }> }} config
 */
function recorderMain(config) {
  if (window.__tr) {
    return;
  }
  const PLACEHOLDER = ".loading, .mb-delayed-loading";
  const EMPTY = ".preview-empty, [data-preview-empty]";
  const NativeResizeObserver = window.ResizeObserver;
  const R = {
    frames: [],
    regionLog: [],
    lastBox: {},
    muts: [],
    navMuts: [],
    shifts: [],
    longtasks: [],
    loafs: [],
    events: [],
    inputs: [],
    alerts: [],
    hiddenFrames: 0,
    visibilityChanges: 0,
    readyFn: null,
    readyAt: null,
    readyRead: null,
    readyNext: null,
    readyBeforeInput: null,
    readyAtArm: false,
    startEvents: null,
    inputAt: null,
    armedAt: 0,
    frameCount: 0,
    pending: null,
    regions: config.regions,
    observers: {},
    listSpec: null,
    listLog: [],
    lastList: null,
    milestoneFns: null,
    milestones: {},
  };
  window.__tr = R;
  const images = new WeakMap();

  const nodeName = (n) => {
    if (!n) {
      return "?";
    }
    if (n.nodeType !== 1) {
      return "#text";
    }
    const cls =
      typeof n.className === "string" && n.className.trim()
        ? `.${n.className.trim().split(/\s+/).slice(0, 2).join(".")}`
        : "";
    return n.tagName.toLowerCase() + (n.id ? `#${n.id}` : "") + cls;
  };
  const observe = (type, fn, options) => {
    try {
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) {
          fn(e);
        }
      }).observe({ type, buffered: true, ...options });
      R.observers[type] = true;
    } catch (_error) {
      R.observers[type] = false;
    }
  };
  observe("layout-shift", (e) => {
    R.shifts.push({
      t: e.startTime,
      v: e.value,
      input: e.hadRecentInput,
      src: (e.sources || []).slice(0, 5).map((x) => ({
        n: nodeName(x.node),
        dx: Math.round(x.currentRect.x - x.previousRect.x),
        dy: Math.round(x.currentRect.y - x.previousRect.y),
        dw: Math.round(x.currentRect.width - x.previousRect.width),
        dh: Math.round(x.currentRect.height - x.previousRect.height),
      })),
    });
  });
  observe("longtask", (e) => {
    R.longtasks.push([e.startTime, e.duration]);
  });
  observe("long-animation-frame", (e) => {
    R.loafs.push([e.startTime, e.duration, e.blockingDuration || 0, e.renderStart || 0]);
  });
  observe(
    "event",
    (e) => {
      if (e.interactionId) {
        R.events.push([e.startTime, e.duration, e.name]);
      }
    },
    { durationThreshold: 16 },
  );
  // `pointerover` is kept for a hover-click's realized dwell (revision 6), with a fourth
  // field, 1 when its target is inside the element the hover-click armed (`hoverTarget`).
  for (const type of ["pointerover", "pointerdown", "mousedown", "click", "keydown", "popstate"]) {
    window.addEventListener(
      type,
      (e) => {
        const onTarget =
          type === "pointerover" && R.hoverTarget && e.target?.closest?.(R.hoverTarget) ? 1 : 0;
        R.inputs.push([type, e.timeStamp, e.isTrusted, onTarget]);
        if (R.inputAt === null && R.startEvents?.includes(type)) {
          R.inputAt = e.timeStamp;
        }
      },
      true,
    );
  }
  document.addEventListener("visibilitychange", () => {
    R.visibilityChanges += 1;
  });

  // Rendered at all: in layout, and not hidden by display, visibility, content-visibility,
  // or zero opacity on the element or an ancestor.
  // An element with `display: contents` has no box of its own, so its nearest ancestor
  // with one answers for it.
  const rendered = (el) => {
    let e = el;
    while (e && getComputedStyle(e).display === "contents") {
      e = e.parentElement;
    }
    if (!e) {
      return false;
    }
    return typeof e.checkVisibility === "function"
      ? e.checkVisibility({ opacityProperty: true, visibilityProperty: true })
      : e.getClientRects().length > 0;
  };
  // An element that clips its descendants to its box: overflow other than visible, or
  // paint containment (`contain: paint`, `content`, or `strict`; revision 6).
  const clips = (cs) =>
    cs.overflowX !== "visible" ||
    cs.overflowY !== "visible" ||
    /paint|content|strict/.test(cs.contain);
  // A viewport rectangle that survives the viewport and every clipping ancestor of `from`
  // (a collapsed tree group is height 0 with overflow hidden), with no ancestor at zero
  // opacity or display none in between (the inert preview stage).
  const clipped = (from, r) => {
    if (r.width === 0 || r.height === 0) {
      return false;
    }
    let left = Math.max(r.left, 0);
    let top = Math.max(r.top, 0);
    let right = Math.min(r.right, innerWidth);
    let bottom = Math.min(r.bottom, innerHeight);
    for (let a = from; a && a !== document.documentElement; a = a.parentElement) {
      if (right <= left || bottom <= top) {
        return false;
      }
      const cs = getComputedStyle(a);
      if (cs.display === "none" || Number.parseFloat(cs.opacity) <= 0.01) {
        return false;
      }
      if (clips(cs)) {
        const ar = a.getBoundingClientRect();
        left = Math.max(left, ar.left);
        top = Math.max(top, ar.top);
        right = Math.min(right, ar.right);
        bottom = Math.min(bottom, ar.bottom);
      }
    }
    return right > left && bottom > top;
  };
  // A placeholder in layout and on screen; its own opacity is read separately, because a
  // mounted placeholder inside its reveal delay is transparent by design.
  const isPlaceholderShown = (l) => clipped(l.parentElement, l.getBoundingClientRect());
  const isPlaceholderVisible = (l) => {
    const cs = getComputedStyle(l);
    return (
      cs.visibility !== "hidden" && cs.display !== "none" && Number.parseFloat(cs.opacity) > 0.01
    );
  };
  const placeholders = (root) => {
    if (!root) {
      return [];
    }
    const all = root.matches(PLACEHOLDER)
      ? [root, ...root.querySelectorAll(PLACEHOLDER)]
      : [...root.querySelectorAll(PLACEHOLDER)];
    return all.filter(isPlaceholderShown);
  };
  // An image counts once it has loaded and decoded: `decode()` is asked once per source,
  // and the image counts from the first frame after it resolves.
  const decoded = (img) => {
    if (!img.complete || img.naturalWidth === 0) {
      return false;
    }
    const src = img.currentSrc || img.src;
    const known = images.get(img);
    if (known && known.src === src) {
      return known.ok;
    }
    const entry = { src, ok: false };
    images.set(img, entry);
    img.decode().then(
      () => {
        entry.ok = true;
      },
      () => {
        entry.ok = false;
      },
    );
    return false;
  };
  const mediaShown = (el) => {
    if (!rendered(el)) {
      return false;
    }
    const r = el.getBoundingClientRect();
    if (!clipped(el.parentElement, r)) {
      return false;
    }
    const tag = el.localName;
    if (tag === "img") {
      return decoded(el);
    }
    if (tag === "video") {
      return el.readyState >= 2;
    }
    if (tag === "svg") {
      return r.width >= 64 && r.height >= 64;
    }
    // A canvas or an iframe is counted when it is laid out at a useful size; its pixels
    // are not read.
    return r.width >= 16 && r.height >= 16;
  };
  const range = document.createRange();
  // A text node's own boxes, one of them on screen; its parent is already known rendered.
  // Only the slice's non-blank parts are measured: each run of lines that holds a non-space
  // character, trimmed to its first and last one, so a stretch of blank lines on screen
  // after text that is not is not content (revision 6).
  // At most TEXT_RUNS runs of a slice are measured, each with one range. A run is at least
  // a line of text and the blank line after it, so 32 runs are at least 64 lines, more than
  // the 900 px viewport holds at a 14 px line height: a slice whose first 32 runs are not on
  // screen has its screen after them. Such a slice is not measured further (`R.textCapped`),
  // and the walk sends the search on to the hit test, which measures from the line the
  // caret lands on. The cap has not been timed on its own; transitions-search-cost.mjs
  // times whole calls.
  const TEXT_RUNS = 32;
  const textRuns = (text, start, end) => {
    const runs = [];
    let a = -1;
    let b = -1;
    for (let i = start; i < end; i++) {
      const ch = text.charCodeAt(i);
      if (ch === 10) {
        if (a >= 0) {
          // A line break closes the run when the next line is blank.
          let j = i + 1;
          while (j < end && text.charCodeAt(j) !== 10 && /\s/.test(text[j])) {
            j += 1;
          }
          if (j >= end || text.charCodeAt(j) === 10) {
            runs.push([a, b + 1]);
            a = -1;
            if (runs.length === TEXT_RUNS) {
              runs.capped = HAS_TEXT.test(text.slice(j, end));
              return runs;
            }
          }
        }
      } else if (!/\s/.test(text[i])) {
        if (a < 0) {
          a = i;
        }
        b = i;
      }
    }
    if (a >= 0) {
      runs.push([a, b + 1]);
    }
    return runs;
  };
  // `R.lastSearch.chars` counts the characters a search measured, for the tests.
  const sliceShown = (node, parent, start, end) => {
    const runs = textRuns(node.nodeValue, start, end);
    for (const [a, b] of runs) {
      R.searchChars += b - a;
      range.setStart(node, a);
      range.setEnd(node, b);
      for (const r of range.getClientRects()) {
        if (r.width > 0 && r.height > 0 && clipped(parent, r)) {
          return true;
        }
      }
    }
    if (runs.capped) {
      R.textCapped = true;
    }
    return false;
  };
  // A long text node, such as a plain source view's single node of thousands of lines, is
  // not measured whole: its boxes cost in proportion to its lines (3 ms for the corpus's
  // app.js line-number gutter of 41,000 characters in one node, in every frame of that
  // view), and so does any range inside it. Revision 6 measures LONG_TEXT characters of a
  // node: from its start in the walk, and from the start of the line the caret landed on
  // (`near`) in the hit test. A long node whose start is not shown sends the walk's search
  // on to the hit test.
  const LONG_TEXT = 2000;
  const isLong = (node) => node.nodeValue.length > LONG_TEXT;
  const textBoxShown = (node, parent, near = null) => {
    const len = node.nodeValue.length;
    const from = near === null ? 0 : node.nodeValue.lastIndexOf("\n", near - 1) + 1;
    return sliceShown(node, parent, from, Math.min(len, from + LONG_TEXT));
  };
  const textShown = (node, near = null) => {
    const parent = node.parentElement;
    return !!parent && rendered(parent) && textBoxShown(node, parent, near);
  };
  // Visible, laid-out content: text on screen outside a placeholder, prompt, or
  // screen-reader-only label, or media that has loaded. A root that is, or is inside, a
  // placeholder, prompt, or label has none.
  //
  // The search walks the root's subtree in document order and stops at the first hit. It
  // passes over, without entering, the subtree of a placeholder, a prompt, or a label; of
  // an element with display none, content-visibility hidden, or zero opacity, none of whose
  // descendants can show; and of an element whose box is empty and clips its overflow (a
  // collapsed block). Revision 6: a box-less element (an inline whose only child is
  // positioned) and a zero-size one that does not clip (a windowed list's anchor) are
  // entered, so their descendants are tested by their own boxes. An element wholly outside
  // the viewport is passed over unless its scrollable overflow, which holds the content
  // and the positioned descendants laid out outside its box, reaches the viewport.
  // Text under a hidden parent (visibility hidden, zero opacity) is not measured.
  //
  // Revision 6 bounds the walk by the nodes it visits, entered or not (SEARCH_VISITS), and
  // by the text nodes whose boxes it measures (SEARCH_TEXTS), so a long document of short
  // lines scrolled to its end costs the search what its top does. The bound is the
  // search's alone: the rest of a frame's read (its state's prompt and placeholder queries,
  // the regions' selectors, the alert query) still traverses the view, and a text node
  // costs up to LONG_TEXT characters, so neither a read nor a search over long text nodes
  // costs what a short view does (README, **How content is found**). When the walk reaches
  // a bound, or passed over an element on its own box and found nothing, a hit test of
  // points across the area where the root can paint looks at what is on screen there,
  // whatever its ancestors' boxes (`hitSearch`). Each frame's read records its own cost
  // (README, "Transition Navigation Scenario").
  // The line-number gutter of a source view is not the file's content, so a view whose
  // gutter is painted and whose code is not shows none of the file.
  const NOT_CONTENT = `${PLACEHOLDER}, .sr-only, .visually-hidden, .source-line-numbers, ${EMPTY}`;
  const MEDIA_TAGS = new Set(["img", "canvas", "iframe", "video", "svg"]);
  // The bounds were set from the cost of a call on synthetic documents of 2,000 to 40,000
  // lines in headless Chrome, measured with transitions-search-cost.mjs beside this file:
  // README, "Transition Navigation Scenario", **How content is found**.
  const SEARCH_VISITS = 1500;
  const SEARCH_TEXTS = 400;
  const HIT_POINTS = 60;
  // The hit test's bound is counted in work, so the same page gives the same answer on a
  // busy machine as on a quiet one. Each point is charged what a hit test passes on its
  // way to it: the child nodes of every element from the one the point lands on up to the
  // root, and one per HIT_CHARS_PER_NODE characters of the text among that element's first
  // HIT_CHILDREN children. No point starts once a call's charge reaches HIT_WORK; the first
  // always runs. In headless Chrome at a load average of about 20, a point over the blank
  // space past a flat list of 40,000 lines (charged 40,002) took 1.2 ms for its
  // elementFromPoint and 0.2 ms for its caret lookup, and one in a <pre> of a single
  // 40,000-line text node of about 340,000 characters 1.2 and 0.3 ms. HIT_WORK stops
  // either after its second point, about 3 ms there, and a blank screen past 10,000 lines
  // after its eighth, and lets one past 40,000 lines in sections of 50 try all 60 points
  // (README, **How content is found**, where transitions-search-cost.mjs prints each
  // call's points and work). A call that stops here marks its frame's read
  // `searchTruncated`; its time is only reported, in the read's cost.
  const HIT_WORK = 80000;
  const HIT_CHARS_PER_NODE = 8;
  // Rows tried first, in px below the paint area's top and below the root's own top when
  // that is inside the area: where a view's content starts.
  const HIT_TOP_ROWS_PX = [8, 28];
  const HIT_COLUMNS = [0.02, 0.5, 0.25, 0.75];
  // An element a point lands on, and each ancestor up to the root, is tested by the text
  // among its first HIT_CHILDREN children (elements and blank text count toward the 32).
  // That covers more than a screen of one-line children; text past them is found through
  // the caret lookup at the point, which lands on the text nearest it. Each child holds up
  // to LONG_TEXT measured characters, so an ancestor can cost up to 64,000; the limit has
  // not been timed on its own.
  const HIT_CHILDREN = 32;
  const HAS_TEXT = /\S/;
  const outside = (r) =>
    r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth;
  // How the walk treats an element: 0 passes over its subtree, 1 enters it, and 2 passes
  // over it on its own box, which a descendant painted elsewhere (fixed, translated) can
  // escape, so the hit test looks again.
  // An element wholly outside the viewport is decided on its box and its scrollable
  // overflow alone, without reading its style, so passing over a long document's
  // off-screen lines costs what revision 5 did per line.
  const enter = (el) => {
    if (el.matches(NOT_CONTENT)) {
      return 0;
    }
    const r = el.getBoundingClientRect();
    const sized = r.width > 0 && r.height > 0;
    if (sized && outside(r)) {
      const w = Math.max(r.width, el.scrollWidth);
      const h = Math.max(r.height, el.scrollHeight);
      if (outside({ left: r.left, top: r.top, right: r.left + w, bottom: r.top + h })) {
        return 2;
      }
    }
    const cs = getComputedStyle(el);
    if (
      cs.display === "none" ||
      cs.contentVisibility === "hidden" ||
      Number.parseFloat(cs.opacity) <= 0.01
    ) {
      return 0;
    }
    if (sized) {
      return outside(r) && clips(cs) ? 2 : 1;
    }
    // No box, or an empty one: `display: contents`, an inline whose only child is
    // positioned, a windowed list's zero-height anchor. Its descendants are tested by
    // their own boxes, unless it clips them away (overflow or paint containment).
    return clips(cs) && el.getClientRects().length > 0 ? 0 : 1;
  };
  const walk = (root, s) => {
    let n = root.firstChild;
    while (n !== null) {
      if (s.visits >= SEARCH_VISITS || s.texts >= SEARCH_TEXTS) {
        s.bounded = true;
        return false;
      }
      s.visits += 1;
      let into = false;
      if (n.nodeType === 1) {
        const e = enter(n);
        if (e === 2) {
          s.pruned = true;
        }
        into = e === 1;
        if (into && MEDIA_TAGS.has(n.localName) && mediaShown(n)) {
          return true;
        }
      } else if (n.nodeType === 3 && HAS_TEXT.test(n.nodeValue)) {
        const parent = n.parentElement;
        if (parent && rendered(parent)) {
          s.texts += 1;
          R.textCapped = false;
          if (textBoxShown(n, parent)) {
            return true;
          }
          if (isLong(n) || R.textCapped) {
            s.pruned = true;
          }
        }
      }
      if (into && n.firstChild) {
        n = n.firstChild;
        continue;
      }
      while (n !== root && n.nextSibling === null) {
        n = n.parentNode;
      }
      if (n === root) {
        return false;
      }
      n = n.nextSibling;
    }
    return false;
  };
  // The area where a root's content can paint: the viewport, cut by the root and every
  // ancestor that clips its overflow.
  const paintArea = (root) => {
    let left = 0;
    let top = 0;
    let right = innerWidth;
    let bottom = innerHeight;
    for (let a = root; a && a !== document.documentElement; a = a.parentElement) {
      if (clips(getComputedStyle(a))) {
        const ar = a.getBoundingClientRect();
        left = Math.max(left, ar.left);
        top = Math.max(top, ar.top);
        right = Math.min(right, ar.right);
        bottom = Math.min(bottom, ar.bottom);
      }
      if (right - left < 1 || bottom - top < 1) {
        return null;
      }
    }
    return { left, top, right, bottom };
  };
  // Row positions across a paint area after the top rows, coarse to fine: the middle, then
  // the quarters, the eighths, and the sixteenths, each level from its outer rows inward
  // (the lowest, the highest, the next lowest, and so on), so that a level the point cap
  // cuts short still spans the area down to its bottom eighth.
  const HIT_ROWS = (() => {
    const rows = [];
    for (let d = 2; rows.length < HIT_POINTS / HIT_COLUMNS.length; d *= 2) {
      for (let lo = 1, hi = d - 1; lo <= hi; lo += 2, hi -= 2) {
        rows.push(hi / d);
        if (lo !== hi) {
          rows.push(lo / d);
        }
      }
    }
    return rows;
  })();
  // What a point costs the hit test, in HIT_WORK's units (above).
  const hitCharge = (top, root) => {
    let w = 1;
    for (let el = top; el && el !== root.parentElement; el = el.parentElement) {
      w += el.childNodes.length;
    }
    let k = 0;
    for (let c = top.firstChild; c !== null && k < HIT_CHILDREN; c = c.nextSibling) {
      k += 1;
      if (c.nodeType === 3) {
        w += Math.ceil(c.nodeValue.length / HIT_CHARS_PER_NODE);
      }
    }
    return w;
  };
  // What is on screen at up to HIT_POINTS points across the root's paint area, within
  // HIT_WORK: the top rows of the area and of the root first, then as many rows, coarse to
  // fine, as the points left fill, at HIT_COLUMNS across. A point whose topmost element is
  // outside the root (an overlay) does not show the root. Otherwise that element and its
  // ancestors up to the root, outside a placeholder, prompt, or label, are tested as media
  // and by the text among their first HIT_CHILDREN children. A hit test passes over
  // elements with `pointer-events: none`, and content smaller than the grid can fall
  // between its points. Each point costs a walk of the siblings it lands among, so a blank
  // screen over a long flat list costs the most (README).
  const hitSearch = (root, s) => {
    const area = paintArea(root);
    if (!area) {
      return false;
    }
    const seen = new Set();
    const width = area.right - area.left;
    const height = area.bottom - area.top;
    const rootTop = root.getBoundingClientRect().top;
    const firstRows = [
      ...HIT_TOP_ROWS_PX.map((px) => area.top + px),
      ...(rootTop > area.top + HIT_TOP_ROWS_PX[0] && rootTop < area.bottom
        ? HIT_TOP_ROWS_PX.map((px) => rootTop + px)
        : []),
    ];
    const fill = HIT_ROWS.slice(0, HIT_POINTS / HIT_COLUMNS.length - firstRows.length);
    const rows = [...firstRows, ...fill.map((f) => area.top + height * f)].filter(
      (y) => y < area.bottom,
    );
    for (const y of rows) {
      for (const f of HIT_COLUMNS) {
        if (s.points >= HIT_POINTS) {
          return false;
        }
        if (s.points > 0 && s.work >= HIT_WORK) {
          s.truncated = true;
          R.searchTruncated = true;
          return false;
        }
        s.points += 1;
        const x = area.left + Math.max(2, width * f);
        const top = document.elementFromPoint(x, y);
        if (!top || !root.contains(top)) {
          s.work += 1;
          continue;
        }
        s.work += hitCharge(top, root);
        // The first time a topmost element is met, the text the caret lands on at that
        // point: it sees text under `pointer-events: none` and the text nearest the point
        // in that element, so a lone line between rows is found.
        if (!seen.has(top)) {
          const caret = document.caretPositionFromPoint?.(x, y);
          const node = caret?.offsetNode;
          if (
            node?.nodeType === 3 &&
            root.contains(node) &&
            !node.parentElement?.closest(NOT_CONTENT) &&
            HAS_TEXT.test(node.nodeValue) &&
            textShown(node, caret.offset)
          ) {
            return true;
          }
        }
        for (let el = top; el && el !== root.parentElement; el = el.parentElement) {
          if (seen.has(el)) {
            continue;
          }
          seen.add(el);
          if (el.closest(NOT_CONTENT)) {
            continue;
          }
          if (MEDIA_TAGS.has(el.localName)) {
            if (mediaShown(el)) {
              return true;
            }
            continue;
          }
          let k = 0;
          for (let c = el.firstChild; c !== null && k < HIT_CHILDREN; c = c.nextSibling) {
            k += 1;
            if (c.nodeType === 3 && HAS_TEXT.test(c.nodeValue) && textShown(c)) {
              return true;
            }
          }
        }
      }
    }
    return false;
  };
  R.searchChars = 0;
  const search = (root) => {
    const s = {
      visits: 0,
      texts: 0,
      pruned: false,
      bounded: false,
      points: 0,
      work: 0,
      truncated: false,
      chars: 0,
    };
    R.lastSearch = s;
    const before = R.searchChars;
    try {
      return searchRoot(root, s);
    } finally {
      s.chars = R.searchChars - before;
    }
  };
  const searchRoot = (root, s) => {
    // A root hidden by its own content-visibility, whose descendants are skipped, has none
    // (checkVisibility answers only for the descendants).
    if (
      !root ||
      root.closest(NOT_CONTENT) ||
      !rendered(root) ||
      getComputedStyle(root).contentVisibility === "hidden"
    ) {
      return false;
    }
    if (walk(root, s)) {
      return true;
    }
    return (s.bounded || s.pruned) && hitSearch(root, s);
  };
  // Within one frame's read nothing can change the page, so a root asked about twice (by
  // the frame's state and by the ready predicate) is searched once.
  const hasUseful = (root) => {
    const cache = R.readCache;
    if (!cache || !root) {
      return search(root);
    }
    if (!cache.has(root)) {
      cache.set(root, search(root));
    }
    return cache.get(root);
  };
  R.hasUseful = hasUseful;
  R.hasPlaceholder = (root) => placeholders(root).length > 0;
  R.rendered = (el) => !!el && rendered(el);

  // What the reader can see in the preview pane this frame. Letters: U useful content,
  // E a prompt (`.preview-empty` or `[data-preview-empty]`), P a visible placeholder, p a
  // mounted placeholder still inside its reveal delay, b the pending modifier, N a visible
  // placeholder in the active nav panel. A frame with no letter among U and E showed
  // nothing at all; "H" is a preview pane that is not rendered.
  const state = () => {
    const pane = document.getElementById("preview-pane");
    if (!pane) {
      return "-";
    }
    if (!rendered(pane)) {
      return "H";
    }
    const active = pane.querySelector(':scope > [data-active-view="true"]');
    const roots = active
      ? [active]
      : [...pane.children].filter(
          (c) => !c.classList.contains("preview-file-stage") && !c.classList.contains("sr-only"),
        );
    let useful = false;
    let empty = false;
    let shown = 0;
    let visible = 0;
    for (const c of roots) {
      if (c.matches(EMPTY)) {
        if (rendered(c)) {
          empty = true;
        }
        continue;
      }
      if (!empty && [...c.querySelectorAll(EMPTY)].some(rendered)) {
        empty = true;
      }
      if (!useful && hasUseful(c)) {
        useful = true;
      }
      for (const l of placeholders(c)) {
        shown += 1;
        if (isPlaceholderVisible(l)) {
          visible += 1;
        }
      }
    }
    let nav = "";
    const panel = document.querySelector(
      '#tree-content > [data-tab-content]:not([style*="display: none"])',
    );
    if (panel && placeholders(panel).some(isPlaceholderVisible)) {
      nav = "N";
    }
    return (
      (useful ? "U" : "") +
      (empty ? "E" : "") +
      (shown ? (visible ? "P" : "p") : "") +
      (pane.classList.contains("preview-navigation-pending") ? "b" : "") +
      nav
    );
  };
  R.state = state;

  // Whether a box is on screen (`scroll` false), or could be brought there by scrolling
  // (`scroll` true): it survives every ancestor that clips it, each cut to its client box,
  // and then the viewport. With `scroll`, a scroll container takes the box on each axis
  // it scrolls when the box lies within all it can scroll to, and projects it onto its
  // client box there, so a tree row below the fold of `#tree-content` survives the
  // panes around it that clip without scrolling; the document is taken to its own
  // scrollable area the same way. An ancestor that clips to an empty area (a block
  // collapsed to height 0) hides the box, and so does a position nothing scrolls to (a
  // surface parked at left: -10000px). On each axis where the box has extent the overlap
  // must be positive, so a box that only touches an edge (parked at left: 100%) is
  // hidden. Revision 6.
  const reachable = (from, r, scroll) => {
    const span = [
      [r.left, r.right, r.width > 0],
      [r.top, r.bottom, r.height > 0],
    ];
    // Cut axis k to [lo, hi]; false when nothing of the box is left on it.
    const cut = (k, lo, hi) => {
      span[k][0] = Math.max(span[k][0], lo);
      span[k][1] = Math.min(span[k][1], hi);
      return span[k][2] ? span[k][1] > span[k][0] : span[k][1] >= span[k][0];
    };
    for (let a = from; a && a !== document.documentElement; a = a.parentElement) {
      const cs = getComputedStyle(a);
      if (!clips(cs)) {
        continue;
      }
      if (a.clientWidth === 0 || a.clientHeight === 0) {
        return false;
      }
      const ar = a.getBoundingClientRect();
      const axes = [
        [ar.left + a.clientLeft, a.clientWidth, a.scrollLeft, a.scrollWidth, cs.overflowX],
        [ar.top + a.clientTop, a.clientHeight, a.scrollTop, a.scrollHeight, cs.overflowY],
      ];
      for (const [k, [c0, size, offset, extent, overflow]] of axes.entries()) {
        if (scroll && /auto|scroll/.test(overflow)) {
          if (!cut(k, c0 - offset, c0 - offset + extent)) {
            return false;
          }
          span[k][0] = c0;
          span[k][1] = c0 + size;
        } else if (!cut(k, c0, c0 + size)) {
          return false;
        }
      }
    }
    if (!scroll) {
      return cut(0, 0, innerWidth) && cut(1, 0, innerHeight);
    }
    const page = document.scrollingElement ?? document.documentElement;
    return (
      cut(0, -scrollX, page.scrollWidth - scrollX) && cut(1, -scrollY, page.scrollHeight - scrollY)
    );
  };
  // A box is [x, y, w, h], and a region with `identity` also carries that attribute.
  // A region is the first rendered element its selector matches whose box is on screen,
  // or failing one, the first whose box could be scrolled there, so a surface kept
  // mounted but hidden ahead of the one on screen (by display, visibility, opacity,
  // content-visibility, a collapsed clipping ancestor, or a parked position) is not taken
  // for it, and a tree row below the fold is still the row (revision 6).
  // Among those a scroll could bring on screen, the element that was the region in the
  // previous read comes first while it still can, so a shown surface scrolled out of its
  // pane stays the region rather than a retained one parked further down the pane. It is
  // held weakly, so a surface the page removed is not kept alive for the memory reading.
  R.regionEls = {};
  const box = (spec, name) => {
    let el = null;
    let r = null;
    const candidates = [...document.querySelectorAll(spec.selector)]
      .map((c) => [c, c.getBoundingClientRect()])
      .filter(([c, cr]) => (cr.width > 0 || cr.height > 0) && rendered(c));
    const before = R.regionEls[name]?.deref();
    for (const scroll of [false, true]) {
      const hit =
        (scroll &&
          candidates.find(([c, cr]) => c === before && reachable(c.parentElement, cr, true))) ||
        candidates.find(([c, cr]) => reachable(c.parentElement, cr, scroll));
      if (hit) {
        [el, r] = hit;
        break;
      }
    }
    if (!el) {
      return null;
    }
    R.regionEls[name] = new WeakRef(el);
    let sx = 0;
    let sy = 0;
    if (spec.scroller) {
      const sc = document.querySelector(spec.scroller);
      sx = sc ? sc.scrollLeft : 0;
      sy = sc ? sc.scrollTop : 0;
    }
    const b = [
      Math.round(r.x + sx),
      Math.round(r.y + sy),
      Math.round(r.width),
      Math.round(r.height),
    ];
    if (spec.identity) {
      b.push(el.getAttribute(spec.identity));
    }
    return b;
  };
  const sameBox = (a, b) =>
    a === b || (a && b && a.length === b.length && a.every((v, i) => v === b[i]));
  R.snapshotRegions = () => {
    const out = {};
    for (const [name, spec] of Object.entries(R.regions)) {
      out[name] = box(spec, name);
    }
    R.lastBox = { ...out };
    return out;
  };
  // An entry is [frame time, region, box, 1 when that frame's read saw the input].
  const trackRegions = (t, seen) => {
    for (const [name, spec] of Object.entries(R.regions)) {
      const b = box(spec, name);
      if (!sameBox(b, R.lastBox[name])) {
        R.regionLog.push([t, name, b, seen ? 1 : 0]);
        R.lastBox[name] = b;
      }
    }
  };
  // An ordered list under watch (the palette's results): each row's key and the selected
  // index, logged when either changes.
  const trackList = (t) => {
    const spec = R.listSpec;
    if (!spec) {
      return;
    }
    const rows = [...document.querySelectorAll(spec.rows)].slice(0, 12);
    const keys = rows.map((r) =>
      (r.getAttribute("aria-label") || r.textContent || "").trim().slice(0, 80),
    );
    const selected = rows.findIndex((r) => r.getAttribute("aria-selected") === "true");
    const sig = `${selected}|${keys.join("\u0001")}`;
    if (sig !== R.lastList) {
      R.lastList = sig;
      R.listLog.push([t, keys, selected]);
    }
  };
  // A milestone is [frame time, post-layout read time, next frame time].
  const trackMilestones = (t, readNow) => {
    if (!R.milestoneFns) {
      return;
    }
    for (const [name, fn] of Object.entries(R.milestoneFns)) {
      if (R.milestones[name]) {
        continue;
      }
      let ok = false;
      try {
        ok = Boolean(fn());
      } catch (_error) {
        ok = false;
      }
      if (ok) {
        R.milestones[name] = [t, readNow, null];
      }
    }
  };
  const ALERTS =
    '#preview-pane [role="alert"], #preview-pane .preview-error, #tree-content [role="alert"]';
  const checkAlerts = (t) => {
    for (const el of document.querySelectorAll(ALERTS)) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) {
        continue;
      }
      if (R.alerts.length < 8) {
        R.alerts.push([t, nodeName(el), (el.textContent || "").trim().slice(0, 160)]);
      }
    }
  };

  const round1 = (v) => Math.round(v * 10) / 10;
  // One frame's post-layout read. A frame is a candidate for readiness only when the input
  // event that starts the transition reached the page before the read, so its state
  // includes whatever the input's handlers did, and the read itself is after the input;
  // a predicate that holds in an earlier frame is recorded as `readyBeforeInput`.
  // A frame is logged as [begin time, state, read time, the read's own cost in ms, 1 when
  // the read saw the input, 1 when a content search in it stopped at its hit-test bound]:
  // the fifth places it in its transition's window or before it, whatever Chrome stamped
  // its begin time (`inWindow`, revision 6).
  const read = (frame) => {
    R.readCache = new Map();
    R.searchTruncated = false;
    try {
      readFrame(frame);
    } finally {
      R.readCache = null;
    }
  };
  const readFrame = (frame) => {
    frame.readNow = performance.now();
    const inputSeen = R.inputAt !== null;
    let code;
    try {
      code = state();
    } catch (_error) {
      code = "X";
    }
    const entry = [frame.t, code, round1(frame.readNow), null, inputSeen ? 1 : 0, 0];
    R.frames.push(entry);
    trackRegions(frame.t, inputSeen);
    checkAlerts(frame.t);
    trackList(frame.t);
    if (inputSeen) {
      trackMilestones(frame.t, frame.readNow);
    }
    if (R.readyFn && R.readyAt === null) {
      let ok = false;
      try {
        ok = Boolean(R.readyFn());
      } catch (_error) {
        ok = false;
      }
      if (ok && !inputSeen) {
        R.readyBeforeInput ??= frame.t;
      } else if (ok) {
        R.readyAt = frame.t;
        R.readyRead = frame.readNow;
      }
    }
    // The page is not cross-origin isolated, so its clock resolves 0.1 ms.
    entry[3] = round1(performance.now() - frame.readNow);
    entry[5] = R.searchTruncated ? 1 : 0;
  };
  const tick = (t) => {
    R.frameCount += 1;
    // A frame whose observation never arrived is recorded without a state. Its read would
    // have come before this tick: when the input has still not reached the page, that read
    // was before the input (0), and when the read before it saw the input, it was after it
    // (1); otherwise it is placed by its begin time (`inWindow`).
    const missed = R.pending;
    if (missed && missed.readNow === null) {
      missed.observer?.disconnect();
      const before = R.frames[R.frames.length - 1];
      const seen = R.inputAt === null ? 0 : before?.[4] === 1 ? 1 : null;
      R.frames.push([missed.t, null, null, null, seen, 0]);
    }
    if (R.readyAt !== null && R.readyNext === null && t > R.readyAt) {
      R.readyNext = t;
    }
    for (const m of Object.values(R.milestones)) {
      if (m[2] === null && m[0] < t) {
        m[2] = t;
      }
    }
    if (document.visibilityState !== "visible") {
      R.hiddenFrames += 1;
    }
    const frame = { t, readNow: null, observer: null };
    R.pending = frame;
    const root = document.documentElement;
    if (root && NativeResizeObserver) {
      const ro = new NativeResizeObserver(() => {
        ro.disconnect();
        if (frame.readNow === null) {
          read(frame);
        }
      });
      frame.observer = ro;
      ro.observe(root);
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  // DOM work in the preview and in the navigation panels, for the settle times.
  const attach = () => {
    const pane = document.getElementById("preview-pane");
    if (pane) {
      new MutationObserver((records) => {
        let removed = 0;
        let added = 0;
        for (const m of records) {
          if (m.target === pane && m.type === "childList") {
            removed += m.removedNodes.length;
            added += m.addedNodes.length;
          }
        }
        R.muts.push([performance.now(), records.length, removed, added]);
      }).observe(pane, { childList: true, subtree: true, attributes: true, characterData: true });
    }
    const nav = document.getElementById("tree-content");
    if (nav) {
      new MutationObserver((records) => {
        if (R.navMuts.length < 4000) {
          R.navMuts.push([performance.now(), records.length]);
        }
      }).observe(nav, { childList: true, subtree: true, attributes: true, characterData: true });
    }
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attach);
  } else {
    attach();
  }
}

/** Source evaluated at document start: the region map, then the recorder. */
export function recorderSource(regions = REGIONS) {
  const config = { regions: Object.fromEntries(Object.entries(regions)) };
  return `(${recorderMain.toString()})(${JSON.stringify(config)});`;
}

// Request classes. `background` is the Pulls catalog work that runs on its own timers
// after every page load whatever the reader does: the core-preparation and catalog-refresh
// POSTs (the palette posts the same refresh, flagged background, when a query needs pull
// requests), and the warm walk over All, which reads `pulls?state=all` eight rows at a
// time (`CORE_BATCH_SIZE` in pulls-panel.js). The visible list's own window reads, with
// `after` and its own limit, are `data`. The rule is by URL shape, so a change to
// `CORE_BATCH_SIZE` moves the walk into `data`; the Requests table shows it at once.
export function requestClass(url, type) {
  let u;
  try {
    u = new URL(url);
  } catch (_error) {
    return "other";
  }
  if (u.protocol === "data:" || u.protocol === "blob:") {
    return "inline";
  }
  const p = u.pathname;
  if (type === "Document") {
    return "document";
  }
  if (p.startsWith("/api/kpress/") || p.startsWith("/kpress-static/")) {
    return "kpress";
  }
  if (
    p === "/api/plugin/github/pull-cores-prepare" ||
    p === "/api/plugin/github/pulls-refresh" ||
    (p === "/api/plugin/github/pulls" &&
      u.searchParams.get("state") === "all" &&
      u.searchParams.get("limit") === "8")
  ) {
    return "background";
  }
  if (p === "/api/events") {
    return "stream";
  }
  if (p.startsWith("/api/")) {
    return "data";
  }
  if (p.startsWith("/plugin-static/")) {
    return "plugin";
  }
  if (p.startsWith("/static/")) {
    return "static";
  }
  return "other";
}

// Route families for cache disposition: what kind of thing a request fetched.
export function routeFamily(url, type) {
  let u;
  try {
    u = new URL(url);
  } catch (_error) {
    return "other";
  }
  if (u.protocol === "data:" || u.protocol === "blob:") {
    return "inline";
  }
  if (type === "Document") {
    return "document";
  }
  const p = u.pathname;
  if (p.startsWith("/static/")) {
    return "static";
  }
  if (p.startsWith("/plugin-static/")) {
    return "plugin_static";
  }
  if (p.startsWith("/kpress-static/")) {
    return "kpress_static";
  }
  if (p === "/api/events") {
    return "stream";
  }
  if (p.startsWith("/api/")) {
    return "data";
  }
  return "other";
}

/**
 * How a request was satisfied, from its DevTools events:
 * - `cache` when the memory cache answered (`requestServedFromCache`) or the disk cache
 *   did with no network exchange (`fromDiskCache` and no raw network status);
 * - `revalidated` for a 304 on the wire. `responseReceivedExtraInfo` carries the raw
 *   status, and it is the only place a 304 the browser answered from its own cache shows:
 *   `responseReceived` reports that exchange as the cached 200;
 * - `network` for any other response, `failed`, or `pending` when no response arrived.
 */
export function disposition(entry) {
  if (entry.cache === "memory") {
    return "cache";
  }
  if (entry.netStatus === 304 || entry.status === 304) {
    return "revalidated";
  }
  if (entry.cache === "disk" && entry.netStatus === null) {
    return "cache";
  }
  if (entry.failed) {
    return "failed";
  }
  if (entry.status !== null || entry.netStatus !== null) {
    return "network";
  }
  return "pending";
}

const postBytesOf = (request) => {
  if (Array.isArray(request.postDataEntries)) {
    return request.postDataEntries.reduce(
      (a, e) => a + (e.bytes ? Buffer.from(e.bytes, "base64").length : 0),
      0,
    );
  }
  if (typeof request.postData === "string") {
    return Buffer.byteLength(request.postData, "utf8");
  }
  return request.hasPostData ? null : 0;
};

// The start of a POST body as text, enough to read a small JSON request's fields.
const postTextOf = (request) => {
  if (Array.isArray(request.postDataEntries)) {
    return Buffer.concat(
      request.postDataEntries.map((e) =>
        e.bytes ? Buffer.from(e.bytes, "base64") : Buffer.alloc(0),
      ),
    )
      .toString("utf8")
      .slice(0, 1024);
  }
  return typeof request.postData === "string" ? request.postData.slice(0, 1024) : null;
};

export const PULL_REFRESH_ROUTE = "/api/plugin/github/pull-refresh";

/**
 * Reads of the selected subject in one transition's requests, per route pattern. A cold
 * selection issues each route once, so a further read is a duplicate, except a read of a
 * pull request that follows the page's own `pull-refresh` POST for that number in the
 * same window: the page polls the record until a refresh it asked for settles, and those
 * settlement reads are counted apart. A refresh whose body could not be read is taken to
 * be for the subject, since only the subject's page posts one.
 */
export function subjectReads(requests, patterns, pullNumber = null) {
  let total = 0;
  let duplicates = 0;
  let settlement = 0;
  for (const pattern of patterns) {
    const re = new RegExp(pattern);
    let refreshed = false;
    let reads = 0;
    for (const r of requests) {
      const p = r.url.replace(/^https?:\/\/[^/]+/, "");
      if (pullNumber !== null && r.method === "POST" && p.split("?")[0] === PULL_REFRESH_ROUTE) {
        let number = null;
        try {
          number = JSON.parse(r.postText ?? "null")?.number ?? null;
        } catch (_error) {
          number = null;
        }
        if (number === null || Number(number) === Number(pullNumber)) {
          refreshed = true;
        }
      } else if (re.test(p)) {
        total += 1;
        if (refreshed) {
          settlement += 1;
        } else {
          reads += 1;
        }
      }
    }
    duplicates += Math.max(0, reads - 1);
  }
  return { total, duplicates, settlement };
}

/** The request log one browser keeps: entries in order, and an index by session and id. */
export function networkLog() {
  return { net: [], byId: new Map(), byRequest: new Map(), early: new Map() };
}

/**
 * Apply one DevTools Network event to a request log. The ExtraInfo events can arrive
 * before the event they belong to, so their fields wait in `early` until it does. They
 * can also arrive on another session: for a request a dedicated worker makes, Chrome
 * sends `requestWillBeSent` and `responseReceived` on the worker's session and both
 * ExtraInfo events on the page's, with the worker request's ID. So an ExtraInfo event is
 * matched to its request by session and ID, else by the request ID alone, and waits under
 * the ID alone, in either order of arrival.
 */
export function applyNetworkEvent(log, method, params, kind, sid) {
  const key = `${sid}:${params.requestId}`;
  const merge = (entry, extra) => {
    if (extra.netStatus !== undefined) {
      entry.netStatus = extra.netStatus;
    }
    if (extra.conditional !== undefined) {
      entry.conditional = extra.conditional;
    }
  };
  const later = (fields) => {
    const entry = log.byId.get(key) ?? log.byRequest.get(params.requestId);
    if (entry) {
      merge(entry, fields);
    } else {
      const id = params.requestId;
      log.early.set(id, { ...(log.early.get(id) ?? {}), ...fields });
    }
  };
  if (method === "Network.requestWillBeSent") {
    const previous = log.byId.get(key);
    if (params.redirectResponse && previous) {
      previous.status = params.redirectResponse.status;
      previous.redirected = true;
    }
    const entry = {
      kind,
      sid,
      id: params.requestId,
      method: params.request.method,
      family: routeFamily(params.request.url, params.type),
      postBytes: params.request.method === "POST" ? postBytesOf(params.request) : 0,
      postText: params.request.method === "POST" ? postTextOf(params.request) : null,
      encoded: null,
      url: params.request.url,
      type: params.type,
      cls: requestClass(params.request.url, params.type),
      wall: Math.round((params.wallTime ?? 0) * 1000),
      status: null,
      netStatus: null,
      conditional: false,
      cache: null,
      failed: null,
    };
    if (params.redirectResponse) {
      entry.redirect = true;
    }
    const early = log.early.get(params.requestId);
    if (early) {
      merge(entry, early);
      log.early.delete(params.requestId);
    }
    log.net.push(entry);
    log.byId.set(key, entry);
    log.byRequest.set(params.requestId, entry);
  } else if (method === "Network.requestWillBeSentExtraInfo") {
    const headers = Object.keys(params.headers ?? {}).map((h) => h.toLowerCase());
    later({
      conditional: headers.includes("if-none-match") || headers.includes("if-modified-since"),
    });
  } else if (method === "Network.responseReceivedExtraInfo") {
    later({ netStatus: params.statusCode ?? null });
  } else if (method === "Network.responseReceived") {
    const entry = log.byId.get(key);
    if (entry) {
      entry.status = params.response.status;
      if (params.response.fromDiskCache) {
        entry.cache = "disk";
      }
    }
  } else if (method === "Network.requestServedFromCache") {
    const entry = log.byId.get(key);
    if (entry) {
      entry.cache = "memory";
    }
  } else if (method === "Network.loadingFinished") {
    const entry = log.byId.get(key);
    if (entry) {
      entry.encoded = params.encodedDataLength;
    }
  } else if (method === "Network.loadingFailed") {
    const entry = log.byId.get(key);
    if (entry) {
      entry.failed = params.canceled ? "canceled" : params.errorText || "failed";
    }
  }
}

const KEYS = {
  ArrowDown: { key: "ArrowDown", code: "ArrowDown", windowsVirtualKeyCode: 40 },
  ArrowUp: { key: "ArrowUp", code: "ArrowUp", windowsVirtualKeyCode: 38 },
  ArrowRight: { key: "ArrowRight", code: "ArrowRight", windowsVirtualKeyCode: 39 },
  ArrowLeft: { key: "ArrowLeft", code: "ArrowLeft", windowsVirtualKeyCode: 37 },
  Enter: { key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, text: "\r" },
  Escape: { key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 },
};

/** A measured transition that could not be made to mean anything. */
export class Refusal extends Error {
  constructor(guard, detail) {
    super(`${guard}: ${detail}`);
    this.guard = guard;
    this.detail = detail;
  }
}

/** Kill a Chrome and every helper still holding its profile, then remove the profile. */
async function stopChrome(chrome, conn, profileDir) {
  try {
    if (conn) {
      await Promise.race([conn.send("Browser.close", {}, undefined, 3000), sleep(3000)]);
    }
  } catch (_error) {
    // The browser may already be gone.
  }
  try {
    conn?.close();
  } catch (_error) {
    // Already closed.
  }
  if (chrome.pid !== undefined) {
    for (let i = 0; i < 30 && chrome.exitCode === null && chrome.signalCode === null; i++) {
      await sleep(100);
    }
    if (chrome.exitCode === null && chrome.signalCode === null) {
      chrome.kill("SIGKILL");
    }
  }
  try {
    const out = execFileSync("ps", ["-A", "-o", "pid=,args="], { encoding: "utf8", timeout: 5000 });
    for (const line of out.split("\n")) {
      if (line.includes(`--user-data-dir=${profileDir}`)) {
        try {
          process.kill(Number(line.trim().split(/\s+/)[0]), "SIGKILL");
        } catch (_error) {
          // Exited meanwhile.
        }
      }
    }
  } catch (_error) {
    // No process table; the main process was killed above.
  }
  fs.rmSync(profileDir, { recursive: true, force: true, maxRetries: 5 });
}

/**
 * One fresh Chrome profile with the recorder installed on every new document.
 * Network, exceptions, and console errors are collected from the page and from its
 * dedicated workers. `onSpawn` receives the Chrome process as soon as it exists, so a
 * caller's signal handler can kill it; a launch that fails after the spawn stops it here.
 * `endpointTimeoutMs` bounds the wait for Chrome to publish its DevTools endpoint.
 */
export async function launchBrowser({
  profileDir,
  headed = false,
  width = 1440,
  height = 900,
  extraArgs = [],
  onSpawn = null,
  endpointTimeoutMs = 30000,
}) {
  fs.rmSync(profileDir, { recursive: true, force: true });
  fs.mkdirSync(profileDir, { recursive: true });
  const args = [
    ...(headed ? [] : ["--headless=new"]),
    "--remote-debugging-port=0",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-networking",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-features=Translate,MediaRouter",
    "--force-device-scale-factor=1",
    `--window-size=${width},${height + (headed ? 140 : 0)}`,
    `--user-data-dir=${profileDir}`,
    ...extraArgs,
    "about:blank",
  ];
  const chrome = spawn(CHROME, args, { stdio: ["ignore", "ignore", "pipe"] });
  let launchError = null;
  chrome.once("error", (error) => {
    launchError = error;
  });
  chrome.stderr.on("data", () => {});
  onSpawn?.(chrome);
  let conn = null;
  try {
    let ws = null;
    const portFile = path.join(profileDir, "DevToolsActivePort");
    const deadline = Date.now() + endpointTimeoutMs;
    while (!ws && Date.now() < deadline) {
      if (launchError !== null) {
        throw new Error(`Chrome could not start (${CHROME})`, { cause: launchError });
      }
      if (chrome.exitCode !== null || chrome.signalCode !== null) {
        throw new Error(`Chrome exited during launch (${chrome.exitCode ?? chrome.signalCode})`);
      }
      if (fs.existsSync(portFile)) {
        const [port, wsPath] = fs.readFileSync(portFile, "utf8").trim().split("\n");
        if (port && wsPath) {
          ws = `ws://127.0.0.1:${port}${wsPath}`;
        }
      }
      if (!ws) {
        await sleep(100);
      }
    }
    if (!ws) {
      throw new Error(
        `Chrome did not publish a DevTools endpoint within ${endpointTimeoutMs / 1000} s`,
      );
    }
    conn = new Connection(ws);
    await conn.open();
    const version = await conn.send("Browser.getVersion", {}, undefined, 10000);
    const page = await conn.newPage("about:blank");
    const log = networkLog();
    const exceptions = [];
    const consoleErrors = [];
    const workers = new Map();
    const kindOf = (sid) => (sid === page.sessionId ? "page" : workers.has(sid) ? "worker" : null);
    const connection = conn;
    conn.listeners.add((method, params, sid) => {
      if (method === "Target.detachedFromTarget") {
        workers.delete(params.sessionId);
        return;
      }
      if (method === "Target.attachedToTarget") {
        const child = connection.adopt(params.sessionId, params.targetInfo.targetId);
        workers.set(params.sessionId, params.targetInfo.type);
        void (async () => {
          try {
            await child.send("Network.enable");
            await child.send("Runtime.enable");
          } catch (_error) {
            // A worker that exits while attaching has nothing left to record.
          }
          try {
            await child.send("Runtime.runIfWaitingForDebugger");
          } catch (_error) {
            // Same: the target is already gone.
          }
        })();
        return;
      }
      const kind = kindOf(sid);
      if (kind === null) {
        return;
      }
      if (method.startsWith("Network.")) {
        applyNetworkEvent(log, method, params, kind, sid);
      } else if (method === "Runtime.exceptionThrown") {
        const d = params.exceptionDetails || {};
        exceptions.push({
          kind,
          wall: Date.now(),
          text: String(d.exception?.description || d.text || "exception").slice(0, 400),
          url: d.url || "",
          line: d.lineNumber,
        });
      } else if (method === "Runtime.consoleAPICalled" && params.type === "error") {
        consoleErrors.push({
          kind,
          wall: Date.now(),
          text: (params.args || [])
            .map((a) => a.value ?? a.description ?? "")
            .join(" ")
            .slice(0, 300),
        });
      }
    });
    await page.send("Page.enable");
    await page.send("Runtime.enable");
    await page.send("Network.enable");
    await page.send("Target.setAutoAttach", {
      autoAttach: true,
      waitForDebuggerOnStart: true,
      flatten: true,
    });
    await page.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await page.send("Page.addScriptToEvaluateOnNewDocument", { source: recorderSource() });
    let closed = false;
    const close = async () => {
      if (closed) {
        return;
      }
      closed = true;
      await stopChrome(chrome, connection, profileDir);
    };
    return {
      conn,
      page,
      close,
      chrome,
      version,
      net: log.net,
      exceptions,
      consoleErrors,
      workers,
      viewport: { width, height },
    };
  } catch (error) {
    await stopChrome(chrome, conn, profileDir);
    throw error;
  }
}

const round1 = (v) => (v === null || v === undefined ? null : Math.round(v * 10) / 10);
const round4 = (v) => Math.round(v * 10000) / 10000;

/** The frame interval: the 20th percentile of positive frame-to-frame steps. */
export function frameInterval(times) {
  const steps = [];
  for (let i = 1; i < times.length; i++) {
    const d = times[i] - times[i - 1];
    if (d > 0.5) {
      steps.push(d);
    }
  }
  if (steps.length < 4) {
    return 1000 / 60;
  }
  steps.sort((a, b) => a - b);
  return steps[Math.floor(steps.length * 0.2)];
}

/**
 * When a frame read at `readAt` reached the screen, on the frame clock: the first frame
 * boundary after its main-thread rendering ended. The frame's nominal begin time is
 * `frameAt` (its rAF timestamp, on the display's frame grid); its rendering ended at the
 * later of its post-layout read and the end of a Long Animation Frame entry that covers
 * that read (a frame over 50 ms, whose paint and commit the read cannot see). A task that
 * runs after the frame, however long, does not move it, and neither does the next frame's
 * rAF timestamp, which Chrome reports on the grid even when the main thread starts that
 * frame late.
 */
export function presentedAt(frameAt, readAt, loafs, interval) {
  let end = readAt ?? frameAt;
  for (const [start, duration, , renderStart] of loafs) {
    if (renderStart > 0 && renderStart <= end + 0.5 && start + duration >= end) {
      end = Math.max(end, start + duration);
    }
  }
  return frameAt + interval * Math.max(1, Math.ceil((end - frameAt) / interval - 1e-6));
}

/**
 * Whether a logged frame belongs to a transition's window, from its start: its read saw
 * the input (`seen`, revision 6), whatever its begin time. Chrome stamps frames on its
 * own clock, so the frame that draws an input can begin, by its stamp, a fraction of a
 * millisecond before the input's own time stamp, and a frame read before the input can
 * begin after it; placed by begin time, as revision 5 placed them, the first fell outside
 * the window and the second inside. An entry without the flag (a frame whose read never
 * came, logged while it could not be told which side of the input it fell) is placed by
 * its begin time.
 */
export const inWindow = (t, seen, origin) => seen === 1 || (seen == null && t >= origin);

/**
 * Frame accounting for one transition window, from the per-frame states.
 * `frames` are [frame time, state code or null, read time, read cost ms, seen, search
 * truncated]; a null code (a frame whose observation never arrived) shows what the
 * previous frame showed and is counted as uncredited. Every count covers the whole
 * window, from the input's own frame to its end, and is split at the ready frame;
 * `emptyState` is the destination's own prompt, declared by the journey, whose frames
 * are not blank. Each entry is placed in the window or before it on its own (`inWindow`),
 * as `regionMovement` places region boxes.
 */
export function accountFrames({
  frames,
  origin,
  windowEnd,
  readyAt,
  readyRead,
  readyNext,
  loafs = [],
  emptyState = false,
  initialCode = "",
}) {
  const before = frames.filter((f) => !inWindow(f[0], f[4], origin));
  const window = frames.filter((f) => inWindow(f[0], f[4], origin) && f[0] <= windowEnd);
  let last = initialCode;
  for (const f of before) {
    if (f[1] !== null) {
      last = f[1];
    }
  }
  const atOrigin = last;
  // Frames read after arm and before the input whose content search stopped at its
  // bound: the frames the ready-before-input guard read (revision 6).
  const truncatedBeforeInput = before.filter((f) => f[5] === 1).length;
  // A null code shows what the entry logged before it showed.
  const inside = new Set(window);
  const filled = [];
  last = initialCode;
  for (const f of frames) {
    if (inside.has(f)) {
      filled.push({ t: f[0], code: f[1] === null ? last : f[1], uncredited: f[1] === null });
    }
    if (f[1] !== null) {
      last = f[1];
    }
  }
  const interval = frameInterval(frames.map((f) => f[0]));
  const isBlank = (code) =>
    !code.includes("U") && !(emptyState && code.includes("E") && !code.includes("P"));
  const dur = (i) =>
    i + 1 < filled.length
      ? filled[i + 1].t - filled[i].t
      : Math.min(interval, windowEnd - filled[i].t);
  const tally = (pick) => {
    let before = 0;
    let after = 0;
    let ms = 0;
    filled.forEach((f, i) => {
      if (!pick(f)) {
        return;
      }
      if (readyAt === null || f.t <= readyAt) {
        before += 1;
      } else {
        after += 1;
      }
      ms += Math.max(0, dur(i));
    });
    return { before, after, total: before + after, ms: round1(ms) };
  };
  const blank = tally((f) => isBlank(f.code));
  // Blank frames that still show the prompt that was on screen at the input, until the
  // pane shows anything else: counted as blank, and reported apart, since the reader saw
  // the origin's prompt rather than an empty pane. Since revision 6 only the U and E
  // letters decide that, so a placeholder or the pending modifier appearing beside the
  // prompt does not end the run.
  let originPromptFrames = 0;
  const shows = (code) => (code.includes("U") ? "U" : "") + (code.includes("E") ? "E" : "");
  if (shows(atOrigin) === "E") {
    for (const f of filled) {
      if (shows(f.code) !== "E") {
        break;
      }
      if (isBlank(f.code)) {
        originPromptFrames += 1;
      }
    }
  }
  const placeholder = tally((f) => f.code.includes("P"));
  const nav = tally((f) => f.code.includes("N"));
  const uncredited = tally((f) => f.uncredited);
  const upto = readyAt === null ? filled : filled.filter((f) => f.t <= readyAt);
  const painted = readyAt === null ? null : presentedAt(readyAt, readyRead, loafs, interval);
  const rel = (t) => (t === null || t === undefined ? null : round1(t - origin));
  const states = [];
  for (const f of filled) {
    if (!states.length || states[states.length - 1][1] !== f.code) {
      states.push([rel(f.t), f.code]);
    }
  }
  const steps = window.map((f, i) => (i ? f[0] - window[i - 1][0] : null)).filter((x) => x);
  steps.sort((a, b) => a - b);
  // The recorder's own read in each frame of the window (revision 6), so a comparison can
  // show when the instrument cost one condition more than the other.
  const cost = (list) => list.map((f) => f[3]).filter((c) => typeof c === "number");
  const costs = cost(window);
  const costsToReady =
    readyAt === null ? [] : cost(window.filter((f) => f[0] <= readyAt && f[1] !== null));
  return {
    // The ready frame's post-layout read, which is after the input by construction.
    readyMs: rel(readyRead ?? readyAt),
    paintedReadyMs: rel(painted),
    nextFrameMs: rel(readyNext),
    framesToReady: upto.length,
    framesInWindow: filled.length,
    frameIntervalMs: round1(interval),
    medianFrameStepMs: steps.length ? round1(steps[Math.floor(steps.length / 2)]) : null,
    blankFrames: blank.total,
    blankFramesBeforeReady: blank.before,
    blankFramesAfterReady: blank.after,
    blankFramesOriginPrompt: originPromptFrames,
    blankMs: blank.ms,
    placeholderVisibleFrames: placeholder.total,
    placeholderVisibleFramesAfterReady: placeholder.after,
    placeholderVisibleMs: placeholder.ms,
    navPlaceholderVisibleFrames: nav.total,
    uncreditedFrames: uncredited.total,
    readCostMaxMs: costs.length ? round1(Math.max(...costs)) : null,
    // Frames whose content search stopped at its hit-test bound, where on-screen content
    // can have read as blank (revision 6): in the window, the part of them up to the ready
    // frame, where readiness can have been found late and the window's end with it, and
    // before the input.
    searchTruncatedFrames: window.filter((f) => f[5] === 1).length,
    searchTruncatedToReady:
      readyAt === null ? 0 : window.filter((f) => f[5] === 1 && f[0] <= readyAt).length,
    searchTruncatedBeforeInput: truncatedBeforeInput,
    readCostToReadyMs: readyAt === null ? null : round1(costsToReady.reduce((a, c) => a + c, 0)),
    frameStates: states.slice(0, 24),
  };
}

/**
 * The recorder's reads from the input to the frame that began at `until` (a milestone's
 * frame), among the frames logged by then, the window's and those read while milestones
 * were awaited after it (revision 6): the longest read, the reads summed, and how many of
 * those frames had a content search stopped at its bound, where the milestone's
 * predicate can have held late.
 */
export function readsUpTo(frames, origin, until) {
  const reads = frames.filter(
    (f) => f[1] !== null && inWindow(f[0], f[4], origin) && f[0] <= until,
  );
  const costs = reads.map((f) => f[3]).filter((c) => typeof c === "number");
  return {
    maxMs: costs.length ? round1(Math.max(...costs)) : null,
    toMs: round1(costs.reduce((a, c) => a + c, 0)),
    truncated: reads.filter((f) => f[5] === 1).length,
  };
}

/**
 * A hover-click's realized dwell (revision 6): from the pointer's arrival over the target,
 * its first `pointerover` inside the element the transition armed after arm, to the press
 * at `t0` that starts the clock. A boundary event elsewhere, such as one Chrome sends under
 * a stationary pointer when the page replaces the element below it, is not the arrival.
 */
export function hoverDwellOf(inputs, t0) {
  const over = inputs.find((i) => i[0] === "pointerover" && i[3] === 1 && i[1] <= t0);
  return over ? round1(t0 - over[1]) : null;
}

/**
 * Region movement over the window, from the arm-time snapshot and the per-frame log.
 * Per region and tracked component: the largest single step, the net displacement from
 * the first box to the last, and the path length (the sum of every step). A group's
 * figure is the largest over its regions and components. A region is the same region
 * across a re-created element and across frames in which it is absent: when it comes
 * back, its step is measured from where it last was, so a pull request header replaced
 * by the next one's, of another height, moves the tab bar below it. A region with
 * `identity` counts a change of that value as a replacement, not a movement.
 */
export function regionMovement(snapshot, log, t0, regions, windowEnd = Number.POSITIVE_INFINITY) {
  const out = {};
  const groups = {};
  const group = (g) => {
    groups[g] ??= { step: 0, net: 0, path: 0, replaced: 0, frames: new Set() };
    return groups[g];
  };
  group("page");
  for (const [name, spec] of Object.entries(regions)) {
    const g = group(spec.group ?? "page");
    const seq = [snapshot[name] ?? null];
    const times = [null];
    // A box logged by a frame in the window moves the region; one logged before is where
    // it stood at the input (revision 6: the input's own frame is in the window, and a
    // frame read before the input is not, whatever its begin time).
    for (const [t, n, b, seen] of log) {
      if (n !== name || t > windowEnd) {
        continue;
      }
      if (inWindow(t, seen, t0)) {
        seq.push(b);
        times.push(t);
      } else {
        seq[0] = b;
      }
    }
    const idx = { x: 0, y: 1, w: 2, h: 3 };
    const tracked = spec.track.map((c) => idx[c]);
    let steps = 0;
    let appeared = 0;
    let removed = 0;
    let replaced = 0;
    const max = [0, 0, 0, 0];
    const path = [0, 0, 0, 0];
    // Net displacement is measured between boxes of one identity: the first box after
    // the last replacement against the last box.
    let anchor = seq[0];
    // The last box the region had, so a step bridges the frames in which it was absent.
    let seen = seq[0];
    for (let i = 1; i < seq.length; i++) {
      const b = seq[i];
      if (seq[i - 1] !== null && b === null) {
        removed += 1;
      }
      if (b === null) {
        continue;
      }
      const a = seen;
      seen = b;
      if (a === null) {
        appeared += 1;
        anchor ??= b;
        continue;
      }
      if (spec.identity && a[4] !== b[4]) {
        replaced += 1;
        anchor = b;
        continue;
      }
      steps += 1;
      let moved = false;
      for (let k = 0; k < 4; k++) {
        const d = b[k] - a[k];
        path[k] += Math.abs(d);
        if (Math.abs(d) > Math.abs(max[k])) {
          max[k] = d;
        }
        if (d !== 0 && tracked.includes(k)) {
          moved = true;
        }
      }
      if (moved) {
        g.frames.add(times[i]);
      }
    }
    const first = seq[0];
    const last = seq[seq.length - 1];
    if (first === null && last === null && appeared === 0) {
      continue;
    }
    const net =
      anchor && last && (!spec.identity || anchor[4] === last[4])
        ? [0, 1, 2, 3].map((k) => last[k] - anchor[k])
        : null;
    for (const k of tracked) {
      g.step = Math.max(g.step, Math.abs(max[k]));
      g.path = Math.max(g.path, path[k]);
      if (net) {
        g.net = Math.max(g.net, Math.abs(net[k]));
      }
    }
    g.replaced += replaced;
    out[name] = {
      present: [first !== null, last !== null],
      dx: max[0],
      dy: max[1],
      dw: max[2],
      dh: max[3],
      path,
      net,
      steps,
      appeared,
      removed,
      ...(spec.identity ? { replaced } : {}),
    };
  }
  const summary = Object.fromEntries(
    Object.entries(groups).map(([g, v]) => [
      g,
      { step: v.step, net: v.net, path: v.path, replaced: v.replaced, frames: v.frames.size },
    ]),
  );
  return { regions: out, groups: summary };
}

/** What a watched list did after its first rows painted. */
export function listChanges(log, origin) {
  const after = log.filter((e) => e[0] >= origin - 1);
  const firstIndex = after.findIndex((e) => e[1].length > 0);
  if (firstIndex < 0) {
    return { firstRowsMs: null, changes: 0, rowReplacements: 0, rowsReplacedBelowSelection: 0 };
  }
  const first = after[firstIndex];
  const selected = first[2] < 0 ? 0 : first[2];
  let rowReplacements = 0;
  let selectionReplaced = false;
  const below = new Set();
  for (let i = firstIndex + 1; i < after.length; i++) {
    const prev = after[i - 1][1];
    const cur = after[i][1];
    for (let k = 0; k < Math.min(prev.length, cur.length); k++) {
      if (prev[k] !== cur[k]) {
        rowReplacements += 1;
        if (k > selected) {
          below.add(k);
        } else if (k === selected) {
          selectionReplaced = true;
        }
      }
    }
  }
  const last = after[after.length - 1];
  return {
    firstRowsMs: round1(first[0] - origin),
    lastChangeMs: round1(last[0] - origin),
    changes: after.length - firstIndex - 1,
    rowReplacements,
    rowsReplacedBelowSelection: below.size,
    selectionReplaced,
    firstKeys: first[1].slice(0, 8),
    finalKeys: last[1].slice(0, 8),
  };
}

/** The input event types whose first occurrence starts each kind of transition. */
export const START_EVENTS = {
  click: ["pointerdown", "mousedown"],
  "hover-click": ["pointerdown", "mousedown"],
  key: ["keydown"],
  "key-repeat": ["keydown"],
  type: ["keydown"],
  history: ["popstate"],
};

/** Driver bound to one page: evaluation, trusted input, and the measure step. */
export function driver(browser) {
  const { page } = browser;
  async function evaluate(expression, timeoutMs = 30000) {
    const r = await page.send(
      "Runtime.evaluate",
      { expression, returnByValue: true, awaitPromise: true },
      timeoutMs,
    );
    if (r.exceptionDetails) {
      throw new Error(
        `evaluate failed: ${expression.slice(0, 160)}: ${JSON.stringify(r.exceptionDetails).slice(0, 400)}`,
      );
    }
    return r.result.value;
  }
  async function waitFor(expression, timeoutMs = 20000, pollMs = 20) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (await evaluate(expression, Math.max(1000, deadline - Date.now()))) {
        return true;
      }
      await sleep(pollMs);
    }
    return false;
  }
  const frames = (n = 2) =>
    evaluate(
      `new Promise((resolve) => { let k = ${n}; const step = () => { k -= 1; if (k <= 0) { resolve(true); } else { requestAnimationFrame(step); } }; requestAnimationFrame(step); setTimeout(() => resolve(false), 3000); })`,
    );
  // Driver-owned scrolling happens here, before any clock starts: scroll the target into
  // view, let two frames settle, then take its center and prove a press there lands on it.
  // A list that re-anchors while it fills (the Pulls list as a selected row expands) can
  // move the target after the scroll; up to three attempts, all before the clock starts.
  async function resolveTarget(selector) {
    for (let attempt = 1; ; attempt++) {
      try {
        return await resolveOnce(selector);
      } catch (error) {
        if (!(error instanceof Refusal) || error.guard !== "hit_test" || attempt >= 3) {
          throw error;
        }
        await sleep(500);
      }
    }
  }
  async function resolveOnce(selector) {
    const sel = JSON.stringify(selector);
    const found = await evaluate(
      `(() => { const e = document.querySelector(${sel}); if (!e) { return false; } e.scrollIntoView({ block: "nearest", inline: "nearest" }); return true; })()`,
    );
    if (!found) {
      throw new Refusal("target_missing", `no element matches ${selector}`);
    }
    if (!(await frames(2))) {
      throw new Refusal("raf", "two animation frames did not arrive within 3 s");
    }
    await sleep(120);
    const point = await evaluate(`(() => {
      const e = document.querySelector(${sel});
      if (!e) { return null; }
      const r = e.getBoundingClientRect();
      const x = Math.round(r.x + Math.min(r.width / 2, 60));
      const y = Math.round(r.y + r.height / 2);
      const hit = document.elementFromPoint(x, y);
      return { x, y, hit: !!hit && (e === hit || e.contains(hit)), w: r.width, h: r.height };
    })()`);
    if (!point) {
      throw new Refusal("target_missing", `element ${selector} vanished after scrolling`);
    }
    if (!point.hit || point.w === 0 || point.h === 0) {
      throw new Refusal("hit_test", `a press at ${point.x},${point.y} would miss ${selector}`);
    }
    return point;
  }
  async function moveTo(x, y) {
    await page.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  }
  async function press(x, y) {
    await page.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    await page.send("Input.dispatchMouseEvent", {
      type: "mousePressed",
      x,
      y,
      button: "left",
      clickCount: 1,
    });
    await page.send("Input.dispatchMouseEvent", {
      type: "mouseReleased",
      x,
      y,
      button: "left",
      clickCount: 1,
    });
  }
  async function click(selector) {
    const p = await resolveTarget(selector);
    await press(p.x, p.y);
    return p;
  }
  async function key(name) {
    const k = KEYS[name] ?? {
      key: name,
      code: name.length === 1 ? `Key${name.toUpperCase()}` : name,
      windowsVirtualKeyCode: name.toUpperCase().charCodeAt(0),
      text: name,
    };
    await page.send("Input.dispatchKeyEvent", { type: k.text ? "keyDown" : "rawKeyDown", ...k });
    await page.send("Input.dispatchKeyEvent", { type: "keyUp", ...k, text: undefined });
  }
  async function park() {
    const { width, height } = browser.viewport;
    await moveTo(width - 2, height - 2);
  }
  // Characters typed back to back, each a keyDown with text and a keyUp.
  async function typeText(text, intervalMs = 0) {
    for (const ch of text) {
      await page.send("Input.dispatchKeyEvent", {
        type: "keyDown",
        key: ch,
        text: ch,
        unmodifiedText: ch,
        windowsVirtualKeyCode: ch.toUpperCase().charCodeAt(0),
      });
      await page.send("Input.dispatchKeyEvent", { type: "keyUp", key: ch });
      if (intervalMs) {
        await sleep(intervalMs);
      }
    }
  }
  // A held key: one keyDown as the key goes down, then `count - 1` keyDowns flagged
  // autoRepeat, `intervalMs` apart, then one keyUp.
  async function keyRepeat(name, count, intervalMs) {
    const k = KEYS[name];
    if (!k) {
      throw new Error(`no key definition for ${name}`);
    }
    for (let i = 0; i < count; i++) {
      if (i) {
        await sleep(intervalMs);
      }
      await page.send("Input.dispatchKeyEvent", {
        type: k.text ? "keyDown" : "rawKeyDown",
        autoRepeat: i > 0,
        ...k,
      });
    }
    await page.send("Input.dispatchKeyEvent", { type: "keyUp", ...k, text: undefined });
  }
  /**
   * Retained memory, read over the DevTools protocol after a full garbage collection
   * (revision 6). The page's main-thread V8 heap (`Runtime.getHeapUsage`: `usedSize`, and
   * where Chrome reports it the embedder heap, Blink's own objects, DOM nodes among them,
   * as `embedderHeapUsedSize`), the renderer's live DOM nodes, documents, and event
   * listeners (`Memory.getDOMCounters`: attached and detached nodes alike, so a surface
   * kept off the document still counts), the elements attached to the document, and the
   * V8 heaps of the page's dedicated workers, each collected first. It does not count
   * GPU memory, decoded images, compositor tiles, layout and style objects outside the
   * heaps, the HTTP and memory caches, or any other process. The collection is not what
   * a reader's page does on its own, so a reading taken between two transitions changes
   * what the later one measures; one taken after a journey's last transition changes
   * nothing measured.
   */
  async function memory() {
    const t0 = Date.now();
    const kb = (bytes) => (typeof bytes === "number" ? Math.round(bytes / 1024) : null);
    // The recorder's own logs since the last arm would count, and they grow with each
    // condition's frames and DOM work; every caller has read what it needs of them.
    await evaluate(`(() => {
      const R = window.__tr;
      const logs = ["frames", "regionLog", "muts", "navMuts", "shifts", "longtasks", "loafs", "events", "inputs", "alerts", "listLog"];
      for (const k of logs) { if (R && Array.isArray(R[k])) { R[k].length = 0; } }
      return true;
    })()`);
    await page.send("HeapProfiler.collectGarbage", {}, 60000);
    const heap = await page.send("Runtime.getHeapUsage", {}, 10000);
    const dom = await page.send("Memory.getDOMCounters", {}, 10000);
    let workers = 0;
    let workerHeap = 0;
    for (const [sid, type] of browser.workers) {
      const session = browser.conn.sessions.get(sid);
      if (type !== "worker" || !session) {
        continue;
      }
      try {
        await session.send("HeapProfiler.collectGarbage", {}, 30000);
        const h = await session.send("Runtime.getHeapUsage", {}, 10000);
        workers += 1;
        workerHeap += h.usedSize;
      } catch (_error) {
        // A worker that has exited holds no memory.
      }
    }
    const elements = await evaluate("document.getElementsByTagName('*').length");
    return {
      jsHeapUsedKb: kb(heap.usedSize),
      jsHeapTotalKb: kb(heap.totalSize),
      embedderHeapUsedKb: kb(heap.embedderHeapUsedSize),
      domNodes: dom.nodes,
      documents: dom.documents,
      listeners: dom.jsEventListeners,
      elements,
      workers,
      workerHeapUsedKb: kb(workerHeap),
      gcMs: Date.now() - t0,
    };
  }
  async function historyStep(delta) {
    const h = await page.send("Page.getNavigationHistory");
    const entry = h.entries[h.currentIndex + delta];
    if (!entry) {
      throw new Refusal("history", `no history entry at offset ${delta}`);
    }
    await page.send("Page.navigateToHistoryEntry", { entryId: entry.id });
  }

  /**
   * Measure one transition.
   * spec.ready: in-page `() => boolean` source, true once the exact subject is shown
   *   with useful content. It must be false before the input: a predicate that holds at
   *   arm time or in a frame before the input reaches the page refuses the transition.
   * spec.converged: in-page `() => string` source, "" when the whole application agrees
   *   on the subject after settling, else what disagrees.
   * spec.input: { kind: "click" | "hover-click" | "key" | "key-repeat" | "type" |
   *   "history" | "navigate" | "reload", selector?, hoverMs?, key?, count?, intervalMs?,
   *   text?, delta?, url? }.
   * spec.emptyState: true when the destination is a tab's prompt by design, so frames
   *   that show only the prompt are not blank.
   * spec.milestones: { name: in-page `() => boolean` source }, each timed like painted
   *   ready, waited for after the window closes so the other fields keep their window.
   * spec.list: { rows: selector }, an ordered list whose rows are watched for replacement.
   * spec.landing: in-page `() => string` source naming which of a destination's landings
   *   the subject was (the Commits landing: `empty`, `newest`, or `restored`), read with
   *   `converged` and recorded as `landing`; null when the subject was never ready. A ready
   *   predicate with several branches may name the one that held first in `readyBranch`,
   *   cleared at arm and recorded as `landingAtReady`.
   * spec.memory: true to read retained memory after the transition (`memory`), which
   *   collects garbage and so changes what the journey's later transitions measure.
   */
  async function measure(spec) {
    const settleMs = spec.settleMs ?? 400;
    const timeoutMs = spec.timeoutMs ?? 20000;
    const input = spec.input;
    let point = null;
    if (input.kind === "click" || input.kind === "hover-click") {
      point = await resolveTarget(input.selector);
    }
    const viewport0 = await evaluate(
      "({ w: innerWidth, h: innerHeight, vis: document.visibilityState })",
    );
    const netMark = browser.net.length;
    const excMark = browser.exceptions.length;
    const consoleMark = browser.consoleErrors.length;
    const landing = input.kind === "navigate" || input.kind === "reload";
    const startEvents = START_EVENTS[input.kind] ?? null;
    const milestoneFns = spec.milestones
      ? `{ ${Object.entries(spec.milestones)
          .map(([name, fn]) => `${JSON.stringify(name)}: (${fn})`)
          .join(", ")} }`
      : "null";
    const hoverTarget = input.kind === "hover-click" ? input.selector : null;
    const armExtras = `R.listSpec = ${JSON.stringify(spec.list ?? null)}; R.listLog = []; R.lastList = null; R.milestoneFns = ${milestoneFns}; R.milestones = {}; R.readyBranch = null; R.hoverTarget = ${JSON.stringify(hoverTarget)};`;
    let armScript = null;
    if (landing) {
      // Marks the outgoing document, so waiting below cannot read its recorder.
      await evaluate("window.__trOld = true");
      armScript = await page.send("Page.addScriptToEvaluateOnNewDocument", {
        // Runs after the recorder's own document-start script, so the recorder exists. A
        // landing's origin is navigation start, so the input is in from the first frame.
        source: `(() => { const R = window.__tr; R.readyFn = (${spec.ready}); R.armedAt = 0; R.inputAt = 0; R.startEvents = null; ${armExtras} })();`,
      });
    } else {
      await evaluate(`(() => {
        const R = window.__tr;
        const pane = document.getElementById("preview-pane");
        for (const c of pane ? pane.children : []) { c.dataset.trMark = "1"; }
        R.frames.length = 0; R.regionLog.length = 0; R.muts.length = 0; R.navMuts.length = 0;
        R.shifts.length = 0; R.longtasks.length = 0; R.loafs.length = 0; R.events.length = 0;
        R.inputs.length = 0; R.alerts.length = 0; R.hiddenFrames = 0; R.frameCount = 0;
        R.snapshot = R.snapshotRegions();
        R.state0 = R.state();
        R.spanMark = window.metabrowser?.perf?.snapshot ? window.metabrowser.perf.snapshot().measure_samples_seen : null;
        R.readyAt = null; R.readyRead = null; R.readyNext = null; R.readyBeforeInput = null;
        R.inputAt = null; R.startEvents = ${JSON.stringify(startEvents)};
        R.readyFn = (${spec.ready});
        R.searchTruncated = false;
        R.readyAtArm = (() => { try { return Boolean(R.readyFn()); } catch (_error) { return false; } })();
        R.armTruncated = R.searchTruncated;
        R.dom0 = document.getElementsByTagName("*").length;
        ${armExtras}
        R.armedAt = performance.now();
      })()`);
    }
    if (input.kind === "click") {
      await press(point.x, point.y);
    } else if (input.kind === "hover-click") {
      await moveTo(point.x, point.y);
      await sleep(input.hoverMs);
      await press(point.x, point.y);
    } else if (input.kind === "key") {
      await key(input.key);
    } else if (input.kind === "key-repeat") {
      await keyRepeat(input.key, input.count, input.intervalMs);
    } else if (input.kind === "type") {
      await typeText(input.text, input.intervalMs ?? 0);
    } else if (input.kind === "history") {
      await historyStep(input.delta);
    } else if (input.kind === "navigate") {
      await page.send("Page.navigate", { url: input.url });
    } else if (input.kind === "reload") {
      await page.send("Page.reload", { ignoreCache: false });
    } else {
      throw new Error(`unknown input kind ${input.kind}`);
    }
    if (landing) {
      await waitFor("!window.__trOld && !!window.__tr", timeoutMs);
    }
    const reached = await waitFor("!!window.__tr && window.__tr.readyNext !== null", timeoutMs);
    if (armScript) {
      await page.send("Page.removeScriptToEvaluateOnNewDocument", {
        identifier: armScript.identifier,
      });
    }
    await sleep(settleMs);
    const raw = await evaluate(`(() => {
      const R = window.__tr;
      const pane = document.getElementById("preview-pane");
      const kept = !!(pane && pane.querySelector(":scope > [data-tr-mark]"));
      for (const c of document.querySelectorAll("[data-tr-mark]")) { delete c.dataset.trMark; }
      let spans = [];
      try {
        if (R.spanMark !== null && R.spanMark !== undefined) {
          const snap = window.metabrowser.perf.snapshot();
          const n = snap.measure_samples_seen - R.spanMark;
          spans = n > 0 ? snap.raw_measure.slice(-n).filter((x) => /ToReady/.test(x.label)).slice(0, 6).map((x) => [x.label, Math.round(x.duration_ms * 10) / 10]) : [];
        }
      } catch (_error) { spans = []; }
      return {
        frames: R.frames, regionLog: R.regionLog, snapshot: R.snapshot || {}, muts: R.muts,
        navMuts: R.navMuts, shifts: R.shifts, longtasks: R.longtasks, loafs: R.loafs,
        events: R.events, inputs: R.inputs, alerts: R.alerts, hiddenFrames: R.hiddenFrames,
        visibilityChanges: R.visibilityChanges, readyAt: R.readyAt, readyRead: R.readyRead,
        readyNext: R.readyNext, readyBeforeInput: R.readyBeforeInput,
        readyAtArm: R.readyAtArm === true, armTruncated: R.armTruncated === true, inputAt: R.inputAt,
        armedAt: R.armedAt, observers: R.observers, kept, spans, state0: R.state0 ?? "",
        dom0: R.dom0 ?? null, dom1: document.getElementsByTagName("*").length,
        w: innerWidth, h: innerHeight, vis: document.visibilityState, path: location.pathname,
        timeOrigin: performance.timeOrigin,
        listLog: R.listLog, readyBranch: R.readyBranch ?? null,
      };
    })()`);
    await evaluate("window.__tr.readyFn = null; window.__tr.listSpec = null");
    // A converged check whose content search stopped at its bound can report content
    // missing that is on screen; it is marked uncertain (revision 6).
    const [converged, convergedTruncated] =
      raw.readyAt === null
        ? ["never ready", false]
        : await evaluate(
            `(() => { const R = window.__tr; R.searchTruncated = false; const v = (${spec.converged})(); return [v, R.searchTruncated === true]; })()`,
          );
    const landingSeen =
      spec.landing && raw.readyAt !== null ? await evaluate(`(${spec.landing})()`) : null;
    const net = browser.net.slice(netMark);
    const exceptions = browser.exceptions.slice(excMark);
    const consoleErrors = browser.consoleErrors.slice(consoleMark);

    const refusals = [];
    let t0;
    if (landing) {
      t0 = 0;
    } else {
      const first = raw.inputs.find((i) => startEvents.includes(i[0]));
      t0 = first ? first[1] : null;
      if (first && first[2] !== true) {
        refusals.push([
          "input_observed",
          `the ${first[0]} that started the transition was not trusted`,
        ]);
      }
    }
    if (t0 === null) {
      refusals.push(["input_observed", `no ${startEvents.join(" or ")} event reached the page`]);
    }
    if (raw.readyAtArm || raw.readyBeforeInput !== null) {
      refusals.push([
        "ready_before_input",
        raw.readyAtArm
          ? "the ready predicate already held when the transition was armed"
          : "the ready predicate held in a frame before the input reached the page",
      ]);
    }
    if (!reached || raw.readyAt === null) {
      refusals.push(["converged", `not ready within ${timeoutMs} ms`]);
    } else if (converged !== "") {
      refusals.push([
        "converged",
        `${converged}${convergedTruncated ? " (uncertain: the content search stopped at its bound)" : ""}`,
      ]);
    }
    if (viewport0.vis !== "visible" || raw.vis !== "visible" || raw.hiddenFrames > 0) {
      refusals.push([
        "visibility",
        `${viewport0.vis}/${raw.vis}, hidden frames ${raw.hiddenFrames}`,
      ]);
    }
    if (viewport0.w < 1440 || viewport0.h < 900 || raw.w < 1440 || raw.h < 900) {
      refusals.push(["viewport", `${raw.w}x${raw.h}`]);
    }
    const origin = t0 ?? raw.armedAt;
    const lastFrame = raw.frames.length ? raw.frames[raw.frames.length - 1][0] : origin;
    const windowEnd = raw.readyNext === null ? lastFrame : raw.readyNext + settleMs;
    const gesture = raw.inputs.filter((i) => startEvents?.includes(i[0]) && i[1] >= origin);
    const inputSpanMs = gesture.length > 1 ? round1(gesture[gesture.length - 1][1] - origin) : 0;
    // A hover-click's realized dwell (`hoverDwellOf`), which the page's own hover intent
    // sees, not the requested `hoverMs`.
    const hoverDwellMs =
      input.kind === "hover-click" && t0 !== null ? hoverDwellOf(raw.inputs, t0) : undefined;

    // Milestones are waited for after the window above has closed, so every other field
    // keeps the window it had before milestones existed. One that never arrives is null,
    // and is named in `milestonesMissing`.
    // The frames read while they were awaited are read too, for each milestone's reads up
    // to it and the content searches stopped at their bound there (revision 6).
    let milestones;
    let milestonesMissing;
    let milestoneReads;
    let searchTruncatedAfterWindow;
    let extraWaitMs = 0;
    if (spec.milestones) {
      const names = Object.keys(spec.milestones);
      const w0 = Date.now();
      await waitFor(
        `(() => { const m = window.__tr.milestones; return ${JSON.stringify(names)}.every((n) => m[n] && m[n][2] !== null); })()`,
        spec.milestoneTimeoutMs ?? 10000,
        50,
      );
      extraWaitMs = Date.now() - w0;
      const got = await evaluate("window.__tr.milestones");
      const loafsNow = await evaluate("window.__tr.loafs");
      const later = await evaluate(`window.__tr.frames.slice(${raw.frames.length})`);
      await evaluate("window.__tr.milestoneFns = null");
      const read = [...raw.frames, ...later];
      milestoneReads = Object.fromEntries(
        names.map((n) => [n, got[n] ? readsUpTo(read, origin, got[n][0]) : null]),
      );
      searchTruncatedAfterWindow = read.filter(
        (f) => f[5] === 1 && f[0] > windowEnd && inWindow(f[0], f[4], origin),
      ).length;
      const interval = frameInterval(raw.frames.map((f) => f[0]));
      milestones = Object.fromEntries(
        names.map((n) => {
          const m = got[n];
          if (!m || m[2] === null) {
            return [n, null];
          }
          return [n, round1(presentedAt(m[0], m[1], loafsNow, interval) - origin)];
        }),
      );
      milestonesMissing = names.filter((n) => milestones[n] === null);
    }
    // A body the DevTools event left out is asked for once the request has been sent.
    for (const r of net) {
      if (r.method === "POST" && r.postBytes === null) {
        try {
          const session = r.sid === page.sessionId ? page : browser.conn.sessions.get(r.sid);
          const body = await session.send("Network.getRequestPostData", { requestId: r.id });
          const bytes = body.base64Encoded
            ? Buffer.from(body.postData, "base64")
            : Buffer.from(body.postData, "utf8");
          r.postBytes = bytes.length;
          r.postText ??= bytes.toString("utf8").slice(0, 1024);
        } catch (_error) {
          // The body is no longer held; the request stays counted with unknown bytes.
        }
      }
    }
    // Retained memory after this transition, when the round asked for it: read last, after
    // every other field, since its garbage collection changes what follows (`memory`).
    const retained = spec.memory ? await memory() : undefined;
    const frameAccount = accountFrames({
      frames: raw.frames,
      origin,
      windowEnd,
      readyAt: raw.readyAt,
      readyRead: raw.readyRead,
      readyNext: raw.readyNext,
      loafs: raw.loafs,
      emptyState: spec.emptyState === true,
      initialCode: landing ? "" : raw.state0,
    });
    if (frameAccount.framesInWindow < 2) {
      refusals.push(["raf", `${frameAccount.framesInWindow} animation frames after input`]);
    }
    // A frame clock running far below the display rate is a throttled page, not a slow one.
    if (frameAccount.medianFrameStepMs !== null && frameAccount.medianFrameStepMs > 50) {
      refusals.push([
        "frame_clock",
        `median frame step ${frameAccount.medianFrameStepMs} ms over the window`,
      ]);
    }
    if (exceptions.length) {
      refusals.push(["page_exceptions", exceptions[0].text]);
    }
    if (raw.alerts.length) {
      refusals.push(["rendered_errors", `${raw.alerts[0][1]}: ${raw.alerts[0][2]}`]);
    }

    const rel = (t) => round1(t - origin);
    const muts = raw.muts.filter((m) => m[0] >= origin && m[0] <= windowEnd);
    const navMuts = raw.navMuts.filter((m) => m[0] >= origin && m[0] <= windowEnd);
    const shifts = raw.shifts.filter((s) => s.t >= (landing ? 0 : raw.armedAt));
    const end = raw.readyNext === null ? Number.POSITIVE_INFINITY : windowEnd;
    const longtasks = raw.longtasks.filter((x) => x[0] + x[1] >= origin && x[0] <= end);
    const loafs = raw.loafs.filter((x) => x[0] + x[1] >= origin && x[0] <= end);
    const events = raw.events.filter((x) => x[0] >= origin - 1);
    const movement = regionMovement(raw.snapshot, raw.regionLog, origin, REGIONS, windowEnd);
    const byFamily = {};
    for (const r of net) {
      if (r.family === "inline") {
        continue;
      }
      byFamily[r.family] ??= {};
      const d = disposition(r);
      byFamily[r.family][d] = (byFamily[r.family][d] ?? 0) + 1;
    }
    const posts = net.filter((r) => r.method === "POST");

    const byClass = {};
    for (const r of net) {
      byClass[r.cls] = (byClass[r.cls] ?? 0) + 1;
    }
    // Requests for the selected subject: duplicates, and a pull request page's settlement
    // reads after its own refresh, counted apart (see subjectReads).
    const subject = subjectReads(net, [spec.subjectRequest ?? []].flat(), spec.subjectPull ?? null);
    const readyReadMs = raw.readyRead === null ? null : raw.readyRead;
    const page0 = movement.groups.page;
    return {
      id: spec.id,
      journey: spec.journey,
      subject: spec.subject,
      input: input.kind,
      ok: refusals.length === 0,
      refusals,
      ...(spec.landing ? { landing: landingSeen, landingAtReady: raw.readyBranch } : {}),
      ...frameAccount,
      // Local correlation with server and subprocess records. The transition durations
      // still use the browser's monotonic clock.
      inputEpochMs: t0 === null ? null : round1(raw.timeOrigin + t0),
      // The ready-before-input guard read the arm check and the frames before the input;
      // when a content search in any of them stopped at its bound, a false "not ready"
      // there can have hidden a subject shown before the input (revision 6).
      searchTruncatedBeforeInput:
        frameAccount.searchTruncatedBeforeInput + (raw.armTruncated ? 1 : 0),
      readyBeforeInputUncertain:
        frameAccount.searchTruncatedBeforeInput > 0 || raw.armTruncated === true,
      convergedUncertain: convergedTruncated === true,
      // DOM work after the subject was shown, reported apart from readiness: when the
      // preview, and the navigation panels, last changed inside the window; 0 when they
      // did not change at all.
      settledMs: muts.length ? rel(muts[muts.length - 1][0]) : 0,
      paneMutationsAfterReady:
        readyReadMs === null ? null : muts.filter((m) => m[0] > readyReadMs).length,
      navSettledMs: navMuts.length ? rel(navMuts[navMuts.length - 1][0]) : 0,
      windowMs: rel(windowEnd),
      movementPx: page0.step,
      movementNetPx: page0.net,
      movementPathPx: page0.path,
      movementByGroup: Object.fromEntries(
        Object.entries(movement.groups).filter(([g]) => g !== "page"),
      ),
      regions: movement.regions,
      inputSpanMs,
      hoverDwellMs,
      readyAfterLastInputMs:
        frameAccount.paintedReadyMs === null
          ? null
          : round1(frameAccount.paintedReadyMs - inputSpanMs),
      milestones,
      milestonesMissing,
      milestoneReads,
      searchTruncatedAfterWindow,
      extraWaitMs,
      list: spec.list ? listChanges(raw.listLog, origin) : undefined,
      shifts: {
        available: raw.observers["layout-shift"] === true,
        count: shifts.length,
        sum: round4(shifts.reduce((a, s) => a + s.v, 0)),
        sumNoInput: round4(shifts.filter((s) => !s.input).reduce((a, s) => a + s.v, 0)),
        entries: shifts.slice(0, 8).map((s) => ({
          t: rel(s.t),
          v: round4(s.v),
          input: s.input,
          src: s.src.slice(0, 3),
        })),
      },
      requests: {
        total: net.filter((r) => r.cls !== "inline").length,
        byClass,
        subject: subject.total,
        subjectDuplicates: subject.duplicates,
        subjectSettlementReads: subject.settlement,
        byFamily,
        fileEnvelopes: net.filter((r) => /^https?:\/\/[^/]+\/api\/file\?/.test(r.url)).length,
        // Background posts (the Pulls catalog walk) run on their own timer, so they are
        // reported by class and left out of the total.
        postBytes: posts
          .filter((r) => r.cls !== "background")
          .reduce((a, r) => a + (r.postBytes ?? 0), 0),
        postBytesByClass: posts.reduce((acc, r) => {
          acc[r.cls] = (acc[r.cls] ?? 0) + (r.postBytes ?? 0);
          return acc;
        }, {}),
        posts: posts.slice(0, 12).map((r) => ({
          u: r.url.replace(/^https?:\/\/[^/]+/, "").slice(0, 100),
          bytes: r.postBytes,
        })),
        list: net
          .filter((r) => r.cls !== "inline")
          .slice(0, 60)
          .map((r) => ({
            c: r.cls,
            k: r.kind === "worker" ? "w" : undefined,
            m: r.method === "GET" ? undefined : r.method,
            u: r.url.replace(/^https?:\/\/[^/]+/, "").slice(0, 140),
            st: r.status,
            net: r.netStatus ?? undefined,
            d: disposition(r),
            cache: r.cache ?? undefined,
            failed: r.failed ?? undefined,
          })),
      },
      previewTop: {
        removed: muts.reduce((a, m) => a + m[2], 0),
        added: muts.reduce((a, m) => a + m[3], 0),
        records: muts.reduce((a, m) => a + m[1], 0),
        keptPriorTop: raw.kept,
      },
      longTasks: {
        available: raw.observers.longtask === true,
        count: longtasks.length,
        maxMs: Math.round(Math.max(0, ...longtasks.map((x) => x[1]))),
        totalMs: Math.round(longtasks.reduce((a, x) => a + x[1], 0)),
      },
      loaf: {
        available: raw.observers["long-animation-frame"] === true,
        count: loafs.length,
        maxMs: Math.round(Math.max(0, ...loafs.map((x) => x[1]))),
        maxBlockingMs: Math.round(Math.max(0, ...loafs.map((x) => x[2]))),
      },
      eventTimingMaxMs: events.length ? Math.round(Math.max(...events.map((x) => x[1]))) : null,
      // Event Timing's own presentation time for the first event of each type, the next
      // paint after its handlers (rounded by Chrome to 8 ms; events under 16 ms are not
      // reported). A frame that showed the subject in that paint should match it.
      eventPresentedMs: Object.fromEntries(
        ["pointerdown", "click", "keydown"].flatMap((type) => {
          const e = events.find((x) => x[2] === type);
          return e ? [[type, round1(e[0] + e[1] - origin)]] : [];
        }),
      ),
      spans: raw.spans,
      dom: { start: raw.dom0, end: raw.dom1 },
      memory: retained,
      route: raw.path,
      exceptions,
      consoleErrors,
      alerts: raw.alerts,
      raw: spec.debug ? raw : undefined,
    };
  }

  const navigate = (url) => page.send("Page.navigate", { url });
  return {
    evaluate,
    waitFor,
    frames,
    resolveTarget,
    moveTo,
    press,
    click,
    key,
    park,
    navigate,
    measure,
    memory,
  };
}
