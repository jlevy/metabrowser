// The event log's four views drawn: Timeline, Latency, By kind, and Errors.
//
// Each reads one route of the event-log plugin (event_log_views.py) for the file it shows
// and draws what the server answered; nothing here counts, sorts, or nests. What the page
// owns is which filters are chosen, which rows are open, and which pages of the timeline
// have been read (event-log-model.js), so the same module runs browserless in
// tests/dom/event-log-view-session.js against an SDK stand-in.

import {
  axisBar,
  beginPage,
  bucketLabels,
  chooseMinimum,
  createShared,
  createTimeline,
  emptyFilters,
  failPage,
  filterParams,
  filtersActive,
  flatten,
  formatDuration,
  formatOffset,
  holds,
  lengthShare,
  minimumChoices,
  outcomeLabel,
  outcomeTone,
  pageParams,
  takePage,
  toggleChoice,
  toggleRow,
  wantsPage,
} from "./event-log-model.js";

/** @typedef {import("./event-log-model.js").EventRow} EventRow */
/** @typedef {import("./event-log-model.js").Filters} Filters */
/** @typedef {import("./event-log-model.js").TimelineState} TimelineState */
/** @typedef {import("./event-log-model.js").TimelineLine} TimelineLine */
/** @typedef {import("./event-log-model.js").Order} Order */
/** @typedef {import("./event-log-model.js").Shared} Shared */
/** @typedef {"timeline" | "latency" | "kinds" | "errors"} ViewName */

// The least width a span's bar is drawn, as a fraction of the log's whole time axis: a
// request of a few milliseconds in a log of minutes is a hairline, and a bar that is not
// drawn at all would say nothing happened.
const MIN_BAR = 0.003;
const FILTER_KIND = "event-log-kind";
const FILTER_OUTCOME = "event-log-outcome";
const FILTER_MINIMUM = "event-log-minimum";
const FILTER_ORDER = "event-log-order";
/**
 * @typedef {Object} Mount One view mounted in one container.
 * @property {AbortController} abort
 * @property {number} generation Bumped by each render, so an answer to an old one is dropped.
 * @property {() => void} [stop] Ends what the mount subscribed to.
 */

/** @type {WeakMap<HTMLElement, Mount>} */
const mounts = new WeakMap();

/**
 * What the views of one file share, held while any is mounted: the filters, so a choice
 * made in one view is the next view's, and the request to show a row in the Timeline.
 *
 * @type {Map<string, {shared: Shared, users: number}>}
 */
const sharing = new Map();

/** @param {string} path */
function acquireShared(path) {
  const held = sharing.get(path) ?? { shared: createShared(), users: 0 };
  held.users += 1;
  sharing.set(path, held);
  return held.shared;
}

/** @param {string} path */
function releaseShared(path) {
  const held = sharing.get(path);
  if (held === undefined) {
    return;
  }
  held.users -= 1;
  if (held.users <= 0) {
    sharing.delete(path);
  }
}

/** @param {unknown} value @returns {Record<string, unknown>} */
const record = (value) =>
  value !== null && typeof value === "object" ? /** @type {Record<string, unknown>} */ (value) : {};
/** @param {unknown} value @returns {unknown[]} */
const list = (value) => (Array.isArray(value) ? /** @type {unknown[]} */ (value) : []);
/** @param {unknown} value */
const text = (value) => (typeof value === "string" ? value : "");
/** @param {unknown} value */
const count = (value) => (typeof value === "number" && Number.isFinite(value) ? value : 0);
/** @param {unknown} value @returns {number | null} */
const figure = (value) => (typeof value === "number" && Number.isFinite(value) ? value : null);

/**
 * An element with its attributes and children, the factory every plugin builds nodes with.
 *
 * @param {string} tag
 * @param {Record<string, string>} attributes `class` sets the class name.
 * @param {Array<Node | string>} [children]
 */
function h(tag, attributes, children = []) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    if (name === "class") {
      node.className = value;
    } else {
      node.setAttribute(name, value);
    }
  }
  node.append(...children);
  return node;
}

/**
 * @param {string} tag
 * @param {string} [className]
 * @param {Array<Node | string>} [children]
 */
function make(tag, className = "", children = []) {
  return h(tag, className ? { class: className } : {}, children);
}

/**
 * A box that says something about what the view shows (docs/design-system.md, "Notices").
 *
 * @param {string} message
 * @param {"warning" | "error" | "neutral"} [severity] Neutral is a notice with no severity.
 */
function notice(message, severity = "warning") {
  const box = make("div", "notice event-log-notice", [message]);
  if (severity !== "neutral") {
    box.setAttribute("data-severity", severity);
  }
  box.setAttribute("role", severity === "error" ? "alert" : "status");
  return box;
}

/**
 * A heading's tally, as the shell writes one (docs/design-system.md, "Heading Tallies"):
 * after the name, a dot, then the figure.
 *
 * @param {string} figureText
 */
function tally(figureText) {
  return h("span", { class: "heading-tally" }, [
    " ",
    h("span", { class: "heading-tally-dot", "aria-hidden": "true" }, ["·"]),
    " ",
    h("span", { class: "heading-tally-figure" }, [figureText]),
  ]);
}

/**
 * A section's heading: its name, and how many it holds.
 *
 * @param {string} name
 * @param {string} [figureText]
 */
function heading(name, figureText) {
  const parts = [make("span", "", [name])];
  if (figureText !== undefined) {
    parts.push(tally(figureText));
  }
  return make("h3", "section-heading", parts);
}

