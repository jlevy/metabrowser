// Diff built-in plugin — File Diff Format views for .patch/.diff files.
//
// Owns one view:
//   ("diff", "diff") — the document from /api/plugin/diff/document,
//                      validated by diff-model.js and rendered by
//                      diff-view.js. Validation before rendering is the
//                      point: the renderer only ever sees documents the
//                      conformance corpus vouches for.

import { validateDocument, validateManifest } from "./diff-model.js";
import { mountDiffSummary, mountDiffView, setChangeLoader } from "./diff-view.js";

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

/**
 * @typedef {{left: string, right: string, base_policy: "direct" | "merge_base", route?: string, image_route?: string, rendered_route?: string, branch?: {ref: string} | null}} Comparison
 *   *route* is the plugin route that answers the comparison, *rendered_route* the one
 *   that renders a changed Markdown file of it, and *image_route* the one that serves an
 *   image that Markdown shows: all come from the server that issued them, so this plugin
 *   spells none. *branch* is a pull request's: its head ref when the comparison shows the
 *   pull request's head, which View on branch opens, and null when it shows another
 *   commit, which nothing opens.
 */

/** @param {Comparison} comparison */
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

/**
 * The rendered Markdown layer of a comparison that names a rendered route, or null. Its
 * module is imported now, beside the diff's own request and the View file opener, so it
 * is usually loaded before the comparison answers (a cold import took 1.2-4.2 ms); a
 * mount waits for it, and mounts its views only when the manifest lists a Markdown file.
 * A failed import leaves every file in Source.
 *
 * diff-markdown.js is an on-demand tier: a pull request's Changes loads it, and no other
 * diff does: 25,267 bytes, 7,861 gzipped.
 *
 * @param {Comparison | undefined} comparison
 */
function markdownLayer(comparison) {
  const route = comparison?.rendered_route;
  if (typeof route !== "string") {
    return null;
  }
  let target;
  try {
    target = pluginComparisonRoute(route);
  } catch (error) {
    console.error(
      "metabrowser diff: rendered Markdown unavailable",
      { hook: "diff/markdown" },
      error,
    );
    return null;
  }
  const { plugin, hook, params } = target;
  return {
    module: import("./diff-markdown.js").catch((error) => {
      console.error("metabrowser diff: Markdown view unavailable", error);
      return null;
    }),
    /** @param {string} fileId @param {AbortSignal} [signal] @param {boolean} [ahead] */
    load: (fileId, signal, ahead = false) =>
      mb.fetchPluginData(
        plugin,
        hook,
        { ...params, file: fileId, ...(ahead ? { prefetch: "1" } : {}) },
        signal === undefined ? undefined : { signal },
      ),
  };
}

/**
 * Ask the server for the first screen's projections while the reader is still on another
 * tab, one at a time, so Changes finds them computed. The answers are the server's to
 * keep; *signal* is the page's, so a page leaving stops the rest.
 *
 * @param {NonNullable<ReturnType<typeof markdownLayer>>} markdown
 * @param {unknown} payload
 * @param {AbortSignal} [signal]
 */
