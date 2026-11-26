// The table view's state and decisions, with no DOM and no SDK: what the address says
// the view shows, the rows request it makes, how a cell is presented, which columns fit,
// which rows the window draws, and where a key moves the focus.
//
// table-view.js draws what these decide. Everything here is a pure function of its
// arguments, so tests/dom/table-view-session.js runs it, with the view, from the command
// line.
//
// The address. The table's state is the query on the table's own address, in the names
// the rows route takes (metabrowser.table_source.parse_table_query), so a link reproduces
// the view and Back restores it: `sort`, `order`, `q`, `f.<field>=<op>:<value>`, `ref`,
// `cols`, and `record`, the open record's key, which only the view reads. `cols` repeats,
// one field each (`cols=a&cols=b`), since a field's name may hold a comma. A parameter
// the view does not own, such as the shell's `plain=1`, is kept as it was.

/** @typedef {"asc" | "desc"} TableOrder */
/** @typedef {"eq" | "ne" | "lt" | "le" | "gt" | "ge" | "null" | "notnull" | "contains"} TableFilterOp */
/** @typedef {Readonly<{field: string, op: TableFilterOp, value: string | null}>} TableFilter */
/**
 * @typedef {Readonly<{
 *   sort: string | null,
 *   order: TableOrder,
 *   q: string,
 *   filters: ReadonlyArray<TableFilter>,
 *   ref: string | null,
 *   via?: string,
 *   cols: ReadonlyArray<string> | null,
 *   record: string | null,
 *   other: ReadonlyArray<readonly [string, string]>,
 * }>} TableState
 */
/**
 * A field descriptor as the schema route sends it (metabrowser.table_source.field_wire).
 *
 * @typedef {Readonly<{
 *   name: string,
 *   title?: string | null,
 *   type: string,
 *   declared_type?: string | null,
 *   key?: boolean,
 *   list?: boolean,
 *   enum?: ReadonlyArray<string> | null,
 *   ref?: Readonly<{table: string, fields: ReadonlyArray<string>, to: ReadonlyArray<string>}> | null,
 *   sortable?: boolean,
 *   sort_note?: string | null,
 *   filterable?: boolean,
 *   numeric?: boolean,
 * }>} TableField
 */
/** @typedef {Readonly<{key: string, cells: Readonly<Record<string, unknown>>}>} TableRow */
/**
 * The rows route's envelope, the parts the view reads.
 *
 * @typedef {Readonly<{
 *   rows: ReadonlyArray<TableRow>,
 *   columns: ReadonlyArray<string>,
 *   next_after: string | null,
 *   complete: boolean,
 *   truncated: boolean,
 *   reason?: string | null,
 *   count: number | null,
 *   count_complete: boolean,
 *   estimate?: number | null,
 *   skipped?: number,
 *   examined?: number | null,
 *   searched?: ReadonlyArray<string> | null,
 *   sort_refused?: string | null,
 *   limit?: number | null,
 *   generation?: string,
 * }>} TablePage
 */

/** The filter operators, in the order the header menu offers them. */
export const FILTER_OPS = /** @type {const} */ ([
  "eq",
  "ne",
  "contains",
  "lt",
  "le",
  "gt",
  "ge",
  "null",
  "notnull",
]);
/** Operators that take no value. */
const VALUELESS = new Set(["null", "notnull"]);
/** What each operator says in a filter chip and the header menu. */
export const FILTER_OP_LABELS = Object.freeze({
  eq: "is",
  ne: "is not",
  contains: "contains",
  lt: "<",
  le: "≤",
  gt: ">",
  ge: "≥",
  null: "is null",
  notnull: "is not null",
});
/** The view's own parameters, in the order the address writes them. */
const OWNED = new Set(["sort", "order", "q", "ref", "via", "cols", "record"]);

/** The state of a table with nothing chosen: the source's order, every default column. */
export const EMPTY_STATE = Object.freeze(
  /** @type {TableState} */ ({
    sort: null,
    order: "asc",
    q: "",
    filters: [],
    ref: null,
    cols: null,
    record: null,
    other: [],
  }),
);

/** @param {string} value @returns {value is TableFilterOp} */
function isFilterOp(value) {
  return /** @type {ReadonlyArray<string>} */ (FILTER_OPS).includes(value);
}

/**
 * The view's state from its address's query (without the `?`). A filter the view could
 * not have written, such as one with no operator, is kept as written, so the route's
 * refusal names it, rather than dropped without a word; the view keeps one filter per
 * field, the last the query names.
 *
 * @param {string} query
 * @returns {TableState}
 */
