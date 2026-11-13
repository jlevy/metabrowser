// The gate's verdicts from sample records, without a browser: `make test` in apps/macos
// runs it with `node --test`.
import assert from "node:assert/strict";
import { test } from "node:test";
import { markdown, summarize } from "./summary.mjs";

/**
 * @typedef {import("./summary.mjs").CaseSummary} CaseSummary
 * @typedef {import("./summary.mjs").Engine} Engine
 * @typedef {import("./summary.mjs").Sample} Sample
 */

const OPEN = "open (ms)";

/**
 * One measured sample; `error` makes it a failed one, which records no metrics.
 * @param {Engine} engine
 * @param {number | null} pair
 * @param {Record<string, number>} values
 * @param {{ error?: string | null, caseName?: string }} [options]
 * @returns {Sample}
 */
function sample(engine, pair, values, { error = null, caseName = "source" } = {}) {
  return {
    case: caseName,
    engine,
    pair,
    warmup: pair === null,
    error,
    metrics: error
      ? []
      : Object.entries(values).map(([name, value]) => ({ name, value, gated: true })),
  };
}

/**
 * Both engines in each of `ids`, WebKit at `ratio` times Chrome's 100 ms.
 * @param {number[]} ids
 */
function measured(ids, ratio = 1.1, caseName = "source") {
  return ids.flatMap((pair) => [
    sample("chrome", pair, { [OPEN]: 100 }, { caseName }),
    sample("webkit", pair, { [OPEN]: 100 * ratio }, { caseName }),
  ]);
}

/** @param {CaseSummary[]} summary */
function row(summary, name = OPEN, caseName = "source") {
  const found = summary.find((entry) => entry.case === caseName)?.rows.find((r) => r.name === name);
  assert.ok(found, `no row ${name} in ${caseName}`);
  return found;
}

test("every requested pair under 1.3x passes, and one over fails", () => {
  assert.equal(row(summarize(measured([0, 1, 2]), { pairs: 3 })).verdict, "pass");
  const over = [...measured([0, 1]), ...measured([2], 1.5)];
  assert.equal(row(summarize(over, { pairs: 3 })).verdict, "FAIL");
});

test("a pair under the timer floor in both engines is not judged", () => {
  const samples = [0, 1].flatMap((pair) => [
    sample("chrome", pair, { [OPEN]: 1 }),
    sample("webkit", pair, { [OPEN]: 3 }),
  ]);
  assert.equal(row(summarize(samples, { pairs: 2 })).verdict, "under 5 ms");
});

test("one engine's failed sample leaves the pair, and the metric, incomplete", () => {
  const samples = [
    ...measured([0, 1]),
    sample("chrome", 2, { [OPEN]: 100 }),
    sample("webkit", 2, {}, { error: "webkit-driver exited with 1" }),
  ];
  const summary = summarize(samples, { pairs: 3 });
  assert.equal(row(summary).verdict, "incomplete");
  assert.deepEqual(summary[0].failures, ["webkit pair 3: webkit-driver exited with 1"]);
});

test("both engines failing one pair leaves the metric incomplete, not passing", () => {
  const samples = [
    ...measured([0, 1, 2, 3]),
    sample("chrome", 4, {}, { error: "Chrome did not open its DevTools port" }),
    sample("webkit", 4, {}, { error: "webkit-driver exited with 1" }),
  ];
  const summary = summarize(samples, { pairs: 5 });
  assert.equal(row(summary).verdict, "incomplete");
  assert.deepEqual(row(summary).chrome, [100, 100, 100, 100, null]);
  assert.equal(summary[0].failures.length, 2);
});

