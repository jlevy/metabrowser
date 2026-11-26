// Unified diff renderer over File Diff Format.
//
// A diff of more than one file opens with its Diff summary, the toolbar's header that says
// what the change set holds and opens to its files as a tree by folder (diff-summary.js).
//
// Each file renders as a section under a bar: the section-disclosure
// primitive carrying the filename (styled as a filename, not a
// heading); right after the name a copy-path control riding the shared
// [data-mb-copy] delegation; the inline +N −N stat pair and change
// notes; then the View file controls of diff-view-file.js when the page
// can open a file at a commit; and, at the bar's end, a rendered file's
// view chooser (diff-markdown.js). The diff's own choosers,
// Diff | Current and Split | Unified, end its toolbar. Sections start
// expanded; the bar collapses the body without disposing it.
// Every availability state has exactly one rendering path — an absent
// patch is a labeled state, never an empty box. Rendering is
// deliberately dumber than the model: the data plane is tested by the
// conformance corpus and CLI goldens, and this layer only projects it.

import { foldExpander, shellIcon } from "./diff-fold.js";
import { diffSummaryOf, fileChangeLabel, plainTotals, validateDocument } from "./diff-model.js";
import { buildFileRenderModel, refineFileChangedRuns } from "./diff-render-model.js";
import { highlightFileSyntax, syntaxInputBytes } from "./diff-syntax.js";

/**
 * @typedef {object} DiffViewApi
 * @property {(data: Record<string, unknown>) => boolean} isLargeTextPreview
 * @property {(source: string, language: string, options?: {signal?: AbortSignal, inputBytes?: number}) => Promise<MetabrowserSyntaxTokenLines | null>} highlightSyntax
 * @property {(pathOrName: string) => string} langForPath
 * @property {(<T extends Element>(element: T) => T) | undefined} [ownDelegate]
 * @property {NonNullable<MetabrowserPublicSdk["filterControls"]> | undefined} [filterControls]
 * @property {Pick<MetabrowserPublicSdk["perf"], "measure" | "measureAsync"> | undefined} [perf]
 * @property {MetabrowserPublicSdk["ensureAsset"]} [ensureAsset]
 * @property {MetabrowserPublicSdk["loadKpressAssets"]} [loadKpressAssets]
 * @property {MetabrowserPublicSdk["ensureKindAssets"]} [ensureKindAssets]
 * @property {MetabrowserPublicSdk["plugins"]} [plugins]
 * @property {{get: <T>(name: string, fallback: T) => T, set: (name: string, value: unknown) => boolean} | undefined} [prefs]
 * @property {MetabrowserPublicSdk["shortcuts"]} [shortcuts]
 * @property {MetabrowserPublicSdk["formatInteger"]} [formatInteger]
 * @property {MetabrowserPublicSdk["countPartsNodes"]} [countPartsNodes] The shell's painter
 *   of a count summary, which a Diff summary is drawn with.
 * @property {MetabrowserPublicSdk["changeLine"]} [changeLine] The brief change line's builder.
 * @property {MetabrowserPublicSdk["changeLineNodes"]} [changeLineNodes] Its painter.
 * @property {MetabrowserPublicSdk["navigation"]} [navigation]
 * @property {MetabrowserPublicSdk["repository"]} [repository] What a rendered file's links
 *   into the repository open is read against (static/repository-links.js).
 * @property {MetabrowserPublicSdk["sourceKind"]} [sourceKind]
 * @property {MetabrowserPublicSdk["decorateExternalLink"]} [decorateExternalLink]
 * @property {MetabrowserPublicSdk["loadRepositoryLinks"]} [loadRepositoryLinks]
 */

/**
 * @typedef {object} FileViewState
 * @property {Record<string, unknown>} change
 * @property {HTMLElement} body
 * @property {Set<string>} expandedFolds
 * @property {boolean} unfold Whether every fold of the file opens as it is drawn, as a
 *   pull request's Docs tab shows its documents whole (`mountDiffView`'s *unfold*).
 * @property {Set<string>} foldsOpened The folds *unfold* has opened: each opens the first
 *   time it is drawn, so one the reader closes stays closed when the file is drawn again.
 * @property {Map<string, {timer: number}>} foldTasks
 * @property {Record<string, unknown>} patch
 * @property {DiffViewApi} api
 * @property {ReturnType<typeof buildFileRenderModel>} renderModel
 * @property {{host: HTMLElement, line: ReturnType<typeof buildFileRenderModel>["hunks"][number]["lines"][number], side: "old" | "new"}[]} textHosts
 * @property {Projection | null} drawn The projection its body draws now, null before the first.
 * @property {GapSource | null} gaps Where the unchanged lines between hunks come from, or
 *   null where this diff has none to read, so each hunk's separator is a plain header.
 * @property {GapLines} gapLines What has been read of them.
 * @property {FullSource | null} fullSource
 * @property {{rows: DiffLine[] | null, message: string, stop: (() => void) | null}} full
 */

/**
 * How a file's diff reads the unchanged lines its hunks leave out, and keeps the reader's
 * place while it draws them: the comparison route's `view=lines`, through the loader the
 * plugin sets (`setGapLoader`), for a diff whose document came from a comparison. A patch
 * file names no snapshot, and a Guided Review excerpt draws no gaps, so both have none.
 *
 * @typedef {object} GapSource
 * @property {(path: string, ask: GapAsk) => Promise<unknown>} load
 * @property {(state: FileViewState, change: () => void) => void} keep Run *change*, which
 *   draws rows, and hold the row at the pane's top where it was while they are drawn.
 * @property {number} context The context lines Git wrote around each change, past which a
 *   last hunk's trailing context may not be the end of the file.
 * @property {string} comparisonId The comparison the diff drew, which every answer names:
 *   one for another, as a ref that moved since answers, is refused (`gapAnswer`).
 * @property {AbortSignal} signal The mounted view's, which ends its asks and highlighting.
 */

/**
 * @typedef {{
 *   wanted: () => boolean, load: () => Promise<unknown>,
 *   keep: (state: FileViewState, change: () => void) => void, signal: AbortSignal,
 *   comparisonId?: string, path: string, open?: (label: HTMLElement) => void
 * }} FullSource
 */

/**
 * @typedef {({start: number, count: number} | {end: number, count: number}) & {whole?: true}} GapAsk
 *   At most *count* of the new side's lines from *start*, 1-based, for a gap opened downward
 *   from a hunk, or before *end*, for one opened upward to a hunk, so an answer its byte
 *   bound cuts short keeps the lines beside the hunk.
 */

/**
 * What a file holds of the unchanged lines its hunks leave out, kept while its diff is
 * mounted, so a fold drawn again, in another layout or after it closed, asks for nothing.
 *
 * @typedef {object} GapLines
 * @property {Map<number, DiffLine>} byNumber Each line read, by its new number.
 * @property {number | null} lineCount The new side's lines in all, once an answer says.
 * @property {Map<string, Promise<void>>} asked Asks on their way, by range.
 * @property {Map<string, number>} reach Where an open whose answer its byte bound cut short
 *   stopped, by the end it opened from (`up:<end>` or `down:<start>`): the line past its
 *   last, so it opens to the same lines again and its nested bar stands for the rest.
 * @property {boolean} refused The route declined this file's lines, so its gaps draw as
 *   plain headers.
 * @property {number} syntaxBytes The bytes of gap lines highlighted so far, which count
 *   against `SYNTAX_HIGHLIGHT_MAX_BYTES` beside the hunks' own.
 */

/**
 * @typedef {object} MountedDiffState
 * @property {DiffViewApi | undefined} api
 * @property {Map<string, FileEntry>} byNewPath Each file by the path it has now.
 * @property {Map<string, FileEntry>} byOldPath Each file by the path it had.
 * @property {Map<HTMLElement, FileEntry>} bySection Each file by its mounted section.
 * @property {() => void} notifyCurrentFile Queue a current-file report for subscribers.
 * @property {AbortController} controller
 * @property {Map<string, DeferredFile>} deferred Files asked for when they are reached, by id.
 * @property {number} deferredFailed Files of this comparison that could not be loaded.
 * @property {Map<HTMLElement, string>} deferredBySection
 * @property {boolean} disposed
 * @property {FileViewState[]} files
 * @property {number} generation
 * @property {ReturnType<typeof createHydrationScheduler>} hydration
 * @property {{controller: ReturnType<import("./diff-markdown.js").createMarkdownViews>, format: typeof import("./diff-markdown.js").renderedFormat} | null} markdown
 * @property {IntersectionObserver | null} hydrationObserver
 * @property {Set<string>} reached Held files whose section is within the hydration
 *   lookahead, whether or not their body is to be drawn (`bodyWanted`).
 * @property {boolean} awaitingWidth Nothing is drawn until the first report of a width.
 * @property {"unified" | "split"} chosenLayout What the reader chose, whatever fits.
 * @property {boolean} insistedOnSplit The reader chose Split where it does not fit.
 * @property {"unified" | "split"} layout What the diff draws.
 * @property {HTMLElement | null} layoutControl
 * @property {MetabrowserPublicPluginShortcutHandle | null} layoutKey `L`, on the option it
 *   would select, once the toolbar has drawn the control.
 * @property {number} layoutGeneration
 * @property {boolean} listTruncated The comparison's own list stopped at its bound.
 * @property {boolean} narrow The diff is too narrow for Split.
 * @property {HTMLElement} hydrationFailure
 * @property {HTMLElement | null} pinned The file a jump put at the top, until the reader moves.
 * @property {number} pinnedAt When the pin was set, on the event clock, so the key that
 *   caused a jump does not also release it.
 * @property {AbortController | null} pinListeners
 * @property {Record<string, unknown>} resolved
 * @property {HTMLElement} root
 * @property {Promise<void>} enhancementTail
 * @property {HTMLElement[]} sections In the comparison's order.
 * @property {HTMLElement | null} spacer Room past the last file, for a jump near the end.
 * @property {Set<number>} timers
 * @property {import("./diff-view-file.js").ViewFileOpener | null} viewFile
 * @property {HTMLElement | null} viewFileBusy The control whose switch is on its way.
 * @property {{change: Record<string, unknown>, controls: HTMLElement[], said: {element: HTMLElement, timer: number}}[]} viewFileBars
 *   Each bar that has controls, with the change they open, for a repaint when the page
 *   learns its pin is no longer served.
 * @property {Set<{timer: number, resolve: (active: boolean) => void}>} yielders
 * @property {MetabrowserChangedFilesTree | null} changedFiles The shared tree the Diff
 *   summary is drawn on, or null where it could not be loaded.
 * @property {((path: string) => void) | null} openFile How the host opens one changed file
 *   at its own address, or null where a file has none in this diff.
 * @property {boolean} unfold Whether folds open as they are drawn (*unfold*).
 * @property {Shown} show What the diff shows, one choice for every file (`setShow`).
 * @property {string} showPreference The preference the choice is remembered as: the
 *   surface's own (*showPreference*), or `diff.show`.
 * @property {boolean} canShowFull Whether this comparison can read complete files.
 * @property {{layout?: "split" | "unified"}} presentation The layout chosen in this comparison.
 * @property {HTMLElement | null} showControl The toolbar's Diff | Current chooser.
 * @property {MetabrowserPublicPluginShortcutHandle | null} showKey `N`, on the chip it would
 *   select in the toolbar's chooser (`attachShowKey`).
 * @property {{dispose: () => void}[]} pdfCards The PDF cards binary changes drew, to
 *   dispose with the view.
 */

/**
 * What a diff shows: its changes, or the new version alone with its changes marked.
 *
 * @typedef {"diff" | "current" | "full"} Shown
 */

/**
 * What a file's code rows are drawn as: its changes in one of the two layouts, or, in
 * Current, its new version in one column whatever the layout (`projectionOf`).
 *
 * @typedef {"unified" | "split" | "current"} Projection
 */

/**
 * A place on the screen a redraw keeps: the file at the pane's top, by its section's top in
 * the viewport's coordinates, and, for a Diff | Current choice, a row of that file that both
 * draw and where it is to be (`placeOfTopRow`). *find* answers the element that is that row
 * now, or null where it is not drawn; *state* is the code file whose rows it is.
 *
 * @typedef {object} Place
 * @property {HTMLElement} section
 * @property {number} top
 * @property {{find: () => HTMLElement | null, top: number, state: FileViewState | null}} [row]
 */

/**
 * @typedef {object} FileEntry
 * @property {Record<string, unknown>} change
 * @property {HTMLElement} section
 * @property {() => void} expand
 */

/**
 * @typedef {{manifest: {files: Record<string, unknown>[]}, patches: Record<string, Record<string, unknown>>}} OneFileAnswer
 *   One file's answer, as the comparison route gives it for one path.
 *
 * @typedef {object} DeferredFile
 * @property {HTMLElement} section
 * @property {HTMLElement} body
 * @property {Record<string, unknown>} change
 * @property {OneFileAnswer | null} held The answer already in hand, for a ready file the
 *   mount did not draw: drawn when it is reached, and never asked for.
 * @property {string} revision
 * @property {HTMLElement | null} box The progress box while it is being asked for.
 * @property {ReturnType<typeof setTimeout> | null} slow
 * @property {number} startedAt
 */

/**
 * What the mount draws its first rows by, measured with the root in its container: the
 * pane's height, how far down the pane the diff starts, and what one file's bar and one row
 * of lines take on the page.
 *
 * @typedef {{paneHeight: number, rootTop: number, barPx: number, rowPx: number}} ScreenGeometry
 */

/**
 * What a jump did, for the changed-files list that asked. A row in that list comes from
 * GitHub's own list of the pull request's files, so it can name a path this comparison does
 * not hold: the two are computed apart, and this one stops at its bound.
 *
 * @typedef {(
 *   {kind: "jumped", fileId: string, path: string, availability: string, lines: Promise<JumpOutcome>} |
 *   {kind: "not_in_comparison", path: string, listTruncated: boolean} |
 *   {kind: "disposed", path: string}
 * )} FileJump
 *
 * What a comparison holds at a path, for the same list, with nothing moved. `changeKind` is
 * the change's own kind (`modified`, `renamed`, and so on), apart from the answer's.
 *
 * @typedef {(
 *   {kind: "file", path: string, fileId: string, changeKind: string, availability: string} |
 *   {kind: "not_in_comparison", path: string, listTruncated: boolean}
 * )} FileLookup
 */

/**
 * Fetch one file's change from a comparison. Injected by the plugin so
 * this module keeps its only job — projecting a document — and stays
 * testable without a shell.
 *
 * @type {(revision: string, path: string, options?: {signal?: AbortSignal}) => Promise<Record<string, unknown>>}
 */
let loadOneChange = async () => {
  throw new Error("no loader configured");
};

/** @returns {DiffViewApi} */
function plainSyntaxApi() {
  return {
    highlightSyntax: async () => null,
    isLargeTextPreview: () => true,
    langForPath: () => "",
    filterControls: undefined,
    prefs: undefined,
  };
}

/** @param {(revision: string, path: string, options?: {signal?: AbortSignal}) => Promise<Record<string, unknown>>} loader */
export function setChangeLoader(loader) {
  loadOneChange = loader;
}

/**
 * Read a run of one changed file's unchanged lines from a comparison: the route's
 * `view=lines` answer. Injected by the plugin, as `loadOneChange` is; until it is set, no
 * diff reads its gaps and every hunk's separator is a plain header.
 *
 * @type {((revision: string, path: string, ask: GapAsk, options?: {signal?: AbortSignal}) => Promise<unknown>) | null}
 */
let loadGapLines = null;

/** @param {(revision: string, path: string, ask: GapAsk, options?: {signal?: AbortSignal}) => Promise<unknown>} loader */
export function setGapLoader(loader) {
  loadGapLines = loader;
}

/**
 * The context lines the comparison wrote around each change (`GapSource.context`), where
 * its files read their gaps, else null.
 *
 * @param {MountedDiffState} view
 * @param {string | undefined} revision
 * @returns {number | null}
 */
function gapContextOf(view, revision) {
  if (!revision || loadGapLines === null) {
    return null;
  }
  const options = /** @type {{context?: unknown} | undefined} */ (view.resolved.options);
  const context = Number(options?.context ?? 3);
  return Number.isInteger(context) && context >= 0 ? context : 3;
}

/**
 * Where a mounted comparison's files read their gaps, or null for a diff with no comparison
 * to read them from (a patch file's) or no loader. Rows a gap draws keep the reader's place
 * as a layout change does: the row at the pane's top stays where it is on the screen, or a
 * jump's file stays at the top, while every batch of them is drawn.
 *
 * @param {MountedDiffState} view
 * @param {string | undefined} revision
 * @returns {GapSource | null}
 */
function gapSourceOf(view, revision) {
  const loader = loadGapLines;
  const context = gapContextOf(view, revision);
  if (loader === null || context === null || !revision) {
    return null;
  }
  const { signal } = view.controller;
  return {
    context,
    comparisonId: String(view.resolved.comparison_id ?? ""),
    load: (path, ask) => loader(revision, path, ask, { signal }),
    keep(state, change) {
      const anchor = view.pinned === null ? placeOfTopRow(view, view.show) : null;
      change();
      holdPlace(view, anchor);
      settlePlace(view, anchor, state);
    },
    signal,
  };
}

/**
 * @param {MountedDiffState} view @param {GapSource | null} gaps
 * @param {Record<string, unknown>} change
 * @returns {FullSource | null}
 */
function fullSourceOf(view, gaps, change) {
  const path = /** @type {{path?: unknown} | null} */ (change.new)?.path;
  if (gaps === null || typeof path !== "string") {
    return null;
  }
  return {
    path,
    wanted: () => view.show === "full",
    load: () => gaps.load(path, fullSourceAsk()),
    keep: gaps.keep,
    signal: gaps.signal,
    comparisonId: gaps.comparisonId,
    open: (label) => appendFullFileAction(view, change, label),
  };
}

function fullSourceAsk() {
  return /** @type {const} */ ({ start: 1, count: GAP_LINES, whole: true });
}

// Copy for states that are facts about the change, not steps the
// reader can take. `deferred` is deliberately absent: it is progress,
// and progress is a spinner, never prose.
const AVAILABILITY_COPY = /** @type {Record<string, string>} */ ({
  binary: "Binary file; no textual diff.",
  too_large: "This change is too large to show inline.",
  timed_out: "Producing this diff timed out.",
  failed: "Could not produce this diff.",
  stale: "The comparison changed underneath this file. Reload the page to see it as it is now.",
  unsupported: "This change cannot be shown as a text diff.",
});

/**
 * The side of a binary change whose first page a PDF card shows: the new side, or the
 * old one for a deletion, when its path ends in `.pdf` and its content is a blob of the
 * repository the comparison was read from. Null for every other change.
 *
 * A PDF named without the extension is still a binary change with no card: the
 * comparison does not sniff its sides, and the file bar's View file reaches its view.
 *
 * @param {Record<string, unknown>} change
 * @returns {{path: string, oid: string} | null}
 */
export function pdfCardSide(change) {
  const side = /** @type {Record<string, unknown> | undefined} */ (
    change.kind === "deleted" ? change.old : change.new
  );
  const path = side?.path;
  const content = /** @type {Record<string, unknown> | undefined} */ (side?.content);
  if (typeof path !== "string" || !/\.pdf$/i.test(path)) {
    return null;
  }
  if (content?.kind !== "git_object" || typeof content.oid !== "string") {
    return null;
  }
  return { path, oid: content.oid };
}

/**
 * Below a binary change's line, the PDF plugin's card for the side `pdfCardSide` names
 * (`requires = ["pdf"]` in manifest.toml). The card holds an image the server drew,
 * never a viewer; a page whose plugins cannot load leaves the line alone.
 *
 * The card carries the file bar's own View file controls (`renderViewFileControl`), so
 * the PDF's page in Metabrowser, with its viewer, Open, and Download, is one press from
 * the card and not only from the bar above it. They are registered with the bar's, so a
 * pin change repaints both, and a refusal is said under the card. A deleted PDF's card
 * has none, as its bar has none.
 *
 * @param {MountedDiffState} view
 * @param {Record<string, unknown>} change
 * @param {HTMLElement} body
 */
function appendPdfCard(view, change, body) {
  const side = pdfCardSide(change);
  const plugins = view.api?.plugins;
  if (side === null || typeof plugins?.load !== "function") {
    return;
  }
  const slot = el("div", "diff-pdf-card");
  body.append(slot);
  /** @type {{dispose: () => void} | null} */
  let card = null;
  let disposed = false;
  view.pdfCards.push({
    dispose() {
      disposed = true;
      card?.dispose();
      // The card's View file notice goes with it.
      slot.replaceChildren();
      slot.remove();
    },
  });
  // A load that throws at once is a page without the plugin, as one that rejects is.
  void new Promise((resolve) => resolve(plugins.load("pdf")))
    .then((pdf) => {
      const mount = /** @type {{mountPdfCard?: Function} | undefined} */ (pdf)?.mountPdfCard;
      if (disposed || view.disposed || typeof mount !== "function") {
        return;
      }
      const name = side.path.slice(side.path.lastIndexOf("/") + 1) || side.path;
      const controls = pdfCardControls(view, change);
      card = mount(slot, { oid: side.oid, name, links: controls.links });
      if (controls.notice !== null) {
        slot.append(controls.notice);
      }
    })
    .catch(() => slot.remove());
}

/**
 * The View file controls a PDF card carries: the ones the file bar draws for *change*,
 * registered with the bar's so a repaint reaches them, and the notice their refusals are
 * said in, which goes under the card. No controls and no notice where the bar has none.
 *
 * @param {MountedDiffState} view
 * @param {Record<string, unknown>} change
 * @returns {{links: HTMLElement[], notice: HTMLElement | null}}
 */
function pdfCardControls(view, change) {
  const actions = view.viewFile?.actions(change, view.resolved) ?? [];
  if (actions.length === 0) {
    return { links: [], notice: null };
  }
  const notice = el("div", "diff-availability diff-file-notice");
  notice.setAttribute("role", "status");
  notice.hidden = true;
  const said = { element: notice, timer: 0 };
  const links = actions.map((action) => renderViewFileControl(action, view, said));
  view.viewFileBars.push({ change, controls: links, said });
  return { links, notice };
}

// What a file whose availability the table does not name says.
const UNAVAILABLE_COPY = "These changes are unavailable.";

// A single file's answer owes the file or a reason. `deferred` there is neither, so it is
// said as what it is and not as a failure of this page; in a document with no source to
// ask, a deferred file is simply unavailable, which the table above's fallback says.
const DEFERRED_AGAIN_COPY =
  "The server did not load this file's changes. Reload the page to try again.";

// Chrome 151, five runs of explorations/diff-intraline/benchmark.html:
// ordinary edits completed in <= 1.2 ms, an 8 MiB mostly-equal line in
// <= 20.5 ms, and unrelated 8 MiB lines reached this bound in <= 32.6 ms.
// This deterministic limit caps edit-distance work; it does not impose a
// smaller input-size cutoff than the existing patch bound.
const INTRALINE_WORK_BUDGET = 1_000_000;

// A load this slow is worth a console record even when it eventually
// succeeds: a reader watching a spinner deserves a diagnosable stall.
const SLOW_LOAD_MS = 4000;

// Match the Pulls list's short forward lookahead. Only one nearby file is worked on,
// and extending the bottom edge keeps on-screen files ahead of off-screen files.
const HYDRATION_AHEAD_PX = 240;

/**
 * The app's standard progress box: hidden until --loading-state-delay,
 * so a fast load never flashes a spinner.
 *
 * @param {string} label Accessible name; never rendered as prose.
 * @returns {HTMLElement}
 */
function progressBox(label) {
  const box = el("div", "diff-progress mb-delayed-loading");
  box.setAttribute("role", "status");
  box.setAttribute("aria-label", label);
  const spinner = el("span", "spinner spinner-sm");
  spinner.setAttribute("aria-hidden", "true");
  box.append(spinner);
  return box;
}

/**
 * Report a load that failed or overran, with everything needed to
 * diagnose it from the console alone.
 *
 * @param {string} what
 * @param {Record<string, unknown>} detail
 * @param {unknown} [error]
 */
function reportLoad(what, detail, error) {
  const payload = { ...detail, elapsedMs: Math.round(Number(detail.elapsedMs) || 0) };
  if (error === undefined) {
    console.warn(`metabrowser diff: ${what} is slow`, payload);
    return;
  }
  console.error(`metabrowser diff: ${what} failed`, payload, error);
}

let sectionSequence = 0;
let foldSequence = 0;

const SETTINGS = /** @type {Record<string, number>} */ (
  /** @type {{METABROWSER_SETTINGS?: Record<string, number>}} */ (globalThis)
    .METABROWSER_SETTINGS ?? {}
);
// Server-set, with the same defaults, so a page served by an older
// build still folds sensibly. 0 disables folding.
const FOLD_THRESHOLD = Number(SETTINGS.DIFF_FOLD_THRESHOLD ?? 40);
const FOLD_VISIBLE = Number(SETTINGS.DIFF_FOLD_VISIBLE ?? 20);
// The unchanged lines one open of a hunk's gap shows, the server's `DIFF_GAP_LINES`
// (settings.py), whose comment holds the measurement.
const GAP_LINES = Math.max(1, Number(SETTINGS.DIFF_GAP_LINES ?? 1000));
// The existing measured layout projection batch creates at least three row
// elements per file. Keeping fold expansion to 100 rows is the stricter of
// the two projection budgets and gives the browser a task boundary between
// chunks of a very large changed run.
const FOLD_MATERIALIZATION_BATCH_ROWS = 100;
// Chrome 151 took 223.7 ms to reproject 1,000 ready files in one pass.
// One-tenth-sized batches keep the same measured work below the 200 ms
// interaction budget; explorations/diff-layout/README.md records the fixture.
const LAYOUT_PROJECTION_BATCH_FILES = 100;
// What Split needs to show both sides: the `min-width` of `.diff-hunk-split` in styles.css,
// in ems of the diff's text, which tests/test_diff_browser_js.py keeps equal to this, and
// the 2 px of border around a file. Measured 2026-11-02 in Chrome 152 at 14 px on a 34-file
// pull request: with `.diff-root` 618 px wide every file body fits, and at 617 px each
// overflows by a pixel. At 440 px a body shows 438 of its 616 px, and the right column's
// text is behind a sideways scroll, so an added line reads as a blank gap.
export const SPLIT_MIN_WIDTH_EM = 44;
const FILE_BORDER_PX = 2;
// How much more room going back to Split takes. Drawing the other layout changes the page's
// height, and so whether the pane has a scrollbar, which takes width: 11 px in the same
// Chrome. With no margin, a pane within that of the limit could flip for as long as it stayed.
export const SPLIT_RETURN_MARGIN_PX = 20;
const SPLIT_TOO_NARROW_TIP =
  "Too narrow for Split, so this shows Unified. Choose Split to scroll sideways.";
