// The WebKit gate's verdicts: per-pair ratios, medians, and a verdict for each metric of
// each case, from a run's sample records. Pure, so summary.test.mjs runs it without a
// browser; run.mjs calls it at the end of a run and for --summarize.

/**
 * @typedef {"chrome" | "webkit"} Engine
 * @typedef {{ name: string, value: unknown, gated: boolean }} Metric
 * @typedef {{
 *   case: string, engine: Engine, pair: number | null, warmup: boolean,
 *   error: string | null, metrics: Metric[]
 * }} Sample The fields of a samples.jsonl record that the summary reads.
 * @typedef {{
 *   name: string, gated: boolean, chrome: (number | null)[], webkit: (number | null)[],
 *   ratios: number[], chrome_median: number | null, webkit_median: number | null,
 *   median_ratio: number | null, max_ratio: number | null, verdict: string,
 *   judged_pairs: number, complete: boolean | null, missing_pairs: number[]
 * }} Row
 * @typedef {{
 *   case: string, diagnostic: boolean, pairs: number, expected_pairs: number | null,
 *   complete: boolean | null, rows: Row[], failures: string[]
 * }} CaseSummary
 * @typedef {{
 *   started: string, finished?: string, machine: string, macos: string, chrome: string,
 *   webkit: string, metab: string, commit: string, load_start: number[],
 *   load_end?: number[]
 * }} RunMeta The fields of meta.json that the Markdown names.
 */

export const PASS_RATIO = 1.3;
// WebKit coarsens performance.now() to 1 ms (Chrome: 0.1 ms), so a pair whose two times
// are both under five of those steps has no meaningful ratio. It is reported, not judged.
export const TIMER_FLOOR_MS = 5;

/**
 * @param {readonly unknown[]} values
 * @returns {number | null}
 */
