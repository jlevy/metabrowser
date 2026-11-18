// A pull request page's brief line in its Diff summary's row (mb-z8ea): "36 files changed ·
// 2 A, 3 D, 31 M · +2,076 −224", what the pull request's cached list of changed files sums
// to, drawn while the page reads the comparison its Diff summary is drawn from.
//
// The comparison waits on the record, which on a page whose record is not cached is the full
// record from GitHub, seconds away, and is then read from the store. The changed-files list
// is the one the Pulls row's change line sums (row-lines.js), usually cached already: the
// Pulls tab's prefetch lists the rows in view. So the page shows that line's sums in the
// row first, and the Diff summary replaces it in one step once read.
//
// Where it comes from, in order: the document's memory of the Pulls rows' lines
// (`documentRowLines`), so a page opened from a Pulls row asks nothing; else one
// `GET pull-files-summary?numbers=<n>` when the page mounts, the cache alone (no GitHub call,
// no Git), not behind the comparisons a page reads (row-lines.js reads behind them), since
// it is this page's own first screen. Measured 2026-11-17 in headless Chrome 152, that read
// answered in 2 ms on a running server, and in 0.66 to 1.27 s on one just started at a load
// average of 38 to 94, behind its first requests.
//
// Which pull request it is of: a list names the head it was listed for and its base, the
// comparison's base commit or GitHub's base branch. The page draws it only once it knows
// the head, and only for the head and base it shows (`briefMatches`); another head's or
// base's line is never shown, so a pushed or retargeted pull request waits for its own
// counts, and a line the Pulls lane knows is out of date is read again.

import {
  documentRowLines,
  isFilesSummary,
  PULL_FILES_SUMMARY_ROUTE,
  rowLineInput,
  rowLineKey,
} from "./row-lines.js";

/** The dot after the file count, a line's, said as a comma (diff-view.js, `LINE_SEPARATOR`). */
const SEPARATOR = Object.freeze({ separator: "·", spoken: ", " });

/**
 * A cached list's sums with what it was listed against, as `GET pull-files-summary` answers
 * them (pull_files_summary.py, `FilesSummaryWire`).
 *
 * @typedef {import("./row-lines.js").FilesSummary & {base: string | null, base_ref: string | null}} BriefSummary
 *
 * What the page shows its Diff summary for: the head, and the comparison's base, or with
 * no comparison yet the base branch; each null while unknown.
 * @typedef {{head: string | null, base: string | null, baseRef: string | null}} BriefFor
 */

/** @param {unknown} value @returns {value is BriefSummary} */
function isBriefSummary(value) {
  if (!isFilesSummary(value)) {
    return false;
  }
  const body = /** @type {Record<string, unknown>} */ (/** @type {unknown} */ (value));
  const named = (/** @type {unknown} */ part) => part === null || typeof part === "string";
  return named(body.base) && named(body.base_ref);
}

/**
 * Whether *summary* is the list of what the page shows (*shown*), so its counts are this
 * pull request's now and not an earlier head's or base's: the same head, and a local
 * comparison's list of the same base commit, or GitHub's list read for the same base
 * branch, as the changed-files route calls a list current (pull_files_route.py, `_state`).
 * Nothing is drawn before the page knows a head.
 *
 * @param {BriefSummary} summary
 * @param {BriefFor} shown
 */
export function briefMatches(summary, shown) {
  if (shown.head === null || summary.head !== shown.head) {
    return false;
  }
  if (summary.listed_from === "comparison") {
    return shown.base !== null && summary.base === shown.base;
  }
  if (summary.listed_from === "github") {
    return shown.baseRef !== null && summary.base_ref === shown.baseRef;
  }
  return false;
}

/**
 * The brief line's source for one page.
 *
 * @param {{
 *   read(number: number, signal: AbortSignal): Promise<{status: number, body: unknown}>,
 *   ready(): Promise<((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null>,
 *   changed(): void,
 *   index?: import("./change-lines.js").BoundedIndex<import("./row-lines.js").RowLineOutcome>,
 * }} deps *read* asks the route for one pull request, under the brief's signal, which
 * `dispose` aborts; *ready* loads what the line is painted with, the diff plugin's styles
 * and the changed-files tree, and answers the tree's status breakdown, asked only once a
 * listed line is in hand; *changed* repaints the row once the line can be drawn.
 */