// Why the layout chips are unavailable while reading Excerpt or Full.
const LAYOUT_IN_CURRENT_TIP = "Switch to Diff to change the layout.";

/** @param {string} tag @param {string} className @param {string} [text] */
function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/**
 * A box saying something about the diff it sits in: `.notice`, the shell's one primitive,
 * with the severity on its border. The plain availability reasons stay muted text.
 *
 * @param {"warning" | "error"} severity
 * @param {string} className
 * @param {string} [text]
 */
function noticeEl(severity, className, text) {
  const node = el("div", `notice diff-notice diff-availability ${className}`.trim(), text);
  node.setAttribute("data-severity", severity);
  return node;
}

/**
 * @typedef {object} ComposedTextRun
 * @property {string[]} classes
 * @property {string} text
 */

/**
 * Intersect syntax and intraline boundaries while preserving the source exactly.
 * @param {string} text
 * @param {MetabrowserSyntaxTokenRun[] | null} tokenRuns
 * @param {import("./diff-intraline.js").IntralineRange[]} intralineRanges
 * @returns {ComposedTextRun[]}
 */
export function composeTextRuns(text, tokenRuns, intralineRanges) {
  const boundaries = new Set([0, text.length]);
  /** @type {{start: number, end: number, classes: string[]}[]} */
  const tokens = [];
  let tokenOffset = 0;
  for (const run of tokenRuns ?? [{ classes: [], text }]) {
    const end = tokenOffset + run.text.length;
    boundaries.add(tokenOffset);
    boundaries.add(end);
    tokens.push({ classes: run.classes, end, start: tokenOffset });
    tokenOffset = end;
  }
  const ranges = intralineRanges.filter(
    (range) => 0 <= range.start && range.start < range.end && range.end <= text.length,
  );
  for (const range of ranges) {
    boundaries.add(range.start);
    boundaries.add(range.end);
  }
  const offsets = [...boundaries].sort((left, right) => left - right);
  /** @type {ComposedTextRun[]} */
  const result = [];
  let tokenIndex = 0;
  let rangeIndex = 0;
  for (let index = 0; index + 1 < offsets.length; index += 1) {
    const start = offsets[index];
    const end = offsets[index + 1];
    if (start === end) {
      continue;
    }
    while (tokenIndex + 1 < tokens.length && tokens[tokenIndex].end <= start) {
      tokenIndex += 1;
    }
    while (rangeIndex + 1 < ranges.length && ranges[rangeIndex].end <= start) {
      rangeIndex += 1;
    }
    const classes = [...(tokens[tokenIndex]?.classes ?? [])];
    const range = ranges[rangeIndex];
    if (range !== undefined && range.start <= start && end <= range.end) {
      classes.push("diff-intraline-change");
    }
    result.push({ classes, text: text.slice(start, end) });
  }
  return result;
}

/**
 * Put composed scanner and intraline runs into an existing text host.
 * @param {HTMLElement} host
 * @param {string} text
 * @param {MetabrowserSyntaxTokenRun[] | null} tokenRuns
 * @param {import("./diff-intraline.js").IntralineRange[]} intralineRanges
 */
function renderComposedText(host, text, tokenRuns, intralineRanges) {
  const spans = composeTextRuns(text, tokenRuns, intralineRanges).map((run) => {
    const span = el("span", run.classes.join(" "));
    span.textContent = run.text;
    return span;
  });
  host.replaceChildren(...spans);
}

/** @typedef {ReturnType<typeof buildFileRenderModel>["hunks"][number]["lines"][number]} DiffLine */
/** @typedef {import("./diff-render-model.js").DiffSplitRow} SplitRow */

/**
 * @param {DiffLine} line
 * @param {"old" | "new"} side
 */
function sideTokens(line, side) {
  return side === "old" ? line.oldTokens : line.newTokens;
}

/**
 * @param {DiffLine} line
 * @param {"old" | "new"} side
 */
function sideIntralineRanges(line, side) {
  return side === "old" ? line.oldIntralineRanges : line.newIntralineRanges;
}

/**
 * @param {FileViewState} state
 * @param {DiffLine} line
 * @param {"old" | "new"} side
 */
function renderTextHost(state, line, side) {
  // `hljs` marks this as already owned by the token pipeline. The
  // first paint remains complete plain text, and the shell's global
  // `pre code:not(.hljs)` enhancer cannot select this span.
  const host = el("span", "diff-line-text hljs", line.text);
  const runs = sideTokens(line, side);
  const intralineRanges = sideIntralineRanges(line, side);
  if (runs !== null || intralineRanges.length > 0) {
    renderComposedText(host, line.text, runs, intralineRanges);
  }
  state.textHosts.push({ host, line, side });
  return host;
}

/**
 * A hunk's separator as Git writes it, its old and new ranges between `@@` marks and the
 * heading after them, or in Current the new side's range alone. Git takes the heading
 * from the old file, so it can be a line the change removed, which Current does not show.
 *
 * @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk
 * @param {boolean} current
 */
function hunkHeaderText(hunk, current) {
  if (current) {
    return `@@ +${hunk.newStart},${hunk.newCount} @@`;
  }
  const heading = hunk.heading ? ` ${hunk.heading}` : "";
  return `@@ -${hunk.oldStart},${hunk.oldCount} +${hunk.newStart},${hunk.newCount} @@${heading}`;
}

/**
 * The top of hunk *hunkIndex*: where unchanged lines lie between it and the hunk above, or
 * the file's start, and the diff can read them, the fold bar that opens to them with the
 * hunk's separator beside its label (`renderGapFold`); otherwise the separator alone. A
 * last hunk is followed by the bar for the lines after it, where the file may go on.
 *
 * @param {HTMLElement} section
 * @param {FileViewState} state
 * @param {number} hunkIndex
 * @param {boolean} current
 * @param {(line: DiffLine) => HTMLElement} renderGapRow How this projection draws a gap's line.
 */
function appendHunkTop(section, state, hunkIndex, current, renderGapRow) {
  const hunk = state.renderModel.hunks[hunkIndex];
  const text = hunkHeaderText(hunk, current);
  const gaps = gapsOf(state);
  const gap = gaps?.[hunkIndex] ?? null;
  if (gap === null) {
    section.append(el("div", "diff-hunk-header", text));
  } else {
    const fold = renderGapFold(state, gap, "up", text, renderGapRow, null);
    section.append(fold.control, fold.group);
  }
}

/**
 * The bar for the lines after the last hunk, at the end of its section, where the file may
 * go on past it (`hunkGaps`).
 *
 * @param {HTMLElement} section
 * @param {FileViewState} state
 * @param {number} hunkIndex
 * @param {(line: DiffLine) => HTMLElement} renderGapRow
 */
function appendHunkEnd(section, state, hunkIndex, renderGapRow) {
  const gaps = gapsOf(state);
  const gap = gaps !== null && hunkIndex === gaps.length - 2 ? gaps[gaps.length - 1] : null;
  if (gap !== null) {
    const fold = renderGapFold(state, gap, "down", "", renderGapRow, null);
    section.append(fold.control, fold.group);
  }
}

/** @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk */
export function projectUnifiedHunk(hunk) {
  return hunk.lines.slice();
}

/** @param {DiffLine[]} lines @returns {SplitRow[]} */
function positionalChangedRunRows(lines) {
  const oldLines = lines.filter((line) => line.op === "del");
  const newLines = lines.filter((line) => line.op === "add");
  const changedRun = lines[0]?.changedRun ?? null;
  return Array.from({ length: Math.max(oldLines.length, newLines.length) }, (_, index) => ({
    changedRun,
    new: newLines[index] ?? null,
    old: oldLines[index] ?? null,
    refined: false,
  }));
}

/**
 * Duplicate context and positionally pair each contiguous changed run.
 * @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk
 * @returns {SplitRow[]}
 */
export function projectSplitHunk(hunk) {
  /** @type {SplitRow[]} */
  const rows = [];
  for (let index = 0; index < hunk.lines.length; ) {
    const line = hunk.lines[index];
    if (line.op === "context") {
      rows.push({ changedRun: null, new: line, old: line, refined: false });
      index += 1;
      continue;
    }
    const run = line.changedRun;
    let end = index + 1;
    while (end < hunk.lines.length && hunk.lines[end].changedRun === run) {
      end += 1;
    }
    rows.push(
      ...(run === null
        ? []
        : (hunk.changedRunRows.get(run) ?? positionalChangedRunRows(hunk.lines.slice(index, end)))),
    );
    index = end;
  }
  return rows;
}

/**
 * @param {FileViewState} state
 * @param {DiffLine} line
 */
function renderUnifiedLine(state, line) {
  const refined = line.intralineRefined ? " diff-line-refined" : "";
  const row = el("div", `diff-line diff-line-${line.op}${refined}`);
  row.append(
    el("span", "diff-line-number", line.oldNumber === null ? "" : String(line.oldNumber)),
    el("span", "diff-line-number", line.newNumber === null ? "" : String(line.newNumber)),
    el("span", "diff-line-marker", line.op === "add" ? "+" : line.op === "del" ? "-" : " "),
    renderTextHost(state, line, line.op === "del" ? "old" : "new"),
  );
  if (line.noNewline) {
    row.append(el("span", "diff-line-no-newline", "⏎ absent"));
    row.dataset.tipText = "No newline at end of file";
  }
  return row;
}

/**
 * @param {FileViewState} state
 * @param {DiffLine | null} line
 * @param {"old" | "new"} side
 */
function renderSplitSide(state, line, side) {
  if (line === null) {
    const empty = el("div", `diff-split-side diff-split-${side} diff-split-empty`);
    empty.setAttribute("aria-hidden", "true");
    return empty;
  }
  const op = line.op === "context" ? "context" : side === "old" ? "del" : "add";
  const number = side === "old" ? line.oldNumber : line.newNumber;
  const refined = line.intralineRefined ? " diff-line-refined" : "";
  const cell = el("div", `diff-split-side diff-split-${side} diff-line-${op}${refined}`);
  cell.append(
    el("span", "diff-line-number", number === null ? "" : String(number)),
    el("span", "diff-line-marker", op === "del" ? "-" : op === "add" ? "+" : " "),
    renderTextHost(state, line, side),
  );
  if (line.noNewline) {
    cell.append(el("span", "diff-line-no-newline", "⏎ absent"));
    cell.dataset.tipText = "No newline at end of file";
  }
  return cell;
}

/** @param {FileViewState} state @param {SplitRow} row */
function renderSplitLine(state, row) {
  const className =
    row.changedRun === null
      ? "diff-split-context"
      : `diff-split-change${row.refined ? " diff-line-refined" : ""}`;
  const element = el("div", `diff-split-row ${className}`);
  element.append(renderSplitSide(state, row.old, "old"), renderSplitSide(state, row.new, "new"));
  return element;
}

/**
 * Append context rows and foldable changed runs. Split calls this with
 * paired rows, so thresholds and labels count paired rows.
 * @template T
 * @param {HTMLElement} section
 * @param {T[]} rows
 * @param {(row: T) => number | null} changedRunOf
 * @param {(row: T) => HTMLElement} renderRow
 * @param {FileViewState} state
 * @param {number} hunkIndex
 */
function appendFoldedRows(section, rows, changedRunOf, renderRow, state, hunkIndex) {
  for (let index = 0; index < rows.length; ) {
    const changedRun = changedRunOf(rows[index]);
    if (changedRun === null) {
      section.append(renderRow(rows[index]));
      index += 1;
      continue;
    }
    let end = index + 1;
    while (end < rows.length && changedRunOf(rows[end]) === changedRun) {
      end += 1;
    }
    const run = rows.slice(index, end);
    if (FOLD_THRESHOLD <= 0 || run.length <= FOLD_THRESHOLD) {
      section.append(...run.map(renderRow));
      index = end;
      continue;
    }
    section.append(...run.slice(0, FOLD_VISIBLE).map(renderRow));
    const key = `${String(state.change.id)}:${hunkIndex}:${changedRun}`;
    if (state.unfold && !state.foldsOpened.has(key)) {
      // Drawn open, its rows materialized in batches as a reader's opening does; once,
      // so a fold the reader closed stays closed when a layout change draws it again.
      state.foldsOpened.add(key);
      state.expandedFolds.add(key);
    }
    foldSequence += 1;
    const fold = renderFoldControl(
      `diff-fold-group-${foldSequence}`,
      run.slice(FOLD_VISIBLE),
      renderRow,
      state,
      key,
    );
    section.append(fold.control, fold.group);
    index = end;
  }
}

/**
 * @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk
 * @param {FileViewState} state
 * @param {number} hunkIndex
 */
function renderUnifiedHunk(hunk, state, hunkIndex) {
  const section = el("div", "diff-hunk diff-hunk-unified");
  /** @param {DiffLine} line */
  const renderLine = (line) => renderUnifiedLine(state, line);
  appendHunkTop(section, state, hunkIndex, false, renderLine);
  const rows = projectUnifiedHunk(hunk);
  appendFoldedRows(section, rows, (line) => line.changedRun, renderLine, state, hunkIndex);
  appendHunkEnd(section, state, hunkIndex, renderLine);
  return section;
}

/**
 * @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk
 * @param {FileViewState} state
 * @param {number} hunkIndex
 */
function renderSplitHunk(hunk, state, hunkIndex) {
  const section = el("div", "diff-hunk diff-hunk-split");
  /** @param {DiffLine} line An unchanged line, the same on both sides. */
  const renderGapRow = (line) =>
    renderSplitLine(state, { changedRun: null, new: line, old: line, refined: false });
  appendHunkTop(section, state, hunkIndex, false, renderGapRow);
  const rows = projectSplitHunk(hunk);
  appendFoldedRows(
    section,
    rows,
    (row) => row.changedRun,
    (row) => renderSplitLine(state, row),
    state,
    hunkIndex,
  );
  appendHunkEnd(section, state, hunkIndex, renderGapRow);
  return section;
}

/**
 * The rows a hunk draws in Current: its lines of the new file, context and added, in order.
 * Pure.
 *
 * @param {ReturnType<typeof buildFileRenderModel>["hunks"][number]} hunk
 */
export function projectCurrentHunk(hunk) {
  return hunk.lines.filter((line) => line.op !== "del");
}

/**
 * A line of the new file: its new number alone, and its marker, so an added line says so
 * by more than its color.
 *
 * @param {FileViewState} state
 * @param {DiffLine} line
 */
function renderCurrentLine(state, line) {
  const refined = line.intralineRefined ? " diff-line-refined" : "";
  const row = el("div", `diff-line diff-line-${line.op}${refined}`);
  row.append(
    el("span", "diff-line-number", line.newNumber === null ? "" : String(line.newNumber)),
    el("span", "diff-line-marker", line.op === "add" ? "+" : " "),
    renderTextHost(state, line, "new"),
  );
  if (line.noNewline) {
    row.append(el("span", "diff-line-no-newline", "⏎ absent"));
    row.dataset.tipText = "No newline at end of file";
  }
  return row;
}

/**
 * A hunk in Current: its header names the new side's range alone, and a changed run folds
 * by the rows Current draws of it, under the key Diff's fold of that run has. The header
 * has no heading: Git takes the function-context line it writes after `@@` from the old
 * file, so it can be a line the change removed, which Current does not show. Diff keeps it.
 *
 * @param {DiffLine[]} rows `projectCurrentHunk`'s.
 * @param {FileViewState} state
 * @param {number} hunkIndex
 */
function renderCurrentHunk(rows, state, hunkIndex) {
  const section = el("div", "diff-hunk diff-hunk-current");
  /** @param {DiffLine} line */
  const renderLine = (line) => renderCurrentLine(state, line);
  appendHunkTop(section, state, hunkIndex, true, renderLine);
  appendFoldedRows(section, rows, (line) => line.changedRun, renderLine, state, hunkIndex);
  appendHunkEnd(section, state, hunkIndex, renderLine);
  return section;
}

/**
 * What a file with no lines in its new version says in Current, or null for one that has
 * lines: a deleted file, and a file left empty, whose one hunk ends at the new side's line
 * 0. Pure.
 *
 * @param {Record<string, unknown>} change
 * @param {{newStart: number, newCount: number}[]} hunks
 * @returns {string | null}
 */
export function currentAbsence(change, hunks) {
  if (String(change.kind) === "deleted") {
    return "This file was deleted, so it has no current version.";
  }
  if (hunks.length > 0 && hunks.every((hunk) => hunk.newStart === 0 && hunk.newCount === 0)) {
    return "This file is empty now.";
  }
  return null;
}

/**
 * Draw a file's Current: each hunk's lines of the new file. A hunk that only removed lines,
 * with no context around it, has none and is left out.
 *
 * @param {FileViewState} state
 */
function renderCurrentBody(state) {
  const absence = currentAbsence(state.change, state.renderModel.hunks);
  if (absence !== null) {
    state.body.append(el("div", "diff-availability diff-current-absent", absence));
    return;
  }
  for (const [hunkIndex, hunk] of state.renderModel.hunks.entries()) {
    const rows = projectCurrentHunk(hunk);
    if (rows.length > 0) {
      state.body.append(renderCurrentHunk(rows, state, hunkIndex));
    }
    appendDeletionNotices(state.body, hunk);
  }
}

/** @param {HTMLElement} body @param {FileViewState["renderModel"]["hunks"][number]} hunk */
function appendDeletionNotices(body, hunk) {
  let nextLine = hunk.newStart + Number(hunk.newCount === 0);
  let removed = 0;
  let added = false;
  /** @param {number} at */
  const mark = (at) => {
    if (removed > 0 && !added) {
      body.append(
        el(
          "div",
          "diff-availability diff-excerpt-removed",
          `${removed} ${removed === 1 ? "line removed" : "lines removed"} before line ${at}. See Diff.`,
        ),
      );
    }
    removed = 0;
    added = false;
  };
  for (const line of hunk.lines) {
    if (line.op === "del") {
      removed += 1;
    } else if (line.op === "add") {
      added = true;
      nextLine += 1;
    } else {
      mark(nextLine);
      nextLine += 1;
    }
  }
  mark(nextLine);
}

/** @param {FileViewState} state */
function renderFullSource(state) {
  const rows = state.full.rows;
  if (rows === null) {
    return false;
  }
  if (rows.length === 0) {
    state.body.append(
      el("div", "diff-availability diff-current-absent", "This file is empty now."),
    );
    return true;
  }
  const section = el("div", "diff-hunk diff-hunk-current");
  for (const line of rows) {
    section.append(renderCurrentLine(state, line));
  }
  state.body.append(section);
  return true;
}

/** @param {FileViewState} state @param {ReturnType<typeof gapAnswer>} answer */
function fullSourceRows(state, answer) {
  /** @type {Map<number, DiffLine>} */
  const changed = new Map();
  for (const hunk of state.renderModel.hunks) {
    for (const line of hunk.lines) {
      if (line.newNumber !== null) {
        changed.set(line.newNumber, line);
      }
    }
  }
  return answer.lines.map((text, index) => {
    const number = index + 1;
    const line = changed.get(number);
    return line?.text === text
      ? line
      : gapLine(number, 0, text, number === answer.line_count && !answer.ends_with_newline);
  });
}

/** @param {FileViewState} state */
function queueFullSource(state) {
  const source = state.fullSource;
  if (source === null || state.full.stop !== null || state.full.message !== "") {
    return;
  }
  let stopped = false;
  /** @type {IntersectionObserver | null} */
  let observer = null;
  const stop = () => {
    stopped = true;
    observer?.disconnect();
    source.signal.removeEventListener("abort", stop);
    state.full.stop = null;
  };
  state.full.stop = stop;
  source.signal.addEventListener("abort", stop, { once: true });
  const read = async () => {
    observer?.disconnect();
    const progress = progressBox("Full source is loading");
    state.body.append(progress);
    try {
      const payload = await source.load();
      const answer = gapAnswer(payload, fullSourceAsk(), source.comparisonId, source.path);
      if (stopped) {
        return;
      }
      if (answer.lines.length === answer.line_count) {
        state.full.rows = fullSourceRows(state, answer);
      } else {
        state.full.message = "This file is too large to show in full here. Showing an excerpt.";
      }
    } catch (error) {
      if (!stopped) {
        const payload = /** @type {{payload?: {code?: string}}} */ (error)?.payload;
        state.full.message =
          payload?.code === "blob_too_large"
            ? "This file is too large to show in full here. Showing an excerpt."
            : "The full source is unavailable here. Showing an excerpt.";
      }
    } finally {
      if (!stopped) {
        stop();
        source.keep(state, () => renderFileBody(state, "current"));
        if (state.full.rows !== null) {
          void highlightGapLines(
            state,
            state.full.rows.filter((line) => line.op === "context"),
          );
        }
      }
    }
  };
  if (typeof IntersectionObserver === "function") {
    observer = new IntersectionObserver((entries) => {
      if (!stopped && entries.some((entry) => entry.isIntersecting)) {
        void read();
      }
    });
    observer.observe(state.body);
  } else {
    void read();
  }
}

/**
 * Build the cached semantic state shared by every projection.
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown>} patch
 * @param {DiffViewApi} api
 * @param {HTMLElement} body
 * @param {boolean} [unfold]
 * @param {GapSource | null} [gaps] Where the lines between its hunks come from, if anywhere.
 * @returns {FileViewState}
 */
export function createFileState(change, patch, api, body, unfold = false, gaps = null) {
  const hunks = /** @type {Record<string, unknown>[]} */ (patch.hunks);
  return {
    api,
    body,
    change,
    drawn: null,
    expandedFolds: new Set(),
    foldTasks: new Map(),
    gapLines: {
      asked: new Map(),
      byNumber: new Map(),
      reach: new Map(),
      lineCount: null,
      refused: false,
      syntaxBytes: 0,
    },
    gaps,
    fullSource: null,
    full: { rows: null, message: "", stop: null },
    unfold,
    foldsOpened: new Set(),
    patch,
    renderModel: measureProjection(
      api,
      "diffMount:model",
      () => buildFileRenderModel(change, patch, api.langForPath),
      {
        hunk_count: hunks.length,
        line_count: hunks.reduce(
          (total, hunk) => total + (Array.isArray(hunk.lines) ? hunk.lines.length : 0),
          0,
        ),
      },
    ),
    textHosts: [],
  };
}

/**
 * Render one active projection from cached source and token facts.
 * @param {FileViewState} state
 * @param {Projection} layout
 */
export function renderFileBody(state, layout) {
  cancelFoldMaterializations(state);
  const full = layout === "current" && state.fullSource?.wanted() === true;
  if (!full) {
    state.full.stop?.();
    state.full.message = "";
  }
  return measureProjection(
    state.api,
    "diffMount:fileProjection",
    () => {
      state.body.replaceChildren();
      state.textHosts = [];
      state.drawn = layout;
      if (state.gapLines.refused) {
        // Its gaps are plain separators now; one line says why the bar the reader pressed
        // went (docs/design-system-messages.md, "Degrade Gracefully").
        state.body.append(noticeEl("warning", "diff-gap-refused", GAP_REFUSED_COPY));
      }
      if (state.renderModel.hunks.length === 0 && !full) {
        state.body.append(el("div", "diff-availability", "No content changes."));
        return;
      }
      if (layout === "current") {
        if (!full || !renderFullSource(state)) {
          if (full && state.full.message !== "") {
            const notice = noticeEl("warning", "diff-full-source-refused", state.full.message);
            state.fullSource?.open?.(notice);
            state.body.append(notice);
          }
          renderCurrentBody(state);
          if (full && currentAbsence(state.change, state.renderModel.hunks) === null) {
            queueFullSource(state);
          }
        }
      } else {
        for (const [hunkIndex, hunk] of state.renderModel.hunks.entries()) {
          state.body.append(
            layout === "split"
              ? renderSplitHunk(hunk, state, hunkIndex)
              : renderUnifiedHunk(hunk, state, hunkIndex),
          );
        }
      }
      if (state.patch.truncated) {
        state.body.append(
          noticeEl("warning", "diff-patch-truncated", "This patch is too long to show in full."),
        );
      }
    },
    {
      hunk_count: state.renderModel.hunks.length,
      layout,
      line_count: state.renderModel.hunks.reduce((total, hunk) => total + hunk.lines.length, 0),
    },
  );
}

/**
 * One file's hunks, drawn as Changes draws a file's body: each hunk under its header bar,
 * a long changed run behind its fold bar, and, after first paint, changed-run pairs and
 * syntax. For another plugin that shows part of a change in its own place: Guided Review's
 * excerpts (`mountFilePatch` in index.js). Unified only, since its host is a column.
 *
 * @param {HTMLElement} body The element the hunks are drawn into.
 * @param {Record<string, unknown>} change A changed file: its `old` and `new` paths.
 * @param {Record<string, unknown>} patch Its `hunks`, as the diff route answers them.
 * @param {DiffViewApi} api
 * @param {{path: string, load: (signal: AbortSignal) => Promise<unknown>} | null} [fullFile]
 * @returns {{dispose: () => void, show: (mode: Shown) => void}}
 */
export function mountFilePatch(body, change, patch, api, fullFile = null) {
  const controller = new AbortController();
  const state = createFileState(change, patch, api, body);
  /** @type {Projection} */
  let projection = "unified";
  /** @type {Shown} */
  let shown = "diff";
  if (fullFile !== null) {
    state.fullSource = {
      path: fullFile.path,
      wanted: () => shown === "full",
      load: () => fullFile.load(controller.signal),
      keep: (_state, change) => change(),
      signal: controller.signal,
    };
  }
  renderFileBody(state, projection);
  const isCurrent = () => !controller.signal.aborted;
  void (async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    if (!isCurrent()) {
      return;
    }
    await enhanceFileIntraline(state, api, controller.signal, isCurrent, () => projection);
    if (isCurrent()) {
      await enhanceFileSyntax(state, api, controller.signal, isCurrent);
    }
  })();
  return {
    show(mode) {
      const next = mode === "diff" ? "unified" : "current";
      if (shown !== mode && isCurrent()) {
        shown = mode;
        projection = next;
        renderFileBody(state, projection);
      }
    },
    dispose() {
      controller.abort();
      cancelFoldMaterializations(state);
    },
  };
}

