// Delimited text built-in plugin: `.csv` and `.tsv` files.
//
// Each file is one table, served by the table plugin's routes through this plugin's
// `[[table_source]]` adapter (source.py). Until the table view arrives, the kind's one
// view is its source text, drawn by the SDK's shared Source renderer as the text kind's
// is.
const mb = window.metabrowser;

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

mb.registerView("delimited", "source", { render: renderSource });
