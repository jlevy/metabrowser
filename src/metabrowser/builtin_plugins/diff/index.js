// Diff built-in plugin — File Diff Format views for .patch/.diff files.
//
// Owns one view:
//   ("diff", "diff") — the document from /api/plugin/diff/document,
//                      validated by diff-model.js and rendered by
//                      diff-view.js. Validation before rendering is the
//                      point: the renderer only ever sees documents the
//                      conformance corpus vouches for.

import { changeSummaryRow, validateDocument, validateManifest } from "./diff-model.js";
import {
  fileDisclosure,
  mountDiffSummary,
  mountDiffView,
  mountFilePatch,
  presentationControlHtml,
  setChangeLoader,
  setGapLoader,
} from "./diff-view.js";

const mb = window.metabrowser;
if (!mb) {
  throw new Error("metabrowser diff plugin: SDK is unavailable");
}

// The view projects documents; fetching is the plugin's job. This wires
// the deferred-file loader to the same hook the whole comparison came
// from, narrowed to one path.
setChangeLoader((revision, path, options) => fetchComparison(revision, options, path));
// And the unchanged lines between a file's hunks to the same hook's `view=lines`, which a
// pull request's comparison route answers as the diff plugin's does: a run from its start,
// or up to its end, for a gap opened upward to a hunk.
setGapLoader((revision, path, ask, options) =>
  fetchComparison(revision, options, path, {
    view: "lines",
    ...(ask.whole
      ? { whole: "1" }
      : {
          ...("start" in ask ? { start: String(ask.start) } : { end: String(ask.end) }),
          count: String(ask.count),
        }),
  }),
);

// A comparison between two endpoints travels to the deferred loader as one opaque
// string, the way a revision does: `left...right` from their merge base, as
// `git diff` spells it, or `left..right` directly. No Git ref name contains `..`, so
// neither spelling can be mistaken for a revision.

/**
 * @typedef {{left: string, right: string, base_policy: "direct" | "merge_base", route?: string, image_route?: string, rendered_route?: string, branch?: {ref: string | null} | null}} Comparison
 *   *route* is the plugin route that answers the comparison, *rendered_route* the one
 *   that renders a changed Markdown file of it, and *image_route* the one that serves an
 *   image that Markdown shows: all come from the server that issued them, so this plugin
 *   spells none. A pull request's *branch* names the ref its file controls open.
 *   A null ref opens by commit. A null branch omits the controls.
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
 * The layer is an on-demand tier: a pull request's Changes loads it, and no other diff
 * does. It is two modules, diff-markdown.js and the diff-structured.js it imports
 * statically: on 2026-11-18, 34,717 and 14,341 bytes, 10,373 and 4,637 gzipped at
 * `delivery.GZIP_LEVEL` (`gzip -6 -c FILE | wc -c` reports them). The static import stays:
 * importing diff-structured.js at the first YAML or JSON file would spare a pull request
 * with only Markdown under 5 KB, and the second request starts only once the first is
 * parsed, 4 to 11 ms later on localhost (mb-8274 review C7).
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
    /**
     * @param {string} fileId
     * @param {AbortSignal} [signal]
     * @param {import("./diff-markdown.js").RenderedAsk & {ahead?: boolean}} [ask] A Markdown
     *   file's view or blocks (`GET github/pull-rendered-diff`), and whether this asks
     *   ahead of the reader.
     */
    load: (fileId, signal, { ahead = false, ...ask } = {}) =>
      mb.fetchPluginData(
        plugin,
        hook,
        { ...params, file: fileId, ...ask, ...(ahead ? { prefetch: "1" } : {}) },
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
  const first = views.firstScreenRendered(files);
  // A tree's renderer is the structured plugin's, which loads on demand: ask for it now
  // too, so Changes finds it loaded (mb-8274 review C1).
  const ids = new Set(first);
  const trees = files.some((file) => {
    const change = /** @type {Record<string, unknown> | null} */ (file);
    return (
      typeof change?.id === "string" &&
      ids.has(change.id) &&
      views.renderedFormat(change) !== "markdown"
    );
  });
  if (trees) {
    mb.plugins.load("structured").catch(() => {});
  }
  for (const fileId of first) {
    if (signal?.aborted) {
      return;
    }
    try {
      // The smaller answer: the server keeps the projection either view is drawn from.
      await markdown.load(fileId, signal, { ahead: true, view: "concise" });
    } catch {
      return;
    }
  }
}

