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

/**
 * How this page opens a file at a commit, for the View file controls of a diff: its
 * `/view/` address for the commit the page shows, and the pin route for any other. The
 * server writes the commit a page shows into every page on a pinned revision and into
 * no other, so a served folder, which has no file at a commit to open, gets `null` and
 * no controls.
 *
 * Three things here are the shell's and the server's rather than the plugin SDK's: the
 * page's pin (`METABROWSER_SOURCE_PIN`), the pin route, and the route codec's wire
 * encoder (`MetabrowserNavigationRoute`). The SDK has no accessor for the first two,
 * and the ref selector and the freshness row, which are shell code, read the global and
 * call the route directly as well; there is no host path to share. Adding one would be
 * a new public SDK surface, which the thin-mirror plan rules out for the alpha, and a
 * built-in plugin ships with the shell and the server as one artifact, so these are
 * internal contracts it may use, as the GitHub plugin posts to the pin route and the
 * image and folder plugins use the route codec.
 *
 * @returns {import("./diff-view-file.js").ViewFileHost | null}
 */
function viewFileHost() {
  const pin = window.METABROWSER_SOURCE_PIN?.pin;
  if (typeof pin !== "string" || pin === "") {
    return null;
  }
  return {
    pin,
    href(path) {
      const wire = window.MetabrowserGitPath?.wire(path) ?? null;
      return wire === null ? null : mb.navigation.href({ path: wire });
    },
    onRestored(restored) {
      /** @param {PageTransitionEvent} event */
      const shown = (event) => {
        if (event.persisted) {
          restored();
        }
      };
      window.addEventListener("pageshow", shown);
      return () => window.removeEventListener("pageshow", shown);
    },
    // The ref selector's own request: a same-origin JSON POST, which content in a
    // served page cannot make with a link, an image, or a form. The server answers any
    // other content type with 415.
    async switchPin(body) {
      const response = await fetch("/api/source/pin", {
        method: "POST",
        headers: { "content-type": "application/json" },
        cache: "no-store",
        body: JSON.stringify(body),
      });
      let decoded = null;
      try {
        decoded = await response.json();
      } catch {
        decoded = null;
      }
      return { status: response.status, body: decoded };
    },
    navigate: (href) => window.location.assign(href),
  };
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
    return mountDiffView(container, result.document, mb, {
      showSummary: !ctx.revision,
      viewFile: viewFileHost(),
    });
  },
});