export function parseState(query) {
  const params = new URLSearchParams(query);
  /** @type {Map<string, TableFilter>} */
  const filters = new Map();
  /** @type {Array<readonly [string, string]>} */
  const other = [];
  /** @type {Record<string, string>} */
  const owned = {};
  /** @type {string[]} */
  const cols = [];
  for (const [name, value] of params) {
    if (name.startsWith("f.") && name.length > 2) {
      const field = name.slice(2);
      const colon = value.indexOf(":");
      const op = colon < 0 ? value : value.slice(0, colon);
      const operand = colon < 0 ? null : value.slice(colon + 1);
      filters.delete(field);
      filters.set(
        field,
        Object.freeze({
          field,
          op: isFilterOp(op) ? op : /** @type {TableFilterOp} */ (op),
          value: VALUELESS.has(op) ? null : operand,
        }),
      );
    } else if (name === "cols") {
      if (value) {
        cols.push(value);
      }
    } else if (OWNED.has(name)) {
      owned[name] = value;
    } else {
      other.push([name, value]);
    }
  }
  return Object.freeze({
    sort: owned.sort || null,
    order: owned.order === "desc" ? "desc" : "asc",
    q: owned.q ?? "",
    filters: Object.freeze([...filters.values()]),
    ref: owned.ref || null,
    ...(owned.ref && owned.via ? { via: owned.via } : {}),
    cols: cols.length ? Object.freeze(cols) : null,
    record: owned.record || null,
    other: Object.freeze(other),
  });
}

/**
 * The address's query for *state*, in one order, so one state has one address: the
 * view's own parameters, then any it does not own, as they came.
 *
 * @param {TableState} state
 * @returns {string}
 */
export function stateQuery(state) {
  const params = new URLSearchParams();
  if (state.sort) {
    params.set("sort", state.sort);
    if (state.order === "desc") {
      params.set("order", "desc");
    }
  }
  if (state.q) {
    params.set("q", state.q);
  }
  for (const filter of state.filters) {
    params.append(`f.${filter.field}`, filterValue(filter));
  }
  if (state.ref) {
    params.set("ref", state.ref);
    if (state.via !== undefined) {
      params.set("via", state.via);
    }
  }
  for (const name of state.cols ?? []) {
    params.append("cols", name);
  }
  if (state.record) {
    params.set("record", state.record);
  }
  for (const [name, value] of state.other) {
    params.append(name, value);
  }
  return params.toString();
}

/** @param {TableFilter} filter */
function filterValue(filter) {
  return VALUELESS.has(filter.op) ? filter.op : `${filter.op}:${filter.value ?? ""}`;
}

/**
 * The rows route's parameters for *state*: its query, one page of at most *limit* rows,
 * after the cursor *after*. `cols` is a list, which the SDK sends one field a parameter.
 * `path` is the caller's.
 *
 * A cursor holds the sort and order it was made for, and the route refuses it under
 * another, so *after* must come from an answer to this same *state*'s rows: a new
 * question starts again from its first page.
 *
 * @param {TableState} state
 * @param {{after?: string | null, limit: number}} page
 * @returns {Record<string, string | string[]>}
 */
export function rowsParams(state, page) {
  /** @type {Record<string, string | string[]>} */
  const params = {};
  if (state.sort) {
    params.sort = state.sort;
    params.order = state.order;
  }
  if (state.q) {
    params.q = state.q;
  }
  for (const filter of state.filters) {
    params[`f.${filter.field}`] = filterValue(filter);
  }
  if (state.ref) {
    params.ref = state.ref;
    if (state.via !== undefined) {
      params.via = state.via;
    }
  }
  if (state.cols) {
    params.cols = [...state.cols];
  }
  if (page.after) {
    params.after = page.after;
  }
  params.limit = String(page.limit);
  return params;
}

/**
 * Whether two states ask the rows route the same question, so the rows held answer both
 * and only the record, or nothing, differs.
 *
 * @param {TableState} left
 * @param {TableState} right
 */
export function sameRows(left, right) {
  const query = (/** @type {TableState} */ state) => {
    const params = new URLSearchParams();
    for (const [name, value] of Object.entries(rowsParams(state, { limit: 1 }))) {
      for (const item of Array.isArray(value) ? value : [value]) {
        params.append(name, item);
      }
    }
    return params.toString();
  };
  return query(left) === query(right);
}

/**
 * The state after the reader asks to sort by *field* in *order*, or, with no order, the
 * next step of a header's click: the source's order, then ascending, then descending,
 * then the source's order again.
 *
 * @param {TableState} state
 * @param {string} field
 * @param {TableOrder | null} [order]
 * @returns {TableState}
 */
export function withSort(state, field, order) {
  if (order === null) {
    return Object.freeze({ ...state, sort: null, order: "asc" });
  }
  if (order) {
    return Object.freeze({ ...state, sort: field, order });
  }
  if (state.sort !== field) {
    return Object.freeze({ ...state, sort: field, order: "asc" });
  }
  if (state.order === "asc") {
    return Object.freeze({ ...state, sort: field, order: "desc" });
  }
  return Object.freeze({ ...state, sort: null, order: "asc" });
}

/**
 * The state with *filter* in place of any filter on its field, at the end of the chips.
 *
 * @param {TableState} state
 * @param {TableFilter} filter
 * @returns {TableState}
 */
export function withFilter(state, filter) {
  const value = VALUELESS.has(filter.op) ? null : (filter.value ?? "");
  const kept = state.filters.filter((item) => item.field !== filter.field);
  return Object.freeze({
    ...state,
    filters: Object.freeze([...kept, Object.freeze({ ...filter, value })]),
  });
}