async function prefetchMarkdown(markdown, payload, signal) {
  const views = await markdown.module;
  const files = /** @type {{manifest?: {files?: unknown}} | null | undefined} */ (payload)?.manifest
    ?.files;
  if (views === null || !Array.isArray(files)) {
    return;
  }
  for (const fileId of views.firstScreenRendered(files)) {
    if (signal?.aborted) {
      return;
    }
    try {
      await markdown.load(fileId, signal, true);
    } catch {
      return;
    }
  }
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
 * The commit this page shows, which the server writes into every page on a pinned
 * revision and into no other; null on a served folder.
 *
 * Three things here are the shell's and the server's rather than the plugin SDK's: the
 * page's pin (`METABROWSER_SOURCE_PIN`), the pin route, and the route codec's wire
 * encoder (`MetabrowserGitPath`). The SDK has no accessor for the first two, and the ref
 * selector and the freshness row, which are shell code, read the global and call the
 * route directly as well; there is no host path to share. Adding one would be a new
 * public SDK surface, which the thin-mirror plan rules out for the alpha, and a built-in
 * plugin ships with the shell and the server as one artifact, so these are internal
 * contracts it may use, as the image and folder plugins use the route codec.
 *
 * @returns {string | null}
 */
function pagePin() {
  const pin = window.METABROWSER_SOURCE_PIN?.pin;
  return typeof pin === "string" && pin !== "" ? pin : null;
}

// Whether this page has heard that the server serves another pin than the one it shows
// (static/source-pin-guard.js announces it), after which a `/view/` address it holds
// opens that other pin. The plugin loads once per page, so one listener serves every diff.
let pinChanged = false;
/** @type {Set<() => void>} */
const pinChangeListeners = new Set();
window.addEventListener?.("metabrowser:pin-changed", () => {
  pinChanged = true;
  for (const listener of [...pinChangeListeners]) {
    listener();
  }
});

/** @param {() => void} changed @returns {() => void} */
function onPinChanged(changed) {
  if (pinChanged) {
    changed();
  }
  pinChangeListeners.add(changed);
  return () => {
    pinChangeListeners.delete(changed);
  };
}

/** @param {() => void} restored @returns {() => void} */
function onRestored(restored) {
  /** @param {PageTransitionEvent} event */
  const shown = (event) => {
    if (event.persisted) {
      restored();
    }
  };
  window.addEventListener("pageshow", shown);
  return () => window.removeEventListener("pageshow", shown);
}

/**
 * The ref selector's own request: a same-origin JSON POST, which content in a served page
 * cannot make with a link, an image, or a form. The server answers any other content type
 * with 415.
 *
 * @param {import("./diff-view-file.js").PinSelection} selection
 */
async function postPin(selection) {
  const response = await fetch("/api/source/pin", {
    method: "POST",
    headers: { "content-type": "application/json" },
    cache: "no-store",
    body: JSON.stringify(selection),
  });
  let decoded = null;
  try {
    decoded = await response.json();
  } catch {
    decoded = null;
  }
  return { status: response.status, body: decoded };
}

/**
 * The page's one pin switch, made with diff-view-file.js the first time it loads.
 *
 * @type {import("./diff-view-file.js").PinSwitch | null}
 */
let pagePinSwitch = null;

/** diff-view-file.js, loaded on demand (see `viewFileOpener` for the tier), and the switch. */
async function viewFileModule() {
  const module = await import("./diff-view-file.js");
  pagePinSwitch ??= module.createPinSwitch({ post: postPin, onRestored });
  return { module, pinSwitch: pagePinSwitch };
}

/**
 * The address of a file in a checkout's working tree, for View on branch beside it: the
 * path the diff shows is the repository's, and the served folder may be a folder inside
 * it (`served_prefix`). Null for a path outside the served folder, and for a name that is
 * not UTF-8, which no folder address here spells.
 *
 * @param {string | Uint8Array} path
 * @param {string} prefix
 * @returns {string | null}
 */
function checkoutHref(path, prefix) {
  if (typeof path !== "string" || path === "") {
    return null;
  }
  const within =
    prefix === "" ? path : path.startsWith(`${prefix}/`) ? path.slice(prefix.length + 1) : null;
  return within ? mb.navigation.href({ path: within }) : null;
}

/**
 * The page a diff's controls open files on, or null when it has none: a pinned revision,
 * which a commit's diff and a pull request's Changes both use; or, for a pull request
 * beside a checkout, the checkout when its HEAD is the diff's head. A served folder's
 * commit diffs, a patch file, and a pull request whose diff is not at its head have none.
 *
 * @param {Comparison | undefined} comparison
 * @returns {Omit<import("./diff-view-file.js").ViewFileHost, "pinSwitch"> | null}
 */
function viewFileHost(comparison) {
  const branch = comparison?.branch;
  if (branch === null) {
    return null;
  }
  const ref = branch === undefined ? null : branch.ref;
  const pin = pagePin();
  const navigate = (/** @type {string} */ href) => window.location.assign(href);
  if (pin !== null) {
    return {
      kind: "pin",
      pin,
      branch: ref,
      href(path) {
        // No codec, no address: the control is not offered, never pointed elsewhere.
        const wire = window.MetabrowserGitPath?.wire(path) ?? null;
        return wire === null ? null : mb.navigation.href({ path: wire });
      },
      navigate,
      onPinChanged,
    };
  }
  // A checkout's page has no pin: what it shows is its working tree, which is the pull
  // request's head only while its HEAD is that commit, as the page's header says.
  const repository = mb.repository;
  if (
    ref === null ||
    comparison === undefined ||
    mb.sourceKind() !== "filesystem" ||
    repository?.revision !== comparison.right
  ) {
    return null;
  }
  return {
    kind: "checkout",
    pin: repository.revision,
    branch: ref,
    href: (path) => checkoutHref(path, repository.served_prefix),
    navigate,
    onPinChanged: () => () => {},
  };
}

/**
 * What makes this page's View file opener, or null when nothing on the page can open a
 * changed file (`viewFileHost`).
 *
 * diff-view-file.js loads here, for the first diff that has controls, and not with the
 * plugin's module tree: a served folder's commit diffs have none and never call it. As a
 * static import it was a seventh module on a served folder's first diff view, which the
 * plugin could not evaluate without. Without it the view requests the six modules v0.11.0
 * did. Measured 2026-11-02 in Chrome 152 on a pinned page's first diff: 4,135 bytes
 * transferred and 11,161 decoded. A page with controls pays that one local request, which
 * render starts beside the diff's own, and in that measurement it finished before the
 * comparison did. Its controls still arrive with the mount. A failed import is the view's
 * to report: render says the diff did not load, and logs which request failed.
 *
 * @param {Comparison | undefined} comparison
 * @returns {Promise<import("./diff-view-file.js").ViewFileOpenerFactory | null>}
 */
async function viewFileOpener(comparison) {
  const host = viewFileHost(comparison);
  if (host === null) {
    return null;
  }
  const { module, pinSwitch } = await viewFileModule();
  return (options) => module.createViewFileOpener({ ...host, pinSwitch }, options);
}

/**
 * Whether a link in rendered Markdown to a file of the head may open at its `/view/`
 * address: only while this page shows that head, the one commit at which the address
 * names that file. The rendered answer is the same for every page (its cache key names no
 * pin), so the page decides, and a link it does not keep is plain text.
 *
 * @param {Comparison | undefined} comparison
 * @returns {() => boolean}
 */
function headLinksOpen(comparison) {
  const pin = pagePin();
  return () => pin !== null && pin === comparison?.right && !pinChanged;
}

/**
 * The shared changed-files tree, the shell's `changed-files-tree` bundle, which the Pulls tab
 * draws a pull request's files with too. A multi-file diff draws its Diff summary on it, and
 * every diff shows its files' paths by its display rule. It is asked for beside the diff's
 * own request, so it is in hand when the diff mounts: a cold load is one small local request.
 * A diff whose tree does not load keeps its totals line and raw paths, and says why in the
 * console.
 *
 * @returns {Promise<MetabrowserChangedFilesTree | null>}
 */
function changedFilesTree() {
  return mb.loadChangedFilesTree().catch((error) => {
    console.error("metabrowser diff: the Diff summary is unavailable", error);
    return null;
  });
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
    const opener = viewFileOpener(ctx.comparison);
    void opener.catch(() => {});
    const markdown = markdownLayer(ctx.comparison);
    // The tree the Diff summary is drawn on, whose display rule the file bars show paths by.
    const summaryTree = changedFilesTree();
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
    const markdownViews = markdown === null ? null : await markdown.module;
    if (signal?.aborted) {
      return null;
    }
    const files = /** @type {{files: Record<string, unknown>[]}} */ (result.document.manifest)
      .files;
    const changedFiles = await summaryTree;
    if (signal?.aborted) {
      return null;
    }
    const rendered =
      markdown !== null &&
      markdownViews !== null &&
      files.some((file) => markdownViews.supportsRenderedChange(file));
    ctx.onDocument?.(result.document);
    // A commit's page and a pull request's keep the Diff summary at their own top
    // (mb-pb35): a commit's asks for it there (`summaryHost`), and a pull request's draws it
    // itself and asks for none (`summary: false`). Direct diff documents and other
    // comparisons lead their toolbar with it.
    const summaryHost = ctx.summaryHost ?? null;
    return mountDiffView(container, result.document, mb, {
      showSummary: ctx.summary !== false && (summaryHost !== null || !ctx.revision),
      summaryHost,
      // The commit's own totals, which the summary says where the list is cut short (A3 of
      // review A on #470).
      ...(ctx.summaryTotals === undefined ? {} : { summaryTotals: ctx.summaryTotals }),
      changedFiles,
      ...(typeof ctx.openFile === "function" ? { openFile: ctx.openFile } : {}),
      viewFile,
      ...(!rendered
        ? {}
        : {
            markdownViews,
            renderMarkdown: (fileId, signal) => markdown.load(fileId, signal),
            markdownTargets: markdownViews.markdownTargets(
              ctx.comparison?.image_route,
              headLinksOpen(ctx.comparison),
            ),
            ...(typeof ctx.markdownHoldMs === "number"
              ? { markdownHoldMs: ctx.markdownHoldMs }
              : {}),
          }),
    });
  },
  /**
   * The comparison `render` would fetch for `ctx.comparison`, fetched now, for a page that
   * will show it: the pull-request page's Conversation. The answer is handed back to
   * `render` as `ctx.raw`, and a Back onto the page is answered by the browser's cache,
   * because this request's address is the one `render` would ask.
   *
   * The comparison alone: a page that keeps the answer for later pages shares its request,
   * so the first screen's Markdown is asked for apart from it (`prefetchMarkdown`).
   *
   * @param {Comparison} comparison
   * @param {AbortSignal} [signal]
   * @returns {Promise<unknown>}
   */
  prefetch: (comparison, signal) =>
    fetchComparison(comparisonKey(comparison), signal === undefined ? undefined : { signal }),
  /**
   * The first screen's Markdown projections of a comparison a page shows, asked for while
   * the reader is still on another tab, for the comparison *raw* is the answer to. Nothing
   * for a comparison that names no rendered route. *signal* is the page's, so a page
   * leaving stops the rest.
   *
   * @param {Comparison} comparison
   * @param {unknown} raw
   * @param {AbortSignal} signal
   * @returns {Promise<void>}
   */
  prefetchMarkdown: async (comparison, raw, signal) => {
    const markdown = markdownLayer(comparison);
    if (markdown !== null && !signal.aborted) {
      await prefetchMarkdown(markdown, raw, signal);
    }
  },
  /**
   * A comparison's Diff summary on its own, at the top of a page that keeps it while its diff
   * comes and goes: a pull request's page, on every tab (mb-pb35). *raw* is the comparison
   * `prefetch` or `render` read, of which only the manifest is read and validated; a file the
   * summary opens goes to *openFile*. Null for a comparison whose manifest is not valid, which
   * draws nothing.
   *
   * @param {HTMLElement} slot
   * @param {{raw: unknown, openFile: (path: string) => void}} ctx
   * @returns {Promise<{dispose: () => void} | null>}
   */
  summary: async (slot, ctx) => {
    const result = validateManifest(ctx.raw);
    if (!result.ok) {
      return null;
    }
    const changedFiles = await changedFilesTree();
    return mountDiffSummary(slot, { manifest: result.manifest }, mb, {
      changedFiles,
      openFile: ctx.openFile,
    });
  },
  /**
   * Switch the served pin through the page's one switch, which every diff's controls share:
   * for a pull request's page, whose Browse code and offer of a newer head switch it too.
   * The answer says what happened in the words a diff's control says it; going on is the
   * caller's.
   *
   * @param {import("./diff-view-file.js").PinSelection} selection
   * @param {() => boolean} [wanted]
   * @returns {Promise<import("./diff-view-file.js").PinSwitchOutcome>}
   */
  switchPin: async (selection, wanted) => {
    const { pinSwitch } = await viewFileModule();
    return pinSwitch.switchTo(selection, wanted);
  },
});
