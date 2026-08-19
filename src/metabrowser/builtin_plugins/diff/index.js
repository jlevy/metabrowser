// Diff built-in plugin — File Diff Format views for .patch/.diff files.
//
// Owns one view:
//   ("diff", "diff") — the document from /api/plugin/diff/document,
//                      validated by diff_model.js and rendered by
//                      diff_view.js. Validation before rendering is the
//                      point: the renderer only ever sees documents the
//                      conformance corpus vouches for.

import { validateDocument } from "./diff_model.js";
import { mountDiffView } from "./diff_view.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser diff plugin: SDK is unavailable");
}

/** @param {HTMLElement} container @param {string} message */
function renderFailure(container, message) {
  const notice = document.createElement("div");
  notice.className = "diff-availability";
  notice.setAttribute("role", "alert");
  notice.textContent = message;
  container.append(notice);
  return { dispose: () => notice.remove() };
}

mb.registerView("diff", "diff", {
  render: async (container, ctx) => {
    let payload;
    try {
      payload = await mb.fetchPluginData("diff", "document", { path: ctx.path || "" });
    } catch (_error) {
      return renderFailure(container, "Could not load this diff. Refresh the page to try again.");
    }
    const result = validateDocument(payload);
    if (!result.ok) {
      return renderFailure(container, `This diff document is not valid: ${result.error}`);
    }
    return mountDiffView(container, result.document);
  },
});
