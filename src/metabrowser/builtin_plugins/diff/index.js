// Diff built-in plugin — File Diff Format views for .patch/.diff files.
//
// Owns one view:
//   ("diff", "diff") — the document from /api/plugin/diff/document,
//                      validated by diff-model.js and rendered by
//                      diff-view.js. Validation before rendering is the
//                      point: the renderer only ever sees documents the
//                      conformance corpus vouches for.

import { validateDocument } from "./diff-model.js";
import { mountDiffView, setChangeLoader } from "./diff-view.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser diff plugin: SDK is unavailable");
}

// The view projects documents; fetching is the plugin's job. This wires
// the deferred-file loader to the same hook the whole comparison came
// from, narrowed to one path.
setChangeLoader((revision, path, options) =>
  mb.fetchPluginData("diff", "comparison", { ...comparisonParams(revision), file: path }, options),
);

// A comparison between two endpoints travels to the deferred loader as one opaque
// string, the way a revision does: `left...right` from their merge base, as
// `git diff` spells it, or `left..right` directly. No Git ref name contains `..`, so
// neither spelling can be mistaken for a revision.

/** @param {{left: string, right: string, base_policy: "direct" | "merge_base"}} comparison */
function comparisonKey(comparison) {
  const separator = comparison.base_policy === "merge_base" ? "..." : "..";
  return `${comparison.left}${separator}${comparison.right}`;
}

/** @param {string} key @returns {Record<string, string>} */
function comparisonParams(key) {
  const merged = key.split("...");
  if (merged.length === 2) {
    return { left: merged[0], right: merged[1], base_policy: "merge_base" };
  }
  const direct = key.split("..");
  if (direct.length === 2) {
    return { left: direct[0], right: direct[1], base_policy: "direct" };
  }
  return { revision: key };
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
    // Two ctx shapes reach the same renderer: a path (a patch file, or
    // one entry inside it) and a revision (the history view asking for
    // a commit's comparison). Both resolve to one ChangeSetDocument,
    // which is the whole point of the format.
    // A revision is a commit against its first parent; a comparison names both ends.
    const revision = ctx.comparison ? comparisonKey(ctx.comparison) : ctx.revision || "";
    const startedAt = Date.now();
    let payload;
    try {
      payload = revision
        ? await (ctx.raw === undefined
            ? mb.fetchPluginData("diff", "comparison", comparisonParams(revision))
            : ctx.raw)
        : await mb.fetchPluginData("diff", "document", { path: ctx.path || "" });
      if (revision && payload && typeof payload === "object") {
        // The document is source-agnostic by design, so the revision
        // rides beside it for the deferred loader rather than inside it.
        Object.defineProperty(payload, "__revision", { value: revision, enumerable: false });
      }
    } catch (error) {
      // The SDK preserves the hook's JSON on the error for exactly this
      // moment: the server's message ("unknown revision …", "not the
      // root of a Git repository") beats generic advice, and "refresh"
      // is only honest for transport-shaped failures.
      const failure = /** @type {{status?: number, payload?: {message?: string}}} */ (error);
      const message =
        typeof failure?.payload?.message === "string" && failure.payload.message
          ? failure.payload.message
          : "Could not load this diff. Refresh the page to try again.";
      console.error(
        "metabrowser diff: view load failed",
        {
          hook: revision ? "diff/comparison" : "diff/document",
          revision: revision || undefined,
          path: ctx.path || undefined,
          status: failure?.status,
          elapsedMs: Date.now() - startedAt,
        },
        error,
      );
      return renderFailure(container, message);
    }
    const result = mb.perf?.measure
      ? mb.perf.measure("diffDocument:validate", () => validateDocument(payload), {
          source: revision ? "revision" : "path",
        })
      : validateDocument(payload);
    if (!result.ok) {
      return renderFailure(container, `This diff document is not valid: ${result.error}`);
    }
    // A commit comparison already carries these totals beside its revision,
    // author, and age. Direct diff documents and two-endpoint comparisons own
    // their aggregate summary.
    return mountDiffView(container, result.document, mb, { showSummary: !ctx.revision });
  },
});