/**
 * The summary strip every view opens with: what the file holds.
 *
 * @param {Record<string, unknown>} log
 * @param {MetabrowserPublicSdk} mb
 */
function summaryStrip(log, mb) {
  const strip = make("div", "event-log-summary");
  /** @param {string} label @param {string} value */
  const stat = (label, value) =>
    strip.append(
      make("div", "event-log-stat", [
        make("span", "event-log-stat-label", [label]),
        make("span", "event-log-stat-value", [value]),
      ]),
    );
  stat("Records", mb.formatInteger(count(log.records)));
  stat("Spans", mb.formatInteger(count(log.spans)));
  const unfinished = count(log.unfinished);
  if (unfinished > 0) {
    // A span with no end here may have ended in the segment that follows (`continues`).
    stat(log.continues === true ? "No end here" : "Unfinished", mb.formatInteger(unfinished));
  }
  stat("Covers", formatDuration(figure(log.extent_ms)));
  const started = text(log.started);
  if (started) {
    stat("From", `${started.slice(0, 19).replace("T", " ")} UTC`);
  }
  return strip;
}

/**
 * The line that says the file held lines it did not read.
 *
 * @param {Record<string, unknown>} log
 * @param {MetabrowserPublicSdk} mb
 */
function skippedNotice(log, mb) {
  const skipped = count(log.skipped);
  if (skipped === 0) {
    return null;
  }
  // Why each was skipped is the route's (`skipped`), for an agent.
  return notice(
    `${mb.formatInteger(skipped)} ${skipped === 1 ? "line was" : "lines were"} not read. ` +
      "Raw JSON shows every line.",
  );
}

// ── Filters ─────────────────────────────────────────────────────────────────────────

/**
 * Draw the filter bar and answer its choices. A chip is a choice among the words the
 * server names (the answer's `kinds` and `outcomes`), and the least time is one of the
 * edges of its distribution (`edges_ms`). Every group wraps: the bar is as narrow as the
 * pane, and a joined group wider than it would clip the choices past its edge.
 *
 * @param {HTMLElement} host
 * @param {MetabrowserPublicSdk} mb
 * @param {Filters} filters
 * @param {{kinds: string[], outcomes: string[], edges: number[]}} vocabulary
 * @param {Order | null} order The roots' order, for the Timeline's bar; null for the others.
 * @returns {void}
 */
function drawFilters(host, mb, filters, vocabulary, order) {
  const controls = mb.filterControls;
  if (!controls) {
    return;
  }
  const restore = controls.keepFocus(host);
  host.innerHTML =
    controls.groupHtml({
      key: FILTER_KIND,
      select: "many",
      layout: "wrap",
      label: "Kind",
      options: vocabulary.kinds.map((value) => ({ value, label: value })),
      value: filters.kind,
    }) +
    controls.groupHtml({
      key: FILTER_OUTCOME,
      select: "many",
      layout: "wrap",
      label: "Outcome",
      options: vocabulary.outcomes.map((value) => ({ value, label: value.replace(/_/g, " ") })),
      value: filters.outcome,
    }) +
    controls.groupHtml({
      key: FILTER_MINIMUM,
      select: "one",
      layout: "wrap",
      label: "At least",
      options: minimumChoices(vocabulary.edges).map((ms) => ({
        value: ms === null ? "" : String(ms),
        label: ms === null ? "Any" : formatDuration(ms),
      })),
      value: filters.minMs === null ? "" : String(filters.minMs),
    }) +
    (order === null
      ? ""
      : controls.groupHtml({
          key: FILTER_ORDER,
          select: "one",
          layout: "wrap",
          label: "Order",
          options: [
            { value: "oldest", label: "Oldest first" },
            { value: "newest", label: "Newest first" },
          ],
          value: order,
        }));
  restore();
}

/**
 * The filters a choice in the bar makes.
 *
 * @param {Filters} filters
 * @param {string} key
 * @param {string} value
 * @returns {Filters | null} Null when the key is not one of the bar's.
 */
export function chosen(filters, key, value) {
  if (key === FILTER_KIND) {
    return toggleChoice(filters, "kind", value);
  }
  if (key === FILTER_OUTCOME) {
    return toggleChoice(filters, "outcome", value);
  }
  if (key === FILTER_MINIMUM) {
    return chooseMinimum(filters, value === "" ? null : Number(value));
  }
  return null;
}

// ── Rows ────────────────────────────────────────────────────────────────────────────

/**
 * The detail a row opens to: what the log says of it, then its attributes as written.
 *
 * @param {EventRow} row
 */
function detail(row) {
  const facts = make("dl", "event-log-facts");
  /** @param {string} label @param {string} value */
  const fact = (label, value) => {
    if (value) {
      facts.append(make("dt", "", [label]), make("dd", "event-log-fact-value", [value]));
    }
  };
  fact(row.span === null ? "Record" : "Span", row.key);
  fact("Client", row.client ?? "");
  fact("Began", formatOffset(row.start_ms));
  fact("Took", formatDuration(row.dur_ms));
  if (row.state === "unfinished") {
    fact("Open records", String(row.opens ?? 0));
  }
  if (row.orphan === true) {
    fact("Started", "before this file: the span above it is in an earlier segment");
  }
  const body = make("div", "event-log-detail", [facts]);
  const attrs = JSON.stringify(row.attrs, null, 2);
  if (attrs !== "{}") {
    body.append(make("pre", "event-log-attrs", [attrs]));
  }
  return body;
}

