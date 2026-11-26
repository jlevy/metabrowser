// The rendered layer of a comparison whose server names a route for it, as a pull
// request's does: Markdown as rendered blocks, with its front matter as the Document
// view's Frontmatter disclosure, and YAML and JSON as the structured plugin's tree
// (diff-structured.js). Source stays hydrated by the diff's existing scheduler, so a
// refusal or a reader's Source selection has a patch ready. This module names no route:
// the comparison carries the rendered route and the image route its images load from.
//
// Every changed file of a rendered format has a chooser, whatever its size and whatever
// the server answers: a Markdown file's Full | Concise | Source, and a YAML or JSON file's
// Rendered | Source. Full draws every block of the document. Concise draws each change
// with the unchanged blocks beside it and folds the runs between, each fold the diff's own
// expander (diff-fold.js); the server says which runs fold (diff/markdown_views.py). A
// tree has no runs of its own to fold, so it has one rendered view. Where rendering cannot
// be shown the file shows Source, and its rendered chips stay in place, unavailable, and
// say why (`REFUSALS`).
//
// A document is drawn whole within `WHOLE_UNITS` and `WHOLE_BYTES`, so the browser's
// find, Select All, and print reach all of it. A longer one is drawn a chunk at a time,
// near the viewport (`CHUNK_UNITS`): what is not drawn yet keeps an estimated height, so
// the page scrolls as the whole document would, and is drawn as the reader comes near it,
// follows a link into it, or prints; find and Select All reach only what is drawn.

import { foldExpander } from "./diff-fold.js";
import { isStructuredProjection, mountStructuredDiff } from "./diff-structured.js";

// The formats a changed file renders as, by its extension, as the server's route admits
// them (github/pull_rendered_diff.py), each with the name its chooser and progress use.
// An extension follows at least one character of its name, as Python's `Path.suffix`
// reads it, so a dotfile named `.json` has none.
/** @type {ReadonlyArray<[RegExp, RenderedFormat, string]>} */
const FORMATS = [
  [/[^/]\.(?:md|markdown|mdown|mkd)$/i, "markdown", "Markdown"],
  [/[^/]\.ya?ml$/i, "yaml", "YAML"],
  [/[^/]\.json$/i, "json", "JSON"],
];
// How far below the viewport a projection is requested: one viewport. A projection
// answers in 12 ms at the median and 31-33 ms at p90 of server CPU (434 real pairs), plus
// the round trip, and one `git diff` serves sixteen files. In headless Chrome, the
// production client against a simulated one-slot server (420 px files in a 900 px pane;
// earlier client in adjacent runs): at 3,000 px/s and 70 ms answers only the first
// screen's 3 of 60 files swapped from Source to Rendered in view, as before; at
// 10,000 px/s, 10-11 of 100 swapped against 51, and none was left in Source by a refusal
// against 32; at 10,000 px/s and 35 ms answers, 3 swapped against 96.
const LOOKAHEAD = "100%";
// The blocks (a closed fold is one), and their HTML bytes, a rendered file may hold and
// still be drawn whole; past either it is drawn a chunk at a time. Drawing 500 blocks and
// their first layout and paint took about 60 ms in every shape measured, as the comment
// on `FULL_MAX_BLOCKS` in diff/markdown_views.py records, so these are that bound: a
// document the Docs tab opens in Full is drawn whole, as it was before chunks. The page
// counts a block's bytes here, and in CHUNK_BYTES and BYTE_PX, as `html.length`, UTF-16
// code units, where FULL_MAX_BYTES counts UTF-8 bytes; a string never has more code units
// than UTF-8 bytes, so what the Docs tab opens in Full is within WHOLE_BYTES too.
const WHOLE_UNITS = 500;
const WHOLE_BYTES = 512 * 1024;
// How much of a rendered file is drawn at a time: the first chunk with its answer, and
// each next one as the reader comes within LOOKAHEAD of it. A chunk is this many blocks
// (a closed fold is one) or this many bytes of their HTML, whichever comes first. Drawing
// blocks grows with their count: measured 2026-11-24 in headless Chrome 152 at 1,280 x 900
// on an Apple M1 Pro at a load average of 130 to 195, `appendBlocks` and `sanitizeBlock`
// and their first layout and paint took 59-62 ms for 500 short blocks and 96-100 ms for
// 1,000 (about 0.08 ms a block over 22 ms), and 48-53 ms for 200 paragraphs of 2.3 KB
// (468 KB), so a chunk of 100 blocks or 128 KiB costs about 30 ms. In the page, at a load
// average of 270 to 330, reaching finterm-ai/investment-research #31's 3,408-block book
// took a worst task of 62-64 ms on Docs (351-352 ms drawn whole) and none over 50 ms on
// Changes (361-437 ms), and scrolling it at 400 px a frame for 6 s drew a chunk at a time
// with no frame over 50 ms. Smaller or larger chunks were not measured.
const CHUNK_UNITS = 100;
const CHUNK_BYTES = 128 * 1024;
// The height a chunk not drawn yet keeps: BLOCK_PX for each block and BYTE_PX for each
// byte of its HTML, and FOLD_PX for a closed fold. Fitted 2026-11-24 in headless Chrome 152
// at 1,280 x 900 to the 3,449 blocks of #31's rendered Markdown files drawn whole, each
// block's top to the next block's: a chunk of 100 blocks so estimated came to 0.90-1.03 of
// its drawn height (median 1.00), where 37 px and 0.32 px had estimated 1.26-1.53. Lists
// and tables draw 13-22% taller than estimated, and paragraphs as estimated. A closed fold's bar
// is 24 px and its top was 24-56 px above the next block's, by that block's margin, in the
// seven folds of #31 (median 36).
const BLOCK_PX = 20;
const BYTE_PX = 0.24;
const FOLD_PX = 36;
// How many times a fold's blocks, or Full's, are asked again while the server's one
// projection slot is busy, after RETRY_MS doubling to RETRY_MAX_MS: about 3 seconds.
const MORE_TRIES = 5;
// A refused request (429: the server's one projection slot is busy, often with a load
// the reader has already scrolled past) is asked again after this, doubling to the cap.
const RETRY_MS = 100;
const RETRY_MAX_MS = 1600;
// The app's --loading-state-delay: how long `firstScreen` waits for the first screen's
// files, for a page that asks for no other bound (*holdMs*).
const LOADING_DELAY_MS = 50;
// How long, from mount, a file near the first screen waits for its rendered view with
// Source hidden, so that view is the first thing its body shows and never replaces Source
// in view. At this ceiling a file still waiting shows Source and keeps it, as one whose
// request failed does: Rendered stays to choose, its request goes on and its answer is
// kept for that choice, and it is asked for no more by itself, which also ends a busy
// server's retries. Nothing replaces Source afterwards, so nothing moves. A page, or a
// file drawn alone, can set its own (*waitMs*).
// Measured 2026-11-26 in headless Chrome on a pull request's Changes at a load average
// near 25, from the file's mount to its rendered view drawn: 10 to 97 ms (median 17,
// n 12); the page's own hold measured 29 to 170 ms (CHANGES_FIRST_SCREEN_MS in
// github/pull-page.js). This is ten times the longest of those, so a rendering that is
// merely slow still lands as the first thing shown, and short enough that files which
// need nothing from the server are not kept out of sight behind one that will not come:
// a Markdown child started cold has taken 0.57 to 6.8 s (markdown_projection_worker.py),
// and past this such a file shows Source.
export const RENDERED_WAIT_MS = 2000;
// A file's section while it waits so. styles.css keeps everything after it in the diff
// out of sight meanwhile, so its body arriving moves nothing a reader sees. Shown at the
// wait's bound with Source, as it was, a file's card grew from 75 to 118 px when its
// answer came and every card below moved 43 px, under a press already aimed (review A of
// #872, A1; mb-ne65). Measured 2026-11-26 in headless Chrome on a pull request's Changes
// with the rendered answer held 1.5 s: the page showed at 271 ms with the waiting file's
// bar alone, 31 px, and the file after it out of sight; at 1,657 ms the body drew, 118 px,
// and the file after it first showed, at the top it keeps.
// tests/dom/diff-file-bar-chrome.mjs holds the rule under the real stylesheet.
export const WAITING_CLASS = "diff-file-awaiting-rendered";
// Why a file's rendered views are unavailable, by the `reason` the server's refusal names
// (`MarkdownRefusal` in diff/markdown_projection.py, `StructuredRefusal` in
// diff/structured_projection.py) and, where it names none, by its `status`. Each is the
// tooltip of the file's rendered chips (Full and Concise, or a tree's Rendered) and the end
// of their accessible names.
/** @type {Readonly<Record<string, string>>} */
const REFUSALS = {
  no_changes: "This file's content did not change.",
  nesting: "This file is nested too deeply to show rendered.",
  deadline: "Rendering this file took too long, so it was stopped. Reload the page to try again.",
  too_large: "This file is too large to show rendered.",
};
// A refusal that names no reason: a file the projection could not read as its format.
/** @type {Readonly<Record<RenderedFormat, string>>} */
const UNREADABLE = {
  markdown: "This file's changes cannot be matched to its rendered Markdown.",
  yaml: "Rendered cannot show YAML that does not parse, or has a key twice in one mapping.",
  json: "Rendered cannot show JSON that does not parse.",
};

/** @typedef {Parameters<MetabrowserPublicSdk["loadKpressAssets"]>[0]} KpressAssetManifest */
/** @typedef {"markdown" | "yaml" | "json"} RenderedFormat */
/** @typedef {import("./diff-structured.js").TreeHelpers} TreeHelpers */
/** @typedef {{key: string, change: "context" | "removed" | "added", text: string}} FrontmatterEntry */
/** @typedef {{change: "context" | "modified" | "removed" | "added", entries: FrontmatterEntry[]}} Frontmatter */
/** @typedef {"full" | "concise"} View */
/** @typedef {"rendered" | "source"} Mode */
/** @typedef {{view?: View | "prefer-full", blocks?: string}} RenderedAsk What a request asks of the route. */
/** @typedef {{kind: "context" | "removed" | "added", html: string, source_only?: boolean}} Block */
/** @typedef {{at: number, count: number, lines: number, withheld?: true, ids?: string[]}} Fold
 *   *count* unchanged blocks from *at* that Concise folds, spanning *lines* of source; a
 *   withheld one's blocks are not in a Concise answer, and *ids* are its headings' anchors. */
/** @typedef {{blocks: (Block | undefined)[], folds: Fold[], frontmatter?: Frontmatter}} Model
 *   A Markdown file's projection as far as the page holds it. */
/** @typedef {{kind: "block", index: number} | {kind: "fold", fold: Fold}} Unit */
/** @typedef {{units: Unit[], start: number, end: number, spacer: HTMLElement | null}} Chunk
 *   *spacer* holds the chunk's place until it is drawn. */
/** @typedef {{file: FileView, top: boolean, chunks: Chunk[]}} Region */
/** @typedef {{fold: Fold, expander: import("./diff-fold.js").FoldExpander, region: Region | null, status: {failed: boolean}}} FoldView
 *   *failed* is a withheld fold whose blocks did not load, which its bar says until it
 *   opens again. */