test("a pair missing from a resumed or summarized run leaves the metric incomplete", () => {
  // The run asked for five pairs and its samples.jsonl stops after the third.
  const summary = summarize(measured([0, 1, 2]), { pairs: 5 });
  assert.equal(row(summary).verdict, "incomplete");
  assert.equal(summary[0].pairs, 3);
  assert.equal(summary[0].expected_pairs, 5);
  assert.match(markdown(summary, meta()), /### source \(3 of 5 pairs\)/);
});

test("a pair missing from the middle of a run leaves the metric incomplete", () => {
  const summary = summarize(measured([0, 2]), { pairs: 3 });
  assert.equal(row(summary).verdict, "incomplete");
  assert.deepEqual(row(summary).missing_pairs, [2]);
  assert.equal(summary[0].complete, false);
});

test("without a pair count, completeness is unknown and nothing passes", () => {
  // Pairs 1 and 3 of a run whose meta.json has no count: pair 2, and any after 3, may
  // be missing, and nothing here can tell.
  const summary = summarize(measured([0, 2]));
  assert.equal(row(summary).verdict, "pair count unknown");
  assert.equal(row(summary).complete, null);
  assert.equal(summary[0].complete, null);
  assert.equal(summary[0].expected_pairs, null);
  assert.match(
    markdown(summary, meta()),
    /### source \(2 pairs of an unknown number\)\n\n- Completeness unknown: /,
  );
});

test("an invalid pair count is treated as unknown", () => {
  for (const pairs of [0, -1, 2.5, "2", Number.NaN, null]) {
    const summary = summarize(measured([0, 1]), { pairs });
    assert.equal(row(summary).verdict, "pair count unknown", `pairs: ${pairs}`);
    assert.equal(summary[0].complete, null, `pairs: ${pairs}`);
  }
});

test("a diagnostic case without a pair count says so", () => {
  const summary = summarize(measured([0]), { diagnostic: () => true });
  assert.equal(row(summary).verdict, "diagnostic, pair count unknown");
});

test("a metric both engines omit in one pair is incomplete", () => {
  const other = { "other (ms)": 50 };
  const samples = [
    ...[0, 1].flatMap((pair) => [
      sample("chrome", pair, { [OPEN]: 100, ...other }),
      sample("webkit", pair, { [OPEN]: 110, ...other }),
    ]),
    sample("chrome", 2, other),
    sample("webkit", 2, other),
  ];
  const summary = summarize(samples, { pairs: 3 });
  assert.equal(row(summary).verdict, "incomplete");
  assert.equal(row(summary, "other (ms)").verdict, "pass");
});

test("a value that is not a finite number counts as missing", () => {
  const samples = [
    ...measured([0, 1]),
    sample("chrome", 2, { [OPEN]: 100 }),
    sample("webkit", 2, { [OPEN]: Number.NaN }),
  ];
  assert.equal(row(summarize(samples, { pairs: 3 })).verdict, "incomplete");
});

test("a failed warm-up does not count against the measured pairs", () => {
  const samples = [
    sample("chrome", null, {}, { error: "warm-up failed" }),
    sample("webkit", null, { [OPEN]: 100 }),
    ...measured([0, 1]),
  ];
  const summary = summarize(samples, { pairs: 2 });
  assert.equal(row(summary).verdict, "pass");
  assert.deepEqual(summary[0].failures, ["chrome warm-up: warm-up failed"]);
});

test("a requested case with no sample is listed as unmeasured", () => {
  const summary = summarize(measured([0, 1]), { pairs: 2, cases: ["source", "binary"] });
  const binary = summary.find((entry) => entry.case === "binary");
  assert.ok(binary, "the unmeasured case is missing from the summary");
  assert.equal(binary.pairs, 0);
  assert.equal(binary.complete, false);
  assert.match(markdown(summary, meta()), /### binary \(0 of 2 pairs\)\n\n- Not measured/);
});

test("a diagnostic case's incomplete metric says so", () => {
  const summary = summarize(measured([0]), { pairs: 2, diagnostic: () => true });
  assert.equal(row(summary).verdict, "diagnostic, incomplete");
});

test("a complete case says it is complete", () => {
  assert.equal(summarize(measured([0, 1]), { pairs: 2 })[0].complete, true);
  assert.equal(summarize(measured([0]), { pairs: 2 })[0].complete, false);
});

function meta() {
  return {
    started: "start",
    finished: "end",
    machine: "machine",
    macos: "26",
    chrome: "Chrome",
    webkit: "1",
    metab: "metab",
    commit: "abc",
    load_start: [1, 1, 1],
    load_end: [1, 1, 1],
  };
}