/**
 * Record synchronous projection work when the host profiler is present.
 * @template T
 * @param {DiffViewApi | undefined} api
 * @param {string} label
 * @param {() => T} work
 * @param {Record<string, unknown>} metadata
 * @returns {T}
 */
function measureProjection(api, label, work, metadata) {
  return api?.perf?.measure ? api.perf.measure(label, work, metadata) : work();
}

/**
 * Record progressive diff work when the host profiler is present without
 * making progressive enhancement depend on diagnostics.
 * @template T
 * @param {DiffViewApi} api
 * @param {string} label
 * @param {() => Promise<T>} work
 * @param {Record<string, unknown>} metadata
 * @returns {Promise<T>}
 */
function measureEnhancement(api, label, work, metadata) {
  return api.perf ? api.perf.measureAsync(label, work, metadata) : work();
}

/**
 * Refresh current text hosts without changing unified row order or fold DOM.
 * @param {FileViewState} state
 */
function refreshTextHosts(state) {
  for (const { host, line, side } of state.textHosts) {
    const runs = sideTokens(line, side);
    const ranges = sideIntralineRanges(line, side);
    renderComposedText(host, line.text, runs, ranges);
    const row = host.closest(".diff-line");
    row?.classList.toggle("diff-line-refined", line.intralineRefined);
  }
}

/**
 * Attach browser-local changed ranges before syntax for the same file.
 * @param {FileViewState} state
 * @param {DiffViewApi} api
 * @param {AbortSignal} signal
 * @param {() => boolean} isCurrent
 * @param {() => Projection | null} currentLayout `null` until a layout is drawn.
 */
async function enhanceFileIntraline(state, api, signal, isCurrent, currentLayout) {
  try {
    const enhanced = await measureEnhancement(
      api,
      "diffIntraline:file",
      async () =>
        refineFileChangedRuns(state.renderModel, { maxWork: INTRALINE_WORK_BUDGET }, signal),
      { hunk_count: state.renderModel.hunks.length },
    );
    if (!enhanced || !isCurrent()) {
      return;
    }
    if (currentLayout() === "split") {
      renderFileBody(state, "split");
    } else {
      refreshTextHosts(state);
    }
  } catch (error) {
    if (signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      return;
    }
    console.warn("metabrowser diff: intraline enhancement failed", error);
  }
}

/**
 * Enhance only the text hosts from the current projection. Token data
 * stays on the semantic records for later projections.
 * @param {FileViewState} state
 * @param {DiffViewApi} api
 * @param {AbortSignal} signal
 * @param {() => boolean} isCurrent
 */
async function enhanceFileSyntax(state, api, signal, isCurrent) {
  try {
    state.renderModel.inputBytes ??= syntaxInputBytes(state.renderModel.hunks);
    const metadata = {
      hunk_count: state.renderModel.hunks.length,
      input_bytes: state.renderModel.inputBytes,
      lexer_calls: 0,
    };
    const measuredApi = {
      ...api,
      highlightSyntax: /** @type {DiffViewApi["highlightSyntax"]} */ (
        (source, language, options) => {
          metadata.lexer_calls += 1;
          return measureEnhancement(
            api,
            "diffSyntax:lexer",
            () => api.highlightSyntax(source, language, { signal: options?.signal }),
            {
              input_bytes: options?.inputBytes ?? 0,
              language,
            },
          );
        }
      ),
    };
    const enhanced = await measureEnhancement(
      api,
      "diffSyntax:file",
      () => highlightFileSyntax(state.renderModel, measuredApi, signal),
      metadata,
    );
    if (!enhanced || !isCurrent()) {
      return;
    }
    for (const { host, line, side } of state.textHosts) {
      const runs = sideTokens(line, side);
      if (runs !== null) {
        renderComposedText(host, line.text, runs, sideIntralineRanges(line, side));
      }
    }
  } catch (error) {
    if (signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      return;
    }
    console.warn("metabrowser diff: syntax enhancement failed", error);
  }
}

/** @param {MountedDiffState} view @param {number} generation */
function mountIsCurrent(view, generation) {
  return !view.disposed && view.generation === generation;
}

/**
 * Yield one task between file-sized lexer units. Disposal resolves the
 * waiter as inactive instead of leaving the queue pending.
 * @param {MountedDiffState} view
 * @param {number} generation
 */
function yieldForEnhancement(view, generation) {
  return new Promise((resolve) => {
    if (!mountIsCurrent(view, generation)) {
      resolve(false);
      return;
    }
    const waiter = { resolve, timer: 0 };
    waiter.timer = setTimeout(() => {
      view.yielders.delete(waiter);
      resolve(mountIsCurrent(view, generation));
    }, 0);
    view.yielders.add(waiter);
  });
}

/**
 * Serialize file-sized enrichment in document order, with intraline first.
 * @param {MountedDiffState} view
 * @param {FileViewState} state
 */
function scheduleFileEnhancement(view, state) {
  const api = view.api ?? plainSyntaxApi();
  const generation = view.generation;
  view.enhancementTail = view.enhancementTail.then(async () => {
    if (!(await yieldForEnhancement(view, generation))) {
      return;
    }
    await enhanceFileIntraline(
      state,
      api,
      view.controller.signal,
      () => mountIsCurrent(view, generation),
      () => (view.awaitingWidth ? null : projectionOf(view)),
    );
    await enhanceFileSyntax(state, api, view.controller.signal, () =>
      mountIsCurrent(view, generation),
    );
  });
}

/**
 * A changed run's fold (`foldExpander` in diff-fold.js), stating the count it holds so the
 * reader knows what is hidden. Its rows are drawn when it opens, in batches.
 *
 * @template T
 * @param {string} id The group's id.
 * @param {T[]} hiddenRows
 * @param {(row: T) => HTMLElement} renderRow
 * @param {FileViewState} state
 * @param {string} key
 * @returns {import("./diff-fold.js").FoldExpander}
 */
function renderFoldControl(id, hiddenRows, renderRow, state, key) {
  const hidden = hiddenRows.length;
  const fold = foldExpander({
    id,
    expanded: state.expandedFolds.has(key),
    label: (expanded) =>
      expanded
        ? `Hide ${hidden} line${hidden === 1 ? "" : "s"}`
        : `${hidden} more changed line${hidden === 1 ? "" : "s"}`,
    onToggle(expanded) {
      if (expanded) {
        state.expandedFolds.add(key);
        scheduleMaterialization();
      } else {
        state.expandedFolds.delete(key);
        cancelMaterialization();
      }
    },
  });
  const { group } = fold;

  function cancelMaterialization() {
    const task = state.foldTasks.get(key);
    if (task) {
      clearTimeout(task.timer);
      state.foldTasks.delete(key);
    }
    state.textHosts = state.textHosts.filter(({ host }) => !group.contains(host));
    group.replaceChildren();
  }

  function scheduleMaterialization() {
    cancelMaterialization();
    let index = 0;
    const task = { timer: 0 };
    const appendBatch = () => {
      if (state.foldTasks.get(key) !== task || !state.expandedFolds.has(key)) {
        return;
      }
      const end = Math.min(index + FOLD_MATERIALIZATION_BATCH_ROWS, hiddenRows.length);
      group.append(...hiddenRows.slice(index, end).map(renderRow));
      index = end;
      if (index >= hiddenRows.length) {
        state.foldTasks.delete(key);
        return;
      }
      task.timer = setTimeout(appendBatch, 0);
    };
    task.timer = setTimeout(appendBatch, 0);
    state.foldTasks.set(key, task);
  }

  if (fold.expanded()) {
    scheduleMaterialization();
  }
  return fold;
}

/** @param {FileViewState} state */
function cancelFoldMaterializations(state) {
  for (const task of state.foldTasks.values()) {
    clearTimeout(task.timer);
  }
  state.foldTasks.clear();
}

// ── Gaps: the unchanged lines between hunks ──────────────────────────────────────────────

// What a file whose lines the comparison declines to give says, above its hunks: a gap's
// bar is then its plain separator (`refuseGaps`).
const GAP_REFUSED_COPY = "The unchanged lines of this file cannot be shown.";

/**
 * Where a hunk's hidden lines lie, by the new side's numbers: from *start* to one before
 * *end*, or to the file's end where *end* is null, which no answer has said yet. *offset* is
 * what a new number adds for the old one, the change's net lines above the gap, so a gap's
 * old and new numbers advance together.
 *
 * @typedef {{start: number, end: number | null, offset: number}} HunkGap
 */

/**
 * The unchanged lines each hunk leaves out above it, and the last one below it. Pure.
 *
 * Entry *i* is the gap above hunk *i*, null where it touches the hunk above or the file's
 * first line; the entry after the last hunk's is the gap below it, from the line after it to
 * the file's end. A patch says where each hunk starts and not where the file ends, so that
 * gap is open where *lineCount* is not known and the last hunk ends in a full *context* of
 * unchanged lines, as Git writes up to that many after a change, and its last line ends
 * with a newline: a shorter run, or none, ends the file there. A gap whose old and new
 * spans disagree, which no patch Git writes has, is left out. A count of 0 starts a side
 * after its line, as a hunk of `-3,0 +4,2` adds two lines after old line 3.
 *
 * @param {{oldStart: number, oldCount: number, newStart: number, newCount: number, lines: {op: string, noNewline: boolean}[]}[]} hunks
 * @param {number} context
 * @param {number | null} [lineCount] The new side's lines in all, where an answer said.
 * @returns {(HunkGap | null)[]}
 */
export function hunkGaps(hunks, context, lineCount = null) {
  if (hunks.length === 0) {
    return [];
  }
  /** @type {(HunkGap | null)[]} */
  const gaps = [];
  let oldNext = 1;
  let newNext = 1;
  for (const hunk of hunks) {
    const oldFirst = hunk.oldCount > 0 ? hunk.oldStart : hunk.oldStart + 1;
    const newFirst = hunk.newCount > 0 ? hunk.newStart : hunk.newStart + 1;
    const span = newFirst - newNext;
    gaps.push(
      span > 0 && oldFirst - oldNext === span
        ? { start: newNext, end: newFirst, offset: oldNext - newNext }
        : null,
    );
    oldNext = oldFirst + hunk.oldCount;
    newNext = newFirst + hunk.newCount;
  }
  const last = hunks[hunks.length - 1];
  let trailing = 0;
  for (let index = last.lines.length - 1; index >= 0; index -= 1) {
    if (last.lines[index].op !== "context") {
      break;
    }
    trailing += 1;
  }
  const endsFile = last.lines.at(-1)?.noNewline === true;
  const open =
    lineCount === null ? context > 0 && trailing >= context && !endsFile : lineCount >= newNext;
  gaps.push(
    open
      ? {
          start: newNext,
          end: lineCount === null ? null : lineCount + 1,
          offset: oldNext - newNext,
        }
      : null,
  );
  return gaps;
}

/**
 * A file's gaps as it draws them now, or null where its diff draws plain separators: no
 * source of lines, a refusal, a change with no new file to read them from, or, below the
 * last hunk, a patch cut short, whose last hunk is not the file's.
 *
 * @param {FileViewState} state
 * @returns {(HunkGap | null)[] | null}
 */
function gapsOf(state) {
  const side = /** @type {{entry_type?: unknown} | undefined} */ (state.change.new);
  if (
    state.gaps === null ||
    state.gapLines.refused ||
    state.change.binary === true ||
    side?.entry_type !== "file"
  ) {
    return null;
  }
  const gaps = hunkGaps(state.renderModel.hunks, state.gaps.context, state.gapLines.lineCount);
  if (state.patch.truncated && gaps.length > 0) {
    gaps[gaps.length - 1] = null;
  }
  return gaps;
}

/**
 * One unchanged line read for a gap, as the patch's own context lines are: both numbers,
 * the same text on both sides, and no changes inside it.
 *
 * @param {number} number Its new number.
 * @param {number} offset
 * @param {string} text
 * @param {boolean} noNewline The file's last line, with no newline after it.
 * @returns {DiffLine}
 */
function gapLine(number, offset, text, noNewline) {
  return {
    changedRun: null,
    intralineRefined: false,
    newIntralineRanges: [],
    newNumber: number,
    newTokens: null,
    noNewline,
    oldIntralineRanges: [],
    oldNumber: number + offset,
    oldTokens: null,
    op: "context",
    text,
  };
}

/**
 * The route's `view=lines` answer to *ask*, or a throw for anything else: a run of at most
 * its count, from its start, or ending before its end or at the side's last line. An answer
 * for another comparison than the one drawn, as a ref that moved since it was drawn gives,
 * would put another commit's lines between these hunks as unchanged; it is refused, as a
 * declined file is, since asking again gets the same (`refusesGapLines`).
 *
 * @param {unknown} payload
 * @param {GapAsk} ask
 * @param {string | undefined} comparisonId
 * @param {string} [path]
 * @returns {{start: number, lines: string[], line_count: number, ends_with_newline: boolean}}
 */
function gapAnswer(payload, ask, comparisonId, path) {
  const answer = /** @type {Record<string, unknown> | null} */ (
    payload !== null && typeof payload === "object" ? payload : null
  );
  if (
    answer === null ||
    !Number.isInteger(answer.start) ||
    !Array.isArray(answer.lines) ||
    answer.lines.length > ask.count ||
    !answer.lines.every((line) => typeof line === "string") ||
    !Number.isInteger(answer.line_count) ||
    typeof answer.ends_with_newline !== "boolean"
  ) {
    throw new Error("The comparison answered with something other than these lines.");
  }
  // Before the run's range: another comparison's file may end before the lines asked for, and
  // its answer is still a refusal, not a failure a Retry gets past.
  if (
    (comparisonId !== undefined && answer.comparison_id !== comparisonId) ||
    (path !== undefined && answer.path !== path)
  ) {
    throw Object.assign(new Error("The comparison answered for another comparison."), {
      refused: true,
    });
  }
  const start = Number(answer.start);
  const end = start + answer.lines.length;
  if (
    "start" in ask
      ? start !== ask.start
      : start < Math.max(1, ask.end - ask.count) ||
        end !== Math.min(ask.end, Number(answer.line_count) + 1)
  ) {
    throw new Error("The comparison answered with something other than these lines.");
  }
  return /** @type {{start: number, lines: string[], line_count: number, ends_with_newline: boolean}} */ (
    /** @type {unknown} */ (answer)
  );
}

/**
 * Whether a file holds every line from *from* to before *to* that its new side has, and,
 * where *needsEnd*, knows where that side ends.
 *
 * @param {GapLines} lines
 * @param {number} from
 * @param {number} to
 * @param {boolean} needsEnd
 */
function holdsGapLines(lines, from, to, needsEnd) {
  if (needsEnd && lines.lineCount === null) {
    return false;
  }
  const end = lines.lineCount === null ? to : Math.min(to, lines.lineCount + 1);
  for (let number = from; number < end; number += 1) {
    if (!lines.byNumber.has(number)) {
      return false;
    }
  }
  return true;
}

/**
 * Read a gap's lines from *from* to before *to*, or to the side's end, into the file's
 * keep, in one ask: from *from* for a gap opened downward (*toward* "down"), and up to *to*
 * for one opened upward, so an answer its byte bound cuts short holds the lines nearest the
 * hunk. Where it stops short of the range, before the side's end, the open's reach records
 * where, and the open draws what came with its nested bar for the rest (`renderGapFold`):
 * one press is one ask, of at most `MAX_LINES_ANSWER_BYTES` of text (diff/side_lines.py).
 * One ask a range, however many folds wait for it. The lines are highlighted after they are
 * drawn.
 *
 * @param {FileViewState} state
 * @param {HunkGap} gap
 * @param {number} from
 * @param {number} to
 * @param {"up" | "down"} toward
 * @returns {Promise<void>}
 */
function readGapLines(state, gap, from, to, toward) {
  const lines = state.gapLines;
  const key = `${toward}:${from}-${to}`;
  let asked = lines.asked.get(key);
  if (asked !== undefined) {
    return asked;
  }
  const source = /** @type {GapSource} */ (state.gaps);
  const side = /** @type {{path?: unknown}} */ (state.change.new);
  const path = String(side.path ?? "");
  /** @type {GapAsk} */
  const ask = toward === "up" ? { end: to, count: to - from } : { start: from, count: to - from };
  asked = (async () => {
    const answer = gapAnswer(await source.load(path, ask), ask, source.comparisonId);
    lines.lineCount = answer.line_count;
    /** @type {DiffLine[]} */
    const fresh = [];
    for (const [index, text] of answer.lines.entries()) {
      const number = answer.start + index;
      if (!lines.byNumber.has(number)) {
        const record = gapLine(
          number,
          gap.offset,
          text,
          number === answer.line_count && !answer.ends_with_newline,
        );
        lines.byNumber.set(number, record);
        fresh.push(record);
      }
    }
    if (
      toward === "up"
        ? answer.start > from
        : answer.start + answer.lines.length < Math.min(to, answer.line_count + 1)
    ) {
      lines.reach.set(
        toward === "up" ? `up:${to}` : `down:${from}`,
        toward === "up" ? answer.start : answer.start + answer.lines.length,
      );
    }
    // After the folds waiting for these lines draw them plain, as a hunk's first paint is.
    setTimeout(() => void highlightGapLines(state, fresh), 0);
  })().finally(() => lines.asked.delete(key));
  lines.asked.set(key, asked);
  return asked;
}

/**
 * Highlight lines read for a gap as one source, as each hunk side is (`highlightFileSyntax`),
 * within the same whole-file bound: the hunks' bytes and every gap's highlighted so far
 * count against `SYNTAX_HIGHLIGHT_MAX_BYTES`. Past it they stay plain, as a file past it
 * does. The rows drawn of them take their tokens.
 *
 * @param {FileViewState} state
 * @param {DiffLine[]} records
 */
async function highlightGapLines(state, records) {
  const language = state.renderModel.newLanguage;
  const source = state.gaps;
  if (records.length === 0 || !language || source === null || source.signal.aborted) {
    return;
  }
  const text = records.map((record) => record.text).join("\n");
  const bytes = new TextEncoder().encode(text).byteLength;
  state.renderModel.inputBytes ??= syntaxInputBytes(state.renderModel.hunks);
  const total = state.renderModel.inputBytes + state.gapLines.syntaxBytes + bytes;
  if (state.api.isLargeTextPreview({ size: total })) {
    return;
  }
  state.gapLines.syntaxBytes += bytes;
  try {
    const tokens = await measureEnhancement(
      state.api,
      "diffSyntax:gap",
      () => state.api.highlightSyntax(text, language, { inputBytes: bytes, signal: source.signal }),
      { input_bytes: bytes, language, line_count: records.length },
    );
    if (
      tokens === null ||
      source.signal.aborted ||
      tokens.length !== records.length ||
      tokens.some((runs, index) => runs.map((run) => run.text).join("") !== records[index].text)
    ) {
      return;
    }
    for (const [index, record] of records.entries()) {
      record.newTokens = tokens[index];
      record.oldTokens = tokens[index];
    }
    const highlighted = new Set(records);
    for (const { host, line, side } of state.textHosts) {
      if (highlighted.has(line)) {
        renderComposedText(
          host,
          line.text,
          sideTokens(line, side),
          sideIntralineRanges(line, side),
        );
      }
    }
  } catch (error) {
    if (!source.signal.aborted) {
      console.warn("metabrowser diff: a gap's syntax enhancement failed", error);
    }
  }
}

/**
 * Whether a failed ask is the comparison declining these lines, which asking again will not
 * change, rather than a failure a Retry may get past: a refusal of the request itself, or an
 * answer for another comparison (`gapAnswer`).
 *
 * @param {unknown} error
 */
function refusesGapLines(error) {
  const failed = /** @type {{status?: unknown, refused?: unknown} | null} */ (error);
  const status = failed?.status;
  return (
    failed?.refused === true ||
    (typeof status === "number" && status >= 400 && status < 500 && ![408, 429].includes(status))
  );
}

/**
 * The comparison declines this file's lines (a binary or converted file, a side past the
 * read bound): draw it again with each gap as its plain separator, and one line saying so,
 * where the reader is.
 *
 * @param {FileViewState} state
 */
function refuseGaps(state) {
  if (state.gapLines.refused) {
    return;
  }
  state.gapLines.refused = true;
  const source = /** @type {GapSource} */ (state.gaps);
  const drawn = state.drawn;
  if (drawn !== null && !source.signal.aborted) {
    source.keep(state, () => renderFileBody(state, drawn));
  }
}

/**
 * A gap's fold (`foldExpander` in diff-fold.js), the bar every fold of the diff draws.
 *
 * Closed, it says how many unchanged lines it holds, or, below the last hunk, before an
 * answer has said where the file ends, that it holds the rest of the file. Opening it draws
 * up to `GAP_LINES` of them, asking the comparison first, once, for any the file does not
 * hold yet; a gap longer than that, or one whose answer its byte bound cut short, opens the
 * lines nearest its hunk (*toward*: "up" above a hunk, "down" below the last), and a fold of
 * the same kind stands for the rest, at the far end of the group, as one step more. Open, it
 * says how many lines it shows, its open steps' among them. A gap whose lines do not load
 * closes again saying so, and a press asks again. Every change of its height while the
 * reader waits, its rows, the box that stood for them, and closing after a failure, is made
 * where the reader keeps their place (`GapSource.keep`).
 *
 * @param {FileViewState} state
 * @param {HunkGap} gap
 * @param {"up" | "down"} toward
 * @param {string} detail The hunk's separator, beside the label, for a gap above a hunk.
 * @param {(line: DiffLine) => HTMLElement} renderRow
 * @param {{relabel: () => void} | null} parent The fold this one is a step of.
 * @returns {import("./diff-fold.js").FoldExpander & {shown: () => number, cancel: () => void}}
 */
function renderGapFold(state, gap, toward, detail, renderRow, parent) {
  const key = `gap:${gap.start}-${toward === "down" ? "end" : gap.end}`;
  const count = countFormatter(state.api);
  const status = { failed: false };
  /** @type {ReturnType<typeof renderGapFold> | null} */
  let step = null;
  let own = 0;
  const shown = () => own + (step?.expanded() ? step.shown() : 0);
  const end = () =>
    gap.end ?? (state.gapLines.lineCount === null ? null : state.gapLines.lineCount + 1);

  /** @param {boolean} expanded */
  function label(expanded) {
    const known = end();
    if (expanded) {
      const lines = shown() || (known === null ? 0 : Math.min(known - gap.start, GAP_LINES));
      return lines > 0 ? `Hide ${count(lines)} line${lines === 1 ? "" : "s"}` : "Hide these lines";
    }
    if (known === null) {
      return status.failed ? "Could not load the rest of the file. Retry" : "Rest of the file";
    }
    const held = known - gap.start;
    const lines = `${count(held)} unchanged line${held === 1 ? "" : "s"}`;
    return status.failed ? `Could not load ${lines}. Retry` : lines;
  }

  foldSequence += 1;
  const fold = foldExpander({
    id: `diff-gap-group-${foldSequence}`,
    expanded: state.expandedFolds.has(key),
    label,
    detail,
    groupClass: "diff-gap-group",
    onToggle(expanded) {
      if (expanded) {
        state.expandedFolds.add(key);
        status.failed = false;
        open(true);
      } else {
        state.expandedFolds.delete(key);
        // Its steps close with it, so it opens again to its first lines.
        step?.set(false);
        cancel();
      }
      parent?.relabel();
    },
  });
  fold.control.classList.add("diff-gap-control");
  const { group } = fold;
  const view = { ...fold, shown, cancel, relabel };

  function relabel() {
    fold.relabel();
    parent?.relabel();
  }

  /**
   * The lines this fold draws itself, by the new side's numbers, from what is known: up to
   * `GAP_LINES` nearest its hunk, or as far as an answer cut short reached (`GapLines.reach`).
   */
  function range() {
    const known = end();
    if (toward === "up" && known !== null) {
      const reach = state.gapLines.reach.get(`up:${known}`) ?? gap.start;
      return { from: Math.max(gap.start, known - GAP_LINES, reach), to: known };
    }
    const reach = state.gapLines.reach.get(`down:${gap.start}`) ?? Number.POSITIVE_INFINITY;
    const to = Math.min(gap.start + GAP_LINES, reach);
    return { from: gap.start, to: known === null ? to : Math.min(known, to) };
  }

  function cancel() {
    const task = state.foldTasks.get(key);
    if (task) {
      clearTimeout(task.timer);
      state.foldTasks.delete(key);
    }
    step?.cancel();
    step = null;
    own = 0;
    state.textHosts = state.textHosts.filter(({ host }) => !group.contains(host));
    group.replaceChildren();
  }

  /**
   * @param {boolean} keep Whether the reader opened it, so its rows keep their place:
   *   one drawn open with its file draws inside the redraw that holds it.
   */
  function open(keep) {
    const { from, to } = range();
    if (holdsGapLines(state.gapLines, from, to, toward === "down")) {
      fill(keep);
      return;
    }
    fold.control.setAttribute("aria-busy", "true");
    // Its accessible name, never shown: what it reads, by count where the file's end is known.
    const what = end() === null ? "the rest of the file" : `${count(to - from)} unchanged lines`;
    const box = progressBox(`Loading ${what}`);
    group.append(box);
    const source = /** @type {GapSource} */ (state.gaps);
    readGapLines(state, gap, from, to, toward).then(
      () => {
        fold.control.removeAttribute("aria-busy");
        if (fold.expanded() && fold.control.isConnected && !source.signal.aborted) {
          // Its rows take the box's place inside the change that holds the reader's.
          fill(true);
        } else {
          box.remove();
        }
      },
      (error) => {
        fold.control.removeAttribute("aria-busy");
        if (source.signal.aborted || isAbortError(error)) {
          box.remove();
          return;
        }
        if (refusesGapLines(error)) {
          console.warn("metabrowser diff: the comparison declines this file's lines", error);
          // The file is drawn again, the box with it, where the reader is.
          refuseGaps(state);
          box.remove();
          return;
        }
        console.warn("metabrowser diff: a gap's lines did not load", error);
        // Closed again, its bar says why, unless the reader closed it meanwhile.
        if (fold.expanded() && fold.control.isConnected) {
          source.keep(state, () => {
            status.failed = true;
            fold.set(false);
          });
        } else {
          box.remove();
        }
      },
    );
  }

  /** @param {boolean} keep Draw its rows where the reader keeps their place (`GapSource.keep`). */
  function fill(keep) {
    const source = /** @type {GapSource} */ (state.gaps);
    const { from, to } = range();
    const known = end();
    const stop = known === null ? to : Math.min(to, known);
    /** @type {DiffLine[]} */
    const records = [];
    for (let number = from; number < stop; number += 1) {
      const record = state.gapLines.byNumber.get(number);
      if (record !== undefined) {
        records.push(record);
      }
    }
    if (records.length === 0 && toward === "down") {
      // The file ended at the last hunk after all: there was nothing below it. A reader who
      // pressed the bar from the keyboard goes on from the file's own bar, not the page's top.
      const leave = () => {
        if (fold.control.contains(document.activeElement)) {
          /** @type {HTMLElement | null | undefined} */ (
            state.body.closest(".diff-file")?.querySelector(".diff-file-toggle")
          )?.focus();
        }
        fold.control.remove();
        group.remove();
      };
      if (keep) {
        source.keep(state, leave);
      } else {
        leave();
      }
      return;
    }
    const rest =
      toward === "up"
        ? from > gap.start
          ? { start: gap.start, end: from, offset: gap.offset }
          : null
        : known !== null && stop < known
          ? { start: stop, end: known, offset: gap.offset }
          : null;
    const draw = () => {
      // What it drew before, a loading box among it, goes in the same change.
      cancel();
      own = records.length;
      if (rest !== null) {
        step = renderGapFold(state, rest, toward, "", renderRow, view);
        group.append(step.control, step.group);
      }
      materializeGapRows(state, key, group, records, renderRow, toward === "down" ? step : null);
    };
    if (keep) {
      source.keep(state, draw);
    } else {
      draw();
    }
    relabel();
  }

  if (fold.expanded()) {
    open(false);
  }
  return view;
}