/** @typedef {{
 *   section: HTMLElement, source: HTMLElement, rendered: HTMLElement,
 *   progress: HTMLElement, progressLabel: HTMLElement,
 *   control: HTMLElement, expand: HTMLButtonElement, fallback: HTMLElement, fallbackMessage: HTMLElement,
 *   id: string, format: RenderedFormat, mode: Mode, pending: boolean,
 *   expandedContext: boolean, forceFull: boolean, automaticView: View | null, fullFailed: boolean,
 *   expanded: boolean, holding: boolean,
 *   tree: ReturnType<typeof mountStructuredDiff> | null,
 *   retryAt: number, retries: number,
 *   model: Model | null, build: ((html: string) => Node) | null,
 *   drawn: View | null, top: Region | null,
 *   foldViews: Map<number, FoldView>, openFolds: Set<number>,
 *   folding: Map<string, Promise<void>>, asking: Set<AbortController>, upgrading: boolean,
 *   fetching: number,
 *   removed: HTMLElement[], gone: boolean, emptied: boolean,
 *   state: "idle" | "ready" | "unavailable", reason: string,
 *   onSource: ((shown: boolean) => void) | null
 * }} FileView
 *   *drawn* is the view the article draws, and *top* its own run of rows. *openFolds* are the
 *   folds open, by their first block, kept when the view is drawn again.
 *   *reason* is why rendering is unavailable, a sentence, while *state* says it is.
 *   *fetching* counts the requests for more of the projection in flight (`askMore`): a
 *   withheld fold's blocks, or Full's.
 *   *removed* is what a Markdown file's rendered view draws that Current leaves out: its removed
 *   blocks and front matter keys (`removedParts`). *gone* is a deleted file, which has no
 *   current version: in Current it shows its Source body, which says so. *emptied* is a file
 *   whose rendered view is all removed, a file left empty: Current has nothing of it to draw, so it
 *   shows its Source body too, which says it is empty now (`currentAbsence` in diff-view.js). */

/**
 * The format a changed file renders as, when both its sides are files of one rendered
 * format: the files that have a view chooser. Nothing else decides it,
 * neither a file's size nor whether its changes loaded. File kinds are admitted here,
 * and source comparisons, rendering and repository reads stay with their existing owners.
 * @param {Record<string, unknown>} change
 * @returns {RenderedFormat | null}
 */
export function renderedFormat(change) {
  /** @type {Set<RenderedFormat | null>} */
  const formats = new Set();
  for (const side of [change.old, change.new]) {
    if (side == null) {
      continue;
    }
    const entry = /** @type {{entry_type?: unknown, path?: unknown}} */ (side);
    const path = typeof entry.path === "string" ? entry.path : "";
    formats.add(
      entry.entry_type === "file"
        ? (FORMATS.find(([pattern]) => pattern.test(path))?.[1] ?? null)
        : null,
    );
  }
  const [only] = formats;
  return formats.size === 1 ? (only ?? null) : null;
}

/**
 * Whether a projection may be asked for a changed file: it has a rendered format, and
 * its changes are ones the server reads a patch for. Any other file of a rendered format
 * keeps its chooser, with its rendered chips unavailable for the reason its Source body
 * gives.
 * @param {Record<string, unknown>} change
 */
export function supportsRenderedChange(change) {
  return (
    renderedFormat(change) !== null &&
    (change.availability === "ready" || change.availability === "deferred")
  );
}

/**
 * Why the server refused a file's projection, as the sentence its rendered chips say.
 * @param {unknown} answer The route's answer, which is not a projection to draw.
 * @param {RenderedFormat} format
 * @returns {string}
 */
export function refusalReason(answer, format) {
  const refusal = /** @type {{status?: unknown, reason?: unknown} | null} */ (
    answer !== null && typeof answer === "object" ? answer : null
  );
  const reason = refusal?.reason;
  if (typeof reason === "string" && Object.hasOwn(REFUSALS, reason)) {
    return REFUSALS[reason];
  }
  return refusal?.status === "too_large" ? REFUSALS.too_large : UNREADABLE[format];
}

// Each chip's name, as the chooser says it (docs/design-system.md, "Choosing Among Values").
/** @type {Readonly<Record<Mode, string>>} */
const MODE_LABELS = { rendered: "Rendered", source: "Source" };

/** @param {Mode} mode */
function isRendered(mode) {
  return mode !== "source";
}

/** @param {RenderedFormat} format */
function formatName(format) {
  return FORMATS.find(([, each]) => each === format)?.[2] ?? "";
}

/** @param {unknown} value @returns {value is Frontmatter} */
function isFrontmatter(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const frontmatter = /** @type {{change?: unknown, entries?: unknown}} */ (value);
  return (
    ["context", "modified", "removed", "added"].includes(String(frontmatter.change)) &&
    Array.isArray(frontmatter.entries) &&
    frontmatter.entries.every(
      (entry) =>
        entry !== null &&
        typeof entry === "object" &&
        typeof entry.key === "string" &&
        typeof entry.text === "string" &&
        ["context", "removed", "added"].includes(entry.change),
    )
  );
}

/**
 * Front matter as the Document view's Frontmatter disclosure shows it (KPress's
 * `kpress-frontmatter`), closed when nothing in it changed, as the Document view's is,
 * and open with each changed key in the change gutter otherwise. Every key and value is
 * text, set as text.
 * @param {Frontmatter} frontmatter
 * @returns {HTMLElement}
 */
export function frontmatterRow(frontmatter) {
  const whole = frontmatter.change === "added" || frontmatter.change === "removed";
  const row = document.createElement("div");
  row.className = `diff-markdown-block diff-markdown-frontmatter diff-markdown-${
    whole ? frontmatter.change : "context"
  }`;
  const details = document.createElement("details");
  details.className = "kpress-frontmatter";
  details.open = frontmatter.change !== "context";
  const heading = document.createElement("summary");
  heading.className = "disclosure-toggle";
  heading.textContent = "Frontmatter";
  const list = document.createElement("dl");
  const added = new Set(
    frontmatter.entries.filter((entry) => entry.change === "added").map((entry) => entry.key),
  );
  for (const entry of frontmatter.entries) {
    const term = document.createElement("dt");
    const value = document.createElement("dd");
    value.textContent = entry.text;
    if (!whole && entry.change !== "context") {
      const label = document.createElement("span");
      label.className = "sr-only";
      label.textContent = entry.change === "added" ? "Added: " : "Removed: ";
      const key = document.createElement("span");
      key.textContent = entry.key;
      term.append(label, key);
      term.className = `diff-frontmatter-${entry.change}`;
      value.className = `diff-frontmatter-${entry.change}`;
    } else {
      term.textContent = entry.key;
    }
    list.append(term, value);
    if (!whole && entry.change === "removed" && !added.has(entry.key)) {
      const removedKey = document.createElement("dt");
      const marker = document.createElement("dd");
      removedKey.textContent = entry.key;
      marker.textContent = "Removed. See Diff.";
      for (const part of [removedKey, marker]) {
        part.className = "diff-frontmatter-removal-marker";
        part.hidden = true;
      }
      list.append(removedKey, marker);
    }
  }
  details.append(heading, list);
  if (whole) {
    const label = document.createElement("span");
    label.className = "sr-only";
    label.textContent = frontmatter.change === "added" ? "Added: " : "Removed: ";
    row.append(label);
  }
  row.append(details);
  return row;
}

