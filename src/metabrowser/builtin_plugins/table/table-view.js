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
// is read whole and drawn as a plain <table>, so find in page, select all, copy, and print
// are the browser's. A larger one is a role="grid" whose body draws only the rows near the
// view over two spacers, at one fixed row height, reading the next page as the reader
// nears the last row held. There, Search stands in for find in page, Shift with Up or Down
// and Control-A or Command-A select rows that copy as tab-separated values, and print
// draws every row held, as docs/large-content-rendering.md asks of a windowed view.
//
// The keyboard. The grid is one Tab stop with roving focus: Up and Down, or `k` and `j`,
// move a row; Left and Right move from the row to its cells, so a link in a cell is
// reachable; Enter on the row opens its record, and on a cell follows its link.

import {
  columnWidths,
  countText,
  EMPTY_STATE,
  FILTER_OP_LABELS,
  FILTER_OPS,
  filterLabel,
  fitColumns,
  formatCount,
  isFiltered,
  keyStep,
  pageNotes,
  parseState,
  positionOf,
  presentCell,
  reconcileState,
  rowsParams,
  rowsTsv,
  sameRows,
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
// Measured with tests/dom/table-view-measure.mjs in headless Chrome 152 on a shared
// 4-processor Linux container (2026-11-20), over a 12-column table of short text, numbers,
// dates, and booleans, in a 1,280 x 800 window; rerun it for the current numbers.

// The most rows a table may hold and still be read and drawn whole, keeping the browser's
// own find, select all, copy, and print. Drawing a whole table is linear in its rows: 500
// rows took 52 to 61 ms from the answer to the first paint, 1,000 rows 98 to 117 ms,
// 2,000 rows 190 to 236 ms, and 4,000 rows 385 to 462 ms, against 22 to 30 ms for the
// window at any size. A thousand rows keeps a whole table's first paint near a tenth of
// a second, under the 0.2 s past which a click stops feeling immediate.
export const WHOLE_TABLE_MAX_ROWS = 1000;

// Rows the first request asks for: a screen of them several times over, so a windowed
// table scrolls a while before its next request, in one answer the server encodes in a
// few milliseconds (TABLE_PAGE_ROWS_DEFAULT's measurement in table_source.py).
export const FIRST_PAGE_ROWS = 200;

// Rows each later request asks for: as many as the route gives at once
// (TABLE_PAGE_ROWS_MAX), so reading a whole table of WHOLE_TABLE_MAX_ROWS takes one more
// request and a long scroll asks seldom.
export const NEXT_PAGE_ROWS = 1000;

// A row's height before the first row is measured, by its line count, so the window's
// first draw places its spacers near where they end up. One line of the 14 px body text
// with the cell's padding measured 29 px and two lines 47 px; the view measures its first
// drawn row and uses that.
export const ROW_HEIGHT_ESTIMATE_PX = Object.freeze({ 1: 29, 2: 47 });

// Rows the window draws past each edge of the view, so a scroll by the wheel or a key
// shows rows already drawn. A window of the view's rows and 12 past each edge redrew in
// 2 to 4 ms per step at 12 columns; a wheel step moves about three rows and a Page Down a
// view's height, so twelve rows keeps a fast wheel from showing a blank band at 60 Hz,
// where six showed one.
export const ROWS_OVERSCAN = 12;

// How near the last row held, in rows, the window comes before the next page is read.
export const READ_AHEAD_ROWS = 100;

// The pause after the reader stops typing in Search before the table asks again: the same
// a quarter-second the shell's filter fields wait.
export const SEARCH_DEBOUNCE_MS = 250;

// How long the pointer rests on a reference before its hover card is read, and how long
// after it leaves before the card is put away.
export const CARD_DELAY_MS = 300;

/** The history state key under which the view keeps its scroll and focused row. */
const PLACE_KEY = "metabrowserTablePlace";

/**
 * What the view needs from its host: the SDK, and the platform services it uses, so the
 * browserless session can supply its own.
 *
 * @typedef {{
 *   fetchPluginData: Window["metabrowser"]["fetchPluginData"],
 *   navigation: Window["metabrowser"]["navigation"],
 *   tooltip?: Window["metabrowser"]["tooltip"],
 *   escapeHtml: Window["metabrowser"]["escapeHtml"],
 *   formatInteger?: Window["metabrowser"]["formatInteger"],
 * }} TableSdk
 */
/**
 * @typedef {{
 *   sdk?: TableSdk,
 *   window?: Pick<Window, "addEventListener" | "removeEventListener" | "requestAnimationFrame" | "cancelAnimationFrame" | "setTimeout" | "clearTimeout" | "getSelection">,
 *   history?: Pick<History, "back" | "replaceState" | "state">,
 *   document?: Document,
 * }} TableHost
 */
/**
 * @typedef {{
 *   ready: Promise<void>,
 *   dispose(): void,
 *   state(): TableState,
 * }} TableHandle
 */

/**
 * Mount the table at *ctx.path*, the address of one table, into *container*.
 *
 * @param {HTMLElement} container
 * @param {{path: string}} ctx
 * @param {TableHost} [host]
 * @returns {TableHandle}
 */
export function mountTable(container, ctx, host = {}) {
  const sdk = /** @type {TableSdk} */ (host.sdk ?? window.metabrowser);
  const win = host.window ?? window;
  const history = host.history ?? window.history;
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
  /** @type {TablePage | null} */
  let page = null;
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
  let printing = false;
  /** Whether this view pushed the open record's history entry, so Back returns. */
  let recordOpenedHere = false;
  /** @type {Map<number, HTMLTableRowElement>} */
  const rowElements = new Map();
  /** @type {Map<string, Promise<unknown>>} */
  const cards = new Map();

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
      "aria-haspopup": "true",
      "aria-expanded": "false",
    },
    "Columns",
  );
  toolbar.append(search, chips, status, fitNote, columnsButton);
  const notes = el("div", { class: "table-notes" });
  const scroller = el("div", { class: "table-scroll" });
  const table = /** @type {HTMLTableElement} */ (el("table", { class: "data-grid" }));
  const colgroup = el("colgroup", {});
  const thead = el("thead", {});
  const tbody = el("tbody", {});
  table.append(colgroup, thead, tbody);
  scroller.append(table);
  const recordPane = el("div", { class: "table-record", hidden: "" });
  const live = el("div", { class: "sr-only", "aria-live": "polite" });
  const fitStyle = el("style", {});
  root.append(fitStyle, toolbar, notes, scroller, recordPane, live);
  container.replaceChildren(root);
  /** The open menu, and the control that opened it. @type {{menu: HTMLElement, opener: HTMLElement} | null} */
  let openMenu = null;

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
    return sdk.navigation.href(query ? { path, query } : { path });
  }

  function onPopState() {
    if (disposed) {
      return;
    }
    const current = sdk.navigation.current();
    if (current && normalPath(current.path) === normalPath(path)) {
      recordOpenedHere = false;
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
   * @param {Record<string, string>} params
   * @param {AbortSignal} signal
   */
  function ask(route, params, signal) {
    return sdk.fetchPluginData("table", route, { path, ...params }, { signal });
  }

  async function loadSchema() {
    const schema = /** @type {{fields: TableField[]}} */ (
      /** @type {unknown} */ (await ask("schema", {}, abort.signal))
    );
    fields = schema.fields;
    fieldsByName = new Map(fields.map((field) => [field.name, field]));
    const reconciled = reconcileState(state, fields);
    if (reconciled.dropped.length) {
      state = reconciled.state;
      notice(
        "warning",
        `This table has no ${reconciled.dropped.map((name) => `“${name}”`).join(", ")} now, so the view no longer uses it.`,
      );
      const query = stateQuery(state);
      void sdk.navigation
        .open(query ? { path, query } : { path }, { replace: true })
        .catch(() => {});
    }
  }

  /** Read the first page of the current question, and the rest of a table small enough to draw whole. */
  async function loadRows() {
    const seq = ++loadSeq;
    loading?.abort();
    const controller = new AbortController();
    loading = controller;
    abort.signal.addEventListener("abort", () => controller.abort(), { once: true });
    const question = state;
    root.setAttribute("aria-busy", "true");
    try {
      const first = /** @type {TablePage} */ (
        /** @type {unknown} */ (
          await ask("rows", rowsParams(question, { limit: FIRST_PAGE_ROWS }), controller.signal)
        )
      );
      /** @type {TableRow[]} */
      const held = [...first.rows];
      let last = first;
      const whole =
        first.count_complete && first.count !== null && first.count <= WHOLE_TABLE_MAX_ROWS;
      while (whole && last.next_after && held.length < WHOLE_TABLE_MAX_ROWS) {
        last = /** @type {TablePage} */ (
          /** @type {unknown} */ (
            await ask(
              "rows",
              rowsParams(question, { after: last.next_after, limit: NEXT_PAGE_ROWS }),
              controller.signal,
            )
          )
        );
        held.push(...last.rows);
      }
      if (seq !== loadSeq || disposed) {
        return;
      }
      rows = held;
      page = { ...first, next_after: last.next_after };
      windowed = !whole || Boolean(last.next_after);
      drawTable();
    } catch (error) {
      if (seq === loadSeq && !disposed && !isAbort(error)) {
        failed(error);
      }
    } finally {
      if (seq === loadSeq) {
        root.removeAttribute("aria-busy");
      }
    }
  }

  /** Read the next page of a windowed table, once the window nears the last row held. */
  async function readMore() {
    if (readingMore || !page?.next_after || !windowed) {
      return;
    }
    readingMore = true;
    const seq = loadSeq;
    const signal = loading?.signal ?? abort.signal;
    try {
      const next = /** @type {TablePage} */ (
        /** @type {unknown} */ (
          await ask(
            "rows",
            rowsParams(state, { after: page.next_after, limit: NEXT_PAGE_ROWS }),
            signal,
          )
        )
      );
      if (seq !== loadSeq || disposed) {
        return;
      }
      rows.push(...next.rows);
      page = { ...page, next_after: next.next_after, complete: next.complete, reason: next.reason };
      drawNotes();
      drawWindow(true);
    } catch (error) {
      if (seq === loadSeq && !disposed && !isAbort(error)) {
        notice("error", `The next rows could not be read. ${errorText(error)}`);
      }
    } finally {
      readingMore = false;
    }
  }

  // ── Drawing the grid ─────────────────────────────────────────

  function drawTable() {
    if (!page) {
      return;
    }
    const sample = rows.slice(0, FIRST_PAGE_ROWS);
    columns = [...page.columns];
    ({ widths, lines: rowLines } = columnWidths(columns, sample, fields));
    rowHeight = ROW_HEIGHT_ESTIMATE_PX[rowLines];
    rowHeightMeasured = false;
    focus = { row: Math.min(focus.row, Math.max(0, rows.length - 1)), col: -1 };
    selection = null;
    status.textContent = countText(page, isFiltered(state));
    live.textContent = status.textContent;
    drawNotes();
    if (rows.length === 0) {
      thead.replaceChildren();
      colgroup.replaceChildren();
      tbody.replaceChildren();
      rowElements.clear();
      table.hidden = true;
      fitNote.hidden = true;
      drawEmpty();
      return;
    }
    table.hidden = false;
    table.style.setProperty("--table-row-lines", String(rowLines));
    if (windowed) {
      table.setAttribute("role", "grid");
      table.setAttribute(
        "aria-rowcount",
        page.count_complete && page.count !== null ? String(page.count + 1) : "-1",
      );
    } else {
      table.removeAttribute("role");
      table.removeAttribute("aria-rowcount");
    }
    refit(true);
    restorePlace();
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
      widths,
      chPx: measureCh(),
      fixedPx: positional() ? (String(rows.length).length + 2) * measureCh() + 16 : 0,
      padPx: 20,
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

  let chPx = 0;
  function measureCh() {
    if (chPx > 0) {
      return chPx;
    }
    const probe = el("span", { class: "table-ch-probe", "aria-hidden": "true" }, "0000000000");
    table.append(probe);
    const width = probe.getBoundingClientRect?.().width ?? 0;
    probe.remove();
    chPx = width > 0 ? width / 10 : 8;
    return chPx;
  }

  /** Whether rows are named by position, so the row's own column shows its number. */
  function positional() {
    return rows.length > 0 && positionOf(rows[0].key) !== null;
  }

  function drawHeader() {
    const cols = [];
    const heads = [];
    if (positional()) {
      cols.push(
        el("col", {
          class: "table-col-position",
          style: `width: ${String(rows.length).length + 2}ch`,
        }),
      );
      heads.push(
        el("th", { scope: "col", class: "table-position-head", "aria-label": "Row" }, "#"),
      );
    }
    for (const name of fit.visible) {
      const field = fieldsByName.get(name);
      cols.push(el("col", { style: `width: calc(${widths[name] ?? 8}ch + 20px)` }));
      heads.push(headerCell(name, field));
    }
    colgroup.replaceChildren(...cols);
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
        { type: "button", class: "table-sort", "data-field": name },
        el("span", { class: "table-head-label" }, title),
        el("span", { class: "table-sort-arrow", "aria-hidden": "true" }, arrow),
      );
      button.dataset.tipText = sorted
        ? state.order === "asc"
          ? `Sorted ascending; press to sort descending`
          : `Sorted descending; press to show the file's order`
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
          "aria-haspopup": "true",
          "aria-label": `${title}: sort, filter, or hide`,
        },
        "▾",
      ),
    );
    return th;
  }

  function drawAllRows() {
    rowElements.clear();
    const drawnRows = rows.map((row, index) => rowElement(row, index));
    tbody.replaceChildren(...drawnRows);
    drawn = { start: 0, end: rows.length };
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
    const hadFocus = root.contains(doc.activeElement) && doc.activeElement !== search;
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
    if (wantsMore(range, rows.length, READ_AHEAD_ROWS)) {
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
    if (
      selection &&
      index >= Math.min(selection.anchor, selection.head) &&
      index <= Math.max(selection.anchor, selection.head)
    ) {
      tr.setAttribute("aria-selected", "true");
    }
    const position = positionOf(row.key);
    if (position !== null) {
      const link = el(
        "a",
        { class: "table-position", href: href(withRecord(state, row.key)), tabindex: "-1" },
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
    if (view.cut !== null && view.kind === "text") {
      box.append(el("span", { class: "table-cut", "aria-hidden": "true" }, "…"));
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

  /** The table id the rows route answered for, "" for a source that is its own table. */
  function tableOf() {
    return /** @type {{table?: string} | null} */ (page)?.table ?? "";
  }

  function drawEmpty() {
    const filtered = isFiltered(state);
    const message = el(
      "p",
      { class: "table-empty" },
      filtered ? "No rows match. " : "This table has no rows.",
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
  }

  /**
   * @param {"warning" | "error"} severity
   * @param {string} text
   * @param {HTMLElement} [extra]
   */
  function notice(severity, text, extra) {
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
    notes.append(box);
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
    notice(
      "error",
      `The table could not be read. ${errorText(error)}`,
      el("a", { href: href(EMPTY_STATE), class: "table-reset" }, "Show the whole table"),
    );
  }

  function drawChips() {
    const made = [];
    if (state.ref) {
      made.push(chip("ref", `Referencing ${state.ref}`, withRef(state, null)));
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
    if (windowed && !printing) {
      revealRow(next.row);
    }
    syncFocusable();
    const target = focusElement();
    if (target) {
      target.focus({ preventScroll: true });
      if (!windowed) {
        target.scrollIntoView?.({ block: "nearest" });
      }
      showCardFor(target);
    }
    rememberPlace();
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
    if (openMenu && event.key === "Escape") {
      closeMenu(true);
      event.preventDefault();
      return;
    }
    const target = /** @type {Node | null} */ (event.target);
    if (!target || !scroller.contains(target) || rows.length === 0) {
      return;
    }
    const step = keyStep(focus, event, {
      rows: rows.length,
      cols: fit.visible.length,
      pageRows: Math.max(1, Math.floor((scroller.clientHeight || rowHeight * 10) / rowHeight) - 1),
    });
    if (step.action === "none") {
      return;
    }
    if (step.action === "select-all" && !windowed) {
      // A table drawn whole keeps the browser's own select all.
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
      case "select-all":
        select({ anchor: 0, head: rows.length - 1 });
        break;
      case "open":
        openRecord(rows[focus.row].key);
        break;
      case "follow": {
        const link = focusElement();
        if (link?.localName === "a") {
          activateLink(/** @type {HTMLAnchorElement} */ (link));
        } else {
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
   * number, or a reset.
   *
   * @param {HTMLAnchorElement} link
   */
  function activateLink(link) {
    if (link.classList.contains("table-value-filter")) {
      const field = link.dataset.filterField ?? "";
      go(withFilter(state, { field, op: "eq", value: link.dataset.filterValue ?? "" }));
    } else if (link.classList.contains("table-chip-remove")) {
      const name = link.dataset.chip ?? "";
      go(name === "ref" ? withRef(state, null) : withoutFilter(state, name));
    } else if (link.classList.contains("table-clear")) {
      go(withoutFilter(state));
    } else if (link.classList.contains("table-reset")) {
      go(EMPTY_STATE);
    } else if (link.classList.contains("table-position")) {
      const tr = ancestor(link, (node) => node.localName === "tr");
      const index = Number(tr?.dataset.index ?? 0);
      focus = { row: index, col: -1 };
      openRecord(rows[index].key);
    } else if (link.classList.contains("table-ref")) {
      const ref = { table: link.dataset.refTable ?? "", key: link.dataset.refKey ?? "" };
      void sdk.navigation.open(referenceTarget(ref)).catch(() => {});
    } else if (link.classList.contains("table-back")) {
      closeRecord();
    } else if (link.classList.contains("table-open-ref")) {
      void sdk.navigation
        .open({ path: link.dataset.path ?? path, query: link.dataset.query ?? "" })
        .catch(() => {});
    }
  }

  /** @param {Event} event */
  function onScroll(event) {
    if (event.target !== scroller) {
      return;
    }
    scheduleWindow();
    hideCard();
    schedulePlace();
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
    const menu = el("div", { class: "menu table-menu", role: "group", "aria-label": "Columns" });
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
    const menu = el("div", {
      class: "menu table-menu",
      role: "menu",
      "aria-label": `${field?.title || name}`,
    });
    /** @param {string} label @param {() => void} run */
    const item = (label, run) => {
      const control = el("button", { type: "button", class: "menu-item", role: "menuitem" }, label);
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
        item("The file's order", () => go(withSort(state, name, null)));
      }
    } else if (field?.sort_note) {
      menu.append(el("div", { class: "table-menu-note" }, `Not sortable: ${field.sort_note}`));
    }
    if (field?.filterable) {
      menu.append(filterForm(name, field));
    }
    item("Hide column", () => {
      const current = state.cols ? [...state.cols] : [...fit.visible];
      const next = current.filter((item) => item !== name);
      go(withColumns(state, next.length ? next : null));
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
    root.append(menu);
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
    opener.setAttribute("aria-expanded", "false");
    menu.remove();
    if (restore && opener.isConnected) {
      opener.focus();
    }
  }

  /** @param {PointerEvent} event */
  function onPointerDown(event) {
    if (openMenu) {
      const target = /** @type {Node} */ (event.target);
      if (!openMenu.menu.contains(target) && !openMenu.opener.contains(target)) {
        closeMenu(false);
      }
    }
  }

  // ── The record ───────────────────────────────────────────────

  /** @param {string} key */
  function openRecord(key) {
    recordOpenedHere = true;
    rememberPlace();
    go(withRecord(state, key));
  }

  function closeRecord() {
    if (recordOpenedHere) {
      recordOpenedHere = false;
      history.back();
      return;
    }
    go(withRecord(state, null), { replace: true });
  }

  let recordSeq = 0;
  /** @param {string} key */
  async function showRecord(key) {
    const seq = ++recordSeq;
    hideCard();
    closeMenu(false);
    toolbar.hidden = true;
    notes.hidden = true;
    scroller.hidden = true;
    recordPane.hidden = false;
    recordPane.setAttribute("aria-busy", "true");
    /** @type {Record<string, string>} */
    const params = { key };
    if (page?.generation && positionOf(key) !== null) {
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
      drawRecord(record);
    } catch (error) {
      if (seq !== recordSeq || disposed || isAbort(error)) {
        return;
      }
      recordPane.replaceChildren(
        backLink(),
        el(
          "div",
          { class: "notice table-notice", "data-severity": "error", role: "alert" },
          `This record could not be read. ${errorText(error)}`,
        ),
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
   *   generation_moved?: boolean | null,
   *   cells: Record<string, unknown>,
   *   referenced_by: Array<{table: string, fields: string[], to: string[], count: number, count_complete: boolean}>,
   * }} RecordAnswer
   */

  /** @param {RecordAnswer} record */
  function drawRecord(record) {
    const position = positionOf(record.key);
    const heading = el(
      "h2",
      { class: "table-record-title" },
      position !== null ? `Row ${formatCount(position)}` : recordLabel(record),
    );
    const back = backLink();
    const head = el("div", { class: "table-record-head" }, back, heading);
    const parts = [head];
    if (record.positional) {
      parts.push(
        el("p", { class: "table-record-note" }, "This row is named by its position in the file."),
      );
    }
    if (record.generation_moved) {
      parts.push(
        el(
          "div",
          { class: "notice table-notice", "data-severity": "warning", role: "status" },
          "The file changed since this row was read, so the row at this position may be a different one.",
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
        value.append(
          el(
            "a",
            {
              class: "table-ref",
              href: sdk.navigation.href(referenceTarget(view.ref)),
              "data-ref-table": view.ref.table,
              "data-ref-key": view.ref.key,
            },
            view.text,
          ),
        );
      } else if (view.filter) {
        value.append(
          el(
            "a",
            {
              class: "table-value-filter",
              href: href(withRecord(withFilter(state, view.filter), null)),
              "data-filter-field": view.filter.field,
              "data-filter-value": view.filter.value ?? "",
            },
            view.text,
          ),
        );
      } else {
        value.append(
          view.kind === "absent" ? "No value: this row is shorter than the header." : view.text,
        );
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
          query: stateQuery(withRef(EMPTY_STATE, `${tableOf()}:${record.key}`)),
        };
        section.append(
          el(
            "p",
            { class: "table-record-backref" },
            `${ref.table} (${ref.fields.join(", ")}): ${count} `,
            el(
              "a",
              {
                class: "table-open-ref",
                href: sdk.navigation.href(target),
                "data-path": target.path,
                "data-query": target.query,
              },
              "Open as table",
            ),
          ),
        );
      }
      parts.push(section);
    }
    recordPane.replaceChildren(...parts);
    back.focus({ preventScroll: true });
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
    recordPane.hidden = true;
    recordPane.replaceChildren();
    toolbar.hidden = false;
    notes.hidden = false;
    scroller.hidden = false;
    restorePlace();
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
    const cacheKey = `${address}\n${ref.key}`;
    let card = cards.get(cacheKey);
    if (!card) {
      const asked = sdk.fetchPluginData(
        "table",
        "card",
        { path: address, key: ref.key },
        { signal: abort.signal },
      );
      asked.catch(() => cards.delete(cacheKey));
      cards.set(cacheKey, asked);
      card = asked;
    }
    let answer;
    try {
      answer = /** @type {{label: unknown, cells: Record<string, unknown>}} */ (await card);
    } catch {
      return;
    }
    if (cardAnchor !== anchor || disposed || !anchor.isConnected) {
      return;
    }
    sdk.tooltip?.show(cardHtml(answer), anchor);
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
  function schedulePlace() {
    if (placeTimer) {
      return;
    }
    placeTimer = win.setTimeout(() => {
      placeTimer = 0;
      rememberPlace();
    }, SEARCH_DEBOUNCE_MS);
  }

  function rememberPlace() {
    if (disposed || !recordPane.hidden) {
      return;
    }
    const place = {
      query: stateQuery(withRecord(state, null)),
      top: scroller.scrollTop,
      row: focus.row,
    };
    try {
      history.replaceState({ ...(history.state ?? {}), [PLACE_KEY]: place }, "");
    } catch {
      // A browser that refuses the write (Safari past its rate) keeps the place unsaved.
    }
  }

  function restorePlace() {
    const place = /** @type {{query: string, top: number, row: number} | undefined} */ (
      history.state?.[PLACE_KEY]
    );
    if (!place || place.query !== stateQuery(withRecord(state, null)) || rows.length === 0) {
      return;
    }
    focus = { row: Math.min(place.row, rows.length - 1), col: -1 };
    scroller.scrollTop = place.top;
    if (windowed) {
      drawWindow(true);
    }
    syncFocusable();
  }

  // ── Print ────────────────────────────────────────────────────

  function onBeforePrint() {
    if (windowed && page) {
      printing = true;
      drawAllRows();
    }
  }

  function onAfterPrint() {
    if (printing) {
      printing = false;
      drawn = { start: 0, end: 0 };
      drawWindow(true);
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
  root.addEventListener("focusin", (event) =>
    showCardFor(/** @type {HTMLElement} */ (event.target)),
  );
  scroller.addEventListener("scroll", onScroll, { passive: true });
  search.addEventListener("input", onSearchInput);
  search.addEventListener("keydown", onSearchKey);
  win.addEventListener("popstate", onPopState);
  win.addEventListener("beforeprint", onBeforePrint);
  win.addEventListener("afterprint", onAfterPrint);
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
      hideCard();
      sdk.tooltip?.hide(root);
      closeMenu(false);
      win.removeEventListener("popstate", onPopState);
      win.removeEventListener("beforeprint", onBeforePrint);
      win.removeEventListener("afterprint", onAfterPrint);
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