/**
 * Draw a gap's rows into its group in batches of `FOLD_MATERIALIZATION_BATCH_ROWS`, the
 * first at once and the rest a task each, as an open changed run's are; before the bar of
 * the next step where it comes after them. Closing, a redraw, and disposal cancel the rest.
 *
 * @param {FileViewState} state
 * @param {string} key
 * @param {HTMLElement} group
 * @param {DiffLine[]} records
 * @param {(line: DiffLine) => HTMLElement} renderRow
 * @param {{control: HTMLElement} | null} before
 */
function materializeGapRows(state, key, group, records, renderRow, before) {
  let index = 0;
  const task = { timer: 0 };
  const appendBatch = () => {
    if (state.foldTasks.get(key) !== task) {
      return;
    }
    const end = Math.min(index + FOLD_MATERIALIZATION_BATCH_ROWS, records.length);
    const rows = records.slice(index, end).map(renderRow);
    if (before === null) {
      group.append(...rows);
    } else {
      before.control.before(...rows);
    }
    index = end;
    if (index >= records.length) {
      state.foldTasks.delete(key);
      return;
    }
    task.timer = setTimeout(appendBatch, 0);
  };
  state.foldTasks.set(key, task);
  appendBatch();
}

/**
 * One View file control of a file bar: a link when the page already has the file's
 * address, and a button when following it first switches the served pin. The link has
 * no handler, so a click, a new tab, and a copied address are the browser's own. The
 * text is the application's; the path reaches only the tooltip and accessible name, as
 * text.
 *
 * @param {import("./diff-view-file.js").ViewFileAction} action
 * @param {MountedDiffState} view
 * @param {{element: HTMLElement, timer: number}} notice Where a refusal is said, under
 *   the bar.
 * @returns {HTMLElement}
 */
function renderViewFileControl(action, view, notice) {
  const opener = /** @type {NonNullable<MountedDiffState["viewFile"]>} */ (view.viewFile);
  const link = action.mode === "link";
  const control = el(link ? "a" : "button", "diff-file-view");
  control.textContent = action.label;
  control.setAttribute("data-tip-text", action.detail);
  control.setAttribute("aria-label", `${action.label}: ${action.detail}`);
  if (link) {
    control.setAttribute("href", action.href);
    return control;
  }
  control.setAttribute("type", "button");
  control.addEventListener("click", () => {
    if (opener.switching()) {
      // Another control's switch is on its way: this click changes nothing, and that
      // control stays the busy one.
      return;
    }
    clearTimeout(notice.timer);
    view.timers.delete(notice.timer);
    notice.element.textContent = "";
    notice.element.hidden = true;
    control.setAttribute("aria-busy", "true");
    view.viewFileBusy = control;
    void opener.switchTo(action).then((outcome) => {
      if (outcome.kind === "navigated") {
        // The page is leaving; the control stays busy until it does, or until the
        // browser brings the page back (the opener's `released`).
        return;
      }
      control.setAttribute("aria-busy", "false");
      view.viewFileBusy = null;
      if (outcome.kind !== "refused") {
        return;
      }
      // A live region announces a change it was shown before: unhide it first, and
      // set its text in the next task.
      notice.element.hidden = false;
      notice.timer = setTimeout(() => {
        view.timers.delete(notice.timer);
        notice.element.textContent = outcome.message;
      }, 0);
      view.timers.add(notice.timer);
    });
  });
  return control;
}

/**
 * @param {MountedDiffState} view @param {Record<string, unknown>} change
 * @param {HTMLElement} notice
 */
function appendFullFileAction(view, change, notice) {
  const action = view.viewFile?.fullFileAction?.(change, view.resolved);
  if (!action) {
    return;
  }
  const reply = el("span", "diff-availability");
  reply.setAttribute("role", "status");
  reply.hidden = true;
  notice.append(renderViewFileControl(action, view, { element: reply, timer: 0 }), reply);
}

/**
 * Paint each bar's controls again from what the opener says now, in place: after the page
 * learns that the server serves another pin, a link at the commit the page shows is a
 * switch. A control whose switch is on its way stays as it is.
 *
 * @param {MountedDiffState} view
 */
function repaintViewFileControls(view) {
  if (view.viewFile === null || view.disposed) {
    return;
  }
  for (const bar of view.viewFileBars) {
    const actions = view.viewFile.actions(bar.change, view.resolved);
    bar.controls = bar.controls.map((control, index) => {
      const action = actions[index];
      if (action === undefined || control === view.viewFileBusy) {
        return control;
      }
      const next = renderViewFileControl(action, view, bar.said);
      control.replaceWith(next);
      return next;
    });
  }
}

/**
 * The per-file bar, per the section-disclosure and icon button primitives in the design
 * system. It leads with the group that names the file: one disclosure trigger (kind,
 * path), the copy control right after the name, and the change's stats and notes, which
 * describe the trigger. The View file controls follow that group, each a part of the bar
 * of its own, so a bar that wraps moves them to the next line before the name gives way.
 * Its end group holds a rendered file's view chooser alone (diff-markdown.js), at the
 * bar's far end. The toolbar sets presentation for the comparison (`renderShowControl`).
 *
 * @param {Record<string, unknown>} change
 * @param {Pick<DiffFileDisclosure, "bar" | "toggle">} disclosure The file's bar and its
 *   trigger, which this fills (`fileDisclosure`).
 * @param {string} factsId The id of the stats and notes, which describe the trigger.
 * @param {MountedDiffState} view
 * @returns {{end: HTMLElement, notice: HTMLElement | null}}
 */
function renderFileBar(change, disclosure, factsId, view) {
  const api = view.api;
  // The path is shown as the Diff summary shows it, by the server's display rule, and the
  // raw path stays for the copy control and the jump; without the shared tree it is raw.
  const model = view.changedFiles;
  const { letter, label, notes } = fileChangeLabel(change, model?.displayPath);
  const { bar, toggle } = disclosure;
  const status = el("span", "diff-file-kind file-change-status", letter);
  status.dataset.fileStatus = String(change.kind);
  toggle.append(status);
  const pathSpan = el("span", "diff-file-path", label);
  pathSpan.dataset.tipText = label;
  toggle.append(pathSpan);
  /** @param {unknown} value */
  const count = (value) => (typeof value === "number" ? value : null);
  const additions = count(change.additions);
  const deletions = count(change.deletions);
  // Its lines as every lines summary says them, through the shell's one component (mb-ox6a).
  const paint = additions === null && deletions === null ? null : shellPainters(api);
  const counts = paint === null ? null : paint.changeLine({ statuses: [], additions, deletions });
  // The change's stats and notes follow the copy control, which sits right after the name
  // it copies, so they are not in the trigger: they describe it, and a click on them
  // toggles the file as anywhere else on the bar does.
  /** @type {HTMLElement | null} */
  let facts = null;
  if (counts !== null || notes.length > 0) {
    facts = el("span", "diff-file-facts");
    facts.setAttribute("id", factsId);
    toggle.setAttribute("aria-describedby", factsId);
    if (counts !== null && paint !== null) {
      const stats = el("span", "diff-file-stats");
      stats.append(...paint.changeLineNodes(counts));
      facts.append(stats);
    }
    for (const note of notes) {
      facts.append(el("span", "diff-file-note", note));
    }
  }
  // Each group is one flex item: a bar that wraps or cuts a long path short never parts
  // the copy control or the stats from the name, and its end group moves as one.
  const lead = el("div", "diff-file-lead");
  const end = el("div", "diff-file-end");
  lead.append(toggle);
  const side = /** @type {Record<string, unknown> | undefined} */ (change.new ?? change.old);
  if (side !== undefined) {
    const copy = el("button", "icon-btn icon-btn-reveal diff-file-copy");
    copy.setAttribute("type", "button");
    copy.setAttribute("data-mb-copy", "text");
    copy.setAttribute("data-mb-copy-text", String(side.path));
    copy.setAttribute("data-mb-copy-label", "Copy path");
    api?.ownDelegate?.(copy);
    copy.setAttribute("data-tip-text", "Copy path");
    copy.setAttribute("aria-label", "Copy path");
    copy.innerHTML = shellIcon("copy");
    lead.append(copy);
  }
  if (facts !== null) {
    lead.append(facts);
  }

  /** @type {HTMLElement | null} */
  let notice = null;
  /** @type {HTMLElement[]} */
  let controls = [];
  const actions = view.viewFile?.actions(change, view.resolved) ?? [];
  if (actions.length > 0) {
    notice = el("div", "diff-availability diff-file-notice");
    notice.setAttribute("role", "status");
    notice.hidden = true;
    const said = { element: notice, timer: 0 };
    controls = actions.map((action) => renderViewFileControl(action, view, said));
    view.viewFileBars.push({ change, controls, said });
  }
  // The View file controls sit between the name's group and the end group, in neither:
  // where the bar wraps, they take the next line, and the name keeps the first.
  bar.append(lead, ...controls, end);
  return { end, notice };
}

/**
 * A file card's disclosure, the one every card that shows a file's changes has
 * (docs/design-system.md, "Diff File Bar"): Changes' files (`renderFileSection`), and the
 * cards a guided review step draws around its references, which take this from the guide's
 * drawer (`guidePatchDrawer` in index.js). It makes the card's bar and the button that leads
 * it, with the shell's disclosure chevron, and binds them to *section* and *folded*: the
 * whole bar is one activation surface, like a tree row, and the button stays the semantic
 * trigger for focus and the keyboard, whose synthesized click bubbles to the bar. Only a
 * control on the bar that acts for itself opts out: the copy control, a file's view chooser,
 * and a link or control that views the file (`.diff-file-view`). A card starts open.
 * Collapsing keeps *folded* in the document, at no height, so nothing it drew is disposed,
 * and the bar stays where it was.
 *
 * The caller appends what names the file to *toggle*, places *toggle* and its other
 * controls in *bar*, and puts *bar* and *folded* in *section*. *folded* takes an id of the
 * card's own, which anything else of the card can be named from.
 *
 * @param {HTMLElement} section The card.
 * @param {HTMLElement} folded What the bar shows or hides.
 * @param {(expanded: boolean) => void} [changed] Hears each change, after it is drawn.
 * @returns {DiffFileDisclosure} The one shape of it, in `static/types.d.ts`.
 */
export function fileDisclosure(section, folded, changed) {
  sectionSequence += 1;
  const toggleId = `diff-file-toggle-${sectionSequence}`;
  const bodyId = `diff-file-body-${sectionSequence}`;
  section.setAttribute("aria-labelledby", toggleId);
  folded.setAttribute("id", bodyId);
  const bar = el("div", "diff-file-bar disclosure-toggle");
  const toggle = /** @type {HTMLButtonElement} */ (el("button", "diff-file-toggle expanded"));
  toggle.setAttribute("type", "button");
  toggle.setAttribute("id", toggleId);
  toggle.setAttribute("aria-controls", bodyId);
  toggle.setAttribute("aria-expanded", "true");
  // The same disclosure glyph the nav tree leads with, rotated by the
  // same expanded/collapsed rules.
  const chevron = el("span", "diff-file-chevron");
  chevron.innerHTML = shellIcon("toggle");
  toggle.append(chevron);
  let expanded = true;
  /** @param {boolean} next */
  const setExpanded = (next) => {
    expanded = next;
    toggle.setAttribute("aria-expanded", String(expanded));
    toggle.classList.toggle("expanded", expanded);
    toggle.classList.toggle("collapsed", !expanded);
    folded.classList.toggle("diff-file-body-collapsed", !expanded);
    section.classList.toggle("diff-file-collapsed", !expanded);
    changed?.(expanded);
  };
  bar.addEventListener("click", (event) => {
    const origin = /** @type {{closest?: (selector: string) => unknown}} */ (event.target);
    if (
      typeof origin?.closest === "function" &&
      (origin.closest("[data-mb-copy]") ||
        origin.closest(".diff-file-view") ||
        origin.closest(".diff-markdown-control"))
    ) {
      return;
    }
    setExpanded(!expanded);
  });
  return { bar, toggle, expanded: () => expanded, setExpanded };
}

/** @param {DiffViewApi | undefined} api @returns {"unified" | "split"} */
export function readLayoutPreference(api) {
  const value = api?.prefs?.get("diff.layout", /** @type {unknown} */ ("split"));
  return value === "unified" ? "unified" : "split";
}

/**
 * Let a drag select one split code column without interleaving the
 * opposite side's row-major DOM text. Full-width rows clear the gate.
 * @param {HTMLElement} root
 */
export function installSplitSelectionGate(root) {
  const owner = root.ownerDocument || document;
  function clear() {
    delete root.dataset.selectionSide;
  }
  /** @param {Event} event */
  function onPointerDown(event) {
    const target = /** @type {{closest?: (selector: string) => unknown} | null} */ (event.target);
    const text = typeof target?.closest === "function" ? target.closest(".diff-line-text") : null;
    const side =
      text && typeof (/** @type {{closest?: unknown}} */ (text).closest) === "function"
        ? /** @type {HTMLElement | null} */ (
            /** @type {{closest: (selector: string) => unknown}} */ (text).closest(
              ".diff-split-side",
            )
          )
        : null;
    if (!side || !root.contains(side)) {
      clear();
      return;
    }
    root.dataset.selectionSide = side.classList.contains("diff-split-old") ? "old" : "new";
  }
  root.addEventListener("pointerdown", onPointerDown);
  owner.addEventListener("pointerup", clear);
  owner.addEventListener("pointercancel", clear);
  return () => {
    clear();
    root.removeEventListener("pointerdown", onPointerDown);
    owner.removeEventListener("pointerup", clear);
    owner.removeEventListener("pointercancel", clear);
  };
}

/**
 * Whether a diff *width* px wide is too narrow for Split, given what it was. Pure.
 *
 * @param {number} width
 * @param {number} fontSize The diff's text, in px.
 * @param {boolean} narrow
 */
export function tooNarrowForSplit(width, fontSize, narrow) {
  if (!(width > 0) || !(fontSize > 0)) {
    // Not laid out, as in a hidden tab: nothing is known, so nothing changes.
    return narrow;
  }
  const needs = SPLIT_MIN_WIDTH_EM * fontSize + FILE_BORDER_PX;
  return width < (narrow ? needs + SPLIT_RETURN_MARGIN_PX : needs);
}

/**
 * The first decision, with no earlier one to hold it. A width within the return margin of
 * the limit counts as narrow, because a pane has no scrollbar until what is drawn brings
 * one: measured 2026-11-02 in Chrome 152, Files changed with its root resting at 617 px
 * measured 628 at mount, and drew Split to throw it away. An unknown width is not narrow,
 * which is what a browserless caller gets. Pure.
 *
 * @param {number} width
 * @param {number} fontSize The diff's text, in px.
 */
export function opensTooNarrowForSplit(width, fontSize) {
  return width > 0 && fontSize > 0 && tooNarrowForSplit(width, fontSize, true);
}

/**
 * What a diff draws: the reader's choice, except Split where it does not fit, unless the
 * reader chose it there. Pure.
 *
 * @param {"unified" | "split"} chosen
 * @param {boolean} narrow
 * @param {boolean} insisted
 * @returns {"unified" | "split"}
 */
export function drawnLayout(chosen, narrow, insisted) {
  return chosen === "split" && narrow && !insisted ? "unified" : chosen;
}

/** @param {HTMLElement} element */
function fontSizeOf(element) {
  return typeof getComputedStyle === "function"
    ? Number.parseFloat(getComputedStyle(element).fontSize)
    : 0;
}

/** @param {MountedDiffState} view */
function renderLayoutControl(view) {
  const control = view.layoutControl;
  const filterControls = view.api?.filterControls;
  if (!control || !filterControls) {
    return;
  }
  // The control shows what the diff draws. While Split does not fit that is Unified, and
  // the reader's choice waits in `chosenLayout`, so Split says why it is not selected.
  // While the diff shows Current, one column whatever the layout, it keeps its place and
  // shows the layout Diff draws, and both chips say why neither can be chosen. They are
  // `aria-disabled`, not `disabled`, so the pointer and the keyboard reach what they say.
  // Focus in it stays on the chosen chip, as in Diff | Current: the markup is new, and a
  // Diff | Current choice, `N` among them, draws it again with focus where it was.
  const current = view.show !== "diff";
  const fellBack = view.chosenLayout === "split" && view.layout === "unified";
  const splitTip = current ? LAYOUT_IN_CURRENT_TIP : fellBack ? SPLIT_TOO_NARROW_TIP : null;
  const active = /** @type {Element | null | undefined} */ (globalThis.document?.activeElement);
  const restore = active != null && control.contains?.(active) === true;
  control.innerHTML = filterControls.groupHtml({
    key: "diff-layout",
    label: "Diff layout",
    layout: "joined",
    options: [
      { label: "Split", value: "split", ...(splitTip ? { tip: splitTip } : {}) },
      { label: "Unified", value: "unified", ...(current ? { tip: LAYOUT_IN_CURRENT_TIP } : {}) },
    ],
    select: "one",
    value: view.layout,
  });
  if (current) {
    for (const chip of control.querySelectorAll("[data-chip-value]")) {
      chip.setAttribute("aria-disabled", "true");
      chip.setAttribute(
        "aria-label",
        `${chip.getAttribute("data-chip-value") === "split" ? "Split" : "Unified"}, unavailable. ${LAYOUT_IN_CURRENT_TIP}`,
      );
    }
  }
  if (restore) {
    /** @type {HTMLElement | null} */ (
      control.querySelector(`[data-chip-value="${view.layout}"]`)
    )?.focus();
  }
  // The markup is new, so `L`'s badge moves to the new chip it would select.
  const option = view.layoutKey ? layoutKeyOption(view) : null;
  if (option) {
    view.layoutKey?.retarget(option);
  }
}

/**
 * The layout chip `L` would select, the one not checked: what its badge sits on.
 *
 * @param {MountedDiffState} view
 * @returns {HTMLElement | null}
 */
function layoutKeyOption(view) {
  const other = view.layout === "split" ? "unified" : "split";
  return /** @type {HTMLElement | null} */ (
    view.layoutControl?.querySelector(`[data-chip-value="${other}"]`) ?? null
  );
}

/**
 * `L`: switch to the other layout, exactly as clicking its chip does. It goes through
 * `setLayout`, so where Split does not fit, `L` chooses Split and its sideways scroll.
 *
 * @param {MountedDiffState} view
 */
export function toggleLayout(view) {
  setLayout(view, view.layout === "split" ? "unified" : "split");
}

/**
 * The reader's choice: draw it, and optionally persist it. Choosing Split where it does not
 * fit gets Split, with its sideways scroll, until the diff has room and loses it again.
 * Choosing what is already drawn changes nothing, so Unified chosen while Split does not
 * fit leaves Split the choice for when it does.
 *
 * @param {MountedDiffState} view
 * @param {string} value
 */
export function setLayout(view, value) {
  if (view.disposed || view.show !== "diff") {
    return;
  }
  const layout = value === "split" ? "split" : "unified";
  if (layout === view.layout) {
    return;
  }
  view.chosenLayout = layout;
  view.insistedOnSplit = layout === "split" && view.narrow;
  view.presentation.layout = layout;
  drawLayout(view, layout);
}

// ── Diff | Excerpt | Full ────────────────────────────────────────

/**
 * The presentation chooser used by a comparison and by a block of guide references.
 * @param {NonNullable<DiffViewApi["filterControls"]>} controls
 * @param {Shown | null} value
 * @param {boolean} full
 */
export function presentationControlHtml(controls, value, full) {
  return controls.groupHtml({
    key: "diff-show",
    label: "Comparison view",
    layout: "joined",
    options: [
      {
        label: "Diff",
        value: "diff",
        tip: "Show additions and removals with surrounding context.",
      },
      { label: "Excerpt", value: "current", tip: "Show the new version around the changes." },
      ...(full
        ? [
            {
              label: "Full",
              value: "full",
              tip: "Show the entire new version at the revision under review.",
            },
          ]
        : []),
    ],
    select: "one",
    value: value ?? "",
  });
}

/**
 * Draw the toolbar's Diff | Current chooser from the diff's choice. Focus in it stays on the
 * chosen chip: the markup is new. `N`'s badge moves to the new chip it would select.
 *
 * @param {MountedDiffState} view
 */
function renderShowControl(view) {
  const control = view.showControl;
  const filterControls = view.api?.filterControls;
  if (!control || !filterControls) {
    return;
  }
  const active = /** @type {Element | null | undefined} */ (globalThis.document?.activeElement);
  const restore = active != null && control.contains?.(active) === true;
  control.innerHTML = presentationControlHtml(filterControls, view.show, view.canShowFull);
  if (restore) {
    /** @type {HTMLElement | null} */ (
      control.querySelector(`[data-chip-value="${view.show}"]`)
    )?.focus();
  }
  const option = view.showKey ? showKeyOption(view) : null;
  if (option) {
    view.showKey?.retarget(option);
  }
}

/**
 * What the diff shows when it opens: the reader's last choice on this surface, stored as
 * *preference*, or the surface's own default (*fallback*) for a reader who never chose there
 * or a stored value that is not a choice. A pull request's Docs tab opens on Current and
 * remembers its choice apart; every other surface opens on Diff and shares `diff.show`.
 *
 * @param {DiffViewApi | undefined} api
 * @param {string} [preference]
 * @param {Shown} [fallback]
 * @returns {Shown}
 */
export function readShowPreference(api, preference = "diff.show", fallback = "diff") {
  const value = api?.prefs?.get(preference, /** @type {unknown} */ (fallback));
  if (value === "full" || value === "diff") {
    return value;
  }
  if (value === "excerpt" || (value === "current" && fallback !== "full")) {
    return "current";
  }
  return fallback;
}

/**
 * The reader's choice of what the diff shows: store it, so this surface's diffs open in it,
 * and draw it. The row at the pane's top keeps its place on the screen, or the nearest row
 * the choice still draws (`placeOfTopRow`); a file a jump pinned keeps the pane's top.
 *
 * @param {MountedDiffState} view
 * @param {string} value
 * @param {boolean} [persist]
 */
export function setShow(view, value, persist = true) {
  if (view.disposed) {
    return;
  }
  const show =
    value === "full" && view.canShowFull ? "full" : value === "current" ? "current" : "diff";
  if (show === view.show) {
    if (!persist && show === "full") {
      view.markdown?.controller.show(show);
    }
    return;
  }
  const place = view.pinned === null ? placeOfTopRow(view, show) : null;
  view.show = show;
  if (persist) {
    view.api?.prefs?.set(view.showPreference, show === "current" ? "excerpt" : show);
  }
  drawShow(view, place);
}

/**
 * `N`: switch the diff between Diff and Current, exactly as clicking the other chip does.
 *
 * @param {MountedDiffState} view
 */
export function toggleShow(view) {
  setShow(view, view.show === "diff" ? "current" : "diff");
}

/**
 * The chip `N` would select, the one not checked: what its badge sits on.
 *
 * @param {MountedDiffState} view
 * @returns {HTMLElement | null}
 */
function showKeyOption(view) {
  const other = view.show === "diff" ? "current" : "diff";
  return /** @type {HTMLElement | null} */ (
    view.showControl?.querySelector(`[data-chip-value="${other}"]`) ?? null
  );
}

/**
 * Give the diff its `N`, once, on the toolbar's chooser, drawn before this runs. Each later
 * draw retargets it (`renderShowControl`), and dispose() detaches it.
 *
 * @param {MountedDiffState} view
 */
function attachShowKey(view) {
  const shortcuts = view.api?.shortcuts;
  const option = typeof shortcuts?.attach === "function" ? showKeyOption(view) : null;
  if (!shortcuts || !option) {
    return;
  }
  view.showKey = shortcuts.attach(option, {
    activate: () => toggleShow(view),
    copy: {
      action: "Toggle Diff or Excerpt",
      description: "Switch between the comparison and an excerpt of the new version.",
      hint: "Excerpt",
    },
    group: "controls",
    id: "diff.show",
    key: "n",
    order: 41,
  });
}

