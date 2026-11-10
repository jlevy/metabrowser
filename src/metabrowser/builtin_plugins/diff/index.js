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
setChangeLoader((revision, path, options) => fetchComparison(revision, options, path));

// A comparison between two endpoints travels to the deferred loader as one opaque
// string, the way a revision does: `left...right` from their merge base, as
// `git diff` spells it, or `left..right` directly. No Git ref name contains `..`, so
// neither spelling can be mistaken for a revision.

/** @param {{left: string, right: string, base_policy: "direct" | "merge_base", route?: string}} comparison */
function comparisonKey(comparison) {
  if (comparison.route !== undefined) {
    pluginComparisonRoute(comparison.route);
    return comparison.route;
  }
  const separator = comparison.base_policy === "merge_base" ? "..." : "..";
  return `${comparison.left}${separator}${comparison.right}`;
}

// Every comparison request names this build and, on a store, the store, so the browser may
// keep an answer that cannot change without asking again: the server says so only for an
// address that names both, and a folder's page has no store to name. This is the one place
// the address is spelled; the pull-request page's prefetch asks `prefetch` below for it, so
// the browser's cache, keyed by the address, answers the mount from the prefetch.
const SETTINGS = window.METABROWSER_SETTINGS;
/** @type {Record<string, string>} */
const SCOPE_PARAMS = {
  ...(typeof SETTINGS?.BUILD_TAG === "string" ? { build: SETTINGS.BUILD_TAG } : {}),
  ...(typeof SETTINGS?.STORE_TAG === "string" ? { store: SETTINGS.STORE_TAG } : {}),
};

/**
 * An optional comparison route comes from the server's PR envelope. It remains
 * a same-origin plugin-data request, including for each deferred file.
 * @param {string} route
 */
function pluginComparisonRoute(route) {
  const url = new URL(route, "http://metabrowser.invalid");
  const match = /^\/api\/plugin\/([a-z][a-z0-9_-]*)\/([a-z][a-z0-9_-]*)$/.exec(url.pathname);
  if (!route.startsWith("/") || url.origin !== "http://metabrowser.invalid" || url.hash || !match) {
    throw new Error("The comparison route is not a same-origin plugin route.");
  }
  return { plugin: match[1], hook: match[2], params: Object.fromEntries(url.searchParams) };
}

/** @param {string} key @param {{signal?: AbortSignal}} [options] @param {string} [file] */
function fetchComparison(key, options, file) {
  const target = key.startsWith("/")
    ? pluginComparisonRoute(key)
    : { plugin: "diff", hook: "comparison", params: comparisonParams(key) };
  return mb.fetchPluginData(
    target.plugin,
    target.hook,
    { ...target.params, ...(file === undefined ? {} : { file }) },
    options,
  );
}

