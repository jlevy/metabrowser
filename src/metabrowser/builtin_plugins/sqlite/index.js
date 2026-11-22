// SQLite built-in plugin: any SQLite database, claimed by its magic number.
//
// A database is a navigation container whose children are its tables, each at
// `<database>/<segment>`. Owns three views:
//   ("sqlite", "table")  — at the database's address, its overview: tables, views,
//                          virtual and internal tables with their estimates
//                          (/api/plugin/table/tables); at a table's address, that table,
//                          drawn by the table plugin (mountTable)
//   ("sqlite", "schema") — each object's DDL, indexes, triggers, and foreign keys, or one
//                          table's (/api/plugin/sqlite/schema)
//   ("sqlite", "info")   — what a reader process saw of the database: its pages,
//                          encoding, journal and log, how it was opened and why, and the
//                          SQLite library against the reader's minimum
//                          (/api/plugin/sqlite/info).

import { mountInfo } from "./info-view.js";
import { mountSchema, mountTableView } from "./tables-view.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser sqlite plugin: SDK is unavailable");
}

mb.registerView("sqlite", "table", {
  render: (container, ctx) => mountTableView(container, ctx, mb),
});
mb.registerView("sqlite", "schema", {
  render: (container, ctx) => mountSchema(container, ctx, mb),
});
mb.registerView("sqlite", "info", {
  render: (container, ctx) => mountInfo(container, ctx, mb),
});

// What a plugin that requires this one gets from `mb.plugins.load("sqlite")`: the Info
// view's model and its drawing, and the Table and Schema views, which the fsqlite
// plugin's store views reuse for the snapshot a store's `current` names.
export { infoModel } from "./info-model.js";
export { drawInfo } from "./info-view.js";
export { mountSchema, mountTableView } from "./tables-view.js";
