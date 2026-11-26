// The table view: one table of a tabular source, drawn from the table routes
// (/api/plugin/table/{schema,rows,record,card}) and steered by its address.
//
// A source plugin mounts it for its kind's Table view (`mountTable`, which index.js
// exports to a plugin that requires `table`). The view owns no data: the schema route
// says what the columns are and which sort and filter, the rows route answers each
// question the address asks, a page at a time, and the record and card routes answer
// one row. What the view decides (the state the address holds, how a cell is drawn, which
// columns fit, which rows the window draws, where a key moves the focus) is table-model.js,
// pure functions that tests/dom/table-view-session.js runs with this module from the
// command line.
//
// Layout. A toolbar (search, filter chips, the count, columns), then the grid in a scroll
// box of its own, so its header stays put and its window can be computed from its own
// scroll; the record opens in place of the grid, with a way back to it, as paraverse's
// browser opens one.
//
// Drawn whole or windowed (plan Decision 11). A table of at most WHOLE_TABLE_MAX_ROWS rows
// is read whole and every row drawn, so find in page, select all, copy, and print are the
// browser's. A larger one draws only the rows near the view over two spacers, at one fixed
// row height, reading the next page as the reader nears the last row held. There, Search
// stands in for find in page, Shift with Up, Down, Home, or End selects rows that copy as
// tab-separated values (a chord such as Command-A stays the browser's), and print draws
// every row held, saying on the page when rows past them were not read, as
// docs/large-content-rendering.md asks of a windowed view. Either way the table is a
// role="grid", since its rows take focus and can be selected.
//
// The keyboard. The grid is one Tab stop with roving focus: Up and Down, or `k` and `j`,
// move a row; Left and Right move from the row to its cells, so a link in a cell is
// reachable; Enter on the row opens its record, and on a cell follows its link. Up from
// the first row moves to the header, whose sort and menu buttons Left and Right cross, so
// a column's controls add no Tab stop (keyStep in table-model.js).
//
// The place. Each history entry keeps its scroll and focused row, so Back to the table and
// a reload return to them. The browser bounds history writes (Chrome ignores those past
// 200 in 10 seconds, pushes too, and WebKit throws past 100 in 30), so the place is written
// only when it matters: before the view navigates, when the page is hidden, and once a
// pause after the last move or scroll (PLACE_SAVE_MS), never a key press each.
//
// A new answer to the same question (`refresh()`, for a source that changes under the
// view) keeps the reader where they were, by row key: the focused row, the row at the top
// of the view, and the selection.

import {
  ABSENT_TEXT,
  columnWidths,
  countText,
  EMPTY_STATE,
  FILTER_OP_LABELS,
  FILTER_OPS,
  filterLabel,
  fitColumns,
  formatCount,
  isFiltered,
  joinPage,
  jsonValue,
  keyStep,
  literalField,
  liveFailure,
  liveMerge,
  livePillText,
  noMatchText,
  pageNotes,
  parseState,
  presentCell,
  reconcileState,
  rowPosition,
  rowsParams,
  rowsTsv,
  sameRows,
  sortRefused,
  stateQuery,
  wantsMore,
  windowRange,
  withColumns,
  withFilter,
  withoutFilter,
  withRecord,
  withRef,
  withSearch,
  withSort,
} from "./table-model.js";

/** @typedef {import("./table-model.js").TableState} TableState */
/** @typedef {import("./table-model.js").TableField} TableField */
/** @typedef {import("./table-model.js").TableRow} TableRow */
/** @typedef {import("./table-model.js").TablePage} TablePage */
/** @typedef {import("./table-model.js").GridFocus} GridFocus */

// ── Bounds and timings ────────────────────────────────────────
//
// Measured with tests/dom/table-view-measure.mjs in headless Chrome on a shared
// 4-processor Linux container (2026-11-20), over generated tables of 12 columns of short
// text, numbers, dates, and booleans, one line a row, in a 1,280 x 800 window, three
// opens of each; rerun it for the current numbers.

// The most rows a table may hold and still be read and drawn whole, keeping the browser's
// own find, select all, copy, and print. Drawing a whole table is linear in its rows, and
// layout is most of it: from the last answer to laid out, at a load average near 2, 500
// rows took 64 to 93 ms, 1,000 rows 159 to 201 ms, and 2,000 rows 279 to 329 ms, and at a
// load average of 4 to 5 about half as long again, where the first window of a windowed
// table of 50,000 rows took 7 to 32 ms. Five hundred rows keeps a whole table under the
// 0.2 s past which a click stops feeling immediate on a busy machine as well as an idle
// one; a thousand reached it.
export const WHOLE_TABLE_MAX_ROWS = 500;

// Rows the first request asks for: a screen of them several times over, so a windowed
// table scrolls a while before its next request, in one answer the server encodes in a
// few milliseconds (TABLE_PAGE_ROWS_DEFAULT's measurement in table_source.py).
export const FIRST_PAGE_ROWS = 200;

// Rows each later request asks for: as many as the route gives at once
// (TABLE_PAGE_ROWS_MAX), so a table of WHOLE_TABLE_MAX_ROWS is read in two requests and a
// long scroll asks seldom.
//
// Both are what the view asks, not what it gets: a page of wide rows carries fewer
// (TABLE_PAGE_CELLS_MAX), and its `limit` says how many. The view counts the rows that
// came and reads on from `next_after` until the table, or the window's need, is met.
export const NEXT_PAGE_ROWS = 1000;

// A row's height before the first drawn row is measured, by its line count, so the
// window's first draw places its spacers where they end up: one line of the 14 px body
// text with the cell's padding measured 32.2 px in Chrome 152 (2026-11-20), and two lines
// 52.2 px. The view measures its first drawn row and uses that, drawing the window again
// when the estimate was more than half a pixel off, so tests/test_table_view_chrome.py
// checks that each estimate is within that of what Chrome measures.
export const ROW_HEIGHT_ESTIMATE_PX = Object.freeze({ 1: 32, 2: 52 });

// Rows the window draws past each edge of the view, so a scroll the compositor moves
// ahead of the page's own redraw shows rows already drawn: twelve rows is about a third
// of a view in the default window, more than a wheel step moves. Redrawing a window of the
// view's rows and twelve past each edge, 41 rows of 12 columns, took 1.5 to 8.1 ms a step
// while scrolling, and 1.7 to 6.6 ms at a load average near 2.
export const ROWS_OVERSCAN = 12;

// How near the last row held, in rows, the window comes before the next page is read.
export const READ_AHEAD_ROWS = 100;

// Rows held. A windowed table keeps every page it reads, so what it holds grows as the
// reader scrolls on, up to what its source parses; the view sets no bound of its own,
// because at the delimited source's own bounds the cost stayed small and flat. Measured
// with tests/dom/table-view-measure.mjs's `held` mode in headless Chrome 152 on the
// shared 4-processor container at a load average of 8 to 14 (2026-11-20), scrolling a
// 12-column table to its byte bound and a 2-column one to its row bound: at 139,676 rows
// of 12 columns, the most the source parses of that shape, the JavaScript heap after a
// collection was 38.8 MB and a window's redraw while scrolling 1.7 to 14.2 ms, as at
// 10,200 rows (2 to 8.6 ms); at 500,000 rows of 2 columns, DELIMITED_MAX_ROWS, 83.5 MB
// and 0.9 to 1.3 ms, its scroll box 16 million pixels tall. A source that parses more
// than these brings a bound for it with it.

// The most rows a printout of a windowed table draws: about what a table drawn whole may
// be, a few times over. Drawing every row held for print is linear in them and stops the
// page while it runs, as drawing a table whole is (WHOLE_TABLE_MAX_ROWS): in the
// measurement above, 10,200 rows took 3.4 s from `beforeprint` to laid out, 50,200 rows
// 6.8 to 15.7 s, and 500,000 rows of 2 columns 21.5 s, where 2,000 rows drawn whole took
// 0.28 to 0.33 s. Past it the printout says which rows it holds and how to print others.
export const PRINT_MAX_ROWS = 2000;

// The pause after the reader stops typing in Search before the table asks again: the same
// a quarter-second the shell's filter fields wait.
export const SEARCH_DEBOUNCE_MS = 250;

// How long the pointer rests on a reference before its hover card is read, and how long
// after it leaves before the card is put away.
export const CARD_DELAY_MS = 300;

// The pause after the last move of the focus or scroll before the place is written to the
// history entry. A held key or a long scroll restarts it, so it writes once, after it
// stops: well under WebKit's 100 history writes in 30 seconds, the stricter of the two
// engines' bounds, however long the reader keeps moving. Half a second is past a key's
// repeat interval (about 33 ms at a fast rate) and a wheel's gaps, and short of the time
// a reader takes to reach for Reload; the page's hiding writes it at once too.
export const PLACE_SAVE_MS = 500;

// How long the view gathers `file.changed` events before it reads its rows again. The
// window is bounded, as createInventoryWatch's is (static/inventory-scope.js): the first
// change starts it and later ones join it without extending it, so a writer that never
// pauses still gets a refresh every window. The server polls a watched file at most
// every FILE_WATCH_MIN_SPACING_S (metabrowser.file_watches), so two polls a window apart
// make one read here; a refresh reads the rows held, which for a table drawn whole is up
// to WHOLE_TABLE_MAX_ROWS rows in two requests.
export const LIVE_COALESCE_MS = 300;

// How far apart two live refreshes are, in multiples of what the last one took: the next
// starts no sooner than this many times the last's duration after a change, nor sooner
// than LIVE_COALESCE_MS. A refresh's cost is the server's, and for a delimited file it is
// a parse of the whole file at each new generation (the parse cache is keyed by it):
// measured for review A of #675 on a shared 4-core container at a load near 8, the read
// after one line appended to a 15 MB, 199,096-row CSV took 0.47 to 0.66 s, and to a 1 MB
// one 0.05 s. At twice the duration a writer that never pauses keeps the server reading
// for a tab at most a third of the time, and a cheap file still refreshes every window.
export const LIVE_COST_SPACING = 2;

// How long a changed or arrived row keeps its flash: the length of the shared
// `tree-row-flash-in` animation in static/styles.css, after which a row drawn again by a
// scroll is drawn plainly.
export const LIVE_FLASH_MS = 900;

/** The history state key under which the view keeps its scroll and focused row. */
const PLACE_KEY = "metabrowserTablePlace";
/**
 * Frames a saved place is tried for before it is given up: a fresh load lays the scroll
 * box out within a frame or two of the first draw, and a place the box can no longer
 * reach (a table that shrank) is not chased.
 */
const PLACE_TRIES = 10;
/** Links made and kept for reuse, a few dozen, the filter values of a drawing's columns. */
const HREFS_KEPT = 64;
/** A key no source mints, which a row's record link holds until its key replaces it. */
const RECORD_SLOT = "__record__";
/**
 * A cell's horizontal padding, both sides, where nothing is laid out to measure it, as in
 * the browserless session: --panel-cell-padding's 0.6rem twice, rounded up. A browser
 * measures it from a probe that carries that padding (measureCh).
 */
const CELL_PAD_PX = 20;

/**
 * What the view needs from its host: the SDK, and the platform services it uses, so the
 * browserless session can supply its own.
 *
 * @typedef {{
 *   fetchPluginData: Window["metabrowser"]["fetchPluginData"],
 *   navigation: Window["metabrowser"]["navigation"],
 *   tooltip?: Window["metabrowser"]["tooltip"],
 *   escapeHtml: Window["metabrowser"]["escapeHtml"],
 *   watchFile?: Window["metabrowser"]["watchFile"],
 *   menus: MetabrowserMenus,
 * }} TableSdk
 */
/**
 * @typedef {{
 *   sdk?: TableSdk,
 *   window?: Pick<Window, "addEventListener" | "removeEventListener" | "requestAnimationFrame" | "cancelAnimationFrame" | "setTimeout" | "clearTimeout" | "getSelection"> & {performance?: Pick<Performance, "now">},
 *   history?: Pick<History, "back" | "replaceState" | "state">,
 *   location?: Pick<Location, "search">,
 *   document?: Document,
 * }} TableHost
 */
/**
 * @typedef {{
 *   ready: Promise<void>,
 *   dispose(): void,
 *   state(): TableState,
 *   refresh(): Promise<void>,
 * }} TableHandle
 */
/**
 * What a source's view hands the table: the address of the table, and how to draw a
 * JSON value in a record, which the table plugin, needing no other plugin, cannot. The
 * structured plugin passes its inline tree; without it a JSON value is its text.
 *
 * @typedef {{
 *   path: string,
 *   renderJson?: (container: HTMLElement, value: unknown) => ({dispose?: () => void} | void),
 * }} TableContext
 */