/** @param {string} key @returns {Record<string, string>} */
function comparisonParams(key) {
  const merged = key.split("...");
  if (merged.length === 2) {
    return { left: merged[0], right: merged[1], base_policy: "merge_base", ...SCOPE_PARAMS };
  }
  const direct = key.split("..");
  if (direct.length === 2) {
    return { left: direct[0], right: direct[1], base_policy: "direct", ...SCOPE_PARAMS };
  }
  return { revision: key, ...SCOPE_PARAMS };
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
      // No codec, no address: the control is not offered, never pointed elsewhere.
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

/**
 * What makes this page's View file opener, or null on a page with no pin.
 *
 * diff-view-file.js loads here, for a pinned page's first diff, and not with the plugin's
 * module tree: a served folder has no controls and never calls it. As a static import it
 * was a seventh module on a served folder's first diff view, which the plugin could not
 * evaluate without. Without it the view requests the six modules v0.11.0 did. Measured
 * 2026-11-02 in Chrome 152 on a pinned page's first diff: 4,135 bytes transferred and
 * 11,161 decoded. A pin pays that one local request, which render starts beside the diff's
 * own, and in that measurement it finished before the comparison did. Its controls still
 * arrive with the mount. A failed import is the view's to report: render says the diff did
 * not load, and logs which request failed.
 *
 * @param {string} revision
 * @returns {Promise<import("./diff-view-file.js").ViewFileOpenerFactory | null>}
 */
async function viewFileOpener(revision) {
  if (revision.startsWith("/")) {
    const { plugin, hook, params } = pluginComparisonRoute(revision);
    const fullOid = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;
    if (
      plugin === "github" &&
      hook === "pull-comparison" &&
      fullOid.test(params.left) &&
      fullOid.test(params.right) &&
      /^[0-9a-f]{16}$/.test(params.store) &&
      /^[1-9][0-9]*$/.test(params.number)
    ) {
      if (!window.MetabrowserGitPath) {
        const codec = "/static/git-path.js";
        await import(codec);
      }
      const { createViewFileOpener } = await import("./diff-view-file.js");
      return (options) =>
        createViewFileOpener(
          {
            pin: "",
            href: () => null,
            snapshotHref(side) {
              if (side.commit !== (side.side === "base" ? params.left : params.right)) {
                return null;
              }
              const path = window.MetabrowserGitPath?.wire(side.address);
              if (!path) {
                return null;
              }
              const query = new URLSearchParams({
                number: params.number,
                left: params.left,
                right: params.right,
                store: params.store,
                side: side.side,
                path,
              });
              return `/api/plugin/github/pull-snapshot?${query}`;
            },
            onRestored: () => () => {},
            switchPin: () => Promise.resolve({ status: 400, body: null }),
            navigate: () => {},
          },
          options,
        );
    }
  }
  const host = viewFileHost();
  if (host === null) {
    return null;
  }
  const { createViewFileOpener } = await import("./diff-view-file.js");
  return (options) => createViewFileOpener(host, options);
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
    const signal = ctx.comparisonSignal;
    if (signal?.aborted) {
      return null;
    }
    // Two ctx shapes reach the same renderer: a path (a patch file, or
    // one entry inside it) and a revision (the history view asking for
    // a commit's comparison). Both resolve to one ChangeSetDocument,
    // which is the whole point of the format.
    // A revision is a commit against its first parent; a comparison names both ends.
    const revision = ctx.comparison ? comparisonKey(ctx.comparison) : ctx.revision || "";
    const startedAt = Date.now();
    // Asked for now, so its request overlaps the diff's own instead of following it. Its
    // failure waits for the mount below, and may never reach it: a diff that fails first
    // answers for itself, and the rejection still needs a handler.
    const opener = viewFileOpener(revision);
    void opener.catch(() => {});
    let payload;
    try {
      payload = revision
        ? await (ctx.raw === undefined
            ? fetchComparison(revision, signal === undefined ? undefined : { signal })
            : ctx.raw)
        : await mb.fetchPluginData("diff", "document", { path: ctx.path || "" });
      if (signal?.aborted) {
        return null;
      }
      if (revision && payload && typeof payload === "object") {
        // The document is source-agnostic by design, so the revision
        // rides beside it for the deferred loader rather than inside it.
        Object.defineProperty(payload, "__revision", { value: revision, enumerable: false });
      }
    } catch (error) {
      if (signal?.aborted) {
        return null;
      }
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
    let viewFile;
    try {
      viewFile = await opener;
    } catch (error) {
      if (signal?.aborted) {
        return null;
      }
      console.error(
        "metabrowser diff: view load failed",
        {
          hook: "diff/view-file",
          revision: revision || undefined,
          path: ctx.path || undefined,
          elapsedMs: Date.now() - startedAt,
        },
        error,
      );
      return renderFailure(container, "Could not load this diff. Refresh the page to try again.");
    }
    if (signal?.aborted) {
      return null;
    }
    // A commit comparison already carries these totals beside its revision,
    // author, and age. Direct diff documents and two-endpoint comparisons own
    // their aggregate summary.
    return mountDiffView(container, result.document, mb, {
      showSummary: !ctx.revision,
      viewFile,
    });
  },
  /**
   * The comparison `render` would fetch for `ctx.comparison`, fetched now, for a page that
   * will show it: the pull-request page's Conversation. The answer is handed back to
   * `render` as `ctx.raw`, and a Back onto the page is answered by the browser's cache,
   * because this request's address is the one `render` would ask.
   *
   * @param {{left: string, right: string, base_policy: "direct" | "merge_base", route?: string}} comparison
   * @param {AbortSignal} [signal]
   * @returns {Promise<unknown>}
   */
  prefetch: (comparison, signal) =>
    fetchComparison(comparisonKey(comparison), signal === undefined ? undefined : { signal }),
});