// A path in the Git path codec's wire form, and a `/view/` address of one with, at most,
// a fragment, which the server writes into the file's own heading anchors and spells with
// percent escapes.
const GIT_PATH = /^g1-[\w-]+(?:\/g1-[\w-]+)*$/;
const HEAD_LINK = /^\/view\/g1-[\w-]+(?:\/g1-[\w-]+)*(?:#[\w%.~-]+)?$/;

/**
 * Which addresses in a rendered block open something of this comparison, as the server
 * spelled them, before the shared sanitizer, which would drop every local one:
 *
 * - an image, on the comparison's own image route, which the server completes with the
 *   path of an image at the head in the Git path codec's wire form;
 * - a link to a file of the head, at its `/view/` address, only while *linksOpen* says
 *   the page shows that head. Anywhere else the address would open the same path at
 *   another commit, and a link that switched the pin first would let content choose what
 *   the server serves, so the link stays plain text.
 *
 * Every other local address is dropped.
 * @param {string | undefined} imageRoute The comparison's `image_route`, when it names one.
 * @param {() => boolean} linksOpen
 * @returns {(value: string, image: boolean) => boolean}
 */
export function markdownTargets(imageRoute, linksOpen) {
  const images =
    typeof imageRoute === "string" && imageRoute.startsWith("/") && imageRoute.includes("?")
      ? imageRoute
      : null;
  return (value, image) => {
    if (!image) {
      return HEAD_LINK.test(value) && linksOpen();
    }
    if (images === null || !value.startsWith(`${images}&`)) {
      return false;
    }
    const query = new URLSearchParams(value.slice(images.length + 1));
    return [...query.keys()].join() === "path" && GIT_PATH.test(query.get("path") ?? "");
  };
}

// The files a projection is asked for before the reader opens Changes: the rendered files
// among the ones the first screen shows. The page draws files in manifest order, a file
// bar and its first rows take about 420 px, and the server hydrates the first 8 files'
// patches with the comparison, so at most 4 rendered files of the first 8 are asked for.
// Each costs one projection, sent one at a time after the comparison arrives; the server
// waits for its projection process to start before it answers one of these, so none runs
// on the server's interpreter (mb-8274 review C2). A Markdown pair took 12 ms at the
// median and 31-33 ms at p90 of 434 real pairs before front matter was read, and those
// with front matter p50 14.6 and p90 31.4 ms after (811 pairs, review C4); a YAML pair
// 14 ms and 40 ms of 168; a JSON pair under 3 ms at p90, with 5.6-6.5 ms of reads where
// nothing else held the store's reader (review C5, since held for both reads). Review C1
// measured tree first screens holding Changes back longer than Markdown's; re-measuring
// these two and CHANGES_FIRST_SCREEN_MS on them is bead mb-10ip.
const FIRST_SCREEN_FILES = 8;
const FIRST_SCREEN_MARKDOWN = 4;

/**
 * The IDs of the rendered files a page asks projections for ahead of Changes.
 * @param {unknown[]} files A comparison manifest's files, in their order.
 * @returns {string[]}
 */
export function firstScreenRendered(files) {
  return files
    .slice(0, FIRST_SCREEN_FILES)
    .filter(
      (file) =>
        file !== null &&
        typeof file === "object" &&
        typeof (/** @type {{id?: unknown}} */ (file).id) === "string" &&
        supportsRenderedChange(/** @type {Record<string, unknown>} */ (file)),
    )
    .slice(0, FIRST_SCREEN_MARKDOWN)
    .map((file) => String(/** @type {{id: string}} */ (file).id));
}

/** @param {string} value */
function outsideLink(value) {
  if (!/^https?:\/\//i.test(value)) {
    return false;
  }
  try {
    return new URL(value).origin !== window.location.origin;
  } catch {
    return false;
  }
}

/**
 * The shared sanitizer discards reserved application URLs. Preserve only
 * the addresses *isTarget* keeps (`markdownTargets`) through it and discard other local targets
 * before the detached nodes can load any resource.
 * @param {string} html
 * @param {MetabrowserInertHtmlRuntime} inert
 * @param {HTMLTemplateElement} template
 * @param {Document} scratch
 * @param {(value: string, image: boolean) => boolean} isTarget
 */
export function sanitizeBlock(html, inert, template, scratch, isTarget) {
  template.innerHTML = html;
  /** @type {Map<string, string>} */
  const targets = new Map();
  for (const element of template.content.querySelectorAll("a[href], img[src]")) {
    const image = element.tagName === "IMG";
    const attribute = image ? "src" : "href";
    const value = element.getAttribute(attribute) ?? "";
    if (isTarget(value, image)) {
      const marker = `mb-markdown-target-${targets.size}`;
      targets.set(marker, value);
      element.setAttribute(attribute, marker);
    } else if (
      // An image from the web keeps its address: the sanitizer loads it or replaces it
      // as the reader has set. Any other image, and a link that goes nowhere, loses its.
      image
        ? inert.remoteImage(value, null) === null
        : !value.startsWith(`#${inert.ANCHOR_PREFIX}`) && !outsideLink(value)
    ) {
      element.removeAttribute(attribute);
    }
  }
  const prose = inert.kpressProse(
    inert.sanitizeNodes(template.content.childNodes, scratch, null),
    scratch,
  );
  for (const element of prose.querySelectorAll("a[href], img[src]")) {
    const image = element.tagName === "IMG";
    const attribute = image ? "src" : "href";
    const scoped = targets.get(element.getAttribute(attribute) ?? "");
    if (scoped !== undefined) {
      element.setAttribute(attribute, scoped);
    }
  }
  return prose;
}

/**
 * One rendered block's row: its kind and its screen-reader label. A changed row draws no
 * band of its own; the run that holds it does (`changeRuns`). A block whose source says
 * more than its render shows draws nothing to say so: the chooser's Source is how a reader
 * reaches what the rendering does not show.
 * @param {Block} block
 * @param {(html: string) => Node} build
 */
export function blockRow(block, build) {
  const row = document.createElement("div");
  row.className = `diff-markdown-block diff-markdown-${block.kind}`;
  if (block.kind !== "context") {
    const label = document.createElement("span");
    label.className = "sr-only";
    label.textContent = block.kind === "added" ? "Added: " : "Removed: ";
    row.append(label);
  }
  row.append(build(block.html));
  return row;
}

/**
 * The kind of a changed row, `blockRow`'s or `frontmatterRow`'s; null for anything else an
 * article holds: an unchanged row, a fold's bar or group, or a chunk's place.
 * @param {Element} row
 * @returns {"added" | "removed" | null}
 */
function changedKind(row) {
  if (!row.classList.contains("diff-markdown-block")) {
    return null;
  }
  return row.classList.contains("diff-markdown-added")
    ? "added"
    : row.classList.contains("diff-markdown-removed")
      ? "removed"
      : null;
}

/** Whether an element of an article is a change (`changeRuns`). @param {Element} element */
function isChange(element) {
  return element.classList.contains("diff-markdown-change");
}

/**
 * An article's rows as it places them, so that one box draws each band: each run of changed
 * rows is one change (`.diff-markdown-change`), and each run of one kind inside it one run
 * (`.diff-markdown-run`, with `-added` or `-removed`), whose box draws the band, its fill
 * and its change gutter, across its rows and the space between them. Current hides a
 * change's removed runs, and the change then draws one band across the added runs left
 * (styles.css, "A change's band"). A change and a run are plain blocks, with no padding,
 * border, or formatting context, so their rows' margins collapse through them as they
 * would with nothing around them, and no block moves. Unchanged rows, fold bars, and fold
 * groups are placed as they are.
 * @param {HTMLElement[]} rows Rows `blockRow` and `frontmatterRow` built, and fold bars and
 *   groups, in order.
 * @returns {HTMLElement[]}
 */
export function changeRuns(rows) {
  return joinChanges(
    rows.map((row) => {
      const kind = changedKind(row);
      if (kind === null) {
        return row;
      }
      const run = document.createElement("div");
      run.className = `diff-markdown-run diff-markdown-run-${kind}`;
      run.append(row);
      const change = document.createElement("div");
      change.className = "diff-markdown-change";
      change.append(run);
      return change;
    }),
  );
}

/**
 * *elements*, neighbours in this order, with each change that follows a change joined to
 * it: its runs move into the change before it, and its first run's rows into that change's
 * last run when the two are of one kind. Returns the elements that remain. An article is
 * drawn a chunk at a time, so a chunk is joined here to the chunks drawn beside it, and a
 * run that crosses from one chunk into the next is one box.
 * @template {Element} T
 * @param {(T | null)[]} elements
 * @returns {T[]}
 */
export function joinChanges(elements) {
  /** @type {T[]} */
  const kept = [];
  for (const element of elements) {
    if (element === null) {
      continue;
    }
    const before = kept[kept.length - 1];
    if (before === undefined || !isChange(before) || !isChange(element)) {
      kept.push(element);
      continue;
    }
    const runs = [...element.children];
    const end = before.children[before.children.length - 1];
    const [start] = runs;
    if (end !== undefined && start !== undefined && end.className === start.className) {
      end.append(...start.children);
      start.remove();
      runs.shift();
    }
    before.append(...runs);
    element.remove();
  }
  return kept;
}

// KPress's rules that space a block by the block before it in one document: a list or a
// quote continued gives way its margins on both sides, so its items are spaced as inside
// one list, and a paragraph straight under an h4, h5, or h6 has no space above it (`h4 + p`
// to `h6 + p` in KPress's document.css). KPress's `h2 + h3` sets a space of its own, not a
// zero, so it is not carried: an h3 after an h2 keeps its own space above it.
const CONTINUED = new Set(["UL", "OL", "BLOCKQUOTE"]);
const CLOSE_UNDER = new Set(["H4", "H5", "H6"]);

/**
 * How KPress spaces a block that starts with *after* below one that ends with *before*,
 * by tag: whether the later block's start margin gives way, and the earlier's end margin.
 * @param {string | null} before
 * @param {string | null} after
 * @returns {{start: boolean, end: boolean}}
 */
export function joinOf(before, after) {
  if (before !== null && before === after && CONTINUED.has(before)) {
    return { start: true, end: true };
  }
  return { start: after === "P" && before !== null && CLOSE_UNDER.has(before), end: false };
}

/**
 * The tag of a row's block at one edge, the first or the last element its prose holds, or
 * null for a row with no prose, as front matter's.
 * @param {Element} row
 * @param {boolean} last
 * @returns {string | null}
 */
function edgeTag(row, last) {
  for (const child of row.children) {
    if (child.classList.contains("kpress-prose")) {
      const element = child.children[last ? child.children.length - 1 : 0];
      return element === undefined ? null : element.tagName;
    }
  }
  return null;
}

/**
 * The rows an element of an article shows, in order: a row, unless hidden; the rows a
 * change shows in its runs; and null for anything else, a fold's bar or group or a chunk
 * not drawn yet, which stands between the rows on either side of it.
 * @param {Element} element
 * @returns {Element[] | null}
 */
function shownRows(element) {
  if (isChange(element)) {
    return [...element.children].flatMap((run) =>
      /** @type {HTMLElement} */ (run).hidden
        ? []
        : [...run.children].filter((row) => !(/** @type {HTMLElement} */ (row).hidden)),
    );
  }
  if (element.classList.contains("diff-markdown-block")) {
    return /** @type {HTMLElement} */ (element).hidden ? [] : [element];
  }
  return null;
}

/**
 * The row shown next to *element* on one side, among its siblings: past rows and changes
 * that show none, up to anything that stands between rows.
 * @param {Element} element
 * @param {boolean} before
 * @returns {Element | null}
 */
function shownNeighbour(element, before) {
  for (
    let node = before ? element.previousElementSibling : element.nextElementSibling;
    node !== null;
    node = before ? node.previousElementSibling : node.nextElementSibling
  ) {
    const rows = shownRows(node);
    if (rows === null) {
      return null;
    }
    if (rows.length > 0) {
      return /** @type {Element} */ (rows[before ? rows.length - 1 : 0]);
    }
  }
  return null;
}

/**
 * Mark each row of *elements*, neighbours in an article or an open fold, and the row shown
 * on either side of them, with how KPress spaces it by the row shown before it and the row
 * shown after it (`joinOf`), which its block cannot see from its own row. Every row shown
 * carries `data-join`, which holds `start` when its block's start margin gives way and
 * `end` when its end margin does (styles.css), and is empty when neither does. The rows
 * shown are the rows drawn and not hidden, so Current, which hides a removed run, marks
 * each row by the rows around it in the new version, and a run of changes or a chunk
 * boundary between two rows makes no difference. Call it whenever what is drawn or hidden
 * changes: a chunk drawn, a fold filled, Diff or Current chosen.
 * @param {Element[]} elements
 */
export function markJoins(elements) {
  const [first] = elements;
  if (first === undefined) {
    return;
  }
  /** @type {(Element | null)[]} */
  const sequence = [shownNeighbour(first, true)];
  for (const element of elements) {
    const rows = shownRows(element);
    if (rows === null) {
      sequence.push(null);
    } else {
      sequence.push(...rows);
    }
  }
  sequence.push(shownNeighbour(/** @type {Element} */ (elements[elements.length - 1]), false));
  for (let index = 0; index + 1 < sequence.length; index += 1) {
    const before = sequence[index] ?? null;
    const after = sequence[index + 1] ?? null;
    const join = joinOf(
      before === null ? null : edgeTag(before, true),
      after === null ? null : edgeTag(after, false),
    );
    if (before !== null) {
      setJoin(/** @type {HTMLElement} */ (before), "end", join.end);
    }
    if (after !== null) {
      setJoin(/** @type {HTMLElement} */ (after), "start", join.start);
    }
  }
}

/**
 * @param {HTMLElement} row
 * @param {"start" | "end"} edge
 * @param {boolean} joined
 */
function setJoin(row, edge, joined) {
  const kept = (row.dataset.join ?? "").split(" ").filter((each) => each !== "" && each !== edge);
  row.dataset.join = (joined ? [...kept, edge].sort() : kept).join(" ");
}

/**
 * What a view draws of a projection, in order: in Full, each block; in Concise, each block
 * outside a fold, and each fold, which stands for the blocks it holds until it opens.
 * @param {Model} model
 * @param {View} view
 * @returns {Unit[]}
 */
export function viewUnits(model, view) {
  /** @type {Unit[]} */
  const units = [];
  const folds = view === "concise" ? model.folds : [];
  let next = 0;
  for (let index = 0; index < model.blocks.length; ) {
    const fold = folds[next];
    if (fold !== undefined && fold.at === index) {
      units.push({ kind: "fold", fold });
      index += fold.count;
      next += 1;
    } else {
      units.push({ kind: "block", index });
      index += 1;
    }
  }
  return units;
}

/**
 * The units of a run in the chunks it is drawn in: one, within `WHOLE_UNITS` and
 * `WHOLE_BYTES`; past either, a chunk ends at `CHUNK_UNITS` units, or once its blocks
 * hold `CHUNK_BYTES` of HTML. A fold is one unit of no bytes, as its bar is.
 * @param {Unit[]} units
 * @param {(index: number) => number} bytesOf A block's HTML bytes, by its index.
 * @returns {Unit[][]}
 */
export function chunkUnits(units, bytesOf) {
  const blockBytes = (/** @type {Unit} */ unit) =>
    unit.kind === "block" ? bytesOf(unit.index) : 0;
  if (
    units.length <= WHOLE_UNITS &&
    units.reduce((sum, unit) => sum + blockBytes(unit), 0) <= WHOLE_BYTES
  ) {
    return units.length > 0 ? [units] : [];
  }
  /** @type {Unit[][]} */
  const chunks = [];
  /** @type {Unit[]} */
  let chunk = [];
  let bytes = 0;
  for (const unit of units) {
    chunk.push(unit);
    bytes += blockBytes(unit);
    if (chunk.length >= CHUNK_UNITS || bytes >= CHUNK_BYTES) {
      chunks.push(chunk);
      chunk = [];
      bytes = 0;
    }
  }
  if (chunk.length > 0) {
    chunks.push(chunk);
  }
  return chunks;
}

/** The blocks a unit stands for, from its first, the end not included. @param {Unit} unit */
function unitSpan(unit) {
  return unit.kind === "block"
    ? [unit.index, unit.index + 1]
    : [unit.fold.at, unit.fold.at + unit.fold.count];
}

/**
 * The height a chunk not yet drawn keeps for itself, in pixels (`BLOCK_PX`, `BYTE_PX`).
 * @param {Unit[]} units
 * @param {(index: number) => number} bytesOf
 */
export function estimatedHeight(units, bytesOf) {
  let height = 0;
  for (const unit of units) {
    height += unit.kind === "block" ? BLOCK_PX + BYTE_PX * bytesOf(unit.index) : FOLD_PX;
  }
  return Math.round(height);
}

/** Whether a model holds every block from *start* up to *end*. @param {Model} model @param {number} start @param {number} end */
function holds(model, start, end) {
  for (let index = start; index < end; index += 1) {
    if (model.blocks[index] === undefined) {
      return false;
    }
  }
  return true;
}

/** @param {string} value */
function unescapeAttribute(value) {
  return value.replace(/&(?:amp|quot|#39|lt|gt);/g, (entity) =>
    entity === "&amp;"
      ? "&"
      : entity === "&quot;"
        ? '"'
        : entity === "&#39;"
          ? "'"
          : entity === "&lt;"
            ? "<"
            : ">",
  );
}

/**
 * The block of a model whose HTML holds the anchor *id*, or, for one of a withheld fold,
 * which the model has not yet, the fold's first block; -1 for none.
 * @param {Model} model
 * @param {string} id
 */
export function blockOf(model, id) {
  for (let index = 0; index < model.blocks.length; index += 1) {
    const html = model.blocks[index]?.html ?? "";
    for (const match of html.matchAll(/\sid="([^"]+)"/g)) {
      if (unescapeAttribute(match[1]) === id) {
        return index;
      }
    }
  }
  const fold = model.folds.find((each) => each.ids?.includes(id));
  return fold === undefined ? -1 : fold.at;
}

/** @param {unknown} value @returns {value is Block} */
function isBlock(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const block = /** @type {{kind?: unknown, html?: unknown, source_only?: unknown}} */ (value);
  return (
    ["context", "removed", "added"].includes(String(block.kind)) &&
    typeof block.html === "string" &&
    (block.source_only === undefined || typeof block.source_only === "boolean")
  );
}

/** @param {unknown} value @returns {value is Fold} */
function isFold(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const fold =
    /** @type {{at?: unknown, count?: unknown, lines?: unknown, withheld?: unknown, ids?: unknown}} */ (
      value
    );
  return (
    Number.isInteger(fold.at) &&
    Number.isInteger(fold.count) &&
    Number(fold.count) > 0 &&
    Number.isInteger(fold.lines) &&
    (fold.withheld === undefined || fold.withheld === true) &&
    (fold.ids === undefined ||
      (Array.isArray(fold.ids) && fold.ids.every((id) => typeof id === "string")))
  );
}

/**
 * A ready answer as the model a file draws its views from, or null for anything else. A
 * Concise answer leaves out a withheld fold's blocks, which the model holds as
 * `undefined` until they are asked for (`blocks=`).
 * @param {unknown} value
 * @returns {{model: Model, view: View, sourceOnly: boolean, assets?: KpressAssetManifest} | null}
 */
export function projectionModel(value) {
  if (value === null || typeof value !== "object") {
    return null;
  }
  const answer =
    /** @type {{version?: unknown, status?: unknown, blocks?: unknown, source_only?: unknown, frontmatter?: unknown, view?: unknown, count?: unknown, folds?: unknown, assets?: unknown}} */ (
      value
    );
  if (
    answer.version !== "markdown-diff-v1" ||
    answer.status !== "ready" ||
    (answer.view !== "full" && answer.view !== "concise") ||
    typeof answer.source_only !== "boolean" ||
    (answer.frontmatter !== undefined && !isFrontmatter(answer.frontmatter)) ||
    !Number.isInteger(answer.count) ||
    !Array.isArray(answer.blocks) ||
    !answer.blocks.every(isBlock) ||
    !Array.isArray(answer.folds) ||
    !answer.folds.every(isFold)
  ) {
    return null;
  }
  const count = Number(answer.count);
  const folds = /** @type {Fold[]} */ (answer.folds);
  const sent = /** @type {Block[]} */ (answer.blocks);
  /** @type {(Block | undefined)[]} */
  const blocks = Array.from({ length: count });
  let end = 0;
  let next = 0;
  for (const fold of folds) {
    // In order, apart, and inside the document.
    if (fold.at < end || fold.at + fold.count > count) {
      return null;
    }
    end = fold.at + fold.count;
  }
  const withheld = answer.view === "concise" ? folds.filter((fold) => fold.withheld) : [];
  for (let index = 0, each = 0; index < count; ) {
    const fold = withheld[each];
    if (fold !== undefined && fold.at === index) {
      index += fold.count;
      each += 1;
      continue;
    }
    if (next >= sent.length) {
      return null;
    }
    blocks[index] = sent[next];
    next += 1;
    index += 1;
  }
  if (next !== sent.length) {
    return null;
  }
  return {
    model: {
      blocks,
      folds,
      ...(answer.frontmatter === undefined
        ? {}
        : { frontmatter: /** @type {Frontmatter} */ (answer.frontmatter) }),
    },
    view: answer.view,
    sourceOnly: answer.source_only,
    ...(answer.assets === undefined
      ? {}
      : { assets: /** @type {KpressAssetManifest} */ (answer.assets) }),
  };
}

/**
 * A withheld fold's blocks as the route answers `blocks=` for it, or null for anything else.
 * @param {unknown} value
 * @param {Fold} fold
 * @returns {Block[] | null}
 */
export function foldBlocks(value, fold) {
  if (value === null || typeof value !== "object") {
    return null;
  }
  const answer =
    /** @type {{version?: unknown, status?: unknown, at?: unknown, blocks?: unknown}} */ (value);
  return answer.version === "markdown-diff-v1" &&
    answer.status === "ready" &&
    answer.at === fold.at &&
    Array.isArray(answer.blocks) &&
    answer.blocks.length === fold.count &&
    answer.blocks.every(isBlock)
    ? /** @type {Block[]} */ (answer.blocks)
    : null;
}

/**
 * Whether a model's rows are all removed, a file left empty: its front matter, when it has
 * one, and every block.
 * @param {Model} model
 */
function emptiedModel(model) {
  const rows = [
    ...(model.frontmatter === undefined
      ? []
      : [model.frontmatter.change === "removed" ? "removed" : "context"]),
    ...model.blocks.map((block) => block?.kind),
  ];
  return rows.length > 0 && rows.every((kind) => kind === "removed");
}

/**
 * What Current leaves out of a Markdown file's rendered rows, before they are placed: each
 * removed run (`changeRuns`) and its blocks, a wholly removed front matter among them, and
 * each removed key of a front matter that changed. A run and each of its rows are hidden
 * together, so a hidden run draws no band, and a row says by its own attribute whether it
 * shows. Every deleted word is in a removed block (`<del>` marks only those), so what is
 * left is the new version, its added blocks still marked. A fold holds only unchanged
 * blocks, so the rows are the article's own and the front matter's terms.
 * @param {Iterable<Element>} rows What `changeRuns` placed.
 * @returns {HTMLElement[]}
 */
export function removedParts(rows) {
  /** @type {HTMLElement[]} */
  const parts = [];
  /** @param {Element} node */
  const keys = (node) => {
    for (const child of node.children) {
      if (
        child.classList.contains("diff-frontmatter-removed") ||
        child.classList.contains("diff-frontmatter-removal-marker")
      ) {
        parts.push(/** @type {HTMLElement} */ (child));
      }
      keys(child);
    }
  };
  for (const row of rows) {
    if (isChange(row)) {
      for (const run of row.children) {
        if (run.classList.contains("diff-markdown-run-removed")) {
          parts.push(/** @type {HTMLElement} */ (run));
          parts.push(.../** @type {HTMLElement[]} */ ([...run.children]));
        }
      }
    } else if (row.classList.contains("diff-markdown-frontmatter")) {
      keys(row);
    }
  }
  return parts;
}

/**
 * The stylesheets of a projection's KPress asset manifest that the page loads: each
 * `loading: "stylesheet"` entry whose address, resolved against *base*, has the page's
 * origin and a path under `/kpress-static/`, the route that serves the KPress package
 * (`kpress_static_asset` in server.py), ending `.css`. Nothing of the manifest runs.
 *
 * The check reads the address as the browser resolves it, its origin and its normalized
 * path, and not the characters of its segments, which are the server's to choose: the
 * asset stamp (metabrowser.asset_stamps) and KPress's version, which is a PEP 440 version
 * and so may hold `+` and `!`, as an editable KPress's `v0.3.10.dev10+5c60a81` does
 * (`kpress_static_url` in kpress_adapter.py). A pattern over those characters dropped
 * every stylesheet of such a KPress (mb-2r08). Nor is it the page's own KPress prefix: a
 * live KPress tree moves its stamp at each edit, so a projection can name a newer one than
 * the page was rendered with.
 *
 * Without KPress's document.css a rendered document has no face rule and reads in the
 * page's sans, so a stylesheet left out is named in a warning, never dropped silently.
 *
 * @param {KpressAssetManifest} assets
 * @param {string} base The page's address, `document.baseURI`.
 * @returns {KpressAssetManifest}
 */
export function kpressStylesheets(assets, base) {
  const origin = new URL(base).origin;
  /** @type {KpressAssetManifest["assets"]} */
  const kept = [];
  /** @type {string[]} */
  const dropped = [];
  for (const asset of assets.assets) {
    if (asset.loading !== "stylesheet") {
      continue;
    }
    const url = asset.public_url ?? "";
    /** @type {URL | null} */
    let address = null;
    try {
      address = new URL(url, base);
    } catch {
      // Not an address: left out, and named below.
    }
    if (
      address !== null &&
      address.origin === origin &&
      address.pathname.startsWith("/kpress-static/") &&
      address.pathname.endsWith(".css")
    ) {
      kept.push(asset);
    } else {
      dropped.push(url);
    }
  }
  if (dropped.length > 0) {
    console.warn(
      "metabrowser diff: KPress stylesheets the server named are not same-origin KPress CSS, so they are not loaded",
      dropped,
    );
  }
  return { schema_version: "kpress-asset-manifest-v2", import_map: {}, assets: kept };
}

/**
 * One queue for a mounted comparison, one request at a time to match the server's one
 * projection slot. An answer that arrives after its file switched to Source or left
 * the lookahead is kept for when the reader comes back to it.
 *
 * *holdMs* is how long `firstScreen` waits for the first screen's files,
 * `LOADING_DELAY_MS` unless a page says otherwise. It settles once none of them waits,
 * each drawn, Rendered or Source, or when the wait is over; a file still waiting then
 * goes on waiting with Source hidden and nothing shown below it (`WAITING_CLASS`), until
 * *waitMs* from mount, `RENDERED_WAIT_MS` unless the host says otherwise, when it shows
 * Source and keeps it. *opens* is the view
 * a Markdown file opens in: `concise`, as Changes opens one, or `prefer-full`, Full for a
 * document small enough to draw whole and Concise otherwise, as Docs does; the server
 * decides which (`prefers_full` in diff/markdown_views.py). A page that keeps the
 * comparison out of sight until then shows its first screen at the heights it keeps.
 * @param {{
 *   load: (fileId: string, signal: AbortSignal, ask?: RenderedAsk) => Promise<unknown>,
 *   controls: NonNullable<MetabrowserPublicSdk["filterControls"]>,
 *   ensureInert: () => Promise<MetabrowserInertHtmlRuntime | undefined>,
 *   ensureStructured?: () => Promise<TreeHelpers | undefined>,
 *   loadStyles: (assets: KpressAssetManifest) => Promise<void>,
 *   mutate: (change: () => void) => void,
 *   isTarget?: (value: string, image: boolean) => boolean,
 *   now?: () => number,
 *   later?: (callback: () => void, ms: number) => unknown,
 *   cancel?: (handle: unknown) => void,
 *   opens?: "concise" | "prefer-full",
 *   holdMs?: number,
 *   waitMs?: number,
 *   show?: "diff" | "current" | "full"
 * }} deps
 *   *show* is the comparison's initial presentation.
 */
export function createMarkdownViews(deps) {
  const now = deps.now ?? (() => Date.now());
  const isTarget = deps.isTarget ?? (() => false);
  const opens = deps.opens ?? "concise";
  let shown = deps.show ?? "diff";
  let explicitFull = false;
  /** @type {FileView | null} */
  let upgradingFile = null;
  /** @type {WeakMap<HTMLElement, HTMLElement>} */
  const deletionNotices = new WeakMap();
  const later = deps.later ?? ((callback, ms) => setTimeout(callback, ms));
  const cancel =
    deps.cancel ??
    ((handle) => clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (handle)));
  /** @type {Map<HTMLElement, FileView>} */
  const files = new Map();
  // Each file's chooser is bound by itself, never the diff around them all: a bound
  // container answers for every dropdown inside it, and the diff's toolbar holds the File
  // type menu, which is its own control's (mb-yn7w). A binding is three listeners on the
  // chooser and one on the window: 1,000 of them took 2.9 to 4.4 ms to bind, 4.3 to 5.4 ms
  // to answer one window resize, and 3.2 to 3.7 ms to unbind (headless Chrome,
  // 2026-11-26, load average near 50, five runs).
  /** @type {Array<() => void>} */
  const unbinds = [];
  /** @type {Set<FileView>} */
  const nearby = new Set();
  /** @type {Map<HTMLElement, {region: Region, chunk: Chunk}>} */
  const spacers = new Map();
  /** @type {{file: FileView, controller: AbortController} | null} */
  let active = null;
  /** @type {IntersectionObserver | null} */
  let observer = null;
  /** @type {IntersectionObserver | null} */
  let chunkObserver = null;
  /** @type {Promise<MetabrowserInertHtmlRuntime | undefined> | undefined} */
  let inertReady;
  /** @type {Promise<void> | undefined} */
  let stylesReady;
  /** @type {Promise<TreeHelpers | undefined> | undefined} */
  let structuredReady;
  let disposed = false;
  let observed = false;
  let reported = false;
  /** @type {unknown} */
  let holdTimer;
  /** @type {unknown} */
  let retryTimer;
  /** @type {unknown} */
  let waitTimer;
  let waitUntil = 0;
  /** @type {(() => void) | undefined} */
  let unprint;
  let firstScreenSettled = false;
  /** @type {() => void} */
  let settleFirstScreen = () => {};
  /** @type {Promise<void>} */
  const firstScreen = new Promise((resolve) => {
    settleFirstScreen = () => {
      firstScreenSettled = true;
      resolve(undefined);
    };
  });

  // The first screen has been reported and none of its files waits for Rendered any more.
  function checkFirstScreen() {
    if (firstScreenSettled) {
      return;
    }
    if (
      disposed ||
      (reported &&
        !Array.from(files.values()).some(
          (file) =>
            file.holding &&
            file.expanded &&
            isRendered(file.mode) &&
            file.state === "idle" &&
            nearby.has(file),
        ))
    ) {
      settleFirstScreen();
    }
  }

  // Whether a file is to show its rendering: chosen, unless it was deleted or left empty
  // and the diff shows its current version, which such a file's Source body says it has
  // none of.
  /** @param {FileView} file */
  function wantsRendered(file) {
    return isRendered(file.mode) && !(shown !== "diff" && (file.gone || file.emptied));
  }

  /** @param {FileView} file */
  function draw(file) {
    const wanted = wantsRendered(file);
    const rich = wanted && file.state === "ready";
    const waiting = !rich && file.holding && wanted && file.expanded;
    const hidden = rich || waiting;
    const changed = file.source.hidden !== hidden;
    file.source.hidden = hidden;
    // Nothing shows below a file whose first drawing is still to come (styles.css), so
    // its body, whenever it arrives, moves nothing a reader can see or press.
    file.section.classList.toggle(WAITING_CLASS, waiting);
    file.rendered.hidden = !file.expanded || !rich;
    const markdown = wanted && file.format === "markdown" && file.model !== null;
    const shortened = shown === "full" && file.drawn === "concise";
    const hasContext = shown === "diff" && (file.model?.folds.length ?? 0) > 0;
    file.fallback.hidden = !(markdown && rich && file.expanded && (shortened || hasContext));
    file.fallbackMessage.hidden = !shortened;
    file.fallbackMessage.textContent = file.fullFailed
      ? "Could not show the full document. Showing an excerpt."
      : file.upgrading
        ? "Showing an excerpt."
        : "This document opens as an excerpt because of its size.";
    file.expand.disabled = file.upgrading;
    file.expand.textContent =
      shown === "diff"
        ? file.expandedContext
          ? "Collapse unchanged sections"
          : "Expand unchanged sections"
        : "Show full file";
    drawProgress(file);
    if (changed) {
      file.onSource?.(!hidden);
    }
  }

  // What Rendered draws of Current: a Markdown file's removed blocks and keys hidden, by
  // the attribute, so which show is decided here and not by a selector, and a YAML or JSON
  // tree drawn again without its removed entries (`setCurrent` in diff-structured.js).
  /** @param {FileView} file */
  function applyShow(file) {
    const current = shown !== "diff";
    const excerpt = shown === "current" || (shown === "full" && file.drawn === "concise");
    for (const part of file.removed) {
      if (part.classList.contains("diff-frontmatter-removal-marker")) {
        part.hidden = !excerpt;
        continue;
      }
      part.hidden = current;
      if (!part.classList.contains("diff-markdown-run-removed") || part.parentElement == null) {
        continue;
      }
      let notice = deletionNotices.get(part);
      const onlyRemoval = !part.nextElementSibling?.classList.contains("diff-markdown-run-added");
      if (notice === undefined && excerpt && onlyRemoval) {
        notice = document.createElement("div");
        notice.className = "diff-availability";
        notice.textContent = "Content removed here. See Diff.";
        part.before(notice);
        deletionNotices.set(part, notice);
      }
      if (notice !== undefined) {
        notice.hidden = !excerpt || !onlyRemoval;
      }
    }
    // Which rows are shown changed, so what each is shown beside did too.
    if (file.removed.length > 0) {
      markJoins([...file.rendered.children]);
    }
    file.tree?.setCurrent(current, shown === "current");
  }

  // The chooser stays for a file that can only show Source: its rendered chips are
  // unavailable and say why, as their tooltip and in their accessible name, which a
  // keyboard and a screen reader reach. They are `aria-disabled`, not `disabled`: a
  // disabled button takes no pointer and no focus, so nothing could say why. select()
  // keeps them from being chosen.
  /** @param {FileView} file */
  function drawControl(file) {
    const restoreFocus = file.control.contains(document.activeElement);
    const unavailable = file.state === "unavailable";
    const tip = unavailable ? { tip: file.reason } : {};
    /** @param {Mode} value */
    const option = (value) => ({
      label: MODE_LABELS[value],
      value,
      ...(value === "rendered" ? tip : {}),
    });
    file.control.innerHTML = deps.controls.groupHtml({
      key: file.source.id,
      label: `${formatName(file.format)} diff format`,
      layout: "joined",
      options: [option("rendered"), option("source")],
      select: "one",
      value: file.mode,
    });
    for (const chip of file.control.querySelectorAll("button[data-chip-value]")) {
      const button = /** @type {HTMLButtonElement} */ (chip);
      const mode = /** @type {Mode} */ (button.dataset.chipValue);
      button.setAttribute("aria-controls", isRendered(mode) ? file.rendered.id : file.source.id);
      if (isRendered(mode) && unavailable) {
        button.setAttribute("aria-disabled", "true");
        button.setAttribute("aria-label", `${MODE_LABELS[mode]}, unavailable. ${file.reason}`);
      }
      if (restoreFocus && mode === file.mode) {
        button.focus();
      }
    }
  }

  // The progress mark sits in the file bar beside the chooser, so it never moves the
  // diff, and stays invisible until the loading-state delay passes.
  /** @param {FileView} file */
  function drawProgress(file) {
    const showing = (file.pending || file.fetching > 0) && file.expanded && wantsRendered(file);
    file.progress.classList.toggle("mb-delayed-loading", showing);
    file.progressLabel.textContent = showing ? `Rendering ${formatName(file.format)}` : "";
  }

  /** @param {FileView} file */
  function interested(file) {
    return (
      nearby.has(file) &&
      file.expanded &&
      isRendered(file.mode) &&
      file.state === "idle" &&
      file.retryAt <= now()
    );
  }

  // The wait for the first screen is over, so a page that kept the comparison out of
  // sight shows it. A file still waiting goes on waiting, its bar drawn and nothing shown
  // below it: drawing its Source now and replacing it when its answer came moved every
  // file under it (mb-ne65).
  function release() {
    holdTimer = undefined;
    settleFirstScreen();
    // The ceiling is counted from mount, and timed only while a file may still wait.
    if (Array.from(files.values()).some((file) => file.holding && file.state === "idle")) {
      waitTimer = later(endWaits, Math.max(0, waitUntil - now()));
    }
  }

  // The ceiling on a file's wait (`RENDERED_WAIT_MS`): each file still waiting shows
  // Source and keeps it, as one whose request failed does.
  function endWaits() {
    waitTimer = undefined;
    for (const file of files.values()) {
      if (file.section.classList.contains(WAITING_CLASS)) {
        fallBack(file, null);
      }
    }
  }

  function pump() {
    if (disposed || !observed) {
      return;
    }
    if (active !== null || upgradingFile !== null) {
      // The request in flight finishes even when its file leaves the lookahead: the
      // server finishes the work regardless (a cancelled waiter does not stop its
      // load), and one slot busy with a load nobody waits for refused the next file.
      // In review C's simulation of 100 files at 10,000 px/s that was 33 of them.
      return;
    }
    const file = Array.from(nearby).find(interested);
    if (file === undefined) {
      const upgrade = Array.from(nearby).find(
        (candidate) =>
          candidate.expanded &&
          wantsRendered(candidate) &&
          !candidate.fullFailed &&
          coverage(candidate) === "full" &&
          candidate.model !== null &&
          !holds(candidate.model, 0, candidate.model.blocks.length),
      );
      if (upgrade !== undefined) {
        askFull(upgrade);
        return;
      }
      scheduleRetry();
      return;
    }
    const controller = new AbortController();
    const { signal } = controller;
    active = { file, controller };
    void load(file, signal);
  }

  /** @param {FileView} file */
  function retryLater(file) {
    file.retryAt = now() + Math.min(RETRY_MS * 2 ** file.retries, RETRY_MAX_MS);
    file.retries += 1;
  }

  // Wake for the earliest refused file still waiting near the viewport.
  function scheduleRetry() {
    const waiting = Array.from(nearby).filter(
      (file) =>
        file.expanded && isRendered(file.mode) && file.state === "idle" && file.retryAt > now(),
    );
    if (retryTimer !== undefined || waiting.length === 0) {
      return;
    }
    const at = Math.min(...waiting.map((file) => file.retryAt));
    retryTimer = later(
      () => {
        retryTimer = undefined;
        pump();
      },
      Math.max(at - now(), 0),
    );
  }

  // The structured plugin's assets, asked for when the first YAML or JSON file is added,
  // so they load beside its first request; every load awaits this one promise, and
  // index.js asks for them too with the first screen's prefetch. They are four files,
  // preview.js, tree.js, index.js and styles.css: 37,324 bytes, 12,373 gzipped at
  // `delivery.GZIP_LEVEL` on 2026-11-18. Loaded inside the first-screen hold, as they were
  // before, the hold took a median 130 ms cold against 106 ms warm in the live app (mb-8274
  // review C1). A failure is not kept here, so the next load asks again, but the SDK
  // answers a provider that failed to load with that failure until the page is reloaded
  // ("Declared Dependencies" in docs/plugins.md).
  function ensureStructured() {
    structuredReady ??= Promise.resolve()
      .then(() => deps.ensureStructured?.())
      .catch(() => undefined);
    return structuredReady;
  }

  /**
   * More of a file's projection than its first answer holds: a withheld fold's blocks, or
   * Full's. Asked for at once, beside the queue, since the reader is waiting for it; a
   * refusal while the server's one slot is busy is asked again, as the queue's are.
   * @param {FileView} file
   * @param {RenderedAsk} ask
   * @returns {Promise<unknown>}
   */
  async function askMore(file, ask) {
    const controller = new AbortController();
    const { signal } = controller;
    file.asking.add(controller);
    file.fetching += 1;
    drawProgress(file);
    try {
      for (let tries = 0; ; tries += 1) {
        try {
          return await deps.load(file.id, signal, ask);
        } catch (error) {
          if (
            /** @type {{status?: unknown}} */ (error)?.status !== 429 ||
            tries >= MORE_TRIES ||
            signal.aborted ||
            disposed
          ) {
            throw error;
          }
          // The wait ends early when `dispose` cancels the request, which then asks no more.
          await new Promise((resolve) => {
            const stop = () => {
              cancel(handle);
              resolve(undefined);
            };
            const handle = later(
              () => {
                signal.removeEventListener("abort", stop);
                resolve(undefined);
              },
              Math.min(RETRY_MS * 2 ** tries, RETRY_MAX_MS),
            );
            signal.addEventListener("abort", stop, { once: true });
          });
          if (signal.aborted || disposed) {
            throw error;
          }
        }
      }
    } finally {
      file.asking.delete(controller);
      file.fetching -= 1;
      if (!disposed) {
        drawProgress(file);
      }
    }
  }

  /** @param {FileView} file @param {AbortSignal} signal */
  async function load(file, signal) {
    let settled = false;
    try {
      file.pending = true;
      deps.mutate(() => drawProgress(file));
      if (file.format !== "markdown") {
        const projection = await deps.load(file.id, signal);
        if (signal.aborted || disposed) {
          return;
        }
        if (!isStructuredProjection(projection)) {
          fallBack(file, refusalReason(projection, file.format));
          return;
        }
        const tree = await ensureStructured();
        if (tree === undefined) {
          structuredReady = undefined;
          throw new Error("The structured tree renderer is unavailable.");
        }
        if (signal.aborted || disposed) {
          return;
        }
        settled = true;
        deps.mutate(() => {
          file.tree?.dispose();
          file.tree = mountStructuredDiff(file.rendered, projection.root, tree, {
            sourceOnly: projection.source_only,
            current: shown !== "diff",
            excerpt: shown === "current",
          });
          file.emptied =
            projection.root.length > 0 &&
            projection.root.every((entry) => entry.change === "removed");
          file.state = "ready";
          file.pending = false;
          file.retries = 0;
          draw(file);
        });
        checkFirstScreen();
        return;
      }
      const view =
        shown === "full" && !explicitFull && opens === "prefer-full"
          ? "prefer-full"
          : coverage(file);
      const projection = await deps.load(file.id, signal, { view });
      if (signal.aborted || disposed) {
        return;
      }
      const ready = projectionModel(projection);
      if (ready === null) {
        fallBack(file, refusalReason(projection, file.format));
        return;
      }
      inertReady ??= deps.ensureInert();
      /** @type {MetabrowserInertHtmlRuntime | undefined} */
      let inert;
      try {
        inert = await inertReady;
      } catch {
        inert = undefined;
      }
      if (inert === undefined) {
        // Not kept: choosing Rendered again loads it again.
        inertReady = undefined;
        throw new Error("The untrusted Markdown sanitizer is unavailable.");
      }
      if (ready.assets !== undefined) {
        // A stylesheet that does not load leaves the document in the page's faces, so it
        // is said, and the file is still drawn.
        stylesReady ??= deps
          .loadStyles(kpressStylesheets(ready.assets, document.baseURI))
          .catch((error) => {
            console.warn("metabrowser diff: KPress's stylesheets did not load", error);
          });
        await stylesReady;
      }
      if (signal.aborted || disposed) {
        return;
      }
      const scratch = document.implementation.createHTMLDocument("");
      const template = document.createElement("template");
      settled = true;
      deps.mutate(() => {
        file.model = ready.model;
        file.build = (html) => sanitizeBlock(html, inert, template, scratch, isTarget);
        file.emptied = emptiedModel(ready.model);
        if (view === "prefer-full") {
          file.automaticView = ready.view;
        }
        file.state = "ready";
        file.pending = false;
        file.retries = 0;
        refresh(file);
        draw(file);
      });
      checkFirstScreen();
    } catch (error) {
      if (!signal.aborted && !disposed) {
        if (/** @type {{status?: unknown}} */ (error)?.status === 429) {
          retryLater(file);
        } else {
          console.warn("metabrowser diff: a rendered file failed; showing Source", error);
          fallBack(file, null);
        }
      }
    } finally {
      if (!settled && !disposed) {
        file.pending = false;
        deps.mutate(() => drawProgress(file));
      }
      active = null;
      pump();
    }
  }

  /** @param {FileView} file @returns {View} */
  function coverage(file) {
    if (shown === "full") {
      return !explicitFull && !file.forceFull && file.automaticView === "concise"
        ? "concise"
        : "full";
    }
    return shown === "diff" && file.expandedContext ? "full" : "concise";
  }

  // Draw what a ready Markdown file's chosen view shows, once it holds the blocks to: Full
  // waits for the blocks a Concise answer left out, showing what is drawn meanwhile, or
  // Concise when nothing is.
  /** @param {FileView} file */
  function refresh(file) {
    const model = file.model;
    if (model === null || !isRendered(file.mode)) {
      return;
    }
    const view = file.fullFailed ? "concise" : coverage(file);
    if (view === "full" && !holds(model, 0, model.blocks.length)) {
      pump();
      if (file.drawn === null) {
        paint(file, "concise");
      }
      return;
    }
    if (file.drawn !== view) {
      paint(file, view);
    }
  }

  // The blocks a Concise answer withheld, all at once, for Full.
  /** @param {FileView} file */
  function askFull(file) {
    if (file.upgrading) {
      return;
    }
    file.upgrading = true;
    upgradingFile = file;
    deps.mutate(() => draw(file));
    askMore(file, { view: "full" })
      .then((answer) => {
        const full = projectionModel(answer);
        const model = file.model;
        if (
          full === null ||
          full.view !== "full" ||
          model === null ||
          full.model.blocks.length !== model.blocks.length
        ) {
          throw new Error("The server answered Full with another document.");
        }
        model.blocks = full.model.blocks;
      })
      .catch((error) => {
        if (disposed) {
          return;
        }
        console.warn("metabrowser diff: Full did not load", error);
        file.fullFailed = true;
        file.expandedContext = false;
      })
      .finally(() => {
        file.upgrading = false;
        upgradingFile = null;
        if (!disposed) {
          deps.mutate(() => {
            drawControl(file);
            refresh(file);
            draw(file);
          });
          pump();
        }
      });
  }

  // Forget what a file's article draws: its chunks still to draw and its folds.
  /** @param {FileView} file */
  function clearDrawn(file) {
    for (const [spacer, entry] of spacers) {
      if (entry.region.file === file) {
        chunkObserver?.unobserve(spacer);
        spacers.delete(spacer);
      }
    }
    file.foldViews.clear();
    file.removed = [];
    file.top = null;
    file.drawn = null;
  }

  // The article drawn in *view*: the front matter, then the view's first chunk, and a
  // place kept for each chunk after it, drawn as the reader comes near it.
  /** @param {FileView} file @param {View} view */
  function paint(file, view) {
    const model = /** @type {Model} */ (file.model);
    clearDrawn(file);
    const content = document.createDocumentFragment();
    if (model.frontmatter !== undefined) {
      const placed = changeRuns([frontmatterRow(model.frontmatter)]);
      content.append(...placed);
      file.removed.push(...removedParts(placed));
    }
    file.top = fillRegion(file, content, viewUnits(model, view), true);
    // Changed front matter and a changed first block are one change.
    joinChanges([...content.children]);
    file.drawn = view;
    file.rendered.replaceChildren(content);
    applyShow(file);
    observeSpacers(file);
  }

  /** @param {FileView} file */
  function observeSpacers(file) {
    for (const [spacer, entry] of spacers) {
      if (entry.region.file === file) {
        chunkObserver?.observe(spacer);
      }
    }
  }

  /**
   * A run of rows drawn into *container* a chunk at a time: the first now, and for each
   * one after it a spacer of its estimated height, which `chunkObserver` draws it in place
   * of as the reader comes within `LOOKAHEAD` of it.
   * @param {FileView} file
   * @param {DocumentFragment | HTMLElement} container
   * @param {Unit[]} units
   * @param {boolean} top Whether this is the article's own run, not an open fold's.
   * @returns {Region}
   */
  function fillRegion(file, container, units, top) {
    const model = /** @type {Model} */ (file.model);
    const bytesOf = (/** @type {number} */ index) => model.blocks[index]?.html.length ?? 0;
    /** @type {Region} */
    const region = { file, top, chunks: [] };
    for (const chunkUnitsOf of chunkUnits(units, bytesOf)) {
      const start = unitSpan(chunkUnitsOf[0])[0];
      const end = unitSpan(chunkUnitsOf[chunkUnitsOf.length - 1])[1];
      /** @type {Chunk} */
      const chunk = { units: chunkUnitsOf, start, end, spacer: null };
      const first = region.chunks.length === 0;
      region.chunks.push(chunk);
      if (first) {
        const placed = chunkRows(region, chunk);
        container.append(...placed);
        markJoins(placed);
        continue;
      }
      const spacer = document.createElement("div");
      spacer.className = "diff-markdown-spacer";
      spacer.setAttribute("aria-hidden", "true");
      spacer.dataset.span = `${start}-${end}`;
      spacer.style.height = `${estimatedHeight(chunkUnitsOf, bytesOf)}px`;
      container.append(spacer);
      chunk.spacer = spacer;
      spacers.set(spacer, { region, chunk });
    }
    return region;
  }

  /**
   * A chunk's rows: each block's, in its change and run (`changeRuns`), and each fold's bar
   * and group.
   * @param {Region} region
   * @param {Chunk} chunk
   * @returns {HTMLElement[]}
   */
  function chunkRows(region, chunk) {
    const { file } = region;
    const model = /** @type {Model} */ (file.model);
    const build = /** @type {(html: string) => Node} */ (file.build);
    /** @type {HTMLElement[]} */
    const rows = [];
    for (const unit of chunk.units) {
      if (unit.kind === "block") {
        const row = blockRow(/** @type {Block} */ (model.blocks[unit.index]), build);
        row.dataset.block = String(unit.index);
        rows.push(row);
      } else {
        const fold = foldView(file, unit.fold);
        rows.push(fold.expander.control, fold.expander.group);
      }
    }
    const placed = changeRuns(rows);
    if (region.top) {
      // A fold holds only unchanged blocks, so what Current leaves out is the article's own.
      const parts = removedParts(placed);
      for (const part of parts) {
        part.hidden = shown !== "diff";
      }
      file.removed.push(...parts);
    }
    return placed;
  }

  /**
   * Draw a chunk in place of its spacer, joined to the chunks drawn on either side of it
   * where a change crosses from one into the other (`joinChanges`).
   * @param {Region} region
   * @param {Chunk} chunk
   */
  function mountChunk(region, chunk) {
    const spacer = chunk.spacer;
    if (spacer === null) {
      return;
    }
    chunk.spacer = null;
    spacers.delete(spacer);
    chunkObserver?.unobserve(spacer);
    const before = /** @type {HTMLElement | null} */ (spacer.previousElementSibling);
    const after = /** @type {HTMLElement | null} */ (spacer.nextElementSibling);
    const placed = chunkRows(region, chunk);
    spacer.replaceWith(...placed);
    markJoins(placed);
    joinChanges([before, ...placed, after]);
    if (region.top && shown !== "diff") {
      applyShow(region.file);
    }
  }

  // Draw a run's chunks up to the one that holds block *index*, so the rows above it are
  // drawn at their own heights and a link can go to it.
  /** @param {Region} region @param {number} index */
  function mountThrough(region, index) {
    for (const chunk of region.chunks) {
      mountChunk(region, chunk);
      if (chunk.end > index) {
        break;
      }
    }
  }

  /**
   * A fold's bar and group (`foldExpander` in diff-fold.js): the diff's own fold, opening
   * to its blocks, and closed again when its view is drawn again unless the reader opened
   * it.
   * @param {FileView} file
   * @param {Fold} fold
   * @returns {FoldView}
   */
  function foldView(file, fold) {
    const { count } = fold;
    const blocks = `block${count === 1 ? "" : "s"}`;
    // Read by the bar's label, which the bar draws as it is made.
    const status = { failed: false };
    /** @type {FoldView} */
    const view = {
      fold,
      region: null,
      status,
      expander: foldExpander({
        id: `${file.rendered.id}-fold-${fold.at}`,
        expanded: false,
        // A bar whose blocks did not load says so, and a press asks again (docs/design-
        // system-messages.md, "Degrade Gracefully"; docs/design-system.md, "Refresh,
        // Retry, and Reload Page").
        label: (expanded) =>
          expanded
            ? `Hide ${count} ${blocks}`
            : status.failed
              ? `Could not load ${count} unchanged ${blocks}. Retry`
              : `${count} unchanged ${blocks}`,
        onToggle: (expanded) => toggleFold(file, view, expanded),
        groupClass: "diff-markdown-fold",
      }),
    };
    view.expander.control.dataset.span = `${fold.at}-${fold.at + count}`;
    file.foldViews.set(fold.at, view);
    if (
      file.openFolds.has(fold.at) &&
      file.model !== null &&
      holds(file.model, fold.at, fold.at + count)
    ) {
      view.expander.set(true);
    }
    return view;
  }

  /**
   * Open or close a fold: open, its blocks are drawn into its group, once the file holds
   * them; a withheld fold's are asked for first (`blocks=`).
   * @param {FileView} file
   * @param {FoldView} view
   * @param {boolean} expanded
   */
  function toggleFold(file, view, expanded) {
    const { fold, expander } = view;
    if (!expanded) {
      file.openFolds.delete(fold.at);
      for (const chunk of view.region?.chunks ?? []) {
        if (chunk.spacer !== null) {
          chunkObserver?.unobserve(chunk.spacer);
          spacers.delete(chunk.spacer);
        }
      }
      view.region = null;
      expander.group.replaceChildren();
      return;
    }
    file.openFolds.add(fold.at);
    view.status.failed = false;
    const model = /** @type {Model} */ (file.model);
    if (holds(model, fold.at, fold.at + fold.count)) {
      fillFold(file, view);
      return;
    }
    // The file's progress mark shows while the blocks are asked for (`askMore`).
    expander.control.setAttribute("aria-busy", "true");
    askFold(file, fold).then(
      () => {
        expander.control.removeAttribute("aria-busy");
        if (!disposed && expander.expanded() && file.foldViews.get(fold.at) === view) {
          deps.mutate(() => fillFold(file, view));
        }
      },
      (error) => {
        expander.control.removeAttribute("aria-busy");
        if (!disposed) {
          console.warn("metabrowser diff: a fold's blocks did not load", error);
          // Closed again, its bar says why, unless the reader closed it meanwhile.
          if (expander.expanded()) {
            view.status.failed = true;
            expander.set(false);
          }
        }
      },
    );
  }

  /** @param {FileView} file @param {FoldView} view */
  function fillFold(file, view) {
    if (view.region !== null) {
      return;
    }
    const { at, count } = view.fold;
    /** @type {Unit[]} */
    const units = Array.from({ length: count }, (_, offset) => ({
      kind: "block",
      index: at + offset,
    }));
    view.region = fillRegion(file, view.expander.group, units, false);
    observeSpacers(file);
  }

  /**
   * A withheld fold's blocks, asked for once however many wait for them.
   * @param {FileView} file
   * @param {Fold} fold
   * @returns {Promise<void>}
   */
  function askFold(file, fold) {
    const key = `${fold.at}-${fold.at + fold.count}`;
    let asked = file.folding.get(key);
    if (asked === undefined) {
      asked = askMore(file, { blocks: key })
        .then((answer) => {
          const blocks = foldBlocks(answer, fold);
          if (blocks === null || file.model === null) {
            throw new Error("The server answered a fold with other blocks.");
          }
          for (const [offset, block] of blocks.entries()) {
            file.model.blocks[fold.at + offset] = block;
          }
        })
        .finally(() => file.folding.delete(key));
      file.folding.set(key, asked);
    }
    return asked;
  }

  /**
   * Draw what a link into a file's article goes to, *id*: its chunk and the ones before
   * it, and the fold that holds it, opened. Returns, when that waits for a withheld fold's
   * blocks, when it is drawn; otherwise null, and the link's own navigation finds it.
   * @param {FileView} file
   * @param {string} id
   * @returns {Promise<HTMLElement | null> | null}
   */
  function reveal(file, id) {
    const model = file.model;
    const top = file.top;
    if (model === null || top === null || elementWithId(file.rendered, id) !== null) {
      return null;
    }
    const index = blockOf(model, id);
    if (index < 0) {
      return null;
    }
    const fold =
      file.drawn === "concise"
        ? model.folds.find((each) => each.at <= index && index < each.at + each.count)
        : undefined;
    deps.mutate(() => mountThrough(top, fold?.at ?? index));
    const view = fold === undefined ? undefined : file.foldViews.get(fold.at);
    if (fold === undefined || view === undefined) {
      return null;
    }
    const inside = () => {
      if (view.region !== null) {
        const region = view.region;
        deps.mutate(() => mountThrough(region, blockOf(model, id)));
      }
    };
    if (holds(model, fold.at, fold.at + fold.count)) {
      view.expander.set(true);
      inside();
      return null;
    }
    view.expander.set(true);
    return askFold(file, fold).then(
      () =>
        new Promise((resolve) => {
          // After the fold's own fill, which its toggle asked for first.
          queueMicrotask(() => {
            inside();
            resolve(elementWithId(file.rendered, id));
          });
        }),
      () => null,
    );
  }

  // Source is what a file shows when it is not rendered, and nothing in its body says
  // so. A file the server refused keeps its chooser with its rendered chips unavailable,
  // for *reason*; one whose request failed, with no reason, keeps them to choose, which
  // asks again.
  /** @param {FileView} file @param {string | null} reason */
  function fallBack(file, reason) {
    deps.mutate(() => {
      file.state = reason === null ? "idle" : "unavailable";
      file.reason = reason ?? "";
      file.mode = "source";
      file.holding = false;
      drawControl(file);
      draw(file);
    });
    checkFirstScreen();
  }

  /** @param {FileView} file @param {Mode} mode */
  function select(file, mode) {
    if (disposed || file.mode === mode || (isRendered(mode) && file.state === "unavailable")) {
      return;
    }
    deps.mutate(() => {
      file.mode = mode;
      file.holding = false;
      if (isRendered(mode)) {
        file.retryAt = 0;
      }
      drawControl(file);
      if (file.state === "ready") {
        refresh(file);
      }
      draw(file);
    });
    pump();
  }

  // Printing draws every chunk not yet drawn, so the page prints whole, holding the
  // reader's place as the chunks above it take their own heights.
  function mountAll() {
    if (disposed || spacers.size === 0) {
      return;
    }
    deps.mutate(() => {
      for (const { region, chunk } of [...spacers.values()]) {
        mountChunk(region, chunk);
      }
    });
  }

  /**
   * Draw the chunk that holds block *index* of a file's article, in its own run and in an
   * open fold's, so a block the reader was looking at is drawn again where it was after
   * the view is drawn anew; the chunks around it wait for the reader as before.
   * @param {FileView} file
   * @param {number} index
   */
  function drawBlock(file, index) {
    const top = file.top;
    if (top === null) {
      return;
    }
    const holding = (/** @type {Region} */ region) => {
      const chunk = region.chunks.find((each) => each.start <= index && index < each.end);
      if (chunk !== undefined) {
        mountChunk(region, chunk);
      }
    };
    holding(top);
    // After the article's chunk, which draws the fold's bar and fills it when it is open.
    for (const view of file.foldViews.values()) {
      const { at, count } = view.fold;
      if (view.region !== null && at <= index && index < at + count) {
        holding(view.region);
      }
    }
  }

  return {
    /**
     * @param {{
     *   section: HTMLElement, bar: HTMLElement, end: HTMLElement, source: HTMLElement,
     *   id: string, format: RenderedFormat, unavailable?: string, gone?: boolean,
     *   onSource?: (shown: boolean) => void
     * }} input The file's section; its bar; the group at the bar's end, which the
     *   chooser ends, so it is at the bar's far end; its Source body; and the format it
     *   renders as (`renderedFormat`).
     *   *onSource* hears each change of whether the Source body shows, so the diff can
     *   leave its rows undrawn while the rendered view hides it.
     *   *unavailable* is why no projection is asked for the file, a sentence, for one
     *   whose changes the page has no patch of (`supportsRenderedChange`): it shows
     *   Source, which says the same, from the start. *gone* is a deleted file, which shows
     *   its Source body in Current.
     */
    add({ section, bar, end, source, id, format, unavailable, gone, onSource }) {
      const control = document.createElement("div");
      control.className = "diff-markdown-control";
      // Markdown is a KPress fragment; a tree is the structured plugin's own surface.
      const rendered = document.createElement(format === "markdown" ? "article" : "div");
      if (format === "markdown") {
        rendered.className = "kpress kpress-inert diff-markdown";
      } else {
        rendered.className = "diff-structured";
        ensureStructured();
      }
      rendered.id = `${source.id}-rendered`;
      const progress = document.createElement("span");
      progress.className = "diff-markdown-progress";
      progress.setAttribute("role", "status");
      const spinner = document.createElement("span");
      spinner.className = "spinner spinner-sm";
      spinner.setAttribute("aria-hidden", "true");
      const progressLabel = document.createElement("span");
      progressLabel.className = "sr-only";
      progress.append(spinner, progressLabel);
      const expand = document.createElement("button");
      expand.type = "button";
      expand.className = "diff-file-view";
      const fallback = document.createElement("div");
      fallback.className = "diff-availability";
      const fallbackMessage = document.createElement("span");
      fallbackMessage.setAttribute("role", "status");
      fallback.append(fallbackMessage, expand);
      /** @type {FileView} */
      const file = {
        section,
        source,
        rendered,
        progress,
        progressLabel,
        id,
        format,
        tree: null,
        control,
        mode: unavailable === undefined ? "rendered" : "source",
        expand,
        fallback,
        fallbackMessage,
        automaticView: null,
        expandedContext: false,
        forceFull: false,
        fullFailed: false,
        expanded: true,
        pending: false,
        holding: unavailable === undefined,
        retryAt: 0,
        retries: 0,
        model: null,
        build: null,
        drawn: null,
        top: null,
        foldViews: new Map(),
        openFolds: new Set(),
        folding: new Map(),
        asking: new Set(),
        upgrading: false,
        fetching: 0,
        removed: [],
        gone: gone === true,
        emptied: false,
        state: unavailable === undefined ? "idle" : "unavailable",
        reason: unavailable ?? "",
        onSource: onSource ?? null,
      };
      // A fragment link to a block not drawn yet draws it, and opens the fold that holds
      // it, before the browser looks; where that waits for the fold's blocks, the link
      // goes there once they are drawn.
      rendered.addEventListener("click", (event) => {
        const origin = /** @type {{closest?: (selector: string) => Element | null}} */ (
          event.target
        );
        const href = origin?.closest?.("a[href]")?.getAttribute("href") ?? "";
        if (!href.startsWith("#")) {
          return;
        }
        let target = href.slice(1);
        try {
          target = decodeURIComponent(target);
        } catch {
          // Not percent-encoded: the anchor as written.
        }
        const drawn = reveal(file, target);
        if (drawn !== null) {
          event.preventDefault();
          void drawn.then((element) => element?.scrollIntoView({ block: "start" }));
        }
      });
      // The progress mark leads the chooser, on the side of the bar's free space, so the
      // chooser stays where it is when the mark appears.
      bar.classList.add("diff-file-bar-markdown");
      expand.addEventListener("click", () => {
        deps.mutate(() => {
          file.fullFailed = false;
          if (shown === "diff") {
            file.expandedContext = !file.expandedContext;
          } else {
            file.forceFull = true;
          }
          refresh(file);
          draw(file);
        });
      });
      end.append(progress, control);
      source.before(fallback, rendered);
      files.set(section, file);
      unbinds.push(
        deps.controls.bind(control, {
          onChange(key, value, selectType) {
            if (
              key === source.id &&
              selectType === "one" &&
              (value === "rendered" || value === "source")
            ) {
              // The shared handler moves focus first. Repaint once that handler
              // returns, so its focus recovery finds the chips it acted on.
              queueMicrotask(() => select(file, /** @type {Mode} */ (value)));
            }
          },
        }),
      );
      drawControl(file);
      draw(file);
      return {
        /** @param {boolean} expanded */
        setExpanded(expanded) {
          file.expanded = expanded;
          draw(file);
          pump();
        },
      };
    },
    /** @param {Element | null} root */
    observe(root) {
      observed = true;
      if (files.size === 0) {
        settleFirstScreen();
        return;
      }
      holdTimer = later(release, deps.holdMs ?? LOADING_DELAY_MS);
      waitUntil = now() + (deps.waitMs ?? RENDERED_WAIT_MS);
      observer = new IntersectionObserver(
        (entries) => {
          if (disposed) {
            return;
          }
          /** @type {FileView[]} */
          const away = [];
          for (const entry of entries) {
            const file = files.get(/** @type {HTMLElement} */ (entry.target));
            if (file !== undefined) {
              if (entry.isIntersecting) {
                nearby.add(file);
              } else {
                nearby.delete(file);
                if (file.holding) {
                  away.push(file);
                }
              }
            }
          }
          // Only the files near the first screen wait; the rest draw Source now.
          if (!reported) {
            reported = true;
            for (const file of files.values()) {
              if (file.holding && !nearby.has(file) && !away.includes(file)) {
                away.push(file);
              }
            }
          }
          if (away.length > 0) {
            deps.mutate(() => {
              for (const file of away) {
                file.holding = false;
                draw(file);
              }
            });
          }
          pump();
          checkFirstScreen();
        },
        { root, rootMargin: `0px 0px ${LOOKAHEAD} 0px` },
      );
      for (const section of files.keys()) {
        observer.observe(section);
      }
      // A chunk is drawn as the reader comes within LOOKAHEAD of it, from above or below,
      // as a link or a find can put them past it.
      chunkObserver = new IntersectionObserver(
        (entries) => {
          if (disposed) {
            return;
          }
          /** @type {{region: Region, chunk: Chunk}[]} */
          const near = [];
          for (const entry of entries) {
            const found = entry.isIntersecting
              ? spacers.get(/** @type {HTMLElement} */ (entry.target))
              : undefined;
            if (found !== undefined) {
              near.push(found);
            }
          }
          if (near.length > 0) {
            // One hold of the reader's place for every chunk drawn at once.
            deps.mutate(() => {
              for (const { region, chunk } of near) {
                mountChunk(region, chunk);
              }
            });
          }
        },
        { root, rootMargin: `${LOOKAHEAD} 0px ${LOOKAHEAD} 0px` },
      );
      for (const spacer of spacers.keys()) {
        chunkObserver.observe(spacer);
      }
      const view =
        /** @type {{addEventListener?: Window["addEventListener"], removeEventListener?: Window["removeEventListener"]} | undefined} */ (
          globalThis.window
        );
      if (typeof view?.addEventListener === "function") {
        view.addEventListener("beforeprint", mountAll);
        unprint = () => view.removeEventListener?.("beforeprint", mountAll);
      }
    },
    firstScreen,
    /**
     * Draw block *index* of the file in *section* where its view keeps it undrawn: the
     * chunk that holds it. The diff asks this when it finds again the block at the pane's
     * top after a change drew the view anew, as `mutate` does (`drawnRows` in
     * diff-view.js), so the reader keeps that block's place rather than a chunk's.
     * @param {HTMLElement} section
     * @param {number} index
     */
    drawBlock(section, index) {
      const file = files.get(section);
      if (!disposed && file !== undefined) {
        drawBlock(file, index);
      }
    },
    /**
     * Apply the comparison mode without changing any file's format choice.
     * @param {"diff" | "current" | "full"} next
     */
    show(next) {
      if (disposed || (next === shown && (next !== "full" || explicitFull))) {
        return;
      }
      shown = next;
      explicitFull = shown === "full";
      for (const file of files.values()) {
        file.fullFailed = false;
        refresh(file);
        applyShow(file);
        draw(file);
      }
      pump();
    },
    /**
     * Make every link to a file of the head plain text, in what is drawn: the page learned
     * that the server serves another pin, at which those addresses open other files. What
     * is drawn later asks *isTarget*, which says so itself.
     */
    closeHeadLinks() {
      for (const file of files.values()) {
        for (const link of file.rendered.querySelectorAll('a[href^="/view/"]')) {
          link.removeAttribute("href");
        }
      }
    },
    dispose() {
      disposed = true;
      settleFirstScreen();
      observer?.disconnect();
      chunkObserver?.disconnect();
      unprint?.();
      unprint = undefined;
      active?.controller.abort();
      if (active !== null) {
        active.file.progress.classList.remove("mb-delayed-loading");
      }
      for (const handle of [holdTimer, retryTimer, waitTimer]) {
        if (handle !== undefined) {
          cancel(handle);
        }
      }
      for (const unbind of unbinds.splice(0)) {
        unbind();
      }
      for (const file of files.values()) {
        for (const controller of file.asking) {
          controller.abort();
        }
        file.asking.clear();
        file.tree?.dispose();
        file.tree = null;
      }
      spacers.clear();
      files.clear();
      nearby.clear();
    },
  };
}

/**
 * The element inside *root* whose `id` is *id*, found without a selector, so any id is
 * one.
 * @param {Element} root
 * @param {string} id
 * @returns {HTMLElement | null}
 */
function elementWithId(root, id) {
  for (const child of root.children) {
    if (child.getAttribute("id") === id) {
      return /** @type {HTMLElement} */ (child);
    }
    const found = elementWithId(child, id);
    if (found !== null) {
      return found;
    }
  }
  return null;
}