/**
 * What the diff's code rows are drawn as now: Current whatever the layout, or the layout.
 *
 * @param {MountedDiffState} view
 * @returns {Projection}
 */
function projectionOf(view) {
  return view.show === "diff" ? view.layout : "current";
}

/**
 * Draw what the diff shows now: the toolbar's choosers, the code rows of every file, and the
 * Rendered layer's files.
 *
 * @param {MountedDiffState} view
 * @param {Place | null} anchor
 */
function drawShow(view, anchor) {
  view.root.dataset.show = view.show;
  renderShowControl(view);
  renderLayoutControl(view);
  view.markdown?.controller.show(view.show);
  if (view.awaitingWidth) {
    // Nothing is drawn before the first width, which draws what is chosen then.
    holdPlace(view, anchor);
  } else {
    reproject(view, anchor);
  }
  view.notifyCurrentFile();
}

/**
 * The diff's width changed: draw what now fits. The reader's choice is not touched.
 *
 * The pane keeps its pixel `scrollTop` through the redraw, as it does through the control,
 * and Unified is taller than Split, so a long diff moves under the reader: measured in
 * Chrome 152 on 10 files, a reader 3,744 px into a file was 5,029 px into it after narrowing
 * and stayed there after widening. Accepted: keeping the line would need an anchor both
 * layouts share, across a projection that runs in batches above 100 files.
 *
 * @param {MountedDiffState} view
 * @param {number} width
 */
function fitLayout(view, width) {
  if (view.disposed) {
    return;
  }
  const narrow = tooNarrowForSplit(width, fontSizeOf(view.root), view.narrow);
  if (narrow === view.narrow) {
    return;
  }
  view.narrow = narrow;
  view.insistedOnSplit = view.insistedOnSplit && narrow;
  const layout = drawnLayout(view.chosenLayout, narrow, view.insistedOnSplit);
  if (layout !== view.layout) {
    drawLayout(view, layout);
  }
}

/**
 * Draw the diff in *layout*. In Current the rows are one column whatever the layout, so
 * only the first width, before which nothing was drawn, draws them.
 *
 * @param {MountedDiffState} view
 * @param {"unified" | "split"} layout
 */
function drawLayout(view, layout) {
  const first = view.awaitingWidth;
  view.awaitingWidth = false;
  view.layout = layout;
  view.root.dataset.layout = layout;
  renderLayoutControl(view);
  view.notifyCurrentFile();
  if (first || view.show === "diff") {
    reproject(view);
  }
}

/**
 * Reproject cached file state as `projectionOf` says, in batches above 100 files. With an
 * *anchor*, that file keeps its place after each batch; without one, as for a layout, the
 * browser's scroll anchoring keeps it.
 *
 * @param {MountedDiffState} view
 * @param {Place | null} [anchor]
 */
function reproject(view, anchor) {
  const projection = projectionOf(view);
  for (const file of view.deferred.values()) {
    reserveFileBody(file, projection, view);
  }
  view.layoutGeneration += 1;
  const layoutGeneration = view.layoutGeneration;
  if (view.files.length <= LAYOUT_PROJECTION_BATCH_FILES) {
    delete view.root.dataset.layoutPending;
    for (const state of view.files) {
      renderFileBody(state, projection);
    }
    if (anchor !== undefined) {
      holdPlace(view, anchor);
      settlePlace(view, anchor);
    }
    return;
  }
  view.root.dataset.layoutPending = "true";
  projectLayoutBatch(view, projection, layoutGeneration, 0, anchor);
}

/**
 * Reproject one measured file batch and yield before the next. A generation
 * check makes a rapid second switch authoritative without cancelling shared
 * hydration or syntax work.
 * @param {MountedDiffState} view
 * @param {Projection} layout
 * @param {number} layoutGeneration
 * @param {number} start
 * @param {Place | null} [anchor] Held after each batch.
 */
function projectLayoutBatch(view, layout, layoutGeneration, start, anchor) {
  if (view.disposed || view.layoutGeneration !== layoutGeneration) {
    return;
  }
  const end = Math.min(start + LAYOUT_PROJECTION_BATCH_FILES, view.files.length);
  for (let index = start; index < end; index += 1) {
    renderFileBody(view.files[index], layout);
  }
  if (anchor !== undefined) {
    holdPlace(view, anchor);
  }
  if (end >= view.files.length) {
    delete view.root.dataset.layoutPending;
    if (anchor !== undefined) {
      settlePlace(view, anchor);
    }
    return;
  }
  const timer = setTimeout(() => {
    view.timers.delete(timer);
    projectLayoutBatch(view, layout, layoutGeneration, end, anchor);
  }, 0);
  view.timers.add(timer);
}

/**
 * The shell's number format, which every count a reader sees is written in, or the
 * browser's own outside the shell.
 *
 * @param {DiffViewApi | undefined} api
 * @returns {(count: number) => string}
 */
function countFormatter(api) {
  const format = api?.formatInteger;
  if (typeof format === "function") {
    return (count) => format(count);
  }
  const fallback = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
  return (count) => fallback.format(count);
}

/** Each Diff summary's tree has an id of its own, which its header controls. */
let summaryIds = 0;

/**
 * The dot after the Diff summary's file count, as a count summary's part: muted, and hidden
 * from a screen reader. A header that is its toggle is named in words, so its dot says
 * nothing; a header that is a line has no name, so its dot says a comma in its place.
 */
const SUMMARY_SEPARATOR = Object.freeze({ separator: "·" });
/** @see SUMMARY_SEPARATOR */
const LINE_SEPARATOR = Object.freeze({ separator: "·", spoken: ", " });

/**
 * The shell's painters a Diff summary is drawn with, the SDK's (formatters.js;
 * docs/design-system.md, "Count Summaries Bold Their Numbers" and "Brief Change Line"):
 * `countPartsNodes`, a count summary's one painter, for its file count, and `changeLine` and
 * `changeLineNodes`, the brief change line, the one component for "2 A, 3 D, 30 M · +1,234
 * −3,423", for the rest. The diff paints none of their classes itself.
 *
 * @param {DiffViewApi | undefined} api
 * @returns {{countPartsNodes: NonNullable<DiffViewApi["countPartsNodes"]>, changeLine: NonNullable<DiffViewApi["changeLine"]>, changeLineNodes: NonNullable<DiffViewApi["changeLineNodes"]>}}
 */
function shellPainters(api) {
  const countPartsNodes = api?.countPartsNodes;
  const changeLine = api?.changeLine;
  const changeLineNodes = api?.changeLineNodes;
  if (
    typeof countPartsNodes !== "function" ||
    typeof changeLine !== "function" ||
    typeof changeLineNodes !== "function"
  ) {
    throw new TypeError(
      "A Diff summary is painted by the SDK's countPartsNodes, changeLine, and changeLineNodes.",
    );
  }
  return { countPartsNodes, changeLine, changeLineNodes };
}

/**
 * The Diff summary's file count, "35 files changed", in `.diff-summary-files`, its text the
 * phrase as it reads, and the dot after it, as one item of the line
 * (`.diff-summary-group`), so a line that wraps breaks after the dot and no line starts with
 * one.
 *
 * @param {MetabrowserCountParts} parts
 * @param {(parts: MetabrowserCountParts) => Array<Node | string>} paint
 * @param {MetabrowserCountPart} separator
 * @returns {HTMLElement}
 */
function summaryFiles(parts, paint, separator) {
  const words = el("span", "diff-summary-files");
  words.append(...paint(parts));
  const item = el("span", "diff-summary-group");
  item.append(words, ...paint([separator]));
  return item;
}

/**
 * A summary's words without its file count, "2 A · +1 −1 (2 listed)" and "2 added; 1 line
 * added, 1 deleted; 2 listed", for a header whose page says the count on its size line
 * (docs/design-system.md, "Change Size Line"): the notes after the totals stay.
 *
 * @param {{filesParts: MetabrowserCountParts, text: string, label: string}} said
 * @returns {{text: string, label: string}}
 */
function withoutFileCount(said) {
  const files = said.filesParts
    .map((part) => (typeof part === "string" ? part : "number" in part ? part.number : ""))
    .join("");
  const text = said.text.startsWith(`${files} · `) ? said.text.slice(files.length + 3) : said.text;
  const label = said.label.startsWith(files)
    ? said.label.slice(files.length).replace(/^[:;] /, "")
    : said.label;
  return { text, label };
}

/**
 * The note of a list cut short at its bound, "(2,000 listed)": its figure a bold number,
 * muted with the note, as a count summary's numbers are (docs/design-system.md, "Count
 * Summaries Bold Their Numbers").
 *
 * @param {string} listed the number of files listed, formatted
 * @param {(parts: MetabrowserCountParts) => Array<Node | string>} paint
 * @returns {HTMLElement}
 */
function listedNote(listed, paint) {
  const note = el("span", "diff-summary-note");
  note.append(...paint(["(", { number: listed }, " listed)"]));
  return note;
}

/**
 * What a Diff summary reads of what it heads: a diff's view (`summaryOwnerOf`), or a page that
 * draws the summary on its own (`mountDiffSummary`). *jump* goes to a changed file, through
 * the host's address where it has one, or in the diff.
 *
 * @typedef {object} SummaryOwner
 * @property {DiffViewApi | undefined} api
 * @property {boolean} disposed
 * @property {MetabrowserChangedFilesTree | null} changedFiles
 * @property {(path: string) => void} jump
 * @property {boolean} countsFiles Whether the header says the file count. A page header
 *   says it on its size line above the summary (docs/design-system.md, "Change Size Line"),
 *   so a summary drawn there is its statuses and line totals alone.
 */

/**
 * The whole change set's totals, where its list stopped at its bound and the page knows more
 * than the list does, as a commit's page does from the commit's own stats.
 *
 * @typedef {{files: number, additions: number | null, deletions: number | null, exact: boolean}} WholeTotals
 */

/**
 * A diff's view as its Diff summary reads it.
 *
 * @param {MountedDiffState} view
 * @param {boolean} [countsFiles]
 * @returns {SummaryOwner}
 */
function summaryOwnerOf(view, countsFiles = true) {
  return {
    api: view.api,
    countsFiles,
    get disposed() {
      return view.disposed;
    },
    changedFiles: view.changedFiles,
    jump(path) {
      if (view.openFile !== null) {
        view.openFile(path);
      } else {
        jumpToFirstFile(view, path);
      }
    },
  };
}

/**
 * A multi-file diff's Diff summary: the header that says what the change set holds, "35
 * files changed · 2 A, 3 D, 30 M · +1,234 −3,423", and is the disclosure toggle of its files
 * as a tree by folder, its chevron after its words, as every toggle that expands a diff
 * summary has it (docs/design-system.md, "Diff Summary"; mb-f0pz). Each status is its
 * count and its rows' letter, both bold in the
 * status's ink, and the dots between the groups, the commas, and the notes after the totals
 * are muted. It starts collapsed, and the tree is not mounted, or its module imported, until
 * the header is first opened; hovering or focusing the header asks for the module first.
 * Its words are the shared model's (`describeChanges`), from the manifest's totals and the
 * kinds of the files it lists, or, for a list cut short, the whole change set's totals
 * (*whole*) and how many files it lists, and its accessible name says them in words, "35
 * files changed: 2 added, 3 deleted, 30 modified; …". A change set of no files has nothing
 * to open, so its header is a line. A header whose host cuts its breakdown short, as a
 * pull request's header does to keep one line, has its whole words as its tooltip while it
 * is cut.
 *
 * @param {Record<string, unknown>} totals
 * @param {Record<string, unknown>[]} files
 * @param {SummaryOwner} view
 * @param {MetabrowserChangedFilesTree} model
 * @param {WholeTotals | null} [whole]
 * @returns {{element: HTMLElement, dispose: () => void}}
 */
function renderDiffSummary(totals, files, view, model, whole = null) {
  const formatCount = countFormatter(view.api);
  const paint = shellPainters(view.api);
  const { rows, said, listed } = diffSummaryOf(totals, files, model, formatCount, whole);
  // "N files changed · ", then the brief change line, each an item of the header's line. A
  // header with files to open is its toggle, which says the line in words; a line says a
  // comma in each hidden dot's place.
  const named = rows.length > 0;
  /** @type {Array<Node | string>} */
  const parts = [
    ...(view.countsFiles
      ? [
          summaryFiles(
            said.filesParts,
            paint.countPartsNodes,
            named ? SUMMARY_SEPARATOR : LINE_SEPARATOR,
          ),
        ]
      : []),
    ...paint.changeLineNodes(said.line, named ? {} : { spoken: ", " }),
  ];
  if (said.estimated) {
    parts.push(el("span", "diff-summary-note", "(estimated)"));
  }
  if (listed !== null) {
    parts.push(listedNote(listed, paint.countPartsNodes));
  }
  if (rows.length === 0) {
    const line = el("div", "diff-summary");
    line.append(...parts);
    return { element: line, dispose: () => {} };
  }
  const toggle = el(
    "button",
    "diff-summary diff-summary-toggle summary-toggle disclosure-toggle collapsed",
  );
  toggle.setAttribute("type", "button");
  toggle.setAttribute("aria-expanded", "false");
  const words = view.countsFiles ? said : withoutFileCount(said);
  toggle.setAttribute("aria-label", words.label);
  const chevron = el("span", "diff-summary-chevron summary-toggle-chevron");
  chevron.setAttribute("aria-hidden", "true");
  const chevronSvg = shellIcon("toggle");
  chevron.innerHTML = chevronSvg;
  toggle.append(...parts, chevron);

  summaryIds += 1;
  const id = `diff-summary-tree-${summaryIds}`;
  /** @type {ReturnType<typeof import("./diff-summary.js").mountSummaryTree> | null} */
  let tree = null;
  /** @type {Promise<typeof import("./diff-summary.js")> | null} */
  let loading = null;
  let disposed = false;
  let failures = 0;
  const load = () => {
    // A module that did not load is asked for again at an address of its own: a browser keeps
    // a failed import in its module map, and the same address would fail again unasked.
    loading ??= /** @type {Promise<typeof import("./diff-summary.js")>} */ (
      failures === 0 ? import("./diff-summary.js") : import(`./diff-summary.js?retry=${failures}`)
    ).catch((error) => {
      failures += 1;
      loading = null;
      throw error;
    });
    return loading;
  };
  const listening = new AbortController();
  const { signal } = listening;
  toggle.addEventListener(
    "pointerenter",
    () => {
      void load().catch(() => {});
      // The whole of a breakdown cut short (docs/design-system.md, "Tooltips Add
      // Information"), and nothing while it is whole; a press that failed keeps its own.
      if (toggle.getAttribute("aria-disabled") === "true") {
        return;
      }
      const statuses = toggle.querySelector(".change-line-statuses");
      if (statuses !== null && statuses.scrollWidth > statuses.clientWidth) {
        toggle.dataset.tipText = words.text;
      } else {
        delete toggle.dataset.tipText;
      }
    },
    { signal },
  );
  toggle.addEventListener("focus", () => void load().catch(() => {}), { signal });
  toggle.addEventListener(
    "click",
    async () => {
      if (tree === null) {
        let module;
        try {
          module = await load();
        } catch (error) {
          // The press did nothing, so the header says so, and that the next press tries again.
          console.error("metabrowser diff: the Diff summary's tree did not load", error);
          if (!disposed) {
            toggle.setAttribute("aria-disabled", "true");
            toggle.dataset.tipText = "The list of files did not load. Press to try again.";
          }
          return;
        }
        if (disposed || view.disposed) {
          return;
        }
        toggle.removeAttribute("aria-disabled");
        delete toggle.dataset.tipText;
        tree ??= measureProjection(
          view.api,
          "diffSummary:mount",
          () =>
            module.mountSummaryTree({
              tree: model,
              files: rows,
              id,
              formatCount,
              changeLineNodes: paint.changeLineNodes,
              // The header's own chevron, for each folder row of the tree.
              chevron: () => {
                if (!chevronSvg) {
                  return null;
                }
                const box = el("span", "");
                box.innerHTML = chevronSvg;
                return box.firstElementChild;
              },
              // A file opens at its own address where the host has one, as a pull request's
              // page does (`/pull/<n>/files/<path>`), and the address shows it; elsewhere
              // the diff goes to it in place.
              jump: (path) => view.jump(path),
            }),
          { file_count: rows.length },
        );
        toggle.setAttribute("aria-controls", id);
        // Under the toolbar in a diff; under the header itself where a page places the
        // summary at its top (mb-pb35).
        (toggle.closest(".diff-toolbar") ?? toggle).after(tree.body);
      }
      const open = !tree.isOpen();
      const shown = tree;
      measureProjection(view.api, "diffSummary:toggle", () => shown.setOpen(open), {
        file_count: rows.length,
        open,
      });
      toggle.setAttribute("aria-expanded", String(open));
      toggle.classList.toggle("expanded", open);
      toggle.classList.toggle("collapsed", !open);
    },
    { signal },
  );
  return {
    element: toggle,
    dispose() {
      disposed = true;
      listening.abort();
      tree?.dispose();
      tree = null;
    },
  };
}

/**
 * A change set's Diff summary, or, where the shared changed-files tree did not load, its
 * totals on their own, "41 files changed · +6,526 −555": only the statuses, which the tree's
 * model names, and the tree of files are lost.
 *
 * @param {Record<string, unknown>} totals
 * @param {Record<string, unknown>[]} files
 * @param {SummaryOwner} view
 * @param {WholeTotals | null} [whole]
 * @returns {{element: HTMLElement, dispose: () => void}}
 */
function summaryOrTotals(totals, files, view, whole = null) {
  if (view.changedFiles !== null) {
    return renderDiffSummary(totals, files, view, view.changedFiles, whole);
  }
  const formatCount = countFormatter(view.api);
  const paint = shellPainters(view.api);
  const said = plainTotals(whole ?? totals, formatCount);
  const line = el("div", "diff-summary");
  line.append(
    ...(view.countsFiles
      ? [summaryFiles(said.filesParts, paint.countPartsNodes, LINE_SEPARATOR)]
      : []),
    ...paint.changeLineNodes(paint.changeLine(said.change), { spoken: ", " }),
  );
  if (said.estimated) {
    line.append(el("span", "diff-summary-note", "(estimated)"));
  }
  if (whole !== null) {
    line.append(listedNote(formatCount(files.length), paint.countPartsNodes));
  }
  return { element: line, dispose: () => {} };
}

/**
 * The whole change set's totals a page gave the diff, for a list cut short at its bound, or
 * null: a list that is whole says its own totals, and a page's totals that are not counts
 * are not said (A3 of review A on #470).
 *
 * @param {{truncated?: unknown}} manifest
 * @param {unknown} given
 * @returns {WholeTotals | null}
 */
function wholeTotalsOf(manifest, given) {
  if (manifest.truncated !== true || given === null || typeof given !== "object") {
    return null;
  }
  const totals = /** @type {Record<string, unknown>} */ (given);
  /** @param {unknown} value */
  const count = (value) => Number.isInteger(value) && Number(value) >= 0;
  /** @param {unknown} value */
  const lines = (value) => (count(value) ? Number(value) : null);
  if (!count(totals.files)) {
    return null;
  }
  return {
    files: Number(totals.files),
    additions: lines(totals.additions),
    deletions: lines(totals.deletions),
    exact: totals.exact === true,
  };
}

/**
 * The toolbar ends with the diff's choosers: Diff | Current, then the layout control, which
 * is present in the shell unless the host fixes the layout (*chooseLayout* false), as a pull
 * request's Docs tab does, where Diff | Current ends the toolbar alone. A multi-file diff's
 * toolbar leads with its Diff summary; single-file views avoid repeating their file bar. A
 * page that places the summary at its own top passes the place (*summaryHost*), as a
 * commit's page does (mb-pb35): the summary is drawn there, for one file too, since there it
 * stands for the change set's totals, and the toolbar holds the choosers alone. *whole* is
 * the change set's whole totals, where its list was cut short and the page knows them
 * (`wholeTotalsOf`). A *control* the host keeps across mounts, a narrowed diff's File type
 * control, leads the choosers.
 * @param {Record<string, unknown>} totals
 * @param {Record<string, unknown>[]} files
 * @param {MountedDiffState} view
 * @param {boolean} showSummary
 * @param {HTMLElement | null} [summaryHost]
 * @param {WholeTotals | null} [whole]
 * @param {HTMLElement | null} [hostControl]
 * @param {boolean} [chooseLayout] Whether the reader chooses the layout here, with the
 *   control and `L`.
 * @returns {{toolbar: HTMLElement, unbind: () => void}}
 */
function renderDiffToolbar(
  totals,
  files,
  view,
  showSummary,
  summaryHost = null,
  whole = null,
  hostControl = null,
  chooseLayout = true,
) {
  const toolbar = el("div", "diff-toolbar");
  /** @type {(() => void) | null} */
  let disposeSummary = null;
  if (showSummary && (summaryHost !== null || Number(totals.files) !== 1)) {
    // A page that places the summary at its own top says its file count on the size line
    // above it.
    const summary = summaryOrTotals(
      totals,
      files,
      summaryOwnerOf(view, summaryHost === null),
      whole,
    );
    disposeSummary = summary.dispose;
    if (summaryHost !== null) {
      summaryHost.replaceChildren(summary.element);
    } else {
      toolbar.append(summary.element);
    }
  }
  const filterControls = view.api?.filterControls;
  if (!filterControls) {
    return { toolbar, unbind: () => disposeSummary?.() };
  }
  if (hostControl !== null) {
    toolbar.append(hostControl);
  }
  // The choosers for the whole diff are one group at the toolbar's end, so where they do not
  // fit beside what leads them they take the next line together, still at its end.
  const end = el("div", "diff-toolbar-end");
  toolbar.append(end);
  const show = el("div", "diff-show-control");
  view.showControl = show;
  renderShowControl(view);
  end.append(show);
  const unbindShow = filterControls.bind(show, {
    onChange(key, value, select) {
      if (key === "diff-show" && select === "one") {
        setShow(view, value);
      }
    },
  });
  // Once, after the first draw, as `L` below: every host reaches this view through the
  // plugin's render, so a diff file, the Git commit view, and a pull request's Changes and
  // Docs all have `N`.
  attachShowKey(view);
  if (!chooseLayout) {
    return {
      toolbar,
      unbind: () => {
        unbindShow();
        disposeSummary?.();
      },
    };
  }
  const control = el("div", "diff-layout-control");
  view.layoutControl = control;
  renderLayoutControl(view);
  end.append(control);
  const unbindControls = filterControls.bind(control, {
    onChange(key, value, select) {
      if (key === "diff-layout" && select === "one") {
        setLayout(view, value);
      }
    },
  });
  const unbind = () => {
    unbindShow();
    unbindControls();
    disposeSummary?.();
  };
  // Once, after the first draw; each later draw retargets it, and dispose() detaches it.
  // Every host reaches this view through the plugin's render, so a diff file, the Git
  // commit view, and a pull request's Changes all have `L`.
  const shortcuts = view.api?.shortcuts;
  const option = typeof shortcuts?.attach === "function" ? layoutKeyOption(view) : null;
  if (shortcuts && option) {
    view.layoutKey = shortcuts.attach(option, {
      activate: () => toggleLayout(view),
      copy: {
        action: "Toggle diff layout",
        description: "Switch the diff between Split and Unified.",
        hint: "Layout",
      },
      group: "controls",
      id: "diff.layout",
      key: "l",
      order: 40,
    });
  }
  return { toolbar, unbind };
}

// ── Which deferred file is asked for next ───────────────────────
//
// A large comparison's remaining files are bars until a reader approaches them.
// This decides when each is requested and rendered, and owns no DOM, so
// tests/dom/diff-file-jump-session.js runs it with a scripted clock. It is here and not in a
// module of its own because a served folder's first diff requests the modules v0.11.0 did,
// which tests/test_diff_view_file_session.py holds.
//
// - One request at a time. On a store the route answers a file in tens of milliseconds from
//   its kept manifest, so a second one buys nothing, and a viewport that shows several bars
//   would otherwise fan out. On a folder nothing is kept, so each file costs the manifest
//   run again (about 0.7 s at 1,183 files, measured in the adapter), one after the other,
//   which is still ahead of the two-at-a-time whole-patch runs it replaced.
// - At most one file rendered per frame: the next request starts only after the frame
//   that rendered the last, so input is never waiting behind rendering it caused.
// - The file a reader jumped to is first, ahead of anything else, and latest wins: a jump
//   cancels the request for anything else. Scrolling cancels a request outside the
//   lookahead or puts an earlier file first. An answer already in hand can still draw.
// - A jump after a quiet moment asks at once. A jump during a burst, which is a held key, waits
//   until the burst stops, so a key held through ninety files asks for the one it rests on.

// How long a burst of jumps has to stop before the file it rests on is asked for. A key held
// down repeats about every 33 ms, so this is past one repeat, and it is what's left of the lines
// budget of 150 ms after a request of 13 to 30 ms and a frame of 16 ms.
export const JUMP_QUIET_MS = 50;

/**
 * @typedef {"painted" | "none" | "failed" | "superseded"} JumpOutcome
 *   What became of a jump's lines: on the page, none to show, the request failed, or another
 *   jump came first.
 *
 * @typedef {{
 *   load(id: string, signal: AbortSignal): Promise<unknown>,
 *   render(id: string, payload: unknown): JumpOutcome,
 *   fail(id: string, error: unknown): void,
 *   abandon(id: string): void,
 *   frame(callback: () => void): unknown,
 *   cancelFrame(handle: unknown): void,
 *   after(delayMs: number, callback: () => void): unknown,
 *   cancelAfter(handle: unknown): void,
 *   now(): number,
 * }} HydrationDependencies
 *
 * @typedef {{id: string, index: number, state: "pending" | "loading" | "done"}} HydrationEntry
 */

/**
 * @param {HydrationDependencies} deps
 */
