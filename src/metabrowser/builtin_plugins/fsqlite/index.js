// fsqlite built-in plugin: an fsqlite store, claimed by its fsqlite.json marker.
//
// Owns one view:
//   ("sqlite-store", "info") — the store as a reader sees it: its format and identity,
//                              the version `current` names and that snapshot, pending
//                              transaction envelopes, and the snapshot as the SQLite
//                              plugin's Info view shows a database
//                              (/api/plugin/fsqlite/info).

import { mountStoreInfo } from "./store-view.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser fsqlite plugin: SDK is unavailable");
}

mb.registerView("sqlite-store", "info", {
  render: (container, ctx) => mountStoreInfo(container, ctx, mb),
});
