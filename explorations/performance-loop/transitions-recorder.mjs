// In-page recorder and trusted-input driver for the transition-navigation/v1 scenario
// (revision 2).
//
// Measurement only: it drives the unmodified product over the Chrome DevTools Protocol
// with trusted input and observes it from inside the page. Every in-page time is on the
// page clock (input event timeStamp, rAF timestamps, performance.now), so CDP round-trip
// latency never enters a number. See README.md, "Transition Navigation Scenario".
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { CHROME, Connection, sleep } from "./pr-cdp.mjs";

export { sleep };

// Named regions whose per-frame post-layout box is recorded. `track` names the box
// components that count toward a transition's movement figure; the others are still
// recorded per region. Add a region here and every later run records it.
//
// `group` keeps figures apart: the page group (the default) is `movementPx`, and every
// other group reports under `movementByGroup`, so adding a group never changes the page
// figure. A `sameNode` region counts a step only while the selector keeps matching the
// same element; a different element is a replacement, not a movement. A `scroller`
// region is measured in that scroll container's content coordinates, so scrolling it is
// not movement, as Layout Instability does not count scrolling either.
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
    sameNode: true,
    scroller: "#tree-content",
  },
  treeRowTests: {
    selector: '#tab-files .tree-item.tree-folder[data-path="tests"]',
    track: ["y"],
    group: "tree",
    sameNode: true,
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
 * @param {{ regions: Record<string, { selector: string }> }} config
 */
function recorderMain(config) {
  if (window.__tr) {
    return;
  }
  const PLACEHOLDER = ".loading, .mb-delayed-loading";
  const MEDIA = "img, canvas, iframe, video";
  const R = {
    frames: [],
    regionLog: [],
    lastBox: {},
    muts: [],
    shifts: [],
    longtasks: [],
    loafs: [],
    events: [],
    inputs: [],
    alerts: [],
    hiddenFrames: 0,
    visibilityChanges: 0,
    lastChange: 0,
    readyFn: null,
    readyAt: null,
    readyNext: null,
    armedAt: 0,
    frameCount: 0,
    regions: config.regions,
    observers: {},
    listSpec: null,
    listLog: [],
    lastList: null,
    milestoneFns: null,
    milestones: {},
  };
  window.__tr = R;
  const nodeIds = new WeakMap();
  let nextNodeId = 0;
  const nodeId = (el) => {
    if (!nodeIds.has(el)) {
      nextNodeId += 1;
      nodeIds.set(el, nextNodeId);
    }
    return nodeIds.get(el);
  };

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
    R.loafs.push([e.startTime, e.duration, e.blockingDuration || 0]);
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
      },
      true,
    );
  }
  document.addEventListener("visibilitychange", () => {
    R.visibilityChanges += 1;
  });

  // In layout, inside the viewport, and not clipped away by a scrolling or collapsed
  // ancestor (a collapsed tree group is height 0 with overflow hidden) or hidden by an
  // ancestor at zero opacity (the inert preview stage).
  const isPlaceholderShown = (l) => {
    const r = l.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) {
      return false;
    }
    let left = Math.max(r.left, 0);
    let top = Math.max(r.top, 0);
    let right = Math.min(r.right, innerWidth);
    let bottom = Math.min(r.bottom, innerHeight);
    for (let a = l.parentElement; a && a !== document.documentElement; a = a.parentElement) {
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
  // Some text outside a placeholder, prompt, or screen-reader-only label; else a media
  // element or a drawing larger than an icon. Stops at the first hit, so a large
  // document costs one step.
  const hasUseful = (root) => {
    if (!root) {
      return false;
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.nodeValue?.trim()) {
        continue;
      }
      const parent = node.parentElement;
      if (parent?.closest(`${PLACEHOLDER}, .sr-only, .preview-empty, [data-preview-empty]`)) {
        continue;
      }
      return true;
    }
    if (root.querySelector(MEDIA)) {
      return true;
    }
    for (const svg of root.querySelectorAll("svg")) {
      const r = svg.getBoundingClientRect();
      if (r.width >= 64 && r.height >= 64) {
        return true;
      }
    }
    return false;
  };
  R.hasUseful = hasUseful;
  R.hasPlaceholder = (root) => placeholders(root).length > 0;

  // What the reader can see in the preview pane this frame. Letters: U useful content,
  // E an empty prompt, P a visible placeholder, p a mounted placeholder still inside its
  // reveal delay, b the pending modifier, N a visible placeholder in the active nav panel.
  const state = () => {
    const pane = document.getElementById("preview-pane");
    if (!pane) {
      return "-";
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
      if (c.classList.contains("preview-empty") || c.hasAttribute("data-preview-empty")) {
        empty = true;
        continue;
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
      (empty || roots.length === 0 ? "E" : "") +
      (shown ? (visible ? "P" : "p") : "") +
      (pane.classList.contains("preview-navigation-pending") ? "b" : "") +
      nav
    );
  };
  R.state = state;

  // A box is [x, y, w, h]; a sameNode region's box also carries the element's id.
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
    if (spec.sameNode) {
      b.push(nodeId(el));
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
  const trackMilestones = (t) => {
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
        R.milestones[name] = [t, null];
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

  // Sampling runs in a task posted from rAF, after that frame's own style, layout, and
  // paint. A frame is credited only when no DOM change followed its rAF; an uncredited
  // frame reads no geometry at all, so the recorder never forces a layout.
  const sample = (t, rafNow) => {
    R.frameCount += 1;
    if (R.readyAt !== null && R.readyNext === null) {
      R.readyNext = t;
    }
    for (const m of Object.values(R.milestones)) {
      if (m[1] === null && m[0] < t) {
        m[1] = t;
      }
    }
    if (document.visibilityState !== "visible") {
      R.hiddenFrames += 1;
    }
    if (R.lastChange > rafNow) {
      R.frames.push([t, null]);
      return;
    }
    let code;
    try {
      code = state();
    } catch (_error) {
      code = "X";
    }
    R.frames.push([t, code]);
    trackRegions(t);
    checkAlerts(t);
    trackList(t);
    trackMilestones(t);
    if (R.readyFn && R.readyAt === null) {
      let ok = false;
      try {
        ok = Boolean(R.readyFn());
      } catch (_error) {
        ok = false;
      }
      if (ok) {
        R.readyAt = t;
      }
    }
  };
  const channel = new MessageChannel();
  const queue = [];
  channel.port1.onmessage = () => {
    const q = queue.shift();
    if (q !== undefined) {
      sample(q[0], q[1]);
    }
  };
  const tick = (t) => {
    queue.push([t, performance.now()]);
    channel.port2.postMessage(0);
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  new MutationObserver(() => {
    R.lastChange = performance.now();
  }).observe(document, {
    childList: true,
    subtree: true,
    attributes: true,
    characterData: true,
  });
  const attachPane = () => {
    const pane = document.getElementById("preview-pane");
    if (!pane) {
      return;
    }
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
    }).observe(pane, { childList: true, subtree: true });
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachPane);
  } else {
    attachPane();
  }
}

