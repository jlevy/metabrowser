// In-page recorder and trusted-input driver for the transition-navigation/v1 scenario
// (revision 3).
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
  for (const type of ["pointerdown", "mousedown", "click", "keydown", "popstate"]) {
    window.addEventListener(
      type,
      (e) => {
        R.inputs.push([type, e.timeStamp, e.isTrusted]);
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
      if (cs.overflowX !== "visible" || cs.overflowY !== "visible") {
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
  const textShown = (node) => {
    const parent = node.parentElement;
    if (!parent || !rendered(parent)) {
      return false;
    }
    range.selectNodeContents(node);
    for (const r of range.getClientRects()) {
      if (r.width > 0 && r.height > 0 && clipped(parent, r)) {
        return true;
      }
    }
    return false;
  };
  // Visible, laid-out content: text on screen outside a placeholder, prompt, or
  // screen-reader-only label, or media that has loaded. Stops at the first hit and looks
  // at no more than 400 candidate text nodes, so a large document costs a few steps.
  const hasUseful = (root) => {
    if (!root || !rendered(root)) {
      return false;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let candidates = 0;
    for (let node = walker.nextNode(); node && candidates < 400; node = walker.nextNode()) {
      if (!node.nodeValue?.trim()) {
        continue;
      }
      const parent = node.parentElement;
      if (parent?.closest(`${PLACEHOLDER}, .sr-only, ${EMPTY}`)) {
        continue;
      }
      candidates += 1;
      if (textShown(node)) {
        return true;
      }
    }
    for (const el of root.querySelectorAll("img, canvas, iframe, video, svg")) {
      if (mediaShown(el)) {
        return true;
      }
    }
    return false;
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

  // A box is [x, y, w, h], and a region with `identity` also carries that attribute.
  const box = (spec) => {
    const el = document.querySelector(spec.selector);
    if (!el) {
      return null;
    }
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) {
      return null;
    }
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
      out[name] = box(spec);
    }
    R.lastBox = { ...out };
    return out;
  };
  const trackRegions = (t) => {
    for (const [name, spec] of Object.entries(R.regions)) {
      const b = box(spec);
      if (!sameBox(b, R.lastBox[name])) {
        R.regionLog.push([t, name, b]);
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
  const read = (frame) => {
    frame.readNow = performance.now();
    let code;
    try {
      code = state();
    } catch (_error) {
      code = "X";
    }
    R.frames.push([frame.t, code, round1(frame.readNow)]);
    trackRegions(frame.t);
    checkAlerts(frame.t);
    trackList(frame.t);
    const inputSeen = R.inputAt !== null;
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
  };
  const tick = (t) => {
    R.frameCount += 1;
    // A frame whose observation never arrived is recorded without a state.
    const missed = R.pending;
    if (missed && missed.readNow === null) {
      missed.observer?.disconnect();
      R.frames.push([missed.t, null, null]);
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
  return { net: [], byId: new Map(), early: new Map() };
}

/**
 * Apply one DevTools Network event to a request log. The ExtraInfo events can arrive
 * before the event they belong to, so their fields wait in `early` until it does.
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
    const entry = log.byId.get(key);
    if (entry) {
      merge(entry, fields);
    } else {
      log.early.set(key, { ...(log.early.get(key) ?? {}), ...fields });
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
    const early = log.early.get(key);
    if (early) {
      merge(entry, early);
      log.early.delete(key);
    }
    log.net.push(entry);
    log.byId.set(key, entry);
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
 */
export async function launchBrowser({
  profileDir,
  headed = false,
  width = 1440,
  height = 900,
  extraArgs = [],
  onSpawn = null,
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
    const deadline = Date.now() + 30000;
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
      throw new Error("Chrome did not publish a DevTools endpoint within 30 s");
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
 * Frame accounting for one transition window, from the per-frame states.
 * `frames` are [frame time, state code or null, read time]; a null code (a frame whose
 * observation never arrived) shows what the previous frame showed and is counted as
 * uncredited. Every count covers the whole window, from the input to its end, and is
 * split at the ready frame; `emptyState` is the destination's own prompt, declared by
 * the journey, whose frames are not blank.
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
  let last = initialCode;
  for (const f of frames) {
    if (f[0] < origin && f[1] !== null) {
      last = f[1];
    }
  }
  const window = frames.filter((f) => f[0] >= origin && f[0] <= windowEnd);
  const filled = window.map((f) => {
    if (f[1] !== null) {
      last = f[1];
    }
    return { t: f[0], code: f[1] === null ? last : f[1], uncredited: f[1] === null };
  });
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
    blankMs: blank.ms,
    placeholderVisibleFrames: placeholder.total,
    placeholderVisibleFramesAfterReady: placeholder.after,
    placeholderVisibleMs: placeholder.ms,
    navPlaceholderVisibleFrames: nav.total,
    uncreditedFrames: uncredited.total,
    frameStates: states.slice(0, 24),
  };
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
    for (const [t, n, b] of log) {
      if (n !== name || t > windowEnd) {
        continue;
      }
      if (t >= t0 - 1) {
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
    const armExtras = `R.listSpec = ${JSON.stringify(spec.list ?? null)}; R.listLog = []; R.lastList = null; R.milestoneFns = ${milestoneFns}; R.milestones = {};`;
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
        R.readyAtArm = (() => { try { return Boolean(R.readyFn()); } catch (_error) { return false; } })();
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
        readyAtArm: R.readyAtArm === true, inputAt: R.inputAt,
        armedAt: R.armedAt, observers: R.observers, kept, spans, state0: R.state0 ?? "",
        dom0: R.dom0 ?? null, dom1: document.getElementsByTagName("*").length,
        w: innerWidth, h: innerHeight, vis: document.visibilityState, path: location.pathname,
        listLog: R.listLog,
      };
    })()`);
    await evaluate("window.__tr.readyFn = null; window.__tr.listSpec = null");
    const converged =
      raw.readyAt === null ? "never ready" : await evaluate(`(${spec.converged})()`);
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
      refusals.push(["converged", String(converged)]);
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

    // Milestones are waited for after the window above has closed, so every other field
    // keeps the window it had before milestones existed. One that never arrives is null,
    // and is named in `milestonesMissing`.
    let milestones;
    let milestonesMissing;
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
      await evaluate("window.__tr.milestoneFns = null");
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
      ...frameAccount,
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
      readyAfterLastInputMs:
        frameAccount.paintedReadyMs === null
          ? null
          : round1(frameAccount.paintedReadyMs - inputSpanMs),
      milestones,
      milestonesMissing,
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
  };
}