export function createHydrationScheduler(deps) {
  /** @type {Map<string, HydrationEntry>} */
  const entries = new Map();
  /** Files in or immediately below the viewport. @type {Set<HydrationEntry>} */
  const nearby = new Set();
  /**
   * The request in flight. A request, not its file: an abandoned request's rejection
   * arrives after its file may have been asked for again, and must not answer for the
   * new request.
   *
   * @type {{entry: HydrationEntry, controller: AbortController} | null}
   */
  let active = null;
  /** A request that answered, waiting for its frame. @type {{entry: HydrationEntry, frame: unknown} | null} */
  let arrived = null;
  /** A passive continuation waiting one frame for updated observations. @type {unknown} */
  let continuation = null;
  /** @type {{entry: HydrationEntry, settle: (outcome: JumpOutcome) => void} | null} */
  let target = null;
  /** @type {unknown} */
  let quietTimer = null;
  let lastJumpAt = Number.NEGATIVE_INFINITY;
  let requests = 0;
  let disposed = false;

  /** @param {JumpOutcome} outcome */
  function settleTarget(outcome) {
    if (target !== null) {
      target.settle(outcome);
      target = null;
    }
  }

  function clearQuiet() {
    if (quietTimer !== null) {
      deps.cancelAfter(quietTimer);
      quietTimer = null;
    }
  }

  /** Forget the request or the answer in hand, and leave its file to be asked for again. */
  function abandonWork() {
    if (active !== null) {
      const { entry, controller } = active;
      active = null;
      entry.state = "pending";
      controller.abort();
      deps.abandon(entry.id);
    }
    if (arrived !== null) {
      const { entry, frame } = arrived;
      arrived = null;
      entry.state = "pending";
      deps.cancelFrame(frame);
      deps.abandon(entry.id);
    }
  }

  /**
   * Paint either answer in a frame, then let the new layout update nearby candidates
   * before starting a passive request. An explicit jump can still take the slot now.
   * @param {HydrationEntry} entry
   * @param {() => JumpOutcome} paint
   */
  function paintAnswer(entry, paint) {
    arrived = {
      entry,
      frame: deps.frame(() => {
        arrived = null;
        entry.state = "done";
        nearby.delete(entry);
        /** @type {JumpOutcome} */
        let outcome = "failed";
        try {
          outcome = paint();
        } finally {
          if (target?.entry === entry) {
            settleTarget(outcome);
          }
          if (nearby.size > 0 && continuation === null) {
            continuation = deps.frame(() => {
              continuation = null;
              pump();
            });
          }
        }
      }),
    };
  }

  /** @param {HydrationEntry} entry */
  function begin(entry) {
    const controller = new AbortController();
    entry.state = "loading";
    const ticket = { entry, controller };
    active = ticket;
    requests += 1;
    deps.load(entry.id, controller.signal).then(
      (payload) => {
        if (active !== ticket) {
          return;
        }
        active = null;
        paintAnswer(entry, () => {
          try {
            return deps.render(entry.id, payload);
          } catch (error) {
            deps.fail(entry.id, error);
            return "failed";
          }
        });
      },
      (error) => {
        if (active !== ticket) {
          return;
        }
        active = null;
        if (isAbortError(error)) {
          // Not an answer: the file is asked for again when it is next needed.
          entry.state = "pending";
          pump();
          return;
        }
        paintAnswer(entry, () => {
          deps.fail(entry.id, error);
          return "failed";
        });
      },
    );
  }

  /** The first pending file in or below the viewport. @returns {HydrationEntry | null} */
  function nextNearby() {
    /** @type {HydrationEntry | null} */
    let best = null;
    for (const entry of nearby) {
      if (entry.state === "pending" && (best === null || entry.index < best.index)) {
        best = entry;
      }
    }
    return best;
  }

  function pump() {
    if (disposed || active !== null || arrived !== null || quietTimer !== null) {
      return;
    }
    if (target !== null) {
      begin(target.entry);
      return;
    }
    if (continuation !== null) {
      return;
    }
    const quietLeft = lastJumpAt + JUMP_QUIET_MS - deps.now();
    if (quietLeft > 0) {
      quietTimer = deps.after(quietLeft, () => {
        quietTimer = null;
        pump();
      });
      return;
    }
    const entry = nextNearby();
    if (entry !== null) {
      begin(entry);
    }
  }

  return Object.freeze({
    /**
     * @param {string} id
     * @param {number} index The file's place in the comparison.
     */
    add(id, index) {
      entries.set(id, { id, index, state: "pending" });
    },
    /**
     * Apply one observation batch before picking a file, so a stale candidate that also
     * left in this batch cannot start a request.
     * @param {[id: string, inRange: boolean][]} changes
     */
    setNearby(changes) {
      if (disposed) {
        return;
      }
      for (const [id, inRange] of changes) {
        const entry = entries.get(id);
        if (entry === undefined || entry.state === "done") {
          continue;
        }
        if (inRange) {
          nearby.add(entry);
        } else {
          nearby.delete(entry);
        }
      }
      if (active !== null && target === null) {
        const first = nextNearby();
        if (!nearby.has(active.entry) || (first !== null && first.index < active.entry.index)) {
          abandonWork();
        }
      }
      pump();
    },
    /**
     * The reader asked for this file. Whatever else is under way stops.
     *
     * @param {string} id
     * @returns {Promise<JumpOutcome> | null} Its lines' outcome, or null for a file that has
     *   nothing left to ask for.
     */
    jump(id) {
      if (disposed) {
        return null;
      }
      const quiet = deps.now() - lastJumpAt >= JUMP_QUIET_MS;
      lastJumpAt = deps.now();
      settleTarget("superseded");
      clearQuiet();
      const entry = entries.get(id);
      const working = active?.entry ?? arrived?.entry ?? null;
      if (working !== null && working !== entry) {
        abandonWork();
      }
      if (entry === undefined || entry.state === "done") {
        pump();
        return null;
      }
      /** @type {Promise<JumpOutcome>} */
      const lines = new Promise((settle) => {
        target = { entry, settle };
      });
      if (entry.state === "pending") {
        if (quiet) {
          begin(entry);
        } else {
          quietTimer = deps.after(JUMP_QUIET_MS, () => {
            quietTimer = null;
            pump();
          });
        }
      }
      return lines;
    },
    dispose() {
      disposed = true;
      clearQuiet();
      if (continuation !== null) {
        deps.cancelFrame(continuation);
        continuation = null;
      }
      abandonWork();
      settleTarget("superseded");
      nearby.clear();
    },
    snapshot: () => ({
      asking: active?.entry.id ?? null,
      rendering: arrived?.entry.id ?? null,
      target: target?.entry.id ?? null,
      nearby: [...nearby].map((entry) => entry.id),
      requests,
    }),
  });
}

/** @param {unknown} error */
function isAbortError(error) {
  return (
    typeof error === "object" &&
    error !== null &&
    /** @type {{name?: unknown}} */ (error).name === "AbortError"
  );
}

/**
 * The rows a changed run of *adds* added and *dels* removed lines draws: Split pairs them,
 * Unified draws each, and Current draws the added alone. Pure.
 *
 * @param {number} adds
 * @param {number} dels
 * @param {Projection} layout
 */
function changedRows(adds, dels, layout) {
  if (layout === "split") {
    return Math.max(adds, dels);
  }
  return layout === "current" ? adds : adds + dels;
}

/**
 * Rows a deferred file should reserve until it arrives. An estimate from the manifest's line
 * counts, in the layout it will draw: a long run folds to its visible rows, and a change on
 * both sides has context around it. Pure.
 *
 * @param {Record<string, unknown>} change
 * @param {Projection} layout
 */
export function reservedRows(change, layout) {
  const adds = Number(change.additions ?? 0);
  const dels = Number(change.deletions ?? 0);
  const changed = changedRows(adds, dels, layout);
  const shown = FOLD_THRESHOLD > 0 && changed > FOLD_THRESHOLD ? FOLD_VISIBLE + 1 : changed;
  const context = adds > 0 && dels > 0 ? 6 : 0;
  return shown + context + 1;
}

/**
 * Rows a patch in hand draws in *layout*, before intraline pairing: a header per hunk, a row
 * per context line, and each changed run its rows, or its visible rows and the fold control
 * when it folds. These logical units estimate the initial drawing budget; the reserved
 * height accounts for each row kind separately. Soft-wrapped code can grow. Pure.
 *
 * @param {Record<string, unknown>} patch
 * @param {Projection} layout
 * @param {Record<string, unknown> | null} [change] The file's manifest entry.
 */
export function patchRows(patch, layout, change = null) {
  const { lines, headers, folds, notices } = patchRowCounts(patch, layout, change);
  return lines + headers + folds + notices;
}

/**
 * The gaps a patch in hand draws bars for (`gapsOf`, before any answer says where the file
 * ends), or null for a change whose gaps draw as plain headers.
 *
 * @param {Record<string, unknown>} patch
 * @param {Record<string, unknown>} change
 * @param {number} context
 * @returns {(HunkGap | null)[] | null}
 */
function patchGaps(patch, change, context) {
  const side = /** @type {{entry_type?: unknown} | undefined} */ (change.new);
  if (change.binary === true || side?.entry_type !== "file") {
    return null;
  }
  const hunks =
    /** @type {{old_start?: unknown, old_count?: unknown, new_start?: unknown, new_count?: unknown, lines?: {op?: unknown, no_newline?: unknown}[]}[]} */ (
      patch.hunks ?? []
    );
  const gaps = hunkGaps(
    hunks.map((hunk) => ({
      oldStart: Number(hunk.old_start),
      oldCount: Number(hunk.old_count),
      newStart: Number(hunk.new_start),
      newCount: Number(hunk.new_count),
      lines: (hunk.lines ?? []).map((line) => ({
        op: String(line.op),
        noNewline: line.no_newline === true,
      })),
    })),
    context,
  );
  if (patch.truncated && gaps.length > 0) {
    gaps[gaps.length - 1] = null;
  }
  return gaps;
}

/**
 * Count each differently sized row without drawing held lines. Soft-wrapped code can
 * grow after rendering; the single-line chrome has its exact shared CSS metrics. Current
 * leaves out a hunk with no line of the new file, header and all, and a file with no new
 * version, deleted or emptied, draws the one sentence that says so (`currentAbsence`),
 * which its manifest entry, *change*, tells. Where the diff reads its gaps (*gapContext*), a
 * hunk with a gap above it draws that gap's fold bar in place of its header, and a last
 * hunk the file may go on past draws one more below it (`hunkGaps`).
 * @param {Record<string, unknown>} patch
 * @param {Projection} layout
 * @param {Record<string, unknown> | null} [change]
 * @param {number | null} [gapContext] `GapSource.context`, where the diff reads its gaps.
 */
export function patchRowCounts(patch, layout, change = null, gapContext = null) {
  const rows = { lines: 0, headers: 0, folds: 0, notices: patch.truncated ? 1 : 0 };
  const hunks =
    /** @type {{lines?: {op?: unknown}[], new_start?: unknown, new_count?: unknown}[]} */ (
      patch.hunks ?? []
    );
  if (
    layout === "current" &&
    change !== null &&
    currentAbsence(
      change,
      hunks.map((hunk) => ({ newStart: Number(hunk.new_start), newCount: Number(hunk.new_count) })),
    ) !== null
  ) {
    rows.notices += 1;
    return rows;
  }
  const gaps = gapContext === null || change === null ? null : patchGaps(patch, change, gapContext);
  for (const [index, hunk] of hunks.entries()) {
    if (layout === "current" && (hunk.lines ?? []).every((line) => line.op === "del")) {
      continue;
    }
    if (gaps?.[index]) {
      rows.folds += 1;
    } else {
      rows.headers += 1;
    }
    if (gaps !== null && index === hunks.length - 1 && gaps[hunks.length]) {
      rows.folds += 1;
    }
    let adds = 0;
    let dels = 0;
    const endRun = () => {
      const run = changedRows(adds, dels, layout);
      const folded = FOLD_THRESHOLD > 0 && run > FOLD_THRESHOLD;
      rows.lines += folded ? FOLD_VISIBLE : run;
      rows.folds += folded ? 1 : 0;
      adds = 0;
      dels = 0;
    };
    for (const line of hunk.lines ?? []) {
      if (line.op === "context") {
        endRun();
        rows.lines += 1;
      } else if (line.op === "add") {
        adds += 1;
      } else {
        dels += 1;
      }
    }
    endRun();
  }
  return rows;
}

/**
 * How far below the diff's top the mount draws rows: what the pane shows of the diff, and one
 * screen more, so the first scroll finds lines and not reserved space. Infinite where nothing
 * was measured, so a diff mounted where nothing is laid out draws every ready file at once, as
 * it always did. Pure.
 *
 * @param {ScreenGeometry | null} screen
 */
export function firstScreenBudget(screen) {
  if (screen === null) {
    return Number.POSITIVE_INFINITY;
  }
  const shown = Math.max(0, screen.paneHeight - Math.max(0, screen.rootTop));
  return shown + screen.paneHeight;
}

/**
 * Hold a file's place on the page until its lines arrive, so what they push down is the
 * difference between this estimate and the truth and not a whole file.
 *
 * @param {HTMLElement} body
 * @param {{lines: number, headers: number, folds: number, notices: number}} rows
 */
function reserveBody(body, rows) {
  if (body.style) {
    body.style.setProperty(
      "--diff-reserved-height",
      `calc(${rows.lines} * var(--diff-code-row-height) + ${rows.headers} * var(--diff-header-row-height) + ${rows.folds} * var(--diff-fold-row-height) + ${rows.notices} * var(--diff-notice-row-height))`,
    );
  }
}

/**
 * Reserve the rows this file will draw in the current layout. Held answers use
 * their patch; a file not fetched yet uses the manifest estimate.
 * @param {DeferredFile} file
 * @param {Projection} layout
 * @param {MountedDiffState} view
 */
function reserveFileBody(file, layout, view) {
  if (file.held !== null) {
    reserveBody(
      file.body,
      patchRowCounts(
        file.held.patches[String(file.change.id)],
        layout,
        file.change,
        gapContextOf(view, file.revision),
      ),
    );
    return;
  }
  const adds = Number(file.change.additions ?? 0);
  const dels = Number(file.change.deletions ?? 0);
  const changed = changedRows(adds, dels, layout);
  const folds = FOLD_THRESHOLD > 0 && changed > FOLD_THRESHOLD ? 1 : 0;
  reserveBody(file.body, {
    lines: reservedRows(file.change, layout) - 1 - folds,
    headers: 1,
    folds,
    notices: 0,
  });
}

/** @param {HTMLElement} body */
function unreserveBody(body) {
  if (body.style) {
    body.style.removeProperty("--diff-reserved-height");
  }
}

/** @param {DeferredFile} file */
function deferredPath(file) {
  const side = /** @type {Record<string, unknown> | undefined} */ (
    file.change.new ?? file.change.old
  );
  return String(side?.path ?? "");
}

/**
 * Resolve after the next frame, or reject as aborted when *signal* is, cancelling the frame.
 * Immediate where there are no frames.
 *
 * @param {AbortSignal} signal
 * @returns {Promise<void>}
 */
function afterNextFrame(signal) {
  return new Promise((resolve, reject) => {
    if (typeof requestAnimationFrame !== "function") {
      resolve();
      return;
    }
    /** @type {number} */
    let handle = 0;
    const stop = () => {
      cancelAnimationFrame(handle);
      reject(new DOMException("The jump moved on.", "AbortError"));
    };
    handle = requestAnimationFrame(() => {
      signal.removeEventListener("abort", stop);
      resolve();
    });
    signal.addEventListener("abort", stop, { once: true });
  });
}

/**
 * Ask for one deferred file, behind the standard progress box. A file whose answer is in hand
 * is not asked for. When it is the file a jump put at the top, it waits one frame first, so the
 * frame that shows its bar there is not also the one that draws its rows: drawn in the same
 * frame, a jump to a held file showed its bar in 49 to 54 ms on a 1,031-file comparison and in
 * 137 ms on a 1,627-file one, against a budget of 50 (2026-11-03, Chrome 152, load 8 to 21).
 *
 * @param {DeferredFile} file
 * @param {AbortSignal} signal
 * @param {MountedDiffState} view
 * @returns {Promise<OneFileAnswer>}
 */
async function loadDeferred(file, signal, view) {
  if (file.held !== null) {
    if (view.pinned === file.section) {
      await afterNextFrame(signal);
    }
    return file.held;
  }
  const path = deferredPath(file);
  file.box = progressBox(`Loading the diff for ${path}`);
  file.body.append(file.box);
  file.startedAt = Date.now();
  const generation = view.generation;
  file.slow = setTimeout(() => {
    if (mountIsCurrent(view, generation)) {
      reportLoad("file hydration", {
        revision: file.revision,
        path,
        elapsedMs: Date.now() - file.startedAt,
      });
    }
  }, SLOW_LOAD_MS);
  const payload = await loadOneChange(file.revision, path, { signal });
  const result = validateDocument(payload);
  if (!result.ok) {
    // The validator's location rides as the cause, which the console report of a failed
    // file prints (docs/design-system-messages.md).
    throw new Error("This diff document is not valid.", { cause: result.error });
  }
  return /** @type {OneFileAnswer} */ (result.document);
}

/** @param {DeferredFile} file */
function stopLoading(file) {
  if (file.slow !== null) {
    clearTimeout(file.slow);
    file.slow = null;
  }
  file.box?.remove();
  file.box = null;
}

/**
 * A deferred file arrived or failed. Release its progress, reservation, and observation.
 *
 * @param {DeferredFile} file
 * @param {MountedDiffState} view
 */
function settleDeferred(file, view) {
  stopLoading(file);
  unreserveBody(file.body);
  view.hydrationObserver?.unobserve(file.section);
  view.deferred.delete(String(file.change.id));
  view.deferredBySection.delete(file.section);
  view.reached.delete(String(file.change.id));
  if (view.deferred.size === 0) {
    view.hydrationObserver?.disconnect();
    view.hydrationObserver = null;
  }
}

/**
 * Splice an answer in. Runs in its own frame, and what the reader is looking at stays where it
 * is: a jump's file, or the first file at the top of the pane.
 *
 * @param {DeferredFile} file
 * @param {OneFileAnswer} loaded
 * @param {MountedDiffState} view
 * @returns {JumpOutcome}
 */
function renderDeferred(file, loaded, view) {
  const anchor = view.pinned === null ? placeOfTopFile(view, true) : null;
  settleDeferred(file, view);
  /** @type {JumpOutcome} */
  let outcome;
  try {
    outcome = spliceDeferred(file, loaded, view);
  } catch (error) {
    // The file is settled, so its failure is its own to show and count: the scheduler's
    // own failure path looks the file up by id and would find nothing (review of #284, D4).
    outcome = failDeferred(file, error, view);
  }
  holdPlace(view, anchor);
  view.notifyCurrentFile();
  return outcome;
}

/**
 * What a settled file's answer puts in its body.
 *
 * @param {DeferredFile} file
 * @param {OneFileAnswer} loaded
 * @param {MountedDiffState} view
 * @returns {JumpOutcome}
 */
function spliceDeferred(file, loaded, view) {
  const only = loaded.manifest.files[0];
  const patch = only ? loaded.patches[String(only.id)] : undefined;
  const availability = only ? String(only.availability) : "";
  const reason =
    availability === "deferred" ? DEFERRED_AGAIN_COPY : AVAILABILITY_COPY[availability];
  if (only && patch === undefined && reason) {
    // The server looked and has a reason: a file past the bound of one patch.
    file.body.append(el("div", "diff-availability", reason));
    if (availability === "binary") {
      appendPdfCard(view, only, file.body);
    }
    return "none";
  }
  if (!only || patch === undefined) {
    return failDeferred(file, new Error("the comparison returned no hunks for this file"), view);
  }
  if (/** @type {unknown[]} */ (patch.hunks).length === 0 && !view.canShowFull) {
    file.body.append(el("div", "diff-availability", "No content changes."));
    return "none";
  }
  const state = createFileState(
    only,
    patch,
    view.api ?? plainSyntaxApi(),
    file.body,
    view.unfold,
    gapSourceOf(view, file.revision),
  );
  state.fullSource = fullSourceOf(view, state.gaps, only);
  if (!view.awaitingWidth) {
    renderFileBody(state, projectionOf(view));
  }
  // Only a file whose rows are in the page is a file of the view: one whose render threw
  // would throw again at every relayout.
  view.files.push(state);
  scheduleFileEnhancement(view, state);
  return "painted";
}

/**
 * @param {DeferredFile} file
 * @param {unknown} error
 * @param {MountedDiffState} view
 * @returns {JumpOutcome}
 */
function failDeferred(file, error, view) {
  const count = ++view.deferredFailed;
  view.hydrationFailure.textContent = `Could not load changes for ${countFormatter(view.api)(count)} ${count === 1 ? "file" : "files"}.`;
  view.hydrationFailure.hidden = false;
  reportLoad(
    "file hydration",
    {
      revision: file.revision,
      path: deferredPath(file),
      hook: "diff/comparison",
      elapsedMs: Date.now() - file.startedAt,
    },
    error,
  );
  file.body.append(noticeEl("error", "", "Could not load this file's changes."));
  return "failed";
}

/**
 * Defer one file request until its section approaches the visible scroll area.
 * The comparison payload already hydrates the leading files. The rest are queued
 * by their place and observed once the diff is in its scroll pane.
 *
 * A ready file past the first screen takes the same path with its answer in *held*: it is
 * drawn when it is reached or gone to, one file a frame like the rest, and never asked for.
 *
 * @param {HTMLElement} section
 * @param {HTMLElement} body
 * @param {Record<string, unknown>} change
 * @param {string} revision
 * @param {MountedDiffState} view
 * @param {OneFileAnswer | null} [held]
 */
function queueDeferredHydration(section, body, change, revision, view, held = null) {
  const id = String(change.id);
  view.deferred.set(id, {
    body,
    box: null,
    change,
    held,
    revision,
    section,
    slow: null,
    startedAt: 0,
  });
  view.deferredBySection.set(section, id);
  view.hydration.add(id, view.deferred.size);
  reserveFileBody(/** @type {DeferredFile} */ (view.deferred.get(id)), projectionOf(view), view);
}

/** @param {MountedDiffState} view */
function observeHydration(view) {
  if (view.deferred.size === 0) {
    return;
  }
  const pane = scrollerOf(view);
  // Expand the inner pane's own clipping edge. Use the implicit viewport for
  // document scrolling, where the document element's box moves with scroll.
  const root = pane === view.root.ownerDocument?.scrollingElement ? null : pane;
  view.hydrationObserver = new IntersectionObserver(
    (entries) => {
      if (view.disposed || view.controller.signal.aborted) {
        return;
      }
      /** @type {[string, boolean][]} */
      const changes = [];
      for (const entry of entries) {
        const id = view.deferredBySection.get(/** @type {HTMLElement} */ (entry.target));
        if (id !== undefined) {
          if (entry.isIntersecting) {
            view.reached.add(id);
          } else {
            view.reached.delete(id);
          }
          changes.push([id, entry.isIntersecting && bodyWanted(view, id)]);
        }
      }
      view.hydration.setNearby(changes);
    },
    { root, rootMargin: `0px 0px ${HYDRATION_AHEAD_PX}px 0px` },
  );
  for (const section of view.deferredBySection.keys()) {
    view.hydrationObserver.observe(section);
  }
}

/**
 * Whether a held file's body is to be drawn once it is reached: not while the file's
 * rendered view hides it (`createMarkdownViews`), since rows nobody sees would cost what
 * the reader sees: a 17,177-line document's Source on a pull request's Docs, drawn at load
 * behind its rendered view, was 72,000 nodes and 4 s of main-thread work.
 *
 * @param {MountedDiffState} view
 * @param {string} id
 */
function bodyWanted(view, id) {
  return view.deferred.get(id)?.body.hidden !== true;
}

/**
 * A held file's rendered view showed or hid its body: drawn now if it is reached, and not
 * drawn while it is hidden.
 *
 * @param {MountedDiffState} view
 * @param {string} id
 */
function bodyShownChanged(view, id) {
  if (view.deferred.has(id)) {
    view.hydration.setNearby([[id, view.reached.has(id) && bodyWanted(view, id)]]);
  }
}

/**
 * What runs a view's hydration in a browser: its frames and its timers.
 *
 * @param {MountedDiffState} view
 * @returns {HydrationDependencies}
 */
function hydrationHost(view) {
  /** @param {string} id */
  const fileOf = (id) => /** @type {DeferredFile} */ (view.deferred.get(id));
  return {
    load: (id, signal) => loadDeferred(fileOf(id), signal, view),
    render: (id, payload) =>
      renderDeferred(
        fileOf(id),
        /** @type {Parameters<typeof renderDeferred>[1]} */ (payload),
        view,
      ),
    fail(id, error) {
      const file = view.deferred.get(id);
      if (file === undefined) {
        // Settled already: `renderDeferred` owns a throw past `settleDeferred` and has
        // counted and said it, so this is the one its own message could not be appended
        // for. Nothing is settled twice, and the frame it runs in ends clean.
        reportLoad("file hydration", { fileId: id, hook: "diff/comparison" }, error);
        return;
      }
      const anchor = view.pinned === null ? placeOfTopFile(view, true) : null;
      settleDeferred(file, view);
      try {
        failDeferred(file, error, view);
      } finally {
        holdPlace(view, anchor);
        view.notifyCurrentFile();
      }
    },
    abandon: (id) => stopLoading(fileOf(id)),
    frame: (callback) =>
      typeof requestAnimationFrame === "function"
        ? requestAnimationFrame(callback)
        : setTimeout(callback, 0),
    cancelFrame(handle) {
      if (typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(/** @type {number} */ (handle));
      } else {
        clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (handle));
      }
    },
    after: (delayMs, callback) => setTimeout(callback, delayMs),
    cancelAfter: (handle) => clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (handle)),
    now: () => Date.now(),
  };
}

// ── Going to a file ─────────────────────────────────────────────

/** The element that scrolls this diff. @param {MountedDiffState} view */
function scrollerOf(view) {
  return /** @type {HTMLElement | null} */ (
    view.root.closest?.("[data-kpress-viewport]") ??
      view.root.ownerDocument?.scrollingElement ??
      null
  );
}

/**
 * Where a jump puts the pane, and the room past the last file it takes for the target to
 * reach the top. Pure. Tops and bottoms are in the viewport's coordinates, and *contentBottom*
 * is the end of the diff without any room already added.
 *
 * @param {{paneTop: number, paneHeight: number, scrollTop: number, targetTop: number, contentBottom: number}} geometry
 * @returns {{scrollTop: number, spacer: number}}
 */
