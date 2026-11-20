// The structured kind's Table view: a JSON or YAML list of mappings as a table (plan
// Decision 12).
//
// Every structured file has the tab. The table plugin draws it from its routes, which
// ask this plugin's record-list source (records.py), and a document that is not a list
// of records is the source's refusal, which the view says in place of a table. Tree
// stays the kind's default, so the table plugin's module is asked for when the tab is
// first shown, not when the file opens.
//
// The table plugin needs no other plugin, so it cannot draw a JSON value as a tree
// itself; this view hands it the structured plugin's inline tree for a record's nested
// values.

const mb = window.metabrowser;

/**
 * @typedef {{
 *   mountTable: typeof import("../table/table-view.js").mountTable,
 * }} TableExports
 */

/** @type {Promise<TableExports> | null} */
let table = null;

/**
 * @param {(container: HTMLElement, value: unknown, opts: {virtualize: boolean}) => {dispose(): void}} renderInlineTree
 * @returns {{render(container: HTMLElement, ctx: {path?: string}): Promise<ReturnType<TableExports["mountTable"]>>}}
 */
export function recordTableView(renderInlineTree) {
  return {
    async render(container, ctx) {
      table ??= /** @type {Promise<TableExports>} */ (mb.plugins.load("table"));
      const { mountTable } = await table;
      return mountTable(container, {
        path: ctx.path ?? "",
        // A record's value is at most TABLE_RECORD_VALUE_BYTES of JSON, and the tree
        // opens only as much of it as its first draw allows, so it is drawn whole.
        renderJson: (host, value) => renderInlineTree(host, value, { virtualize: false }),
      });
    },
  };
}