/**
 * The state without the filter on *field*; with no field, without every filter, the
 * search, and the reference filter.
 *
 * @param {TableState} state
 * @param {string} [field]
 * @returns {TableState}
 */
export function withoutFilter(state, field) {
  if (field === undefined) {
    return Object.freeze({ ...state, filters: Object.freeze([]), q: "", ref: null });
  }
  return Object.freeze({
    ...state,
    filters: Object.freeze(state.filters.filter((item) => item.field !== field)),
  });
}

/**
 * @param {TableState} state
 * @param {string} q
 * @returns {TableState}
 */
export function withSearch(state, q) {
  return Object.freeze({ ...state, q: q.trim() });
}

/**
 * The state with the reader's choice of columns, or the defaults again with null.
 *
 * @param {TableState} state
 * @param {ReadonlyArray<string> | null} cols
 * @returns {TableState}
 */
export function withColumns(state, cols) {
  return Object.freeze({ ...state, cols: cols?.length ? Object.freeze([...cols]) : null });
}

/**
 * @param {TableState} state
 * @param {string | null} key
 * @returns {TableState}
 */
export function withRecord(state, key) {
  return Object.freeze({ ...state, record: key });
}

/**
 * The state with the reference filter, rows that reference one record (`<table>:<key>`;
 * the route splits it at its last colon, since a key token holds none and a table's name
 * may).
 *
 * @param {TableState} state
 * @param {string | null} ref
 * @param {string} [via] The two field lists of a declared relationship, as JSON.
 * @returns {TableState}
 */
export function withRef(state, ref, via) {
  return Object.freeze({ ...state, ref, via: ref ? via : undefined });
}

/**
 * Whether the state narrows the rows, so an empty answer says "no rows match".
 *
 * @param {TableState} state
 */
export function isFiltered(state) {
  return state.filters.length > 0 || state.q !== "" || state.ref !== null;
}

/**
 * The state without what the schema no longer offers: a sort, filter, or chosen column on
 * a field it does not have. Returns the state, and the names it dropped, so the view can
 * say so.
 *
 * @param {TableState} state
 * @param {ReadonlyArray<TableField>} fields
 * @returns {{state: TableState, dropped: string[]}}
 */
export function reconcileState(state, fields) {
  const names = new Set(fields.map((field) => field.name));
  /** @type {Set<string>} */
  const dropped = new Set();
  const sortField = state.sort ? fields.find((field) => field.name === state.sort) : null;
  let next = state;
  if (state.sort && !sortField?.sortable) {
    dropped.add(state.sort);
    next = withSort(next, state.sort, null);
  }
  const filters = state.filters.filter((filter) => {
    const keep = names.has(filter.field);
    if (!keep) {
      dropped.add(filter.field);
    }
    return keep;
  });
  const cols = state.cols?.filter((name) => {
    const keep = names.has(name);
    if (!keep) {
      dropped.add(name);
    }
    return keep;
  });
  if (dropped.size === 0) {
    return { state, dropped: [] };
  }
  next = Object.freeze({
    ...next,
    filters: Object.freeze(filters),
    cols: cols?.length ? Object.freeze(cols) : null,
  });
  return { state: next, dropped: [...dropped] };
}

// ── Cells ──────────────────────────────────────────────────────

/**
 * How one cell is drawn.
 *
 * - `kind`: `absent` (a short row's missing cell), `null`, `empty` (the empty string),
 *   `text`, `number`, `boolean`, `list`, `json`, `blob`, `ref`, `unpreviewed` (a value
 *   too large to preview), or `error` (one the source refused);
 * - `text`: what the cell shows, already cut by the server where it says so;
 * - `tip`: what the shared tooltip adds, the whole text of a value the clamp may hide, or
 *   what a marker means;
 * - `cut`: the whole value's length in characters, when the page holds a preview;
 * - `size`: the whole value's size in bytes, when the page holds a preview and the source
 *   knows only that (a SQLite text read in part);
 * - `missing`: a reference no row of the referenced table holds, drawn as its value;
 * - `stored`: the stored type of a value whose type differs from its column's;
 * - `invalid`: the text was not valid UTF-8 and was decoded with replacement characters;
 * - `literal`: drawn in the monospaced face, as a key, timestamp, hex, or JSON is;
 * - `filter`: the filter a click on the value adds, for an enum or boolean value;
 * - `ref`: the record a reference names.
 *
 * @typedef {{
 *   kind: "absent" | "null" | "empty" | "text" | "number" | "boolean" | "list" | "json" | "blob" | "ref" | "unpreviewed" | "error",
 *   text: string,
 *   tip: string | null,
 *   cut: number | null,
 *   size: number | null,
 *   missing: boolean,
 *   stored: string | null,
 *   invalid: boolean,
 *   literal: boolean,
 *   filter: TableFilter | null,
 *   ref: {table: string, key: string, label: string} | null,
 * }} CellView
 */

/** Field types whose values are literals, drawn in the monospaced face. */
const LITERAL_TYPES = new Set(["date", "datetime", "json", "blob"]);

/**
 * Whether a field's values are literals, drawn in the monospaced face: a key, or a date,
 * time, JSON, or bytes.
 *
 * @param {TableField | undefined} field
 */