/**
 * @param {string} key
 * @param {{signal?: AbortSignal}} [options]
 * @param {string} [file]
 * @param {Record<string, string>} [narrowing] `types=` or `view=types` (diff-type-filter.js),
 *   or `group=`, a fixed File type group (`ctx.group`).
 */
function fetchComparison(key, options, file, narrowing = {}) {
  const target = key.startsWith("/")
    ? pluginComparisonRoute(key)
    : { plugin: "diff", hook: "comparison", params: comparisonParams(key) };
  return mb.fetchPluginData(
    target.plugin,
    target.hook,
    { ...target.params, ...narrowing, ...(file === undefined ? {} : { file }) },
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
 * pin), so the page decides, and a link it does not keep opens the file on github.com
 * (`headFile`).
 *
 * @param {Comparison | undefined} comparison
 * @returns {() => boolean}
 */
function headLinksOpen(comparison) {
  const pin = pagePin();
  return () => pin !== null && pin === comparison?.right && !pinChanged;
}

/**
 * The file a link in rendered Markdown names at the comparison's head, on github.com, for
 * when the page does not show that head (`headLinksOpen`): static/repository-links.js reads
 * the link's `/view/` address back and spells the github.com one (`viewFileUrl`). Null
 * without a GitHub repository, or for a name that is not text.
 *
 * The renderer supplies the resolver it receives alongside the allowlist. A load
 * that misses the SDK deadline can still serve a projection that renders later.
 *
 * @param {Comparison | undefined} comparison
 * @returns {(href: string, links?: MetabrowserRepositoryLinksRuntime | null) => string | null}
 */
function headFile(comparison) {
  return (href, links) => {
    const head = comparison?.right;
    return links && typeof head === "string" ? links.viewFileUrl(mb.repository, head, href) : null;
  };
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

/** @typedef {typeof import("./diff-type-filter.js")} TypeFilterModule */

/**
 * diff-type-filter.js, for a comparison that may change more than one file, on a page whose
 * SDK has the File type menu; otherwise null.
 *
 * An on-demand tier, asked for beside the comparison so it is in hand when the diff mounts,
 * not a request after the comparison answers. A patch file's diff never asks, nor a
 * comparison its page already knows changes one file (*summaryTotals*); any other comparison
 * asks whether or not it turns out to change more than one. On 2026-11-22 it was 12,382
 * bytes, 4,075 gzipped at `delivery.GZIP_LEVEL`: one small local request beside the
 * comparison's own, which cli-ui-diff-view-file.tryscript.md counts. A failed import leaves
 * the diff without its filter, and says why in the console.
 *
 * @param {string} revision
 * @param {unknown} summaryTotals
 * @returns {Promise<TypeFilterModule | null> | null}
 */
function typeFilterModule(revision, summaryTotals) {
  const known = /** @type {{files?: unknown} | null | undefined} */ (summaryTotals)?.files;
  if (
    !revision ||
    typeof mb.filterControls?.typeMenu !== "object" ||
    (typeof known === "number" && known <= 1)
  ) {
    return null;
  }
  return import("./diff-type-filter.js").catch((error) => {
    console.error("metabrowser diff: the File type filter is unavailable", error);
    return null;
  });
}

/**
 * Whether a comparison's diff offers its File type filter: one of more than one file, on a
 * page whose SDK has the File type menu. A patch file's document, which no route narrows,
 * and a single file's diff have none.
 *
 * @param {Record<string, unknown>} document_
 * @param {unknown} summaryTotals
 */
function filterable(document_, summaryTotals) {
  return (
    typeof mb.filterControls?.typeMenu === "object" && wholeFiles(document_, summaryTotals) > 1
  );
}

/**
 * How many files the whole comparison changes: the page's own totals where it knows them,
 * as a commit's page does for a list cut short, or else the document's.
 *
 * @param {Record<string, unknown>} document_
 * @param {unknown} summaryTotals
 */
function wholeFiles(document_, summaryTotals) {
  const given = /** @type {{files?: unknown} | null | undefined} */ (summaryTotals)?.files;
  if (typeof given === "number") {
    return given;
  }
  const manifest = /** @type {{totals?: {files?: unknown}} | undefined} */ (document_.manifest);
  return typeof manifest?.totals?.files === "number" ? manifest.totals.files : 0;
}

// What a diff document that breaks the format says; where it breaks is the console's.
const INVALID_DOCUMENT = "This diff document is not valid.";

/**
 * A comparison narrowed to some file types (`types=`, sorted and joined), validated, with
 * the revision beside it for the deferred loader, as the whole comparison's.
 *
 * @param {string} revision
 * @param {string} types
 * @param {AbortSignal} [signal]
 * @returns {Promise<Record<string, unknown>>}
 */
async function loadNarrowed(revision, types, signal) {
  const payload = await fetchComparison(
    revision,
    signal === undefined ? undefined : { signal },
    undefined,
    { types },
  );
  const result = validateDocument(payload);
  if (!result.ok) {
    // Where the document breaks the format rides as the cause, for the console
    // (docs/design-system-messages.md).
    throw new Error(INVALID_DOCUMENT, { cause: result.error });
  }
  Object.defineProperty(result.document, "__revision", { value: revision, enumerable: false });
  return result.document;
}

/**
 * A comparison's diff with its File type filter in the toolbar (diff-type-filter.js). The
 * whole comparison mounts at once, or the choice its host kept (*kept*); a choice asks the
 * same route for `types=` and mounts that answer in its place, its summary still the whole
 * comparison's, and the counts are the route's `view=types` answer, asked for as the diff
 * mounts. Each choice is told to the host (`ctx.onTypes`). The handle a host holds goes to
 * whichever diff is mounted.
 *
 * @param {HTMLElement} container
 * @param {Record<string, unknown>} whole
 * @param {string} revision
 * @param {Parameters<typeof mountDiffView>[3]} options
 * @param {{summaryTotals?: unknown, onTypes?: (types: Array<string> | null) => void}} ctx
 * @param {TypeFilterModule} module
 * @param {{types: Array<string>, document: Record<string, unknown>} | null} kept
 */
function mountTypeFiltered(container, whole, revision, options, ctx, module, kept) {
  const { createTypeFilter, createTypeFilterControl, NONE_KEPT } = module;
  const fc = /** @type {NonNullable<typeof mb.filterControls>} */ (mb.filterControls);
  const element = document.createElement("div");
  /** @type {ReturnType<TypeFilterModule["createTypeFilter"]> | null} */
  let filter = null;
  const control = createTypeFilterControl(element, fc, {
    select: (types) => filter?.select(types),
    formatInteger: (value) => mb.formatInteger(value),
    shortcuts: mb.shortcuts,
  });
  // A narrowed diff's summary still lists every file: one it hides goes back to every type
  // and then to the file, as the host's own jumps do, unless the host opens files itself.
  const openFile =
    options?.openFile ?? ((/** @type {string} */ path) => void filter?.facade.scrollToFile(path));
  const presentation = {};
  filter = createTypeFilter({
    whole,
    wholeFiles: wholeFiles(whole, ctx.summaryTotals),
    initial: kept,
    load: (types, signal) => loadNarrowed(revision, types, signal),
    counts: (signal) =>
      /** @type {Promise<MetabrowserPublicTypeTally>} */ (
        fetchComparison(revision, { signal }, undefined, { view: "types" })
      ),
    mount: (document_, narrowed) =>
      mountDiffView(container, document_, mb, {
        ...options,
        presentation,
        toolbarControl: element,
        ...(narrowed === null
          ? {}
          : {
              summaryManifest: /** @type {Record<string, unknown>} */ (whole.manifest),
              emptyText: NONE_KEPT,
              openFile,
            }),
      }),
    paint: (state) => control.paint(state),
    swap: (change) => control.swap(change),
    ...(typeof ctx.onTypes === "function" ? { changed: ctx.onTypes } : {}),
    report(what, error) {
      console.error(
        "metabrowser diff: view load failed",
        {
          hook: what === "counts" ? "diff/comparison view=types" : "diff/comparison types",
          revision,
        },
        error,
      );
    },
  });
  control.attachKey();
  const { facade } = filter;
  return {
    ...facade,
    dispose() {
      facade.dispose();
      control.dispose();
    },
  };
}

// What a diff that could not load says in its place: one warning and its one remedy.
const LOAD_FAILURE = "Could not load this diff. Reload the page to try again.";

/** @param {HTMLElement} container @param {string} message */
function renderFailure(container, message) {
  const notice = document.createElement("div");
  notice.className = "notice diff-notice diff-availability";
  notice.setAttribute("data-severity", "error");
  notice.setAttribute("role", "alert");
  notice.textContent = message;
  container.append(notice);
  return { dispose: () => notice.remove() };
}

/** @type {MetabrowserPublicViewSpec} */
const diffView = {
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
    // A fixed File type group, `type:<id>`, which the host shows alone and the reader does
    // not change: a pull request's Docs tab is its documents (`type:docs`). Such a diff
    // has no File type chooser.
    const group = revision && typeof ctx.group === "string" && ctx.group ? ctx.group : null;
    /** @type {Record<string, string>} */
    const narrowing = group === null ? {} : { group };
    // One changed file, by its path: the route's one-file answer, which a deferred file's
    // loader asks for too, drawn as the whole comparison draws that file (`mountRenderedFile`).
    const file = revision && typeof ctx.file === "string" ? ctx.file : undefined;
    const startedAt = Date.now();
    // Asked for now, so its request overlaps the diff's own instead of following it. Its
    // failure waits for the mount below, and may never reach it: a diff that fails first
    // answers for itself, and the rejection still needs a handler.
    const opener = viewFileOpener(ctx.comparison);
    void opener.catch(() => {});
    const markdown = markdownLayer(ctx.comparison);
    // The tree the Diff summary is drawn on, whose display rule the file bars show paths by.
    const summaryTree = changedFilesTree();
    // Asked for beside the comparison too, for a diff of more than one file.
    const typeFilter =
      group === null && file === undefined ? typeFilterModule(revision, ctx.summaryTotals) : null;
    let payload;
    try {
      payload = revision
        ? await (ctx.raw === undefined
            ? fetchComparison(
                revision,
                signal === undefined ? undefined : { signal },
                file,
                narrowing,
              )
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
          : LOAD_FAILURE;
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
      console.warn("metabrowser diff: the document is not valid", result.error);
      return renderFailure(container, INVALID_DOCUMENT);
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
      return renderFailure(container, LOAD_FAILURE);
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
      files.some((file) => markdownViews.renderedFormat(file) !== null);
    ctx.onDocument?.(result.document);
    // A commit's page and a pull request's keep the Diff summary at their own top
    // (mb-pb35): a commit's asks for it there (`summaryHost`), and a pull request's draws it
    // itself and asks for none (`summary: false`). Direct diff documents and other
    // comparisons lead their toolbar with it.
    const summaryHost = ctx.summaryHost ?? null;
    /** @type {Parameters<typeof mountDiffView>[3]} */
    const options = {
      showSummary: ctx.summary !== false && (summaryHost !== null || !ctx.revision),
      summaryHost,
      // The commit's own totals, which the summary says where the list is cut short (A3 of
      // review A on #470).
      ...(ctx.summaryTotals === undefined ? {} : { summaryTotals: ctx.summaryTotals }),
      changedFiles,
      ...(typeof ctx.openFile === "function" ? { openFile: ctx.openFile } : {}),
      ...(ctx.unfold === true ? { unfold: true } : {}),
      ...(ctx.layout === "unified" ? { layout: ctx.layout } : {}),
      ...(ctx.show === undefined ? {} : { show: ctx.show }),
      ...(ctx.embedded ? { embedded: true } : {}),
      ...(typeof ctx.showPreference === "string" ? { showPreference: ctx.showPreference } : {}),
      ...(typeof ctx.emptyText === "string" ? { emptyText: ctx.emptyText } : {}),
      viewFile,
      ...(!rendered
        ? {}
        : {
            markdownViews,
            renderMarkdown: (fileId, signal, ask) => markdown.load(fileId, signal, ask),
            markdownTargets: markdownViews.markdownTargets(
              ctx.comparison?.image_route,
              headLinksOpen(ctx.comparison),
              headFile(ctx.comparison),
            ),
            ...(typeof ctx.markdownHoldMs === "number"
              ? { markdownHoldMs: ctx.markdownHoldMs }
              : {}),
          }),
    };
    const module =
      typeFilter !== null && filterable(result.document, ctx.summaryTotals)
        ? await typeFilter
        : null;
    if (signal?.aborted) {
      return null;
    }
    if (module === null) {
      return mountDiffView(container, result.document, mb, options);
    }
    // The choice the host kept, as a pull request's page keeps it across its tabs, mounts
    // first; one whose files do not load leaves every type, and the host is told so.
    const keptTypes = Array.isArray(ctx.types) && ctx.types.length > 0 ? ctx.types : null;
    let kept = null;
    if (keptTypes !== null) {
      const param = module.typesParam(keptTypes);
      try {
        kept =
          param === null
            ? null
            : { types: keptTypes, document: await loadNarrowed(revision, param, signal) };
      } catch (error) {
        if (signal?.aborted) {
          return null;
        }
        console.error(
          "metabrowser diff: view load failed",
          { hook: "diff/comparison types", revision },
          error,
        );
        ctx.onTypes?.(null);
      }
      if (signal?.aborted) {
        return null;
      }
    }
    return mountTypeFiltered(container, result.document, revision, options, ctx, module, kept);
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
   * A comparison's File type counts, the route's `view=types` answer at the address
   * `prefetch` asks, for a page that decides what to offer by them: a pull request's page
   * shows its Docs tab only where the comparison changes a document.
   *
   * @param {Comparison} comparison
   * @param {AbortSignal} [signal]
   * @returns {Promise<unknown>}
   */
  typeCounts: (comparison, signal) =>
    fetchComparison(
      comparisonKey(comparison),
      signal === undefined ? undefined : { signal },
      undefined,
      { view: "types" },
    ),
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
   * The rows a comparison's Diff summary lists, one for each file of the manifest *raw*
   * holds, each made as the summary makes its own (`changeSummaryRow`), for a page that
   * draws the comparison's files in a tree of its own: the Pulls tab draws a native stack's
   * under its Whole stack row, from the comparison the stack's page draws its Diff summary
   * of (builtin_plugins/github/stack-files.js). Null for a comparison whose manifest is not
   * valid, or where the shared changed-files tree, whose display rule the rows take, did not
   * load.
   *
   * @param {unknown} raw
   * @returns {Promise<MetabrowserChangedFileRow[] | null>}
   */
  summaryRows: async (raw) => {
    const result = validateManifest(raw);
    const changedFiles = result.ok ? await changedFilesTree() : null;
    if (!result.ok || changedFiles === null) {
      return null;
    }
    const files = /** @type {Record<string, unknown>[]} */ (result.manifest.files);
    return files.map((change) => changeSummaryRow(change, changedFiles.displayPath));
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
};
mb.registerView("diff", "diff", diffView);

/**
 * One changed file of a comparison drawn whole by this view's own render, for a page that
 * shows that file in its own place: a guided review's step draws a Markdown file it cites
 * whole as the pull request's Docs tab draws it, and a YAML or JSON file as Changes does.
 * The file is the comparison route's one-file answer (`file=`, which a deferred file's
 * loader asks for too), drawn with *ctx* as a host passes this view, so it has the bar,
 * the Rendered | Source chooser, and the toolbar that host's diff would draw; the render
 * loads the rendered layer (`markdownLayer`) as Changes does, so a page that draws no such
 * file never loads it.
 *
 * *settled* is true once the file is drawn as it stays: its rendered layer drawn, or its
 * wait for it over (`firstScreen`, at most *ctx*'s `markdownHoldMs`), so a page that keeps
 * the file out of sight until then first shows it at the height it keeps. It is false when
 * it is not drawn: the view's notice then says why in the file's place, as for a read that
 * failed or a render that threw, or the handle was disposed first, which leaves nothing.
 * *dispose* ends the read on its way, or removes what was drawn.
 *
 * @param {HTMLElement} container
 * @param {NonNullable<MetabrowserPublicRenderContext["comparison"]>} comparison
 * @param {string} path
 * @param {MetabrowserPublicRenderContext} [ctx]
 * @returns {{settled: Promise<boolean>, show: (mode: "diff" | "current" | "full") => void, dispose: () => void}}
 */
function mountRenderedFile(container, comparison, path, ctx = {}) {
  const controller = new AbortController();
  /** @type {{dispose?: () => void, show?: (mode: "diff" | "current" | "full") => void} | null} */
  let mounted = null;
  /** @type {"diff" | "current" | "full" | null} */
  let requested = null;
  const settled = Promise.resolve(
    diffView.render(container, {
      ...ctx,
      comparison,
      file: path,
      embedded: true,
      layout: "unified",
      // The file alone: a one-file diff draws no summary of its own anyway.
      summary: false,
      comparisonSignal: controller.signal,
    }),
  ).then(
    async (handle) => {
      const owned =
        /** @type {{dispose?: () => void, show?: (mode: "diff" | "current" | "full") => void, currentFile?: unknown, firstScreen?: () => Promise<unknown>} | null} */ (
          handle
        );
      if (controller.signal.aborted) {
        owned?.dispose?.();
        return false;
      }
      mounted = owned;
      if (requested !== null) {
        owned?.show?.(requested);
      }
      // A drawn diff has its file API; a failure's notice, which says why, has none.
      if (typeof owned?.currentFile !== "function") {
        return false;
      }
      await owned.firstScreen?.();
      return !controller.signal.aborted;
    },
    (error) => {
      if (controller.signal.aborted) {
        return false;
      }
      console.error("metabrowser diff: view load failed", { hook: "diff/file", path }, error);
      mounted = renderFailure(container, LOAD_FAILURE);
      return false;
    },
  );
  return {
    settled,
    show(mode) {
      requested = mode;
      mounted?.show?.(mode);
    },
    dispose() {
      controller.abort();
      mounted?.dispose?.();
      mounted = null;
    },
  };
}

// What a plugin that requires this one gets from `mb.plugins.load("diff")`: one file's hunks
// drawn as Changes draws them, and one changed file drawn whole as its comparison's diff draws
// it, for a page that shows part of a change in its own place.
export { mountFilePatch, mountRenderedFile };

/** @param {Comparison} comparison @param {string} path @param {AbortSignal} signal */
export function loadFullSource(comparison, path, signal) {
  const key = comparisonKey(comparison);
  return fetchComparison(key, { signal }, path, { view: "lines", whole: "1" });
}

/** The comparison chrome used by the guide block that owns its file cards. */
export function guidePatchDrawer() {
  return Object.assign(
    /**
     * @param {HTMLElement} body @param {Record<string, unknown>} change
     * @param {Record<string, unknown>} patch
     * @param {{path: string, load: (signal: AbortSignal) => Promise<unknown>} | null} [fullFile]
     */
    (body, change, patch, fullFile) => mountFilePatch(body, change, patch, mb, fullFile),
    {
      /**
       * The bar and chevron that fold a file's card in Changes, for a card the guide draws
       * itself: the diff view's own builder (`fileDisclosure`).
       *
       * @param {HTMLElement} section @param {HTMLElement} folded
       * @param {(expanded: boolean) => void} [changed] Hears each fold and each opening.
       */
      disclose: (section, folded, changed) => fileDisclosure(section, folded, changed),
      /**
       * @param {HTMLElement} host @param {boolean} full
       * @param {"diff" | "current" | "full" | null} initial
       * @param {(mode: "diff" | "current" | "full") => void} choose
       */
      controls(host, full, initial, choose) {
        const chips = mb.filterControls;
        if (!chips) {
          return { dispose() {} };
        }
        host.className = "diff-toolbar";
        const control = document.createElement("div");
        control.className = "diff-toolbar-end diff-show-control";
        const paint = (/** @type {typeof initial} */ mode) => {
          const focused =
            document.activeElement !== null &&
            document.activeElement !== undefined &&
            control.contains(document.activeElement);
          control.innerHTML = presentationControlHtml(chips, mode, full);
          if (mode === null) {
            control.querySelector("[data-chip-value]")?.setAttribute("tabindex", "0");
          } else if (focused) {
            /** @type {HTMLElement | null} */ (
              control.querySelector(`[data-chip-value="${mode}"]`)
            )?.focus();
          }
        };
        paint(initial);
        host.append(control);
        const dispose = chips.bind(control, {
          onChange(key, value, select) {
            if (
              select === "one" &&
              key === "diff-show" &&
              (value === "diff" || value === "current" || (full && value === "full"))
            ) {
              paint(value);
              choose(value);
            }
          },
        });
        return { dispose };
      },
    },
  );
}
