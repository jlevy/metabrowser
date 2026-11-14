// exp-079: the readings the committed samples do not keep, derived from the judged pairs'
// full rows (the harness's runs file, which holds local paths and stays in .bench).
// One JSON line per judged run, for H91 (c)'s evidence as exp-085 declared it:
//
//   node exp-079-derive.mjs JUDGED_RUNS.jsonl OUT.jsonl
//
// - readyAfterLastInputMs: skim.held_arrow_down's ready after the last input (E1, E2);
// - lastSelectToReadyMs: the last fileNavigation:selectToReady span the skim recorded, the
//   final row's select to ready (E2);
// - longTaskTotalMs and loafMaxBlockingMs: the skim's long-task time and its longest
//   animation frame's blocking time (E2);
// - blankFrames and placeholderVisibleFrames: the skim's (E3).
// The rows of H92 and H106 come from exp-065-instruments/derive-h92-h106.mjs, run as it is
// on the same file.
import fs from "node:fs";

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  throw new Error("usage: exp-079-derive.mjs JUDGED_RUNS.jsonl OUT.jsonl");
}
const rows = fs
  .readFileSync(input, "utf8")
  .split("\n")
  .filter(Boolean)
  .map((line) => JSON.parse(line));
const out = [];
for (const row of rows) {
  const t = (row.journeys ?? [])
    .flatMap((j) => j.transitions ?? [])
    .find((x) => x.id === "skim.held_arrow_down");
  const selects = (t?.spans ?? []).filter(([label]) => /fileNavigation:selectToReady/.test(label));
  out.push({
    kind: "skim",
    condition: row.condition,
    run: row.run,
    series: row.series,
    pair: row.pair,
    valid: row.valid,
    measured: Boolean(t),
    readyAfterLastInputMs: t?.readyAfterLastInputMs ?? null,
    lastSelectToReadyMs: selects.length ? selects[selects.length - 1][1] : null,
    selectToReadySpans: selects.length,
    longTaskTotalMs: t?.longTasks?.totalMs ?? null,
    loafMaxBlockingMs: t?.loaf?.maxBlockingMs ?? null,
    blankFrames: t?.blankFrames ?? null,
    placeholderVisibleFrames: t?.placeholderVisibleFrames ?? null,
  });
}
fs.writeFileSync(output, out.map((r) => `${JSON.stringify(r)}\n`).join(""));
console.log(`wrote ${out.length} skim row(s) to ${output}`);