/** Source evaluated at document start: the region map, then the recorder. */
export function recorderSource(regions = REGIONS) {
  const config = { regions: Object.fromEntries(Object.entries(regions)) };
  return `(${recorderMain.toString()})(${JSON.stringify(config)});`;
}

// Request classes. Background routes are the Pulls catalog walk and its preparation,
// which run on a timer after every page load whatever the reader does.
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
      (u.searchParams.has("after") || u.searchParams.get("limit") === "8"))
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
 * How a request was satisfied, from its DevTools events: `cache` when the memory or disk
 * cache answered with no network request, `revalidated` for a 304, `network` for any
 * other response, `failed`, or `pending` when no response had arrived.
 */
export function disposition(entry) {
  if (entry.cache) {
    return "cache";
  }
  if (entry.failed) {
    return "failed";
  }
  if (entry.status === 304) {
    return "revalidated";
  }
  if (entry.status !== null) {
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

/**
 * One fresh Chrome profile with the recorder installed on every new document.
 * Network, exceptions, and console errors are collected from the page and from its
 * dedicated workers.
 */
export async function launchBrowser({ profileDir, headed = false, width = 1440, height = 900 }) {
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
    "about:blank",
  ];
  const chrome = spawn(CHROME, args, { stdio: ["ignore", "ignore", "pipe"] });
  chrome.stderr.on("data", () => {});
  let ws = null;
  for (let i = 0; i < 300 && !ws; i++) {
    const f = path.join(profileDir, "DevToolsActivePort");
    if (fs.existsSync(f)) {
      const [port, wsPath] = fs.readFileSync(f, "utf8").trim().split("\n");
      if (port && wsPath) {
        ws = `ws://127.0.0.1:${port}${wsPath}`;
      }
    }
    if (!ws) {
      if (chrome.exitCode !== null) {
        break;
      }
      await sleep(100);
    }
  }
  if (!ws) {
    chrome.kill("SIGKILL");
    throw new Error("Chrome did not publish a DevTools endpoint");
  }
  const conn = new Connection(ws);
  await conn.open();
  const version = await conn.send("Browser.getVersion");
  const page = await conn.newPage("about:blank");
  const net = [];
  const byId = new Map();
  const exceptions = [];
  const consoleErrors = [];
  const workers = new Map();
  const kindOf = (sid) => (sid === page.sessionId ? "page" : workers.has(sid) ? "worker" : null);
  conn.listeners.add((method, params, sid) => {
    if (method === "Target.attachedToTarget") {
      const child = conn.adopt(params.sessionId, params.targetInfo.targetId);
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
    if (method === "Network.requestWillBeSent") {
      const entry = {
        kind,
        sid,
        id: params.requestId,
        method: params.request.method,
        family: routeFamily(params.request.url, params.type),
        postBytes: params.request.method === "POST" ? postBytesOf(params.request) : 0,
        encoded: null,
        url: params.request.url,
        type: params.type,
        cls: requestClass(params.request.url, params.type),
        wall: Math.round(params.wallTime * 1000),
        status: null,
        cache: null,
        failed: null,
      };
      if (params.redirectResponse) {
        entry.redirect = true;
      }
      net.push(entry);
      byId.set(`${sid}:${params.requestId}`, entry);
    } else if (method === "Network.responseReceived") {
      const entry = byId.get(`${sid}:${params.requestId}`);
      if (entry) {
        entry.status = params.response.status;
        if (params.response.fromDiskCache) {
          entry.cache = "disk";
        }
      }
    } else if (method === "Network.requestServedFromCache") {
      const entry = byId.get(`${sid}:${params.requestId}`);
      if (entry) {
        entry.cache = "memory";
      }
    } else if (method === "Network.loadingFinished") {
      const entry = byId.get(`${sid}:${params.requestId}`);
      if (entry) {
        entry.encoded = params.encodedDataLength;
      }
    } else if (method === "Network.loadingFailed") {
      const entry = byId.get(`${sid}:${params.requestId}`);
      if (entry) {
        entry.failed = params.canceled ? "canceled" : params.errorText || "failed";
      }
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
  const close = async () => {
    try {
      await page.close();
    } catch (_error) {
      // The browser may already be gone.
    }
    conn.close();
    chrome.kill("SIGTERM");
    for (let i = 0; i < 30 && chrome.exitCode === null && chrome.signalCode === null; i++) {
      await sleep(100);
    }
    if (chrome.exitCode === null && chrome.signalCode === null) {
      chrome.kill("SIGKILL");
    }
    fs.rmSync(profileDir, { recursive: true, force: true, maxRetries: 5 });
  };
  return {
    conn,
    page,
    close,
    chrome,
    version,
    net,
    exceptions,
    consoleErrors,
    viewport: { width, height },
  };
}

const round1 = (v) => (v === null || v === undefined ? null : Math.round(v * 10) / 10);

/** Region movement from the arm-time snapshot and the per-frame change log. */
function regionMovement(snapshot, log, t0, regions) {
  const out = {};
  let movementPx = 0;
  const movementByGroup = {};
  // Frames in which some region of the group moved: an animated reveal moves rows over
  // several frames, an unanimated one in one.
  const stepsByGroup = {};
  for (const [name, spec] of Object.entries(regions)) {
    const group = spec.group ?? "page";
    if (group !== "page") {
      movementByGroup[group] ??= 0;
      stepsByGroup[group] ??= new Set();
    }
    const seq = [snapshot[name] ?? null];
    const times = [null];
    for (const [t, n, b] of log) {
      if (n === name && t >= t0 - 1) {
        seq.push(b);
        times.push(t);
      } else if (n === name) {
        seq[0] = b;
      }
    }
    let steps = 0;
    let appeared = 0;
    let removed = 0;
    let replaced = 0;
    const max = [0, 0, 0, 0];
    for (let i = 1; i < seq.length; i++) {
      const a = seq[i - 1];
      const b = seq[i];
      if (a === null && b !== null) {
        appeared += 1;
        continue;
      }
      if (a !== null && b === null) {
        removed += 1;
        continue;
      }
      if (a === null || b === null) {
        continue;
      }
      if (spec.sameNode && a[4] !== b[4]) {
        replaced += 1;
        continue;
      }
      steps += 1;
      if (
        group !== "page" &&
        spec.track.some((c) => b["xywh".indexOf(c)] !== a["xywh".indexOf(c)])
      ) {
        stepsByGroup[group].add(times[i]);
      }
      for (let k = 0; k < 4; k++) {
        const d = b[k] - a[k];
        if (Math.abs(d) > Math.abs(max[k])) {
          max[k] = d;
        }
      }
    }
    const first = seq[0];
    const last = seq[seq.length - 1];
    if (first === null && last === null && appeared === 0) {
      continue;
    }
    const tracked = { x: 0, y: 1, w: 2, h: 3 };
    for (const c of spec.track) {
      if (group === "page") {
        movementPx = Math.max(movementPx, Math.abs(max[tracked[c]]));
      } else {
        movementByGroup[group] = Math.max(movementByGroup[group], Math.abs(max[tracked[c]]));
      }
    }
    out[name] = {
      present: [first !== null, last !== null],
      dx: max[0],
      dy: max[1],
      dw: max[2],
      dh: max[3],
      steps,
      appeared,
      removed,
      ...(spec.sameNode ? { replaced } : {}),
      net: first && last ? [0, 1, 2, 3].map((k) => last[k] - first[k]) : null,
    };
  }
  const movementStepsByGroup = Object.fromEntries(
    Object.entries(stepsByGroup).map(([g, set]) => [g, set.size]),
  );
  return { regions: out, movementPx, movementByGroup, movementStepsByGroup };
}

/** What a watched list did after its first rows painted. */
function listChanges(log, origin) {
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

/** Driver bound to one page: evaluation, trusted input, and the measure step. */
export function driver(browser) {
  const { page } = browser;
  async function evaluate(expression) {
    const r = await page.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (r.exceptionDetails) {
      throw new Error(
        `evaluate failed: ${expression.slice(0, 160)}: ${JSON.stringify(r.exceptionDetails).slice(0, 400)}`,
      );
    }
    return r.result.value;
  }
  async function waitFor(expression, timeoutMs = 20000, pollMs = 20) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (await evaluate(expression)) {
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
  async function resolveTarget(selector) {
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
  // A held key: `count` keyDowns flagged autoRepeat, `intervalMs` apart, then one keyUp.
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
        autoRepeat: true,
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
   *   with useful content. spec.converged: in-page `() => string` source, "" when the
   *   whole application agrees on the subject after settling, else what disagrees.
   * spec.input: { kind: "click" | "hover-click" | "key" | "key-repeat" | "type" |
   *   "history" | "navigate" | "reload", selector?, hoverMs?, key?, count?, intervalMs?,
   *   text?, delta?, url? }.
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
        // Runs after the recorder's own document-start script, so the recorder exists.
        source: `(() => { const R = window.__tr; R.readyFn = (${spec.ready}); R.armedAt = 0; ${armExtras} })();`,
      });
    } else {
      await evaluate(`(() => {
        const R = window.__tr;
        const pane = document.getElementById("preview-pane");
        for (const c of pane ? pane.children : []) { c.dataset.trMark = "1"; }
        R.frames.length = 0; R.regionLog.length = 0; R.muts.length = 0; R.shifts.length = 0;
        R.longtasks.length = 0; R.loafs.length = 0; R.events.length = 0; R.inputs.length = 0;
        R.alerts.length = 0; R.hiddenFrames = 0; R.frameCount = 0;
        R.snapshot = R.snapshotRegions();
        R.state0 = R.state();
        R.spanMark = window.metabrowser?.perf?.snapshot ? window.metabrowser.perf.snapshot().measure_samples_seen : null;
        R.readyAt = null; R.readyNext = null; R.readyFn = (${spec.ready});
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
    const startEvent = {
      click: "pointerdown",
      "hover-click": "pointerdown",
      key: "keydown",
      "key-repeat": "keydown",
      type: "keydown",
    }[input.kind];
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
        shifts: R.shifts, longtasks: R.longtasks, loafs: R.loafs, events: R.events,
        inputs: R.inputs, alerts: R.alerts, hiddenFrames: R.hiddenFrames,
        visibilityChanges: R.visibilityChanges, readyAt: R.readyAt, readyNext: R.readyNext,
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

    let t0;
    if (landing) {
      t0 = 0;
    } else {
      const wanted = startEvent ?? "popstate";
      const first = raw.inputs.find(
        (i) => i[0] === wanted || (wanted === "pointerdown" && i[0] === "mousedown"),
      );
      t0 = first ? first[1] : null;
    }
    const refusals = [];
    if (t0 === null) {
      refusals.push(["input_observed", `no ${startEvent ?? "popstate"} event reached the page`]);
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
    const windowFrames = raw.frames.filter((f) => f[0] >= origin);
    const gesture = raw.inputs.filter((i) => i[0] === (startEvent ?? "popstate") && i[1] >= origin);
    const inputSpanMs = gesture.length > 1 ? round1(gesture[gesture.length - 1][1] - origin) : 0;

    // Milestones are waited for after the window above has closed, so every other field
    // keeps the window it had before milestones existed.
    let milestones;
    let extraWaitMs = 0;
    if (spec.milestones) {
      const names = Object.keys(spec.milestones);
      const w0 = Date.now();
      await waitFor(
        `(() => { const m = window.__tr.milestones; return ${JSON.stringify(names)}.every((n) => m[n] && m[n][1] !== null); })()`,
        spec.milestoneTimeoutMs ?? 10000,
        50,
      );
      extraWaitMs = Date.now() - w0;
      const got = await evaluate("window.__tr.milestones");
      await evaluate("window.__tr.milestoneFns = null");
      milestones = Object.fromEntries(
        names.map((n) => [n, got[n] && got[n][1] !== null ? round1(got[n][1] - origin) : null]),
      );
    }
    // A body the DevTools event left out is asked for once the request has been sent.
    for (const r of net) {
      if (r.method === "POST" && r.postBytes === null) {
        try {
          const session = r.sid === page.sessionId ? page : browser.conn.sessions.get(r.sid);
          const body = await session.send("Network.getRequestPostData", { requestId: r.id });
          r.postBytes = body.base64Encoded
            ? Buffer.from(body.postData, "base64").length
            : Buffer.byteLength(body.postData, "utf8");
        } catch (_error) {
          // The body is no longer held; the request stays counted with unknown bytes.
        }
      }
    }
    if (windowFrames.length < 2) {
      refusals.push(["raf", `${windowFrames.length} animation frames after input`]);
    }
    if (exceptions.length) {
      refusals.push(["page_exceptions", exceptions[0].text]);
    }
    if (raw.alerts.length) {
      refusals.push(["rendered_errors", `${raw.alerts[0][1]}: ${raw.alerts[0][2]}`]);
    }

    // Frame states: an uncredited frame shows what the previous credited frame showed.
    // A landing starts from nothing on screen; a transition from the state at arm time.
    let lastCode = landing ? "" : raw.state0;
    for (const f of raw.frames) {
      if (f[0] < origin && f[1] !== null) {
        lastCode = f[1];
      }
    }
    const filled = windowFrames.map((f) => {
      if (f[1] !== null) {
        lastCode = f[1];
      }
      return [f[0], f[1] === null ? lastCode : f[1], f[1] === null];
    });
    const upto = raw.readyAt === null ? filled : filled.filter((f) => f[0] <= raw.readyAt);
    const rel = (t) => round1(t - origin);
    const states = [];
    for (const f of filled) {
      if (!states.length || states[states.length - 1][1] !== f[1]) {
        states.push([rel(f[0]), f[1]]);
      }
    }
    const muts = raw.muts.filter((m) => m[0] >= origin);
    const shifts = raw.shifts.filter((s) => s.t >= (landing ? 0 : raw.armedAt));
    const end = raw.readyNext === null ? Number.POSITIVE_INFINITY : raw.readyNext + settleMs;
    const longtasks = raw.longtasks.filter((x) => x[0] + x[1] >= origin && x[0] <= end);
    const loafs = raw.loafs.filter((x) => x[0] + x[1] >= origin && x[0] <= end);
    const events = raw.events.filter((x) => x[0] >= origin - 1);
    const movement = regionMovement(raw.snapshot, raw.regionLog, origin, REGIONS);
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
    // Requests for the selected subject, per route pattern: a cold selection issues each
    // route once, so every further match is a duplicate.
    const patterns = [spec.subjectRequest ?? []].flat();
    let subjectRequests = 0;
    let subjectDuplicates = 0;
    for (const pattern of patterns) {
      const re = new RegExp(pattern);
      const n = net.filter((r) => re.test(r.url.replace(/^https?:\/\/[^/]+/, ""))).length;
      subjectRequests += n;
      subjectDuplicates += Math.max(0, n - 1);
    }
    return {
      id: spec.id,
      journey: spec.journey,
      subject: spec.subject,
      input: input.kind,
      ok: refusals.length === 0,
      refusals,
      readyMs: raw.readyAt === null ? null : rel(raw.readyAt),
      paintedReadyMs: raw.readyNext === null ? null : rel(raw.readyNext),
      framesToReady: upto.length,
      blankFrames: upto.filter((f) => !f[1].includes("U")).length,
      placeholderVisibleFrames: upto.filter((f) => f[1].includes("P")).length,
      navPlaceholderVisibleFrames: upto.filter((f) => f[1].includes("N")).length,
      uncreditedFrames: upto.filter((f) => f[2]).length,
      frameStates: states.slice(0, 24),
      movementPx: movement.movementPx,
      movementByGroup: movement.movementByGroup,
      movementStepsByGroup: movement.movementStepsByGroup,
      regions: movement.regions,
      inputSpanMs,
      readyAfterLastInputMs:
        raw.readyNext === null ? null : round1(rel(raw.readyNext) - inputSpanMs),
      milestones,
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
        subject: subjectRequests,
        subjectDuplicates,
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

const round4 = (v) => Math.round(v * 10000) / 10000;
