// The load exclusion rule for exp-060 and exp-062, applied to rows before any result
// in them is read.
//
//   node exp-060-062-load-filter.mjs ROWS.jsonl [--max-load 12] [--out JUDGED.jsonl]
//
// A back-to-back pair is excluded when any run in it saw a one-minute load average above
// --max-load at its start or at the start of any of its measured transitions (or, for a
// levels-probe row, at its start or at its measured landing). A pair is also left out of
// the judged rows when it is incomplete: a run refused, or a condition missing. The rule
// was set on 2026-11-12, after other sessions' disk work raised the load to about 250,
// and before any result of either round was read. Excluded rows stay in the committed
// samples as recorded; --out writes only the rows of the pairs that are judged.
//
// It prints one line per pair: its key, its runs, the highest load it saw, and whether it
// is judged. It reads only a row's series, pair, condition, run, validity, and loads.

import fs from "node:fs";
import { parseArgs } from "node:util";

const { values, positionals } = parseArgs({
  allowPositionals: true,
  options: { "max-load": { type: "string", default: "12" }, out: { type: "string" } },
});
const maxLoad = Number(values["max-load"]);
const rows = fs
  .readFileSync(positionals[0], "utf8")
  .split("\n")
  .filter(Boolean)
  .map((line) => JSON.parse(line));

const pairKey = (row) =>
  row.pair_key ?? `${row.series ?? row.instrument_series ?? "probe"}#${row.pair}`;
const loadsOf = (row) => {
  const out = [];
  if (Array.isArray(row.load_start)) {
    out.push(row.load_start[0]);
  }
  if (typeof row.load1 === "number") {
    out.push(row.load1);
  }
  if (typeof row.load1_landing === "number") {
    out.push(row.load1_landing);
  }
  for (const journey of row.journeys ?? []) {
    for (const t of journey.transitions ?? []) {
      if (typeof t.load1 === "number") {
        out.push(t.load1);
      }
    }
  }
  return out.filter((v) => typeof v === "number");
};
const isValid = (row) => row.valid !== false;

const pairs = new Map();
for (const row of rows) {
  const key = pairKey(row);
  if (!pairs.has(key)) {
    pairs.set(key, []);
  }
  pairs.get(key).push(row);
}
const conditions = [...new Set(rows.map((r) => r.condition))].sort();
const judged = [];
for (const [key, list] of pairs) {
  const loads = list.flatMap(loadsOf);
  const max = loads.length ? Math.max(...loads) : null;
  const complete =
    conditions.every((c) => list.some((r) => r.condition === c && isValid(r))) &&
    list.every(isValid);
  const reasons = [];
  if (max === null || max > maxLoad) {
    reasons.push(`load ${max} above ${maxLoad}`);
  }
  if (!complete) {
    reasons.push("incomplete (a run refused or a condition missing)");
  }
  const runs = list.map((r) => `${r.condition}#${r.run ?? r.pair}${isValid(r) ? "" : " refused"}`);
  console.log(
    `${key}\t${runs.join(", ")}\tmax load ${max}\t${reasons.length ? `EXCLUDED: ${reasons.join("; ")}` : "judged"}`,
  );
  if (!reasons.length) {
    judged.push(...list);
  }
}
if (values.out) {
  fs.writeFileSync(values.out, judged.map((r) => `${JSON.stringify(r)}\n`).join(""));
}