/**
 * Mount the table at *ctx.path*, the address of one table, into *container*.
 *
 * @param {HTMLElement} container
 * @param {TableContext} ctx
 * @param {TableHost} [host]
 * @returns {TableHandle}
 */
export function mountTable(container, ctx, host = {}) {
  const sdk = /** @type {TableSdk} */ (host.sdk ?? window.metabrowser);
  const win = host.window ?? window;
  const history = host.history ?? window.history;
  const loc = host.location ?? window.location;
  const doc = host.document ?? container.ownerDocument ?? document;
  const path = ctx.path;
  const abort = new AbortController();
  let disposed = false;

  // ── State ────────────────────────────────────────────────────
  /** @type {TableState} */
  let state = stateFromAddress();
  /** @type {ReadonlyArray<TableField>} */
  let fields = [];
  /** @type {Map<string, TableField>} */
  let fieldsByName = new Map();
  /** The rows held for the current question, in order. @type {TableRow[]} */
  let rows = [];
  /** The answer held: the first page's count and columns, the last's cursor, every page's rows (`rows`). @type {(TablePage & {rows: TableRow[]}) | null} */
  let page = null;
  /** The table id the schema answered for, "" for a source that is its own table. */
  let tableId = "";
  /** The question `page` answers, whose rows its `next_after` continues. @type {TableState} */
  let answered = state;
  /** @type {string[]} */
  let columns = [];
  /** @type {Record<string, number>} */
  let widths = {};
  /** @type {1 | 2} */
  let rowLines = 1;
  let windowed = false;
  let rowHeight = /** @type {number} */ (ROW_HEIGHT_ESTIMATE_PX[1]);
  let rowHeightMeasured = false;
  /** @type {{visible: string[], hidden: string[], pinned: boolean}} */
  let fit = { visible: [], hidden: [], pinned: false };
  /** @type {{start: number, end: number}} */
  let drawn = { start: 0, end: 0 };
  /** @type {GridFocus} */
  let focus = { row: 0, col: -1 };
  /** @type {{anchor: number, head: number} | null} */
  let selection = null;
  let loadSeq = 0;
  /** @type {AbortController | null} */
  let loading = null;
  let readingMore = false;
  // A scan with no matches pauses so automatic read-ahead cannot chase it indefinitely.
  let scanPaused = false;
  /** Whether reading the next page failed, so scrolling does not ask again. */
  let moreFailed = false;
  let printing = false;
  /**
   * The query of the record entry this view pushed, so its Back link returns to the
   * table entry behind it; null when the record was not opened from this table's grid.
   * @type {string | null}
   */
  let pushedRecord = null;
  /** @type {Map<number, HTMLTableRowElement>} */
  const rowElements = new Map();
  /** @type {Map<string, Promise<unknown>>} */
  const cards = new Map();
  /** @type {Map<string, string>} */
  const hrefs = new Map();
  /** @type {string | null} */
  let recordTemplate = null;

  // Live: the file watch, and what a change does while it is on or paused.
  /** @type {(() => void) | null} */
  let unwatch = null;
  let paused = false;
  /** Changes held back while paused. */
  let heldBack = 0;
  /** @type {ReturnType<typeof setTimeout> | 0} */
  let liveTimer = 0;
  let refreshing = false;
  let refreshAgain = false;
  /** Keys of rows that flash when they are next drawn. @type {Set<string>} */
  let flashing = new Set();
  /** @type {ReturnType<typeof setTimeout> | 0} */
  let flashTimer = 0;
  /** A notice that outlives a redraw: a live refresh that failed, or a column the view dropped. @type {HTMLElement | null} */
  let liveNotice = null;
  /** @type {HTMLElement | null} */
  let stateNotice = null;
  /** The open record's cells as last drawn, and whether it may now be another row. */
  let shownRecord = { key: "", cells: "", moved: false };
  /** How long the last live refresh took, in ms: the next is spaced by it. */
  let liveCost = 0;
  /** A change arrived while the page was hidden: one refresh when it is shown. */
  let hiddenHeld = false;
  /** What the live region last said of the offer and of a failed refresh, so neither repeats. */
  let offerAnnounced = false;
  let failureAnnounced = false;
  /** A notice that the file's watch was refused, so the table does not follow it. @type {HTMLElement | null} */
  let watchNotice = null;
  /** The open record's controls by a name that survives a redraw, to put focus back on. @type {Map<string, HTMLElement>} */
  let recordControls = new Map();
  /** What the open record's JSON values drew, released when the record goes. @type {Array<{dispose?: () => void}>} */
  let recordMounts = [];

  // ── Markup ───────────────────────────────────────────────────
  const root = el("div", { class: "table-view" });
  const toolbar = el("div", { class: "table-toolbar" });
  const search = /** @type {HTMLInputElement} */ (
    el("input", {
      class: "field table-search",
      type: "search",
      placeholder: "Search",
      "aria-label": "Search rows",
      spellcheck: "false",
    })
  );
  const chips = el("span", { class: "table-chips" });
  const status = el("span", { class: "table-status" });
  const fitNote = el("button", { type: "button", class: "table-fit-note", hidden: "" });
  const columnsButton = el(
    "button",
    {
      type: "button",
      class: "btn table-columns-button",
      "aria-haspopup": "dialog",
      "aria-expanded": "false",
    },
    "Columns",
  );
  // Shown once the file's watch is live; pressing it pauses the table, and again resumes
  // it. Its label is its state, and its accessible name the action. The record pane has
  // its own, since the toolbar is hidden while a record shows.
  const livePill = el("button", { type: "button", class: "btn table-live-pill", hidden: "" });
  const recordPill = el("button", { type: "button", class: "btn table-live-pill", hidden: "" });
  // New rows that would land above the reader's place, offered rather than drawn.
  const offer = el("button", { type: "button", class: "btn table-offer", hidden: "" });
  // After the fit note, and before Columns, which its own margin holds at the toolbar's
  // end, so neither moves as these come and go; once shown, each keeps its slot while
  // hidden (styles.css).
  toolbar.append(search, chips, status, fitNote, offer, livePill, columnsButton);
  const notes = el("div", { class: "table-notes" });
  /** On paper only: which rows a windowed table printed, when rows past them were not read. */
  const printNote = el("p", { class: "table-print-note" });
  const scroller = el("div", { class: "table-scroll" });
  const table = /** @type {HTMLTableElement} */ (el("table", { class: "data-grid" }));
  const colgroup = el("colgroup", {});
  const thead = el("thead", {});
  const tbody = el("tbody", {});
  table.append(colgroup, thead, tbody);
  scroller.append(table);
  const recordPane = el("div", { class: "table-record", hidden: "" });
  const live = el("div", { class: "sr-only", "aria-live": "polite" });
  root.append(toolbar, notes, printNote, scroller, recordPane, live);
  container.replaceChildren(root);
  /** The open menu, and the control that opened it. @type {{menu: HTMLElement, opener: HTMLElement} | null} */
  let openMenu = null;
  // The Columns and header menus close as every menu does (docs/design-system.md, "Every
  // Menu Closes Alike"): a press, focus, or the window leaving the menu and its opener, or
  // Escape, which gives focus back to the opener; its opener's click toggles it.
  const dismissal = sdk.menus?.dismissible({
    name: "table-menu",
    trigger: () => openMenu?.opener ?? null,
    inside: (node) => Boolean(openMenu?.menu.contains(node)),
    isOpen: () => openMenu !== null,
    close: () => closeMenu(false),
  });

  // ── The address ──────────────────────────────────────────────

  /** @returns {TableState} */
  function stateFromAddress() {
    const current = sdk.navigation.current();
    if (!current || normalPath(current.path) !== normalPath(path)) {
      return EMPTY_STATE;
    }
    return parseState(current.query ?? "");
  }

  /**
   * Put *next* in the address and show it. A step the reader takes (a sort, a filter, a
   * record) is an entry Back returns from; typing in Search replaces the entry.
   *
   * @param {TableState} next
   * @param {{replace?: boolean}} [how]
   */
  function go(next, how = {}) {
    // The place belongs to the entry the reader leaves: written to it now, or, for an entry
    // replaced, not at all.
    if (how.replace) {
      cancelPlace();
    } else {
      flushPlace();
    }
    const query = stateQuery(next);
    void sdk.navigation
      .open(query ? { path, query } : { path }, { replace: Boolean(how.replace) })
      .catch((/** @type {unknown} */ error) => {
        console.warn("metabrowser table: could not put the table's state in the address", error);
      });
    apply(next);
  }

  /** @param {TableState} next */
  function href(next) {
    const query = stateQuery(next);
    let made = hrefs.get(query);
    if (made === undefined) {
      made = sdk.navigation.href(query ? { path, query } : { path });
      if (hrefs.size >= HREFS_KEPT) {
        hrefs.clear();
      }
      hrefs.set(query, made);
    }
    return made;
  }

  /**
   * A row's record link: the table's address with the row's key as `record`. Each row's
   * differs from the next only in its key, so one address is made per drawing and each
   * row's key put in its place, rather than one per row.
   *
   * @param {string} key
   */
  function recordHref(key) {
    recordTemplate ??= href(withRecord(state, RECORD_SLOT));
    // `record` is the query's last parameter (stateQuery), so its slot is the last
    // occurrence: a search or filter value spelled the same comes before it.
    const at = recordTemplate.lastIndexOf(RECORD_SLOT);
    return `${recordTemplate.slice(0, at)}${new URLSearchParams({ k: key }).toString().slice(2)}${recordTemplate.slice(at + RECORD_SLOT.length)}`;
  }

  function onPopState() {
    if (disposed) {
      return;
    }
    const current = sdk.navigation.current();
    if (current && normalPath(current.path) === normalPath(path)) {
      cancelPlace();
      apply(parseState(current.query ?? ""));
    }
  }

  /**
   * Show *next*: ask the rows route again when its question changed, and open or close
   * the record.
   *
   * @param {TableState} next
   */
  function apply(next) {
    const previous = state;
    state = next;
    stateNotice = null;
    recordTemplate = null;
    if (doc.activeElement !== search) {
      search.value = state.q;
    }
    drawChips();
    if (!sameRows(previous, next) || page === null) {
      void loadRows();
    }
    if (next.record) {
      void showRecord(next.record);
    } else if (!recordPane.hidden) {
      showGrid();
    }
  }

  // ── Reading ──────────────────────────────────────────────────

  /**
   * @param {string} route
   * @param {Record<string, string | string[]>} params
   * @param {AbortSignal} signal
   */
  function ask(route, params, signal) {
    return sdk.fetchPluginData("table", route, { path, ...params }, { signal });
  }

  async function loadSchema() {
    const schema = /** @type {{table?: unknown, fields: TableField[]}} */ (
      /** @type {unknown} */ (await ask("schema", {}, abort.signal))
    );
    // The table this view shows, from the answer awaited before anything is drawn, so a
    // record's links are right before, and whatever, the rows answer.
    tableId = typeof schema.table === "string" ? schema.table : "";
    fields = schema.fields;
    fieldsByName = new Map(fields.map((field) => [field.name, field]));
    const reconciled = reconcileState(state, fields);
    if (reconciled.dropped.length) {
      state = reconciled.state;
      recordTemplate = null;
      stateNotice = noticeBox(
        "warning",
        `This table has no ${reconciled.dropped.map((name) => `“${name}”`).join(", ")} now, so the view no longer uses it.`,
      );
      notes.append(stateNotice);
      const query = stateQuery(state);
      void sdk.navigation
        .open(query ? { path, query } : { path }, { replace: true })
        .catch(() => {});
    }
  }

  /**
   * Read the first page of the current question, and the rest of a table small enough to
   * draw whole. With *keep*, the question is the one answered and this is its new answer
   * (a refresh): it reads as far as the rows the reader has reached, and the drawing keeps
   * their place by key. A question whose history entry holds a place (Back, or a reload)
   * reads as far as that place, so its row and scroll are held to return to.
   *
   * A live refresh (*live*, liveRefresh) is a refresh that merges the new answer with
   * the rows held (table-model.js's liveMerge): rows that would land above the reader's
   * place are offered rather than drawn unless *accept*, what changed or arrived flashes,
   * an answer whose rows are the same draws nothing, and a failure is the caller's, after
   * the schema is read again in case the question moved.
   *
   * @param {{keep?: boolean, live?: {accept: boolean}}} [how]
   */
  async function loadRows(how = {}) {
    const seq = ++loadSeq;
    loading?.abort();
    const controller = new AbortController();
    loading = controller;
    moreFailed = false;
    const question = state;
    const refresh = Boolean(how.keep) && page !== null && sameRows(answered, question);
    const place = refresh ? null : savedPlace(question);
    const reached = refresh
      ? Math.max(drawn.end, focus.row + 1) + READ_AHEAD_ROWS
      : place
        ? Math.max(place.row + 1, Math.ceil(place.top / ROW_HEIGHT_ESTIMATE_PX[1])) +
          READ_AHEAD_ROWS
        : 0;
    root.setAttribute("aria-busy", "true");
    try {
      const first = /** @type {TablePage} */ (
        /** @type {unknown} */ (
          await ask("rows", rowsParams(question, { limit: FIRST_PAGE_ROWS }), controller.signal)
        )
      );
      let held = { ...first, rows: [...first.rows] };
      const whole =
        first.count_complete && first.count !== null && first.count <= WHOLE_TABLE_MAX_ROWS;
      const wanted = whole ? WHOLE_TABLE_MAX_ROWS : reached;
      let paused = first.reason === "budget" && first.rows.length === 0;
      while (held.next_after && held.rows.length < wanted && !paused) {
        const next = /** @type {TablePage} */ (
          /** @type {unknown} */ (
            await ask(
              "rows",
              rowsParams(question, { after: held.next_after, limit: NEXT_PAGE_ROWS }),
              controller.signal,
            )
          )
        );
        paused = next.reason === "budget" && next.rows.length === 0;
        held = joinPage(held, next);
      }
      if (seq !== loadSeq || disposed) {
        return;
      }
      if (how.live && refresh && held.columns.join("\n") !== columns.join("\n")) {
        // The columns moved: the schema again, and the question with it if one it names
        // is gone.
        if (await questionMoved(seq)) {
          return;
        }
      }
      scanPaused = paused;
      const kept = refresh ? keptPlace() : null;
      if (how.live && kept && rows.length > 0 && held.rows.length > 0) {
        const merged = liveDrawn(held, kept, how.live.accept);
        if (merged === null) {
          rows = held.rows;
          page = held;
          windowed = !whole || Boolean(held.next_after);
          return;
        }
        held = { ...held, rows: merged };
      }
      rows = held.rows;
      page = held;
      answered = question;
      windowed = !whole || Boolean(held.next_after);
      drawTable(kept);
      watchFile();
    } catch (error) {
      if (seq === loadSeq && !disposed && !isAbort(error)) {
        if (!how.live) {
          failed(error);
        } else if (!(await questionMoved(seq))) {
          throw error;
        }
      }
    } finally {
      if (seq === loadSeq) {
        root.removeAttribute("aria-busy");
      }
    }
  }

  /**
   * Read the next page of a windowed table, once the window nears the last row held. The
   * cursor continues only the question it was made for, so while a new question's first
   * page is on its way, the rows held for the last one read no further.
   */
  async function readMore() {
    if (readingMore || moreFailed || !page?.next_after || !windowed || !sameRows(answered, state)) {
      return;
    }
    readingMore = true;
    const wasEmpty = rows.length === 0;
    const seq = loadSeq;
    const signal = loading?.signal ?? abort.signal;
    let read = false;
    try {
      const next = /** @type {TablePage} */ (
        /** @type {unknown} */ (
          await ask(
            "rows",
            rowsParams(answered, { after: page.next_after, limit: NEXT_PAGE_ROWS }),
            signal,
          )
        )
      );
      if (seq !== loadSeq || disposed || !page) {
        return;
      }
      scanPaused = next.reason === "budget" && next.rows.length === 0;
      page = joinPage(page, next);
      rows = page.rows;
      read = true;
    } catch (error) {
      if (seq === loadSeq && !disposed && !isAbort(error)) {
        // Said once; the next question, or a reload, asks again.
        moreFailed = true;
        notice("error", `The next rows could not be read. ${errorText(error)}`);
      }
    } finally {
      readingMore = false;
    }
    if (read && wasEmpty) {
      drawTable();
    } else if (read && page) {
      status.textContent = countText(page, isFiltered(state));
      // Drawn once the read is over, so a page shorter than the window's need, as a page
      // of wide rows is, reads the next at once.
      drawNotes();
      drawWindow(true);
    }
  }

  // ── Live ─────────────────────────────────────────────────────
  //
  // The view watches its file through the page's event stream (metabrowser.watchFile).
  // A change, gathered for LIVE_COALESCE_MS and spaced by LIVE_COST_SPACING, asks the
  // question again as refresh() does (loadRows with keep), reading as far as the reader
  // has reached, and table-model.js's liveMerge says what changed: the rows under the
  // reader stay where they were, rows that would land above them are offered, and the
  // focus and the selection follow their rows by key. A read that fails keeps the rows on
  // screen and says so. Nothing is read while the page is hidden.

  function watchFile() {
    if (unwatch || disposed || typeof sdk.watchFile !== "function") {
      return;
    }
    unwatch = sdk.watchFile(path, {
      generation: page?.generation ?? null,
      onChange: onFileChange,
      onState: (watchState) => {
        const shown = watchState === "live" || paused;
        for (const pill of [livePill, recordPill]) {
          pill.hidden = !shown;
          if (shown) {
            pill.dataset.slot = "";
          }
        }
        drawPill();
        // A refused watch is asked again when the page's other watches make room.
        watchNotice =
          watchState === "refused"
            ? noticeBox(
                "warning",
                // Why, `reason`, is the watch's, for an agent (docs/design-system-messages.md).
                "This table is not following changes to its file now.",
              )
            : null;
        drawNotes();
      },
    });
  }

  /** @param {{path: string, generation: string | null}} change */
  function onFileChange(change) {
    if (disposed || (page && change.generation === page.generation)) {
      return;
    }
    if (paused) {
      heldBack += 1;
      drawPill();
      return;
    }
    scheduleLive();
  }

  /** Whether the page is hidden, when nothing reads a refresh. */
  function pageHidden() {
    return doc.visibilityState === "hidden";
  }

  function scheduleLive() {
    if (liveTimer || disposed || paused) {
      return;
    }
    if (pageHidden()) {
      hiddenHeld = true;
      return;
    }
    liveTimer = win.setTimeout(
      () => {
        liveTimer = 0;
        if (pageHidden()) {
          hiddenHeld = true;
        } else {
          void liveRefresh();
        }
      },
      Math.max(LIVE_COALESCE_MS, LIVE_COST_SPACING * liveCost),
    );
  }

  /** The page was shown: one refresh for whatever changed while it was hidden. */
  function onVisibility() {
    if (!pageHidden() && hiddenHeld) {
      hiddenHeld = false;
      scheduleLive();
    }
  }

  /** @returns {number} */
  function now() {
    return win.performance?.now() ?? Date.now();
  }

  function drawPill() {
    for (const pill of [livePill, recordPill]) {
      pill.textContent = livePillText(paused, heldBack);
      pill.setAttribute(
        "aria-label",
        `${pill.textContent}: ${paused ? "resume live updates" : "pause live updates"}`,
      );
      pill.dataset.tipText = paused
        ? "Changes to the file are held back; press to show them"
        : "The table follows changes to its file; press to pause it";
    }
  }

  function togglePaused() {
    paused = !paused;
    const held = heldBack;
    if (!paused) {
      heldBack = 0;
      if (held) {
        scheduleLive();
      }
    }
    drawPill();
    live.textContent = paused ? "Paused" : "Live";
  }

  /**
   * Ask the question again, as refresh() does, and draw what changed. With *accept*, new
   * rows above the reader's place are drawn too, and the view goes to the first of them.
   *
   * @param {boolean} [accept]
   */
  async function liveRefresh(accept = false) {
    if (disposed || !page) {
      return;
    }
    if (refreshing) {
      refreshAgain = true;
      return;
    }
    refreshing = true;
    const began = now();
    try {
      if (state.record && !recordPane.hidden) {
        void showRecord(state.record, true);
      }
      await loadRows({ keep: true, live: { accept } });
    } catch (error) {
      if (!disposed && !isAbort(error)) {
        liveFailed(error);
      }
    } finally {
      refreshing = false;
      liveCost = now() - began;
      if (refreshAgain) {
        refreshAgain = false;
        scheduleLive();
      }
    }
  }

  /**
   * Merge a live refresh's answer, *held*, into the rows drawn: the rows to draw, or null
   * when they read the same and need no drawing. Rows that would land above the first
   * row on screen are offered, and left out, unless *accept*; with *accept*, *kept* puts
   * the view and the keyboard on the first row that arrived.
   *
   * @param {TablePage} held
   * @param {ReturnType<typeof keptPlace>} kept
   * @param {boolean} accept
   * @returns {TableRow[] | null}
   */
  function liveDrawn(held, kept, accept) {
    const atTop = scroller.scrollTop <= 0;
    const anchorAt = atTop ? -1 : rows.findIndex((row) => row.key === kept.anchorKey);
    const merged = liveMerge({
      before: rows,
      after: held.rows,
      anchor: anchorAt >= 0 ? anchorAt : null,
      accept,
    });
    const same =
      held.columns.join("\n") === columns.join("\n") &&
      merged.changed.length === 0 &&
      merged.arrived.length === 0 &&
      merged.offered === 0 &&
      merged.rows.length === rows.length &&
      merged.rows.every((row, index) => row.key === rows[index].key);
    liveNotice = null;
    failureAnnounced = false;
    drawOffer(merged.offered);
    if (same) {
      // Nothing the grid shows changed (a touched file, or a change outside the
      // question): the rows, the selection, and any text selected in them stay drawn.
      status.textContent = countText(held, isFiltered(state));
      drawNotes();
      return null;
    }
    flashing = new Set([...merged.changed, ...merged.arrived]);
    win.clearTimeout(flashTimer);
    flashTimer = win.setTimeout(() => {
      flashTimer = 0;
      flashing = new Set();
    }, LIVE_FLASH_MS);
    kept.live = true;
    const arrived = accept ? merged.arrived[0] : undefined;
    if (arrived !== undefined) {
      // The offer's button is gone: the keyboard goes to the first row it drew.
      kept.header = null;
      kept.focusKey = arrived;
      kept.anchorKey = arrived;
      kept.offset = 0;
      kept.hadFocus = true;
    } else if (atTop) {
      // At the top nothing is above the reader: rows that arrived first are in view.
      kept.anchorKey = null;
      kept.top = 0;
    }
    return merged.rows;
  }

  /**
   * Read the schema again: whether the question the rows answer moved, as when a column
   * it named is gone, in which case its rows are read afresh.
   *
   * @param {number} seq the load the refresh began in
   */
  async function questionMoved(seq) {
    await loadSchema();
    if (seq !== loadSeq || disposed) {
      return true;
    }
    if (sameRows(answered, state)) {
      return false;
    }
    await loadRows();
    return true;
  }

  /** @param {number} count */
  function drawOffer(count) {
    offer.hidden = count === 0;
    // Hidden, it keeps its last words, so its slot keeps their width.
    if (count) {
      offer.textContent = `${formatCount(count)} new ${count === 1 ? "row" : "rows"}`;
      offer.dataset.slot = "";
      offer.dataset.tipText = "Rows that arrived above this place; press to show them";
      // Said when the offer appears, not again as its count grows while rows arrive.
      if (!offerAnnounced) {
        live.textContent = offer.textContent;
      }
    }
    offerAnnounced = count > 0;
  }

  /**
   * A live read failed: keep the rows on screen, and say why they may be old.
   *
   * @param {unknown} error
   */
  function liveFailed(error) {
    const payload = /** @type {{payload?: {code?: unknown}}} */ (error)?.payload;
    const code = typeof payload?.code === "string" ? payload.code : null;
    liveNotice = noticeBox("warning", liveFailure(code));
    drawNotes();
    // Said once, until a refresh reads the file again.
    if (!failureAnnounced) {
      failureAnnounced = true;
      live.textContent = liveNotice.textContent ?? "";
    }
  }

  // ── Drawing the grid ─────────────────────────────────────────

  /**
   * Where the reader is in the answer held, by row key, so a new answer to the same
   * question can put them back: the focused row (or header control), the row at the top
   * of the view and how far into it the view is scrolled, and the selection's ends.
   */
  function keptPlace() {
    const top = scroller.scrollTop;
    const anchor = Math.max(0, Math.min(rows.length - 1, Math.floor(top / rowHeight)));
    return {
      header: focus.row < 0 ? focus.col : null,
      focusKey: focus.row >= 0 ? (rows[focus.row]?.key ?? null) : null,
      col: focus.col,
      anchorKey: /** @type {string | null} */ (rows[anchor]?.key ?? null),
      offset: top - anchor * rowHeight,
      top,
      selection: selection
        ? { anchor: rows[selection.anchor]?.key ?? null, head: rows[selection.head]?.key ?? null }
        : null,
      hadFocus: scroller.contains(doc.activeElement),
      // A live refresh's (liveDrawn), which says nothing of the count in the live region.
      live: false,
    };
  }

  /**
   * Draw the answer held. A new question's answer starts at its first row, unless Back
   * restores a place below; a new answer to the same question (*kept*, from keptPlace)
   * keeps the reader's rows by key, and the first row in view where it was.
   *
   * @param {ReturnType<typeof keptPlace> | null} [kept]
   */
  function drawTable(kept = null) {
    if (!page) {
      return;
    }
    // A place held for the last answer is not this one's; restorePlace holds this one's.
    releasePlace();
    // A header control the keyboard was on (a sort just pressed) keeps the keyboard there.
    const headAt = headControls().indexOf(/** @type {HTMLElement} */ (doc.activeElement));
    const linesBefore = rowLines;
    if (kept) {
      const at = keyIndex();
      const row = kept.focusKey !== null ? (at.get(kept.focusKey) ?? -1) : -1;
      focus =
        kept.header !== null
          ? { row: -1, col: kept.header }
          : row >= 0
            ? { row, col: kept.col }
            : { row: Math.max(0, Math.min(focus.row, rows.length - 1)), col: -1 };
      const ends = kept.selection;
      const anchor = ends?.anchor != null ? (at.get(ends.anchor) ?? -1) : -1;
      const head = ends?.head != null ? (at.get(ends.head) ?? -1) : -1;
      selection = anchor >= 0 && head >= 0 ? { anchor, head } : null;
    } else {
      scroller.scrollTop = 0;
      focus = headAt >= 0 ? { row: -1, col: headAt } : { row: 0, col: -1 };
      selection = null;
      // Nothing in a new answer flashes: only a live read again says what changed.
      flashing = new Set();
    }
    const sample = rows.slice(0, FIRST_PAGE_ROWS);
    columns = [...page.columns];
    // Widths hold for the table's life, from the first rows that showed each column.
    const measured = columnWidths(columns, sample, fields, widths);
    rowLines = measured.lines;
    if (sample.length) {
      widths = measured.widths;
    }
    // A refresh keeps the height measured while the rows' lines are the same.
    if (!kept || rowLines !== linesBefore) {
      rowHeight = ROW_HEIGHT_ESTIMATE_PX[rowLines];
      rowHeightMeasured = false;
    }
    status.textContent = countText(page, isFiltered(state));
    // A live refresh says only what it offers or what failed, each once.
    if (!kept?.live) {
      live.textContent = status.textContent;
    }
    drawNotes();
    if (rows.length === 0) {
      thead.replaceChildren();
      colgroup.replaceChildren();
      tbody.replaceChildren();
      rowElements.clear();
      table.hidden = true;
      fitNote.hidden = true;
      return;
    }
    table.hidden = false;
    if (recordPane.hidden) {
      toolbar.hidden = false;
    }
    table.classList.toggle("table-lines-2", rowLines === 2);
    // A grid whether drawn whole or windowed: its rows take focus and can be selected.
    table.setAttribute("role", "grid");
    table.setAttribute("aria-multiselectable", "true");
    if (windowed) {
      table.setAttribute(
        "aria-rowcount",
        page.count_complete && page.count !== null ? String(page.count + 1) : "-1",
      );
    } else {
      table.removeAttribute("aria-rowcount");
    }
    if (kept) {
      const anchor = kept.anchorKey !== null ? (keyIndex().get(kept.anchorKey) ?? -1) : -1;
      refit(true);
      scroller.scrollTop = anchor >= 0 ? anchor * rowHeight + kept.offset : kept.top;
      if (windowed) {
        drawWindow(true);
      }
      syncFocusable();
      if (kept.hadFocus) {
        focusElement()?.focus({ preventScroll: true });
      }
      return;
    }
    refit(true);
    if (!restorePlace() && focus.row < 0) {
      syncFocusable();
      focusElement()?.focus({ preventScroll: true });
    }
  }

  /** Each held row's index by its key. */
  function keyIndex() {
    return new Map(rows.map((row, index) => [row.key, index]));
  }

  /**
   * The header's controls, in order: each column's sort button, if it sorts, then its
   * menu button. They are the header's stops in the grid's roving focus.
   *
   * @returns {HTMLElement[]}
   */
  function headControls() {
    /** @type {HTMLElement[]} */
    const found = [];
    const row = /** @type {HTMLElement | null} */ (thead.firstChild);
    for (const th of /** @type {HTMLElement[]} */ (Array.from(row?.childNodes ?? []))) {
      for (const node of /** @type {HTMLElement[]} */ (Array.from(th.childNodes ?? []))) {
        if (node.localName === "button") {
          found.push(node);
        }
      }
    }
    return found;
  }

  /** Each shown column's first header control, as headControls counts them. */
  function headStarts() {
    /** @type {number[]} */
    const starts = [];
    let count = 0;
    for (const name of fit.visible) {
      starts.push(count);
      count += fieldsByName.get(name)?.sortable ? 2 : 1;
    }
    return starts;
  }

  /**
   * Choose the columns that fit the scroll box's width, and draw the header and rows
   * again when the choice changed or *force* is set.
   *
   * @param {boolean} [force]
   */
  function refit(force = false) {
    const next = fitColumns({
      columns,
      widths: Object.fromEntries(columns.map((name) => [name, columnPx(name)])),
      chPx: 1,
      fixedPx: positionPx(),
      padPx: 0,
      available: scroller.clientWidth || 0,
      chosen: state.cols !== null,
    });
    const changed =
      next.visible.join("\n") !== fit.visible.join("\n") || next.pinned !== fit.pinned;
    fit = next;
    fitNote.hidden = fit.hidden.length === 0;
    fitNote.textContent = fit.hidden.length
      ? `${fit.hidden.length} ${fit.hidden.length === 1 ? "column" : "columns"} hidden to fit`
      : "";
    if (fit.hidden.length) {
      fitNote.dataset.tipText = `Hidden at this width: ${fit.hidden.join(", ")}. Widen the pane, or choose columns.`;
    }
    table.classList.toggle("table-pinned", fit.pinned);
    // Columns hidden to fit are hidden from the right, so each drawn cell's index is its
    // place among all of them, and the count says there are more.
    if (fit.hidden.length) {
      table.setAttribute(
        "aria-colcount",
        String(fit.visible.length + fit.hidden.length + (positional() ? 1 : 0)),
      );
    } else {
      table.removeAttribute("aria-colcount");
    }
    if (changed || force) {
      drawHeader();
      if (windowed && !printing) {
        drawn = { start: 0, end: 0 };
        drawWindow(true);
      } else {
        drawAllRows();
      }
    }
  }

  /** One character's width in the table's face, and in a literal value's, and a cell's padding. @type {{sans: number, mono: number, pad: number} | null} */
  let chPx = null;
  function measureCh() {
    if (chPx) {
      return chPx;
    }
    /** @param {string} className */
    const width = (className) => {
      const probe = el(
        "span",
        { class: `table-ch-probe ${className}`, "aria-hidden": "true" },
        "0000000000",
      );
      table.append(probe);
      const measured = probe.getBoundingClientRect?.().width ?? 0;
      probe.remove();
      return measured > 0 ? measured / 10 : 8;
    };
    // A cell's padding, both sides: a probe carrying it and nothing else is that wide.
    const padProbe = el("span", { class: "table-pad-probe", "aria-hidden": "true" });
    table.append(padProbe);
    const pad = padProbe.getBoundingClientRect?.().width ?? 0;
    padProbe.remove();
    chPx = { sans: width(""), mono: width("data-literal"), pad: pad > 0 ? pad : CELL_PAD_PX };
    return chPx;
  }

  /**
   * A column's width in pixels: its width in characters, in the face its values are drawn
   * in (a literal's monospaced face is wider than the table's), and the cell's padding.
   *
   * @param {string} name
   */
  function columnPx(name) {
    const ch = measureCh();
    return (
      Math.ceil((widths[name] ?? 8) * (literalField(fieldsByName.get(name)) ? ch.mono : ch.sans)) +
      ch.pad
    );
  }

  /** The row's own column's width in pixels: its largest number, room, and padding; none for keyed rows. */
  function positionPx() {
    if (!positional()) {
      return 0;
    }
    // As many digits as the largest position the table can show: its rows, or a
    // filtered row's place in the file, which can be later than the count.
    const largest = Math.max(
      page?.count ?? 0,
      ...rows.slice(0, FIRST_PAGE_ROWS).map((row) => rowPosition(row.key) ?? 0),
    );
    return Math.ceil((String(largest).length + 2) * measureCh().sans) + measureCh().pad;
  }

  /** Whether rows are named by position, so the row's own column shows its number. */
  function positional() {
    return rows.length > 0 && rowPosition(rows[0].key) !== null;
  }

  function drawHeader() {
    const cols = [];
    const heads = [];
    if (positional()) {
      cols.push(
        el("col", {
          class: "table-col-position",
          style: `width: ${positionPx()}px`,
        }),
      );
      heads.push(
        el("th", { scope: "col", class: "table-position-head", "aria-label": "Row" }, "#"),
      );
    }
    for (const name of fit.visible) {
      const field = fieldsByName.get(name);
      cols.push(el("col", { style: `width: ${columnPx(name)}px` }));
      heads.push(headerCell(name, field));
    }
    colgroup.replaceChildren(...cols);
    // The table is as wide as its columns, so each holds the width its 'col' gives it
    // rather than one its widest value would take.
    const px = fit.visible.reduce((sum, name) => sum + columnPx(name), positionPx());
    table.style.setProperty("width", `${px}px`);
    const row = el("tr", windowed ? { "aria-rowindex": "1" } : {}, ...heads);
    thead.replaceChildren(row);
  }

  /**
   * @param {string} name
   * @param {TableField | undefined} field
   */
  function headerCell(name, field) {
    const title = field?.title || name;
    const sorted = state.sort === name;
    const th = el("th", {
      scope: "col",
      class: field?.numeric ? "data-num" : "",
      "data-field": name,
    });
    if (sorted) {
      th.setAttribute("aria-sort", state.order === "desc" ? "descending" : "ascending");
    }
    if (field?.sortable) {
      const arrow = sorted ? (state.order === "desc" ? " ↓" : " ↑") : "";
      const button = el(
        "button",
        { type: "button", class: "table-sort", "data-field": name, tabindex: "-1" },
        el("span", { class: "table-head-label" }, title),
        el("span", { class: "table-sort-arrow", "aria-hidden": "true" }, arrow),
      );
      button.dataset.tipText = sorted
        ? state.order === "asc"
          ? `Sorted ascending; press to sort descending`
          : `Sorted descending; press to show the table's own order`
        : "Sort ascending";
      th.append(button);
    } else {
      const label = el("span", { class: "table-head-label" }, title);
      if (field?.sort_note) {
        label.dataset.tipText = `Not sortable: ${field.sort_note}`;
      }
      th.append(label);
    }
    th.append(
      el(
        "button",
        {
          type: "button",
          class: "table-head-menu",
          "data-field": name,
          tabindex: "-1",
          "aria-haspopup": "dialog",
          "aria-expanded": "false",
          "aria-label": `${title}: sort, filter, or hide`,
        },
        "▾",
      ),
    );
    return th;
  }

  /** Draw every row held, or for print, the first PRINT_MAX_ROWS of them. */
  function drawAllRows() {
    rowElements.clear();
    const end = printing ? Math.min(rows.length, PRINT_MAX_ROWS) : rows.length;
    const drawnRows = [];
    for (let index = 0; index < end; index++) {
      drawnRows.push(rowElement(rows[index], index));
    }
    tbody.replaceChildren(...drawnRows);
    drawn = { start: 0, end };
    syncFocusable();
    measureRowHeight();
  }

  /**
   * Draw the rows near the view, over two spacers. With *force*, draw them even when the
   * range is the one drawn, as after more rows arrive or the columns change.
   *
   * @param {boolean} [force]
   */
  function drawWindow(force = false) {
    if (!windowed || printing) {
      return;
    }
    const range = windowRange({
      scrollTop: scroller.scrollTop,
      viewport:
        (scroller.clientHeight || rowHeight * 20) - (thead.getBoundingClientRect?.().height ?? 0),
      rowHeight,
      overscan: ROWS_OVERSCAN,
      total: rows.length,
    });
    if (!force && range.start === drawn.start && range.end === drawn.end) {
      maybeReadMore(range);
      return;
    }
    // The keyboard in the grid, on a row this draw replaces; not in a menu or the toolbar.
    const hadFocus = scroller.contains(doc.activeElement);
    drawn = range;
    rowElements.clear();
    const span = fit.visible.length + (positional() ? 1 : 0);
    const before = spacer(range.start * rowHeight, span);
    const after = spacer((rows.length - range.end) * rowHeight, span);
    const drawnRows = [];
    for (let index = range.start; index < range.end; index++) {
      drawnRows.push(rowElement(rows[index], index));
    }
    tbody.replaceChildren(before, ...drawnRows, after);
    syncFocusable();
    if (hadFocus) {
      const target = focusElement();
      if (target) {
        target.focus({ preventScroll: true });
      } else {
        // The focused row scrolled out of the window: keep the keyboard in the grid, and
        // the next key brings the row back.
        scroller.focus({ preventScroll: true });
      }
    }
    if (measureRowHeight()) {
      drawWindow(true);
      return;
    }
    maybeReadMore(range);
  }

  /** @param {{start: number, end: number}} range */
  function maybeReadMore(range) {
    if (!scanPaused && wantsMore(range, rows.length, READ_AHEAD_ROWS)) {
      void readMore();
    }
  }

  /**
   * Take the row height from the first drawn row, once. Returns whether it changed the
   * height the window computes with.
   */
  function measureRowHeight() {
    if (rowHeightMeasured) {
      return false;
    }
    const first = rowElements.get(drawn.start);
    const measured = first?.getBoundingClientRect?.().height ?? 0;
    if (!(measured > 0)) {
      return false;
    }
    rowHeightMeasured = true;
    const changed = Math.abs(measured - rowHeight) > 0.5;
    rowHeight = measured;
    return changed && windowed;
  }

  /**
   * @param {number} height
   * @param {number} span
   */
  function spacer(height, span) {
    return el(
      "tr",
      { class: "table-spacer", "aria-hidden": "true", role: "presentation" },
      el("td", { colspan: String(Math.max(1, span)), style: `height: ${Math.max(0, height)}px` }),
    );
  }

  /**
   * @param {TableRow} row
   * @param {number} index
   * @returns {HTMLTableRowElement}
   */
  function rowElement(row, index) {
    const tr = /** @type {HTMLTableRowElement} */ (
      el("tr", { "data-index": String(index), tabindex: "-1" })
    );
    if (windowed) {
      tr.setAttribute("aria-rowindex", String(index + 2));
    }
    if (flashing.has(row.key)) {
      tr.classList.add("table-row-flash");
    }
    if (
      selection &&
      index >= Math.min(selection.anchor, selection.head) &&
      index <= Math.max(selection.anchor, selection.head)
    ) {
      tr.setAttribute("aria-selected", "true");
    }
    const position = rowPosition(row.key);
    if (position !== null) {
      const link = el(
        "a",
        { class: "table-position", href: recordHref(row.key), tabindex: "-1" },
        String(position),
      );
      tr.append(el("th", { scope: "row", class: "table-position-cell" }, link));
    }
    for (const name of fit.visible) {
      tr.append(cellElement(row.cells[name], fieldsByName.get(name)));
    }
    rowElements.set(index, tr);
    return tr;
  }

  /**
   * @param {unknown} cell
   * @param {TableField | undefined} field
   */
  function cellElement(cell, field) {
    const view = presentCell(cell, field);
    const classes = ["table-cell", `table-cell-${view.kind}`];
    if (view.literal) {
      classes.push("data-literal");
    }
    const td = el("td", field?.numeric ? { class: "data-num" } : {});
    const box = el("div", { class: classes.join(" ") });
    if (view.kind === "ref" && view.ref) {
      const target = referenceTarget(view.ref);
      box.append(
        el(
          "a",
          {
            class: "table-ref",
            href: sdk.navigation.href(target),
            tabindex: "-1",
            "data-ref-table": view.ref.table,
            "data-ref-key": view.ref.key,
          },
          view.text,
        ),
      );
    } else if (view.filter) {
      box.append(
        el(
          "a",
          {
            class: "table-value-filter",
            href: href(withFilter(state, view.filter)),
            tabindex: "-1",
            "data-filter-field": view.filter.field,
            "data-filter-value": view.filter.value ?? "",
          },
          view.text,
        ),
      );
    } else {
      box.append(view.kind === "absent" ? "—" : view.text);
    }
    if ((view.cut !== null || view.size !== null) && view.kind === "text") {
      box.append(el("span", { class: "table-cut", "aria-hidden": "true" }, "…"));
    }
    if (view.missing) {
      box.append(el("span", { class: "table-stored-mark", "aria-label": "missing" }, "missing"));
    }
    if (view.stored) {
      box.append(
        el(
          "span",
          { class: "table-stored-mark", "aria-label": `stored as ${view.stored}` },
          view.stored,
        ),
      );
    }
    if (view.tip) {
      box.dataset.tipText = view.tip;
    }
    td.append(box);
    return td;
  }

  /**
   * The address of the record a reference names. A reference within the table opens on
   * this table's own address; one to another table opens on that table's address, a
   * sibling of this one in its source.
   *
   * @param {{table: string, key: string}} ref
   * @returns {{path: string, query: string}}
   */
  function referenceTarget(ref) {
    const address = referenceAddress(path, tableOf(), ref.table);
    return { path: address, query: stateQuery(withRecord(EMPTY_STATE, ref.key)) };
  }

  /** The table id the schema answered for, "" for a source that is its own table. */
  function tableOf() {
    return tableId;
  }

  function drawEmpty() {
    const refused = page ? sortRefused(page) : null;
    if (refused !== null) {
      // A sort that could not be done in time answers no rows; the table has them.
      const name = fieldsByName.get(refused)?.title || refused;
      // One remedy, the one that always works: the table's own order needs no sort
      // (docs/design-system-messages.md).
      const box = noticeBox(
        "warning",
        `This table is too large to sort by “${name}”.`,
        el(
          "a",
          { href: href(withSort(state, refused, null)), class: "table-unsort" },
          "Show the table’s own order",
        ),
      );
      box.append(".");
      notes.append(box);
      return;
    }
    const filtered = isFiltered(state);
    const message = el(
      "p",
      { class: "table-empty" },
      filtered && page ? `${noMatchText(page)} ` : "This table has no rows.",
    );
    if (filtered) {
      const clear = el(
        "a",
        { href: href(withoutFilter(state)), class: "table-clear" },
        "Clear the search and filters",
      );
      message.append(clear);
    }
    notes.append(message);
  }

  function drawNotes() {
    notes.replaceChildren();
    for (const text of page ? pageNotes(page) : []) {
      notice("warning", text);
    }
    const currentPage = sameRows(answered, state) ? page : null;
    if (scanPaused && currentPage?.next_after) {
      const resume = el(
        "button",
        { type: "button", class: "btn table-continue" },
        isFiltered(state) ? "Continue search" : "Continue reading",
      );
      resume.addEventListener("click", () => {
        resume.setAttribute("disabled", "disabled");
        void readMore();
      });
      notes.append(resume);
    }
    for (const kept of [stateNotice, liveNotice, watchNotice]) {
      if (kept) {
        notes.append(kept);
      }
    }
    if (currentPage && rows.length === 0) {
      drawEmpty();
    }
  }

  /**
   * @param {"warning" | "error"} severity
   * @param {string} text
   * @param {HTMLElement} [extra]
   */
  function notice(severity, text, extra) {
    notes.append(noticeBox(severity, text, extra));
  }

  /**
   * The host's notice: an error is an alert, a warning a status.
   *
   * @param {"warning" | "error"} severity
   * @param {string} text
   * @param {HTMLElement} [extra]
   */
  function noticeBox(severity, text, extra) {
    const box = el(
      "div",
      {
        class: "notice table-notice",
        "data-severity": severity,
        role: severity === "error" ? "alert" : "status",
      },
      text,
    );
    if (extra) {
      box.append(" ", extra);
    }
    return box;
  }

  /** @param {unknown} error */
  function failed(error) {
    page = null;
    rows = [];
    tbody.replaceChildren();
    thead.replaceChildren();
    rowElements.clear();
    table.hidden = true;
    status.textContent = "";
    notes.replaceChildren();
    if (errorCode(error) === "source_unreadable") {
      // The file is there but holds no table, as a JSON document that is not a list of
      // records: the source's own words say why, and no query of the view can change it.
      toolbar.hidden = true;
      notice("warning", errorText(error));
      return;
    }
    notice(
      "error",
      `The table could not be read. ${errorText(error)}`,
      el("a", { href: href(EMPTY_STATE), class: "table-reset" }, "Show the whole table"),
    );
  }

  function drawChips() {
    const made = [];
    if (state.ref) {
      made.push(referenceChip(state.ref, withRef(state, null)));
    }
    for (const filter of state.filters) {
      made.push(
        chip(
          filter.field,
          filterLabel(filter, fieldsByName.get(filter.field)),
          withoutFilter(state, filter.field),
        ),
      );
    }
    chips.replaceChildren(...made);
  }

  /** @param {string} raw @param {TableState} without */
  function referenceChip(raw, without) {
    const boundary = raw.lastIndexOf(":");
    if (boundary < 0) {
      return chip("ref", `Referencing ${raw}`, without);
    }
    const ref = { table: raw.slice(0, boundary), key: raw.slice(boundary + 1) };
    const target = referenceTarget(ref);
    const link = el(
      "a",
      {
        class: "table-open-ref",
        href: sdk.navigation.href(target),
        "data-path": target.path,
        "data-query": target.query,
        "data-tip-text": raw,
      },
      raw,
    );
    const pill = chip("ref", `Referencing ${raw}`, without);
    const label = /** @type {HTMLElement} */ (pill.firstChild);
    const remove = /** @type {HTMLElement} */ (pill.lastChild);
    label.replaceChildren("Referencing ", link);
    void getCard(target.path, ref.key).then(
      (answer) => {
        if (!pill.isConnected) {
          return;
        }
        const display = presentCell(answer.label, undefined);
        if (["text", "number"].includes(display.kind) && display.text) {
          link.textContent = display.text;
          remove.setAttribute("aria-label", `Remove the filter Referencing ${display.text}`);
        }
      },
      () => {},
    );
    return pill;
  }

  /**
   * @param {string} name
   * @param {string} label
   * @param {TableState} without
   */
  function chip(name, label, without) {
    const remove = el(
      "a",
      {
        class: "table-chip-remove",
        href: href(without),
        "aria-label": `Remove the filter ${label}`,
        "data-chip": name,
      },
      "×",
    );
    return el(
      "span",
      { class: "table-chip" },
      el("span", { class: "table-chip-label" }, label),
      remove,
    );
  }

  // ── Focus and selection ──────────────────────────────────────

  /** The element the focus stands on, if it is drawn. */
  function focusElement() {
    if (focus.row < 0) {
      return headControls()[focus.col] ?? null;
    }
    const tr = rowElements.get(focus.row);
    if (!tr) {
      return null;
    }
    if (focus.col < 0) {
      return tr;
    }
    const cells = /** @type {HTMLElement[]} */ (Array.from(tr.childNodes)).filter(
      (node) => node.localName === "td",
    );
    const cell = cells[focus.col];
    if (!cell) {
      return tr;
    }
    const link = /** @type {HTMLElement | undefined} */ (
      Array.from(cell.firstChild?.childNodes ?? []).find(
        (node) => /** @type {HTMLElement} */ (node).localName === "a",
      )
    );
    return link ?? cell;
  }

  /** Make the focused element the grid's one Tab stop. */
  function syncFocusable() {
    for (const [index, tr] of rowElements) {
      tr.setAttribute("tabindex", index === focus.row && focus.col < 0 ? "0" : "-1");
    }
    for (const control of headControls()) {
      control.setAttribute("tabindex", "-1");
    }
    const target = focusElement();
    if (target) {
      target.setAttribute("tabindex", "0");
    }
  }

  /**
   * Move the focus to *next*, scrolling it into the window.
   *
   * @param {GridFocus} next
   */
  function moveFocus(next) {
    const previous = focusElement();
    if (previous && previous.localName !== "tr") {
      previous.setAttribute("tabindex", "-1");
    }
    focus = next;
    if (windowed && !printing && next.row >= 0) {
      revealRow(next.row);
    }
    syncFocusable();
    const target = focusElement();
    if (target) {
      target.focus({ preventScroll: true });
      // The header stays at the top of the box as it scrolls, so it needs no scroll.
      if (!windowed && next.row >= 0) {
        target.scrollIntoView?.({ block: "nearest" });
      }
      showCardFor(target);
    }
    schedulePlace();
  }

  /**
   * Scroll a windowed table so row *index* is in view, and draw it.
   *
   * @param {number} index
   */
  function revealRow(index) {
    const head = thead.getBoundingClientRect?.().height ?? 0;
    const top = index * rowHeight;
    const view = Math.max(rowHeight, (scroller.clientHeight || rowHeight * 20) - head);
    const scrollTop = scroller.scrollTop;
    if (top < scrollTop) {
      scroller.scrollTop = top;
    } else if (top + rowHeight > scrollTop + view) {
      scroller.scrollTop = top + rowHeight - view;
    }
    drawWindow(false);
    if (!rowElements.has(index)) {
      drawWindow(true);
    }
  }

  /** @param {{anchor: number, head: number} | null} next */
  function select(next) {
    selection = next;
    for (const [index, tr] of rowElements) {
      const on =
        next !== null &&
        index >= Math.min(next.anchor, next.head) &&
        index <= Math.max(next.anchor, next.head);
      if (on) {
        tr.setAttribute("aria-selected", "true");
      } else {
        tr.removeAttribute("aria-selected");
      }
    }
  }

  /** @param {KeyboardEvent} event */
  function onKeyDown(event) {
    releasePlace();
    // A chord is the browser's: Command-R reloads, Command-A selects (tests/test_modified_keys.py).
    if (event.altKey || event.ctrlKey || event.metaKey) {
      return;
    }
    const target = /** @type {Node | null} */ (event.target);
    if (target && event.key === "Escape" && !recordPane.hidden && recordPane.contains(target)) {
      // Escape in the record goes back to the table, as its Back link does.
      event.preventDefault();
      closeRecord();
      return;
    }
    if (!target || !scroller.contains(target) || rows.length === 0) {
      return;
    }
    const step = keyStep(focus, event, {
      rows: rows.length,
      cols: fit.visible.length,
      pageRows: Math.max(1, Math.floor((scroller.clientHeight || rowHeight * 10) / rowHeight) - 1),
      heads: headControls().length,
      headStarts: headStarts(),
    });
    if (step.action === "none") {
      return;
    }
    event.preventDefault();
    switch (step.action) {
      case "move":
        select(null);
        moveFocus(step.focus);
        break;
      case "extend":
        select({ anchor: selection?.anchor ?? focus.row, head: step.focus.row });
        moveFocus({ row: step.focus.row, col: -1 });
        break;
      case "open":
        if (rows[focus.row]) {
          openRecord(rows[focus.row].key);
        }
        break;
      case "follow": {
        const link = focusElement();
        if (link?.localName === "a") {
          activateLink(/** @type {HTMLAnchorElement} */ (link));
        } else if (rows[focus.row]) {
          openRecord(rows[focus.row].key);
        }
        break;
      }
    }
  }

  /** @param {ClipboardEvent} event */
  function onCopy(event) {
    if (!selection || !event.clipboardData) {
      return;
    }
    const native = win.getSelection?.();
    if (native && !native.isCollapsed && String(native).length > 0) {
      return;
    }
    const low = Math.min(selection.anchor, selection.head);
    const high = Math.max(selection.anchor, selection.head);
    event.clipboardData.setData(
      "text/plain",
      rowsTsv(fit.visible, rows.slice(low, high + 1), fields),
    );
    event.preventDefault();
  }

  // ── Pointer ──────────────────────────────────────────────────

  /** @param {MouseEvent} event */
  function onClick(event) {
    const target = /** @type {HTMLElement | null} */ (event.target);
    if (!target) {
      return;
    }
    if (target === fitNote) {
      toggleColumnsMenu();
      return;
    }
    if (target === columnsButton || isWithin(target, columnsButton)) {
      toggleColumnsMenu();
      return;
    }
    const menuButton = ancestor(target, (node) => node.classList?.contains("table-head-menu"));
    if (menuButton) {
      toggleHeaderMenu(menuButton);
      return;
    }
    const sort = ancestor(target, (node) => node.classList?.contains("table-sort"));
    if (sort) {
      const name = sort.dataset.field ?? "";
      go(withSort(state, name));
      return;
    }
    const link = /** @type {HTMLAnchorElement | null} */ (
      ancestor(target, (node) => node.localName === "a")
    );
    if (link) {
      if (!plainClick(event)) {
        return;
      }
      event.preventDefault();
      activateLink(link);
      return;
    }
    const tr = ancestor(
      target,
      (node) => node.localName === "tr" && node.dataset.index !== undefined,
    );
    if (tr && plainClick(event) && !hasTextSelection()) {
      const index = Number(tr.dataset.index);
      focus = { row: index, col: -1 };
      openRecord(rows[index].key);
    }
  }

  /**
   * Follow one of the view's own links: a filter, a chip's removal, a reference, a row's
   * number, a refused sort's way back, or a reset.
   *
   * @param {HTMLAnchorElement} link
   */
  function activateLink(link) {
    if (link.classList.contains("table-value-filter")) {
      const field = link.dataset.filterField ?? "";
      // From a record too: the filter shows the table it narrows.
      const filter = {
        field,
        op: /** @type {const} */ ("eq"),
        value: link.dataset.filterValue ?? "",
      };
      go(withRecord(withFilter(state, filter), null));
    } else if (link.classList.contains("table-chip-remove")) {
      const name = link.dataset.chip ?? "";
      go(name === "ref" ? withRef(state, null) : withoutFilter(state, name));
    } else if (link.classList.contains("table-clear")) {
      go(withoutFilter(state));
    } else if (link.classList.contains("table-reset")) {
      go(EMPTY_STATE);
    } else if (link.classList.contains("table-unsort")) {
      go(withSort(state, state.sort ?? "", null));
    } else if (link.classList.contains("table-position")) {
      const tr = ancestor(link, (node) => node.localName === "tr");
      const index = Number(tr?.dataset.index ?? 0);
      focus = { row: index, col: -1 };
      openRecord(rows[index].key);
    } else if (link.classList.contains("table-ref")) {
      const ref = { table: link.dataset.refTable ?? "", key: link.dataset.refKey ?? "" };
      openAddress(referenceTarget(ref));
    } else if (link.classList.contains("table-back")) {
      closeRecord();
    } else if (link.classList.contains("table-open-ref")) {
      openAddress({ path: link.dataset.path ?? path, query: link.dataset.query ?? "" });
    }
  }

  /**
   * Open another table's address, or this table's in another state. The shell keeps the
   * view of the file it shows when only the query changes, so this table's own address is
   * applied here.
   *
   * @param {{path: string, query: string}} target
   */
  function openAddress(target) {
    if (normalPath(target.path) === normalPath(path)) {
      go(parseState(target.query));
      return;
    }
    void sdk.navigation.open(target).catch((/** @type {unknown} */ error) => {
      console.warn("metabrowser table: could not open the table", error);
    });
  }

  /** @param {Event} event */
  function onScroll(event) {
    if (event.target !== scroller) {
      return;
    }
    scheduleWindow();
    hideCard();
    if (pendingPlace) {
      holdPlace();
    } else {
      schedulePlace();
    }
  }

  let frame = 0;
  function scheduleWindow() {
    if (frame || !windowed) {
      return;
    }
    frame = win.requestAnimationFrame(() => {
      frame = 0;
      drawWindow(false);
    });
  }

  /** @type {ReturnType<typeof setTimeout> | 0} */
  let searchTimer = 0;
  function onSearchInput() {
    win.clearTimeout(searchTimer);
    searchTimer = win.setTimeout(() => {
      searchTimer = 0;
      if (search.value.trim() !== state.q) {
        go(withSearch(state, search.value), { replace: true });
      }
    }, SEARCH_DEBOUNCE_MS);
  }

  /** @param {KeyboardEvent} event */
  function onSearchKey(event) {
    if (event.key === "Enter") {
      win.clearTimeout(searchTimer);
      searchTimer = 0;
      if (search.value.trim() !== state.q) {
        go(withSearch(state, search.value), { replace: true });
      }
    }
  }

  // ── Menus ────────────────────────────────────────────────────

  function toggleColumnsMenu() {
    if (openMenu?.opener === columnsButton) {
      closeMenu(true);
      return;
    }
    closeMenu(false);
    const shown = new Set(state.cols ?? fit.visible);
    const menu = el("div", { class: "menu table-menu", role: "dialog", "aria-label": "Columns" });
    const plain = fields.filter((field) => !field.ref);
    const refs = fields.filter((field) => field.ref);
    for (const [heading, group] of /** @type {Array<[string, TableField[]]>} */ ([
      ["Fields", plain],
      ["References", refs],
    ])) {
      if (!group.length) {
        continue;
      }
      menu.append(el("div", { class: "group-heading" }, heading));
      for (const field of group) {
        const box = /** @type {HTMLInputElement} */ (
          el("input", { type: "checkbox", "data-field": field.name })
        );
        box.checked = shown.has(field.name);
        menu.append(
          el("label", { class: "menu-item table-menu-check" }, box, field.title || field.name),
        );
      }
    }
    menu.append(
      el("button", { type: "button", class: "menu-item table-columns-reset" }, "Default columns"),
    );
    menu.addEventListener("change", (event) => {
      const box = /** @type {HTMLInputElement} */ (event.target);
      const name = box.dataset.field ?? "";
      const current = state.cols ? [...state.cols] : [...fit.visible];
      const next = box.checked
        ? fields
            .map((field) => field.name)
            .filter((item) => item === name || current.includes(item))
        : current.filter((item) => item !== name);
      go(withColumns(state, next.length ? next : null), { replace: true });
    });
    menu.addEventListener("click", (event) => {
      if (
        ancestor(/** @type {HTMLElement} */ (event.target), (node) =>
          node.classList?.contains("table-columns-reset"),
        )
      ) {
        go(withColumns(state, null), { replace: true });
        closeMenu(true);
      }
    });
    showMenu(menu, columnsButton);
  }

  /** @param {HTMLElement} button */
  function toggleHeaderMenu(button) {
    if (openMenu?.opener === button) {
      closeMenu(true);
      return;
    }
    closeMenu(false);
    const name = button.dataset.field ?? "";
    const field = fieldsByName.get(name);
    // A dialog, not a menu: it holds a form, and Tab, not the arrows, moves through it.
    const menu = el("div", {
      class: "menu table-menu",
      role: "dialog",
      "aria-label": `${field?.title || name}: sort, filter, or hide`,
    });
    /** @param {string} label @param {() => void} run */
    const item = (label, run) => {
      const control = el("button", { type: "button", class: "menu-item" }, label);
      control.addEventListener("click", () => {
        closeMenu(true);
        run();
      });
      menu.append(control);
    };
    if (field?.sortable) {
      item("Sort ascending", () => go(withSort(state, name, "asc")));
      item("Sort descending", () => go(withSort(state, name, "desc")));
      if (state.sort === name) {
        item("The table's own order", () => go(withSort(state, name, null)));
      }
    } else if (field?.sort_note) {
      menu.append(el("div", { class: "table-menu-note" }, `Not sortable: ${field.sort_note}`));
    }
    if (field?.filterable) {
      menu.append(filterForm(name, field));
    }
    // Which columns show is how the table is viewed, not a step Back walks: the address
    // is replaced, as the Columns menu replaces it.
    item("Hide column", () => {
      const current = state.cols ? [...state.cols] : [...fit.visible];
      const next = current.filter((item) => item !== name);
      go(withColumns(state, next.length ? next : null), { replace: true });
    });
    showMenu(menu, button);
  }

  /**
   * The header menu's filter: an operator and a value, applied with Enter or Filter.
   *
   * @param {string} name
   * @param {TableField} field
   */
  function filterForm(name, field) {
    const current = state.filters.find((filter) => filter.field === name);
    const form = el("form", {
      class: "table-filter-form",
      "aria-label": `Filter ${field.title || name}`,
    });
    const op = /** @type {HTMLSelectElement} */ (
      el("select", { class: "field table-filter-op", "aria-label": "Operator" })
    );
    for (const value of FILTER_OPS) {
      if (value === "contains" && field.type !== "text") {
        continue;
      }
      const option = /** @type {HTMLOptionElement} */ (
        el("option", { value }, FILTER_OP_LABELS[value])
      );
      option.selected = (current?.op ?? "eq") === value;
      op.append(option);
    }
    const value = /** @type {HTMLInputElement} */ (
      el("input", {
        class: "field table-filter-value",
        type: "text",
        "aria-label": "Value",
        spellcheck: "false",
      })
    );
    value.value = current?.value ?? "";
    const submit = el("button", { type: "submit", class: "btn" }, "Filter");
    form.append(op, value, submit);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const chosen = /** @type {import("./table-model.js").TableFilterOp} */ (op.value);
      closeMenu(true);
      go(withFilter(state, { field: name, op: chosen, value: value.value }));
    });
    return form;
  }

  /**
   * @param {HTMLElement} menu
   * @param {HTMLElement} opener
   */
  function showMenu(menu, opener) {
    openMenu = { menu, opener };
    opener.setAttribute("aria-expanded", "true");
    // Focusable itself, so a press on its text keeps the focus in it; it closes when the
    // focus leaves it for anything but its opener, as Tab past its last control does.
    menu.setAttribute("tabindex", "-1");
    root.append(menu);
    dismissal?.opened();
    const anchor = opener.getBoundingClientRect?.();
    const frameBox = root.getBoundingClientRect?.();
    if (anchor && frameBox) {
      menu.style.setProperty("top", `${anchor.bottom - frameBox.top + 2}px`);
      menu.style.setProperty("left", `${Math.max(0, anchor.left - frameBox.left)}px`);
    }
    const first = /** @type {HTMLElement | null} */ (
      menu.querySelector?.("button, input, select") ?? null
    );
    first?.focus();
  }

  /** @param {boolean} restore */
  function closeMenu(restore) {
    if (!openMenu) {
      return;
    }
    const { menu, opener } = openMenu;
    openMenu = null;
    dismissal?.closed();
    opener.setAttribute("aria-expanded", "false");
    menu.remove();
    if (restore && opener.isConnected) {
      opener.focus();
    }
  }

  function onPointerDown() {
    releasePlace();
  }

  // ── The record ───────────────────────────────────────────────

  /** @param {string} key */
  function openRecord(key) {
    const next = withRecord(state, key);
    // go writes the place to the table's entry before it pushes the record's.
    go(next);
    pushedRecord = stateQuery(next);
  }

  /**
   * Back to the table. When the browser's address is the record entry this view pushed
   * from the grid, the table's entry is the one behind it, so this is Back. Otherwise (a
   * record opened from its link, one a link inside a record opened, or a push the browser
   * dropped, which left the address as it was) the table's address replaces the entry, so
   * the reader never leaves the table for whatever page came before it.
   */
  function closeRecord() {
    const behind = pushedRecord !== null && addressQuery() === pushedRecord;
    pushedRecord = null;
    if (behind) {
      history.back();
      return;
    }
    go(withRecord(state, null), { replace: true });
  }

  /**
   * The query the browser's address holds, as the view writes it, or null when it cannot
   * be read. The shell's own target follows the view even when the browser drops a
   * history write; the address does not.
   */
  function addressQuery() {
    try {
      return stateQuery(parseState((loc.search ?? "").replace(/^\?/, "")));
    } catch {
      return null;
    }
  }

  let recordSeq = 0;
  /**
   * @param {string} key
   * @param {boolean} [again] a live refresh of the record on screen
   */
  async function showRecord(key, again = false) {
    const seq = ++recordSeq;
    if (!again) {
      hideCard();
      closeMenu(false);
      toolbar.hidden = true;
      notes.hidden = true;
      scroller.hidden = true;
      recordPane.hidden = false;
      recordPane.setAttribute("aria-busy", "true");
    }
    /** @type {Record<string, string>} */
    const params = { key };
    if (!again && page?.generation && rowPosition(key) !== null) {
      params.generation = page.generation;
    }
    try {
      const record = /** @type {RecordAnswer} */ (
        /** @type {unknown} */ (await ask("record", params, abort.signal))
      );
      if (seq !== recordSeq || disposed) {
        return;
      }
      if (fields.length === 0) {
        await schemaReady;
      }
      // A row named by position may be another row once its file changed: the server
      // says so for a key read under an older generation, and the view when a live
      // refresh finds other cells at the position.
      const cells = JSON.stringify(record.cells);
      const shown = shownRecord;
      if (shownRecord.key !== key) {
        shownRecord = { key, cells, moved: false };
      } else if (again && record.positional && cells !== shownRecord.cells) {
        shownRecord = { key, cells, moved: true };
      } else if (again) {
        shownRecord = { ...shownRecord, cells };
      }
      if (
        again &&
        shown.key === key &&
        shown.cells === cells &&
        shown.moved === shownRecord.moved
      ) {
        // Read again and the same: the pane, its focus, its scroll, and any text selected
        // in it stay as they are.
        return;
      }
      drawRecord(shownRecord.moved ? { ...record, generation_moved: true } : record, again);
    } catch (error) {
      if (seq !== recordSeq || disposed || isAbort(error)) {
        return;
      }
      releaseRecord();
      recordPane.replaceChildren(
        backLink(),
        noticeBox("error", `This record could not be read. ${errorText(error)}`),
      );
    } finally {
      if (seq === recordSeq) {
        recordPane.removeAttribute("aria-busy");
      }
    }
  }

  /**
   * @typedef {{
   *   key: string,
   *   positional: boolean,
   *   label?: string,
   *   generation_moved?: boolean | null,
   *   cells: Record<string, unknown>,
   *   referenced_by: Array<{table: string, fields: string[], to: string[], count: number, count_complete: boolean}>,
   * }} RecordAnswer
   */

  /** Dispose of what the open record's JSON values drew. */
  function releaseRecord() {
    const mounts = recordMounts;
    recordMounts = [];
    for (const mount of mounts) {
      mount.dispose?.();
    }
  }

  /**
   * @param {RecordAnswer} record
   * @param {boolean} [again] a live redraw, which keeps the focus on its control and the
   *   pane's scroll, where a record opened puts the focus on Back
   */
  function drawRecord(record, again = false) {
    const focused = again
      ? [...recordControls].find(([, control]) => control === doc.activeElement)?.[0]
      : undefined;
    const scrolled = recordPane.scrollTop;
    recordControls = new Map();
    releaseRecord();
    const position = rowPosition(record.key);
    const heading = el(
      "h2",
      { class: "table-record-title" },
      record.label || (position !== null ? `Row ${formatCount(position)}` : recordLabel(record)),
    );
    const back = backLink();
    recordControls.set("back", back);
    recordControls.set("live", recordPill);
    const head = el("div", { class: "table-record-head" }, back, heading, recordPill);
    const parts = [head];
    if (record.positional) {
      parts.push(
        el(
          "p",
          { class: "table-record-note" },
          record.label && position !== null
            ? `Row ${formatCount(position)}. This row is named by its position in the table.`
            : "This row is named by its position in the table.",
        ),
      );
    }
    if (record.generation_moved) {
      parts.push(
        noticeBox(
          "warning",
          "This table changed since this row was read, so the row at this position may be a different one.",
        ),
      );
    }
    const list = el("dl", { class: "table-record-fields" });
    for (const field of fields) {
      const cell = record.cells[field.name];
      const view = presentCell(cell, field);
      const dt = el(
        "dt",
        {},
        field.title || field.name,
        el("span", { class: "table-record-type" }, field.type),
      );
      const dd = el("dd", {});
      const value = el("div", {
        class: `table-record-value table-cell-${view.kind}${view.literal ? " data-literal" : ""}${field.numeric ? " data-num-value" : ""}`,
      });
      if (view.kind === "ref" && view.ref) {
        const link = el(
          "a",
          {
            class: "table-ref",
            href: sdk.navigation.href(referenceTarget(view.ref)),
            "data-ref-table": view.ref.table,
            "data-ref-key": view.ref.key,
          },
          view.text,
        );
        recordControls.set(`field:${field.name}`, link);
        value.append(link);
      } else if (view.filter) {
        const link = el(
          "a",
          {
            class: "table-value-filter",
            href: href(withRecord(withFilter(state, view.filter), null)),
            "data-filter-field": view.filter.field,
            "data-filter-value": view.filter.value ?? "",
          },
          view.text,
        );
        recordControls.set(`field:${field.name}`, link);
        value.append(link);
      } else if (view.kind === "json" && ctx.renderJson && jsonValue(cell)) {
        value.classList.add("table-record-json");
        const mount = ctx.renderJson(value, jsonValue(cell)?.value);
        if (mount) {
          recordMounts.push(mount);
        }
      } else {
        value.append(view.kind === "absent" ? `${ABSENT_TEXT}.` : view.text);
      }
      dd.append(value);
      if (view.cut !== null && view.kind === "text") {
        dd.append(
          el(
            "p",
            { class: "table-record-note" },
            `Showing the first ${formatCount(view.text.length)} of ${formatCount(view.cut)} characters.`,
          ),
        );
      }
      if (view.size !== null && view.kind === "text") {
        dd.append(
          el(
            "p",
            { class: "table-record-note" },
            `Showing the first ${formatCount(view.text.length)} characters of ${formatCount(view.size)} bytes.`,
          ),
        );
      }
      if (view.missing) {
        dd.append(
          el("p", { class: "table-record-note" }, "No row of the referenced table has this value."),
        );
      }
      if (view.stored) {
        dd.append(
          el("p", { class: "table-record-note" }, `Stored as ${view.stored}, not ${field.type}.`),
        );
      }
      if (view.invalid) {
        dd.append(
          el(
            "p",
            { class: "table-record-note" },
            "Not valid UTF-8: unreadable bytes are shown as �.",
          ),
        );
      }
      list.append(dt, dd);
    }
    parts.push(list);
    if (record.referenced_by.length) {
      const section = el(
        "section",
        { class: "table-record-backrefs" },
        el("h3", { class: "table-record-subtitle" }, "Referenced by"),
      );
      for (const ref of record.referenced_by) {
        const count = `${ref.count_complete ? "" : "at least "}${formatCount(ref.count)}`;
        const target = {
          path: referenceAddress(path, tableOf(), ref.table),
          query: stateQuery(
            withRef(
              EMPTY_STATE,
              `${tableOf()}:${record.key}`,
              JSON.stringify([ref.fields, ref.to]),
            ),
          ),
        };
        const open = el(
          "a",
          {
            class: "table-open-ref",
            href: sdk.navigation.href(target),
            "data-path": target.path,
            "data-query": target.query,
          },
          "Open as table",
        );
        recordControls.set(`referenced:${ref.table}:${ref.fields.join(",")}`, open);
        section.append(
          el(
            "p",
            { class: "table-record-backref" },
            `${ref.table} (${ref.fields.join(", ")}): ${count} `,
            open,
          ),
        );
      }
      parts.push(section);
    }
    recordPane.replaceChildren(...parts);
    if (!again) {
      back.focus({ preventScroll: true });
      return;
    }
    recordPane.scrollTop = scrolled;
    if (focused !== undefined) {
      (recordControls.get(focused) ?? back).focus({ preventScroll: true });
    }
  }

  /** @param {RecordAnswer} record */
  function recordLabel(record) {
    const first = fields[0];
    const view = first ? presentCell(record.cells[first.name], first) : null;
    return view?.text ? view.text : "Record";
  }

  function backLink() {
    return el(
      "a",
      { class: "table-back", href: href(withRecord(state, null)) },
      "← Back to the table",
    );
  }

  function showGrid() {
    recordSeq += 1;
    shownRecord = { key: "", cells: "", moved: false };
    releaseRecord();
    // The keyboard was in the record: it goes back to the row the record was opened from.
    const refocus = recordPane.contains(doc.activeElement);
    recordPane.hidden = true;
    recordPane.replaceChildren();
    toolbar.hidden = false;
    notes.hidden = false;
    scroller.hidden = false;
    restorePlace();
    if (refocus) {
      focusElement()?.focus({ preventScroll: true });
    }
  }

  // ── Hover cards ──────────────────────────────────────────────

  /** @type {ReturnType<typeof setTimeout> | 0} */
  let cardTimer = 0;
  /** @type {HTMLElement | null} */
  let cardAnchor = null;

  /** @param {HTMLElement | null} target */
  function showCardFor(target) {
    if (target?.classList?.contains("table-ref")) {
      scheduleCard(target);
    } else {
      hideCard();
    }
  }

  /** @param {HTMLElement} anchor */
  function scheduleCard(anchor) {
    if (cardAnchor === anchor) {
      return;
    }
    hideCard();
    cardAnchor = anchor;
    cardTimer = win.setTimeout(() => {
      cardTimer = 0;
      void showCard(anchor);
    }, CARD_DELAY_MS);
  }

  /** @param {HTMLElement} anchor */
  async function showCard(anchor) {
    const ref = { table: anchor.dataset.refTable ?? "", key: anchor.dataset.refKey ?? "" };
    const address = referenceAddress(path, tableOf(), ref.table);
    let answer;
    try {
      answer = await getCard(address, ref.key);
    } catch {
      return;
    }
    if (cardAnchor !== anchor || disposed || !anchor.isConnected) {
      return;
    }
    sdk.tooltip?.show(cardHtml(answer), anchor);
  }

  /** @param {string} address @param {string} key */
  async function getCard(address, key) {
    const cacheKey = `${address}\n${key}`;
    let card = cards.get(cacheKey);
    if (!card) {
      const asked = sdk.fetchPluginData(
        "table",
        "card",
        { path: address, key },
        { signal: abort.signal },
      );
      asked.catch(() => cards.delete(cacheKey));
      cards.set(cacheKey, asked);
      card = asked;
    }
    return /** @type {{label: unknown, cells: Record<string, unknown>}} */ (await card);
  }

  /** @param {{label: unknown, cells: Record<string, unknown>}} answer */
  function cardHtml(answer) {
    const esc = sdk.escapeHtml;
    const label = presentCell(answer.label, undefined).text;
    const lines = Object.entries(answer.cells).map(
      ([name, cell]) =>
        `<div class="table-card-field"><span class="table-card-name">${esc(name)}</span> ${esc(presentCell(cell, undefined).text)}</div>`,
    );
    return `<div class="table-card"><div class="table-card-label">${esc(label)}</div>${lines.join("")}</div>`;
  }

  function hideCard() {
    if (cardTimer) {
      win.clearTimeout(cardTimer);
      cardTimer = 0;
    }
    if (cardAnchor) {
      sdk.tooltip?.hide(cardAnchor);
      cardAnchor = null;
    }
  }

  /** @param {PointerEvent} event */
  function onPointerOver(event) {
    const ref = ancestor(/** @type {HTMLElement} */ (event.target), (node) =>
      node.classList?.contains("table-ref"),
    );
    if (ref) {
      scheduleCard(ref);
    }
  }

  /** @param {PointerEvent} event */
  function onPointerOut(event) {
    const ref = ancestor(/** @type {HTMLElement} */ (event.target), (node) =>
      node.classList?.contains("table-ref"),
    );
    const to = /** @type {Node | null} */ (event.relatedTarget);
    if (ref && !(to && ref.contains(to))) {
      hideCard();
    }
  }

  // ── Place: scroll and focus kept across Back ─────────────────

  /** @type {ReturnType<typeof setTimeout> | 0} */
  let placeTimer = 0;
  /**
   * A place read from the history entry, held until the reader acts (a key, a press, a
   * wheel, or a touch in the view). While it is held a scroll the reader did not make is
   * put back, and no place is written, so a scroll the browser clamped or reset does not
   * replace it: on a fresh load the shell takes the view's host out of the page and puts
   * it back after the first draw, which resets every scroll in it to the top (seen in
   * Chrome 152, 2026-11-20), and a box not yet as tall as the place clamps it.
   * @type {{query: string, top: number, row: number} | null}
   */
  let pendingPlace = null;
  let placeTries = 0;
  let placeFrame = 0;

  /** The reader acted: the place is theirs from here, and is written as it moves. */
  function releasePlace() {
    pendingPlace = null;
    if (placeFrame) {
      win.cancelAnimationFrame(placeFrame);
      placeFrame = 0;
    }
  }

  /** Write the place once a pause after the last move or scroll (PLACE_SAVE_MS). */
  function schedulePlace() {
    if (placeTimer) {
      win.clearTimeout(placeTimer);
    }
    placeTimer = win.setTimeout(() => {
      placeTimer = 0;
      rememberPlace();
    }, PLACE_SAVE_MS);
  }

  function cancelPlace() {
    if (placeTimer) {
      win.clearTimeout(placeTimer);
      placeTimer = 0;
    }
  }

  /** Write the place now, if it moved since it was written: before navigating, or hiding. */
  function flushPlace() {
    cancelPlace();
    rememberPlace();
  }

  function rememberPlace() {
    if (disposed || !recordPane.hidden || pendingPlace || !page) {
      return;
    }
    const place = {
      query: stateQuery(withRecord(state, null)),
      top: scroller.scrollTop,
      row: Math.max(0, focus.row),
    };
    const saved = /** @type {{query?: string, top?: number, row?: number} | undefined} */ (
      history.state?.[PLACE_KEY]
    );
    if (
      saved &&
      saved.query === place.query &&
      saved.top === place.top &&
      saved.row === place.row
    ) {
      return;
    }
    try {
      history.replaceState({ ...(history.state ?? {}), [PLACE_KEY]: place }, "");
    } catch {
      // A browser that refuses the write (WebKit past its rate) keeps the place unsaved.
    }
  }

  /**
   * The place the history entry holds for *question*, if it holds one.
   *
   * @param {TableState} question
   * @returns {{query: string, top: number, row: number} | null}
   */
  function savedPlace(question) {
    const place = /** @type {{query: string, top: number, row: number} | undefined} */ (
      history.state?.[PLACE_KEY]
    );
    return place && place.query === stateQuery(withRecord(question, null)) ? place : null;
  }

  /** Put the reader back where the history entry says they were. Returns whether it had a place. */
  function restorePlace() {
    const place = savedPlace(state);
    if (!place || rows.length === 0) {
      return false;
    }
    focus = { row: Math.min(place.row, rows.length - 1), col: -1 };
    pendingPlace = place;
    placeTries = 0;
    applyPlace();
    return true;
  }

  /**
   * Scroll to the held place. A box that cannot reach it yet (not laid out, or not as
   * tall) is tried again on the next frames, and when it is resized, for PLACE_TRIES
   * frames, and then let go.
   */
  function applyPlace() {
    placeFrame = 0;
    const place = pendingPlace;
    if (!place || disposed) {
      return;
    }
    scroller.scrollTop = place.top;
    if (windowed) {
      drawWindow(true);
    }
    syncFocusable();
    if (Math.abs(scroller.scrollTop - place.top) < 1) {
      placeTries = 0;
      return;
    }
    if (placeTries >= PLACE_TRIES) {
      releasePlace();
      return;
    }
    placeTries += 1;
    placeFrame = win.requestAnimationFrame(applyPlace);
  }

  /** A scroll while a place is held that the reader did not make: back to the place. */
  function holdPlace() {
    if (pendingPlace && !placeFrame && Math.abs(scroller.scrollTop - pendingPlace.top) >= 1) {
      placeFrame = win.requestAnimationFrame(applyPlace);
    }
  }

  // ── Print ────────────────────────────────────────────────────

  function onBeforePrint() {
    if (windowed && page) {
      printing = true;
      drawAllRows();
      // The toolbar, with the count, is not printed: the page says which rows are, when
      // rows past them were not read or past the most a printout draws.
      const printed = drawn.end;
      if (page.next_after || printed < rows.length) {
        const total =
          page.count_complete && page.count !== null
            ? ` of ${formatCount(page.count)}`
            : page.count !== null
              ? ` of at least ${formatCount(page.count)}`
              : "";
        const why =
          printed < rows.length
            ? `A printout holds at most ${formatCount(PRINT_MAX_ROWS)} rows; search or filter for the ones to print.`
            : "The rows after them were not read, so they are not printed.";
        printNote.textContent = `Rows 1 to ${formatCount(printed)}${total}. ${why}`;
      }
    }
  }

  function onAfterPrint() {
    if (printing) {
      printing = false;
      printNote.textContent = "";
      drawn = { start: 0, end: 0 };
      drawWindow(true);
    }
  }

  function onPageHide() {
    flushPlace();
  }

  function onVisibilityChange() {
    if (doc.visibilityState === "hidden") {
      flushPlace();
    }
  }

  // ── Wiring ───────────────────────────────────────────────────

  /** @type {ResizeObserver | null} */
  let resize = null;
  if (typeof ResizeObserver === "function") {
    resize = new ResizeObserver(() => {
      if (page && rows.length) {
        refit(false);
        scheduleWindow();
        applyPlace();
      }
    });
    resize.observe(scroller);
  }
  root.addEventListener("click", onClick);
  root.addEventListener("keydown", onKeyDown);
  root.addEventListener("copy", onCopy);
  root.addEventListener("pointerdown", onPointerDown);
  root.addEventListener("pointerover", onPointerOver);
  root.addEventListener("pointerout", onPointerOut);
  root.addEventListener("focusin", (event) => {
    const target = /** @type {HTMLElement} */ (event.target);
    // A header control the pointer focused is where the keyboard's roving focus stands.
    const head = headControls().indexOf(target);
    if (head >= 0 && (focus.row >= 0 || focus.col !== head)) {
      focus = { row: -1, col: head };
      syncFocusable();
    }
    showCardFor(target);
  });
  scroller.addEventListener("scroll", onScroll, { passive: true });
  scroller.addEventListener("wheel", releasePlace, { passive: true });
  scroller.addEventListener("touchstart", releasePlace, { passive: true });
  search.addEventListener("input", onSearchInput);
  search.addEventListener("keydown", onSearchKey);
  win.addEventListener("popstate", onPopState);
  win.addEventListener("beforeprint", onBeforePrint);
  win.addEventListener("afterprint", onAfterPrint);
  livePill.addEventListener("click", togglePaused);
  recordPill.addEventListener("click", togglePaused);
  offer.addEventListener("click", () => {
    drawOffer(0);
    void liveRefresh(true);
  });
  doc.addEventListener?.("visibilitychange", onVisibility);
  win.addEventListener("pagehide", onPageHide);
  win.addEventListener("visibilitychange", onVisibilityChange);
  scroller.setAttribute("tabindex", "-1");
  search.value = state.q;
  drawChips();

  const schemaReady = loadSchema();
  const ready = (async () => {
    try {
      await schemaReady;
    } catch (error) {
      if (!disposed && !isAbort(error)) {
        failed(error);
      }
      return;
    }
    drawChips();
    if (state.record) {
      void showRecord(state.record);
    }
    await loadRows();
  })();

  return {
    ready,
    state: () => state,
    /**
     * Ask the current question again and draw its new answer in place: the focused row,
     * the row at the top of the view, and the selection stay, by key, when the answer
     * still holds them. For a source whose content changes under the view.
     */
    refresh() {
      if (disposed) {
        return Promise.resolve();
      }
      return loadRows({ keep: true });
    },
    dispose() {
      if (disposed) {
        return;
      }
      disposed = true;
      abort.abort();
      loading?.abort();
      resize?.disconnect();
      if (frame) {
        win.cancelAnimationFrame(frame);
      }
      win.clearTimeout(searchTimer);
      win.clearTimeout(placeTimer);
      win.clearTimeout(liveTimer);
      win.clearTimeout(flashTimer);
      unwatch?.();
      unwatch = null;
      releasePlace();
      hideCard();
      sdk.tooltip?.hide(root);
      closeMenu(false);
      dismissal?.dispose();
      win.removeEventListener("popstate", onPopState);
      win.removeEventListener("beforeprint", onBeforePrint);
      win.removeEventListener("afterprint", onAfterPrint);
      doc.removeEventListener?.("visibilitychange", onVisibility);
      win.removeEventListener("pagehide", onPageHide);
      win.removeEventListener("visibilitychange", onVisibilityChange);
      releaseRecord();
      rowElements.clear();
    },
  };

  // ── Helpers ──────────────────────────────────────────────────

  /**
   * @param {string} tag
   * @param {Record<string, string>} attrs
   * @param {...(Node | string)} children
   * @returns {HTMLElement}
   */
  function el(tag, attrs, ...children) {
    const node = doc.createElement(tag);
    for (const [name, value] of Object.entries(attrs)) {
      if (name === "hidden") {
        node.hidden = true;
      } else if (value !== "") {
        node.setAttribute(name, value);
      }
    }
    node.append(...children);
    return node;
  }

  /**
   * The nearest of *node* and its ancestors, inside the view, for which *test* holds.
   *
   * @param {HTMLElement | null} node
   * @param {(node: HTMLElement) => boolean} test
   * @returns {HTMLElement | null}
   */
  function ancestor(node, test) {
    for (let at = node; at && at !== root; at = /** @type {HTMLElement | null} */ (at.parentNode)) {
      if (test(at)) {
        return at;
      }
    }
    return null;
  }

  /** @param {HTMLElement} node @param {HTMLElement} within */
  function isWithin(node, within) {
    return within.contains(node);
  }

  function hasTextSelection() {
    const selected = win.getSelection?.();
    return Boolean(selected && !selected.isCollapsed && String(selected).length > 0);
  }
}

