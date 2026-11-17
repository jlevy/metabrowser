// What a stack heading's brief change line (stack-lines.js) and a pull request row's
// (row-lines.js) share in the Pulls tab: the component's input, built one way from the
// sums the server answers, so a stack of one pull request draws the line its row draws, and
// the bounded memory each lane keeps of which answer is whose for the document.
//
// The sums are the server's one `accumulate` (pull_change_sums.py), and the line is the
// shell's one component, `metabrowser.changeLine` and `metabrowser.changeLineNodes`
// (docs/design-system.md, "Brief Change Line"); nothing here paints its parts.

/**
 * A change set as the server sums it: its files by status, each status in a pull request's
 * words with its count, and its line totals.
 *
 * @typedef {{
 *   statuses: {status: string, count: number}[],
 *   additions: number | null,
 *   deletions: number | null,
 * }} ChangeSums
 */

/**
 * A document's memory of one lane's answers, by key, the oldest out first past its bound.
 *
 * @template T
 * @typedef {Readonly<{
 *   get(key: string): T | undefined,
 *   set(key: string, value: T): void,
 *   clear(): void,
 * }>} BoundedIndex
 */

/**
 * The change line's input from *sums*: its statuses in the header's order, each with its
 * letter and word, from the changed-files tree's own breakdown, which the Diff summary's
 * header reads, and its line totals. With no tree, a line of its totals alone, as the Diff
 * summary's fallback line is.
 *
 * @param {ChangeSums} sums
 * @param {((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null} breakdown
 * @returns {MetabrowserChangeLineInput}
 */
export function changeLineInput(sums, breakdown) {
  const statuses =
    breakdown === null
      ? []
      : breakdown(
          sums.statuses.flatMap((entry) => Array.from({ length: entry.count }, () => entry.status)),
        );
  return { statuses, additions: sums.additions, deletions: sums.deletions };
}

/**
 * A bounded index of a lane's answers: a key set again is the newest, and past *limit*
 * keys the oldest goes.
 *
 * @template T
 * @param {number} limit
 * @returns {BoundedIndex<T>}
 */
export function createBoundedIndex(limit) {
  /** @type {Map<string, T>} */
  const entries = new Map();
  return Object.freeze({
    /** @param {string} key */
    get: (key) => entries.get(key),
    /** @param {string} key @param {T} value */
    set(key, value) {
      entries.delete(key);
      entries.set(key, value);
      if (entries.size > limit) {
        entries.delete(/** @type {string} */ (entries.keys().next().value));
      }
    },
    clear: () => entries.clear(),
  });
}
