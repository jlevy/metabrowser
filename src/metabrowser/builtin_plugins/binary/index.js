// Binary built-in plugin — the generic byte-preview fallback.
//
// Owns one view:
//   ("binary", "bytes") — a bounded window of the file's logical bytes,
//                         fetched from /api/plugin/binary/chunk and
//                         rendered one display unit per byte.

import { mountBytesView } from "./bytes-view.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser binary plugin: SDK is unavailable");
}

mb.registerView("binary", "bytes", {
  render: (container, ctx) => mountBytesView(container, ctx, mb),
});