export const median = (values) => {
  const sorted = values.filter((value) => typeof value === "number").sort((a, b) => a - b);
  if (sorted.length === 0) {
    return null;
  }
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

/**
 * @param {unknown} value
 * @param {number} [digits]
 */
export const fixed = (value, digits = 1) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "–";

/** @type {readonly Engine[]} */
const ENGINES = ["chrome", "webkit"];

/**
 * A measurement: a finite number. Anything else, NaN included, is a missing one.
 * @param {unknown} value
 * @returns {value is number}
 */
const isValue = (value) => typeof value === "number" && Number.isFinite(value);

/**
 * A sample's metrics by name; a name recorded twice keeps its last value.
 * @param {Sample | undefined} sample
 * @returns {Map<string, unknown>}
 */
const metricValues = (sample) =>
  new Map((sample?.metrics ?? []).map((metric) => [metric.name, metric.value]));

/**
 * A pair count a run can be judged against: a whole number, at least one.
 * @param {unknown} value
 * @returns {value is number}
 */
const isPairCount = (value) =>
  typeof value === "number" && Number.isSafeInteger(value) && value >= 1;

const UNKNOWN = "pair count unknown";

/**
 * Each case's rows. `pairs` is the number of pairs the run asked for (meta.json), and
 * `cases` the cases it asked for; `diagnostic(caseName)` says whether a case is a
 * diagnostic one.
 *
 * A gated metric is judged only when both engines measured it in every pair the run
 * asked for. A failed sample, a pair that never ran, or a metric one or both engines
 * left out of a pair makes it incomplete, whatever the other pairs say.
 *
 * Without a valid `pairs`, a pair missing from the middle or the end of the run cannot be
 * told from one that was never asked for, so completeness is unknown (null) and no gated
 * metric is judged: its verdict is "pair count unknown".
 *
 * @param {readonly Sample[]} samples
 * @param {{ pairs?: unknown, cases?: readonly string[], diagnostic?: (caseName: string) => boolean }} [options]
 * @returns {CaseSummary[]}
 */
export function summarize(samples, { pairs, cases = [], diagnostic = () => false } = {}) {
  const known = isPairCount(pairs);
  const requested = known ? pairs : 0;
  /** @type {CaseSummary[]} */
  const summary = [];
  for (const caseName of new Set([...cases, ...samples.map((sample) => sample.case)])) {
    /** @type {Map<number, Partial<Record<Engine, Sample>>>} */
    const byPair = new Map();
    for (const sample of samples) {
      if (sample.case !== caseName || sample.warmup || sample.pair === null) {
        continue;
      }
      const pair = byPair.get(sample.pair) ?? {};
      pair[sample.engine] = sample;
      byPair.set(sample.pair, pair);
    }
    // Every pair the run asked for, and any other a sample names.
    const pairIds = [...new Set([...Array(requested).keys(), ...byPair.keys()])].sort(
      (a, b) => a - b,
    );
    const perPair = pairIds.map((id) => ({
      id,
      chrome: metricValues(byPair.get(id)?.chrome),
      webkit: metricValues(byPair.get(id)?.webkit),
    }));
    /** @type {string[]} */
    const metricNames = [];
    /** @type {Map<string, boolean>} */
    const gatedByName = new Map();
    for (const id of pairIds) {
      for (const engine of ENGINES) {
        for (const metric of byPair.get(id)?.[engine]?.metrics ?? []) {
          if (!gatedByName.has(metric.name)) {
            metricNames.push(metric.name);
            gatedByName.set(metric.name, metric.gated);
          }
        }
      }
    }
    const rows = metricNames.map((name) => {
      const isGated = gatedByName.get(name) ?? false;
      const cells = perPair.map((pair) => ({
        id: pair.id,
        chrome: pair.chrome.get(name),
        webkit: pair.webkit.get(name),
      }));
      const both = cells.flatMap((cell) =>
        isValue(cell.chrome) && isValue(cell.webkit)
          ? [{ id: cell.id, chrome: cell.chrome, webkit: cell.webkit }]
          : [],
      );
      const missing = cells
        .filter((cell) => !(isValue(cell.chrome) && isValue(cell.webkit)))
        .map((cell) => cell.id + 1);
      const complete = known ? pairIds.length > 0 && missing.length === 0 : null;
      const ratios = both.map((cell) =>
        cell.chrome > 0 ? cell.webkit / cell.chrome : cell.webkit > 0 ? Infinity : 1,
      );
      const judged = both
        .filter(
          (cell) => !name.endsWith("(ms)") || Math.max(cell.chrome, cell.webkit) >= TIMER_FLOOR_MS,
        )
        .map((cell) => (cell.chrome > 0 ? cell.webkit / cell.chrome : Infinity));
      const chrome = cells.map((cell) => (isValue(cell.chrome) ? cell.chrome : null));
      const webkit = cells.map((cell) => (isValue(cell.webkit) ? cell.webkit : null));
      /** @type {Row} */
      const row = {
        name,
        gated: isGated,
        chrome,
        webkit,
        ratios: ratios.map((ratio) => Math.round(ratio * 100) / 100),
        chrome_median: median(chrome),
        webkit_median: median(webkit),
        median_ratio: median(ratios),
        max_ratio: ratios.length ? Math.max(...ratios) : null,
        verdict: !isGated
          ? "reported"
          : !known
            ? UNKNOWN
            : !complete
              ? "incomplete"
              : judged.length === 0
                ? `under ${TIMER_FLOOR_MS} ms`
                : judged.every((ratio) => ratio < PASS_RATIO)
                  ? "pass"
                  : "FAIL",
        judged_pairs: judged.length,
        complete,
        missing_pairs: missing,
      };
      return row;
    });
    const isDiagnostic = diagnostic(caseName);
    for (const row of rows) {
      if (isDiagnostic && row.verdict !== "reported") {
        row.verdict =
          row.verdict === "incomplete" || row.verdict === UNKNOWN
            ? `diagnostic, ${row.verdict}`
            : `diagnostic, ${row.verdict === "FAIL" ? "over" : "under"} ${PASS_RATIO}x`;
      }
    }
    const failures = samples
      .filter((entry) => entry.case === caseName && entry.error)
      .map(
        (entry) =>
          `${entry.engine}${entry.warmup || entry.pair === null ? " warm-up" : ` pair ${entry.pair + 1}`}: ${entry.error}`,
      );
    const everySample = pairIds.every((id) =>
      ENGINES.every((engine) => {
        const sample = byPair.get(id)?.[engine];
        return sample !== undefined && !sample.error;
      }),
    );
    summary.push({
      case: caseName,
      diagnostic: isDiagnostic,
      pairs: byPair.size,
      expected_pairs: known ? pairIds.length : null,
      complete: known
        ? pairIds.length > 0 && everySample && rows.every((row) => !row.gated || row.complete)
        : null,
      rows,
      failures,
    });
  }
  return summary;
}

/**
 * The summary as the Markdown tables summary.md holds.
 * @param {readonly CaseSummary[]} summary
 * @param {RunMeta} meta
 */
export function markdown(summary, meta) {
  const lines = [
    `Run ${meta.started} to ${meta.finished ?? "(unfinished)"}: ${meta.machine}; macOS ${meta.macos};`,
    `${meta.chrome}; WebKit ${meta.webkit}; ${meta.metab}; commit ${meta.commit};`,
    `load average ${meta.load_start.join(", ")} at the start` +
      (meta.load_end ? ` and ${meta.load_end.join(", ")} at the end.` : "."),
    "",
  ];
  for (const { case: caseName, pairs, expected_pairs: expected, rows, failures } of summary) {
    const counted =
      expected === null
        ? `${pairs} pairs of an unknown number`
        : pairs === expected
          ? `${pairs} pairs`
          : `${pairs} of ${expected} pairs`;
    lines.push(`### ${caseName} (${counted})`, "");
    if (expected === null) {
      lines.push(
        "- Completeness unknown: the run records no valid pair count, so a missing pair " +
          "cannot be told from one never asked for, and nothing is judged.",
        "",
      );
    }
    if (pairs === 0) {
      lines.push("- Not measured: the run recorded no sample of this case.", "");
      continue;
    }
    for (const failure of failures) {
      lines.push(`- Failed sample, ${failure}`);
    }
    if (failures.length) {
      lines.push("");
    }
    lines.push("| Metric | Chrome median | WebKit median | Pair ratios | Verdict |");
    lines.push("| --- | ---: | ---: | --- | --- |");
    for (const row of rows) {
      const ratios = row.gated ? row.ratios.map((ratio) => fixed(ratio, 2)).join(", ") : "";
      const verdict =
        row.gated && row.missing_pairs.length
          ? `${row.verdict}: no pair ${row.missing_pairs.join(", ")}`
          : row.verdict;
      lines.push(
        `| ${row.name} | ${fixed(row.chrome_median)} | ${fixed(row.webkit_median)} | ${ratios} | ${verdict} |`,
      );
    }
    lines.push("");
  }
  return lines.join("\n");
}
