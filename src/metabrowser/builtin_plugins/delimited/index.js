// Delimited text built-in plugin: `.csv` and `.tsv` files.
//
// Each file is one table, served by the table plugin's routes through this plugin's
// `[[table_source]]` adapter (source.py). Its views are Table, the default, which the
// table plugin draws (`mountTable`), and Source, its text, drawn by the SDK's shared
// Source renderer as the text kind's is.
//
// Table is the default view, so every file of the kind needs the table plugin's module at
// once. The load starts when this module is evaluated, which the shell does as it opens
// the file, rather than when the view renders, so the table's module and stylesheet are on
// their way while the shell prepares the pane (review A9 of the plugin dependencies
// layer). Starting a provider with its dependents for every plugin would put Markdown on
// every folder's page; a dependent that always needs its provider starts it itself.
const mb = window.metabrowser;

/** @type {Promise<{mountTable: typeof import("../table/table-view.js").mountTable}> | null} */
let table = null;

function loadTable() {
  table ??=
    /** @type {Promise<{mountTable: typeof import("../table/table-view.js").mountTable}>} */ (
      mb.plugins.load("table")
    );
  return table;
}
// A failed load is said by the view that asked; here it only starts early.
loadTable().catch(() => {});

/**
 * @param {HTMLElement} container
 * @param {{path?: string}} ctx
 */
async function renderTable(container, ctx) {
  const { mountTable } = await loadTable();
  return mountTable(container, { path: ctx.path ?? "" });
}

/**
 * @param {HTMLElement} container
 * @param {{raw?: unknown}} ctx
 */
function renderSource(container, ctx) {
  const data = /** @type {Record<string, unknown> & {content?: string, ext?: string}} */ (
    ctx.raw || {}
  );
  mb.perf.measure("renderDelimited:source", () => {
    mb.renderSourceView(container, data);
  });
}

mb.registerView("delimited", "table", { render: renderTable });
mb.registerView("delimited", "source", { render: renderSource });
