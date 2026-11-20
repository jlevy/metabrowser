// SQLite built-in plugin: any SQLite database, claimed by its magic number.
//
// Owns one view:
//   ("sqlite", "info") — what a reader process saw of the database: its pages,
//                        encoding, journal and log, how it was opened and why, and the
//                        SQLite library against the reader's minimum
//                        (/api/plugin/sqlite/info).

import { mountInfo } from "./info-view.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser sqlite plugin: SDK is unavailable");
}

mb.registerView("sqlite", "info", {
  render: (container, ctx) => mountInfo(container, ctx, mb),
});

// What a plugin that requires this one gets from `mb.plugins.load("sqlite")`: the Info
// view's model and its drawing, which the fsqlite plugin's store Info view reuses for
// the snapshot a store's `current` names.
export { infoModel } from "./info-model.js";
export { drawInfo } from "./info-view.js";