export function createSummaryBrief(deps) {
  const index = deps.index ?? documentRowLines;
  const controller = new AbortController();
  /** @type {BriefSummary | null} */
  let summary = null;
  /** @type {((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null} */
  let breakdown = null;
  let asked = false;
  let painted = false;

  /** @param {unknown} found @returns {BriefSummary | null} */
  function listed(found) {
    return isBriefSummary(found) && found.state === "listed" && typeof found.files === "number"
      ? found
      : null;
  }

  /** @param {BriefSummary} found */
  async function paintWith(found) {
    breakdown = await deps.ready().catch(() => null);
    if (controller.signal.aborted) {
      return;
    }
    summary = found;
    painted = true;
    deps.changed();
  }

  return Object.freeze({
    /**
     * The page for pull request *number* of *source*, null while unknown, mounts: its line
     * from the document's memory of the Pulls rows' lines when a row drew it and nothing
     * since said its list changed, else one read. Asked once a page.
     *
     * @param {number} number
     * @param {string | null} source
     */
    want(number, source) {
      if (controller.signal.aborted || asked) {
        return;
      }
      asked = true;
      const seen = source === null ? undefined : index.get(rowLineKey(source, number));
      const kept =
        seen !== undefined && !seen.due && seen.head === seen.summary?.head
          ? listed(seen.summary)
          : null;
      if (kept !== null) {
        void paintWith(kept);
        return;
      }
      void deps.read(number, controller.signal).then(
        (answer) => {
          const body = /** @type {{rows?: unknown} | null} */ (answer.body);
          const found =
            answer.status === 200 && Array.isArray(body?.rows)
              ? listed(
                  body.rows.find(
                    (row) =>
                      isFilesSummary(row) &&
                      /** @type {{number: number}} */ (row).number === number,
                  ),
                )
              : null;
          if (found !== null && !controller.signal.aborted) {
            void paintWith(found);
          }
        },
        () => {},
      );
    },
    /**
     * The line's sums for what the page shows, or null: none listed, another head's or
     * base's (`briefMatches`), or what it is painted with not yet loaded.
     *
     * @param {BriefFor} shown
     * @returns {BriefSummary | null}
     */
    summary(shown) {
      if (!painted || summary === null || controller.signal.aborted) {
        return null;
      }
      return briefMatches(summary, shown) ? summary : null;
    },
    /** The status breakdown the line is painted with, once loaded. */
    breakdown() {
      return breakdown;
    },
    /** The page went: its read is stopped, and nothing more is drawn. */
    dispose() {
      controller.abort();
    },
  });
}

/**
 * The brief line, through the SDK's painters, as the Diff summary's header draws a line with
 * no files to open (diff-view.js, `renderDiffSummary`): the file count, bold, and its dot, one
 * item (`.diff-summary-group`), then the shell's brief change line, each dot said as a comma.
 * An empty slot where the header's chevron is keeps its words where the header's will be
 * (`.github-pull-summary-brief` in styles.css).
 *
 * @param {{
 *   countPartsNodes(parts: MetabrowserCountParts): Array<Node | string>,
 *   changeLine(change: MetabrowserChangeLineInput): MetabrowserChangeLine,
 *   changeLineNodes(line: MetabrowserChangeLine, options?: MetabrowserChangeLineOptions): Array<Node | string>,
 *   formatInteger(value: number): string,
 * }} mb
 * @param {(tag: string, attributes?: Record<string, string>, children?: Array<Node | string>) => HTMLElement} h
 * @param {BriefSummary} summary
 * @param {((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null} breakdown
 * @returns {HTMLElement}
 */
export function briefLine(mb, h, summary, breakdown) {
  const files = summary.files ?? 0;
  const line = mb.changeLine(rowLineInput(summary, breakdown));
  const words = `${mb.formatInteger(files)} ${files === 1 ? "file" : "files"} changed`;
  // Still a wait to a screen reader, as the placeholder it replaces is: the counts so far,
  // and that the summary of changes is on its way.
  return h(
    "div",
    {
      class: "diff-summary github-pull-summary-brief",
      role: "status",
      "aria-label": `${words}${line.label === "" ? "" : `: ${line.label}`}; loading the summary of changes`,
    },
    [
      h("span", { class: "diff-summary-chevron", "aria-hidden": "true" }),
      h("span", { class: "diff-summary-group" }, [
        h(
          "span",
          { class: "diff-summary-files" },
          mb.countPartsNodes([
            { number: mb.formatInteger(files) },
            ` ${files === 1 ? "file" : "files"} changed`,
          ]),
        ),
        ...mb.countPartsNodes([SEPARATOR]),
      ]),
      ...mb.changeLineNodes(line, { spoken: ", " }),
    ],
  );
}

export { PULL_FILES_SUMMARY_ROUTE };