export function literalField(field) {
  return Boolean(field && (field.key || LITERAL_TYPES.has(field.type)));
}

/** @param {unknown} value @returns {value is Record<string, unknown>} */
function isEnvelope(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * How *cell* is drawn in a column of *field*. A cell missing from a row's `cells` is
 * `undefined`, which a source distinguishes from null.
 *
 * @param {unknown} cell
 * @param {TableField | undefined} field
 * @returns {CellView}
 */
export function presentCell(cell, field) {
  /** @type {CellView} */
  const view = {
    kind: "text",
    text: "",
    tip: null,
    cut: null,
    size: null,
    missing: false,
    stored: null,
    invalid: false,
    literal: literalField(field),
    filter: null,
    ref: null,
  };
  if (isEnvelope(cell) && "stored" in cell && "value" in cell) {
    const inner = presentCell(cell.value, field);
    const stored = String(cell.stored);
    return {
      ...inner,
      stored,
      filter: null,
      tip: joinTips(inner.tip, `Stored as ${stored}, not ${field?.type ?? "this column's type"}`),
    };
  }
  if (cell === undefined) {
    return { ...view, kind: "absent", tip: ABSENT_TEXT };
  }
  if (cell === null) {
    return { ...view, kind: "null", text: "null", literal: true };
  }
  if (cell === "") {
    return { ...view, kind: "empty" };
  }
  if (typeof cell === "string") {
    const filter = field?.enum?.includes(cell) ? eqFilter(field, cell) : null;
    return { ...view, text: cell, tip: cell, filter };
  }
  if (typeof cell === "number") {
    return { ...view, kind: "number", text: String(cell) };
  }
  if (typeof cell === "boolean") {
    const text = String(cell);
    return { ...view, kind: "boolean", text, filter: field ? eqFilter(field, text) : null };
  }
  if (Array.isArray(cell)) {
    const text = cell.map((item) => presentCell(item, undefined).text).join(", ");
    return { ...view, kind: "list", text, tip: text };
  }
  if (!isEnvelope(cell)) {
    return { ...view, text: String(cell) };
  }
  if (typeof cell.int === "string") {
    return { ...view, kind: "number", text: cell.int };
  }
  if (typeof cell.real === "string") {
    const text = { inf: "Infinity", "-inf": "−Infinity", nan: "NaN" }[cell.real] ?? cell.real;
    return { ...view, kind: "number", text };
  }
  if (typeof cell.text === "string") {
    const length = typeof cell.length === "number" ? cell.length : null;
    const size = typeof cell.bytes === "number" ? cell.bytes : null;
    const invalid = cell.invalid_utf8 === true;
    const notes = [
      length !== null ? `${formatCount(length)} characters; the record shows more` : null,
      size !== null ? `${formatCount(size)} bytes; the record shows more` : null,
      invalid ? "Not valid UTF-8: unreadable bytes are shown as �" : null,
    ];
    return {
      ...view,
      kind: cell.text === "" && length === null && size === null ? "empty" : "text",
      text: cell.text,
      cut: length,
      size,
      invalid,
      tip: joinTips(cell.text, ...notes),
    };
  }
  if (typeof cell.blob === "string" || typeof cell.hex === "string") {
    const length = typeof cell.length === "number" ? cell.length : null;
    const hex = typeof cell.hex === "string" ? cell.hex : "";
    return {
      ...view,
      kind: "blob",
      literal: true,
      text: hex,
      cut: length,
      tip: length !== null ? `${formatCount(length)} bytes` : null,
    };
  }
  if ("json" in cell) {
    const preview = typeof cell.preview === "string" ? cell.preview : JSON.stringify(cell.json);
    return { ...view, kind: "json", literal: true, text: preview ?? "", tip: preview ?? null };
  }
  if (isEnvelope(cell.ref)) {
    const ref = cell.ref;
    const label = ref.label === null || ref.label === undefined ? String(ref.key) : ref.label;
    if (ref.missing === true) {
      // A value no row of the referenced table holds: shown as itself, marked, with no
      // record to open.
      const text = presentCell(label, undefined).text;
      return {
        ...view,
        text,
        missing: true,
        tip: joinTips(
          text,
          `No row of ${String(ref.table ?? "the referenced table")} has this value`,
        ),
      };
    }
    return {
      ...view,
      kind: "ref",
      text: presentCell(label, undefined).text,
      ref: { table: String(ref.table ?? ""), key: String(ref.key ?? ""), label: String(label) },
    };
  }
  if (typeof cell.error === "string") {
    return { ...view, kind: "error", text: "unreadable", tip: cell.error };
  }
  if (cell.preview === false && typeof cell.length === "number") {
    return {
      ...view,
      kind: "unpreviewed",
      text: `${formatCount(cell.length)} bytes`,
      tip: "Too large to preview in the table",
    };
  }
  const text = JSON.stringify(cell);
  return { ...view, kind: "json", literal: true, text, tip: text };
}

/**
 * What an absent cell says: the row has no value at all for the field, as a delimited
 * row shorter than its header has none, or a record that lacks the key.
 */
export const ABSENT_TEXT = "No value: this row does not have this field";

/**
 * The JSON value a cell carries whole, which a record draws as a tree: a `{json}` cell's,
 * also inside a `{value, stored}` one, or null when the cell carries none, as a nested
 * value past the record's bound, which arrives as its JSON text cut.
 *
 * @param {unknown} cell
 * @returns {{value: unknown} | null}
 */
export function jsonValue(cell) {
  if (!isEnvelope(cell)) {
    return null;
  }
  if ("stored" in cell && "value" in cell) {
    return jsonValue(cell.value);
  }
  return "json" in cell ? { value: cell.json } : null;
}

/** @param {TableField} field @param {string} value @returns {TableFilter} */
function eqFilter(field, value) {
  return Object.freeze({ field: field.name, op: "eq", value });
}

/** @param {...(string | null)} parts */
function joinTips(...parts) {
  const kept = parts.filter((part) => part !== null && part !== "");
  return kept.length ? kept.join("\n") : null;
}

/**
 * A count with a comma between each three digits, in every locale. The host's
 * `formatInteger` follows the reader's locale, but the model does not reach the SDK, and
 * one fixed form keeps what the browserless session prints the same on every machine.
 *
 * @param {number} value
 */
export function formatCount(value) {
  return Math.round(value)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * The text a row's cells copy as: tab-separated values, one row a line, after a header
 * line of the columns. A tab or line break inside a value is a space, so each row stays
 * one line of the right number of fields.
 *
 * @param {ReadonlyArray<string>} columns
 * @param {ReadonlyArray<TableRow>} rows
 * @param {ReadonlyArray<TableField>} fields
 */
export function rowsTsv(columns, rows, fields) {
  const byName = new Map(fields.map((field) => [field.name, field]));
  const clean = (/** @type {string} */ text) => text.replace(/[\t\r\n]+/g, " ");
  const lines = [columns.map(clean).join("\t")];
  for (const row of rows) {
    lines.push(
      columns
        .map((name) => {
          const view = presentCell(row.cells[name], byName.get(name));
          return view.kind === "absent" ? "" : clean(view.text);
        })
        .join("\t"),
    );
  }
  return `${lines.join("\n")}\n`;
}

// ── What the status line says ─────────────────────────────────

/**
 * How many rows the answer covers, as the status line says it: an exact count, a lower
 * bound ("at least"), or an estimate ("about").
 *
 * @param {TablePage} page
 * @param {boolean} filtered
 */
export function countText(page, filtered) {
  const noun = (/** @type {number} */ n) => (n === 1 ? "row" : "rows");
  if (page.count !== null && page.count !== undefined) {
    const shown = page.count_complete ? page.count : Math.max(page.count, page.rows.length);
    const count = formatCount(shown);
    if (!page.count_complete) {
      return `At least ${count} ${noun(shown)}${filtered ? " match" : ""}`;
    }
    if (filtered) {
      return `${count} ${noun(page.count)} ${page.count === 1 ? "matches" : "match"}`;
    }
    return `${count} ${noun(page.count)}`;
  }
  if (typeof page.estimate === "number") {
    return `About ${formatCount(page.estimate)} ${noun(page.estimate)}`;
  }
  return `${formatCount(page.rows.length)}+ rows`;
}

/**
 * The field a sort could not be done by in the time a request may take, when *page* is
 * that refusal (`sort_budget`): it has no rows, and is not an empty table.
 *
 * @param {TablePage} page
 * @returns {string | null}
 */
export function sortRefused(page) {
  return page.reason === "sort_budget" ? (page.sort_refused ?? "") : null;
}

/**
 * What the reader is told about an answer that is not the whole story: a source that
 * read only part of its content, a scan that ran out of time, a cursor from before the
 * content changed, and values a search or filter could not read. Each is a sentence. A
 * refused sort is the view's own notice, with the way back (`sortRefused`).
 *
 * The rows route says a source was cut (`truncated`) without saying where, so the words
 * say only what the answer itself shows: an exact count says every row was read, so what
 * was cut is values within them; a lower bound says the rows go on past what was read.
 * Neither names a file, since a table's source need not be one.
 *
 * @param {TablePage} page
 * @returns {string[]}
 */
export function pageNotes(page) {
  /** @type {string[]} */
  const notes = [];
  if (page.truncated || page.reason === "source_truncated") {
    if (page.count_complete) {
      notes.push("Some values in this table are too large to show.");
    } else {
      // Where the read stopped, and why, are the page's (`reason`, `examined`), for an
      // agent (docs/design-system-messages.md).
      notes.push(
        "Only part of this table is shown, and counts, sorts, and filters cover that part.",
      );
    }
  }
  if (page.reason === "budget") {
    const examined = typeof page.examined === "number" ? formatCount(page.examined) : "some";
    notes.push(`These are the matches among the first ${examined} rows.`);
  } else if (page.reason === "cursor_expired") {
    notes.push("This table changed while it was being read; reload the page to continue.");
  }
  if (page.skipped) {
    notes.push(
      `${formatCount(page.skipped)} ${page.skipped === 1 ? "value was" : "values were"} too large to search.`,
    );
  }
  return notes;
}

/**
 * What an empty answer to a filtered question says: no rows match, or, when the scan ran
 * out of time before it found any, none among the rows it reached, which is all it knows.
 *
 * @param {TablePage} page
 */
export function noMatchText(page) {
  if (page.reason === "budget") {
    return typeof page.examined === "number"
      ? `No matches among the first ${formatCount(page.examined)} rows.`
      : "No matches among the rows read.";
  }
  return "No rows match.";
}

/**
 * The answer a question's pages make together, as the view holds it: the rows of every
 * page, the first page's count and columns, and the last page's word on whether the
 * question is complete, why not, how far a scan reached, and where to read on. A page
 * whose generation differs from the first's continues a table that changed under the
 * cursor, so its rows are not taken and the answer ends there, as `cursor_expired`.
 *
 * @param {TablePage & {rows: TableRow[]}} held The answer so far, its rows a list this appends to.
 * @param {TablePage} next The page read from its `next_after`.
 * @returns {TablePage & {rows: TableRow[]}}
 */
export function joinPage(held, next) {
  if (held.generation && next.generation && next.generation !== held.generation) {
    return {
      ...held,
      next_after: null,
      complete: false,
      reason: "cursor_expired",
    };
  }
  held.rows.push(...next.rows);
  return {
    ...held,
    next_after: next.next_after,
    complete: next.complete,
    reason: next.reason ?? null,
    examined: next.examined ?? held.examined,
    truncated: held.truncated || next.truncated,
  };
}

/**
 * A filter chip's words: the field, the operator, and the value.
 *
 * @param {TableFilter} filter
 * @param {TableField | undefined} field
 */
export function filterLabel(filter, field) {
  const name = field?.title || filter.field;
  const op = FILTER_OP_LABELS[filter.op] ?? filter.op;
  return VALUELESS.has(filter.op) ? `${name} ${op}` : `${name} ${op} ${filter.value ?? ""}`;
}

// ── Columns ────────────────────────────────────────────────────

/** Narrowest column, in characters: a short header and a sort arrow. */
export const COLUMN_MIN_CH = 4;
/**
 * Widest column, in characters. A longer value wraps onto a second line and then clamps,
 * with its whole text in the tooltip. Forty characters is the width paraverse's browser
 * clamps a long-text column near in its default pane (12em of 14 px sans holds about 25
 * characters a line, so two lines hold about 50), and a sentence or a path's last part fits.
 */
export const COLUMN_MAX_CH = 40;
/** Room a header needs past its label, in characters: the sort arrow and the menu button. */
const HEADER_EXTRA_CH = 3;

/**
 * Each column's width in characters, from what it holds: the longest of its header and
 * the values *rows* hold, between COLUMN_MIN_CH and COLUMN_MAX_CH. A column in *known*
 * keeps the width it has there: a width comes from the first rows the view reads of that
 * column and holds for the table's life, so the columns do not move as more rows arrive
 * or a filter narrows them. `lines` is 2 when a value is cut or longer than its column.
 *
 * @param {ReadonlyArray<string>} columns
 * @param {ReadonlyArray<TableRow>} rows
 * @param {ReadonlyArray<TableField>} fields
 * @param {Readonly<Record<string, number>>} [known]
 * @returns {{widths: Record<string, number>, lines: 1 | 2}}
 */
export function columnWidths(columns, rows, fields, known = {}) {
  const byName = new Map(fields.map((field) => [field.name, field]));
  /** @type {Record<string, number>} */
  const widths = {};
  /** @type {1 | 2} */
  let lines = 1;
  for (const name of columns) {
    const field = byName.get(name);
    const header = (field?.title || name).length + HEADER_EXTRA_CH;
    let longest = 0;
    for (const row of rows) {
      const view = presentCell(row.cells[name], field);
      const text = view.kind === "ref" ? `${view.text}  ` : view.text;
      const longestLine = Math.max(...text.split("\n").map((line) => line.length));
      longest = Math.max(longest, longestLine);
      if (text.includes("\n") || view.cut !== null) {
        lines = 2;
      }
    }
    const width =
      known[name] ?? Math.max(COLUMN_MIN_CH, Math.min(COLUMN_MAX_CH, Math.max(header, longest)));
    if (longest > width) {
      lines = 2;
    }
    widths[name] = width;
  }
  return { widths, lines };
}

/**
 * Which columns the table draws in *available* pixels: with the source's default columns,
 * those from the right hide until the rest fit, keeping the first; with the reader's
 * choice, none hide, and the first column pins when they do not fit.
 *
 * @param {{
 *   columns: ReadonlyArray<string>,
 *   widths: Readonly<Record<string, number>>,
 *   chPx: number,
 *   fixedPx: number,
 *   padPx: number,
 *   available: number,
 *   chosen: boolean,
 * }} input `chPx`: one character's width; `fixedPx`: what the row's own column takes;
 *   `padPx`: a cell's horizontal padding.
 * @returns {{visible: string[], hidden: string[], pinned: boolean}}
 */
export function fitColumns(input) {
  const px = (/** @type {string} */ name) =>
    (input.widths[name] ?? COLUMN_MIN_CH) * input.chPx + input.padPx;
  const visible = [...input.columns];
  const total = () => visible.reduce((sum, name) => sum + px(name), input.fixedPx);
  if (input.chosen || !(input.available > 0)) {
    return { visible, hidden: [], pinned: input.chosen && total() > input.available + 1 };
  }
  /** @type {string[]} */
  const hidden = [];
  while (visible.length > 1 && total() > input.available + 1) {
    const last = visible.pop();
    if (last !== undefined) {
      hidden.unshift(last);
    }
  }
  return { visible, hidden, pinned: false };
}

// ── The window ─────────────────────────────────────────────────

/**
 * The rows the window draws: those in the viewport and *overscan* more on each side, as
 * `[start, end)` indexes into the *total* rows held.
 *
 * @param {{scrollTop: number, viewport: number, rowHeight: number, overscan: number, total: number}} input
 * @returns {{start: number, end: number}}
 */
export function windowRange(input) {
  const rowHeight = input.rowHeight > 0 ? input.rowHeight : 1;
  const first = Math.floor(Math.max(0, input.scrollTop) / rowHeight);
  const shown = Math.ceil(Math.max(0, input.viewport) / rowHeight) + 1;
  const start = Math.max(0, Math.min(input.total, first - input.overscan));
  const end = Math.max(start, Math.min(input.total, first + shown + input.overscan));
  return { start, end };
}

/**
 * Whether the window has come near enough the last row held to read the next page: within
 * *ahead* rows of it.
 *
 * @param {{end: number}} range
 * @param {number} held
 * @param {number} ahead
 */
export function wantsMore(range, held, ahead) {
  return range.end + ahead >= held;
}

// ── The keyboard ───────────────────────────────────────────────

/**
 * Where the focus is: a row (`col` -1, the row itself) or one of its cells, or, at `row`
 * -1, the header, where `col` is one of the header's controls (each column's sort button,
 * if it sorts, then its menu button), in order.
 *
 * @typedef {{row: number, col: number}} GridFocus
 */

/**
 * What a key does in the grid, from *focus*: move the focus, open the row's record,
 * follow the focused cell's link, extend the row selection, or nothing.
 *
 * Up and Down, and `k` and `j`, move a row; Left and Right move between the row and its
 * cells; Home and End go to the first and last row held; Page Up and Page Down move a
 * page of *pageRows*. Enter on the row opens its record, and on a cell follows its link,
 * if it has one, or else opens the record. Shift with Up, Down, Home, or End extends the
 * selection, so Home and then Shift-End selects every row held. A key held with Command,
 * Control, or Option is the browser's (tests/test_modified_keys.py).
 *
 * The header is part of the grid's one Tab stop, so its controls do not add a Tab stop a
 * column: Up, or `k`, from the first row moves to the header, onto the focused column's
 * first control; Left and Right move across the header's controls; Down, or `j`, returns
 * to the first row, on the column of the control left. Enter and Space on a header control
 * are the button's own, so they are nothing here. *heads* is how many controls the header
 * has, and *headStarts* each column's first control.
 *
 * @param {GridFocus} focus
 * @param {{key: string, shiftKey?: boolean, ctrlKey?: boolean, metaKey?: boolean, altKey?: boolean}} event
 * @param {{rows: number, cols: number, pageRows: number, heads?: number, headStarts?: ReadonlyArray<number>}} bounds
 * @returns {{action: "move" | "extend" | "open" | "follow" | "none", focus: GridFocus}}
 */
export function keyStep(focus, event, bounds) {
  const none = { action: /** @type {const} */ ("none"), focus };
  if (event.altKey || event.ctrlKey || event.metaKey || bounds.rows === 0) {
    return none;
  }
  const heads = bounds.heads ?? 0;
  const starts = bounds.headStarts ?? [];
  if (focus.row < 0) {
    if (event.shiftKey) {
      return none;
    }
    switch (event.key) {
      case "ArrowLeft":
        return {
          action: /** @type {const} */ ("move"),
          focus: { row: -1, col: Math.max(0, focus.col - 1) },
        };
      case "ArrowRight":
        return {
          action: /** @type {const} */ ("move"),
          focus: { row: -1, col: Math.min(heads - 1, focus.col + 1) },
        };
      case "ArrowDown":
      case "j":
      case "J": {
        let column = -1;
        for (let index = 0; index < starts.length; index++) {
          if (starts[index] <= focus.col) {
            column = index;
          }
        }
        return {
          action: /** @type {const} */ ("move"),
          focus: { row: 0, col: Math.min(column, bounds.cols - 1) },
        };
      }
      default:
        return none;
    }
  }
  const lastRow = bounds.rows - 1;
  const clampRow = (/** @type {number} */ row) => Math.max(0, Math.min(lastRow, row));
  const move = (/** @type {number} */ row, col = focus.col) => ({
    action: /** @type {const} */ ("move"),
    focus: { row: clampRow(row), col },
  });
  /** From the first row, the header, if it has a control. */
  const toHead = () =>
    heads > 0 && focus.row === 0
      ? {
          action: /** @type {const} */ ("move"),
          focus: { row: -1, col: starts[Math.max(0, focus.col)] ?? 0 },
        }
      : null;
  /** Move to *row*, or with Shift, extend the selection to it. @param {number} row */
  const moveOrExtend = (row) =>
    event.shiftKey
      ? { action: /** @type {const} */ ("extend"), focus: { row: clampRow(row), col: focus.col } }
      : move(row);
  switch (event.key) {
    case "ArrowDown":
      return moveOrExtend(focus.row + 1);
    case "ArrowUp":
      return (!event.shiftKey && toHead()) || moveOrExtend(focus.row - 1);
    case "j":
    case "J":
      return move(focus.row + 1);
    case "k":
    case "K":
      return toHead() ?? move(focus.row - 1);
    case "ArrowRight":
      return move(focus.row, Math.min(bounds.cols - 1, focus.col + 1));
    case "ArrowLeft":
      return move(focus.row, Math.max(-1, focus.col - 1));
    case "Home":
      return moveOrExtend(0);
    case "End":
      return moveOrExtend(lastRow);
    case "PageDown":
      return move(focus.row + Math.max(1, bounds.pageRows));
    case "PageUp":
      return move(focus.row - Math.max(1, bounds.pageRows));
    case "Enter":
      return { action: focus.col < 0 ? "open" : "follow", focus };
    default:
      return none;
  }
}

/**
 * A positional key's row number (`@12` is 12), or null for a key the source minted.
 *
 * @param {string} key
 */
export function rowPosition(key) {
  const match = /^@(\d+)$/.exec(key);
  return match ? Number(match[1]) : null;
}

// ── Live ──────────────────────────────────────────────────────
//
// When its file changes, the view reads the rows it holds again with the same question
// and merges the answer here: what changed, what arrived, what left, and which rows stay
// out of the drawing because they would land above the reader's place.

/**
 * A row's cells as one comparable string.
 *
 * @param {TableRow} row
 */
function cellsOf(row) {
  return JSON.stringify(row.cells);
}

/**
 * Merge a live re-read into the rows held.
 *
 * *before* is the rows held over the range read again, *after* the rows the read
 * answered over it, and *anchor* the index in *before* of the first row on screen, or
 * null when the reader is at the top, where nothing is above them. A row is the same row
 * when its key is: a source's key, or a keyless row's position in the file.
 *
 * New rows that would land above the anchor are offered, not drawn, so the rows under the
 * reader stay where they are (docs/design-system.md, "Live Row Arrivals"); `accept`
 * draws them. Every other new row is drawn and flashes, as does each row whose cells
 * changed.
 *
 * @param {{
 *   before: ReadonlyArray<TableRow>,
 *   after: ReadonlyArray<TableRow>,
 *   anchor: number | null,
 *   accept?: boolean,
 * }} input
 * @returns {{
 *   rows: TableRow[],
 *   changed: string[],
 *   arrived: string[],
 *   offered: number,
 *   removed: number,
 * }}
 */
export function liveMerge(input) {
  const { before, after, anchor } = input;
  /** @type {Map<string, TableRow>} */
  const held = new Map(before.map((row) => [row.key, row]));
  const read = new Set(after.map((row) => row.key));
  // The anchor row, or the first row after it still there, places "above".
  let anchorKey = null;
  if (anchor !== null) {
    for (let index = anchor; index < before.length; index++) {
      if (read.has(before[index].key)) {
        anchorKey = before[index].key;
        break;
      }
    }
  }
  const anchorAt = anchorKey === null ? (anchor === null ? 0 : after.length) : -1;
  /** @type {TableRow[]} */
  const rows = [];
  const changed = [];
  const arrived = [];
  let offered = 0;
  let above = anchor !== null;
  for (const [index, row] of after.entries()) {
    if (row.key === anchorKey || (anchorAt >= 0 && index >= anchorAt)) {
      above = false;
    }
    const old = held.get(row.key);
    if (old === undefined) {
      if (above && !input.accept) {
        offered += 1;
        continue;
      }
      arrived.push(row.key);
    } else if (cellsOf(old) !== cellsOf(row)) {
      changed.push(row.key);
    }
    rows.push(row);
  }
  const removed = before.filter((row) => !read.has(row.key)).length;
  return { rows, changed, arrived, offered, removed };
}

/**
 * The Live/Paused pill's words: Live, or Paused with the changes it is holding back.
 *
 * @param {boolean} paused
 * @param {number} held
 */
export function livePillText(paused, held) {
  if (!paused) {
    return "Live";
  }
  return held ? `Paused · ${formatCount(held)} ${held === 1 ? "change" : "changes"}` : "Paused";
}

/**
 * What a failed live refresh says, keeping the rows on screen: a source that reports its
 * writer busy, a file that is gone, a table no longer in its file, or any other refusal.
 *
 * @param {string | null} code the refusal's `code`, when the route sent one
 */
export function liveFailure(code) {
  if (code === "busy") {
    return "The file is busy, so these are the rows last read; the table refreshes once it can.";
  }
  if (code === "not_found") {
    return "This file is no longer there, so these are the rows last read.";
  }
  if (code === "table_not_found") {
    return "This table is no longer in its file, so these are the rows last read.";
  }
  return "The table could not be refreshed, so these are the rows last read.";
}