export function jumpPlacement({ paneTop, paneHeight, scrollTop, targetTop, contentBottom }) {
  return {
    scrollTop: scrollTop + targetTop - paneTop,
    spacer: Math.max(0, paneHeight - (contentBottom - targetTop)),
  };
}

/**
 * Put a file at the top of the pane, with no smooth scroll, and room below it if it is near
 * the end. Room rather than a smaller scroll, because a file that cannot reach the top is
 * pushed off the screen by the files above it filling in: 53,661 px, measured 2026-11-02
 * on a comparison of 1,183 files, whatever the browser's scroll anchoring holds.
 *
 * @param {MountedDiffState} view
 * @param {HTMLElement} section
 */
function placeAtTop(view, section) {
  const pane = scrollerOf(view);
  const spacer = view.spacer;
  if (pane === null || spacer === null) {
    return;
  }
  const paneRect = pane.getBoundingClientRect();
  const place = jumpPlacement({
    paneTop: paneRect.top,
    paneHeight: pane.clientHeight,
    scrollTop: pane.scrollTop,
    targetTop: section.getBoundingClientRect().top,
    contentBottom: view.root.getBoundingClientRect().bottom - spacer.getBoundingClientRect().height,
  });
  spacer.style.height = `${place.spacer}px`;
  pane.scrollTop = place.scrollTop;
}

/**
 * The first file at the top of the pane and where it is, for a change that should not move it.
 * Found by bisection, since the sections are in order: ten reads at 1,183 files.
 *
 * @param {MountedDiffState} view
 * @param {boolean} [mustCoverPaneTop] Preserve an offset above the diff when its heading is visible.
 * @returns {Place | null}
 */
function placeOfTopFile(view, mustCoverPaneTop = false) {
  const pane = scrollerOf(view);
  if (pane === null || view.sections.length === 0) {
    return null;
  }
  const paneTop = pane.getBoundingClientRect().top;
  let low = 0;
  let high = view.sections.length - 1;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (view.sections[middle].getBoundingClientRect().bottom > paneTop) {
      high = middle;
    } else {
      low = middle + 1;
    }
  }
  const section = view.sections[low];
  const { top, bottom } = section.getBoundingClientRect();
  if (mustCoverPaneTop && (top > paneTop || bottom <= paneTop)) {
    return null;
  }
  return { section, top };
}

/**
 * What a rendered file's change keeps on the screen: the file at the pane's top and, when
 * it shows rendered Markdown, the block at the pane's top, found again by its index after
 * the change, which may draw it anew (`drawnRows`).
 *
 * @param {MountedDiffState} view
 * @returns {Place | null}
 */
function placeOfTopRendered(view) {
  const place = placeOfTopFile(view, true);
  const rendered = place?.section.querySelector(".diff-markdown") ?? null;
  return place === null || rendered === null || /** @type {HTMLElement} */ (rendered).hidden
    ? place
    : placeOfTopRow(view, view.show);
}

/**
 * What a Diff | Current choice keeps on the screen: the file at the pane's top, as
 * `placeOfTopFile` finds it, and the row of it at the pane's top, or the nearest row that
 * what the diff is about to show (*next*) draws too (`anchorRow`), with where that row is to
 * be. A rendered file's rows are its blocks, a fold among them, or its tree's rows; a code
 * file's are its lines. A file with no such row keeps its own top.
 *
 * @param {MountedDiffState} view
 * @param {Shown} next
 * @returns {Place | null}
 */
function placeOfTopRow(view, next) {
  const place = placeOfTopFile(view);
  const pane = scrollerOf(view);
  if (place === null || pane === null) {
    return place;
  }
  const paneTop = pane.getBoundingClientRect().top;
  if (place.section.getBoundingClientRect().top >= paneTop) {
    return place;
  }
  const rows = drawnRows(view, place.section, next !== "diff");
  /** @type {Map<number, {top: number, bottom: number, kept: boolean}>} */
  const boxes = new Map();
  const chosen = anchorRow(
    rows.length,
    (index) => {
      let box = boxes.get(index);
      if (box === undefined) {
        const { top, bottom } = rows[index].element.getBoundingClientRect();
        box = { top, bottom, kept: rows[index].kept };
        boxes.set(index, box);
      }
      return box;
    },
    paneTop,
    paneTop + pane.clientHeight,
  );
  if (chosen === null) {
    return place;
  }
  const { find, state } = rows[chosen.index];
  return { ...place, row: { find, top: paneTop + chosen.offset, state } };
}

/**
 * Which of a file's drawn rows a Diff | Current choice keeps, and how far below the pane's
 * top it keeps its top, or null for none. The *count* rows are in order, and *rowAt* gives
 * one's box and whether the choice draws it too (*kept*); the row at the pane's top is found
 * by bisection, so a long file measures few. That row, or the first kept row after it, keeps
 * where it is while it is on the screen. Where the choice leaves out every row from the
 * pane's top to its end, which is Current inside a long removal, the last kept row above goes
 * just above the top, so what follows it, where the removal was, is at the top; with none
 * above, the first kept row below goes to the top. Pure.
 *
 * @param {number} count
 * @param {(index: number) => {top: number, bottom: number, kept: boolean}} rowAt
 * @param {number} paneTop
 * @param {number} paneBottom
 * @returns {{index: number, offset: number} | null}
 */
export function anchorRow(count, rowAt, paneTop, paneBottom) {
  let atTop = 0;
  let high = count;
  while (atTop < high) {
    const middle = (atTop + high) >> 1;
    if (rowAt(middle).bottom > paneTop) {
      high = middle;
    } else {
      atTop = middle + 1;
    }
  }
  let after = -1;
  for (let index = atTop; index < count; index += 1) {
    if (rowAt(index).kept) {
      after = index;
      break;
    }
  }
  if (after !== -1 && rowAt(after).top < paneBottom) {
    return { index: after, offset: rowAt(after).top - paneTop };
  }
  for (let index = atTop - 1; index >= 0; index -= 1) {
    const row = rowAt(index);
    if (row.kept) {
      return { index, offset: row.top - row.bottom };
    }
  }
  return after === -1 ? null : { index: after, offset: 0 };
}

/**
 * A file's rows as it draws them now, in order: each element, whether Current (*current*
 * true) or Diff draws it too, and how to find it once the choice is drawn. Rendered Markdown
 * keeps its block elements and hides what Current leaves out, so a block is its own element
 * after, and a view drawn anew draws it again by its index (`drawnBlock`); a YAML or JSON
 * tree is drawn again, with the same paths; a code file's rows are drawn again from the same
 * lines, so a row is found by its line, the new side's in Split.
 *
 * @param {MountedDiffState} view
 * @param {HTMLElement} section
 * @param {boolean} current
 * @returns {{element: HTMLElement, kept: boolean, find: () => HTMLElement | null, state: FileViewState | null}[]}
 */
function drawnRows(view, section, current) {
  const rendered = /** @type {HTMLElement | null} */ (
    section.querySelector(".diff-markdown") ?? section.querySelector(".diff-structured")
  );
  if (rendered !== null && !rendered.hidden) {
    const tree = /** @type {HTMLElement | null} */ (rendered.querySelector(".tree-viewport"));
    if (tree !== null) {
      return [...tree.children].map((child) => {
        const element = /** @type {HTMLElement} */ (child);
        const path = element.getAttribute("data-path");
        return {
          element,
          kept: !current || !element.classList.contains("srow-change-removed"),
          find: () => {
            if (rendered.hidden) {
              return null;
            }
            const found = [...tree.children].find((row) => row.getAttribute("data-path") === path);
            return found === undefined ? null : /** @type {HTMLElement} */ (found);
          },
          state: null,
        };
      });
    }
    return markdownRows(rendered).map((element) => {
      const at = blockAt(element);
      return {
        element,
        kept: !current || !element.classList.contains("diff-markdown-removed"),
        find: () => {
          if (rendered.hidden) {
            return null;
          }
          if (element.isConnected && !element.hidden) {
            return element;
          }
          if (at === null) {
            return null;
          }
          // Drawn anew, the view may keep the block in a chunk not drawn yet: its chunk is
          // drawn, so the block itself keeps the reader's place.
          view.markdown?.controller.drawBlock(section, at);
          return drawnBlock(/** @type {HTMLElement} */ (rendered), at);
        },
        state: null,
      };
    });
  }
  const state = view.files.find((file) => section.contains(file.body)) ?? null;
  if (state === null || !drawsLines(state)) {
    return [];
  }
  /** @type {Map<HTMLElement, DiffLine>} */
  const lines = new Map();
  for (const { host, line, side } of state.textHosts) {
    const row = rowOfHost(host);
    if (row !== null && (side === "new" || !lines.has(row))) {
      lines.set(row, line);
    }
  }
  // In the page's order: a fold's rows are drawn after the rows below it.
  const split = state.body.querySelectorAll(".diff-split-row");
  const drawn = split.length > 0 ? split : state.body.querySelectorAll(".diff-line");
  return [...drawn].flatMap((element) => {
    const row = /** @type {HTMLElement} */ (element);
    const line = lines.get(row);
    return line === undefined
      ? []
      : [
          {
            element: row,
            kept: !current || line.op !== "del",
            find: () => rowOfLine(state, line),
            state,
          },
        ];
  });
}

/**
 * A rendered Markdown article's rows in the page's order: its own, in place of a change the
 * rows its runs hold (`changeRuns` in diff-markdown.js), and in place of an open fold's
 * group, the rows the group holds, so the row at the pane's top is the block there however
 * deep in a fold it is. A fold's rows are its blocks and the places of its chunks not drawn
 * yet; a closed fold's group holds none.
 *
 * @param {HTMLElement} rendered
 * @returns {HTMLElement[]}
 */
function markdownRows(rendered) {
  /** @type {HTMLElement[]} */
  const rows = [];
  for (const child of rendered.children) {
    const element = /** @type {HTMLElement} */ (child);
    if (element.hidden) {
      continue;
    }
    if (element.classList.contains("diff-markdown-change")) {
      for (const run of element.children) {
        for (const row of run.children) {
          if (!(/** @type {HTMLElement} */ (row).hidden)) {
            rows.push(/** @type {HTMLElement} */ (row));
          }
        }
      }
      continue;
    }
    if (!element.classList.contains("diff-fold-group")) {
      rows.push(element);
      continue;
    }
    if (!element.classList.contains("diff-fold-collapsed")) {
      for (const inner of element.children) {
        if (!(/** @type {HTMLElement} */ (inner).hidden)) {
          rows.push(/** @type {HTMLElement} */ (inner));
        }
      }
    }
  }
  return rows;
}

/**
 * The first block of a rendered Markdown row: a block's own index (`data-block`), or the
 * first of those a fold's bar or a chunk not drawn yet stands for (`data-span`).
 *
 * @param {HTMLElement} element
 * @returns {number | null}
 */
function blockAt(element) {
  const own = element.dataset?.block ?? element.dataset?.span?.split("-")[0];
  return own === undefined ? null : Number(own);
}

/**
 * The element that draws block *index* of a rendered Markdown file now: its row, or what
 * stands for it, the fold's bar that holds it or the place of a chunk not drawn yet. A
 * view drawn anew, Full for Concise or a chunk for its place, keeps its blocks' indexes,
 * so a block the reader was looking at is found again however it is drawn.
 *
 * @param {HTMLElement} rendered
 * @param {number} index
 * @returns {HTMLElement | null}
 */
function drawnBlock(rendered, index) {
  /** @type {HTMLElement | null} */
  let best = null;
  for (const child of rendered.querySelectorAll("[data-block], [data-span]")) {
    const element = /** @type {HTMLElement} */ (child);
    if (element.hidden || element.closest(".diff-fold-collapsed") !== null) {
      continue;
    }
    if (element.dataset.block === String(index)) {
      return element;
    }
    const [start, end] = (element.dataset.span ?? "").split("-").map(Number);
    if (start <= index && index < end) {
      // The innermost: a chunk's place inside an open fold, before the fold's bar.
      best = element;
    }
  }
  return best;
}

/** Whether a code file's body is drawn: not collapsed, and not under its Rendered view. @param {FileViewState} state */
function drawsLines(state) {
  return !state.body.hidden && !state.body.classList.contains("diff-file-body-collapsed");
}

/**
 * The row a line's text sits in: a Unified or Current `.diff-line`, or the Split row whose
 * side it is.
 *
 * @param {HTMLElement} host
 * @returns {HTMLElement | null}
 */
function rowOfHost(host) {
  const cell = host.parentElement;
  return cell?.classList.contains("diff-split-side") ? cell.parentElement : cell;
}

/**
 * Every line a file can draw, in the file's order: each hunk's, after the lines read for the
 * gap above it, and last those read for the gap below the last hunk.
 *
 * @param {FileViewState} state
 * @returns {Map<DiffLine, number>}
 */
function lineOrder(state) {
  /** @type {Map<DiffLine, number>} */
  const order = new Map();
  const gaps = gapsOf(state) ?? [];
  const read = state.gapLines.byNumber;
  const numbers = gaps.length === 0 ? [] : [...read.keys()].sort((a, b) => a - b);
  let next = 0;
  /** @param {number} end */
  const readBefore = (end) => {
    while (next < numbers.length && numbers[next] < end) {
      order.set(/** @type {DiffLine} */ (read.get(numbers[next])), order.size);
      next += 1;
    }
  };
  for (const [index, hunk] of state.renderModel.hunks.entries()) {
    const gap = gaps[index] ?? null;
    if (gap?.end != null) {
      readBefore(gap.end);
    }
    for (const each of hunk.lines) {
      order.set(each, order.size);
    }
  }
  readBefore(Number.POSITIVE_INFINITY);
  return order;
}

/**
 * The row that draws *line* now, or, where a fold keeps it out of the page, the row of the
 * nearest line before it that is drawn, else after it. Null when the file draws no line.
 *
 * @param {FileViewState} state
 * @param {DiffLine} line
 * @returns {HTMLElement | null}
 */
function rowOfLine(state, line) {
  if (!drawsLines(state)) {
    return null;
  }
  if (state.full.rows !== null && line.newNumber !== null) {
    const number = line.newNumber;
    let distance = Number.POSITIVE_INFINITY;
    /** @type {HTMLElement | null} */
    let best = null;
    for (const { host, line: drawn } of state.textHosts) {
      if (!host.isConnected || drawn.newNumber === null) {
        continue;
      }
      const away = Math.abs(drawn.newNumber - number);
      if (away < distance) {
        best = rowOfHost(host);
        distance = away;
      }
    }
    return best;
  }
  const order = lineOrder(state);
  const at = order.get(line) ?? 0;
  /** @type {{host: HTMLElement, index: number} | null} */
  let before = null;
  /** @type {{host: HTMLElement, index: number} | null} */
  let after = null;
  for (const { host, line: drawn } of state.textHosts) {
    if (drawn === line && host.isConnected) {
      return rowOfHost(host);
    }
    const index = order.get(drawn) ?? -1;
    if (index < at && (before === null || index > before.index)) {
      before = { host, index };
    } else if (index > at && (after === null || index < after.index)) {
      after = { host, index };
    }
  }
  const nearest = before ?? after;
  return nearest === null ? null : rowOfHost(nearest.host);
}

/**
 * The page changed height: put back what the reader was looking at, the row a Diff | Current
 * choice keeps (`placeOfTopRow`), or the file at the pane's top. This measures where it is
 * and moves the pane by the difference, so where a browser's own scroll anchoring has kept
 * the same row in place, it moves nothing, and in a browser without anchoring it holds.
 *
 * @param {MountedDiffState} view
 * @param {Place | null} [anchor]
 */
function holdPlace(view, anchor = null) {
  if (view.pinned !== null) {
    placeAtTop(view, view.pinned);
    return;
  }
  if (anchor !== null) {
    const pane = scrollerOf(view);
    const row = anchor.row?.find() ?? null;
    const moved =
      row !== null && anchor.row !== undefined
        ? row.getBoundingClientRect().top - anchor.row.top
        : anchor.section.getBoundingClientRect().top - anchor.top;
    if (pane !== null && Math.abs(moved) >= HOLD_PLACE_MIN_PX) {
      pane.scrollTop += moved;
    }
  }
}

// The least drift `holdPlace` puts back: no finer than the step the pane's scroll position
// takes, so a correction never leaves a drift it would correct again. A move under the step
// is made as a whole step, past the row, and Chrome's own anchoring, which keeps a row's
// rounded place, then holds it there. Chrome's step is a device pixel: set to 1146.25,
// 1146.5, and 1146.75, an element's scrollTop read back 1146, 1147, and 1147 at a device
// pixel ratio of 1, which the Chrome tier forces (tests/dom/chrome-session.mjs), and 1146.5,
// 1146.5, and 1147 at 2 (headless Chrome, 2026-11-25). At 1, opening a hunk gap above the
// pane's top (tests/dom/diff-hunk-gap-chrome.mjs) with half a pixel here, a drift of 0.5 px
// moved the pane from 1146 to 1147, and the row at the pane's top ended 1 px above where it
// was, 1.1-1.5 px while the gap's group grew; with a whole pixel it ended where it was and
// stayed within 0.48 px of it at every frame. It is not `1 / devicePixelRatio`, which in
// Chrome at 2 would put back a drift of half a pixel this leaves: WebKit's step is
// unmeasured, and on any scroller coarser than a device pixel that would bring the overshoot
// back. A drift it leaves is under a pixel, and each call measures it from the place first
// kept, so it does not grow.
const HOLD_PLACE_MIN_PX = 1;

/**
 * Keep holding a Diff | Current choice's row while its file's open folds draw their rows,
 * which they do in batches after the redraw (`renderFoldControl`): a kept line inside one is
 * not drawn until its batch is. Ends when they are drawn, at the next redraw, or at the
 * reader's own move, as a pin does (`releasePinOnInput`).
 *
 * @param {MountedDiffState} view
 * @param {Place | null} anchor
 * @param {FileViewState | null} [drawing] The file whose rows are being drawn, where it is
 *   not the kept row's: a gap opened in a file above the pane's top (`gapSourceOf`).
 */
function settlePlace(view, anchor, drawing = null) {
  const state = drawing ?? anchor?.row?.state ?? null;
  const pane = scrollerOf(view);
  if (anchor === null || state === null || pane === null || state.foldTasks.size === 0) {
    return;
  }
  const generation = view.layoutGeneration;
  const since = eventClockNow();
  const listening = new AbortController();
  const options = { capture: true, passive: true, signal: listening.signal };
  /** @param {{timeStamp?: number}} [event] */
  const releaseHold = (event) => {
    if (typeof event?.timeStamp !== "number" || event.timeStamp >= since) {
      listening.abort();
    }
  };
  for (const type of ["wheel", "touchstart", "pointerdown"]) {
    pane.addEventListener(type, releaseHold, options);
  }
  pane.ownerDocument?.defaultView?.addEventListener("keydown", releaseHold, options);
  const step = () => {
    view.timers.delete(timer);
    if (listening.signal.aborted || view.disposed || view.layoutGeneration !== generation) {
      listening.abort();
      return;
    }
    holdPlace(view, anchor);
    if (state.foldTasks.size === 0) {
      listening.abort();
      return;
    }
    timer = setTimeout(step, 0);
    view.timers.add(timer);
  };
  let timer = setTimeout(step, 0);
  view.timers.add(timer);
}

/**
 * From the reader's own move on, the place is theirs. Only input says so: a browser's scroll
 * anchoring and this view's own corrections move the pane too.
 *
 * @param {MountedDiffState} view
 * @param {HTMLElement} pane
 */
function releasePinOnInput(view, pane) {
  if (view.pinListeners !== null) {
    return;
  }
  const listening = new AbortController();
  view.pinListeners = listening;
  const options = { capture: true, passive: true, signal: listening.signal };
  /** @param {{timeStamp?: number}} [event] */
  const release = (event) => {
    // The key that caused a jump is older than the pin it would release: a list's own
    // handler may run before or after this one, and the pin holds either way. A key
    // pressed after the jump releases it.
    if (typeof event?.timeStamp === "number" && event.timeStamp < view.pinnedAt) {
      return;
    }
    view.pinned = null;
  };
  for (const type of ["wheel", "touchstart", "pointerdown"]) {
    pane.addEventListener(type, release, options);
  }
  pane.ownerDocument?.defaultView?.addEventListener("keydown", release, options);
}

/**
 * The file a path names: what it is called now, which is what GitHub's list of a pull request's
 * files gives as `filename`, or else what it was called, its `previous_filename`.
 *
 * @param {MountedDiffState} view
 * @param {string} path
 */
function fileEntryForPath(view, path) {
  return view.byNewPath.get(path) ?? view.byOldPath.get(path) ?? null;
}

/** The clock an event's `timeStamp` is on, where there is one. */
function eventClockNow() {
  return typeof performance === "object" && typeof performance.now === "function"
    ? performance.now()
    : Date.now();
}

/**
 * Whether this comparison holds a path, for a list of files from elsewhere, without moving
 * anything. Typed as `scrollToFile`'s answer is, so a list can tell a file the comparison
 * lacks from one it holds.
 *
 * @param {MountedDiffState} view
 * @param {string} path
 * @returns {FileLookup}
 */
export function lookupFile(view, path) {
  const entry = fileEntryForPath(view, path);
  if (entry === null) {
    return { kind: "not_in_comparison", path, listTruncated: view.listTruncated };
  }
  return {
    kind: "file",
    path,
    fileId: String(entry.change.id),
    changeKind: String(entry.change.kind),
    availability: String(entry.change.availability),
  };
}

/**
 * Go to one file of this diff, at the top of the pane, and ask for its lines first.
 *
 * @param {MountedDiffState} view
 * @param {string} path
 * @returns {FileJump}
 */
export function jumpToFile(view, path) {
  if (view.disposed) {
    return { kind: "disposed", path };
  }
  const entry = fileEntryForPath(view, path);
  if (entry === null) {
    return { kind: "not_in_comparison", path, listTruncated: view.listTruncated };
  }
  return jumpToEntry(view, entry, path);
}

/**
 * Go to the first section that names *path*, the Diff summary's in-place jump. A patch can
 * list a path more than once, as a file that became a symlink or a commit series that
 * touches a file twice, and the summary shows such a path as one row, which goes to where it
 * first appears. Where a path appears once, this is `jumpToFile`.
 *
 * @param {MountedDiffState} view
 * @param {string} path
 * @returns {FileJump}
 */
export function jumpToFirstFile(view, path) {
  if (view.disposed) {
    return { kind: "disposed", path };
  }
  for (const section of view.sections) {
    const entry = view.bySection.get(section);
    const oldSide = /** @type {{path?: string} | null | undefined} */ (entry?.change.old);
    const newSide = /** @type {{path?: string} | null | undefined} */ (entry?.change.new);
    if (entry !== undefined && (newSide?.path === path || oldSide?.path === path)) {
      return jumpToEntry(view, entry, path);
    }
  }
  return { kind: "not_in_comparison", path, listTruncated: view.listTruncated };
}

/**
 * Put one file at the top of the pane, and ask for its lines first.
 *
 * @param {MountedDiffState} view
 * @param {FileEntry} entry
 * @param {string} path
 * @returns {FileJump}
 */
function jumpToEntry(view, entry, path) {
  entry.expand();
  view.pinned = entry.section;
  view.pinnedAt = eventClockNow();
  placeAtTop(view, entry.section);
  view.notifyCurrentFile();
  const pane = scrollerOf(view);
  if (pane !== null) {
    releasePinOnInput(view, pane);
  }
  const fileId = String(entry.change.id);
  // A file whose rendered view hides its body has no rows to draw for the jump.
  const lines = bodyWanted(view, fileId) ? view.hydration.jump(fileId) : null;
  const availability = String(entry.change.availability);
  return {
    kind: "jumped",
    fileId,
    path,
    availability,
    lines:
      lines ?? Promise.resolve(entry.section.querySelector?.(".diff-hunk") ? "painted" : "none"),
  };
}

/**
 * Keep a file findable by either of its paths. A path a file has now wins over a path another
 * had: a copy's source can be a file changed in its own right.
 *
 * @param {MountedDiffState} view
 * @param {Record<string, unknown>} change
 * @param {HTMLElement} section
 * @param {() => void} expand
 */
function rememberFile(view, change, section, expand) {
  const entry = { change, section, expand };
  view.sections.push(section);
  view.bySection.set(section, entry);
  const oldSide = /** @type {{path?: string} | undefined | null} */ (change.old);
  const newSide = /** @type {{path?: string} | undefined | null} */ (change.new);
  if (newSide?.path !== undefined && !view.byNewPath.has(newSide.path)) {
    view.byNewPath.set(newSide.path, entry);
  }
  if (oldSide?.path !== undefined && !view.byOldPath.has(oldSide.path)) {
    view.byOldPath.set(oldSide.path, entry);
  }
}

/**
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown> | undefined} patch
 * @param {{revision?: string}} context
 * @param {MountedDiffState} view
 * @param {boolean} draw Whether a ready file's rows are drawn now. One past the first screen
 *   is held, with its answer, until it is reached, and so is one with a rendered view,
 *   wherever it is, until its Source is shown and reached (`bodyWanted`).
 * @returns {HTMLElement}
 */