/**
 * The button that takes a row seen out of its place to its place in the Timeline.
 *
 * @param {string} key The row's key, which the Timeline finds it by.
 * @param {(key: string) => void} onShow
 */
function showButton(key, onShow) {
  const button = make("button", "btn event-log-show", ["Show in timeline"]);
  button.setAttribute("type", "button");
  button.addEventListener("click", () => onShow(key));
  return button;
}

/**
 * The line under a row seen out of its place: the spans above it, outermost first, and the
 * way to its place in the Timeline.
 *
 * @param {EventRow} row
 * @param {((key: string) => void) | undefined} onShow
 */
function contextLine(row, onShow) {
  const above = row.path ?? [];
  if (above.length === 0 && onShow === undefined) {
    return null;
  }
  return make("div", "event-log-path", [
    ...(above.length > 0 ? [`in ${above.map((span) => span.name).join(" > ")}`] : []),
    ...(onShow === undefined ? [] : [showButton(row.key, onShow)]),
  ]);
}

/**
 * Focus a row's head, which a repaint made a new node: the key that was on it is the
 * identity that was kept, so a person who opened a row by keyboard is still on it.
 *
 * @param {HTMLElement | undefined} node A row's node, as `rowElement` builds it.
 */
function focusHead(node) {
  /** @type {HTMLElement | undefined} */ (node?.childNodes[0])?.focus();
}

/**
 * Whether a row's head, or the node, has the keyboard.
 *
 * @param {Node | undefined} node
 */
function hasFocus(node) {
  return node !== undefined && globalThis.document?.activeElement === node;
}

/**
 * One row: a button that opens its detail, with the span's kind, name, bar, and ending.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {EventRow} row
 * @param {{
 *   depth: number,
 *   open: boolean,
 *   bar: {left: number, width: number},
 *   showPath: boolean,
 *   onToggle: (row: EventRow) => void,
 *   onShow?: (key: string) => void,
 * }} options
 */
function rowElement(mb, row, options) {
  const tone = outcomeTone(row);
  const head = make("button", "disclosure-toggle event-log-row-head");
  head.setAttribute("type", "button");
  head.setAttribute("aria-expanded", options.open ? "true" : "false");
  const chevron = make("span", "event-log-chevron");
  chevron.innerHTML = mb.icons.toggle;
  chevron.setAttribute("aria-hidden", "true");
  const kind = make("span", "file-header-badge event-log-kind", [row.kind]);
  const name = make("span", "event-log-name", [row.name]);
  const track = make("span", "event-log-bar");
  const fill = make("span", "event-log-bar-fill");
  fill.style.setProperty("--event-log-bar-left", `${(options.bar.left * 100).toFixed(2)}%`);
  fill.style.setProperty("--event-log-bar-width", `${(options.bar.width * 100).toFixed(2)}%`);
  track.append(fill);
  const when = make("span", "event-log-when", [formatOffset(row.start_ms)]);
  const elapsed = make("span", "event-log-dur", [formatDuration(row.elapsed_ms)]);
  const outcome = make("span", "event-log-outcome", [outcomeLabel(row)]);
  head.append(chevron, kind, name, track, when, elapsed, outcome);
  // The parts are columns, which a screen reader reads as one run of words: say which is which.
  head.setAttribute(
    "aria-label",
    [
      `${row.kind} ${row.name}`,
      `began ${formatOffset(row.start_ms)}`,
      row.elapsed_ms === null ? "" : `took ${formatDuration(row.elapsed_ms)}`,
      outcomeLabel(row),
    ]
      .filter(Boolean)
      .join(", "),
  );
  head.addEventListener("click", () => options.onToggle(row));
  const shown = make("div", "event-log-row");
  shown.setAttribute("data-tone", tone);
  shown.setAttribute("data-type", row.type);
  shown.setAttribute("data-key", row.key);
  shown.style.setProperty("--event-log-depth", String(options.depth));
  if (row.matched === false) {
    shown.setAttribute("data-context", "");
  }
  shown.append(head);
  if (options.showPath) {
    const above = contextLine(row, options.onShow);
    if (above) {
      shown.append(above);
    }
  }
  if (options.open) {
    shown.append(detail(row));
  }
  return shown;
}

// ── The mount each view shares ─────────────────────────────────────────────────────

/**
 * @typedef {Object} Frame The parts of a view, which each fills.
 * @property {HTMLElement} summary
 * @property {HTMLElement} filters
 * @property {HTMLElement} body
 */

/**
 * @param {HTMLElement} container
 * @param {boolean} filterable
 * @returns {Frame}
 */
function frame(container, filterable) {
  const summary = make("div", "event-log-head");
  const filters = make("div", "event-log-filters");
  const body = make("div", "event-log-body");
  container.replaceChildren(summary, ...(filterable ? [filters] : []), body);
  return { summary, filters, body };
}

/**
 * @param {Frame} parts
 * @param {unknown} error
 */
function showFailure(parts, error) {
  // The route's `error` is its reader sentence; its `detail`, and an exception's own text,
  // are the console's (docs/design-system-messages.md, "Where the Detail Goes").
  const answer = /** @type {{payload?: {error?: unknown}}} */ (error)?.payload;
  const said =
    typeof answer?.error === "string" && answer.error
      ? answer.error
      : "Could not read the event log.";
  console.error("metabrowser event log: the view could not be read", error);
  parts.summary.replaceChildren();
  parts.body.replaceChildren(notice(said, "error"));
}