/**
 * The address of *table* in the source whose table at *address* is *current*: the same
 * address for the same table, and otherwise its sibling in the source, `<source>/<table>`.
 *
 * @param {string} address
 * @param {string} current
 * @param {string} table
 */
export function referenceAddress(address, current, table) {
  if (table === current) {
    return address;
  }
  const source =
    current && address.endsWith(`/${current}`) ? address.slice(0, -(current.length + 1)) : address;
  return table ? `${source}/${table}` : source;
}

/** @param {string} value */
function normalPath(value) {
  return value.replace(/\/$/, "");
}

/** @param {MouseEvent} event */
function plainClick(event) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

/** @param {unknown} error */
function isAbort(error) {
  return /** @type {{name?: string}} */ (error)?.name === "AbortError";
}

/**
 * A refusal's code, from the route's `table_error` body, or "".
 *
 * @param {unknown} error
 */
function errorCode(error) {
  const payload = /** @type {{payload?: {code?: unknown}}} */ (error)?.payload;
  return typeof payload?.code === "string" ? payload.code : "";
}

/**
 * A refusal's own words, from the route's `table_error` body, or the error's message.
 *
 * @param {unknown} error
 */
function errorText(error) {
  const payload = /** @type {{payload?: {error?: unknown}}} */ (error)?.payload;
  const text = typeof payload?.error === "string" ? payload.error : "";
  if (text) {
    return `${text.charAt(0).toUpperCase()}${text.slice(1)}${/[.!?]$/.test(text) ? "" : "."}`;
  }
  return "Try again.";
}
