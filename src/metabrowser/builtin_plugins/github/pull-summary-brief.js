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
// answered in 2 ms on a running server, and in 0.8 to 1.3 s on one just started at a load
// average of 38 to 94, behind its first requests.
//
// Which head it is for: a list names the commit it was listed for. The page draws it only
// for the head it knows, the comparison's or the core's, or for any while it knows none;
// another head's line is never shown, so a pushed pull request waits for its own counts.

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
 * The brief line's source for one page.
 *
 * @param {{
 *   read(number: number, signal: AbortSignal): Promise<{status: number, body: unknown}>,
 *   ready(): Promise<((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null>,
 *   changed(): void,
 *   index?: import("./change-lines.js").BoundedIndex<import("./row-lines.js").RowLineOutcome>,
 * }} deps *read* asks the route for one pull request; *ready* loads what the line is painted
 * with, the diff plugin's styles and the changed-files tree, and answers the tree's status
 * breakdown; *changed* repaints the row once the line is here.
 */
export function createSummaryBrief(deps) {
  const index = deps.index ?? documentRowLines;
  const controller = new AbortController();
  /** @type {import("./row-lines.js").FilesSummary | null} */
  let summary = null;
  /** @type {((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null} */
  let breakdown = null;
  let asked = false;
  let painted = false;

  /** @param {import("./row-lines.js").FilesSummary | null | undefined} found */
  function take(found) {
    if (
      controller.signal.aborted ||
      found == null ||
      found.state !== "listed" ||
      typeof found.files !== "number"
    ) {
      return;
    }
    summary = found;
  }

  return Object.freeze({
    /**
     * The page for pull request *number* of *source*, null while unknown, mounts: its line
     * from the document's memory, or one read. Asked once a page; later calls take a line the
     * Pulls rows drew since, and ask nothing.
     *
     * @param {number} number
     * @param {string | null} source
     */
    want(number, source) {
      if (controller.signal.aborted) {
        return;
      }
      if (summary === null && source !== null) {
        take(index.get(rowLineKey(source, number))?.summary);
      }
      if (asked) {
        return;
      }
      asked = true;
      const known = summary !== null;
      void Promise.all([
        known
          ? Promise.resolve(null)
          : deps.read(number, controller.signal).then(
              (answer) => answer,
              () => null,
            ),
        deps.ready().catch(() => null),
      ]).then(([answer, loaded]) => {
        if (controller.signal.aborted) {
          return;
        }
        breakdown = loaded;
        const body = /** @type {{rows?: unknown} | null} */ (answer?.body ?? null);
        if (answer?.status === 200 && Array.isArray(body?.rows)) {
          take(body.rows.find((row) => isFilesSummary(row) && row.number === number));
        }
        painted = true;
        if (summary !== null) {
          deps.changed();
        }
      });
    },
    /**
     * The line's sums for *head*, the head the page knows, or any for null; null when there
     * is none, it is another head's, or what it is painted with has not loaded.
     *
     * @param {string | null} head
     * @returns {import("./row-lines.js").FilesSummary | null}
     */
    summary(head) {
      if (!painted || summary === null || (head !== null && summary.head !== head)) {
        return null;
      }
      return summary;
    },
    /** The status breakdown the line is painted with, once loaded. */
    breakdown() {
      return breakdown;
    },
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
 * @param {import("./row-lines.js").FilesSummary} summary
 * @param {((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null} breakdown
 * @returns {HTMLElement}
 */
export function briefLine(mb, h, summary, breakdown) {
  const files = summary.files ?? 0;
  return h("div", { class: "diff-summary github-pull-summary-brief" }, [
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
    ...mb.changeLineNodes(mb.changeLine(rowLineInput(summary, breakdown)), { spoken: ", " }),
  ]);
}

export { PULL_FILES_SUMMARY_ROUTE };
