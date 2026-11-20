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
