// fsqlite built-in plugin: an fsqlite store, claimed by its fsqlite.json marker.
//
// A store is a navigation container whose children are its snapshot's tables, each at
// `<marker>/<segment>`. Owns three views, the SQLite kind's for a database:
//   ("sqlite-store", "table")  — at the marker's address, the store's overview: its
//                                tables by group with their estimates
//                                (/api/plugin/table/tables); at a table's address, that
//                                table, drawn by the table plugin (store-tables.js)
//   ("sqlite-store", "schema") — the snapshot's DDL, every object's or one table's
//                                (/api/plugin/fsqlite/schema)
//   ("sqlite-store", "info")   — the store as a reader sees it: its format and identity,
//                                the version `current` names and that snapshot, pending
//                                transaction envelopes, and the snapshot as the SQLite
//                                plugin's Info view shows a database
//                                (/api/plugin/fsqlite/info).

import { mountStoreSchema, mountStoreTable } from "./store-tables.js";
import { mountStoreInfo } from "./store-view.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser fsqlite plugin: SDK is unavailable");
}

mb.registerView("sqlite-store", "table", {
  render: (container, ctx) => mountStoreTable(container, ctx, mb),
});
mb.registerView("sqlite-store", "schema", {
  render: (container, ctx) => mountStoreSchema(container, ctx, mb),
});
mb.registerView("sqlite-store", "info", {
  render: (container, ctx) => mountStoreInfo(container, ctx, mb),
});
