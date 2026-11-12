// The WebKit gate's verdicts: per-pair ratios, medians, and a verdict for each metric of
// each case, from a run's sample records. Pure, so summary.test.mjs runs it without a
// browser; run.mjs calls it at the end of a run and for --summarize.

export const PASS_RATIO = 1.3;
// WebKit coarsens performance.now() to 1 ms (Chrome: 0.1 ms), so a pair whose two times
// are both under five of those steps has no meaningful ratio. It is reported, not judged.
export const TIMER_FLOOR_MS = 5;

export const median = (values) => {
  const sorted = values.filter((value) => typeof value === "number").sort((a, b) => a - b);
  if (sorted.length === 0) {
    return null;
  }
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

export const fixed = (value, digits = 1) =>
  typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "–";

const ENGINES = ["chrome", "webkit"];

/** A measurement: a finite number. Anything else, NaN included, is a missing one. */
const isValue = (value) => typeof value === "number" && Number.isFinite(value);

/** A sample's metrics by name; a name recorded twice keeps its last value. */
const metricValues = (sample) =>
  new Map((sample?.metrics ?? []).map((metric) => [metric.name, metric.value]));

/**
 * Each case's rows. `pairs` is the number of pairs the run asked for (meta.json), and
 * `cases` the cases it asked for; `diagnostic(caseName)` says whether a case is a
 * diagnostic one.
 *
 * A gated metric is judged only when both engines measured it in every pair the run
 * asked for. A failed sample, a pair that never ran, or a metric one or both engines
 * left out of a pair makes it incomplete, whatever the other pairs say.
 */
export function summarize(
  samples,
  { pairs: requested = 0, cases = [], diagnostic = () => false } = {},
) {
  const summary = [];
  for (const caseName of new Set([...cases, ...samples.map((sample) => sample.case)])) {
    const byPair = new Map();
    for (const sample of samples.filter((entry) => entry.case === caseName && !entry.warmup)) {
      const pair = byPair.get(sample.pair) ?? {};
      pair[sample.engine] = sample;
      byPair.set(sample.pair, pair);
    }
    // Every pair the run asked for, and any other a sample names.
    const pairIds = [...new Set([...Array(requested).keys(), ...byPair.keys()])].sort(
      (a, b) => a - b,
    );
    const values = new Map(
      pairIds.map((id) => [
        id,
        Object.fromEntries(
          ENGINES.map((engine) => [engine, metricValues(byPair.get(id)?.[engine])]),
        ),
      ]),
    );
    const metricNames = [];
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
      const isGated = gatedByName.get(name);
      const cells = pairIds.map((id) => ({
        id,
        chrome: values.get(id).chrome.get(name),
        webkit: values.get(id).webkit.get(name),
      }));
      const both = cells.filter((cell) => isValue(cell.chrome) && isValue(cell.webkit));
      const missing = cells.filter((cell) => !both.includes(cell)).map((cell) => cell.id + 1);
      const complete = pairIds.length > 0 && missing.length === 0;
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
      return {
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
    });
    const isDiagnostic = diagnostic(caseName);
    for (const row of rows) {
      if (isDiagnostic && row.verdict !== "reported") {
        row.verdict =
          row.verdict === "incomplete"
            ? "diagnostic, incomplete"
            : `diagnostic, ${row.verdict === "FAIL" ? "over" : "under"} ${PASS_RATIO}x`;
      }
    }
    const failures = samples
      .filter((entry) => entry.case === caseName && entry.error)
      .map(
        (entry) =>
          `${entry.engine}${entry.warmup ? " warm-up" : ` pair ${entry.pair + 1}`}: ${entry.error}`,
      );
    const everySample = pairIds.every((id) =>
      ENGINES.every((engine) => byPair.get(id)?.[engine] && !byPair.get(id)[engine].error),
    );
    summary.push({
      case: caseName,
      diagnostic: isDiagnostic,
      pairs: byPair.size,
      expected_pairs: pairIds.length,
      complete:
        pairIds.length > 0 && everySample && rows.every((row) => !row.gated || row.complete),
      rows,
      failures,
    });
  }
  return summary;
}

export function markdown(summary, meta) {
  const lines = [
    `Run ${meta.started} to ${meta.finished ?? "(unfinished)"}: ${meta.machine}; macOS ${meta.macos};`,
    `${meta.chrome}; WebKit ${meta.webkit}; ${meta.metab}; commit ${meta.commit};`,
    `load average ${meta.load_start.join(", ")} at the start` +
      (meta.load_end ? ` and ${meta.load_end.join(", ")} at the end.` : "."),
    "",
  ];
  for (const { case: caseName, pairs, expected_pairs: expected, rows, failures } of summary) {
    const counted = pairs === expected ? `${pairs} pairs` : `${pairs} of ${expected} pairs`;
    lines.push(`### ${caseName} (${counted})`, "");
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
