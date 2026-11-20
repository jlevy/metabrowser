// Table built-in plugin: the routes every tabular source answers through
// (/api/plugin/table/{tables,schema,rows,record,card}), served by its Python sidekick.
//
// The plugin has no kind and, until its table view arrives, no browser code: a source
// plugin declares `requires = ["table"]` because these routes serve its
// `[[table_source]]`, and will load the view's exports with
// `mb.plugins.load("table")` once there are some.
export {};