function renderFileSection(change, patch, context, view, draw) {
  const section = el("section", "diff-file");
  const body = el("div", "diff-file-body");
  // The card's bar and trigger, and the state they keep, are the shared disclosure's.
  const disclosure = fileDisclosure(section, body, (expanded) => {
    markdown?.setExpanded(expanded);
    view.notifyCurrentFile();
  });
  const { bar } = disclosure;
  const factsId = `${body.id}-facts`;
  const { end, notice } = renderFileBar(change, disclosure, factsId, view);
  if (notice) {
    section.append(bar, notice, body);
  } else {
    section.append(bar, body);
  }

  const format = view.markdown?.format(change) ?? null;
  const availability = String(change.availability);
  const markdown =
    format === null
      ? null
      : view.markdown?.controller.add({
          section,
          bar,
          end,
          source: body,
          id: String(change.id),
          format,
          gone: String(change.kind) === "deleted",
          onSource: () => bodyShownChanged(view, String(change.id)),
          // A file whose changes did not load has no Rendered either, for the reason its
          // body gives below.
          ...(availability === "ready" || availability === "deferred"
            ? {}
            : { unavailable: AVAILABILITY_COPY[availability] || UNAVAILABLE_COPY }),
        });
  rememberFile(view, change, section, () => {
    if (!disclosure.expanded()) {
      disclosure.setExpanded(true);
    }
  });

  if (availability === "deferred" && context.revision) {
    queueDeferredHydration(section, body, change, context.revision, view);
    return section;
  }
  if (availability !== "ready" || patch === undefined) {
    const copy = AVAILABILITY_COPY[availability] || UNAVAILABLE_COPY;
    body.append(el("div", "diff-availability", copy));
    if (availability === "binary") {
      appendPdfCard(view, change, body);
    }
    return section;
  }
  const hunks = /** @type {Record<string, unknown>[]} */ (patch.hunks);
  if (hunks.length === 0 && !view.canShowFull) {
    // A hydrated patch with no hunks is a metadata-only change (a chmod,
    // a pure rename): the bar already says everything it changes.
    body.append(el("div", "diff-availability", "No content changes."));
    return section;
  }
  if (!draw || markdown !== null) {
    const id = String(change.id);
    const held = { manifest: { files: [change] }, patches: { [id]: patch } };
    queueDeferredHydration(section, body, change, context.revision ?? "", view, held);
    return section;
  }
  const state = createFileState(
    change,
    patch,
    view.api ?? plainSyntaxApi(),
    body,
    view.unfold,
    gapSourceOf(view, context.revision),
  );
  state.fullSource = fullSourceOf(view, state.gaps, change);
  view.files.push(state);
  if (!view.awaitingWidth) {
    renderFileBody(state, projectionOf(view));
  }
  scheduleFileEnhancement(view, state);
  return section;
}

/**
 * The rows a file's body takes or holds a place for, in *layout*, by the same rules that draw
 * or reserve it: a ready file's own patch, a deferred file's estimate, and one row for a
 * sentence. Pure.
 *
 * @param {Record<string, unknown>} change
 * @param {Record<string, unknown> | undefined} patch
 * @param {{revision?: string}} context
 * @param {Projection} layout
 */
function bodyRows(change, patch, context, layout) {
  const availability = String(change.availability);
  if (availability === "deferred" && context.revision) {
    return reservedRows(change, layout);
  }
  if (availability === "ready" && patch !== undefined) {
    return Math.max(1, patchRows(patch, layout, change));
  }
  return 1;
}

/**
 * Two empty files of one row each, for measuring what a bar and a row take before anything is
 * drawn. The root holds them for the measurement alone.
 */
function screenProbe() {
  const probe = el("section", "diff-file");
  const row = el("div", "diff-line");
  row.append(el("span", "diff-line-number", "0"));
  const body = el("div", "diff-file-body");
  body.append(row);
  probe.append(el("div", "diff-file-bar"), body);
  return { probe, row };
}

/**
 * The first screen's geometry, read while the root and its probes are laid out for the width
 * and before anything else changes, so it is the same layout and not another. Null where
 * nothing is laid out, as in a container with no box or without a browser.
 *
 * @param {HTMLElement} root
 * @param {ReturnType<typeof screenProbe>[]} probes Two, one after the other.
 * @returns {ScreenGeometry | null}
 */
function measureScreen(root, probes) {
  const owner = root.ownerDocument;
  const pane = /** @type {HTMLElement | null} */ (
    root.closest?.("[data-kpress-viewport]") ?? owner?.scrollingElement ?? null
  );
  const [first, second] = probes;
  if (pane === null || typeof first.probe.getBoundingClientRect !== "function") {
    return null;
  }
  const paneHeight = Number(pane.clientHeight);
  // The document's own scroller's box moves with its scroll; what it shows starts at 0.
  const paneTop = pane === owner?.scrollingElement ? 0 : pane.getBoundingClientRect().top;
  const top = first.probe.getBoundingClientRect().top;
  const rowPx = first.row.getBoundingClientRect().height;
  const barPx = second.probe.getBoundingClientRect().top - top - rowPx;
  if (!(paneHeight > 0) || !(rowPx > 0) || !(barPx > 0) || !Number.isFinite(top)) {
    return null;
  }
  return { paneHeight, rootTop: top - paneTop, barPx, rowPx };
}

/**
 * The width and text size a diff has in *container*, from the root's own box, which is what
 * every later report measures: a container's `clientWidth` also holds its padding. And, from
 * the same layout, the geometry its first screen is drawn by. The root is back out before
 * anything can paint.
 *
 * @param {HTMLElement} root
 * @param {HTMLElement} container
 */
function measureInContainer(root, container) {
  const probes = [screenProbe(), screenProbe()];
  root.append(...probes.map(({ probe }) => probe));
  container.append(root);
  const width = root.getBoundingClientRect?.().width ?? 0;
  const fontSize = fontSizeOf(root);
  const screen = width > 0 ? measureScreen(root, probes) : null;
  for (const { probe } of probes) {
    probe.remove();
  }
  root.remove();
  return { width, fontSize, screen };
}

/**
 * A change set's Diff summary on its own, for a page that keeps it at its top while its diff
 * comes and goes, as a pull request's page does on every tab (mb-pb35). The header and its
 * tree are the diff's own (`renderDiffSummary`), from the document's manifest, which is all
 * it reads; a file it opens goes to *openFile*.
 *
 * @param {HTMLElement} slot Where the summary is drawn; its children are replaced.
 * @param {{manifest: unknown}} document_ A ChangeSetDocument whose manifest is validated
 *   (`validateManifest`).
 * @param {DiffViewApi | undefined} api
 * @param {{changedFiles: MetabrowserChangedFilesTree | null, openFile: (path: string) => void}} options
 * @returns {{dispose: () => void}}
 */
export function mountDiffSummary(slot, document_, api, options) {
  const manifest =
    /** @type {{files: Record<string, unknown>[], totals: Record<string, unknown>}} */ (
      document_.manifest
    );
  /** @type {SummaryOwner} */
  const owner = {
    api,
    disposed: false,
    changedFiles: options.changedFiles,
    jump: options.openFile,
    // The page's header says the file count on its size line, above the summary.
    countsFiles: false,
  };
  const summary = summaryOrTotals(manifest.totals, manifest.files, owner);
  slot.replaceChildren(summary.element);
  return {
    dispose() {
      owner.disposed = true;
      summary.dispose();
    },
  };
}

/**
 * Mount a validated ChangeSetDocument.
 *
 * @param {HTMLElement} container
 * @param {Record<string, unknown>} document_
 * @param {DiffViewApi} [api]
 * @param {{
 *   showSummary?: boolean,
 *   summaryHost?: HTMLElement | null,
 *   summaryTotals?: unknown,
 *   viewFile?: import("./diff-view-file.js").ViewFileOpenerFactory | null,
 *   renderMarkdown?: (
 *     fileId: string,
 *     signal: AbortSignal,
 *     ask?: import("./diff-markdown.js").RenderedAsk,
 *   ) => Promise<unknown>,
 *   markdownViews?: Pick<typeof import("./diff-markdown.js"), "createMarkdownViews" | "renderedFormat">,
 *   markdownTargets?: (value: string, image: boolean, links?: MetabrowserRepositoryLinksRuntime | null) => string | null,
 *   markdownHoldMs?: number,
 *   changedFiles?: MetabrowserChangedFilesTree | null,
 *   openFile?: (path: string) => void,
 *   summaryManifest?: Record<string, unknown> | null,
 *   toolbarControl?: HTMLElement | null,
 *   emptyText?: string,
 *   unfold?: boolean,
 *   layout?: "unified",
 *   show?: Shown,
 *   showPreference?: string,
 *   presentation?: MountedDiffState["presentation"],
 *   embedded?: boolean
 * }} [options]
 *   *viewFile* makes the opener for a page that can open a file at a commit; without it
 *   the bars carry no View file control. The plugin imports diff-view-file.js for such a
 *   page alone, so this module names it only in types.
 *   *markdownHoldMs* is how long the first screen's Markdown files wait for Rendered
 *   (`createMarkdownViews`'s *holdMs*); `firstScreen` settles when none of them waits.
 *   *changedFiles* is the shell's changed-files tree the Diff summary is drawn on; without
 *   it a multi-file diff has no summary. *openFile* is the host's way to a changed file's own
 *   address, which the summary's file rows take where the host has one. *summaryHost* is
 *   where a page that places the summary at its own top wants it drawn (mb-pb35).
 *   *summaryTotals* are the change set's whole totals, which its summary says where the list
 *   is cut short at its bound, as a commit's page knows them (A3 of review A on #470).
 *   A diff narrowed to some file types (diff-type-filter.js) passes the whole comparison's
 *   manifest as *summaryManifest*, so its summary still describes the whole change set; its
 *   File type control as *toolbarControl*, which leads the toolbar's end group of choosers; and *emptyText*,
 *   what it says when it keeps no file. *unfold* draws the text diff's long changed runs
 *   open and opens a rendered Markdown file in Full where it is small enough to draw whole
 *   (`createMarkdownViews`' *opens*), for a page that shows its files whole: a pull
 *   request's Docs tab. *layout* fixes the layout at
 *   Unified, which the diff then draws with no layout control and no `L`, neither reading
 *   nor writing the reader's stored choice: a pull request's Docs tab, whose rendered
 *   documents take that form. Split is the reader's to choose, so no host fixes it. *show*
 *   is what the toolbar's Diff | Current opens on before the reader chooses on this
 *   surface, Diff unless the host says Current, and *showPreference* the preference the
 *   choice is remembered as, `diff.show` unless the host keeps its own; a stored value that
 *   is not a choice reads as *show*. A pull request's Docs tab opens on Current and
 *   remembers its choice as `github.docs.show`, so neither its choice nor Changes' moves
 *   the other.
 * @returns {{scrollToFile: (path: string) => FileJump, fileForPath: (path: string) => FileLookup, sectionForPath: (path: string) => HTMLElement | null, pathForSection: (section: Element) => string | null, currentFile: () => Extract<FileLookup, {kind: "file"}> | null, onCurrentFile: (listener: (file: Extract<FileLookup, {kind: "file"}> | null) => void) => () => void, firstScreen: () => Promise<void>, cancelPending: () => void, show: (mode: Shown) => void, dispose: () => void}}
 */
export function mountDiffView(container, document_, api, options = {}) {
  const root = el("div", "diff-root");
  const fixedLayout = options.layout === "unified" ? options.layout : null;
  const presentation = options.presentation ?? {};
  const chosenLayout = fixedLayout ?? presentation.layout ?? readLayoutPreference(api);
  const showPreference =
    typeof options.showPreference === "string" && options.showPreference !== ""
      ? options.showPreference
      : "diff.show";
  // Measured before the first draw, so a narrow pane never draws Split to throw it away. A
  // container that is not laid out yet has no width, as a commit's stage has none until it
  // is placed, so nothing is drawn until its first report decides.
  const canShowFull = typeof document_.__revision === "string" && document_.__revision !== "";
  const preferred = readShowPreference(api, showPreference, options.show ?? "diff");
  const { width: mountWidth, fontSize, screen } = measureInContainer(root, container);
  const narrow = opensTooNarrowForSplit(mountWidth, fontSize);
  /** @type {MountedDiffState} */
  const view = {
    api,
    awaitingWidth: !(mountWidth > 0) && typeof ResizeObserver === "function",
    byNewPath: new Map(),
    byOldPath: new Map(),
    bySection: new Map(),
    notifyCurrentFile: () => {},
    chosenLayout,
    controller: new AbortController(),
    deferred: new Map(),
    deferredBySection: new Map(),
    deferredFailed: 0,
    disposed: false,
    files: [],
    generation: 1,
    hydration: /** @type {MountedDiffState["hydration"]} */ (/** @type {unknown} */ (null)),
    hydrationObserver: null,
    reached: new Set(),
    markdown: null,
    insistedOnSplit: false,
    layout: drawnLayout(chosenLayout, narrow, false),
    layoutControl: null,
    layoutGeneration: 0,
    layoutKey: null,
    listTruncated: false,
    narrow,
    hydrationFailure: noticeEl("error", "diff-hydration-failure"),
    pinListeners: null,
    pinned: null,
    pinnedAt: Number.NEGATIVE_INFINITY,
    resolved: /** @type {Record<string, unknown>} */ (document_.resolved ?? {}),
    root,
    enhancementTail: Promise.resolve(),
    sections: [],
    spacer: null,
    timers: new Set(),
    viewFile: null,
    viewFileBusy: null,
    viewFileBars: [],
    yielders: new Set(),
    pdfCards: [],
    changedFiles: options.changedFiles ?? null,
    openFile: options.openFile ?? null,
    unfold: options.unfold === true,
    show: preferred === "full" && !canShowFull ? "current" : preferred,
    canShowFull,
    presentation,
    showPreference,
    showControl: null,
    showKey: null,
  };
  view.hydration = createHydrationScheduler(hydrationHost(view));
  if (
    options.renderMarkdown &&
    options.markdownViews &&
    api?.filterControls &&
    typeof IntersectionObserver === "function"
  ) {
    /** What a rendered file's links open, once loaded with its allowlist. @type {MetabrowserRepositoryLinksRuntime | null} */
    let repositoryLinks = null;
    view.markdown = {
      format: options.markdownViews.renderedFormat,
      controller: options.markdownViews.createMarkdownViews({
        load: options.renderMarkdown,
        controls: api.filterControls,
        isTarget: (value, image) =>
          options.markdownTargets?.(value, image, repositoryLinks) ?? null,
        ...(options.markdownHoldMs === undefined ? {} : { holdMs: options.markdownHoldMs }),
        opens: options.unfold === true ? "prefer-full" : "concise",
        show: view.show,
        async ensureInert() {
          await api?.ensureAsset?.("inert-html");
          return window.MetabrowserInertHtml;
        },
        async prepareLinks() {
          // A later projection can use a bundle that missed the first draw's deadline.
          repositoryLinks = (await api?.loadRepositoryLinks?.()) ?? null;
        },
        // A rendered file's link into the repository opens its page here, a pull request or
        // a commit, which names no revision (static/repository-links.js); a `/view/` target
        // would open whatever the server serves once the pin moves, so it stays a link to
        // github.com, marked as an outside link is everywhere else.
        enhanceLinks(prose) {
          const navigation = api?.navigation;
          const sourceKind = api?.sourceKind;
          if (repositoryLinks && navigation && sourceKind && api?.repository) {
            repositoryLinks.enhance(
              prose,
              { navigation, repository: api.repository, sourceKind },
              { views: false },
            );
          }
          for (const link of prose.querySelectorAll('a[target="_blank"]')) {
            api?.decorateExternalLink?.(/** @type {HTMLElement} */ (link));
          }
        },
        // The structured plugin draws a YAML or JSON file's tree, as in the file view
        // (`requires` in manifest.toml).
        async ensureStructured() {
          return api?.plugins?.load("structured");
        },
        loadStyles: (assets) => api?.loadKpressAssets?.(assets) ?? Promise.resolve(),
        mutate(change) {
          const anchor = view.pinned === null ? placeOfTopRendered(view) : null;
          change();
          holdPlace(view, anchor);
          view.notifyCurrentFile();
        },
      }),
    };
  }
  if (options.viewFile) {
    view.viewFile = options.viewFile({
      released() {
        view.viewFileBusy?.setAttribute("aria-busy", "false");
        view.viewFileBusy = null;
      },
      // Another tab switched the server's pin: a link opens the same path at that pin now,
      // so each becomes the switch back, and rendered Markdown's links to a file of the head
      // open it on github.com.
      changed() {
        repaintViewFileControls(view);
        view.markdown?.controller.closeHeadLinks();
      },
    });
  }
  const removeSelectionGate = installSplitSelectionGate(root);
  root.dataset.show = view.show;
  if (!view.awaitingWidth) {
    root.dataset.layout = view.layout;
  }
  const manifest =
    /** @type {{files: Record<string, unknown>[], totals: Record<string, unknown>, truncated: unknown, cursor?: unknown}} */ (
      document_.manifest
    );
  const patches = /** @type {Record<string, Record<string, unknown>>} */ (document_.patches);
  view.listTruncated = manifest.truncated === true;
  // A diff narrowed to some file types describes the whole change set in its summary.
  const described = /** @type {typeof manifest} */ (options.summaryManifest ?? manifest);
  const { toolbar, unbind } = options.embedded
    ? { toolbar: el("div", "diff-toolbar"), unbind: () => {} }
    : renderDiffToolbar(
        described.totals,
        described.files,
        view,
        options.showSummary !== false,
        options.summaryHost ?? null,
        wholeTotalsOf(described, options.summaryTotals ?? null),
        options.toolbarControl ?? null,
        fixedLayout === null,
      );
  // A fixed layout leaves the toolbar what else it holds, Diff | Current on a pull request's
  // Docs tab, and a toolbar with nothing in it, as where the chip family is not loaded, is not
  // drawn.
  const drawsToolbar = !options.embedded && (fixedLayout === null || toolbar.children.length > 0);
  if (drawsToolbar) {
    root.append(toolbar);
  }
  // A list cut short at its bounds may have left out what was asked for: the truncation
  // notice below says so, and "none" would not be true.
  if (manifest.files.length === 0 && manifest.truncated !== true && options.emptyText) {
    root.append(el("div", "diff-availability diff-type-empty", options.emptyText));
  }
  // What the source could not model is left out of the files below, so it is said above them.
  for (const warning of /** @type {string[]} */ (view.resolved.warnings ?? [])) {
    root.append(noticeEl("warning", "diff-warning", warning));
  }
  const context = { revision: String(document_.__revision ?? "") };
  view.hydrationFailure.hidden = true;
  root.append(view.hydrationFailure);
  // Rows are drawn for the files whose estimated top is within the first screen and one more;
  // every later ready file is held, with its answer, and drawn when it is reached, as is
  // every file with a rendered view, whose Source waits until it shows (`bodyWanted`). The bars
  // are all here, and each held file reserves its code rows and chrome before drawing.
  // Soft wraps and arriving scrollbars can add height. Drawing every hydrated file at
  // once was one task of style, layout and commit
  // proportional to the rows: 1,083 ms at 114,609 nodes on a 1,031-file comparison (review
  // of #284, E1). The toolbar, where there is one, is counted as about a bar.
  const budget = firstScreenBudget(screen);
  let estimatedTop = drawsToolbar ? (screen?.barPx ?? 0) : 0;
  measureProjection(
    api,
    "diffMount:projection",
    () => {
      for (const change of manifest.files) {
        const patch = patches[String(change.id)];
        const draw = estimatedTop < budget;
        root.append(renderFileSection(change, patch, context, view, draw));
        if (screen !== null) {
          estimatedTop +=
            screen.barPx + bodyRows(change, patch, context, projectionOf(view)) * screen.rowPx;
        }
      }
      if (manifest.truncated) {
        root.append(noticeEl("warning", "", "The change list is too long to show in full."));
      }
      view.spacer = el("div", "diff-end-spacer");
      root.append(view.spacer);
    },
    { file_count: manifest.files.length },
  );
  measureProjection(api, "diffMount:attach", () => container.append(root), {
    file_count: manifest.files.length,
  });
  observeHydration(view);
  if (view.markdown !== null) {
    const pane = scrollerOf(view);
    const observerRoot = pane === view.root.ownerDocument?.scrollingElement ? null : pane;
    view.markdown.controller.observe(view.root, observerRoot);
  }
  // Drawing changes the root's height, which this also reports, so it waits for a task of its
  // own: done in the callback, it would be a ResizeObserver loop error. A width is one frame
  // late at the moment it crosses the limit, and the first draw above is not late at all.
  /** @type {number | null} */
  let observedWidth = null;
  /** @type {ReturnType<typeof setTimeout> | null} */
  let fitTimer = null;
  const widths =
    typeof ResizeObserver === "function"
      ? new ResizeObserver((entries) => {
          // Before this frame paints: a height that changed does not show a place that moved.
          holdPlace(view);
          view.notifyCurrentFile();
          const width = entries.at(-1)?.contentRect.width ?? 0;
          if (width === observedWidth) {
            return;
          }
          observedWidth = width;
          if (view.awaitingWidth) {
            if (width > 0) {
              drawAtFirstWidth(width);
            }
            return;
          }
          if (fitTimer !== null) {
            clearTimeout(fitTimer);
            view.timers.delete(/** @type {number} */ (fitTimer));
          }
          const timer = setTimeout(() => {
            view.timers.delete(timer);
            fitTimer = null;
            fitLayout(view, width);
          }, 0);
          fitTimer = timer;
          view.timers.add(timer);
        })
      : null;
  widths?.observe(root);

  /**
   * The first report of a container that had no width at mount. Drawn in the report itself,
   * which the browser makes before it paints, so the diff arrives whole and in one layout.
   * The root is watched again from the next task: the height this changes would otherwise
   * be a ResizeObserver loop error.
   *
   * @param {number} width
   */
  function drawAtFirstWidth(width) {
    view.narrow = opensTooNarrowForSplit(width, fontSizeOf(root));
    widths?.unobserve(root);
    drawLayout(view, drawnLayout(view.chosenLayout, view.narrow, false));
    const timer = setTimeout(() => {
      view.timers.delete(timer);
      widths?.observe(root);
    }, 0);
    view.timers.add(timer);
  }

  /**
   * The first file whose bar or body intersects the pane, including undrawn files.
   * Reuses the ordered-section bisection: a scroll never measures every file.
   * @returns {Extract<FileLookup, {kind: "file"}> | null}
   */
  function currentFile() {
    if (view.disposed) {
      return null;
    }
    const pane = scrollerOf(view);
    const place = placeOfTopFile(view);
    if (pane === null || place === null) {
      return null;
    }
    const bounds = pane.getBoundingClientRect();
    const rect = place.section.getBoundingClientRect();
    if (rect.bottom <= bounds.top || rect.top >= bounds.top + pane.clientHeight) {
      return null;
    }
    const entry = view.bySection.get(place.section);
    if (entry === undefined) {
      return null;
    }
    const side = /** @type {{path?: string}} */ (entry.change.new ?? entry.change.old);
    const path = String(side.path ?? "");
    return {
      kind: "file",
      path,
      fileId: String(entry.change.id),
      changeKind: String(entry.change.kind),
      availability: String(entry.change.availability),
    };
  }
  /** @type {Map<(file: Extract<FileLookup, {kind: "file"}> | null) => void, string | null>} */
  const currentListeners = new Map();
  const currentController = new AbortController();
  /** @type {number | null} */
  let currentFrame = null;
  view.notifyCurrentFile = () => {
    if (view.disposed || currentListeners.size === 0 || currentFrame !== null) {
      return;
    }
    const report = () => {
      currentFrame = null;
      if (view.disposed) {
        return;
      }
      const file = currentFile();
      const id = file?.fileId ?? null;
      for (const [listener, previous] of currentListeners) {
        if (previous !== id) {
          currentListeners.set(listener, id);
          listener(file);
        }
      }
    };
    currentFrame =
      typeof requestAnimationFrame === "function"
        ? requestAnimationFrame(report)
        : setTimeout(report, 0);
  };
  scrollerOf(view)?.addEventListener("scroll", view.notifyCurrentFile, {
    passive: true,
    signal: currentController.signal,
  });

  function cancelPendingWork() {
    view.generation += 1;
    view.controller.abort();
    view.hydrationObserver?.disconnect();
    view.hydrationObserver = null;
    view.hydration.dispose();
    view.markdown?.controller.dispose();
    view.deferred.clear();
    view.deferredBySection.clear();
    view.pinListeners?.abort();
    view.pinListeners = null;
    view.pinned = null;
    for (const file of view.files) {
      cancelFoldMaterializations(file);
    }
    for (const timer of view.timers) {
      clearTimeout(timer);
    }
    view.timers.clear();
    for (const waiter of view.yielders) {
      clearTimeout(waiter.timer);
      waiter.resolve(false);
    }
    view.yielders.clear();
  }
  return {
    /**
     * Go to the file a path names: see `FileJump`, and
     * docs/project/architecture/arch-diff-pipeline.md, "Hydration", for what it promises.
     *
     * @param {string} path
     */
    scrollToFile: (path) => jumpToFile(view, path),
    show: (mode) => setShow(view, mode, false),
    /**
     * Whether this comparison holds a path, for a list of files from elsewhere: see
     * `FileLookup`.
     *
     * @param {string} path
     */
    fileForPath: (path) => lookupFile(view, path),
    /**
     * The section of the file a path names, or null, and the path a file's section is
     * known by: for a host that keeps a reader's place by its file across two comparisons.
     *
     * @param {string} path
     */
    sectionForPath: (path) =>
      view.disposed ? null : (fileEntryForPath(view, path)?.section ?? null),
    /** @param {Element} section */
    pathForSection(section) {
      // A disposed view says nothing of its files, as `sectionForPath` does not.
      const entry = view.disposed
        ? undefined
        : view.bySection.get(/** @type {HTMLElement} */ (section));
      if (entry === undefined) {
        return null;
      }
      const side = /** @type {{path?: string}} */ (entry.change.new ?? entry.change.old);
      return typeof side.path === "string" ? side.path : null;
    },
    currentFile,
    /** Settles when the first screen's Markdown files no longer wait to be drawn. */
    firstScreen: () => view.markdown?.controller.firstScreen ?? Promise.resolve(),
    /** Report immediately, then only when the file changes; unsubscribe is idempotent. */
    onCurrentFile(listener) {
      if (view.disposed) {
        return () => {};
      }
      const file = currentFile();
      currentListeners.set(listener, file?.fileId ?? null);
      listener(file);
      return () => {
        currentListeners.delete(listener);
      };
    },
    cancelPending() {
      if (!view.disposed) {
        cancelPendingWork();
      }
    },
    dispose() {
      if (view.disposed) {
        return;
      }
      view.disposed = true;
      widths?.disconnect();
      currentController.abort();
      currentListeners.clear();
      if (currentFrame !== null) {
        if (typeof cancelAnimationFrame === "function") {
          cancelAnimationFrame(currentFrame);
        } else {
          clearTimeout(currentFrame);
        }
        currentFrame = null;
      }
      cancelPendingWork();
      view.viewFile?.dispose();
      for (const card of view.pdfCards.splice(0)) {
        card.dispose();
      }
      view.layoutKey?.detach();
      view.layoutKey = null;
      view.showKey?.detach();
      view.showKey = null;
      unbind();
      removeSelectionGate();
      root.remove();
    },
  };
}
