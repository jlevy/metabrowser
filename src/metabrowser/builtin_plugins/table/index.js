// Table built-in plugin: the table experience every tabular source shares.
//
// The routes every source answers through (/api/plugin/table/{tables,schema,rows,record,
// card}) are its Python sidekick's. Its browser half is the table view, which a source
// plugin mounts for its own kind's Table view: the plugin has no kind, so a source
// declares `requires = ["table"]` and asks for these exports with
// `mb.plugins.load("table")` (docs/plugins.md, "Declared Dependencies").
//
// `mountTable(container, {path})` draws the table at *path* into *container* and returns
// a handle with `ready` and `dispose()`, as a view's render does. table-view.js holds the
// view and table-model.js the decisions it draws; styles.css holds the view's own rules,
// and static/styles.css the Data Tables component they build on
// (docs/design-system.md, "Data Tables").

export { renderTableCatalog } from "./table-catalog.js";
export { mountTable } from "./table-view.js";