/**
 * Mount a view: the frame at once, then the answer to the route it reads.
 *
 * @param {HTMLElement} container
 * @param {MetabrowserPublicRenderContext} ctx
 * @param {MetabrowserPublicSdk} mb
 * @param {ViewName} view
 */
export function mountEventLogView(container, ctx, mb, view) {
  disposeEventLogView(container);
  /** @type {Mount} */
  const mount = { abort: new AbortController(), generation: 0 };
  mounts.set(container, mount);
  const path = ctx.path ?? "";
  const shared = acquireShared(path);
  const filterable = view !== "errors";
  const parts = frame(container, filterable);
  // The views of one file choose their filters together: this object is theirs, and
  // `applied` is the choice this view last drew, so a view shown again after another
  // changed it knows it is stale.
  const filters = shared.filters;
  let applied = shared.version;
  /** @type {{kinds: string[], outcomes: string[], edges: number[]}} */
  let vocabulary = { kinds: [], outcomes: [], edges: [] };
  /** @type {Order} */
  let order = "oldest";
  /** @type {TimelineState} */
  let timeline = createTimeline(order);
  /** @type {Record<string, unknown>} */
  let head = {};
  /** The most rows the server answers with, which a longer reach is made in pages of. */
  let maxLimit = 1000;
  /** @type {Set<string>} */
  const opened = new Set();
  /**
   * The rows the Latency and Errors views drew, by key: a repaint makes each a new node,
   * and a person on one by keyboard is put back on the new node of the same row.
   *
   * @type {Map<string, HTMLElement>}
   */
  let rowNodes = new Map();
  /** @type {Promise<void>} */
  let firstPage = Promise.resolve();
  /** @type {HTMLElement | null} */
  let revealNote = null;

  /**
   * Take a row seen here to its place in the Timeline: the view opens, the log is asked
   * where the row is, and the Timeline opens each span above it, reads the pages that
   * hold them, and focuses it.
   *
   * @param {string} key
   */
  const showInTimeline = async (key) => {
    shared.focus = key;
    try {
      await mb.navigation.open({ path }, { viewId: "timeline" });
    } catch {
      // The shell says why a view could not open; the request is dropped with it.
      shared.focus = null;
      return;
    }
    shared.reveal?.();
  };

  /** @param {string} route @param {Record<string, string>} extra */
  const read = (route, extra) =>
    mb.fetchPluginData("event-log", route, { path, ...extra }, { signal: mount.abort.signal });

  const current = () => mounts.get(container) === mount;

  /** Draw the filter bar from what the last answer said the words are. */
  const paintFilters = () => {
    if (filterable && vocabulary.kinds.length > 0) {
      drawFilters(parts.filters, mb, filters, vocabulary, view === "timeline" ? order : null);
    }
  };

  /**
   * @param {Record<string, unknown>} log
   */
  const takeHead = (log) => {
    head = log;
    vocabulary = {
      kinds: list(log.kinds).map(text),
      outcomes: list(log.outcomes).map(text),
      edges: list(log.edges_ms).map(count),
    };
    parts.summary.replaceChildren(summaryStrip(log, mb));
    const skipped = skippedNotice(log, mb);
    if (skipped) {
      parts.summary.append(skipped);
    }
  };

  const settled = () => {
    parts.body.className = "event-log-body";
    parts.body.replaceChildren();
  };

  /** What shows while a read is out: nothing, with a note for assistive technology. */
  const loading = () => {
    parts.body.className = "event-log-body preview-empty mb-delayed-loading";
    parts.body.replaceChildren(make("span", "sr-only", ["Reading the event log…"]));
  };

  // ── Timeline ──────────────────────────────────────────────────────────────────

  /**
   * What each line drawn is, by the line's identity, so that a row already drawn as it
   * would be drawn again is kept, and only the nodes that changed are touched. Measured in
   * headless Chrome on 2026-11-19 on a 2 MiB segment (about 6,000 roots) at a load average
   * near 20: reading the next page of 200 rows took 53 to 83 ms from the click to the next
   * frame at every size up to 5,000 rows held, where drawing every row again each time
   * took 82 ms at 400 rows, 181 at 1,000, 364 at 2,000, and 793 at 5,000, a cost in the
   * rows held and not in the rows added. A page of 200 rows is 2,771 nodes.
   *
   * @type {Map<string, {signature: string, node: HTMLElement}>}
   */
  let drawn = new Map();

  /**
   * @param {TimelineLine} line
   * @returns {[string, string]} The line's identity and what it looks like.
   */
  const lineIdentity = (line) => {
    if (line.kind === "row") {
      const row = line.row;
      return [
        `row:${row.key}`,
        `${line.depth}|${line.open}|${row.matched}|${row.children}|${row.below}`,
      ];
    }
    if (line.kind === "more") {
      return [`more:${line.parent ?? ""}`, `${line.depth}|${line.remaining}|${line.loading}`];
    }
    return [`error:${line.parent ?? ""}`, `${line.depth}|${line.message}`];
  };

  /**
   * @param {TimelineLine} line
   * @param {number} extent
   */
  const buildLine = (line, extent) => {
    if (line.kind === "row") {
      return rowElement(mb, line.row, {
        depth: line.depth,
        open: line.open,
        bar: axisBar(line.row, extent, MIN_BAR),
        showPath: false,
        onToggle: toggleTimelineRow,
      });
    }
    if (line.kind === "more") {
      const more = make("button", "btn event-log-more", [
        line.loading ? "Reading…" : `Show more (${mb.formatInteger(line.remaining)} left)`,
      ]);
      more.setAttribute("type", "button");
      more.style.setProperty("--event-log-depth", String(line.depth));
      if (line.loading) {
        more.setAttribute("disabled", "");
      }
      more.addEventListener(
        "click",
        () => void loadLevel(line.parent, { keepFocus: hasFocus(more) }),
      );
      return more;
    }
    const failed = notice(line.message, "error");
    failed.style.setProperty("--event-log-depth", String(line.depth));
    return failed;
  };

  const paintTimeline = () => {
    const extent = figure(head.extent_ms) ?? 0;
    const lines = flatten(timeline);
    if (lines.length === 0 && wantsPage(timeline, null) === false) {
      drawn = new Map();
      parts.body.replaceChildren(
        notice(
          filtersActive(filters)
            ? "Nothing in this log matches these filters."
            : "This log holds no records.",
        ),
      );
      return;
    }
    /** @type {typeof drawn} */
    const now = new Map();
    for (const line of lines) {
      const [identity, signature] = lineIdentity(line);
      const held = drawn.get(identity);
      now.set(identity, {
        signature,
        node: held?.signature === signature ? held.node : buildLine(line, extent),
      });
    }
    // Only what changed is touched: the nodes both lists share at their start and their
    // end stay where they are, and the nodes between are swapped. Reading a page adds rows
    // after the held ones, and opening a row puts its detail and children after it.
    const before = [...drawn.values()].map((entry) => entry.node);
    const after = [...now.values()].map((entry) => entry.node);
    let start = 0;
    while (start < before.length && start < after.length && before[start] === after[start]) {
      start += 1;
    }
    let endBefore = before.length;
    let endAfter = after.length;
    while (endBefore > start && endAfter > start && before[endBefore - 1] === after[endAfter - 1]) {
      endBefore -= 1;
      endAfter -= 1;
    }
    for (const node of before.slice(start, endBefore)) {
      node.remove();
    }
    const anchor = before[endBefore] ?? null;
    for (const node of after.slice(start, endAfter)) {
      parts.body.insertBefore(node, anchor);
    }
    drawn = now;
  };

  /**
   * Read the next page of a level, and draw it.
   *
   * @param {string | null} parent
   * @param {{keepFocus?: boolean, through?: number}} [reach] `keepFocus`: the keyboard was on
   *   the control that asked, which the page replaces, so it goes to the first row the page
   *   added (or the control's replacement). `through`: the place of a row the level has to
   *   hold, so the page is as long as that takes, to the server's most.
   */
  const loadLevel = async (parent, reach = {}) => {
    if (!wantsPage(timeline, parent)) {
      return;
    }
    const generation = mount.generation;
    const state = timeline;
    const params = pageParams(state, parent, filters, { through: reach.through, maxLimit });
    const held = state.levels.get(parent ?? "")?.rows.length ?? 0;
    beginPage(state, parent);
    if (head.records !== undefined) {
      paintTimeline();
    }
    try {
      const answer = await read("timeline", params);
      if (!current() || generation !== mount.generation) {
        return;
      }
      if (head.records === undefined) {
        settled();
        takeHead(record(answer.log));
        paintFilters();
      }
      maxLimit = count(answer.max_limit) || maxLimit;
      takePage(state, parent, {
        rows: /** @type {EventRow[]} */ (list(answer.rows)),
        total: count(answer.total),
        offset: count(answer.offset),
        limit: count(answer.limit),
        has_more: answer.has_more === true,
      });
    } catch (error) {
      if (!current() || generation !== mount.generation || mount.abort.signal.aborted) {
        return;
      }
      if (head.records === undefined) {
        showFailure(parts, error);
        return;
      }
      failPage(
        state,
        parent,
        text(record(record(error).payload).error) || "The page could not be read.",
      );
    }
    paintTimeline();
    if (reach.keepFocus === true) {
      const added = state.levels.get(parent ?? "")?.rows[held];
      const next =
        (added === undefined ? undefined : drawn.get(`row:${added.key}`)?.node) ??
        drawn.get(`more:${parent ?? ""}`)?.node ??
        drawn.get(`error:${parent ?? ""}`)?.node;
      if (added === undefined) {
        next?.focus();
      } else {
        focusHead(next);
      }
    }
  };

  /** @param {EventRow} row */
  const toggleTimelineRow = (row) => {
    const kept = hasFocus(drawn.get(`row:${row.key}`)?.node.childNodes[0]);
    const open = toggleRow(timeline, row.key);
    if (open && (row.children ?? 0) > 0 && wantsPage(timeline, row.key)) {
      void loadLevel(row.key);
    }
    paintTimeline();
    if (kept) {
      focusHead(drawn.get(`row:${row.key}`)?.node);
    }
  };

  /**
   * Read pages of a level until it holds the row at *index*.
   *
   * @param {string | null} parent
   * @param {number} index
   * @param {number} generation The reading this is for; a newer one ends it.
   */
  const holdThrough = async (parent, index, generation) => {
    while (!holds(timeline, parent, index)) {
      const before = timeline.levels.get(parent ?? "")?.rows.length ?? 0;
      if (!wantsPage(timeline, parent)) {
        return false;
      }
      await loadLevel(parent, { through: index });
      const after = timeline.levels.get(parent ?? "")?.rows.length ?? 0;
      if (!current() || generation !== mount.generation || after <= before) {
        return holds(timeline, parent, index);
      }
    }
    return true;
  };

  /** Wait until this view is the one shown: a hidden one has nothing to scroll or focus. */
  const whenShown = () =>
    new Promise((resolve) => {
      if (!mb.viewState || mb.viewState.isActive(container)) {
        resolve(undefined);
        return;
      }
      const done = () => {
        off();
        resolve(undefined);
      };
      const off = mb.viewState.subscribeActive(container, (active) => active && done());
      mount.abort.signal.addEventListener("abort", done, { once: true });
    });

  /** @param {string} message */
  const sayWhyNotShown = (message) => {
    revealNote ??= make("div", "event-log-reveal-note");
    revealNote.replaceChildren(notice(message));
    parts.summary.append(revealNote);
  };

  /**
   * Show the row *key* in the timeline: asked where it is under no filter, each span above
   * it opened with the page that holds the next, and the row itself scrolled to and focused.
   *
   * @param {string} key
   */
  const reveal = async (key) => {
    await firstPage;
    await whenShown();
    if (!current() || head.records === undefined) {
      return;
    }
    revealNote?.remove();
    if (filtersActive(filters)) {
      // The row may be one the filter hides, and a row asked for is shown, so the log is
      // shown whole; the bar says what is chosen.
      Object.assign(filters, emptyFilters());
      shared.version += 1;
      applied = shared.version;
      paintFilters();
      await startTimeline();
      if (!current()) {
        return;
      }
    }
    const generation = mount.generation;
    /** @type {Record<string, unknown>} */
    let answer;
    try {
      answer = await read("timeline", {
        ...filterParams(filters),
        ...(order === "newest" ? { order } : {}),
        focus: key,
        limit: "1",
      });
    } catch {
      sayWhyNotShown("The log could not be asked where that row is.");
      return;
    }
    if (!current() || generation !== mount.generation) {
      return;
    }
    const where = record(answer.focus);
    if (where.found !== true) {
      sayWhyNotShown("That row is not in this log’s timeline.");
      return;
    }
    const steps = list(where.steps).map(record);
    for (const [place, step] of steps.entries()) {
      const above = typeof step.parent === "string" ? step.parent : null;
      if (!(await holdThrough(above, count(step.index), generation))) {
        sayWhyNotShown("The rows above that one could not all be read.");
        return;
      }
      if (place < steps.length - 1) {
        timeline.open.add(text(step.key));
      }
    }
    paintTimeline();
    for (const line of drawn.values()) {
      line.node.removeAttribute("data-revealed");
    }
    const node = drawn.get(`row:${key}`)?.node;
    if (node !== undefined) {
      node.setAttribute("data-revealed", "");
      node.scrollIntoView?.({ block: "center" });
      focusHead(node);
    }
  };

  /** Show the row another view asked for, once, when this is the Timeline. */
  const showAsked = () => {
    const key = shared.focus;
    if (key !== null) {
      shared.focus = null;
      void reveal(key);
    }
  };

  /** @returns {Promise<void>} */
  const startTimeline = () => {
    mount.generation += 1;
    drawn = new Map();
    loading();
    timeline = createTimeline(order);
    head = {};
    firstPage = loadLevel(null);
    return firstPage;
  };

  // ── Latency ───────────────────────────────────────────────────────────────────

  /** @param {Record<string, unknown>} answer @param {string[]} labels */
  const histogramElement = (answer, labels) => {
    const counts = list(answer.histogram).map(count);
    const tallest = Math.max(1, ...counts);
    const bars = make("ol", "event-log-histogram");
    counts.forEach((n, index) => {
      const column = make("li", "event-log-hist-column");
      column.setAttribute("data-empty", n === 0 ? "true" : "false");
      const mark = make("span", "event-log-hist-bar");
      mark.style.setProperty("--event-log-hist-share", `${((n / tallest) * 100).toFixed(1)}%`);
      column.append(
        make("span", "event-log-hist-count", [mb.formatInteger(n)]),
        mark,
        make("span", "event-log-hist-label", [labels[index] ?? ""]),
      );
      bars.append(column);
    });
    return bars;
  };

  /**
   * Open or close a row of a list, and draw the list again, with the keyboard where it was.
   *
   * @param {EventRow} picked
   * @param {() => void} repaint
   */
  const toggleListed = (picked, repaint) => {
    const kept = hasFocus(rowNodes.get(picked.key)?.childNodes[0]);
    if (opened.delete(picked.key) === false) {
      opened.add(picked.key);
    }
    repaint();
    if (kept) {
      focusHead(rowNodes.get(picked.key));
    }
  };

  /** @param {Record<string, unknown>} answer */
  const paintLatency = (answer) => {
    rowNodes = new Map();
    const items = /** @type {EventRow[]} */ (list(answer.items));
    const labels = bucketLabels(list(answer.edges_ms).map(count));
    const longest = Math.max(0, ...items.map((row) => row.elapsed_ms ?? 0));
    parts.body.replaceChildren(
      heading("Distribution of times"),
      histogramElement(answer, labels),
      heading(
        "Slowest",
        `${mb.formatInteger(items.length)} of ${mb.formatInteger(count(answer.timed))}`,
      ),
    );
    if (items.length === 0) {
      parts.body.append(
        notice(
          filtersActive(filters)
            ? "Nothing in this log matches these filters."
            : "Nothing in this log took time.",
        ),
      );
      return;
    }
    for (const row of items) {
      const node = rowElement(mb, row, {
        depth: 0,
        open: opened.has(row.key),
        bar: { left: 0, width: Math.max(MIN_BAR, lengthShare(row.elapsed_ms, longest)) },
        showPath: true,
        onToggle: (picked) => toggleListed(picked, () => paintLatency(answer)),
        onShow: showInTimeline,
      });
      rowNodes.set(row.key, node);
      parts.body.append(node);
    }
    if (items.length < count(answer.timed)) {
      parts.body.append(
        notice(
          `${mb.formatInteger(count(answer.timed) - items.length)} quicker are not listed. The filters above narrow the list.`,
          "neutral",
        ),
      );
    }
  };

  // ── By kind ───────────────────────────────────────────────────────────────────

  /**
   * @param {Array<[string, string]>} columns
   * @param {Array<Array<string>>} rows
   */
  const table = (columns, rows) => {
    const headRow = make(
      "tr",
      "",
      columns.map(([label, align]) => {
        const cell = make("th", `event-log-cell event-log-cell-${align}`, [label]);
        cell.setAttribute("scope", "col");
        return cell;
      }),
    );
    const body = rows.map((cells) =>
      make(
        "tr",
        "",
        cells.map((cell, index) =>
          make("td", `event-log-cell event-log-cell-${columns[index]?.[1] ?? "start"}`, [cell]),
        ),
      ),
    );
    return make("table", "event-log-table", [
      make("thead", "", [headRow]),
      make("tbody", "", body),
    ]);
  };

  /** @param {Record<string, unknown>} answer */
  const paintKinds = (answer) => {
    const labels = bucketLabels(list(answer.edges_ms).map(count));
    parts.body.replaceChildren(heading("Distribution of times"), histogramElement(answer, labels));
    const kinds = list(answer.kinds).map(record);
    if (kinds.length === 0) {
      parts.body.append(
        notice(
          filtersActive(filters)
            ? "Nothing in this log matches these filters."
            : "This log holds no records.",
        ),
      );
      return;
    }
    for (const group of kinds) {
      const outcomes = Object.entries(record(group.outcomes))
        .map(([word, n]) => `${word.replace(/_/g, " ")} ${mb.formatInteger(count(n))}`)
        .join(" · ");
      const names = list(group.names).map(record);
      const section = make("section", "event-log-kind-section", [
        heading(text(group.kind), mb.formatInteger(count(group.count))),
        make("p", "event-log-kind-line", [
          outcomes,
          group.p50_ms === null
            ? ""
            : ` — median ${formatDuration(figure(group.p50_ms))}, 95th ${formatDuration(figure(group.p95_ms))}, longest ${formatDuration(figure(group.max_ms))}`,
        ]),
        table(
          [
            ["Name", "start"],
            ["Count", "end"],
            ["Failed", "end"],
            ["Median", "end"],
            ["95th", "end"],
            ["Longest", "end"],
            ["Total", "end"],
          ],
          names.map((row) => [
            text(row.name),
            mb.formatInteger(count(row.count)),
            mb.formatInteger(count(row.failed)),
            formatDuration(figure(row.p50_ms)),
            formatDuration(figure(row.p95_ms)),
            formatDuration(figure(row.max_ms)),
            formatDuration(figure(row.total_ms)),
          ]),
        ),
      ]);
      const more = count(group.names_more);
      if (more > 0) {
        section.append(make("p", "event-log-more-names", [`${mb.formatInteger(more)} more names`]));
      }
      parts.body.append(section);
    }
  };

  // ── Errors ────────────────────────────────────────────────────────────────────

  /**
   * One example of a failure, as a line: what it was and how it ended, where it ran, and
   * the way to its place in the Timeline.
   *
   * @param {Record<string, unknown>} example
   * @param {string} summary
   */
  const exampleLine = (example, summary) => {
    const key = text(example.key);
    return make("li", "", [summary, ...(key ? [" ", showButton(key, showInTimeline)] : [])]);
  };

  /** @param {Record<string, unknown>} answer */
  const paintErrors = (answer) => {
    rowNodes = new Map();
    const continues = record(answer.log).continues === true;
    const causes = list(answer.causes).map(record);
    const unfinished = record(answer.unfinished);
    const reports = record(answer.page_reports);
    const quiet = Object.entries(record(answer.not_failures));
    parts.body.replaceChildren();
    parts.body.append(heading("Failures by cause", mb.formatInteger(count(answer.failures))));
    if (causes.length === 0) {
      parts.body.append(notice("No failures in this log.", "neutral"));
    }
    for (const group of causes) {
      const box = make("section", "event-log-cause");
      const addresses = list(group.addresses).map(text);
      box.append(
        make("h4", "event-log-cause-name", [
          text(group.cause).replace(/_/g, " "),
          tally(mb.formatInteger(count(group.count))),
        ]),
      );
      const message = text(group.message);
      if (message) {
        box.append(make("p", "event-log-cause-message", [message]));
      }
      if (addresses.length > 0) {
        box.append(
          make("p", "event-log-cause-line", [`Addresses that failed: ${addresses.join(", ")}`]),
        );
      }
      box.append(
        make("p", "event-log-cause-line", [
          `${Object.entries(record(group.names))
            .map(([name, n]) => `${name} ${mb.formatInteger(count(n))}`)
            .join(" · ")}`,
        ]),
        make("p", "event-log-cause-line", [
          `First ${text(group.first).slice(11, 23)} · last ${text(group.last).slice(11, 23)} UTC`,
        ]),
      );
      const examples = list(group.examples).map(record);
      if (examples.length > 0) {
        const items = make("ul", "event-log-examples");
        for (const example of examples) {
          const above = list(example.path).map((span) => text(record(span).name));
          // A probe's name already begins with its kind; saying both is "probe probe ...".
          const kind = text(example.kind);
          const name = text(example.name);
          const called = name.startsWith(`${kind} `) ? name : `${kind} ${name}`;
          items.append(
            exampleLine(
              example,
              `${called} — ${text(example.outcome)} after ${formatDuration(figure(example.dur_ms))}` +
                (above.length > 0 ? ` (in ${above.join(" > ")})` : ""),
            ),
          );
        }
        box.append(items);
      }
      parts.body.append(box);
    }
    const probe = record(answer.probe);
    if (Object.keys(probe).length > 0) {
      const addressLines = list(probe.addresses).map(record);
      parts.body.append(
        heading("Last failed connectivity probe"),
        make("p", "event-log-cause-message", [text(probe.message)]),
        make(
          "ul",
          "event-log-examples",
          addressLines.map((line) =>
            make("li", "", [
              `${text(line.address)}: ${text(line.result)} after ${formatDuration(figure(line.ms))}`,
            ]),
          ),
        ),
      );
    }
    const stuck = /** @type {EventRow[]} */ (list(unfinished.rows));
    // A later segment of the same process may hold the end of what this one did not: the
    // work is not known to be stuck, and the heading does not say it was.
    parts.body.append(
      heading(
        continues ? "Not ended in this segment" : "Still running when the log ended",
        mb.formatInteger(count(unfinished.total)),
      ),
    );
    if (stuck.length === 0) {
      parts.body.append(notice("Everything that started had ended.", "neutral"));
    } else if (continues) {
      parts.body.append(
        notice(
          "The log continues in a later file, which may hold the end of this work.",
          "neutral",
        ),
      );
    }
    for (const row of stuck) {
      const node = rowElement(mb, row, {
        depth: 0,
        open: opened.has(row.key),
        bar: { left: 0, width: 1 },
        showPath: true,
        onToggle: (picked) => toggleListed(picked, () => paintErrors(answer)),
        onShow: showInTimeline,
      });
      rowNodes.set(row.key, node);
      parts.body.append(node);
    }
    parts.body.append(heading("What the pages reported", mb.formatInteger(count(reports.count))));
    const reported = list(reports.examples).map(record);
    if (reported.length === 0) {
      parts.body.append(
        make("p", "event-log-cause-line", ["No page reported a request or wait failing."]),
      );
    } else {
      parts.body.append(
        make("p", "event-log-cause-line", [
          "What a page saw, not why: the causes above are the server's.",
        ]),
        make(
          "ul",
          "event-log-examples",
          reported.map((example) =>
            exampleLine(
              example,
              `${text(example.name)} — ${text(example.outcome).replace(/_/g, " ")} after ${formatDuration(figure(example.dur_ms))}` +
                (text(example.path) ? ` on ${text(example.path)}` : "") +
                // When it was reported and by which page, as the timeline's detail says.
                ` · ${text(example.ts).slice(11, 23)} UTC` +
                (text(example.client) ? ` · page ${text(example.client)}` : ""),
            ),
          ),
        ),
      );
    }
    if (quiet.length > 0) {
      parts.body.append(
        make("p", "event-log-cause-line", [
          `Not failures: ${quiet.map(([word, n]) => `${mb.formatInteger(count(n))} ${word}`).join(" · ")}.`,
        ]),
      );
    }
  };

  // ── Reading ───────────────────────────────────────────────────────────────────

  const startReading = async () => {
    if (view === "timeline") {
      await startTimeline();
      return;
    }
    mount.generation += 1;
    loading();
    const generation = mount.generation;
    const extra = view === "errors" ? {} : filterParams(filters);
    try {
      const answer = await read(view === "latency" ? "slowest" : view, extra);
      if (!current() || generation !== mount.generation) {
        return;
      }
      settled();
      takeHead(record(answer.log));
      paintFilters();
      if (view === "latency") {
        paintLatency(answer);
      } else if (view === "kinds") {
        paintKinds(answer);
      } else {
        paintErrors(answer);
      }
    } catch (error) {
      if (current() && generation === mount.generation && !mount.abort.signal.aborted) {
        showFailure(parts, error);
      }
    }
  };

  const filtersChanged = () => {
    paintFilters();
    void startReading();
  };

  if (filterable && mb.filterControls) {
    mb.filterControls.bind(parts.filters, {
      onChange(key, value) {
        if (key === FILTER_ORDER && view === "timeline") {
          order = value === "newest" ? "newest" : "oldest";
          filtersChanged();
          return;
        }
        const next = chosen(filters, key, value);
        if (next === null) {
          return;
        }
        Object.assign(filters, next);
        shared.version += 1;
        applied = shared.version;
        filtersChanged();
      },
    });
  }
  // A view that was not shown while another chose a filter reads again when it is.
  const stopWatching = filterable
    ? mb.viewState?.subscribeActive(container, (active) => {
        if (active && applied !== shared.version) {
          applied = shared.version;
          filtersChanged();
        }
      })
    : undefined;
  if (view === "timeline") {
    shared.reveal = showAsked;
  }
  mount.stop = () => {
    stopWatching?.();
    if (shared.reveal === showAsked) {
      shared.reveal = null;
    }
    releaseShared(path);
  };
  void startReading();
  showAsked();
}

/** @param {HTMLElement} container */
export function disposeEventLogView(container) {
  const mount = mounts.get(container);
  if (mount === undefined) {
    return;
  }
  mount.abort.abort();
  mount.stop?.();
  mounts.delete(container);
}
